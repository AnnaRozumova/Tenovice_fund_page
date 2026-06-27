"""Integration tests for the get-config handler (Phase C1).

The editable campaign numbers (balance, goal, 3-direction breakdown) live in a
single ``CONFIG`` row. The handler returns documented defaults when the row is
absent, so the endpoint and the site work before the row is ever seeded.
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
def handler_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        from handlers import get_config

        importlib.reload(get_config)

        yield get_config.handler, table


class TestGetConfig:
    def test_returns_defaults_when_no_config_row(self, handler_and_table):
        handler, _ = handler_and_table

        resp = handler({}, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["current_balance"] == 320000
        assert body["fundraising_goal"] == 2700000
        keys = [item["key"] for item in body["breakdown"]]
        assert keys == ["new_gompa", "sangha_house", "basecamp_north"]

    def test_returns_stored_config_row(self, handler_and_table):
        handler, table = handler_and_table
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

        resp = handler({}, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["current_balance"] == 500000
        assert body["fundraising_goal"] == 3000000
        assert body["breakdown"][0]["amount"] == 1000000

    def test_amounts_serialize_as_integers(self, handler_and_table):
        handler, _ = handler_and_table

        body = json.loads(handler({}, None)["body"])
        assert isinstance(body["current_balance"], int)
        assert isinstance(body["fundraising_goal"], int)
        for item in body["breakdown"]:
            assert "key" in item
            assert isinstance(item["amount"], int)
