"""Command-line interface: on-demand import, dataset generation, and snapshot generation (FES-09).

Backs the ``lip`` console script declared in ``pyproject.toml``
(``[project.scripts]``). All commands are explicit, on-demand operations — no
scheduler exists anywhere (IE-08). ``lip import`` records a run with
``import_type="cli"`` and ``started_by`` set from the invoking user (IE-07);
``lip dataset-generate`` builds an immutable, locked dataset (D5/IE-09) — import
never creates a dataset; ``lip statistics`` and ``lip feature-engine`` generate
versioned, immutable snapshots on demand (design §6, FES-09). None of these ever
auto-run during an import (FES-09: no import hooks). The CLI never shells out and
never touches the HTTP layer; it resolves the lottery code via the repository and
delegates all work to the services.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys

from backend.app.config.settings import get_settings
from backend.app.repositories.base import SessionLocal
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import NotFoundError, ServiceError
from backend.app.services.feature_engine_service import FEATURE_SET_CORE, FeatureEngineService
from backend.app.services.graph_service import GraphService
from backend.app.services.import_service import ImportService
from backend.app.services.probability_service import PROB_MODEL_SET_CORE, ProbabilityService
from backend.app.services.statistics_service import StatisticsService


def main(argv: list[str] | None = None) -> int:
    """Parse the ``lip`` command line and dispatch; exit 1 on a domain error."""
    parser = argparse.ArgumentParser(
        prog="lip",
        description=(
            "Lottery Intelligence Platform CLI: on-demand CSV import and dataset "
            "generation (no scheduler)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser(
        "import",
        help="import a CSV draw-history file (IE-07: import_type=cli)",
    )
    import_parser.add_argument("--lottery", required=True, help="lottery code (natural key)")
    import_parser.add_argument("--file", required=True, help="path to the CSV file to import")
    import_parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="resume a matching partial run for the same file (D-D2)",
    )
    import_parser.set_defaults(func=_cmd_import)

    generate_parser = subparsers.add_parser(
        "dataset-generate",
        help="generate an immutable, locked dataset on demand (IE-09)",
    )
    generate_parser.add_argument(
        "--version", required=True, help="dataset version (UNIQUE natural key)"
    )
    generate_parser.add_argument("--lottery", required=True, help="lottery code (natural key)")
    generate_parser.add_argument(
        "--filters",
        default=None,
        help='JSON filters, e.g. \'{"date_from": "2024-01-01", "date_to": "2024-12-31"}\'',
    )
    generate_parser.set_defaults(func=_cmd_dataset_generate)

    statistics_parser = subparsers.add_parser(
        "statistics",
        help="generate or rebuild a statistics snapshot on demand (design §6)",
    )
    statistics_sub = statistics_parser.add_subparsers(dest="statistics_command", required=True)

    statistics_generate = statistics_sub.add_parser(
        "generate", help="generate a snapshot (incremental over an existing one)"
    )
    statistics_generate.add_argument("--lottery", required=True, help="lottery code (natural key)")
    statistics_generate.add_argument(
        "--metrics", default="core", help="metric bundle (only 'core' is supported)"
    )
    statistics_generate.add_argument(
        "--scope", default="incremental", choices=["incremental", "full"], help="fold scope"
    )
    statistics_generate.set_defaults(func=_cmd_statistics_generate)

    statistics_rebuild = statistics_sub.add_parser(
        "rebuild", help="force a full rebuild as a NEW version (never mutates a snapshot)"
    )
    statistics_rebuild.add_argument("--lottery", required=True, help="lottery code (natural key)")
    statistics_rebuild.add_argument("--metrics", default="core", help="metric bundle")
    statistics_rebuild.set_defaults(func=_cmd_statistics_rebuild)

    feature_parser = subparsers.add_parser(
        "feature-engine",
        help="generate or rebuild a feature snapshot on demand (design §6, FES-09)",
    )
    feature_sub = feature_parser.add_subparsers(dest="feature_command", required=True)

    feature_generate = feature_sub.add_parser(
        "generate", help="generate a feature snapshot (incremental over an existing one)"
    )
    feature_generate.add_argument("--lottery", required=True, help="lottery code (natural key)")
    feature_generate.add_argument(
        "--scope", default="incremental", choices=["incremental", "full"], help="fold scope"
    )
    feature_generate.set_defaults(func=_cmd_feature_generate)

    feature_rebuild = feature_sub.add_parser(
        "rebuild", help="force a full rebuild as a NEW version (never mutates a snapshot)"
    )
    feature_rebuild.add_argument("--lottery", required=True, help="lottery code (natural key)")
    feature_rebuild.set_defaults(func=_cmd_feature_rebuild)

    probability_parser = subparsers.add_parser(
        "probability",
        help="generate or rebuild a probability snapshot on demand (design §6, PES-08)",
    )
    probability_sub = probability_parser.add_subparsers(dest="probability_command", required=True)

    probability_generate = probability_sub.add_parser(
        "generate", help="generate a probability snapshot (incremental over an existing one)"
    )
    probability_generate.add_argument("--lottery", required=True, help="lottery code (natural key)")
    probability_generate.add_argument(
        "--model-set", default="core", help="model bundle (only 'core' is supported)"
    )
    probability_generate.add_argument(
        "--scope", default="incremental", choices=["incremental", "full"], help="fold scope"
    )
    probability_generate.set_defaults(func=_cmd_probability_generate)

    probability_rebuild = probability_sub.add_parser(
        "rebuild", help="force a full probability rebuild as a NEW version"
    )
    probability_rebuild.add_argument("--lottery", required=True, help="lottery code (natural key)")
    probability_rebuild.add_argument("--model-set", default="core", help="model bundle")
    probability_rebuild.set_defaults(func=_cmd_probability_rebuild)

    graph_parser = subparsers.add_parser(
        "graph",
        help="compute or list graph snapshots on demand (REQ-08, REQ-09)",
    )
    graph_sub = graph_parser.add_subparsers(dest="graph_command", required=True)

    graph_compute = graph_sub.add_parser("compute", help="compute a graph snapshot (idempotent)")
    graph_compute.add_argument("--lottery", required=True, help="lottery code (natural key)")
    graph_compute.add_argument(
        "--graph-type", default="cooccurrence", help="graph type (default: cooccurrence)"
    )
    graph_compute.add_argument(
        "--window", type=int, default=None, help="rolling window (None for full-history)"
    )
    graph_compute.add_argument(
        "--threshold", type=int, default=1, help="edge threshold (default: 1)"
    )
    graph_compute.set_defaults(func=_cmd_graph_compute)

    graph_list = graph_sub.add_parser("list", help="list graph snapshots for a lottery")
    graph_list.add_argument("--lottery", required=True, help="lottery code (natural key)")
    graph_list.add_argument("--graph-type", default="cooccurrence", help="graph type filter")
    graph_list.set_defaults(func=_cmd_graph_list)

    graph_show = graph_sub.add_parser("show", help="show graph snapshot values")
    graph_show.add_argument("--lottery", required=True, help="lottery code (natural key)")
    graph_show.add_argument("--snapshot-id", required=True, type=int, help="snapshot ID")
    graph_show.set_defaults(func=_cmd_graph_show)

    # --- ML commands (Fase 7, MLE-08) ---
    ml_parser = subparsers.add_parser(
        "ml",
        help="ML engine: train models, list snapshots, view metrics (Fase 7)",
    )
    ml_sub = ml_parser.add_subparsers(dest="ml_command", required=True)

    ml_train = ml_sub.add_parser("train", help="train one or all core-5 ML families")
    ml_train.add_argument("--lottery", required=True, help="lottery code (natural key)")
    ml_train.add_argument("--family", default=None, help="model family (omit for all 5)")
    ml_train.set_defaults(func=_cmd_ml_train)

    ml_models = ml_sub.add_parser("models", help="show active ML snapshot for a lottery")
    ml_models.add_argument("--lottery", required=True, help="lottery code (natural key)")
    ml_models.set_defaults(func=_cmd_ml_models)

    ml_metrics = ml_sub.add_parser("metrics", help="show ML metrics for the active snapshot")
    ml_metrics.add_argument("--lottery", required=True, help="lottery code (natural key)")
    ml_metrics.add_argument("--model", default=None, help="filter by model_id")
    ml_metrics.set_defaults(func=_cmd_ml_metrics)

    # --- Opt commands (Fase 9, OE-10) ---
    opt_parser = subparsers.add_parser(
        "opt",
        help="Optimization engine: train optimizers, list snapshots, view results (Fase 9)",
    )
    opt_sub = opt_parser.add_subparsers(dest="opt_command", required=True)

    opt_train = opt_sub.add_parser("train", help="run one optimization pass")
    opt_train.add_argument("--lottery", required=True, help="lottery code (natural key)")
    opt_train.add_argument(
        "--optimizer", default="ga", help="optimizer slug: ga, pso, bayesian, sa"
    )
    opt_train.add_argument(
        "--metric", default="f1", help="objective metric: f1, roc_auc, accuracy, precision, recall"
    )
    opt_train.add_argument(
        "--direction", default="maximize", help="direction: maximize or minimize"
    )
    opt_train.add_argument("--seed", type=int, default=42, help="RNG seed")
    opt_train.set_defaults(func=_cmd_opt_train)

    opt_models = opt_sub.add_parser("models", help="show active opt snapshot for a lottery")
    opt_models.add_argument("--lottery", required=True, help="lottery code (natural key)")
    opt_models.add_argument("--optimizer", default="ga", help="optimizer slug")
    opt_models.set_defaults(func=_cmd_opt_models)

    opt_metrics = opt_sub.add_parser("metrics", help="show opt results for the active snapshot")
    opt_metrics.add_argument("--lottery", required=True, help="lottery code (natural key)")
    opt_metrics.add_argument("--optimizer", default="ga", help="optimizer slug")
    opt_metrics.set_defaults(func=_cmd_opt_metrics)

    opt_params = opt_sub.add_parser("params", help="show default params for an optimizer")
    opt_params.add_argument("--optimizer", default="ga", help="optimizer slug")
    opt_params.set_defaults(func=_cmd_opt_params)

    # --- Experiment commands (Fase 11, EXP-001) ---
    exp_parser = subparsers.add_parser(
        "exp",
        help="Experiment engine: create, list, compare, export experiments (Fase 11)",
    )
    exp_sub = exp_parser.add_subparsers(dest="exp_command", required=True)

    exp_create = exp_sub.add_parser("create", help="create a new experiment")
    exp_create.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    exp_create.add_argument("--name", required=True, help="experiment name")
    exp_create.add_argument("--description", default=None, help="experiment description")
    exp_create.set_defaults(func=_cmd_exp_create)

    exp_list = exp_sub.add_parser("list", help="list experiments for a lottery")
    exp_list.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    exp_list.add_argument("--status", default=None, help="filter by status (active|retired|failed)")
    exp_list.set_defaults(func=_cmd_exp_list)

    exp_compare = exp_sub.add_parser("compare", help="compare runs within an experiment")
    exp_compare.add_argument("--experiment-id", required=True, type=int, help="experiment ID")
    exp_compare.add_argument("--run-ids", required=True, help="comma-separated run IDs (min 2)")
    exp_compare.set_defaults(func=_cmd_exp_compare)

    exp_export = exp_sub.add_parser("export", help="export experiment results as JSON or CSV")
    exp_export.add_argument("--experiment-id", required=True, type=int, help="experiment ID")
    exp_export.add_argument(
        "--format", default="json", choices=["json", "csv"], help="export format"
    )
    exp_export.set_defaults(func=_cmd_exp_export)

    # --- Backtesting commands (Fase 10, BTS-02) ---
    bt_parser = subparsers.add_parser(
        "bt",
        help="Backtesting engine: run backtests, view history and results (Fase 10)",
    )
    bt_sub = bt_parser.add_subparsers(dest="bt_command", required=True)

    bt_run = bt_sub.add_parser("run", help="run a walk-forward backtest")
    bt_run.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    bt_run.add_argument("--strategy", required=True, help="strategy ID (e.g. ml-core-5)")
    bt_run.add_argument("--train-years", type=int, default=5, help="training window in years")
    bt_run.add_argument("--eval-count", type=int, default=1, help="eval draws per window")
    bt_run.add_argument("--seed", type=int, default=42, help="RNG seed")
    bt_run.set_defaults(func=_cmd_bt_run)

    bt_history = bt_sub.add_parser("history", help="list backtest snapshots for a lottery")
    bt_history.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    bt_history.set_defaults(func=_cmd_bt_history)

    bt_results = bt_sub.add_parser("results", help="show detailed backtest results")
    bt_results.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    bt_results.add_argument(
        "--snapshot-id", type=int, default=None, help="snapshot ID (omit for active)"
    )
    bt_results.set_defaults(func=_cmd_bt_results)

    _add_meta_subparser(subparsers)

    _add_gen_subparser(subparsers)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ServiceError as exc:
        print(f"error: [{exc.code}] {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_import(args: argparse.Namespace) -> None:
    """Run an import from the CLI; print the audit summary as JSON (IE-07)."""
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        summary = ImportService(session).run_import(
            lottery_id=lottery_id,
            source_path=args.file,
            import_type="cli",
            started_by=getpass.getuser(),
            resume=args.resume,
        )
    print(json.dumps(summary, indent=2, default=str))


def _cmd_dataset_generate(args: argparse.Namespace) -> None:
    """Generate an immutable dataset; print the created dataset summary (IE-09)."""
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        dataset = ImportService(session).generate_dataset(
            version=args.version,
            lottery_id=lottery_id,
            generator_version=_generator_version(),
            filters=args.filters,
        )
    print(
        f"dataset {dataset.version!r} created "
        f"(checksum={dataset.checksum}, locked={dataset.is_locked})"
    )


def _cmd_statistics_generate(args: argparse.Namespace) -> None:
    """Generate a statistics snapshot; print it as JSON (design §6).

    Accepts an optional ``--scope`` (default ``incremental``); a metric bundle is
    selected via ``--metrics`` (only ``core``). Mirrors ``_cmd_dataset_generate``:
    resolve the lottery code, delegate to the service, print the snapshot JSON.
    """
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        snapshot = StatisticsService(session).generate(
            lottery_id=lottery_id,
            metric_set=_metric_set_arg(args.metrics),
            scope=args.scope,
        )
    print(_snapshot_json(args.lottery, snapshot))


def _cmd_statistics_rebuild(args: argparse.Namespace) -> None:
    """Force a full rebuild as a NEW version; print the new snapshot JSON.

    ``rebuild`` maps to ``scope="full"`` (design §6), which ALWAYS writes a new
    version — it never mutates a locked snapshot.
    """
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        snapshot = StatisticsService(session).generate(
            lottery_id=lottery_id,
            metric_set=(args.metrics or "core"),
            scope="full",
        )
    print(_snapshot_json(args.lottery, snapshot))


def _metric_set_arg(metrics: str) -> str:
    """Collapse the CLI ``--metrics`` flag onto the supported bundle.

    Only the ``core`` bundle exists this release (design §8); anything else is
    rejected by ``StatisticsService.generate`` (validation_error) the same way the
    API collapses its list.
    """
    return metrics if metrics else "core"


def _cmd_feature_generate(args: argparse.Namespace) -> None:
    """Generate a feature snapshot; print the snapshot header as JSON (FES-09).

    Accepts an optional ``--scope`` (default ``incremental``) for the ``core``
    feature bundle. Mirrors ``_cmd_statistics_generate``: resolve the lottery code,
    delegate to ``FeatureEngineService.generate``, print the snapshot JSON. Explicit,
    on-demand, manual-only — an import never triggers this (FES-09).
    """
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        snapshot = FeatureEngineService(session).generate(
            lottery_id=lottery_id,
            feature_set=FEATURE_SET_CORE,
            scope=args.scope,
        )
    print(_feature_snapshot_json(args.lottery, snapshot))


def _cmd_feature_rebuild(args: argparse.Namespace) -> None:
    """Force a full feature rebuild as a NEW version; print the new snapshot JSON.

    ``rebuild`` maps to ``scope="full"`` (design §7), which ALWAYS writes a new
    version — it never mutates a locked snapshot (FES-04).
    """
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        snapshot = FeatureEngineService(session).generate(
            lottery_id=lottery_id,
            feature_set=FEATURE_SET_CORE,
            scope="full",
        )
    print(_feature_snapshot_json(args.lottery, snapshot))


def _feature_snapshot_json(lottery_code: str, snapshot) -> str:
    """Render a feature snapshot header as the CLI's deterministic JSON line."""
    return json.dumps(
        {
            "lottery_code": lottery_code,
            "snapshot_id": snapshot.id,
            "feature_set": snapshot.feature_set,
            "version": snapshot.version,
            "feature_engine_version": snapshot.feature_engine_version,
            "draws_from": snapshot.draws_from,
            "draws_to": snapshot.draws_to,
            "draw_count": snapshot.draw_count,
            "checksum": snapshot.checksum,
            "status": snapshot.status,
            "is_locked": snapshot.is_locked,
        },
        indent=2,
    )


