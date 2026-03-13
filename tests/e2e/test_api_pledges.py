"""End-to-end tests for the pledges API

These tests run against a deployed API endpoint.

Usage:
    export API_URL="https://your-api-id.execute-api.region.amazonaws.com"
    pytest tests/e2e/test_api_pledges.py -v
"""
import os
import pytest
import requests
import uuid


# Get API URL from environment
API_URL = os.environ.get("API_URL")

if not API_URL:
    pytest.skip("API_URL environment variable not set", allow_module_level=True)


class TestPledgesAPIEndToEnd:
    """End-to-end tests for pledges API"""

    def test_stats_endpoint_accessible(self):
        """Test that stats endpoint is accessible"""
        response = requests.get(f"{API_URL}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "pledged_total" in data
        assert "pledgers_count" in data
        assert "monthly_total" in data

    def test_create_and_get_pledge_flow(self):
        """Test creating a pledge and then retrieving it"""
        # Create a pledge
        pledge_data = {
            "name": f"E2E Test User {uuid.uuid4()}",
            "email": f"e2e-{uuid.uuid4()}@test.com",
            "amount": 100,
            "is_monthly": True,
            "message": "E2E test pledge"
        }

        create_response = requests.post(
            f"{API_URL}/pledges",
            json=pledge_data
        )

        assert create_response.status_code == 201
        create_data = create_response.json()
        assert "pledge_id" in create_data

        pledge_id = create_data["pledge_id"]

        # Get the pledge
        get_response = requests.get(f"{API_URL}/pledges/{pledge_id}")

        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["pledge_id"] == pledge_id
        assert get_data["name"] == pledge_data["name"]
        assert get_data["email"] == pledge_data["email"].lower()
        assert get_data["amount"] == pledge_data["amount"]
        assert get_data["is_monthly"] == pledge_data["is_monthly"]

    def test_create_update_and_get_pledge_flow(self):
        """Test full CRUD flow: create, update, and get"""
        # Create
        create_data = {
            "name": f"Update Test {uuid.uuid4()}",
            "email": f"update-{uuid.uuid4()}@test.com",
            "amount": 50,
            "is_monthly": False,
        }

        create_response = requests.post(f"{API_URL}/pledges", json=create_data)
        assert create_response.status_code == 201
        pledge_id = create_response.json()["pledge_id"]

        # Update
        update_data = {
            "amount": 75,
            "is_monthly": True,
            "message": "Updated in E2E test"
        }

        update_response = requests.put(
            f"{API_URL}/pledges/{pledge_id}",
            json=update_data
        )

        assert update_response.status_code == 200
        update_result = update_response.json()
        assert update_result["amount"] == 75
        assert update_result["is_monthly"] is True
        assert update_result["message"] == "Updated in E2E test"

        # Get and verify
        get_response = requests.get(f"{API_URL}/pledges/{pledge_id}")
        assert get_response.status_code == 200
        final_data = get_response.json()
        assert final_data["amount"] == 75
        assert final_data["is_monthly"] is True

    def test_get_nonexistent_pledge(self):
        """Test getting a pledge that doesn't exist"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{API_URL}/pledges/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_create_pledge_with_invalid_data(self):
        """Test creating a pledge with invalid data"""
        invalid_data = {
            "name": "A",  # Too short
            "email": "not-an-email",
            "amount": 0,  # Too low
            "is_monthly": True,
        }

        response = requests.post(f"{API_URL}/pledges", json=invalid_data)

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_cors_headers_present(self):
        """Test that CORS headers are present"""
        response = requests.get(f"{API_URL}/stats")

        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers

    def test_update_nonexistent_pledge(self):
        """Test updating a pledge that doesn't exist"""
        fake_id = str(uuid.uuid4())
        update_data = {"amount": 100}

        response = requests.put(
            f"{API_URL}/pledges/{fake_id}",
            json=update_data
        )

        assert response.status_code == 404

    def test_create_pledge_without_optional_fields(self):
        """Test creating a pledge without optional message field"""
        pledge_data = {
            "name": f"Minimal Test {uuid.uuid4()}",
            "email": f"minimal-{uuid.uuid4()}@test.com",
            "amount": 25,
            "is_monthly": False,
        }

        response = requests.post(f"{API_URL}/pledges", json=pledge_data)

        assert response.status_code == 201
        data = response.json()
        assert "pledge_id" in data

    def test_stats_updated_after_pledge_creation(self):
        """Test that stats are updated after creating a pledge"""
        # Get initial stats
        initial_response = requests.get(f"{API_URL}/stats")
        initial_stats = initial_response.json()
        initial_count = initial_stats["pledgers_count"]

        # Create a pledge
        pledge_data = {
            "name": f"Stats Test {uuid.uuid4()}",
            "email": f"stats-{uuid.uuid4()}@test.com",
            "amount": 100,
            "is_monthly": False,
        }

        create_response = requests.post(f"{API_URL}/pledges", json=pledge_data)
        assert create_response.status_code == 201

        # Get updated stats
        updated_response = requests.get(f"{API_URL}/stats")
        updated_stats = updated_response.json()

        # Verify stats were updated
        assert updated_stats["pledgers_count"] >= initial_count + 1
