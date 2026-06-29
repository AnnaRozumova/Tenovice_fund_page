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
from moto import mock_aws

from app import handler


def _create_table(dynamodb):
    table = dynamodb.create_table(
        TableName="test-pledges-table",
        KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
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


def _event(method, path, body=None, query=""):
    """A minimal API Gateway HTTP API (payload format v2.0) proxy event."""
    return {
        "version": "2.0",
        "routeKey": "ANY /{proxy+}",
        "rawPath": path,
        "rawQueryString": query,
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "1.2.3.4",
            },
            "stage": "$default",
        },
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
