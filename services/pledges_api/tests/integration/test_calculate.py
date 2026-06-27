"""Integration tests for the read-only simulator handler (Phase D2a).

``POST /calculate`` computes a what-if impact and a projection toward the goal,
reusing the shared pledge math (D8). It reads the ``STATS`` and ``CONFIG`` rows
but must **never write**. Tests run against a moto-mocked DynamoDB table.
"""
import importlib
import json
import os
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from domain.pledge_math import calculate_remaining_months


def _create_table(dynamodb):
    table = dynamodb.create_table(
        TableName="test-pledges-table",
        KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.put_item(
        Item={
            "pledgeID": "STATS",
            "pledged_total": 200000,
            "contributors_count": 19,
            "monthly_total": 0,
        }
    )
    table.put_item(
        Item={
            "pledgeID": "CONFIG",
            "current_balance": 200000,
            "fundraising_goal": 2000000,
            "breakdown": [
                {"key": "new_gompa", "amount": 1000000},
                {"key": "sangha_house", "amount": 800000},
                {"key": "basecamp_north", "amount": 200000},
            ],
        }
    )
    return table


@pytest.fixture(scope="function")
def calculate_handler():
    """Seeded table (STATS + CONFIG) + a freshly reloaded handler under moto."""
    with mock_aws():
        from handlers import calculate

        importlib.reload(calculate)

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        yield calculate.handler, table


@pytest.fixture(scope="function")
def empty_table_handler():
    """No STATS / CONFIG rows — the handler must fall back to 0 / default goal."""
    with mock_aws():
        from handlers import calculate

        importlib.reload(calculate)

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-pledges-table",
            KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        yield calculate.handler


def _call(handler, payload):
    resp = handler({"body": json.dumps(payload)}, None)
    return resp["statusCode"], json.loads(resp["body"])


class TestCalculate:
    def test_one_time_impact_and_projection(self, calculate_handler):
        handler, _ = calculate_handler

        status, body = _call(
            handler, {"people": 100, "amount": 100, "is_monthly": False}
        )

        assert status == 200
        # 100 people * €100, one-time → multiplier 1.
        assert body["total_impact"] == 10000
        assert body["monthly_effect"] == 0
        assert body["remaining_months"] == 0
        assert body["current_total"] == 200000
        assert body["goal"] == 2000000
        assert body["projected_total"] == 210000
        # 200000/2000000 = 10 %; 210000/2000000 = 10.5 %; delta = 0.5 %.
        assert body["baseline_progress_pct"] == 10
        assert body["projected_progress_pct"] == pytest.approx(10.5)
        assert body["scenario_progress_pct"] == pytest.approx(0.5)

    def test_monthly_impact_uses_remaining_months(self, calculate_handler):
        handler, _ = calculate_handler

        now = datetime.now(timezone.utc)
        # A ~12-month inclusive window from this month (handles year wrap).
        end_month = now.month
        end_year = now.year + 1
        months = calculate_remaining_months(end_month, end_year)

        status, body = _call(
            handler,
            {
                "people": 10,
                "amount": 50,
                "is_monthly": True,
                "end_month": end_month,
                "end_year": end_year,
            },
        )

        assert status == 200
        assert months == 13  # this month next year, inclusive
        assert body["remaining_months"] == months
        # 10 people * €50 * months.
        assert body["total_impact"] == 10 * 50 * months
        # Monthly extra is the whole group's per-month figure.
        assert body["monthly_effect"] == 10 * 50
        assert body["projected_total"] == 200000 + 10 * 50 * months

    def test_past_end_date_yields_zero_months_not_an_error(self, calculate_handler):
        handler, _ = calculate_handler

        status, body = _call(
            handler,
            {
                "people": 5,
                "amount": 50,
                "is_monthly": True,
                "end_month": 1,
                "end_year": 2000,
            },
        )

        # Not rejected — the simulation floors months at 0 (no campaign impact).
        assert status == 200
        assert body["remaining_months"] == 0
        assert body["total_impact"] == 0
        assert body["projected_total"] == body["current_total"]
        assert body["scenario_progress_pct"] == 0

    def test_calculate_does_not_write_anything(self, calculate_handler):
        handler, table = calculate_handler

        before = {i["pledgeID"]: i for i in table.scan()["Items"]}

        status, _ = _call(
            handler, {"people": 100, "amount": 500, "is_monthly": False}
        )
        assert status == 200

        after = {i["pledgeID"]: i for i in table.scan()["Items"]}
        assert after == before  # no rows added, STATS/CONFIG untouched

    def test_falls_back_to_defaults_when_rows_absent(self, empty_table_handler):
        handler = empty_table_handler

        status, body = _call(
            handler, {"people": 1, "amount": 1000, "is_monthly": False}
        )

        assert status == 200
        assert body["current_total"] == 0
        assert body["goal"] == 2700000  # get_config's documented default
        assert body["projected_total"] == 1000
        assert body["baseline_progress_pct"] == 0

    def test_amounts_serialize_as_integers(self, calculate_handler):
        handler, _ = calculate_handler

        _, body = _call(
            handler, {"people": 100, "amount": 100, "is_monthly": False}
        )
        for field in ("total_impact", "current_total", "goal", "projected_total"):
            assert isinstance(body[field], int)

    # --- validation ---

    def test_invalid_json(self, calculate_handler):
        handler, _ = calculate_handler
        resp = handler({"body": "not json{"}, None)
        assert resp["statusCode"] == 400
        assert "Invalid JSON" in json.loads(resp["body"])["error"]

    def test_missing_people_rejected(self, calculate_handler):
        handler, _ = calculate_handler
        status, body = _call(handler, {"amount": 100, "is_monthly": False})
        assert status == 400
        assert "people" in body["error"]

    def test_zero_people_rejected(self, calculate_handler):
        handler, _ = calculate_handler
        status, body = _call(
            handler, {"people": 0, "amount": 100, "is_monthly": False}
        )
        assert status == 400
        assert "people" in body["error"]

    def test_missing_amount_rejected(self, calculate_handler):
        handler, _ = calculate_handler
        status, body = _call(handler, {"people": 10, "is_monthly": False})
        assert status == 400
        assert "amount" in body["error"]

    def test_monthly_requires_end_date(self, calculate_handler):
        handler, _ = calculate_handler
        status, body = _call(
            handler, {"people": 10, "amount": 50, "is_monthly": True}
        )
        assert status == 400
        assert "end_month" in body["error"]
