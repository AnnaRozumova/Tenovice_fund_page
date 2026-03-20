"""Domain models for pledges"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Pledge:
    pledge_id: str
    name: str
    email: str
    contributors_count: int
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
            "name": self.name,
            "email": self.email,
            "contributors_count": self.contributors_count,
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
        """Create Pledge from DynamoDB item"""
        return Pledge(
            pledge_id=item["pledgeID"],
            name=item["name"],
            email=item["email"],
            contributors_count=int(item["contributors_count"]),
            amount=item["amount"],
            is_monthly=item["is_monthly"],
            created_at=item["created_at"],
            message=item.get("message"),
            end_month=int(item["end_month"]) if item.get("end_month") is not None else None,
            end_year=int(item["end_year"]) if item.get("end_year") is not None else None,
            campaign_total=item["campaign_total"],
            updated_at=item.get("updated_at"),
        )
