"""Integration tests for ``GET /pledges/by-email`` (Phase B1), via the FastAPI app.

The endpoint must return only the caller's own pledge, projected to an explicit
allowlist of fields — never the raw DynamoDB item, never another person's record,
and (H1) never the email echoed back.
"""
import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app import app


def _create_table(dynamodb):
    return dynamodb.create_table(
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


@pytest.fixture(scope="function")
def client_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield TestClient(app), table


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


def _get(client, email):
    return client.get("/pledges/by-email", params={"email": email})


class TestGetPledgeByEmail:
    def test_returns_only_allowlisted_fields(self, client_and_table):
        client, table = client_and_table
        _seed_pledge(table, "owner@example.com")

        resp = _get(client, "owner@example.com")
        assert resp.status_code == 200
        body = resp.json()

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

    def test_lookup_is_case_insensitive(self, client_and_table):
        client, table = client_and_table
        _seed_pledge(table, "owner@example.com")

        resp = _get(client, "Owner@Example.COM")
        assert resp.status_code == 200
        # Found regardless of case (email matched lowercased); the email isn't echoed
        # (H1), so assert on a returned field instead.
        assert resp.json()["amount"] == 100

    def test_unknown_email_returns_404(self, client_and_table):
        client, _ = client_and_table
        assert _get(client, "nobody@example.com").status_code == 404

    def test_missing_email_returns_400(self, client_and_table):
        client, _ = client_and_table
        assert client.get("/pledges/by-email").status_code == 400
