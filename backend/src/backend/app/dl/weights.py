"""Custom weights serialization format (DLE-09, no pickle/joblib).

Binary format::

    Magic       8B   ``LIPDLW01``
    FmtVer      1B   ``0x01``
    FP-Len      2B   big-endian uint16
    Fingerprint NB   ASCII hex (SHA-256 = 64 chars)
    Manifest-Len 4B  big-endian uint32
    Manifest    MB   UTF-8 JSON ``{architecture, hyperparameters, seed,
                       version, W, weight_shapes}``
    Weights     WB   raw float32 LE, concatenated in sorted key order
    Checksum    32B  SHA-256 over everything before it

Max total size: 16 MiB.  Validation rejects truncated, tampered, or
oversized payloads.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

import numpy as np

if TYPE_CHECKING:  # pragma: no cover — type-check only, torch stays deferred
    import torch

MAGIC: Final[bytes] = b"LIPDLW01"
FORMAT_VERSION: Final[int] = 1
MAX_WEIGHTS_SIZE: Final[int] = 16 * 1024 * 1024  # 16 MiB


class WeightsError(Exception):
    """Base class for weights format errors."""


class InvalidMagicError(WeightsError):
    """Magic bytes do not match ``LIPDLW01``."""


class InvalidFormatVersionError(WeightsError):
    """Format version not recognised."""


class FingerprintMismatchError(WeightsError):
    """Embedded fingerprint differs from expected."""


class ChecksumMismatchError(WeightsError):
    """SHA-256 checksum does not match payload."""


class PayloadTooLargeError(WeightsError):
    """Encoded weights exceed 16 MiB."""


class TruncatedPayloadError(WeightsError):
    """Blob is shorter than the declared structure."""


class InvalidManifestError(WeightsError):
    """Manifest JSON is invalid or missing required keys."""


# ── encode ──────────────────────────────────────────────────────────────


def encode_weights(
    state_dict: Mapping[str, torch.Tensor],
    *,
    fingerprint: str,
    architecture: str,
    hyperparameters: dict[str, object],
    seed: int,
    version: str,
    W: int,
) -> bytes:
    """Serialize a model state_dict into the custom binary format.

    Parameters
    ----------
    state_dict:
        PyTorch parameter state (from ``model.state_dict()``).
    fingerprint:
        SHA-256 hex digest identifying this training run.
    architecture:
        Model family (``"mlp"`` or ``"lstm"``).
    hyperparameters:
        Architecture hyperparams (JSON-serializable).
    seed:
        RNG seed used during training.
    version:
        ``DL_GENERATOR_VERSION``.
    W:
        Window size.

    Returns
    -------
    bytes
        Complete binary blob ready for DB storage.

    Raises
    ------
    PayloadTooLargeError
        If the total encoded size exceeds 16 MiB.
    """
    # Sort keys deterministically.
    sorted_keys = sorted(state_dict.keys())

    # Build weight_shapes manifest entry.
    weight_shapes: dict[str, list[int]] = {}
    weight_chunks: list[bytes] = []
    for key in sorted_keys:
        tensor = state_dict[key].detach().cpu().contiguous()
        weight_shapes[key] = list(tensor.shape)
        weight_chunks.append(tensor.numpy().tobytes(order="C"))

    weight_data = b"".join(weight_chunks)

    manifest = {
        "architecture": architecture,
        "hyperparameters": hyperparameters,
        "seed": seed,
        "version": version,
        "W": W,
        "weight_shapes": weight_shapes,
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")

    # Assemble header (everything before weight_data + checksum).
    fp_bytes = fingerprint.encode("ascii")
    header = (
        MAGIC
        + struct.pack(">B", FORMAT_VERSION)
        + struct.pack(">H", len(fp_bytes))
        + fp_bytes
        + struct.pack(">I", len(manifest_bytes))
        + manifest_bytes
    )

    total_size = len(header) + len(weight_data) + 32  # 32 = SHA-256
    if total_size > MAX_WEIGHTS_SIZE:
        raise PayloadTooLargeError(f"Encoded weights {total_size} bytes exceeds {MAX_WEIGHTS_SIZE}")

    checksum = hashlib.sha256(header + weight_data).digest()
    return header + weight_data + checksum


# ── decode / validate ───────────────────────────────────────────────────


def _parse_blob(
    blob: bytes,
    *,
    expected_fingerprint: str | None = None,
) -> dict[str, object]:
    """Internal: parse and validate a weights blob. Returns manifest dict."""
    if len(blob) < 8 + 1 + 2 + 4 + 4 + 32:
        raise TruncatedPayloadError("Blob too short for header")

    if blob[:8] != MAGIC:
        raise InvalidMagicError(f"Expected {MAGIC!r}, got {blob[:8]!r}")

    offset = 8
    fmt_ver = struct.unpack_from(">B", blob, offset)[0]
    offset += 1
    if fmt_ver != FORMAT_VERSION:
        raise InvalidFormatVersionError(f"Version {fmt_ver} != {FORMAT_VERSION}")

    fp_len = struct.unpack_from(">H", blob, offset)[0]
    offset += 2
    fingerprint = blob[offset : offset + fp_len].decode("ascii")
    offset += fp_len

    manifest_len = struct.unpack_from(">I", blob, offset)[0]
    offset += 4
    manifest_bytes = blob[offset : offset + manifest_len]
    offset += manifest_len

    # Remaining = weight_data + 32-byte checksum.
    if len(blob) < offset + 32:
        raise TruncatedPayloadError("Blob too short for weights + checksum")

    weight_data = blob[offset : len(blob) - 32]
    stored_checksum = blob[len(blob) - 32 :]

    computed_checksum = hashlib.sha256(blob[: len(blob) - 32]).digest()
    if computed_checksum != stored_checksum:
        raise ChecksumMismatchError("SHA-256 checksum does not match")

    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        raise FingerprintMismatchError(
            f"Blob fingerprint {fingerprint} != expected {expected_fingerprint}"
        )

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidManifestError(f"Invalid manifest JSON: {exc}") from exc

    required = {"architecture", "hyperparameters", "seed", "version", "W", "weight_shapes"}
    if not required.issubset(manifest.keys()):
        raise InvalidManifestError(f"Missing manifest keys: {required - manifest.keys()}")

    return {
        "fingerprint": fingerprint,
        "manifest": manifest,
        "weight_data": weight_data,
    }


def decode_weights(
    blob: bytes,
    *,
    expected_fingerprint: str | None = None,
) -> dict[str, torch.Tensor]:
    """Deserialize a weights blob back into a state_dict.

    Parameters
    ----------
    blob:
        Binary blob produced by :func:`encode_weights`.
    expected_fingerprint:
        If provided, the blob's fingerprint must match exactly.

    Returns
    -------
    dict[str, torch.Tensor]
        State dict ready for ``model.load_state_dict()``.
    """
    import torch  # noqa: PLC0415  # deferred: torch must not load at cold start (DLE-17)

    parsed = _parse_blob(blob, expected_fingerprint=expected_fingerprint)
    manifest = parsed["manifest"]
    weight_shapes: dict[str, list[int]] = manifest["weight_shapes"]
    weight_data: bytes = parsed["weight_data"]

    offset = 0
    state_dict: dict[str, torch.Tensor] = {}
    for key in sorted(weight_shapes.keys()):
        shape = weight_shapes[key]
        n_elements = 1
        for s in shape:
            n_elements *= s
        n_bytes = n_elements * 4  # float32
        chunk = weight_data[offset : offset + n_bytes]
        if len(chunk) < n_bytes:
            raise TruncatedPayloadError(f"Weight data truncated at key '{key}'")
        arr = np.frombuffer(chunk, dtype=np.float32).reshape(shape)
        state_dict[key] = torch.from_numpy(arr.copy())
        offset += n_bytes

    return state_dict


def validate_weights(blob: bytes) -> bool:
    """Return ``True`` if the blob is structurally valid (magic + checksum).

    Does **not** check fingerprint — use :func:`decode_weights` with
    ``expected_fingerprint`` for full validation.
    """
    try:
        _parse_blob(blob)
        return True
    except WeightsError:
        return False


__all__ = [
    "MAGIC",
    "FORMAT_VERSION",
    "MAX_WEIGHTS_SIZE",
    "WeightsError",
    "InvalidMagicError",
    "InvalidFormatVersionError",
    "FingerprintMismatchError",
    "ChecksumMismatchError",
    "PayloadTooLargeError",
    "TruncatedPayloadError",
    "InvalidManifestError",
    "encode_weights",
    "decode_weights",
    "validate_weights",
]