def _cmd_probability_generate(args: argparse.Namespace) -> None:
    """Generate a probability snapshot; print the snapshot header as JSON (PES-08).

    Accepts an optional ``--scope`` (default ``incremental``) for the ``core``
    model bundle. Mirrors ``_cmd_feature_generate``: resolve the lottery code,
    delegate to ``ProbabilityService.generate``, print the snapshot JSON.
    """
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        snapshot = ProbabilityService(session).generate(
            lottery_id=lottery_id,
            model_set=args.model_set or PROB_MODEL_SET_CORE,
            scope=args.scope,
        )
    print(_probability_snapshot_json(args.lottery, snapshot))


def _cmd_probability_rebuild(args: argparse.Namespace) -> None:
    """Force a full probability rebuild as a NEW version; print the new snapshot JSON.

    ``rebuild`` maps to ``scope="full"`` (design §7), which ALWAYS writes a new
    version — it never mutates a locked snapshot (PES-04).
    """
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        snapshot = ProbabilityService(session).generate(
            lottery_id=lottery_id,
            model_set=args.model_set or PROB_MODEL_SET_CORE,
            scope="full",
        )
    print(_probability_snapshot_json(args.lottery, snapshot))


def _probability_snapshot_json(lottery_code: str, snapshot) -> str:
    """Render a probability snapshot header as the CLI's deterministic JSON line."""
    return json.dumps(
        {
            "lottery_code": lottery_code,
            "snapshot_id": snapshot.id,
            "model_set": snapshot.model_set,
            "version": snapshot.version,
            "prob_generator_version": snapshot.prob_generator_version,
            "draws_from": snapshot.draws_from,
            "draws_to": snapshot.draws_to,
            "draw_count": snapshot.draw_count,
            "checksum": snapshot.checksum,
            "status": snapshot.status,
            "is_locked": snapshot.is_locked,
        },
        indent=2,
    )


