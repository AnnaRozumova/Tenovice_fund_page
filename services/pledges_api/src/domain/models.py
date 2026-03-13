"""Domain models for pledges"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Pledge:
    pledge_id: str
    name: str
    email: str
    amount: int
    is_monthly: bool
    created_at: str
    message: Optional[str] = None

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        item = {
            "pledgeID": self.pledge_id,
            "name": self.name,
            "email": self.email,
            "amount": self.amount,
            "is_monthly": self.is_monthly,
            "created_at": self.created_at,
        }
        if self.message:
            item["message"] = self.message
        return item

    @staticmethod
    def from_dynamodb_item(item: dict) -> "Pledge":
        """Create Pledge from DynamoDB item"""
        return Pledge(
            pledge_id=item["pledgeID"],
            name=item["name"],
            email=item["email"],
            amount=int(item["amount"]),
            is_monthly=bool(item["is_monthly"]),
            created_at=item["created_at"],
            message=item.get("message"),
        )
