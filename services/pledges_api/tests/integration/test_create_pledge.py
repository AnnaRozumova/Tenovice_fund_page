"""Integration tests for the create/update (upsert) pledge handler.

Rewritten in Phase B (B1): payloads no longer carry ``name``. B4: payloads no
longer carry ``contributors_count`` either — a pledge is one person, so the STATS
supporter tally (still stored under ``contributors_count``) counts pledges: +1 per
new pledge, +0 on edit. Tests run against a moto-mocked DynamoDB table that mirrors
the real schema (PK ``pledgeID`` + ``EmailIndex`` GSI on ``email``).
"""
import importlib
import json
import os

import boto3
import pytest
from moto import mock_aws


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
def dynamodb_table():
    with mock_aws():
        from handlers import create_pledge

        importlib.reload(create_pledge)

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        yield table, create_pledge.handler


class TestCreatePledgeHandler:
    def test_create_one_time_pledge(self, dynamodb_table):
        table, handler = dynamodb_table

        event = {
            "body": json.dumps(
                {
                    "email": "john@example.com",
                    "amount": 100,
                    "is_monthly": False,
                    "message": "Great cause!",
                }
            )
        }

        response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert "pledge_id" in body

        item = table.get_item(Key={"pledgeID": body["pledge_id"]})["Item"]
        assert "name" not in item
        assert "contributors_count" not in item
        assert item["email"] == "john@example.com"
        assert int(item["amount"]) == 100
        assert int(item["campaign_total"]) == 100

    def test_create_pledge_updates_stats(self, dynamodb_table):
        table, handler = dynamodb_table

        event = {
            "body": json.dumps(
                {
                    "email": "test@example.com",
                    "amount": 75,
                    "is_monthly": False,
                }
            )
        }

        assert handler(event, None)["statusCode"] == 201

        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["pledged_total"]) == 75
        # One pledge = one supporter (B4).
        assert int(stats["contributors_count"]) == 1

    def test_two_pledges_count_two_supporters(self, dynamodb_table):
        """B4: each distinct pledge adds exactly one supporter."""
        table, handler = dynamodb_table

        for email in ("a@example.com", "b@example.com"):
            event = {
                "body": json.dumps(
                    {"email": email, "amount": 50, "is_monthly": False}
                )
            }
            assert handler(event, None)["statusCode"] == 201

        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["contributors_count"]) == 2

    def test_monthly_pledge_updates_monthly_total(self, dynamodb_table):
        table, handler = dynamodb_table

        event = {
            "body": json.dumps(
                {
                    "email": "monthly@example.com",
                    "amount": 25,
                    "is_monthly": True,
                    "end_month": 12,
                    "end_year": 2030,
                }
            )
        }

        assert handler(event, None)["statusCode"] == 201

        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["monthly_total"]) == 25

    def test_second_post_same_email_updates_not_duplicates(self, dynamodb_table):
        """A returning pledger (same email) edits their pledge — no new record."""
        table, handler = dynamodb_table

        first = {
            "email": "returning@example.com",
            "amount": 100,
            "is_monthly": False,
        }
        r1 = handler({"body": json.dumps(first)}, None)
        assert r1["statusCode"] == 201

        second = {**first, "amount": 250}
        r2 = handler({"body": json.dumps(second)}, None)
        assert r2["statusCode"] == 200

        # Only one non-STATS row exists, and the amount reflects the edit.
        rows = [i for i in table.scan()["Items"] if i["pledgeID"] != "STATS"]
        assert len(rows) == 1
        assert int(rows[0]["amount"]) == 250

        # STATS reflects the new amount, not the sum of both.
        stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(stats["pledged_total"]) == 250
        assert int(stats["contributors_count"]) == 1

    def test_invalid_json(self, dynamodb_table):
        _, handler = dynamodb_table
        response = handler({"body": "not valid json{"}, None)
        assert response["statusCode"] == 400
        assert "Invalid JSON" in json.loads(response["body"])["error"]

    def test_missing_amount(self, dynamodb_table):
        _, handler = dynamodb_table
        event = {
            "body": json.dumps(
                {"email": "john@example.com", "is_monthly": True}
            )
        }
        response = handler(event, None)
        assert response["statusCode"] == 400
        assert "amount" in json.loads(response["body"])["error"]

    def test_email_normalized_to_lowercase(self, dynamodb_table):
        table, handler = dynamodb_table
        event = {
            "body": json.dumps(
                {
                    "email": "John.Doe@EXAMPLE.COM",
                    "amount": 100,
                    "is_monthly": False,
                }
            )
        }
        body = json.loads(handler(event, None)["body"])
        item = table.get_item(Key={"pledgeID": body["pledge_id"]})["Item"]
        assert item["email"] == "john.doe@example.com"
