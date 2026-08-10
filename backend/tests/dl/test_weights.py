"""Unit tests for dl.weights — encode/decode/validate (DLE-09)."""

from __future__ import annotations

import struct

import pytest
import torch

from backend.app.dl.weights import (
    MAGIC,
    ChecksumMismatchError,
    FingerprintMismatchError,
    InvalidFormatVersionError,
    InvalidMagicError,
    TruncatedPayloadError,
    decode_weights,
    encode_weights,
    validate_weights,
)

_FP = "a" * 64  # dummy fingerprint


def _simple_state_dict() -> dict[str, torch.Tensor]:
    return {"weight": torch.randn(4, 3), "bias": torch.randn(3)}


def test_encode_returns_bytes() -> None:
    blob = encode_weights(
        _simple_state_dict(),
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={"hidden_layers": [64, 32]},
        seed=0,
        version="1.0.0",
        W=10,
    )
    assert isinstance(blob, bytes)
    assert blob[:8] == MAGIC


def test_encode_decode_roundtrip() -> None:
    sd = _simple_state_dict()
    blob = encode_weights(
        sd,
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={"hidden_layers": [64, 32]},
        seed=0,
        version="1.0.0",
        W=10,
    )
    decoded = decode_weights(blob, expected_fingerprint=_FP)
    for key in sd:
        assert torch.equal(sd[key], decoded[key])


def test_validate_valid() -> None:
    blob = encode_weights(
        _simple_state_dict(),
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={},
        seed=0,
        version="1.0.0",
        W=10,
    )
    assert validate_weights(blob)


def test_invalid_magic() -> None:
    with pytest.raises(InvalidMagicError):
        decode_weights(b"BADMAGIC" + b"\x00" * 50)


def test_invalid_format_version() -> None:
    header = MAGIC + struct.pack(">B", 99) + struct.pack(">H", 64)
    header += b"a" * 64 + struct.pack(">I", 10) + b'{"a":1}'
    header += b"\x00" * 100
    header += b"\x00" * 32
    with pytest.raises(InvalidFormatVersionError):
        decode_weights(header)


def test_fingerprint_mismatch() -> None:
    blob = encode_weights(
        _simple_state_dict(),
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={},
        seed=0,
        version="1.0.0",
        W=10,
    )
    with pytest.raises(FingerprintMismatchError):
        decode_weights(blob, expected_fingerprint="b" * 64)


def test_checksum_tamper() -> None:
    blob = encode_weights(
        _simple_state_dict(),
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={},
        seed=0,
        version="1.0.0",
        W=10,
    )
    # Tamper with a weight byte (well past header area).
    tampered = bytearray(blob)
    tampered[-65] ^= 0xFF  # in weight data, before checksum
    with pytest.raises(ChecksumMismatchError):
        decode_weights(bytes(tampered))


def test_truncated_payload() -> None:
    with pytest.raises(TruncatedPayloadError):
        decode_weights(b"\x00" * 10)


def test_no_pickle_in_blob() -> None:
    blob = encode_weights(
        _simple_state_dict(),
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={},
        seed=0,
        version="1.0.0",
        W=10,
    )
    assert b"pickle" not in blob
    assert b"joblib" not in blob
    assert b"torch.save" not in blob


def test_empty_state_dict() -> None:
    blob = encode_weights(
        {},
        fingerprint=_FP,
        architecture="mlp",
        hyperparameters={},
        seed=0,
        version="1.0.0",
        W=10,
    )
    decoded = decode_weights(blob)
    assert decoded == {}
