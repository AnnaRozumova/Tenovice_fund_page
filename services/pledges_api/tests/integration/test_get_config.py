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

        # Canonical defaults are in CZK now (D22): goal = clean 70M CZK (≈ €2.89M).
        assert body["current_balance"] == 7750400
        assert body["fundraising_goal"] == 70000000
        assert body["exchange_rate"] == 24.22
        assert body["currency"] == "czk"
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

    def test_currency_eur_converts_amounts_at_the_stored_rate(self, client_and_table):
        """D22: ?currency=eur divides canonical CZK by the rate; the rate is unchanged."""
        client, table = client_and_table
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": 2500000,  # CZK
                "fundraising_goal": 70000000,  # CZK
                "exchange_rate": 25,
                "breakdown": [
                    {"key": "new_gompa", "amount": 25000000},
                    {"key": "sangha_house", "amount": 25000000},
                    {"key": "basecamp_north", "amount": 20000000},
                ],
            }
        )

        body = client.get("/config", params={"currency": "eur"}).json()
        assert body["currency"] == "eur"
        assert body["current_balance"] == 100000  # 2,500,000 / 25
        assert body["fundraising_goal"] == 2800000  # 70,000,000 / 25
        assert body["breakdown"][0]["amount"] == 1000000  # 25,000,000 / 25
        # The rate itself is currency-independent — returned as stored, not converted.
        assert body["exchange_rate"] == 25

    def test_currency_eur_tolerates_breakdown_item_without_amount(self, client_and_table):
        """A hand-edited CONFIG breakdown item missing 'amount' must not 500 on the EUR
        path (the conversion skips it rather than raising KeyError)."""
        client, table = client_and_table
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": 100,
                "fundraising_goal": 200,
                "exchange_rate": 25,
                "breakdown": [{"key": "new_gompa"}],
            }
        )
        resp = client.get("/config", params={"currency": "eur"})
        assert resp.status_code == 200
        assert resp.json()["breakdown"][0]["key"] == "new_gompa"
