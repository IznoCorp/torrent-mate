"""Pure REST request BUILDERS + the Link ``rel="next"`` pager (ported from the PoC).

These are the *pure* pieces of the PoC's ``github/_rest.py``: request builders that
return ``(method, path, body_or_None)`` tuples (the HTTP call is the injected REST
transport on :class:`~kanbanmate.adapters.github.client.GithubClient`), plus the
``Link``-header pager that lets a listing follow ``rel="next"`` so a sticky comment
(or an open PR) beyond page 1 is still found and no duplicate is created.

Intentionally NOT ported: the PoC's webhook-management builders. They depended on the
n8n delivery path the polling pivot removed, so re-introducing them here would be dead
code. Only the pure REST builders the polling engine actually needs live here.

No I/O: every symbol is a pure function. This module imports only :mod:`re` (for the
``Link`` regex) and stays within ``adapters/github/`` (the layering guard allows the
import here; it is forbidden in ``core/``).
"""

from __future__ import annotations

import re
from typing import Any

# A page-1 listing asks for the max page size so a small issue's comments (or a
# branch's open pulls) fit in one page; any overflow is then followed via the Link
# rel=next header so a sticky/PR beyond page 1 is still found (no duplicate created).
_PER_PAGE = 100

# Matches the ``<url>; rel="next"`` segment of a GitHub ``Link`` pagination header.
_LINK_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


def next_link_path(link_header: str | None, *, base: str = "https://api.github.com") -> str | None:
    """Return the path (relative to ``base``) of the Link ``rel="next"`` URL, or ``None``.

    GitHub paginates with a ``Link`` header like
    ``<https://api.github.com/repos/o/r/issues/1/comments?per_page=100&page=2>; rel="next",
    <...>; rel="last"``. We return the path+query of the ``rel="next"`` URL so the client
    can issue the next GET with the SAME transport (preserving the connect+read timeouts);
    ``None`` when there is no next page.

    Args:
        link_header: The raw ``Link`` response header, or ``None`` when absent.
        base: The API base URL to strip so the result is a path+query the transport can
            re-issue. Defaults to ``https://api.github.com``.

    Returns:
        The path+query of the ``rel="next"`` URL (base stripped when it matches), the
        full URL when it does not start with ``base``, or ``None`` when there is no
        next page.
    """
    if not link_header:
        return None
    m = _LINK_NEXT.search(link_header)
    if not m:
        return None
    url = m.group(1)
    if url.startswith(base):
        return url[len(base) :]
    return url


def list_issue_comments(repo: str, number: int) -> tuple[str, str, None]:
    """Build the request to list an issue's comments, page 1 (``per_page=100``).

    The result is paginated via the Link ``rel="next"`` header: a sticky comment beyond
    page 1 must still be found so the §8.1 upsert edits in place instead of creating a
    duplicate each tick.

    Args:
        repo: The ``owner/name`` repository slug.
        number: The issue number whose comments to list.

    Returns:
        A ``(method, path, body)`` tuple — ``("GET", ".../comments?per_page=100", None)``.
    """
    return "GET", f"/repos/{repo}/issues/{number}/comments?per_page={_PER_PAGE}", None


def list_open_pulls_for_branch(repo: str, branch: str) -> tuple[str, str, None]:
    """Build the request to list OPEN pulls whose head ref is ``branch`` (page 1).

    Qualifies the head with the repo OWNER (``<owner>:<branch>``) so a same-named branch
    in a fork does not match (fork-safety). Asks for ``per_page=100`` and is paginated via
    the Link ``rel="next"`` header (consumed by ``find_open_pr`` in 16.3).

    Args:
        repo: The ``owner/name`` repository slug.
        branch: The remote head branch name (e.g. ``feat/genesis``).

    Returns:
        A ``(method, path, body)`` tuple — the owner-qualified, ``per_page=100`` pulls
        listing path with a ``None`` body.
    """
    owner = repo.split("/", 1)[0]
    return (
        "GET",
        f"/repos/{repo}/pulls?state=open&head={owner}:{branch}&per_page={_PER_PAGE}",
        None,
    )


def parse_open_pull_number(items: list[dict[str, Any]] | None) -> int | None:
    """Return the number of the first open pull in a REST pulls listing, else ``None``.

    Args:
        items: A decoded REST pulls-listing page (a list of PR objects), or ``None``.

    Returns:
        The first ``number`` found (as ``int``), or ``None`` when the page is empty.
    """
    for pr in items or []:
        if (pr or {}).get("number") is not None:
            return int(pr["number"])
    return None