def _cmd_graph_compute(args: argparse.Namespace) -> None:
    """Compute a graph snapshot; print the snapshot header as JSON (REQ-08)."""
    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        result = GraphService(session).compute(
            lottery_id=lottery_id,
            graph_type=args.graph_type,
            window=args.window,
            threshold=args.threshold,
        )
    print(_graph_snapshot_json(args.lottery, result.snapshot))


def _cmd_graph_list(args: argparse.Namespace) -> None:
    """List graph snapshots for a lottery; print as JSON (REQ-08)."""
    from sqlalchemy import select

    from backend.app.models.graph_snapshot import GraphSnapshot

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        stmt = (
            select(GraphSnapshot)
            .where(
                GraphSnapshot.lottery_id == lottery_id,
                GraphSnapshot.graph_type == args.graph_type,
            )
            .order_by(GraphSnapshot.version.desc())
        )
        snapshots = session.scalars(stmt).all()
        items = [
            {
                "snapshot_id": s.id,
                "version": s.version,
                "status": s.status,
                "draw_count": s.draw_count,
                "checksum": s.checksum,
            }
            for s in snapshots
        ]
    print(json.dumps({"lottery_code": args.lottery, "snapshots": items}, indent=2))


def _cmd_graph_show(args: argparse.Namespace) -> None:
    """Show graph snapshot values; print as JSON (REQ-08, no precompute)."""
    from sqlalchemy import select

    from backend.app.graph.snapshot_store import load_snapshot_values
    from backend.app.models.graph_snapshot import GraphSnapshot

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        stmt = select(GraphSnapshot).where(
            GraphSnapshot.id == args.snapshot_id,
            GraphSnapshot.lottery_id == lottery_id,
        )
        snapshot = session.scalar(stmt)
        if snapshot is None:
            raise NotFoundError(f"snapshot {args.snapshot_id!r} not found")
        db_values = load_snapshot_values(session, args.snapshot_id)
        rows = [
            {
                "metric_type": v.metric_type,
                "subject": v.subject,
                "draw_number": v.draw_number,
                "value": str(v.value),
            }
            for v in db_values
        ]
    print(
        json.dumps(
            {
                "snapshot_id": args.snapshot_id,
                "graph_type": snapshot.graph_type,
                "version": snapshot.version,
                "values": rows,
                "count": len(rows),
            },
            indent=2,
        )
    )


