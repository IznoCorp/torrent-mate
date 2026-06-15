"""Load and validate the GitHub PAT (``~/.kanban/token`` 600, or ``$KANBAN_TOKEN``).

The daemon authenticates with a user PAT scoped **exactly** to ``project`` + ``repo``
(DESIGN §10). Webhooks are gone, so ``admin:org_hook`` — or any broader admin scope —
must be **refused**: an over-broad token is a security regression for an autonomous
agent, so we fail loud rather than silently accept it.

The env var wins over the file so CI/tests need not write a token to disk.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".kanban" / "token"

# Exactly the scopes the daemon needs. Nothing else is accepted (DESIGN §10): a
# token carrying e.g. ``admin:org_hook`` or ``admin:org`` is over-broad for a v1
# polling daemon and must be rejected.
_ALLOWED_SCOPES = frozenset({"project", "repo"})

# The required-scope FLOOR (lower bound) a classic PAT must carry to drive the
# daemon (PoC ``cli/plan_doctor.py:14`` ``_REQUIRED_SCOPES``). ``classify_scopes``
# treats a classic token lacking either as missing-required (a doctor FAIL).
_REQUIRED_SCOPES = frozenset({"project", "repo"})


class TokenScopeError(RuntimeError):
    """Raised when a token's granted scopes are not exactly ``{project, repo}``.

    Carries the disallowed scopes so the operator sees precisely which over-broad
    grant must be removed from the PAT.
    """

    def __init__(self, disallowed: frozenset[str]):
        """Build the error from the set of scopes outside the allow-list.

        Args:
            disallowed: The granted scopes that are not in ``{project, repo}``.
        """
        self.disallowed = disallowed
        joined = ", ".join(sorted(disallowed))
        super().__init__(
            f"GitHub token has disallowed scope(s): {joined}. "
            "v1 requires exactly 'project' + 'repo' (no 'admin:org_hook' or broader); "
            "regenerate the PAT with only those scopes."
        )


class TokenAuthError(RuntimeError):
    """Raised when GitHub rejects the token with a ``401``/``403`` (#1).

    A dead or over-broad token is a hard, actionable failure — NOT a transient network note and
    NOT the fine-grained-PAT empty-scope advisory. Carrying the status lets the doctor render the
    precise remediation ("token invalid — regenerate the PAT").
    """

    def __init__(self, status: int):
        """Build the error from the rejecting HTTP status.

        Args:
            status: The HTTP status GitHub returned (401 or 403).
        """
        self.status = status
        super().__init__(
            f"GitHub rejected the token (HTTP {status}): it is invalid, expired, or lacks access. "
            "Regenerate the PAT (scopes: project + repo) and update ~/.kanban/token."
        )


def load_token(*, path: str | Path | None = None, env: dict[str, str] | None = None) -> str:
    """Return the GitHub token. ``$KANBAN_TOKEN`` overrides the file.

    Args:
        path: Token file path (default ``~/.kanban/token``).
        env: Environment mapping to read ``KANBAN_TOKEN`` from (default
            :data:`os.environ`).

    Returns:
        The token string, stripped of surrounding whitespace.

    Raises:
        FileNotFoundError: When no env var is set and no readable token file exists.
    """
    environ = os.environ if env is None else env
    from_env = environ.get("KANBAN_TOKEN")
    if from_env:
        return from_env.strip()
    token_path = Path(path) if path is not None else _DEFAULT_PATH
    if token_path.exists():
        return token_path.read_text().strip()
    raise FileNotFoundError(f"no GitHub token: set $KANBAN_TOKEN or create {token_path}")


def parse_scopes(scope_header: str | None) -> frozenset[str]:
    """Parse a GitHub ``X-OAuth-Scopes`` header value into a set of scope names.

    GitHub returns granted scopes as a comma-separated header (e.g.
    ``"project, repo"``). A missing/empty header yields the empty set.

    Args:
        scope_header: The raw ``X-OAuth-Scopes`` response header, or ``None``.

    Returns:
        The set of granted scope names, whitespace-trimmed.
    """
    if not scope_header:
        return frozenset()
    return frozenset(s.strip() for s in scope_header.split(",") if s.strip())


def validate_scopes(scopes: frozenset[str]) -> None:
    """Validate that ``scopes`` is a subset of the allowed ``{project, repo}`` set.

    Fine-grained PATs may legitimately grant *fewer* scopes than the classic
    ``project`` + ``repo`` pair (GitHub may report an empty scope header for them),
    so we only reject scopes *outside* the allow-list rather than demand an exact
    match. The hard rule (DESIGN §10) is: no ``admin:org_hook`` or broader.

    Args:
        scopes: The granted scopes (e.g. from :func:`parse_scopes`).

    Raises:
        TokenScopeError: If any granted scope is outside ``{project, repo}``.
    """
    disallowed = scopes - _ALLOWED_SCOPES
    if disallowed:
        raise TokenScopeError(frozenset(disallowed))


def classify_scopes(scopes: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Classify granted ``scopes`` against the required FLOOR, without raising (pure).

    This is the doctor-facing companion to :func:`validate_scopes`. Where
    ``validate_scopes`` is a hard load-time gate (raises on anything outside
    ``{project, repo}``), this classifier reports the two independent conditions the
    PoC's ``plan_doctor`` distinguished (``cli/plan_doctor.py:40-45,86-97``) so the
    caller can map them to *three* outcomes — a FAIL on missing-required, a WARNING
    on over-scoped, and an advisory on an empty (fine-grained) scope set — rather
    than collapsing everything to a single hard failure.

    The two halves are orthogonal lower/upper bounds (PoC parity):

    * **missing-required** — the required floor ``{project, repo}`` that is NOT
      present (the lower bound; PoC ``token_required_scopes``). A classic PAT
      lacking ``repo`` is under-scoped → the caller FAILs.
    * **extra** — the granted scopes BEYOND the floor (the over-scoped set; PoC
      ``token_not_overscoped``). Anything here is advisory/over-broad → the caller
      WARNs but does NOT block.

    An EMPTY scope set yields ``(frozenset(), frozenset())`` — neither
    missing-required nor extra. This is the deliberate fine-grained-PAT escape
    hatch: GitHub reports no classic scopes for a fine-grained PAT, so the caller
    surfaces it as an advisory note (not a silent pass, not a FAIL). Distinguishing
    the empty case is the caller's job (it has the original ``scopes`` set).

    Args:
        scopes: The granted scopes (e.g. from :func:`parse_scopes`).

    Returns:
        A ``(missing_required, extra)`` pair: the required scopes ABSENT from
        ``scopes`` (lower-bound shortfall) and the granted scopes BEYOND the floor
        (upper-bound excess).
    """
    # The fine-grained-PAT escape hatch: an empty classic-scope set is neither
    # under- nor over-scoped — the caller reads it as the advisory branch.
    if not scopes:
        return (frozenset(), frozenset())
    missing_required = _REQUIRED_SCOPES - scopes
    extra = scopes - _ALLOWED_SCOPES
    return (frozenset(missing_required), frozenset(extra))


def fetch_token_scopes(
    token: str,
    *,
    connect_timeout: float = 5.0,
    read_timeout: float = 30.0,
) -> frozenset[str]:
    """Query GitHub for ``token``'s granted OAuth scopes (the ``X-OAuth-Scopes`` header).

    Makes ONE authenticated ``GET https://api.github.com/`` and reads the granted scopes off the
    ``X-OAuth-Scopes`` response header. Classic PATs report their scopes there; fine-grained PATs
    report none (→ the empty set). Mandatory connect + read timeouts (CLAUDE.md network-safety) so
    ``kanban doctor`` can never hang on a slow/half-open response. Tests monkeypatch
    ``http.client.HTTPSConnection`` to avoid the network.

    Args:
        token: The GitHub PAT to introspect.
        connect_timeout: Socket connect timeout in seconds.
        read_timeout: Response read timeout in seconds (set on the socket once connected).

    Returns:
        The granted scope names (see :func:`parse_scopes`).

    Raises:
        OSError: On a network/connection failure — the caller (doctor) degrades to a note.
        TokenAuthError: On a ``401``/``403`` response — a dead or over-broad token is NOT a
            transient note. Before #1 this path read the scope header off a 401 response and
            returned ``frozenset()``, which doctor then treated as a fine-grained-PAT advisory
            PASS — so an expired token looked healthy. Raising here makes doctor FAIL the token
            check (the proven silent-401 incident class), DESIGN §10.
    """
    import http.client

    conn = http.client.HTTPSConnection("api.github.com", timeout=connect_timeout)
    try:
        conn.request(
            "GET",
            "/",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "kanbanmate",
                "Accept": "application/vnd.github+json",
            },
        )
        if conn.sock is not None:
            conn.sock.settimeout(read_timeout)
        resp = conn.getresponse()
        resp.read()  # drain so the connection closes cleanly
        # A 401/403 means the token is dead or over-broad — NOT a fine-grained PAT with an empty
        # scope header. Raise so doctor FAILs the token check instead of mistaking the empty
        # scopes for the advisory fine-grained branch (#1).
        if resp.status in (401, 403):
            raise TokenAuthError(resp.status)
        return parse_scopes(resp.getheader("X-OAuth-Scopes"))
    finally:
        conn.close()
