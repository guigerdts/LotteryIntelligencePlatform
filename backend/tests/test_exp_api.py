"""Integration tests for Experiment API (EXP-001/003/004/008)."""

import pytest

from backend.app.models.lottery import Lottery


@pytest.fixture
def seeded_lottery(db):
    """Seed a lottery row for FK compliance."""
    lottery = Lottery(
        id=1,
        code="TEST",
        name="Test Lottery",
        country="US",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
    )
    db.add(lottery)
    db.commit()
    return lottery


class TestExperimentAPI:
    """Test experiment API endpoints."""

    def test_create_experiment(self, client, seeded_lottery):
        """POST /experiment/create creates an experiment."""
        response = client.post(
            "/api/v1/experiment/create",
            json={
                "lottery_id": 1,
                "name": "API Test",
                "description": "Test experiment",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "API Test"
        assert data["data"]["status"] == "active"
        assert data["data"]["version"] == "1"

    def test_create_experiment_duplicate(self, client, seeded_lottery):
        """POST /experiment/create with duplicate name returns 409."""
        # Create first experiment
        client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Duplicate Test"},
        )
        # Create second with same name but different description
        response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Duplicate Test", "description": "Different"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "DUPLICATE_EXPERIMENT"

    def test_get_experiment(self, client, seeded_lottery):
        """GET /experiment/{id} returns experiment."""
        # Create experiment first
        create_response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Get Test"},
        )
        experiment_id = create_response.json()["data"]["experiment_id"]

        # Get experiment
        response = client.get(f"/api/v1/experiment/{experiment_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["name"] == "Get Test"

    def test_get_nonexistent_experiment(self, client, seeded_lottery):
        """GET /experiment/{id} with invalid ID returns 404."""
        response = client.get("/api/v1/experiment/999")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "EXPERIMENT_NOT_FOUND"

    def test_update_experiment(self, client, seeded_lottery):
        """PATCH /experiment/{id} updates experiment."""
        # Create experiment first
        create_response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Update Test"},
        )
        experiment_id = create_response.json()["data"]["experiment_id"]

        # Update experiment
        response = client.patch(
            f"/api/v1/experiment/{experiment_id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["version"] == "2"

    def test_update_retired_experiment(self, client, seeded_lottery):
        """PATCH /experiment/{id} on retired experiment returns 409."""
        # Create and retire experiment
        create_response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Retired Update"},
        )
        experiment_id = create_response.json()["data"]["experiment_id"]
        client.patch(
            f"/api/v1/experiment/{experiment_id}",
            json={"status": "retired"},
        )

        # Try to update retired experiment
        response = client.patch(
            f"/api/v1/experiment/{experiment_id}",
            json={"description": "Should fail"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "EXPERIMENT_RETIRED"

    def test_list_experiments(self, client, seeded_lottery):
        """GET /experiment/ lists experiments."""
        # Create experiments
        client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "List Test 1"},
        )
        client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "List Test 2"},
        )

        # List experiments
        response = client.get("/api/v1/experiment/", params={"lottery_id": 1})
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    def test_list_experiments_with_status_filter(self, client, seeded_lottery):
        """GET /experiment/ with status filter works."""
        # Create experiments
        create_response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Active Exp"},
        )
        create_response.json()["data"]["experiment_id"]
        client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Retired Exp"},
        )

        # Retire second experiment
        retired_response = client.get("/api/v1/experiment/", params={"lottery_id": 1})
        retired_id = [
            e["experiment_id"]
            for e in retired_response.json()["data"]
            if e["name"] == "Retired Exp"
        ][0]
        client.patch(
            f"/api/v1/experiment/{retired_id}",
            json={"status": "retired"},
        )

        # List active experiments
        response = client.get("/api/v1/experiment/", params={"lottery_id": 1, "status": "active"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Active Exp"

    def test_add_run_to_experiment(self, client, seeded_lottery):
        """POST /experiment/{id}/run adds a run."""
        # Create experiment
        create_response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Run Test"},
        )
        experiment_id = create_response.json()["data"]["experiment_id"]

        # Add run (snapshot doesn't exist, but we test the endpoint)
        response = client.post(
            f"/api/v1/experiment/{experiment_id}/run",
            json={
                "run_label": "baseline",
                "engine_type": "backtesting",
                "engine_snapshot_id": 999,
            },
        )
        # Should fail because snapshot doesn't exist
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "SNAPSHOT_NOT_FOUND"

    def test_add_run_invalid_engine_type(self, client, seeded_lottery):
        """POST /experiment/{id}/run with invalid engine type returns 422."""
        # Create experiment
        create_response = client.post(
            "/api/v1/experiment/create",
            json={"lottery_id": 1, "name": "Invalid Engine"},
        )
        experiment_id = create_response.json()["data"]["experiment_id"]

        # Add run with invalid engine type
        response = client.post(
            f"/api/v1/experiment/{experiment_id}/run",
            json={
                "run_label": "should-fail",
                "engine_type": "invalid",
                "engine_snapshot_id": 1,
            },
        )
        assert response.status_code == 422
