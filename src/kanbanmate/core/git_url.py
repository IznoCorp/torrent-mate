"""Pure git-clone-URL allowlist validator (bosun §5.2).

Accepts only ``https://<host>/<owner>/<repo>(.git)`` where ``host`` is in the allowlist. Rejects
file://, ssh://, git://, scp-style ``git@host:path``, and any other scheme/host — defense-in-depth
because the UI is internet-fronted via Caddy. No I/O (no network, no clock) → lives in ``core``.
"""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_GIT_HOSTS: frozenset[str] = frozenset({"github.com"})


def validate_git_url(url: str, *, allowed_hosts: frozenset[str] = ALLOWED_GIT_HOSTS) -> str | None:
    """Return ``None`` if ``url`` is a permitted clone source, else a refusal reason (DESIGN §5.2).

    Args:
        url: The candidate git clone URL.
        allowed_hosts: The host allowlist (default ``github.com`` only).

    Returns:
        ``None`` when permitted; otherwise a human-readable refusal string (HTTP → 422).
    """
    if not url or "://" not in url:
        # scp-style git@host:path has no scheme separator → reject here.
        return "git URL must be https://<host>/<owner>/<repo>"
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return f"scheme '{parsed.scheme}' not allowed (https only)"
    # Reject embedded credentials (``https://user:pass@host/...``). git would persist them into the
    # clone's ``.git/config`` and leak them in the host process list during the clone — defeating the
    # token-file design that deliberately keeps the PAT out of ``.git/config`` (DESIGN §5.2).
    if parsed.username or parsed.password:
        return "git URL must not embed credentials (user:pass@)"
    if parsed.hostname not in allowed_hosts:
        return f"host '{parsed.hostname}' not in allowlist"
    # Require a /<owner>/<repo> path (at least two non-empty segments).
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return "git URL must include <owner>/<repo>"
    # Reject path-traversal segments: a "." / ".." owner or repo lets the derived clone target escape
    # ONBOARD_BASE_DIRS (e.g. ".../owner/.." → repo name ".." → clone dir resolves above the base).
    if any(seg in {".", ".."} for seg in segments):
        return "git URL must not contain '.' or '..' path segments"
    # The repo name (last segment, ``.git`` stripped) must be non-empty so the derived clone dir is a
    # real child of the base (a bare ".git" segment would strip to "" → target == the base dir).
    repo_name = segments[-1][: -len(".git")] if segments[-1].endswith(".git") else segments[-1]
    if not repo_name:
        return "git URL must end with a non-empty <repo> name"
    return None
