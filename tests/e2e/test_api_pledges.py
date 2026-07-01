"""End-to-end tests for the pledges API.

These run against a *deployed* API and are skipped unless ``API_URL`` is set:

    export API_URL="https://your-api-id.execute-api.region.amazonaws.com"
    pytest tests/e2e/test_api_pledges.py -v

They exercise the real 4-endpoint contract:
    GET  /stats             -> {pledged_total, contributors_count, monthly_total}
    GET  /pledges           -> list of anonymous pledge rows
    POST /pledges           -> upsert by email (201 create / 200 update)
    GET  /pledges/by-email  -> the caller's own pledge, projected fields only

Note: creating pledges writes real rows into the target environment's table.
Point ``API_URL`` at a disposable dev stage, not production.
"""
import os
import uuid

import pytest
import requests

API_URL = os.environ.get("API_URL")

if not API_URL:
    pytest.skip("API_URL environment variable not set", allow_module_level=True)


def _unique_email() -> str:
    return f"e2e-{uuid.uuid4()}@test.com"


class TestStatsEndpoint:
    def test_stats_accessible_and_shaped(self):
        response = requests.get(f"{API_URL}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "pledged_total" in data
        assert "contributors_count" in data
        assert "monthly_total" in data

    def test_cors_headers_present(self):
        response = requests.get(f"{API_URL}/stats")
        assert "access-control-allow-origin" in response.headers


class TestListPledges:
    def test_list_is_anonymous(self):
        response = requests.get(f"{API_URL}/pledges")

        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        # No pledge in the public list may expose identity fields.
        for item in items:
            assert "name" not in item
            assert "email" not in item


class TestUpsertAndLookupFlow:
    def test_create_then_lookup_by_email(self):
        email = _unique_email()
        payload = {
            "email": email,
            "amount": 100,
            "is_monthly": False,
            "message": "E2E create",
        }

        create = requests.post(f"{API_URL}/pledges", json=payload)
        assert create.status_code == 201
        assert "pledge_id" in create.json()

        lookup = requests.get(f"{API_URL}/pledges/by-email", params={"email": email})
        assert lookup.status_code == 200
        # Phase M (D23): by-email returns the caller's pledges as a list, each with its id.
        pledges = lookup.json()["pledges"]
        assert len(pledges) == 1
        data = pledges[0]
        assert data["amount"] == 100
        assert data["is_monthly"] is False
        assert data["pledge_id"] == create.json()["pledge_id"]
        # The hardened endpoint projects an allowlist; internals/identity never leak.
        assert "name" not in data
        assert "email" not in data
        assert "updated_at" not in data

    def test_second_post_same_email_creates_second_pledge(self):
        # Phase M (D23): no upsert — a second POST with the same email is a SECOND pledge.
        email = _unique_email()
        base = {
            "email": email,
            "amount": 50,
            "is_monthly": False,
        }

        first = requests.post(f"{API_URL}/pledges", json=base)
        assert first.status_code == 201

        second = requests.post(f"{API_URL}/pledges", json={**base, "amount": 80})
        assert second.status_code == 201

        lookup = requests.get(f"{API_URL}/pledges/by-email", params={"email": email})
        assert lookup.status_code == 200
        pledges = lookup.json()["pledges"]
        assert len(pledges) == 2
        assert sorted(p["amount"] for p in pledges) == [50, 80]

    def test_lookup_unknown_email_returns_empty_list(self):
        lookup = requests.get(
            f"{API_URL}/pledges/by-email", params={"email": _unique_email()}
        )
        assert lookup.status_code == 200
        assert lookup.json()["pledges"] == []

    def test_lookup_without_email_returns_400(self):
        lookup = requests.get(f"{API_URL}/pledges/by-email")
        assert lookup.status_code == 400


class TestValidation:
    def test_invalid_email_rejected(self):
        payload = {
            "email": "not-an-email",
            "amount": 100,
            "is_monthly": False,
        }
        response = requests.post(f"{API_URL}/pledges", json=payload)
        assert response.status_code == 400
        assert "error" in response.json()

    def test_non_positive_amount_rejected(self):
        payload = {
            "email": _unique_email(),
            "amount": 0,
            "is_monthly": False,
        }
        response = requests.post(f"{API_URL}/pledges", json=payload)
        assert response.status_code == 400
        assert "error" in response.json()


class TestStatsReflectPledges:
    def test_stats_increase_after_create(self):
        before = requests.get(f"{API_URL}/stats").json()
        before_contributors = before["contributors_count"]
        before_total = before["pledged_total"]

        payload = {
            "email": _unique_email(),
            "amount": 100,
            "is_monthly": False,
        }
        assert requests.post(f"{API_URL}/pledges", json=payload).status_code == 201

        after = requests.get(f"{API_URL}/stats").json()
        # One new pledge = one new supporter (B4).
        assert after["contributors_count"] >= before_contributors + 1
        assert after["pledged_total"] >= before_total + 100
