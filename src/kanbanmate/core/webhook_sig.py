"""Pure GitHub webhook HMAC verification (ingress-multiproject §4.3).

GitHub signs every webhook delivery with ``X-Hub-Signature-256: sha256=<hex>``, an HMAC-SHA256 of
the RAW request body keyed by the operator's shared secret. The receiver MUST verify this BEFORE
parsing any payload (an unsigned-accepting receiver is a security hole). The verification is pure
(no I/O, no clock) so it lives in ``core`` and is unit-testable without spinning up the HTTP server.

The comparison uses :func:`hmac.compare_digest` (constant-time / timing-safe), so a near-miss
signature cannot be brute-forced byte-by-byte via timing. The function never raises on a bad input
(a missing header / wrong length) — it returns ``False`` so the caller responds ``401`` uniformly.
"""

from __future__ import annotations

import hmac
from hashlib import sha256

#: The signature header GitHub sends (SHA-256 variant; the legacy ``X-Hub-Signature`` SHA-1 header
#: is deliberately NOT accepted — SHA-1 is weak and GitHub always sends the SHA-256 one too).
SIGNATURE_HEADER = "X-Hub-Signature-256"

#: The signature value prefix GitHub uses (``sha256=<hex>``).
_SIG_PREFIX = "sha256="


def compute_signature(secret: bytes, body: bytes) -> str:
    """Compute the expected ``sha256=<hex>`` signature for ``body`` keyed by ``secret`` (pure).

    Args:
        secret: The shared webhook secret bytes (the operator's ``<root>/webhook_secret``).
        body: The RAW request body bytes (verified as-received, BEFORE any JSON decode).

    Returns:
        The expected signature string in GitHub's ``sha256=<hex>`` form.
    """
    digest = hmac.new(secret, body, sha256).hexdigest()
    return f"{_SIG_PREFIX}{digest}"


def verify_signature(secret: bytes, body: bytes, header: str | None) -> bool:
    """Return whether ``header`` is the valid HMAC-SHA256 signature of ``body`` (timing-safe; §4.3).

    Verifies on the RAW bytes BEFORE any JSON parse. Uses :func:`hmac.compare_digest` so the
    comparison is constant-time (no byte-by-byte timing oracle). Any malformed input — a missing
    header, an empty secret, a non-``sha256=`` prefix — returns ``False`` (the caller responds
    ``401`` uniformly), NEVER raises.

    Args:
        secret: The shared webhook secret bytes. An EMPTY secret returns ``False`` (fail-closed —
            the receiver refuses to start without a secret, but this is belt-and-suspenders).
        body: The RAW request body bytes (as received, before decoding).
        header: The ``X-Hub-Signature-256`` header value (``"sha256=<hex>"``), or ``None`` when
            absent.

    Returns:
        ``True`` iff ``header`` exactly matches the expected signature; ``False`` otherwise.
    """
    if not secret or not header:
        return False
    expected = compute_signature(secret, body)
    # compare_digest tolerates differing lengths without leaking via early-exit timing.
    return hmac.compare_digest(expected, header)
