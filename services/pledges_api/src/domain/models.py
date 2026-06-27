"""Domain models for pledges"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Pledge:
    pledge_id: str
    email: str
    amount: Decimal
    is_monthly: bool
    created_at: str
    message: Optional[str] = None
    end_month: Optional[int] = None
    end_year: Optional[int] = None
    campaign_total: Decimal = Decimal("0")
    updated_at: Optional[str] = None

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        item = {
            "pledgeID": self.pledge_id,
            "email": self.email,
            "amount": self.amount,
            "is_monthly": self.is_monthly,
            "campaign_total": self.campaign_total,
            "created_at": self.created_at,
        }
        if self.message:
            item["message"] = self.message

        if self.end_month is not None:
            item["end_month"] = self.end_month

        if self.end_year is not None:
            item["end_year"] = self.end_year

        if self.updated_at:
            item["updated_at"] = self.updated_at

        return item

    @staticmethod
    def from_dynamodb_item(item: dict) -> "Pledge":
        """Create Pledge from DynamoDB item.

        Legacy rows may still carry a ``contributors_count`` attribute (B4 stopped
        writing it; pre-B4 rows keep theirs). It is simply ignored here — a pledge
        now represents one person.
        """
        return Pledge(
            pledge_id=item["pledgeID"],
            email=item["email"],
            amount=item["amount"],
            is_monthly=item["is_monthly"],
            created_at=item["created_at"],
            message=item.get("message"),
            end_month=int(item["end_month"]) if item.get("end_month") is not None else None,
            end_year=int(item["end_year"]) if item.get("end_year") is not None else None,
            campaign_total=item["campaign_total"],
            updated_at=item.get("updated_at"),
        )
