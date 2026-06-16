"""Tests for the pure GitHub webhook HMAC verification (ingress-multiproject §4.3 / §9).

Covers a valid signature pass, a tampered body fail, a missing header fail, a wrong-secret fail,
and the constant-time comparison path (no raise on malformed input).
"""

from __future__ import annotations

import hmac
from hashlib import sha256

from kanbanmate.core.webhook_sig import (
    SIGNATURE_HEADER,
    compute_signature,
    verify_signature,
)


_SECRET = b"s3cr3t-shared-webhook-key"
_BODY = b'{"action":"edited","projects_v2_item":{"project_node_id":"PVT_A"}}'


def _sign(secret: bytes, body: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, sha256).hexdigest()


def test_signature_header_constant() -> None:
    assert SIGNATURE_HEADER == "X-Hub-Signature-256"


def test_valid_signature_passes() -> None:
    sig = _sign(_SECRET, _BODY)
    assert verify_signature(_SECRET, _BODY, sig) is True


def test_compute_signature_matches_manual_hmac() -> None:
    assert compute_signature(_SECRET, _BODY) == _sign(_SECRET, _BODY)


def test_tampered_body_fails() -> None:
    sig = _sign(_SECRET, _BODY)
    assert verify_signature(_SECRET, _BODY + b"x", sig) is False


def test_wrong_secret_fails() -> None:
    sig = _sign(b"other-secret", _BODY)
    assert verify_signature(_SECRET, _BODY, sig) is False


def test_missing_header_fails_without_raising() -> None:
    assert verify_signature(_SECRET, _BODY, None) is False


def test_empty_secret_fails_closed() -> None:
    sig = _sign(b"", _BODY)
    assert verify_signature(b"", _BODY, sig) is False


def test_malformed_header_fails_without_raising() -> None:
    # A non-sha256= prefix / garbage header must return False, never raise (compare_digest tolerant).
    assert verify_signature(_SECRET, _BODY, "garbage") is False
    assert verify_signature(_SECRET, _BODY, "sha1=deadbeef") is False
