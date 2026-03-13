"""Integration tests for create_pledge handler"""
import json
import os
import importlib

import pytest
from moto import mock_aws
import boto3


@pytest.fixture(scope="function")
def dynamodb_table():
    """Create a mock DynamoDB table for testing"""
    with mock_aws():
        # Import handler AFTER mock is active
        from handlers import create_pledge
        importlib.reload(create_pledge)

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="test-pledges-table",
            KeySchema=[{"AttributeName": "pledgeID", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pledgeID", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Initialize STATS record
        table.put_item(Item={
            "pledgeID": "STATS",
            "pledged_total": 0,
            "pledgers_count": 0,
            "monthly_total": 0,
            "updated_at": "2024-01-01T00:00:00Z"
        })

        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"

        yield table, create_pledge.handler


class TestCreatePledgeHandler:
    """Test create_pledge Lambda handler"""

    def test_create_pledge_success(self, dynamodb_table):
        """Test successful pledge creation"""
        table, handler = dynamodb_table

        event = {
            "body": json.dumps({
                "name": "John Doe",
                "email": "john@example.com",
                "amount": 100,
                "is_monthly": True,
                "message": "Great cause!"
            })
        }

        response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert "pledge_id" in body
        assert body["message"] == "Pledge created successfully"

        # Verify pledge was saved
        pledge_id = body["pledge_id"]
        item = table.get_item(Key={"pledgeID": pledge_id})
        assert "Item" in item
        assert item["Item"]["name"] == "John Doe"
        assert item["Item"]["email"] == "john@example.com"
        assert item["Item"]["amount"] == 100

    def test_create_pledge_without_message(self, dynamodb_table):
        """Test pledge creation without optional message"""
        table, handler = dynamodb_table

        event = {
            "body": json.dumps({
                "name": "Jane Smith",
                "email": "jane@example.com",
                "amount": 50,
                "is_monthly": False,
            })
        }

        response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])

        # Verify pledge was saved without message
        pledge_id = body["pledge_id"]
        item = dynamodb_table.get_item(Key={"pledgeID": pledge_id})
        assert "message" not in item["Item"] or item["Item"]["message"] is None

    def test_create_pledge_updates_stats(self, dynamodb_table):
        """Test that creating a pledge updates the STATS record"""
        table, handler = dynamodb_table

        # Check initial stats
        initial_stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        initial_total = int(initial_stats["pledged_total"])
        initial_count = int(initial_stats["pledgers_count"])

        event = {
            "body": json.dumps({
                "name": "Test User",
                "email": "test@example.com",
                "amount": 75,
                "is_monthly": False,
            })
        }

        response = handler(event, None)
        assert response["statusCode"] == 201

        # Check updated stats
        updated_stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(updated_stats["pledged_total"]) == initial_total + 75
        assert int(updated_stats["pledgers_count"]) == initial_count + 1

    def test_create_pledge_monthly_updates_monthly_total(self, dynamodb_table):
        """Test that monthly pledge updates monthly_total in STATS"""
        table, handler = dynamodb_table

        initial_stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        initial_monthly = int(initial_stats.get("monthly_total", 0))

        event = {
            "body": json.dumps({
                "name": "Monthly Supporter",
                "email": "monthly@example.com",
                "amount": 25,
                "is_monthly": True,
            })
        }

        response = handler(event, None)
        assert response["statusCode"] == 201

        updated_stats = table.get_item(Key={"pledgeID": "STATS"})["Item"]
        assert int(updated_stats["monthly_total"]) == initial_monthly + 25

    def test_create_pledge_invalid_json(self, dynamodb_table):
        """Test error handling for invalid JSON"""
        table, handler = dynamodb_table

        event = {"body": "not valid json{"}

        response = handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON" in body["error"]

    def test_create_pledge_missing_required_field(self, dynamodb_table):
        """Test validation error for missing required field"""
        table, handler = dynamodb_table

        event = {
            "body": json.dumps({
                "name": "John Doe",
                "email": "john@example.com",
                # Missing amount
                "is_monthly": True,
            })
        }

        response = handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "amount" in body["error"]

    def test_create_pledge_invalid_email(self, dynamodb_table):
        """Test validation error for invalid email"""
        table, handler = dynamodb_table

        event = {
            "body": json.dumps({
                "name": "John Doe",
                "email": "not-an-email",
                "amount": 100,
                "is_monthly": True,
            })
        }

        response = handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "email" in body["error"].lower()

    def test_create_pledge_amount_out_of_range(self, dynamodb_table):
        """Test validation error for amount out of range"""
        table, handler = dynamodb_table

        event = {
            "body": json.dumps({
                "name": "John Doe",
                "email": "john@example.com",
                "amount": 0,
                "is_monthly": True,
            })
        }

        response = handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Amount" in body["error"]

    def test_create_pledge_email_normalized(self, dynamodb_table):
        """Test that email is normalized to lowercase"""
        table, handler = dynamodb_table

        event = {
            "body": json.dumps({
                "name": "John Doe",
                "email": "John.Doe@EXAMPLE.COM",
                "amount": 100,
                "is_monthly": True,
            })
        }

        response = handler(event, None)
        assert response["statusCode"] == 201

        body = json.loads(response["body"])
        pledge_id = body["pledge_id"]
        item = dynamodb_table.get_item(Key={"pledgeID": pledge_id})
        assert item["Item"]["email"] == "john.doe@example.com"
