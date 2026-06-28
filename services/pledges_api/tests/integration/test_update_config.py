"""Integration tests for ``POST /config`` (Phase C2), via the FastAPI app.

The admin write path is guarded by a single shared secret (D6): a bearer token
compared in constant time against ``ADMIN_SECRET``. It fails closed (no secret
configured → 401) and, when authorized, writes the editable ``CONFIG`` row.
"""
import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app import app

SECRET = "s3cret-token"


def _create_table(dynamodb):
    return dynamodb.create_table(
        TableName="test-pledges-table",
        KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture(scope="function")
def client_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        os.environ["ADMIN_SECRET"] = SECRET

        yield TestClient(app), table

        os.environ.pop("ADMIN_SECRET", None)


def _valid_body():
    return {
        "current_balance": 400000,
        "fundraising_goal": 2700000,
        "breakdown": [
            {"key": "new_gompa", "amount": 1200000},
            {"key": "sangha_house", "amount": 1200000},
            {"key": "basecamp_north", "amount": 300000},
        ],
    }


def _auth(secret):
    return {"Authorization": f"Bearer {secret}"} if secret is not None else {}


class TestUpdateConfigAuth:
    def test_missing_auth_returns_401(self, client_and_table):
        client, table = client_and_table
        resp = client.post("/config", json=_valid_body())
        assert resp.status_code == 401
        # nothing written
        assert "Item" not in table.get_item(Key={"pledgeID": "CONFIG"})

    def test_empty_bearer_returns_401(self, client_and_table):
        client, _ = client_and_table
        resp = client.post("/config", json=_valid_body(), headers=_auth(""))
        assert resp.status_code == 401

    def test_wrong_secret_returns_401(self, client_and_table):
        client, _ = client_and_table
        resp = client.post("/config", json=_valid_body(), headers=_auth("nope"))
        assert resp.status_code == 401

    def test_fails_closed_when_no_secret_configured(self, client_and_table):
        client, _ = client_and_table
        os.environ.pop("ADMIN_SECRET", None)
        # even the "right" secret is rejected when none is configured server-side
        resp = client.post("/config", json=_valid_body(), headers=_auth(SECRET))
        assert resp.status_code == 401


class TestUpdateConfigWrite:
    def test_correct_secret_writes_config_row(self, client_and_table):
        client, table = client_and_table
        resp = client.post("/config", json=_valid_body(), headers=_auth(SECRET))
        assert resp.status_code == 200

        item = table.get_item(Key={"pledgeID": "CONFIG"})["Item"]
        assert item["current_balance"] == 400000
        assert item["fundraising_goal"] == 2700000
        keys = [b["key"] for b in item["breakdown"]]
        assert keys == ["new_gompa", "sangha_house", "basecamp_north"]

    def test_invalid_body_returns_400(self, client_and_table):
        client, table = client_and_table
        bad = _valid_body()
        bad["breakdown"] = bad["breakdown"][:2]  # missing basecamp_north
        resp = client.post("/config", json=bad, headers=_auth(SECRET))
        assert resp.status_code == 400
        assert "Item" not in table.get_item(Key={"pledgeID": "CONFIG"})

    def test_invalid_json_returns_400(self, client_and_table):
        client, _ = client_and_table
        resp = client.post("/config", content="{not json", headers=_auth(SECRET))
        assert resp.status_code == 400
