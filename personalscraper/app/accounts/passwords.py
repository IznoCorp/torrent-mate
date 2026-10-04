"""Password hashing and verification using stdlib hashlib.scrypt (tm-shell feature).

Pure functions with no FastAPI or request dependency — testable standalone.
See docs/features/tm-shell/DESIGN.md §4.4 for the auth design.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import unicodedata
from typing import Final

from personalscraper.app.errors import AppBadRequest, RefusalCode

#: The shortest password a local door accepts, in characters (the maquette's
#: ``passwordMinimum``); answered as ``password.too_short``'s and ``password.too_weak``'s ``minimum``.
PASSWORD_MINIMUM: Final[int] = 12

# scrypt parameters — DESIGN §4.4 / §4.8 (stdlib only, no extra dep).
# maxmem=64 MiB bypasses the default maxmem=0 which rejects n=16384,r=8 on macOS.
_N = 16384
_R = 8
_P = 1
_DKLEN = 64
_SALT_LENGTH = 16
_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    """Hash a password using ``hashlib.scrypt``.

    The output format is ``scrypt$N$r$p$salt_b64$hash_b64`` so that
    ``verify_password`` can recover the exact parameters that were used.

    Args:
        password: The plaintext password to hash.

    Returns:
        A string in the format ``scrypt$N$r$p$salt_b64$hash_b64``.
    """
    salt = secrets.token_bytes(_SALT_LENGTH)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
        maxmem=_MAXMEM,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(key).decode("ascii")
    return f"scrypt${_N}${_R}${_P}${salt_b64}${hash_b64}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored scrypt hash.

    Parses the stored ``scrypt$N$r$p$salt_b64$hash_b64`` format to recover
    the scrypt parameters, recomputes the hash with those parameters, and
    compares in constant time via ``hmac.compare_digest``.

    Args:
        password: The plaintext password to verify.
        stored: The stored hash string.

    Returns:
        ``True`` if the password matches, ``False`` otherwise.
        Malformed or unparseable *stored* values are treated as mismatches
        and never raise.
    """
    try:
        parts = stored.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        _, n_str, r_str, p_str, salt_b64, hash_b64 = parts
        n = int(n_str)
        r = int(r_str)
        p = int(p_str)
        salt = base64.b64decode(salt_b64)
        expected_hash = base64.b64decode(hash_b64)
    except (ValueError, binascii.Error):
        return False

    try:
        key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected_hash),
            maxmem=_MAXMEM,
        )
    except (ValueError, MemoryError):
        return False

    return hmac.compare_digest(key, expected_hash)


def policy_refusal(password: str) -> AppBadRequest | None:
    """Why a password breaks the policy every local door applies, if it does.

    The policy (the operator, 2026-10-04): at least :data:`PASSWORD_MINIMUM` characters,
    one uppercase letter, one digit and one special character. The classes are Unicode
    categories — uppercase ``Lu``, digit ``Nd``, special anything that is neither a
    letter nor a number — so the maquette's check (``lib/password-policy.ts``) answers
    exactly the same. The doors are the CLI's ``create-owner`` and ``set-password``,
    ``changeOwnPassword``, ``resetAccountPassword`` and ``createAccount``. Neither the
    refusal's text nor its params carry the password.

    Args:
        password: The password typed.

    Returns:
        ``password.too_short`` under the minimum; ``password.too_weak`` when a class is
        missing — both name the ``minimum``, so the words can say the whole rule; ``None``
        when the password meets the policy.
    """
    params = {"minimum": PASSWORD_MINIMUM}
    if len(password) < PASSWORD_MINIMUM:
        return AppBadRequest("The password is too short.", code=RefusalCode.PASSWORD_TOO_SHORT, params=params)
    categories = {unicodedata.category(char) for char in password}
    has_upper = "Lu" in categories
    has_digit = "Nd" in categories
    has_special = any(category[0] not in "LN" for category in categories)
    if not (has_upper and has_digit and has_special):
        return AppBadRequest(
            "The password lacks an uppercase letter, a digit or a special character.",
            code=RefusalCode.PASSWORD_TOO_WEAK,
            params=params,
        )
    return None
