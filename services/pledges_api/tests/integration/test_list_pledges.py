"""Integration tests for ``GET /pledges`` (the public anonymous list), via the app.

The list must exclude the sentinel rows (``STATS`` totals, ``CONFIG`` settings) — they
are not pledges. Before the fix only ``STATS`` was filtered, so the ``CONFIG`` row
(added in C1) leaked into the public list as a phantom zero-amount pledge.
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
    # Both sentinel rows, as in a real deployed table (STATS from the start, CONFIG since C1).
    table.put_item(
        Item={
            "pledgeID": "STATS",
            "pledged_total": 0,
            "contributors_count": 0,
            "monthly_total": 0,
        }
    )
    table.put_item(
        Item={
            "pledgeID": "CONFIG",
            "current_balance": 320000,
            "fundraising_goal": 2700000,
            "breakdown": [],
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


class TestListPledges:
    def test_sentinels_excluded_when_no_pledges(self, client_and_table):
        """With only STATS + CONFIG seeded, the public list is empty (no phantom row)."""
        client, _ = client_and_table
        resp = client.get("/pledges")
        assert resp.status_code == 200
        assert resp.json() == {"pledges": []}

    def test_real_pledge_listed_sentinels_excluded(self, client_and_table):
        """A real pledge is returned; the STATS/CONFIG sentinels are not, nor is the email."""
        client, table = client_and_table
        table.put_item(
            Item={
                "pledgeID": "abc-123",
                "email": "friend@example.com",
                "amount": 500,
                "is_monthly": False,
                "campaign_total": 500,
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
        resp = client.get("/pledges")
        assert resp.status_code == 200
        pledges = resp.json()["pledges"]
        assert len(pledges) == 1
        assert pledges[0]["amount"] == 500
        assert pledges[0]["is_monthly"] is False
        # anonymous list: identity fields are never exposed
        assert "email" not in pledges[0]
        assert "pledgeID" not in pledges[0]
