"""Integration tests for the get-pledge-by-email handler.

Added in Phase B (B1): the endpoint must return only the caller's own pledge,
projected to an explicit allowlist of fields — never the raw DynamoDB item, and
never another person's record.
"""
import importlib
import json
import os

import boto3
import pytest
from moto import mock_aws


def _create_table(dynamodb):
    table = dynamodb.create_table(
        TableName="test-pledges-table",
        KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "pledgeID", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "EmailIndex",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


@pytest.fixture(scope="function")
def handler_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        from handlers import get_pledge_by_email

        importlib.reload(get_pledge_by_email)

        yield get_pledge_by_email.handler, table


def _seed_pledge(table, email):
    table.put_item(
        Item={
            "pledgeID": "pledge-1",
            "email": email,
            "contributors_count": 2,
            "amount": 100,
            "is_monthly": False,
            "campaign_total": 100,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-01T00:00:00Z",
            "message": "hi",
        }
    )


def _call(handler, email):
    return handler({"queryStringParameters": {"email": email}}, None)


class TestGetPledgeByEmail:
    def test_returns_only_allowlisted_fields(self, handler_and_table):
        handler, table = handler_and_table
        _seed_pledge(table, "owner@example.com")

        response = _call(handler, "owner@example.com")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # The caller's own pledge fields are present...
        assert body["amount"] == 100
        assert body["message"] == "hi"

        # ...but internal bookkeeping fields never leak.
        assert "pledgeID" not in body
        assert "created_at" not in body
        assert "updated_at" not in body
        assert "name" not in body
        # H1: the email is no longer echoed back — the caller supplied it themselves.
        assert "email" not in body
        # B4: contributors_count is no longer part of the pledge; even a legacy row
        # that still stores it must not surface it (dropped from the allowlist).
        assert "contributors_count" not in body

    def test_lookup_is_case_insensitive(self, handler_and_table):
        handler, table = handler_and_table
        _seed_pledge(table, "owner@example.com")

        response = _call(handler, "Owner@Example.COM")
        assert response["statusCode"] == 200
        # The pledge is found regardless of case (email is matched lowercased); the
        # email isn't echoed (H1), so assert on a returned field instead.
        assert json.loads(response["body"])["amount"] == 100

    def test_unknown_email_returns_404(self, handler_and_table):
        handler, _ = handler_and_table
        response = _call(handler, "nobody@example.com")
        assert response["statusCode"] == 404

    def test_missing_email_returns_400(self, handler_and_table):
        handler, _ = handler_and_table
        response = handler({"queryStringParameters": None}, None)
        assert response["statusCode"] == 400