def _graph_snapshot_json(lottery_code: str, snapshot) -> str:
    """Render a graph snapshot header as the CLI's deterministic JSON line."""
    return json.dumps(
        {
            "lottery_code": lottery_code,
            "snapshot_id": snapshot.id,
            "graph_type": snapshot.graph_type,
            "version": snapshot.version,
            "generator_version": snapshot.graph_generator_version,
            "draws_from": snapshot.draws_from,
            "draws_to": snapshot.draws_to,
            "draw_count": snapshot.draw_count,
            "checksum": snapshot.checksum,
            "fingerprint": snapshot.input_fingerprint,
            "status": snapshot.status,
        },
        indent=2,
    )


def _snapshot_json(lottery_code: str, snapshot) -> str:
    """Render a snapshot header as the CLI's deterministic JSON line."""
    return json.dumps(
        {
            "lottery_code": lottery_code,
            "snapshot_id": snapshot.id,
            "metric_set": snapshot.metric_set,
            "version": snapshot.version,
            "generator_version": snapshot.generator_version,
            "engine_version": snapshot.engine_version,
            "draws_from": snapshot.draws_from,
            "draws_to": snapshot.draws_to,
            "draw_count": snapshot.draw_count,
            "checksum": snapshot.checksum,
            "status": snapshot.status,
            "is_locked": snapshot.is_locked,
        },
        indent=2,
    )


