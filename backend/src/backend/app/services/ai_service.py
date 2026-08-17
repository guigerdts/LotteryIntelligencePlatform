"""AiService composition root: existing services -> engine inputs (A-12)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai.engine import GenerationResult, assist, explain, interpret, report, summarize
from backend.app.ai.providers import RuleBasedTextGenerator, TextGenerator
from backend.app.models.exp_comparison import ExpComparison
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import AssistantError, NotFoundError, SnapshotNotFoundError
from backend.app.services.exp_service import ExpService
from backend.app.services.probability_service import ProbabilityService
from backend.app.services.statistics_service import StatisticsService


class AiService:
    """Composition root: existing services -> engine inputs -> GenerationResult."""

    def __init__(self, session: Session, generator: TextGenerator | None = None) -> None:
        self._session = session
        self._stats = StatisticsService(session)
        self._prob = ProbabilityService(session)
        self._exp = ExpService(session)
        self._gen = generator or RuleBasedTextGenerator()

    def explain(self, *, lottery_code: str) -> GenerationResult:
        """Explain a lottery's results; unknown lottery 404, no data -> empty text."""
        self._resolve_lottery(lottery_code)
        return self._run(lambda: explain(self._stats_inputs(lottery_code), self._gen))

    def interpret(self, *, lottery_code: str) -> GenerationResult:
        """Interpret chart data (frequencies/gaps/averages/probability rows)."""
        self._resolve_lottery(lottery_code)
        inputs = self._stats_inputs(lottery_code)
        inputs["probabilities"] = self._prob_values(lottery_code)
        return self._run(lambda: interpret(inputs, self._gen))

    def report(self, *, lottery_code: str, scope: str | None = None) -> GenerationResult:
        """Render a scoped plain-text report (frequency|gap|average|probability)."""
        self._resolve_lottery(lottery_code)
        inputs = self._stats_inputs(lottery_code)
        inputs["probabilities"] = self._prob_values(lottery_code)
        inputs["scope"] = scope
        return self._run(lambda: report(inputs, self._gen))

    def summarize(
        self, *, experiment_id: int, run_ids: list[int] | None = None
    ) -> GenerationResult:
        """Summarize an experiment comparison; no comparison -> empty text (A-09)."""
        self._exp.get(experiment_id)  # 404 EXPERIMENT_NOT_FOUND when unknown
        comparison = (
            self._exp.compare(experiment_id, run_ids=run_ids)
            if run_ids is not None
            else self._latest_comparison(experiment_id)
        )
        return self._run(
            lambda: summarize(
                {
                    "experiment_id": experiment_id,
                    "run_ids": run_ids,
                    "comparison_json": comparison.comparison_json if comparison else None,
                },
                self._gen,
            )
        )

    def assist(self, *, question: str, lottery_code: str) -> GenerationResult:
        """Classify and route a free-text question to the matching generator (A-10)."""
        self._resolve_lottery(lottery_code)
        data = self._stats_inputs(lottery_code)
        data["probabilities"] = self._prob_values(lottery_code)
        return self._run(
            lambda: assist(
                {"question": question, "lottery_code": lottery_code, "data": data}, self._gen
            )
        )

    def _run(self, function) -> GenerationResult:
        try:
            return function()
        except AssistantError:
            raise
        except Exception as exc:
            raise AssistantError(str(exc)) from exc

    def _resolve_lottery(self, lottery_code: str) -> None:
        if LotteryRepository(self._session).get_by_code(lottery_code) is None:
            raise NotFoundError(f"lottery {lottery_code!r} does not exist")

    def _stats_inputs(self, lottery_code: str) -> dict[str, Any]:
        readers = {
            "frequencies": (
                self._stats.read_frequencies,
                lambda r: {"number": r.number, "count": r.count},
            ),
            "gaps": (self._stats.read_gaps, lambda r: {"number": r.number, "avg": r.avg_gap}),
            "averages": (
                self._stats.read_averages,
                lambda r: {"series": r.series_key, "mean": r.mean},
            ),
        }
        data: dict[str, Any] = {"lottery_code": lottery_code, "scalars": []}
        for key, (reader, mapper) in readers.items():
            try:
                _, rows = reader(lottery_code=lottery_code)
                data[key] = [mapper(row) for row in rows]
            except SnapshotNotFoundError:
                data[key] = []
        return data

    def _prob_values(self, lottery_code: str) -> list[dict]:
        try:
            _, rows = self._prob.read_values(lottery_code=lottery_code)
            return [{"model": r.model_id, "subject": r.subject, "value": r.value} for r in rows]
        except SnapshotNotFoundError:
            return []

    def _latest_comparison(self, experiment_id: int) -> ExpComparison | None:
        statement = (
            select(ExpComparison)
            .where(ExpComparison.experiment_id == experiment_id)
            .order_by(ExpComparison.id.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()
