"""CSV source adapters: stream rows from a local file while hashing its bytes (D-B/D-8)."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from pathlib import Path

# The import input is a single CSV with a comma delimiter (D1/D2, IE-01).
_UTF8_ENCODING = "utf-8"


class FileAdapter:
    """Stream CSV rows from a local path, computing a streamed SHA-256 (D-B/D-G).

    Opens the file once and yields decoded rows one row at a time (the whole
    file is never loaded into memory). While streaming, every raw byte is folded
    into a SHA-256 digest exposed via :attr:`checksum` once streaming finishes;
    the digest later feeds the ``imports.checksum`` audit column (design §8/§3).

    Pure I/O: no database contact. The comma delimiter is fixed per the CSV
    column contract (IE-01/D2) and UTF-8 is enforced strictly — a byte sequence
    that is not valid UTF-8 raises ``UnicodeDecodeError`` while iterating, which
    Phase A surfaces as a whole-file rejection.
    """

    def __init__(self, path: str | Path, delimiter: str = ",") -> None:
        self._path = Path(path)
        self._delimiter = delimiter
        self._checksum: str | None = None

    @property
    def checksum(self) -> str:
        """Hex SHA-256 digest of the raw file bytes.

        Available after :meth:`stream` has been fully consumed (or exhausted, as
        Phase A does); referencing it before streaming raises ``RuntimeError``.
        """
        if self._checksum is None:
            raise RuntimeError("checksum is available only after stream() has run")
        return self._checksum

    def stream(self) -> Iterator[list[str]]:
        """Yield CSV rows one at a time, hashing the raw bytes as they stream.

        The first yielded row is the header; data rows follow. Each row is a
        list of cell strings split on the configured delimiter. Reading is
        strictly incremental (bounded memory). On completion (or when the
        generator is closed) :attr:`checksum` becomes available.
        """
        reader = csv.reader(self._decoded_lines(), delimiter=self._delimiter)
        yield from reader

    # --- private helpers ---------------------------------------------------

    def _decoded_lines(self) -> Iterator[str]:
        """Yield UTF-8 decoded lines while digesting the raw bytes of each line.

        The digest is finalized in ``finally`` so the checksum is available even
        if the generator stops early. ``UnicodeDecodeError`` (non-UTF-8) is
        left to propagate to the caller (Phase A).
        """
        hasher = hashlib.sha256()
        try:
            with self._path.open("rb") as handle:
                for raw_line in handle:
                    hasher.update(raw_line)
                    yield raw_line.decode(_UTF8_ENCODING)
        finally:
            self._checksum = hasher.hexdigest()