def _resolve_lottery(session, code: str) -> int:
    """Resolve a ``lottery_code`` natural key to its id (RESOURCE_NOT_FOUND, CD-07)."""
    lottery = LotteryRepository(session).get_by_code(code)
    if lottery is None:
        raise NotFoundError(f"lottery {code!r} does not exist")
    return lottery.id


def _generator_version() -> str:
    """The dataset generator version recorded on every dataset (CD-03)."""
    return get_settings().app_version


# --- ML CLI commands (Fase 7, MLE-08) ---


def _cmd_ml_train(args: argparse.Namespace) -> None:
    """Train one or all core-5 ML families; print results as JSON."""
    from backend.app.services.ml_service import MlService

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        draw_reader = _CliDrawAdapter(session)
        feature_provider = _CliFeatureAdapter(session)
        service = MlService(session, draw_reader, feature_provider)
        outcomes = service.train(lottery_id, family=args.family)
    print(
        json.dumps(
            [
                {
                    "family": o.family,
                    "status": o.status,
                    "snapshot_id": o.snapshot_id,
                    "fingerprint": o.fingerprint,
                    "metrics_checksum": o.metrics_checksum,
                    "error": o.error,
                }
                for o in outcomes
            ],
            indent=2,
        )
    )


def _cmd_ml_models(args: argparse.Namespace) -> None:
    """Show the active ML snapshot for a lottery; print as JSON."""
    from backend.app.services.ml_service import MlService

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        draw_reader = _CliDrawAdapter(session)
        feature_provider = _CliFeatureAdapter(session)
        service = MlService(session, draw_reader, feature_provider)
        result = service.get_active_snapshot(lottery_id)
    if result is None:
        print(json.dumps({"error": "no active ML snapshot"}))
    else:
        print(json.dumps(result, indent=2))


def _cmd_ml_metrics(args: argparse.Namespace) -> None:
    """Show ML metrics for the active snapshot; print as JSON."""
    from backend.app.services.ml_service import MlService

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        draw_reader = _CliDrawAdapter(session)
        feature_provider = _CliFeatureAdapter(session)
        service = MlService(session, draw_reader, feature_provider)
        metrics = service.get_metrics(lottery_id, model_id=args.model)
    print(json.dumps(metrics, indent=2))


# --- Opt CLI commands (Fase 9, OE-10) ---


def _cmd_opt_train(args: argparse.Namespace) -> None:
    """Run one optimization pass; print results as JSON."""
    from backend.app.opt.search_space import SearchParam, SearchSpace
    from backend.app.services.opt_service import OptService

    search_space = SearchSpace(
        params=(
            SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),
            SearchParam(name="n_estimators", param_type="integer", low=10, high=200),
        )
    )

    def dummy_objective(params: dict) -> float:
        """Placeholder objective — returns 0.5 for testing."""
        return 0.5

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        draw_count = _cli_count_draws(session, lottery_id)
        service = OptService(
            session=session,
            objective_fn=dummy_objective,
            search_space=search_space,
            lottery_id=lottery_id,
            optimizer=args.optimizer,
            metric=args.metric,
            direction=args.direction,
            seed=args.seed,
            draw_count=draw_count,
        )
        outcome = service.train()
    print(
        json.dumps(
            {
                "optimizer": outcome.optimizer,
                "status": outcome.status,
                "snapshot_id": outcome.snapshot_id,
                "fingerprint": outcome.fingerprint,
                "best_fitness": outcome.best_fitness,
                "n_evaluations": outcome.n_evaluations,
                "error": outcome.error,
            },
            indent=2,
        )
    )


def _cmd_opt_models(args: argparse.Namespace) -> None:
    """Show the active opt snapshot for a lottery; print as JSON."""
    from backend.app.opt.search_space import SearchParam, SearchSpace
    from backend.app.services.opt_service import OptService

    search_space = SearchSpace(
        params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
    )

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        service = OptService(
            session=session,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=lottery_id,
            optimizer=args.optimizer,
        )
        result = service.get_active_snapshot()
    if result is None:
        print(json.dumps({"error": "no active opt snapshot"}))
    else:
        print(json.dumps(result, indent=2))


