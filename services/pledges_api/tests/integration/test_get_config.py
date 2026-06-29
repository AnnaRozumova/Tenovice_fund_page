"""Integration tests for ``GET /config`` (Phase C1), via the FastAPI app.

The editable campaign numbers (balance, goal, 3-direction breakdown) live in a
single ``CONFIG`` row. The endpoint returns documented defaults when the row is
absent, so the site works before the row is ever seeded.
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
def client_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield TestClient(app), table


class TestGetConfig:
    def test_returns_defaults_when_no_config_row(self, client_and_table):
        client, _ = client_and_table

        resp = client.get("/config")
        assert resp.status_code == 200
        body = resp.json()

        assert body["current_balance"] == 320000
        assert body["fundraising_goal"] == 2700000
        keys = [item["key"] for item in body["breakdown"]]
        assert keys == ["new_gompa", "sangha_house", "basecamp_north"]

    def test_returns_stored_config_row(self, client_and_table):
        client, table = client_and_table
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": 500000,
                "fundraising_goal": 3000000,
                "breakdown": [
                    {"key": "new_gompa", "amount": 1000000},
                    {"key": "sangha_house", "amount": 1000000},
                    {"key": "basecamp_north", "amount": 1000000},
                ],
            }
        )

        resp = client.get("/config")
        assert resp.status_code == 200
        body = resp.json()

        assert body["current_balance"] == 500000
        assert body["fundraising_goal"] == 3000000
        assert body["breakdown"][0]["amount"] == 1000000

    def test_amounts_serialize_as_integers(self, client_and_table):
        client, _ = client_and_table

        body = client.get("/config").json()
        assert isinstance(body["current_balance"], int)
        assert isinstance(body["fundraising_goal"], int)
        for item in body["breakdown"]:
            assert "key" in item
            assert isinstance(item["amount"], int)
