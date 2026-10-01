#!/usr/bin/env python3
"""Check the Firebase Cloud Messaging credentials by hand — run by the operator, never by a session.

After he has created the Firebase project and its service account
(``docs/features/backend-bricks/fcm-push/DESIGN.md`` § 5, F-1), this probe proves the
project id, the private key and the FCM API are right WITHOUT a device: it mints an
access token from ``FCM_SERVICE_ACCOUNT_FILE`` and sends a ``validate_only`` message to
a placeholder registration token.

Reading the answer:

- ``rejected`` / ``INVALID_ARGUMENT`` — EXPECTED: FCM read the request, so the project,
  the key and the API are right, and refused only the placeholder token (a credential
  fault answers 401 / 403 before the token is read);
- ``misconfigured`` — the credentials or the project are wrong; the code says which;
- ``unreachable`` / ``retry_later`` / ``quota_exceeded`` — Google did not answer usefully; run it again later.

The delivery check on a real device (``--account``) arrives with the subscription
store's file, after the opt-in surfaces are drawn and bound.

The probe prints outcome codes only — never the access token, never the key.

Usage (his hand only):
    python scripts/fcm-probe.py --validate-only
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from personalscraper.api.notify.fcm import FcmSender, PushMessage, PushOutcome, PushResult

#: Not a registration token: FCM must refuse it as INVALID_ARGUMENT once the credentials pass.
PLACEHOLDER_TOKEN = "fcm-probe-placeholder-token"
PROBE_MESSAGE = PushMessage(code="probe.validate_only", link="/")


def verdict(result: PushResult) -> tuple[int, str]:
    """Turns the validate-only answer into the operator's verdict.

    Args:
        result: The sender's result.

    Returns:
        ``(exit code, line to print)`` — 0 only for the expected INVALID_ARGUMENT.
    """
    if result.outcome is PushOutcome.REJECTED and result.fcm_error == "INVALID_ARGUMENT":
        return 0, "credentials OK: FCM refused only the placeholder token (INVALID_ARGUMENT, expected)"
    if result.outcome is PushOutcome.DELIVERED:
        return 1, "unexpected: FCM accepted the placeholder token — check that validate_only was honoured"
    return 1, f"{result.outcome.value}: {result.fcm_error or 'no code'}"


def run(
    env: Mapping[str, str],
    *,
    build: Callable[[Path], FcmSender] = FcmSender.from_service_account_file,
    say: Callable[[str], None] = print,
) -> int:
    """Runs the validate-only check.

    Args:
        env: Where ``FCM_SERVICE_ACCOUNT_FILE`` is read.
        build: Builds the sender from the file (a fake in tests).
        say: Where the verdict is printed.

    Returns:
        The exit code.
    """
    path = env.get("FCM_SERVICE_ACCOUNT_FILE", "")
    if not path:
        say("misconfigured: FCM_SERVICE_ACCOUNT_FILE is not set")
        return 1
    sender = build(Path(path).expanduser())
    say(f"project: {sender.project_id or '(unreadable service-account file)'}")
    code, line = verdict(sender.send(PLACEHOLDER_TOKEN, PROBE_MESSAGE, validate_only=True))
    say(line)
    return code


def main(argv: list[str] | None = None) -> int:
    """Parses the arguments and runs the probe.

    Args:
        argv: The arguments (``sys.argv[1:]`` when None).

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validate-only", action="store_true", required=True, help="check the credentials only")
    parser.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv()
    return run(os.environ)


if __name__ == "__main__":
    sys.exit(main())
