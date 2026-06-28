"""Integration tests for ``GET /stats`` (running totals), via the FastAPI app.

The ``STATS`` row is absent until the first pledge, so on a fresh table the
endpoint must fall back to zeros and still answer **200** — not 500 (regression
guard for P1). Driven through FastAPI's ``TestClient`` against a moto-mocked table.
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
        AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture(scope="function")
def client_seeded():
    """Table seeded with a STATS row, under moto."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        table.put_item(
            Item={
                "pledgeID": "STATS",
                "pledged_total": 228150,
                "contributors_count": 19,
                "monthly_total": 12200,
            }
        )
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield TestClient(app)


@pytest.fixture(scope="function")
def client_empty():
    """No STATS row (fresh table) — the endpoint must fall back to zeros."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield TestClient(app)


class TestGetStats:
    def test_returns_stats_row(self, client_seeded):
        resp = client_seeded.get("/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pledged_total"] == 228150
        assert body["contributors_count"] == 19
        assert body["monthly_total"] == 12200

    def test_empty_table_returns_zeros_not_500(self, client_empty):
        # Regression guard for P1: absent STATS row → 200 with zeros, not a 500.
        resp = client_empty.get("/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pledged_total"] == 0
        assert body["contributors_count"] == 0
        assert body["monthly_total"] == 0
