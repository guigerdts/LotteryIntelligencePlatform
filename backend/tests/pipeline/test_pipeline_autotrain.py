"""D12 RED — missing ml/dl artifacts are auto-trained with registry defaults."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


def test_missing_ml_dl_are_autotrained_and_chain_proceeds(
    db: Session, pipeline_db: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing ml/dl snapshots are auto-trained in-stream and the chain proceeds to gen."""
    from backend.app.services.dl_service import DlService
    from backend.app.services.ml_service import MlService
    from backend.app.services.pipeline_service import PipelineService

    ml_calls: list[dict] = []
    dl_calls: list[dict] = []
    original_ml = MlService.train
    original_dl = DlService.train

    def spying_ml(self: object, *args: object, **kwargs: object) -> object:
        out = original_ml(self, *args, **kwargs)  # type: ignore[arg-type]
        ml_calls.append({"args": args, "kwargs": kwargs, "outcomes": list(out)})
        return out

    def spying_dl(self: object, *args: object, **kwargs: object) -> object:
        out = original_dl(self, *args, **kwargs)  # type: ignore[arg-type]
        dl_calls.append({"args": args, "kwargs": kwargs, "out": out})
        return out

    monkeypatch.setattr(MlService, "train", spying_ml)
    monkeypatch.setattr(DlService, "train", spying_dl)

    outcome = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=9)

    # Auto-train fired exactly once per engine with registry defaults.
    assert len(ml_calls) == 1
    assert len(ml_calls[0]["outcomes"]) == 5  # all core-5 families trained
    for oc in ml_calls[0]["outcomes"]:
        assert oc.status == "active", f"{oc.family}: {oc.error}"
    assert len(dl_calls) == 1
    # Registry-default model bundle (no explicit override in the call).
    assert "model_set" not in dl_calls[0]["kwargs"]

    # The chain proceeded end to end despite the missing artifacts (D12).
    statuses = {s.name: s.status for s in outcome.stages}
    assert statuses["ml"] == "completed"
    assert statuses["dl"] == "completed"
    assert statuses["gen"] == "completed"
    assert outcome.result is not None


def test_current_artifacts_skip_retraining(
    db: Session, pipeline_db: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing active artifacts are reused without triggering retraining."""
    """Warm chain must NOT retrain ml (non-idempotent writer → gated stage)."""
    from backend.app.services.ml_service import MlService
    from backend.app.services.pipeline_service import PipelineService

    PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=9)

    ml_calls: list[int] = []
    original_ml = MlService.train

    def counting_ml(self: object, *args: object, **kwargs: object) -> object:
        ml_calls.append(1)
        return original_ml(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(MlService, "train", counting_ml)

    warm = PipelineService(db).run(lottery_id=pipeline_db, count=2, seed=9)
    assert ml_calls == []  # skipped without invoking the trainer
    assert next(s for s in warm.stages if s.name == "ml").status == "skipped"