def _cmd_opt_metrics(args: argparse.Namespace) -> None:
    """Show opt results for the active snapshot; print as JSON."""
    from backend.app.opt.search_space import SearchParam, SearchSpace
    from backend.app.services.opt_service import OptService

    search_space = SearchSpace(
        params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
    )

    with SessionLocal() as session:
        lottery_id = _resolve_lottery(session, args.lottery)
        service = OptService(
            session=session,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=lottery_id,
            optimizer=args.optimizer,
        )
        results = service.get_results()
    print(json.dumps(results, indent=2))


def _cmd_opt_params(args: argparse.Namespace) -> None:
    """Show default params for an optimizer; print as JSON."""
    from backend.app.opt.registry import get_optimizer_defaults

    try:
        params = get_optimizer_defaults(args.optimizer)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return
    print(json.dumps({"optimizer": args.optimizer, "params": params}, indent=2))


# --- Backtesting CLI commands (Fase 10, BTS-02) ---


def _cmd_exp_create(args: argparse.Namespace) -> None:
    """Create a new experiment; print the experiment as JSON."""
    from backend.app.services.exp_service import ExpService

    with SessionLocal() as session:
        service = ExpService(session)
        outcome = service.create(
            lottery_id=args.lottery_id,
            name=args.name,
            description=args.description,
        )
    print(
        json.dumps(
            {
                "experiment_id": outcome.experiment_id,
                "lottery_id": outcome.lottery_id,
                "name": outcome.name,
                "fingerprint": outcome.fingerprint,
                "version": outcome.version,
                "status": outcome.status,
            },
            indent=2,
        )
    )


def _cmd_exp_list(args: argparse.Namespace) -> None:
    """List experiments for a lottery; print as JSON."""
    from backend.app.services.exp_service import ExpService

    with SessionLocal() as session:
        service = ExpService(session)
        entries = service.list_experiments(args.lottery_id, status=args.status)
    print(
        json.dumps(
            [
                {
                    "experiment_id": e.experiment_id,
                    "lottery_id": e.lottery_id,
                    "name": e.name,
                    "description": e.description,
                    "fingerprint": e.fingerprint,
                    "version": e.version,
                    "status": e.status,
                    "config_json": e.config_json,
                    "created_at": e.created_at,
                }
                for e in entries
            ],
            indent=2,
        )
    )


def _cmd_exp_compare(args: argparse.Namespace) -> None:
    """Compare runs within an experiment; print comparison JSON."""
    from backend.app.services.exp_service import ExpService

    run_ids = [int(x.strip()) for x in args.run_ids.split(",")]
    with SessionLocal() as session:
        service = ExpService(session)
        outcome = service.compare(args.experiment_id, run_ids=run_ids)
    print(outcome.comparison_json)


def _cmd_exp_export(args: argparse.Namespace) -> None:
    """Export experiment results as JSON or CSV."""
    from backend.app.services.exp_service import ExpService

    with SessionLocal() as session:
        service = ExpService(session)
        content = service.export(args.experiment_id, format=args.format)
    print(content)


def _cmd_bt_run(args: argparse.Namespace) -> None:
    """Run a walk-forward backtest; print outcome as JSON."""
    from backend.app.services.bt_service import BtService

    with SessionLocal() as session:
        service = BtService(session)
        outcome = service.run(
            lottery_id=args.lottery_id,
            strategy_id=args.strategy,
            train_years=args.train_years,
            eval_count=args.eval_count,
            seed=args.seed,
        )
    print(
        json.dumps(
            {
                "snapshot_id": outcome.snapshot_id,
                "lottery_id": outcome.lottery_id,
                "strategy_id": outcome.strategy_id,
                "fingerprint": outcome.fingerprint,
                "version": outcome.version,
                "status": outcome.status,
            },
            indent=2,
        )
    )


def _cmd_bt_history(args: argparse.Namespace) -> None:
    """List backtest snapshots for a lottery; print as JSON."""
    from backend.app.services.bt_service import BtService

    with SessionLocal() as session:
        service = BtService(session)
        entries = service.history(args.lottery_id)
    print(
        json.dumps(
            [
                {
                    "snapshot_id": e.snapshot_id,
                    "lottery_id": e.lottery_id,
                    "strategy_id": e.strategy_id,
                    "fingerprint": e.fingerprint,
                    "version": e.version,
                    "status": e.status,
                    "created_at": e.created_at,
                }
                for e in entries
            ],
            indent=2,
        )
    )


def _cmd_bt_results(args: argparse.Namespace) -> None:
    """Show detailed backtest results; print as JSON."""
    from backend.app.services.bt_service import BtService

    with SessionLocal() as session:
        service = BtService(session)
        raw = service.results(args.lottery_id, snapshot_id=args.snapshot_id)
    print(json.dumps(raw, indent=2))


# --- Meta Learning commands (Fase 12, META-014) ---


