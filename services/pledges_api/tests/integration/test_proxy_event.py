"""The Mangum proxy path: a real API Gateway HTTP API v2 event → ``app.handler``.

Every other integration test drives the app via ``TestClient`` (pure ASGI), which
never exercises Mangum's event translation. This locks that a single
``ANY /{proxy+}`` HTTP API v2 proxy event is reconstructed so FastAPI's routes match
(path, query, body, and the Lambda-proxy response envelope Mangum returns).
"""
import json
import os

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_aws

from app import handler


def _create_table(dynamodb):
    table = dynamodb.create_table(
        TableName="test-pledges-table",
        KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "pledgeID", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        # The by-email / upsert paths query the EmailIndex GSI (mirrors the real schema).
        GlobalSecondaryIndexes=[
            {
                "IndexName": "EmailIndex",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.put_item(
        Item={
            "pledgeID": "STATS",
            "pledged_total": 228150,
            "contributors_count": 19,
            "monthly_total": 12200,
        }
    )
    return table


def _event(method, path, body=None, query="", claims=None):
    """A minimal API Gateway HTTP API (payload format v2.0) proxy event.

    Pass ``claims`` to simulate a request that passed the Cognito JWT authorizer — API
    Gateway puts the verified token claims at ``requestContext.authorizer.jwt.claims``
    (AUTH3), which Mangum surfaces to the app on the ASGI scope.
    """
    request_context = {
        "http": {
            "method": method,
            "path": path,
            "protocol": "HTTP/1.1",
            "sourceIp": "1.2.3.4",
        },
        "stage": "$default",
    }
    if claims is not None:
        request_context["authorizer"] = {"jwt": {"claims": claims}}
    return {
        "version": "2.0",
        "routeKey": "ANY /{proxy+}",
        "rawPath": path,
        "rawQueryString": query,
        "headers": {"content-type": "application/json"},
        "requestContext": request_context,
        "body": body,
        "isBase64Encoded": False,
    }


@pytest.fixture(scope="function")
def seeded():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield


class TestProxyEvent:
    def test_get_stats_routes_through_mangum(self, seeded):
        resp = handler(_event("GET", "/stats"), None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["pledged_total"] == 228150
        assert body["contributors_count"] == 19

    def test_post_calculate_body_passthrough(self, seeded):
        # Body + POST routing survive the Mangum translation; CONFIG absent → default
        # goal. total_impact = 2 people * €100 * 1 (one-time) = 200.
        resp = handler(
            _event(
                "POST",
                "/calculate",
                body=json.dumps({"people": 2, "amount": 100, "is_monthly": False}),
            ),
            None,
        )
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["total_impact"] == 200

    def test_unknown_path_is_404(self, seeded):
        resp = handler(_event("GET", "/does-not-exist"), None)
        assert resp["statusCode"] == 404

    def test_options_preflight_is_2xx_not_405(self, seeded):
        # The browser's CORS preflight (OPTIONS) is forwarded through the ANY
        # /{proxy+} route. It must get a 2xx so the browser allows the real POST —
        # without the handler FastAPI returns 405, which fails the preflight.
        # (API Gateway adds the actual CORS headers in front of this.)
        resp = handler(_event("OPTIONS", "/calculate"), None)
        assert resp["statusCode"] == 204

    def test_create_pledge_keys_to_jwt_claim_not_body_email(self, seeded):
        # AUTH3: the pledge must be keyed to the *verified* token email, ignoring any
        # email the body claims — otherwise one user could pledge under another's email.
        resp = handler(
            _event(
                "POST",
                "/pledges",
                body=json.dumps(
                    {
                        "email": "attacker@evil.example",
                        "amount": 100,
                        "is_monthly": False,
                    }
                ),
                claims={"email": "real@user.example"},
            ),
            None,
        )
        assert resp["statusCode"] == 201

        # The stored pledge belongs to the authenticated user, not the body's email.
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-pledges-table")
        owner = table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq("real@user.example"),
        )["Items"]
        assert len(owner) == 1
        impostor = table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq("attacker@evil.example"),
        )["Items"]
        assert impostor == []

    def test_by_email_uses_jwt_claim_not_query_param(self, seeded):
        # Seed a pledge owned by the authenticated user.
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-pledges-table")
        table.put_item(
            Item={
                "pledgeID": "pledge-1",
                "email": "real@user.example",
                "amount": 250,
                "is_monthly": False,
                "campaign_total": 250,
            }
        )

        # Even with a different ?email= in the query, the claim decides whose pledge is
        # returned — the query param is ignored when a verified token is present.
        resp = handler(
            _event(
                "GET",
                "/pledges/by-email",
                query="email=someone@else.example",
                claims={"email": "real@user.example"},
            ),
            None,
        )
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["pledges"][0]["amount"] == 250

    def test_create_pledge_rejects_authenticated_request_without_email_claim(self, seeded):
        # An authenticated request whose token carries no `email` claim (e.g. an access
        # token — the gateway authorizer admits it) must FAIL CLOSED (401), never fall
        # back to the attacker-controlled body email.
        resp = handler(
            _event(
                "POST",
                "/pledges",
                body=json.dumps(
                    {"email": "victim@user.example", "amount": 100, "is_monthly": False}
                ),
                claims={"sub": "00000000-0000-0000-0000-000000000000"},
            ),
            None,
        )
        assert resp["statusCode"] == 401

        # Nothing was written under the body's email.
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-pledges-table")
        victim = table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq("victim@user.example"),
        )["Items"]
        assert victim == []

    def test_by_email_rejects_authenticated_request_without_email_claim(self, seeded):
        resp = handler(
            _event(
                "GET",
                "/pledges/by-email",
                query="email=victim@user.example",
                claims={"sub": "00000000-0000-0000-0000-000000000000"},
            ),
            None,
        )
        assert resp["statusCode"] == 401
