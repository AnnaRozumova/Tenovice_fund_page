"""Integration tests for ``GET /pledges/by-email`` (Phase M), via the FastAPI app.

Since Phase M (D23) the endpoint returns the caller's **own pledges as a list**, each
projected to an explicit allowlist plus its ``pledge_id`` (so the owner can address an
edit/delete). It must never return another person's record, never the raw item, and
(H1) never echo the email back. An account with no pledges gets an empty list, not 404.
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


def _seed_pledge(table, pledge_id, email, amount=100, created_at="2026-01-01T00:00:00Z"):
    table.put_item(
        Item={
            "pledgeID": pledge_id,
            "email": email,
            "contributors_count": 2,  # a legacy attribute — must never surface
            "amount": amount,
            "is_monthly": False,
            "campaign_total": amount,
            "created_at": created_at,
            "updated_at": "2026-02-01T00:00:00Z",
            "message": "hi",
        }
    )


def _get(client, email):
    return client.get("/pledges/by-email", params={"email": email})


class TestGetMyPledges:
    def test_returns_only_allowlisted_fields_plus_id(self, client_and_table):
        client, table = client_and_table
        _seed_pledge(table, "pledge-1", "owner@example.com")

        resp = _get(client, "owner@example.com")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["pledges"], list) and len(body["pledges"]) == 1
        pledge = body["pledges"][0]

        # The caller's own pledge fields are present, incl. the id (to edit/delete)...
        assert pledge["amount"] == 100
        assert pledge["message"] == "hi"
        assert pledge["pledge_id"] == "pledge-1"

        # ...but internal bookkeeping never leaks, and the email is not echoed (H1).
        assert "updated_at" not in pledge
        assert "name" not in pledge
        assert "email" not in pledge
        # A legacy row's contributors_count must not surface (dropped from allowlist).
        assert "contributors_count" not in pledge

    def test_returns_all_pledges_for_the_email(self, client_and_table):
        client, table = client_and_table
        _seed_pledge(table, "p-old", "owner@example.com", amount=100, created_at="2026-01-01T00:00:00Z")
        _seed_pledge(table, "p-new", "owner@example.com", amount=250, created_at="2026-03-01T00:00:00Z")
        _seed_pledge(table, "p-other", "someone-else@example.com", amount=999)

        body = _get(client, "owner@example.com").json()
        assert len(body["pledges"]) == 2
        # Newest first (sorted by created_at desc).
        assert [p["pledge_id"] for p in body["pledges"]] == ["p-new", "p-old"]
        # Never another person's pledge.
        assert all(p["amount"] != 999 for p in body["pledges"])

    def test_lookup_is_case_insensitive(self, client_and_table):
        client, table = client_and_table
        _seed_pledge(table, "pledge-1", "owner@example.com")

        body = _get(client, "Owner@Example.COM").json()
        assert len(body["pledges"]) == 1
        assert body["pledges"][0]["amount"] == 100

    def test_unknown_email_returns_empty_list(self, client_and_table):
        client, _ = client_and_table
        resp = _get(client, "nobody@example.com")
        assert resp.status_code == 200
        assert resp.json()["pledges"] == []

    def test_missing_email_returns_400(self, client_and_table):
        client, _ = client_and_table
        assert client.get("/pledges/by-email").status_code == 400