def _add_meta_subparser(subparsers) -> None:
    """Add ``lip meta`` subparser with 4 subcommands (META-014)."""
    meta_parser = subparsers.add_parser(
        "meta",
        help="Meta Learning: rank, select, and retrieve model rankings (Fase 12)",
    )
    meta_sub = meta_parser.add_subparsers(dest="meta_command", required=True)

    # meta rank
    meta_rank = meta_sub.add_parser("rank", help="compute a ranking for a lottery")
    meta_rank.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    meta_rank.add_argument(
        "--engine-types", nargs="*", default=None, help="engine types to include"
    )
    meta_rank.add_argument(
        "--weights", default=None, help='JSON weights, e.g. \'{"hit_rate": 0.5}\''
    )
    meta_rank.set_defaults(func=_cmd_meta_rank)

    # meta ranking
    meta_ranking = meta_sub.add_parser("ranking", help="retrieve ranking snapshot")
    meta_ranking.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    meta_ranking.add_argument("--context-hash", default=None, help="context hash filter")
    meta_ranking.set_defaults(func=_cmd_meta_ranking)

    # meta select
    meta_select = meta_sub.add_parser("select", help="compute a selection from the active ranking")
    meta_select.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    meta_select.add_argument("--top-k", type=int, default=None, help="top-K (1-20, default 5)")
    meta_select.add_argument(
        "--min-score", type=float, default=None, help="minimum score threshold"
    )
    meta_select.set_defaults(func=_cmd_meta_select)

    # meta selection
    meta_selection = meta_sub.add_parser("selection", help="retrieve selection snapshot")
    meta_selection.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    meta_selection.add_argument("--context-hash", default=None, help="context hash filter")
    meta_selection.set_defaults(func=_cmd_meta_selection)


def _cmd_meta_rank(args: argparse.Namespace) -> None:
    """Compute a ranking; print the result as JSON."""
    from backend.app.services.meta_service import MetaService

    weights = json.loads(args.weights) if args.weights else None
    with SessionLocal() as session:
        service = MetaService(session)
        result = service.rank(
            lottery_id=args.lottery_id,
            engine_types=args.engine_types,
            weights=weights,
        )
    print(
        json.dumps(
            {
                "ranking_id": result.ranking_id,
                "lottery_id": result.lottery_id,
                "context_hash": result.context_hash,
                "version": result.version,
                "status": result.status,
                "fingerprint": result.fingerprint,
                "entries": result.entries,
            },
            indent=2,
        )
    )


def _cmd_meta_ranking(args: argparse.Namespace) -> None:
    """Retrieve ranking snapshot; print as JSON."""
    from backend.app.services.meta_service import MetaService

    with SessionLocal() as session:
        service = MetaService(session)
        result = service.get_ranking(args.lottery_id, context_hash=args.context_hash)
    print(
        json.dumps(
            {
                "lottery_id": result.lottery_id,
                "context_hash": result.context_hash,
                "rankings": result.rankings,
            },
            indent=2,
        )
    )


def _cmd_meta_select(args: argparse.Namespace) -> None:
    """Compute a selection; print the result as JSON."""
    from backend.app.services.meta_service import MetaService

    with SessionLocal() as session:
        service = MetaService(session)
        result = service.select(
            lottery_id=args.lottery_id,
            top_k=args.top_k,
            min_score=args.min_score,
        )
    print(
        json.dumps(
            {
                "selection_id": result.selection_id,
                "lottery_id": result.lottery_id,
                "ranking_id": result.ranking_id,
                "context_hash": result.context_hash,
                "version": result.version,
                "status": result.status,
                "fingerprint": result.fingerprint,
                "entries": result.entries,
            },
            indent=2,
        )
    )


def _cmd_meta_selection(args: argparse.Namespace) -> None:
    """Retrieve selection snapshot; print as JSON."""
    from backend.app.services.meta_service import MetaService

    with SessionLocal() as session:
        service = MetaService(session)
        result = service.get_selection(args.lottery_id, context_hash=args.context_hash)
    print(
        json.dumps(
            {
                "lottery_id": result.lottery_id,
                "context_hash": result.context_hash,
                "selections": result.selections,
            },
            indent=2,
        )
    )


# --- Generator commands (Fase 13, GEN-011) ---


def _add_gen_subparser(subparsers) -> None:
    """Add ``lip gen`` subparser with 4 subcommands (GEN-011)."""
    gen_parser = subparsers.add_parser(
        "gen",
        help="Generator: generate lottery combinations from F12 selections + F5 (Fase 13)",
    )
    gen_sub = gen_parser.add_subparsers(dest="gen_command", required=True)

    gen_generate = gen_sub.add_parser("generate", help="generate a combination snapshot")
    gen_generate.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    gen_generate.add_argument("--count", type=int, default=None, help="combinations (1-100)")
    gen_generate.add_argument("--seed", type=int, default=None, help="seed override (GEN-009)")
    gen_generate.add_argument("--selection-id", type=int, default=None, help="selection override")
    gen_generate.set_defaults(func=_cmd_gen_generate)

    gen_combinations = gen_sub.add_parser("combinations", help="read stored combinations")
    gen_combinations.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    gen_combinations.add_argument("--snapshot-id", type=int, default=None, help="snapshot filter")
    gen_combinations.set_defaults(func=_cmd_gen_combinations)

    gen_snapshot = gen_sub.add_parser("snapshot", help="transition a snapshot lifecycle status")
    gen_snapshot.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    gen_snapshot.add_argument("--snapshot-id", required=True, type=int, help="snapshot ID")
    gen_snapshot.add_argument(
        "--status",
        required=True,
        choices=["active", "retired", "failed"],
        help="target lifecycle status",
    )
    gen_snapshot.set_defaults(func=_cmd_gen_snapshot)

    gen_snapshots = gen_sub.add_parser("snapshots", help="list snapshots for a lottery")
    gen_snapshots.add_argument("--lottery-id", required=True, type=int, help="lottery ID")
    gen_snapshots.set_defaults(func=_cmd_gen_snapshots)


