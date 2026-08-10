"""Tests for experiment API error mapping (EXP-008)."""

from backend.app.api.errors import status_for_code


class TestExperimentErrorMapping:
    """Test experiment error code to HTTP status mapping."""

    def test_experiment_not_found_maps_to_404(self):
        """EXPERIMENT_NOT_FOUND maps to 404."""
        assert status_for_code("EXPERIMENT_NOT_FOUND") == 404

    def test_experiment_retired_maps_to_409(self):
        """EXPERIMENT_RETIRED maps to 409."""
        assert status_for_code("EXPERIMENT_RETIRED") == 409

    def test_duplicate_experiment_maps_to_409(self):
        """DUPLICATE_EXPERIMENT maps to 409."""
        assert status_for_code("DUPLICATE_EXPERIMENT") == 409

    def test_snapshot_not_found_maps_to_404(self):
        """SNAPSHOT_NOT_FOUND maps to 404."""
        assert status_for_code("SNAPSHOT_NOT_FOUND") == 404

    def test_snapshot_type_mismatch_maps_to_422(self):
        """SNAPSHOT_TYPE_MISMATCH maps to 422."""
        assert status_for_code("SNAPSHOT_TYPE_MISMATCH") == 422

    def test_comparison_insufficient_runs_maps_to_422(self):
        """COMPARISON_INSUFFICIENT_RUNS maps to 422."""
        assert status_for_code("COMPARISON_INSUFFICIENT_RUNS") == 422

    def test_export_format_invalid_maps_to_422(self):
        """EXPORT_FORMAT_INVALID maps to 422."""
        assert status_for_code("EXPORT_FORMAT_INVALID") == 422
