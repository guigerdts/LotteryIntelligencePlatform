"""Snapshot store for Meta Learning module.

Manages lifecycle of meta_rankings and meta_selections:
atomic writes, lifecycle transitions (active→retired), idempotency,
and monotonic versioning.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session


class MetaSnapshotStore:
    """I/O owner for meta_* tables (META-005, META-007, META-008, META-010).

    Handles version computation, fingerprint idempotency checks,
    lifecycle transitions, and atomic writes.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def next_version(self, lottery_id: int, context_hash: str) -> str:
        """Compute next monotonic version for (lottery_id, context_hash) (META-005, META-010).

        Returns "1" if no existing versions, else max(version) + 1 as string.
        """
        from backend.app.models.meta_ranking import MetaRanking

        result = (
            self._session.query(MetaRanking.version)
            .filter(
                MetaRanking.lottery_id == lottery_id,
                MetaRanking.context_hash == context_hash,
            )
            .order_by(MetaRanking.version.desc())
            .scalar()
        )
        if result is None:
            return "1"
        return str(int(result) + 1)

    # ------------------------------------------------------------------
    # Fingerprint lookup
    # ------------------------------------------------------------------

    def find_by_fingerprint(self, fingerprint: str) -> Any | None:
        """Find an active ranking or selection by fingerprint (META-007).

        Consults ``meta_rankings`` first, then ``meta_selections``, so both
        rank() and select() idempotency checks resolve their own record type.
        Returns the existing active record if found, None otherwise.
        """
        from backend.app.models.meta_ranking import MetaRanking
        from backend.app.models.meta_selection import MetaSelection

        ranking = (
            self._session.query(MetaRanking)
            .filter(
                MetaRanking.fingerprint == fingerprint,
                MetaRanking.status == "active",
            )
            .first()
        )
        if ranking is not None:
            return ranking

        return (
            self._session.query(MetaSelection)
            .filter(
                MetaSelection.fingerprint == fingerprint,
                MetaSelection.status == "active",
            )
            .first()
        )

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def _retire_active(self, table: str, lottery_id: int, context_hash: str) -> None:
        """Retire the currently active record for (lottery_id, context_hash) (META-008)."""
        if table == "meta_rankings":
            from backend.app.models.meta_ranking import MetaRanking

            model_cls = MetaRanking
        elif table == "meta_selections":
            from backend.app.models.meta_selection import MetaSelection

            model_cls = MetaSelection
        else:
            return

        active = (
            self._session.query(model_cls)
            .filter(
                model_cls.lottery_id == lottery_id,
                model_cls.context_hash == context_hash,
                model_cls.status == "active",
            )
            .first()
        )
        if active is not None:
            active.status = "retired"
            self._session.flush()

    # ------------------------------------------------------------------
    # Ranking persistence
    # ------------------------------------------------------------------

    def create_active_ranking(
        self,
        lottery_id: int,
        context_hash: str,
        version: str,
        fingerprint: str,
        entries: list[dict[str, Any]],
        config_json: dict[str, Any] | None = None,
    ) -> int:
        """Create an active ranking with entries in a single transaction (META-005, META-008).

        Retires any existing active ranking for the same (lottery_id, context_hash).
        Returns the new ranking ID.
        """
        from backend.app.models.meta_ranking import MetaRanking
        from backend.app.models.meta_ranking_entry import MetaRankingEntry

        # Retire existing active
        self._retire_active("meta_rankings", lottery_id, context_hash)

        # Create new ranking
        ranking = MetaRanking(
            lottery_id=lottery_id,
            context_hash=context_hash,
            version=version,
            status="active",
            fingerprint=fingerprint,
            config_json=json.dumps(config_json) if config_json else None,
        )
        self._session.add(ranking)
        self._session.flush()

        # Create entries
        for entry in entries:
            rank_entry = MetaRankingEntry(
                ranking_id=ranking.id,
                model_id=entry["model_id"],
                engine_type=entry["engine_type"],
                score=entry["score"],
                metrics_json=json.dumps(entry.get("metrics", {})),
            )
            self._session.add(rank_entry)

        self._session.flush()
        return ranking.id

    # ------------------------------------------------------------------
    # Selection persistence
    # ------------------------------------------------------------------

    def create_active_selection(
        self,
        lottery_id: int,
        context_hash: str,
        version: str,
        fingerprint: str,
        ranking_id: int,
        entries: list[dict[str, Any]],
        config_json: dict[str, Any] | None = None,
    ) -> int:
        """Create an active selection with entries in a single transaction (META-006, META-008).

        Retires any existing active selection for the same (lottery_id, context_hash).
        Returns the new selection ID.
        """
        from backend.app.models.meta_selection import MetaSelection
        from backend.app.models.meta_selection_entry import MetaSelectionEntry

        # Retire existing active
        self._retire_active("meta_selections", lottery_id, context_hash)

        # Create new selection
        selection = MetaSelection(
            lottery_id=lottery_id,
            context_hash=context_hash,
            version=version,
            status="active",
            fingerprint=fingerprint,
            config_json=json.dumps(config_json) if config_json else None,
        )
        self._session.add(selection)
        self._session.flush()

        # Create entries
        for entry in entries:
            sel_entry = MetaSelectionEntry(
                selection_id=selection.id,
                ranking_id=ranking_id,
                model_id=entry["model_id"],
                engine_type=entry["engine_type"],
                rank=entry["rank"],
                score=entry["score"],
            )
            self._session.add(sel_entry)

        self._session.flush()
        return selection.id

    # ------------------------------------------------------------------
    # History queries
    # ------------------------------------------------------------------

    def get_rankings(self, lottery_id: int, context_hash: str | None = None) -> list[Any]:
        """Get all rankings for a lottery, optionally filtered by context_hash (META-010).

        Returns all (active + retired) ordered by version DESC.
        """
        from backend.app.models.meta_ranking import MetaRanking

        query = self._session.query(MetaRanking).filter(
            MetaRanking.lottery_id == lottery_id,
        )
        if context_hash is not None:
            query = query.filter(MetaRanking.context_hash == context_hash)
        return query.order_by(MetaRanking.version.desc()).all()

    def get_selections(self, lottery_id: int, context_hash: str | None = None) -> list[Any]:
        """Get all selections for a lottery, optionally filtered by context_hash (META-010).

        Returns all (active + retired) ordered by version DESC.
        """
        from backend.app.models.meta_selection import MetaSelection

        query = self._session.query(MetaSelection).filter(
            MetaSelection.lottery_id == lottery_id,
        )
        if context_hash is not None:
            query = query.filter(MetaSelection.context_hash == context_hash)
        return query.order_by(MetaSelection.version.desc()).all()
