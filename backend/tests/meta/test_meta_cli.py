"""Tests for meta CLI commands (META-014).

Spec refs: META-014 (CLI commands).
Design refs: CLI Commands section.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.cli import main


class TestMetaRankCommand:
    """lip meta rank command."""

    def test_rank_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """rank command outputs JSON to stdout."""
        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.return_value = MagicMock(
                ranking_id=1,
                lottery_id=1,
                context_hash="abc123",
                version="1",
                status="active",
                fingerprint="fp123",
                entries=[],
            )
            exit_code = main(["meta", "rank", "--lottery-id", "1"])
            assert exit_code == 0
            output = capsys.readouterr().out
            data = json.loads(output)
            assert data["ranking_id"] == 1
            assert data["lottery_id"] == 1

    def test_rank_with_weights(self, capsys: pytest.CaptureFixture) -> None:
        """rank command accepts --weights JSON."""
        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.return_value = MagicMock(
                ranking_id=1, lottery_id=1, context_hash="h",
                version="1", status="active", fingerprint="f", entries=[],
            )
            exit_code = main([
                "meta", "rank", "--lottery-id", "1",
                "--weights", '{"hit_rate": 0.5, "average_matches": 0.5}',
            ])
            assert exit_code == 0


class TestMetaRankingCommand:
    """lip meta ranking command."""

    def test_ranking_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """ranking command outputs JSON to stdout."""
        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.get_ranking.return_value = MagicMock(
                lottery_id=1,
                context_hash="abc123",
                rankings=[{"ranking_id": 1, "version": "1"}],
            )
            exit_code = main(["meta", "ranking", "--lottery-id", "1"])
            assert exit_code == 0
            output = capsys.readouterr().out
            data = json.loads(output)
            assert data["lottery_id"] == 1


class TestMetaSelectCommand:
    """lip meta select command."""

    def test_select_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """select command outputs JSON to stdout."""
        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.select.return_value = MagicMock(
                selection_id=1, lottery_id=1, ranking_id=1,
                context_hash="abc123", version="1", status="active",
                fingerprint="fp123", entries=[],
            )
            exit_code = main(["meta", "select", "--lottery-id", "1"])
            assert exit_code == 0
            output = capsys.readouterr().out
            data = json.loads(output)
            assert data["selection_id"] == 1

    def test_select_with_top_k(self, capsys: pytest.CaptureFixture) -> None:
        """select command accepts --top-k."""
        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.select.return_value = MagicMock(
                selection_id=1, lottery_id=1, ranking_id=1,
                context_hash="h", version="1", status="active",
                fingerprint="f", entries=[],
            )
            exit_code = main(["meta", "select", "--lottery-id", "1", "--top-k", "10"])
            assert exit_code == 0


class TestMetaSelectionCommand:
    """lip meta selection command."""

    def test_selection_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """selection command outputs JSON to stdout."""
        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.get_selection.return_value = MagicMock(
                lottery_id=1, context_hash="abc123",
                selections=[{"selection_id": 1, "version": "1"}],
            )
            exit_code = main(["meta", "selection", "--lottery-id", "1"])
            assert exit_code == 0
            output = capsys.readouterr().out
            data = json.loads(output)
            assert data["lottery_id"] == 1


class TestMetaErrorHandling:
    """CLI error handling."""

    def test_service_error_returns_1(self) -> None:
        """ServiceError exits with code 1 and prints error to stderr."""
        from backend.app.services.errors import MetaServiceError

        with patch("backend.app.services.meta_service.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.side_effect = MetaServiceError(
                MetaServiceError.META_NO_ENGINE_DATA, "No engine data"
            )
            exit_code = main(["meta", "rank", "--lottery-id", "1"])
            assert exit_code == 1
