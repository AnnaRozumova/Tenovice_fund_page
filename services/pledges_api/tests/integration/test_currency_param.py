"""Integration tests for the ``?currency=`` boundary conversion (decision D22).

DynamoDB stores canonical CZK; the API converts to the requested currency on read and
normalizes the incoming amount to CZK on write. Seeded with a **clean rate of 25** so
the expected EUR values are exact. No param (or ``czk``) returns the stored koruna
unchanged; ``eur`` divides/multiplies by the rate. Counts and percentages are never
converted.
"""
import os
from decimal import Decimal

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app import app

RATE = 25


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
            "pledged_total": 250000,  # CZK
            "contributors_count": 4,
            "monthly_total": 5000,  # CZK
        }
    )
    table.put_item(
        Item={
            "pledgeID": "CONFIG",
            "current_balance": 2500000,  # CZK
            "fundraising_goal": 5000000,  # CZK
            "exchange_rate": RATE,
            "breakdown": [
                {"key": "new_gompa", "amount": 2000000},
                {"key": "sangha_house", "amount": 2000000},
                {"key": "basecamp_north", "amount": 1000000},
            ],
        }
    )
    table.put_item(
        Item={
            "pledgeID": "p1",
            "email": "owner@example.com",
            "amount": 2500,  # CZK
            "is_monthly": False,
            "campaign_total": 2500,  # CZK
            "created_at": "2026-01-01T00:00:00Z",
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


class TestStatsCurrency:
    def test_default_returns_canonical_czk(self, client_and_table):
        client, _ = client_and_table
        body = client.get("/stats").json()
        assert body["currency"] == "czk"
        assert body["pledged_total"] == 250000
        assert body["monthly_total"] == 5000
        assert body["contributors_count"] == 4

    def test_eur_converts_money_but_not_the_count(self, client_and_table):
        client, _ = client_and_table
        body = client.get("/stats", params={"currency": "eur"}).json()
        assert body["currency"] == "eur"
        assert body["pledged_total"] == 10000  # 250000 / 25
        assert body["monthly_total"] == 200  # 5000 / 25
        assert body["contributors_count"] == 4  # a count — never converted


class TestListPledgesCurrency:
    def test_eur_converts_amounts(self, client_and_table):
        client, _ = client_and_table
        body = client.get("/pledges", params={"currency": "eur"}).json()
        assert body["currency"] == "eur"
        assert len(body["pledges"]) == 1
        assert body["pledges"][0]["amount"] == 100  # 2500 / 25
        assert body["pledges"][0]["campaign_total"] == 100


class TestByEmailCurrency:
    def test_default_is_canonical_czk(self, client_and_table):
        client, _ = client_and_table
        body = client.get("/pledges/by-email", params={"email": "owner@example.com"}).json()
        assert body["currency"] == "czk"
        assert body["amount"] == 2500

    def test_eur_converts(self, client_and_table):
        client, _ = client_and_table
        body = client.get(
            "/pledges/by-email", params={"email": "owner@example.com", "currency": "eur"}
        ).json()
        assert body["currency"] == "eur"
        assert body["amount"] == 100  # 2500 / 25


class TestCalculateCurrency:
    def test_eur_normalizes_input_and_localizes_output(self, client_and_table):
        client, _ = client_and_table
        resp = client.post(
            "/calculate",
            params={"currency": "eur"},
            json={"people": 1, "amount": 100, "is_monthly": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["currency"] == "eur"
        # €100 in → 2500 CZK canonical → impact 2500 CZK → €100 back out.
        assert body["amount"] == 100
        assert body["total_impact"] == 100
        assert body["current_total"] == 10000  # 250000 / 25
        assert body["goal"] == 200000  # 5000000 / 25
        assert body["projected_total"] == 10100

    def test_eur_rounds_outputs_not_per_person_input(self, client_and_table):
        """Rounding only the outputs (not the per-person amount) keeps the simulator
        self-consistent: amount * people must equal total_impact even when the EUR→CZK
        conversion is fractional (25 EUR * 24.22 = 605.5 CZK, a .5 that would otherwise
        be rounded per person and amplified by the multiplier)."""
        client, table = client_and_table
        table.put_item(
            Item={
                "pledgeID": "CONFIG",
                "current_balance": 0,
                "fundraising_goal": 70000000,
                "exchange_rate": Decimal("24.22"),
                "breakdown": [],
            }
        )
        body = client.post(
            "/calculate",
            params={"currency": "eur"},
            json={"people": 100, "amount": 25, "is_monthly": False},
        ).json()
        assert body["currency"] == "eur"
        assert body["amount"] == 25
        # 25 EUR * 100 people, one-time = exactly 2500 EUR (no per-person rounding drift).
        assert body["total_impact"] == 2500


class TestCreatePledgeCurrency:
    def test_eur_amount_is_stored_as_canonical_czk(self, client_and_table):
        client, table = client_and_table
        resp = client.post(
            "/pledges",
            params={"currency": "eur"},
            json={"email": "new@example.com", "amount": 200, "is_monthly": False},
        )
        assert resp.status_code == 201
        item = table.get_item(Key={"pledgeID": resp.json()["pledge_id"]})["Item"]
        assert int(item["amount"]) == 5000  # 200 EUR * 25
        assert int(item["campaign_total"]) == 5000

    def test_czk_amount_is_stored_unchanged(self, client_and_table):
        client, table = client_and_table
        resp = client.post(
            "/pledges",
            json={"email": "czk@example.com", "amount": 300, "is_monthly": False},
        )
        assert resp.status_code == 201
        item = table.get_item(Key={"pledgeID": resp.json()["pledge_id"]})["Item"]
        assert int(item["amount"]) == 300
