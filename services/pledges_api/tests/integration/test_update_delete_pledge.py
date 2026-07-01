"""Integration tests for ``PUT`` / ``DELETE /pledges/{id}`` (Phase M, D23).

Editing and deleting a single pledge by id, owner-scoped by the caller's identity
(locally the supplied email; behind the authorizer the JWT email claim). The supporter
tally counts distinct emails: an edit never changes it, and a delete only decrements it
when it removes the account's last pledge. Driven via FastAPI's ``TestClient`` against a
moto-mocked table mirroring the real schema (PK ``pledgeID`` + ``EmailIndex`` GSI).
"""
import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app import app


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
def client_and_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        os.environ["PLEDGES_TABLE_NAME"] = "test-pledges-table"
        yield TestClient(app), table


def _create(client, email, amount, is_monthly=False, **extra):
    payload = {"email": email, "amount": amount, "is_monthly": is_monthly, **extra}
    resp = client.post("/pledges", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["pledge_id"]


def _stats(table):
    return table.get_item(Key={"pledgeID": "STATS"})["Item"]


class TestUpdatePledge:
    def test_owner_can_edit_own_pledge(self, client_and_table):
        client, table = client_and_table
        pid = _create(client, "owner@example.com", 100)

        resp = client.put(
            f"/pledges/{pid}",
            json={"email": "owner@example.com", "amount": 250, "is_monthly": False},
        )
        assert resp.status_code == 200

        item = table.get_item(Key={"pledgeID": pid})["Item"]
        assert int(item["amount"]) == 250
        # STATS reflects the edit (delta 100 -> 250), supporters unchanged.
        stats = _stats(table)
        assert int(stats["pledged_total"]) == 250
        assert int(stats["contributors_count"]) == 1

    def test_edit_does_not_change_supporter_count(self, client_and_table):
        client, table = client_and_table
        pid = _create(client, "owner@example.com", 100)
        client.put(
            f"/pledges/{pid}",
            json={"email": "owner@example.com", "amount": 120, "is_monthly": False},
        )
        assert int(_stats(table)["contributors_count"]) == 1

    def test_noop_edit_of_ongoing_monthly_does_not_corrupt_stats(self, client_and_table):
        """A monthly campaign_total is frozen at create; editing the pledge without
        changing its amount/term must leave STATS.pledged_total untouched. The edit
        recompute is anchored to created_at, so months elapsed since create don't leak a
        negative delta into STATS (D23 / calculate_remaining_months reference)."""
        client, table = client_and_table
        # A monthly pledge created long ago (Jan 2020), still running until Dec 2030.
        # campaign_total is frozen on that create-time baseline: Jan 2020..Dec 2030
        # inclusive = 132 months * 100 = 13200.
        table.put_item(
            Item={
                "pledgeID": "old-monthly",
                "email": "owner@example.com",
                "amount": 100,
                "is_monthly": True,
                "end_month": 12,
                "end_year": 2030,
                "campaign_total": 13200,
                "created_at": "2020-01-01T00:00:00+00:00",
            }
        )
        table.put_item(
            Item={
                "pledgeID": "STATS",
                "pledged_total": 13200,
                "contributors_count": 1,
                "monthly_total": 100,
                "updated_at": "2020-01-01T00:00:00Z",
            }
        )

        # Edit with the SAME amount and term (e.g. adding a message) — a no-op for impact.
        resp = client.put(
            "/pledges/old-monthly",
            json={
                "email": "owner@example.com",
                "amount": 100,
                "is_monthly": True,
                "end_month": 12,
                "end_year": 2030,
                "message": "still in",
            },
        )
        assert resp.status_code == 200

        stats = _stats(table)
        # Anchored to created_at, the recompute reproduces 13200 -> delta 0. (Without the
        # anchor it would recompute against "now" and shrink pledged_total.)
        assert int(stats["pledged_total"]) == 13200
        assert int(stats["monthly_total"]) == 100
        assert int(stats["contributors_count"]) == 1

    def test_cannot_edit_another_persons_pledge(self, client_and_table):
        client, table = client_and_table
        pid = _create(client, "owner@example.com", 100)

        resp = client.put(
            f"/pledges/{pid}",
            json={"email": "intruder@example.com", "amount": 5, "is_monthly": False},
        )
        assert resp.status_code == 403
        # Untouched.
        assert int(table.get_item(Key={"pledgeID": pid})["Item"]["amount"]) == 100

    def test_edit_missing_pledge_returns_404(self, client_and_table):
        client, _ = client_and_table
        resp = client.put(
            "/pledges/does-not-exist",
            json={"email": "owner@example.com", "amount": 5, "is_monthly": False},
        )
        assert resp.status_code == 404

    def test_edit_invalid_body_returns_400(self, client_and_table):
        client, _ = client_and_table
        pid = _create(client, "owner@example.com", 100)
        resp = client.put(f"/pledges/{pid}", json={"email": "owner@example.com"})
        assert resp.status_code == 400


class TestDeletePledge:
    def test_owner_can_delete_and_last_removes_supporter(self, client_and_table):
        client, table = client_and_table
        pid = _create(client, "owner@example.com", 100)

        resp = client.delete(f"/pledges/{pid}", params={"email": "owner@example.com"})
        assert resp.status_code == 200

        assert "Item" not in table.get_item(Key={"pledgeID": pid})
        stats = _stats(table)
        # Back to zero: deleting the only pledge removes its impact and the supporter.
        assert int(stats["pledged_total"]) == 0
        assert int(stats["contributors_count"]) == 0

    def test_deleting_one_of_two_keeps_supporter(self, client_and_table):
        client, table = client_and_table
        pid1 = _create(client, "owner@example.com", 100)
        _create(client, "owner@example.com", 300)  # same email, second pledge

        resp = client.delete(f"/pledges/{pid1}", params={"email": "owner@example.com"})
        assert resp.status_code == 200

        stats = _stats(table)
        # One pledge (300) remains; the email is still one supporter.
        assert int(stats["pledged_total"]) == 300
        assert int(stats["contributors_count"]) == 1

    def test_delete_adjusts_monthly_total(self, client_and_table):
        client, table = client_and_table
        pid = _create(
            client, "m@example.com", 25, is_monthly=True, end_month=12, end_year=2030
        )
        assert int(_stats(table)["monthly_total"]) == 25

        client.delete(f"/pledges/{pid}", params={"email": "m@example.com"})
        assert int(_stats(table)["monthly_total"]) == 0

    def test_cannot_delete_another_persons_pledge(self, client_and_table):
        client, table = client_and_table
        pid = _create(client, "owner@example.com", 100)

        resp = client.delete(f"/pledges/{pid}", params={"email": "intruder@example.com"})
        assert resp.status_code == 403
        assert "Item" in table.get_item(Key={"pledgeID": pid})

    def test_delete_missing_pledge_returns_404(self, client_and_table):
        client, _ = client_and_table
        resp = client.delete("/pledges/nope", params={"email": "owner@example.com"})
        assert resp.status_code == 404

    def test_delete_without_identity_returns_400(self, client_and_table):
        client, _ = client_and_table
        pid = _create(client, "owner@example.com", 100)
        assert client.delete(f"/pledges/{pid}").status_code == 400
