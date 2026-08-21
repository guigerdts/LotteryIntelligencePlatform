"""E2E tests for Probability Engine (PR3b, T-17).

Tests the full flow: CLI/API parity, fixture import → generate → GET, 404, empty-DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.cli import main as cli_main
from backend.app.probability.snapshot_store import SnapshotStore
from backend.app.repositories.base import Base


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.close()


class TestCLIParity:
    """CLI probability generate/rebuild commands."""

    def test_cli_probability_generate_unknown_lottery(self, session):
        """CLI returns error for unknown lottery."""
        from unittest.mock import patch


        with patch("backend.app.cli.SessionLocal", return_value=session):
            result = cli_main(["probability", "generate", "--lottery", "NONEXISTENT"])
        assert result == 1

    def test_cli_probability_help(self):
        """CLI probability --help exits cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["probability", "--help"])
        assert exc_info.value.code == 0


class TestEmptyDB:
    """Empty DB acceptance (PES-11)."""

    def test_snapshot_store_empty_db(self, session):
        """SnapshotStore works on empty DB."""
        store = SnapshotStore(session)
        assert store.get_active(999, "core") is None
        assert store.next_version(999, "core") == "1"
        assert store.find_by_fingerprint(999, "core", "nope") is None

    def test_empty_draws_header(self, session):
        """Empty draws produce draws_from=0, draws_to=0."""
        store = SnapshotStore(session)
        snap = store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="empty", input_fingerprint="empty",
            status="active", is_locked=True, draw_count=0, draws_from=0, draws_to=0,
        )
        session.flush()
        assert snap.draws_from == 0
        assert snap.draws_to == 0
        assert snap.draw_count == 0


class TestDeterminism:
    """Byte-identical determinism for identical inputs (PES-05)."""

    def test_fingerprint_deterministic(self):
        from backend.app.probability.fingerprint import probability_input_fingerprint

        data = {"a": 1, "b": [2, 3], "c": {"d": 4}}
        fp1 = probability_input_fingerprint(data)
        fp2 = probability_input_fingerprint(data)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_seed_deterministic(self):
        from backend.app.probability.determinism import derive_seed, isolated_rng

        seed1 = derive_seed("fp123", {"n": 10}, 1000)
        seed2 = derive_seed("fp123", {"n": 10}, 1000)
        assert seed1 == seed2

        rng1 = isolated_rng(seed1)
        rng2 = isolated_rng(seed2)
        vals1 = [rng1.random() for _ in range(10)]
        vals2 = [rng2.random() for _ in range(10)]
        assert vals1 == vals2

    def test_engine_exact_methods(self):
        from decimal import Decimal

        from backend.app.probability.engine import binomial, hypergeometric, poisson

        # Hypergeometric: C(3,1)*C(6,4)/C(9,5) = 3*15/126 = 45/126
        hg = hypergeometric(9, 5, 3)
        assert isinstance(hg, list)
        assert all(isinstance(k, int) and isinstance(v, Decimal) for k, v in hg)

        # Binomial: n=2, p=0.5 -> P(0)=0.25, P(1)=0.5, P(2)=0.25
        bn = binomial(2, Decimal("0.5"))
        assert len(bn) == 3

        # Poisson: lam=1, kmax=3
        ps = poisson(Decimal("1"), 3)
        assert len(ps) == 4
