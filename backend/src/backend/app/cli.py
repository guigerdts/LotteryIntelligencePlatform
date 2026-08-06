"""Command-line interface: on-demand import and dataset generation (IE-07/08/09).

Backs the ``lip`` console script declared in ``pyproject.toml``
(``[project.scripts]``). Both commands are explicit, on-demand operations — no
scheduler exists anywhere (IE-08). ``lip import`` records a run with
``import_type="cli"`` and ``started_by`` set from the invoking user (IE-07);
``lip dataset-generate`` builds an immutable, locked dataset (D5/IE-09) — import
never creates a dataset. The CLI never shells out and never touches the HTTP
layer; it resolves the lottery code via the repository and delegates all work to
``ImportService``.
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
from backend.app.services.import_service import ImportService


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


def _resolve_lottery(session, code: str) -> int:
    """Resolve a ``lottery_code`` natural key to its id (RESOURCE_NOT_FOUND, CD-07)."""
    lottery = LotteryRepository(session).get_by_code(code)
    if lottery is None:
        raise NotFoundError(f"lottery {code!r} does not exist")
    return lottery.id


def _generator_version() -> str:
    """The dataset generator version recorded on every dataset (CD-03)."""
    return get_settings().app_version