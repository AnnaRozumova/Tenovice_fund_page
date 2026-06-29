"""Unit tests for domain models.

Rewritten in Phase B (B1): ``name`` is gone from the model; pledges carry
``campaign_total``. B4: ``contributors_count`` is gone too — a pledge is one
person — and ``from_dynamodb_item`` ignores it on legacy rows that still have it.
"""
from decimal import Decimal

from domain.models import Pledge


class TestPledgeModel:
    """Test Pledge model"""

    def test_to_dynamodb_item_with_message(self):
        """Test converting Pledge to DynamoDB item format with message"""
        pledge = Pledge(
            pledge_id="test-123",
            email="john@example.com",
            amount=Decimal("100"),
            is_monthly=True,
            created_at="2024-01-01T00:00:00Z",
            campaign_total=Decimal("1200"),
            message="Test message",
        )

        item = pledge.to_dynamodb_item()

        assert item["pledgeID"] == "test-123"
        assert "name" not in item
        assert "contributors_count" not in item
        assert item["email"] == "john@example.com"
        assert item["amount"] == Decimal("100")
        assert item["is_monthly"] is True
        assert item["created_at"] == "2024-01-01T00:00:00Z"
        assert item["message"] == "Test message"

    def test_to_dynamodb_item_without_message(self):
        """Test converting Pledge to DynamoDB item format without message"""
        pledge = Pledge(
            pledge_id="test-456",
            email="jane@example.com",
            amount=Decimal("50"),
            is_monthly=False,
            created_at="2024-01-02T00:00:00Z",
            message=None,
        )

        item = pledge.to_dynamodb_item()

        assert "message" not in item
        assert item["pledgeID"] == "test-456"
        assert item["is_monthly"] is False

    def test_from_dynamodb_item_with_message(self):
        """Test creating Pledge from DynamoDB item with message"""
        item = {
            "pledgeID": "test-789",
            "email": "bob@example.com",
            "amount": Decimal("200"),
            "is_monthly": True,
            "created_at": "2024-01-03T00:00:00Z",
            "campaign_total": Decimal("2400"),
            "message": "Happy to help",
        }

        pledge = Pledge.from_dynamodb_item(item)

        assert pledge.pledge_id == "test-789"
        assert pledge.email == "bob@example.com"
        assert pledge.amount == Decimal("200")
        assert pledge.is_monthly is True
        assert pledge.created_at == "2024-01-03T00:00:00Z"
        assert pledge.message == "Happy to help"

    def test_from_dynamodb_item_without_message(self):
        """Test creating Pledge from DynamoDB item without message"""
        item = {
            "pledgeID": "test-000",
            "email": "alice@example.com",
            "amount": Decimal("75"),
            "is_monthly": False,
            "created_at": "2024-01-04T00:00:00Z",
            "campaign_total": Decimal("75"),
        }

        pledge = Pledge.from_dynamodb_item(item)

        assert pledge.message is None

    def test_from_dynamodb_item_ignores_legacy_contributors_count(self):
        """B4: a pre-B4 row may still carry ``contributors_count`` — it is ignored."""
        item = {
            "pledgeID": "legacy-1",
            "email": "old@example.com",
            "contributors_count": 5,
            "amount": Decimal("100"),
            "is_monthly": False,
            "created_at": "2024-01-04T00:00:00Z",
            "campaign_total": Decimal("100"),
        }

        pledge = Pledge.from_dynamodb_item(item)

        assert pledge.email == "old@example.com"
        assert not hasattr(pledge, "contributors_count")
        # And it does not get re-written when serialized back.
        assert "contributors_count" not in pledge.to_dynamodb_item()

    def test_roundtrip_conversion(self):
        """Test that Pledge → DynamoDB → Pledge preserves data"""
        original = Pledge(
            pledge_id="roundtrip-test",
            email="test@example.com",
            amount=Decimal("150"),
            is_monthly=True,
            created_at="2024-01-05T00:00:00Z",
            campaign_total=Decimal("1800"),
            message="Roundtrip test",
        )

        item = original.to_dynamodb_item()
        restored = Pledge.from_dynamodb_item(item)

        assert restored.pledge_id == original.pledge_id
        assert restored.email == original.email
        assert restored.amount == original.amount
        assert restored.is_monthly == original.is_monthly
        assert restored.created_at == original.created_at
        assert restored.message == original.message
