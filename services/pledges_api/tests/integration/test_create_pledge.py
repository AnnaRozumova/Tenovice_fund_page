"""Integration tests for ``POST /pledges`` (create/update upsert), via the app.

Phase B (B1): payloads no longer carry ``name``. B4: payloads no longer carry
``contributors_count`` either — a pledge is one person, so the STATS supporter tally
(still stored under ``contributors_count``) counts pledges: +1 per new pledge, +0 on
edit. Driven through FastAPI's ``TestClient`` against a moto-mocked table that mirrors
the real schema (PK ``pledgeID`` + ``EmailIndex`` GSI on ``email``).
"""
import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app import app


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
    table.put_item(
        Item={
            "pledgeID": "STATS",
            "pledged_total": 0,
            "contributors_count": 0,
            "monthly_total": 0,
            "updated_at": "2024-01-01T00:00:00Z",
        }
    )
    return table


@pytest.fixture(scope="function")
def client_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield TestClient(app), table


class TestCreatePledge:
    def test_create_one_time_pledge(self, client_and_table):
        client, table = client_and_table

        resp = client.post(
            "/pledges",
            json={
                "email": "john@example.com",
                "amount": 100,
                "is_monthly": False,
                "message": "Great cause!",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert "pledge_id" in body

        item = table.get_item(Key={"pledgeID": body["pledge_id"]})["Item"]
        assert "name" not in item
        assert "contributors_count" not in item
        assert item["email"] == "john@example.com"
        assert int(item["amount"]) == 100
        assert int(item["campaign_total"]) == 100

    def test_create_pledge_updates_stats(self, client_and_table):
        client, table = client_and_table

        resp = client.post(
            "/pledges",
            json={"email": "test@example.com", "amount": 75, "is_monthly": False},
        )
        assert resp.status_code == 201

        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["pledged_total"]) == 75
        # One pledge = one supporter (B4).
        assert int(stats["contributors_count"]) == 1

    def test_two_pledges_count_two_supporters(self, client_and_table):
        """B4: each distinct pledge adds exactly one supporter."""
        client, table = client_and_table

        for email in ("a@example.com", "b@example.com"):
            resp = client.post(
                "/pledges",
                json={"email": email, "amount": 50, "is_monthly": False},
            )
            assert resp.status_code == 201

        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["contributors_count"]) == 2

    def test_monthly_pledge_updates_monthly_total(self, client_and_table):
        client, table = client_and_table

        resp = client.post(
            "/pledges",
            json={
                "email": "monthly@example.com",
                "amount": 25,
                "is_monthly": True,
                "end_month": 12,
                "end_year": 2030,
            },
        )
        assert resp.status_code == 201

        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["monthly_total"]) == 25

    def test_second_post_same_email_updates_not_duplicates(self, client_and_table):
        """A returning pledger (same email) edits their pledge — no new record."""
        client, table = client_and_table

        first = {"email": "returning@example.com", "amount": 100, "is_monthly": False}
        assert client.post("/pledges", json=first).status_code == 201

        second = {**first, "amount": 250}
        assert client.post("/pledges", json=second).status_code == 200

        # Only one non-STATS row exists, and the amount reflects the edit.
        rows = [i for i in table.scan()["Items"] if i["pledgeID"] != "STATS"]
        assert len(rows) == 1
        assert int(rows[0]["amount"]) == 250

        # STATS reflects the new amount, not the sum of both.
        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["pledged_total"]) == 250
        assert int(stats["contributors_count"]) == 1

    def test_invalid_json(self, client_and_table):
        client, _ = client_and_table
        resp = client.post("/pledges", content="not valid json{")
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]

    def test_missing_amount(self, client_and_table):
        client, _ = client_and_table
        resp = client.post(
            "/pledges", json={"email": "john@example.com", "is_monthly": True}
        )
        assert resp.status_code == 400
        assert "amount" in resp.json()["error"]

    def test_email_normalized_to_lowercase(self, client_and_table):
        client, table = client_and_table
        resp = client.post(
            "/pledges",
            json={
                "email": "John.Doe@EXAMPLE.COM",
                "amount": 100,
                "is_monthly": False,
            },
        )
        item = table.get_item(Key={"pledgeID": resp.json()["pledge_id"]})["Item"]
        assert item["email"] == "john.doe@example.com"