def _gen_combination_dict(combo) -> dict:
    """Serialize one combination row for CLI JSON output (GEN-011)."""
    return {
        "position": combo.position,
        "numbers": combo.numbers,
        "super_number": combo.super_number,
        "score": combo.score,
    }


def _gen_snapshot_dict(snapshot) -> dict:
    """Serialize one snapshot header for CLI JSON output (GEN-011)."""
    return {
        "snapshot_id": snapshot.snapshot_id,
        "lottery_id": snapshot.lottery_id,
        "selection_id": snapshot.selection_id,
        "version": snapshot.version,
        "status": snapshot.status,
        "fingerprint": snapshot.fingerprint,
        "created_at": snapshot.created_at,
    }


def _cmd_gen_generate(args: argparse.Namespace) -> None:
    """Generate a combination snapshot; print the result as JSON (GEN-011)."""
    from backend.app.services.gen_service import GenService

    with SessionLocal() as session:
        service = GenService(session)
        result = service.generate(
            lottery_id=args.lottery_id,
            count=args.count,
            seed=args.seed,
            selection_id=args.selection_id,
        )
    print(
        json.dumps(
            {
                "snapshot_id": result.snapshot_id,
                "lottery_id": result.lottery_id,
                "selection_id": result.selection_id,
                "version": result.version,
                "status": result.status,
                "fingerprint": result.fingerprint,
                "seed": result.seed,
                "count": result.count,
                "combinations": [_gen_combination_dict(c) for c in result.combinations],
            },
            indent=2,
        )
    )


def _cmd_gen_combinations(args: argparse.Namespace) -> None:
    """Read stored combinations; print as JSON (GEN-011)."""
    from backend.app.services.gen_service import GenService

    with SessionLocal() as session:
        service = GenService(session)
        result = service.get_combinations(args.lottery_id, snapshot_id=args.snapshot_id)
    print(
        json.dumps(
            {
                "snapshot_id": result.snapshot_id,
                "lottery_id": result.lottery_id,
                "combinations": [_gen_combination_dict(c) for c in result.combinations],
            },
            indent=2,
        )
    )


def _cmd_gen_snapshot(args: argparse.Namespace) -> None:
    """Transition a snapshot lifecycle status; print the result as JSON (GEN-011)."""
    from backend.app.services.gen_service import GenService

    with SessionLocal() as session:
        service = GenService(session)
        result = service.update_snapshot(
            lottery_id=args.lottery_id,
            snapshot_id=args.snapshot_id,
            status=args.status,
        )
    print(json.dumps(_gen_snapshot_dict(result), indent=2))


def _cmd_gen_snapshots(args: argparse.Namespace) -> None:
    """List snapshots for a lottery; print as JSON (GEN-011)."""
    from backend.app.services.gen_service import GenService

    with SessionLocal() as session:
        service = GenService(session)
        result = service.get_snapshots(args.lottery_id)
    print(
        json.dumps(
            {
                "lottery_id": result.lottery_id,
                "snapshots": [_gen_snapshot_dict(s) for s in result.snapshots],
            },
            indent=2,
        )
    )


class _CliDrawAdapter:
    """Minimal draw adapter for CLI context."""

    def __init__(self, session) -> None:
        self._session = session

    def iter_draws(self, lottery_id: int, *, after_draw_number: int | None = None):
        from sqlalchemy import select

        from backend.app.ml.providers import DrawRow
        from backend.app.models.draw import Draw
        from backend.app.models.draw_number import DrawNumber

        stmt = select(Draw).where(Draw.lottery_id == lottery_id).order_by(Draw.draw_number)
        if after_draw_number is not None:
            stmt = stmt.where(Draw.draw_number > after_draw_number)

        for draw in self._session.execute(stmt).scalars().all():
            nums_stmt = (
                select(DrawNumber.number)
                .where(DrawNumber.draw_id == draw.id)
                .order_by(DrawNumber.position)
            )
            numbers = tuple(self._session.execute(nums_stmt).scalars().all())
            yield DrawRow(draw_number=draw.draw_number, numbers=numbers)


class _CliFeatureAdapter:
    """Minimal feature adapter for CLI context."""

    def __init__(self, session) -> None:
        self._session = session

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        from sqlalchemy import select

        from backend.app.models.feature_snapshot import FeatureSnapshot

        stmt = (
            select(FeatureSnapshot)
            .where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.status == "active",
            )
            .order_by(FeatureSnapshot.version.desc())
            .limit(1)
        )
        snap = self._session.execute(stmt).scalar_one_or_none()
        return snap.id if snap is not None else None

    def feature_rows(self, snapshot_id: int):
        from sqlalchemy import select

        from backend.app.ml.feature_reader import FeatureValueRow
        from backend.app.models.feature_value import FeatureValue

        stmt = (
            select(FeatureValue)
            .where(FeatureValue.snapshot_id == snapshot_id)
            .order_by(FeatureValue.draw_number, FeatureValue.feature_id)
        )
        for fv in self._session.execute(stmt).scalars().all():
            yield FeatureValueRow(
                feature_id=fv.feature_id,
                draw_number=fv.draw_number,
                value=float(fv.value),
            )


def _cli_count_draws(session, lottery_id: int) -> int:
    """Count the number of real draws for a lottery (OE-08, CLI)."""
    from sqlalchemy import func, select

    from backend.app.models.draw import Draw

    stmt = select(func.count()).select_from(Draw).where(Draw.lottery_id == lottery_id)
    return int(session.execute(stmt).scalar())
