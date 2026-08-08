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
    probability_rebuild.add_argument(
        "--model-set", default="core", help="model bundle"
    )
    probability_rebuild.set_defaults(func=_cmd_probability_rebuild)

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
