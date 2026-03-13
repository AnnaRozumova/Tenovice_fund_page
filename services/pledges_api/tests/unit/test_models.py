"""Unit tests for domain models"""
from domain.models import Pledge


class TestPledgeModel:
    """Test Pledge model"""

    def test_to_dynamodb_item_with_message(self):
        """Test converting Pledge to DynamoDB item format with message"""
        pledge = Pledge(
            pledge_id="test-123",
            name="John Doe",
            email="john@example.com",
            amount=100,
            is_monthly=True,
            created_at="2024-01-01T00:00:00Z",
            message="Test message"
        )

        item = pledge.to_dynamodb_item()

        assert item["pledgeID"] == "test-123"
        assert item["name"] == "John Doe"
        assert item["email"] == "john@example.com"
        assert item["amount"] == 100
        assert item["is_monthly"] is True
        assert item["created_at"] == "2024-01-01T00:00:00Z"
        assert item["message"] == "Test message"

    def test_to_dynamodb_item_without_message(self):
        """Test converting Pledge to DynamoDB item format without message"""
        pledge = Pledge(
            pledge_id="test-456",
            name="Jane Smith",
            email="jane@example.com",
            amount=50,
            is_monthly=False,
            created_at="2024-01-02T00:00:00Z",
            message=None
        )

        item = pledge.to_dynamodb_item()

        assert "message" not in item
        assert item["pledgeID"] == "test-456"
        assert item["is_monthly"] is False

    def test_from_dynamodb_item_with_message(self):
        """Test creating Pledge from DynamoDB item with message"""
        item = {
            "pledgeID": "test-789",
            "name": "Bob Johnson",
            "email": "bob@example.com",
            "amount": 200,
            "is_monthly": True,
            "created_at": "2024-01-03T00:00:00Z",
            "message": "Happy to help"
        }

        pledge = Pledge.from_dynamodb_item(item)

        assert pledge.pledge_id == "test-789"
        assert pledge.name == "Bob Johnson"
        assert pledge.email == "bob@example.com"
        assert pledge.amount == 200
        assert pledge.is_monthly is True
        assert pledge.created_at == "2024-01-03T00:00:00Z"
        assert pledge.message == "Happy to help"

    def test_from_dynamodb_item_without_message(self):
        """Test creating Pledge from DynamoDB item without message"""
        item = {
            "pledgeID": "test-000",
            "name": "Alice Brown",
            "email": "alice@example.com",
            "amount": 75,
            "is_monthly": False,
            "created_at": "2024-01-04T00:00:00Z"
        }

        pledge = Pledge.from_dynamodb_item(item)

        assert pledge.message is None

    def test_roundtrip_conversion(self):
        """Test that Pledge → DynamoDB → Pledge preserves data"""
        original = Pledge(
            pledge_id="roundtrip-test",
            name="Test User",
            email="test@example.com",
            amount=150,
            is_monthly=True,
            created_at="2024-01-05T00:00:00Z",
            message="Roundtrip test"
        )

        item = original.to_dynamodb_item()
        restored = Pledge.from_dynamodb_item(item)

        assert restored.pledge_id == original.pledge_id
        assert restored.name == original.name
        assert restored.email == original.email
        assert restored.amount == original.amount
        assert restored.is_monthly == original.is_monthly
        assert restored.created_at == original.created_at
        assert restored.message == original.message
