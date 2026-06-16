"""Advisory ``kanban doctor`` checks for ingress + multi-project (ingress-multiproject §8).

Lifted out of :mod:`kanbanmate.cli.doctor` for LOC-ceiling headroom (doctor.py sits near the
1000-LOC hard ceiling — new checks land here, mirroring the existing :mod:`cli.doctor_health`
split). The checks are ADVISORY — they NEVER fail the doctor run (ingress is config, not a launch
gate): they surface a ``WARNING:`` for a missing/over-permissive webhook secret and a one-line
multi-project registry summary, so an operator sees the ingress posture without the daemon being
declared unhealthy.

* **webhook secret** — when ANY enabled project uses ``ingress=webhook``, ``<root>/webhook_secret``
  must exist (mode 0600). Missing → WARNING (``kanban serve`` would refuse to start); wrong mode →
  WARNING (the secret should not be group/other readable).
* **registry summary** — a one-line count of enabled projects + their ingress modes (observability;
  always PASS).
"""

from __future__ import annotations

import stat
from pathlib import Path

# A doctor check result: ``(name, ok, detail)`` — identical to ``cli.doctor.CheckResult`` (kept as a
# local alias so this module does not import from ``cli.doctor`` and risk a cycle).
IngressCheckResult = tuple[str, bool, str]

# The webhook-secret filename under the runtime root (kept in lock-step with the http receiver +
# cli.init seeder; duplicated here so this advisory check needs no import from those modules).
_WEBHOOK_SECRET_FILENAME = "webhook_secret"


def _load_registry_entries(root: Path) -> list[object]:
    """Return the loaded registry entries (empty on any error — advisory, never raises).

    Reads ``<root>/projects.json`` via the cli registry loader. A missing/corrupt file degrades to
    an empty list so the advisory checks PASS-skip rather than crash the doctor run.

    Args:
        root: The runtime root holding ``projects.json``.

    Returns:
        The registry entries (concrete ``ProjectEntry`` objects), or ``[]`` on any error.
    """
    try:
        from kanbanmate.cli.init import _load_registry, _projects_path
        from kanbanmate.core.registry_resolve import enabled_entries

        path = _projects_path(root)
        registry = _load_registry(path) if path.exists() else {}
        return list(enabled_entries(registry))
    except Exception:  # noqa: BLE001 — advisory: any read error → empty (PASS-skip), never crash
        return []


def check_webhook_secret(root: Path) -> IngressCheckResult:
    """Advisory: verify the webhook secret exists (0600) when a webhook-ingress project is enabled.

    ADVISORY — always ``ok=True``:

    * no enabled webhook-ingress project → PASS-skip (the secret is irrelevant for an all-polling
      daemon).
    * secret present + mode 0600 + a REAL value → PASS.
    * secret missing → ``WARNING:`` (``kanban serve`` would refuse to start).
    * secret present but a PLACEHOLDER / empty / comment-only → ``WARNING:`` (``kanban serve`` would
      refuse to start with a publicly-known HMAC key, #3).
    * secret present but group/other readable → ``WARNING:`` (it must be 0600).

    Args:
        root: The runtime root the secret + registry live under.

    Returns:
        A ``(name, ok, detail)`` tuple; ``ok`` is ALWAYS ``True`` (advisory).
    """
    entries = _load_registry_entries(root)
    # ``ingress`` is a ProjectEntry attribute; read it defensively (advisory).
    uses_webhook = any(getattr(e, "ingress", "webhook") == "webhook" for e in entries)
    if not uses_webhook:
        return ("webhook secret", True, "skipped — no webhook-ingress project (advisory)")
    secret = root / _WEBHOOK_SECRET_FILENAME
    if not secret.exists():
        return (
            "webhook secret",
            True,
            f"WARNING: {secret} is missing — `kanban serve` will refuse to start. "
            "Seed it (0600) and set the SAME value on the GitHub webhook.",
        )
    try:
        mode = stat.S_IMODE(secret.stat().st_mode)
    except OSError as exc:  # advisory: an unstatable secret WARNs, never FAILs.
        return ("webhook secret", True, f"WARNING: could not stat {secret} ({exc})")
    if mode & 0o077:
        return (
            "webhook secret",
            True,
            f"WARNING: {secret} is mode {mode:o} — it should be 0600 (owner-only). "
            "Run: chmod 600 " + str(secret),
        )
    # Advisory placeholder check (#3): a present-but-unusable secret (empty / whitespace / the seeded
    # comment-only placeholder) would make `kanban serve` refuse to start — surface it here too.
    try:
        from kanbanmate.http.serve import _extract_secret

        real = _extract_secret(secret.read_bytes())
    except Exception:  # noqa: BLE001 — advisory: any read error degrades to "present" (never crash)
        real = b"present"
    if not real:
        return (
            "webhook secret",
            True,
            f"WARNING: {secret} is still the placeholder (empty/comment-only) — `kanban serve` will "
            "refuse to start with a publicly-known HMAC key. Paste a strong random secret.",
        )
    return ("webhook secret", True, "present (0600)")


def check_registry_summary(root: Path) -> IngressCheckResult:
    """Advisory: a one-line summary of the enabled projects + their ingress modes (observability).

    ALWAYS PASS — pure observability. With no enabled project it is a PASS-skip (the other checks
    already cover an unregistered daemon).

    Args:
        root: The runtime root holding ``projects.json``.

    Returns:
        A ``(name, ok, detail)`` tuple; ``ok`` is ALWAYS ``True``.
    """
    entries = _load_registry_entries(root)
    if not entries:
        return ("registry", True, "skipped — no enabled project registered (advisory)")
    modes: list[str] = []
    for e in entries:
        repo = getattr(e, "repo", "?")
        ingress = getattr(e, "ingress", "webhook")
        modes.append(f"{repo}={ingress}")
    return ("registry", True, f"{len(entries)} enabled project(s): " + ", ".join(sorted(modes)))
