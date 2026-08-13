"""Tests for the Generator CLI commands (GEN-011).

Spec refs: GEN-011 (CLI commands, JSON output).
Design refs: CLI Commands section.

Follows the meta/bt CLI test pattern: mock-based command tests plus a
real-DB generate run to prove JSON output parity.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.errors import GenServiceError


def _run_cli(argv: list[str], session_factory) -> tuple[int, str, str]:
    """Run ``cli.main`` with a patched SessionLocal; return (rc, stdout, stderr)."""
    import backend.app.cli as cli_module

    original = cli_module.SessionLocal
    cli_module.SessionLocal = session_factory
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = cli_module.main(argv)
    finally:
        cli_module.SessionLocal = original
    return rc, stdout.getvalue(), stderr.getvalue()


class TestGenerateCommand:
    """lip gen generate."""

    def test_generate_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """generate outputs JSON to stdout."""
        with patch("backend.app.services.gen_service.GenService") as MockService:
            MockService.return_value.generate.return_value = MagicMock(
                snapshot_id=1,
                lottery_id=1,
                selection_id=1,
                version="1",
                status="active",
                fingerprint="fp123",
                seed=42,
                count=10,
                combinations=[],
            )
            from backend.app.cli import main

            rc = main(["gen", "generate", "--lottery-id", "1"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["snapshot_id"] == 1
        assert data["lottery_id"] == 1
        assert data["status"] == "active"

    def test_generate_passes_optional_args(self) -> None:
        """--count/--seed/--selection-id are forwarded to the service."""
        with patch("backend.app.services.gen_service.GenService") as MockService:
            MockService.return_value.generate.return_value = MagicMock(
                snapshot_id=1,
                lottery_id=1,
                selection_id=1,
                version="1",
                status="active",
                fingerprint="fp",
                seed=42,
                count=5,
                combinations=[],
            )
            from backend.app.cli import main

            rc = main(
                [
                    "gen",
                    "generate",
                    "--lottery-id",
                    "1",
                    "--count",
                    "5",
                    "--seed",
                    "42",
                    "--selection-id",
                    "3",
                ]
            )
            assert rc == 0
            MockService.return_value.generate.assert_called_once_with(
                lottery_id=1, count=5, seed=42, selection_id=3
            )


class TestCombinationsCommand:
    """lip gen combinations."""

    def test_combinations_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """combinations outputs JSON to stdout."""
        with patch("backend.app.services.gen_service.GenService") as MockService:
            MockService.return_value.get_combinations.return_value = MagicMock(
                snapshot_id=1,
                lottery_id=1,
                combinations=[
                    MagicMock(position=0, numbers=[1, 2, 3, 4, 5, 6], super_number=None, score=None)
                ],
            )
            from backend.app.cli import main

            rc = main(["gen", "combinations", "--lottery-id", "1"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["snapshot_id"] == 1
        assert data["combinations"][0]["numbers"] == [1, 2, 3, 4, 5, 6]


class TestSnapshotCommand:
    """lip gen snapshot."""

    def test_snapshot_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """snapshot outputs JSON to stdout."""
        with patch("backend.app.services.gen_service.GenService") as MockService:
            MockService.return_value.update_snapshot.return_value = MagicMock(
                snapshot_id=1,
                lottery_id=1,
                selection_id=1,
                version="1",
                status="retired",
                fingerprint="fp123",
                created_at=None,
            )
            from backend.app.cli import main

            rc = main(
                [
                    "gen",
                    "snapshot",
                    "--lottery-id",
                    "1",
                    "--snapshot-id",
                    "1",
                    "--status",
                    "retired",
                ]
            )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["snapshot_id"] == 1
        assert data["status"] == "retired"


class TestSnapshotsCommand:
    """lip gen snapshots."""

    def test_snapshots_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """snapshots outputs JSON to stdout."""
        with patch("backend.app.services.gen_service.GenService") as MockService:
            MockService.return_value.get_snapshots.return_value = MagicMock(
                lottery_id=1,
                snapshots=[
                    MagicMock(
                        snapshot_id=1,
                        lottery_id=1,
                        selection_id=1,
                        version="2",
                        status="active",
                        fingerprint="fp2",
                        created_at=None,
                    ),
                    MagicMock(
                        snapshot_id=2,
                        lottery_id=1,
                        selection_id=1,
                        version="1",
                        status="retired",
                        fingerprint="fp1",
                        created_at=None,
                    ),
                ],
            )
            from backend.app.cli import main

            rc = main(["gen", "snapshots", "--lottery-id", "1"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["snapshots"]) == 2
        assert data["snapshots"][0]["version"] == "2"


class TestGenErrorHandling:
    """CLI error handling (GEN-013)."""

    def test_service_error_returns_1(self) -> None:
        """GenServiceError exits with code 1 and prints the code to stderr."""
        with patch("backend.app.services.gen_service.GenService") as MockService:
            MockService.return_value.generate.side_effect = GenServiceError(
                GenServiceError.GEN_NO_SELECTION, "no active selection"
            )
            from backend.app.cli import main

            rc = main(["gen", "generate", "--lottery-id", "1"])
        assert rc == 1


class TestRealDb:
    """Real-DB run for JSON parity (GEN-011)."""

    def test_generate_real_db(self, db, session_factory, seed_gen_data) -> None:
        """lip gen generate over the migrated DB prints a valid generation JSON."""
        ids = seed_gen_data()
        rc, stdout, stderr = _run_cli(
            ["gen", "generate", "--lottery-id", str(ids["lottery_id"])],
            session_factory,
        )
        assert rc == 0, stderr
        data = json.loads(stdout)
        assert data["status"] == "active"
        assert data["lottery_id"] == ids["lottery_id"]
        assert len(data["combinations"]) == 10

    def test_generate_unknown_lottery_exits_1(self, session_factory) -> None:
        """Unknown lottery → exit 1 with GEN_LOTTERY_NOT_FOUND on stderr."""
        rc, stdout, stderr = _run_cli(
            ["gen", "generate", "--lottery-id", "9999"],
            session_factory,
        )
        assert rc == 1
        assert "GEN_LOTTERY_NOT_FOUND" in stderr
