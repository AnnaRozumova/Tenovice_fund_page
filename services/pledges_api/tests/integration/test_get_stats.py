"""Integration tests for the running-totals handler.

``GET /stats`` returns the ``STATS`` row (campaign running totals). The row is
absent until the first pledge is created, so on a fresh table the handler must
fall back to zeros and still answer **200** — not crash with a 500 (regression
guard for P1). Tests run against a moto-mocked DynamoDB table.
"""
import importlib
import json
import os

import boto3
import pytest
from moto import mock_aws


def _create_table(dynamodb):
    return dynamodb.create_table(
        TableName="test-pledges-table",
        KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture(scope="function")
def stats_handler():
    """Table seeded with a STATS row + a freshly reloaded handler under moto."""
    with mock_aws():
        from handlers import get_stats

        importlib.reload(get_stats)

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

        yield get_stats.handler


@pytest.fixture(scope="function")
def empty_stats_handler():
    """No STATS row (fresh table) — the handler must fall back to zeros."""
    with mock_aws():
        from handlers import get_stats

        importlib.reload(get_stats)

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        yield get_stats.handler


def _call(handler):
    resp = handler({}, None)
    return resp["statusCode"], json.loads(resp["body"])


class TestGetStats:
    def test_returns_stats_row(self, stats_handler):
        status, body = _call(stats_handler)

        assert status == 200
        assert body["pledged_total"] == 228150
        assert body["contributors_count"] == 19
        assert body["monthly_total"] == 12200

    def test_empty_table_returns_zeros_not_500(self, empty_stats_handler):
        # Regression guard for P1: absent STATS row → 200 with zeros, not a 500.
        status, body = _call(empty_stats_handler)

        assert status == 200
        assert body["pledged_total"] == 0
        assert body["contributors_count"] == 0
        assert body["monthly_total"] == 0
