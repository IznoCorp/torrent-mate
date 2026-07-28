"""Plex media-server client — targeted library refresh after a dispatch (D2).

Why this exists: the storage disks are macFUSE/NTFS mounts, which deliver NO
filesystem events to Plex. A film could therefore land on disk, fully scraped
and indexed, and stay invisible in Plex until somebody triggered a scan by hand
(the Margin Call incident, 2026-07-28). This client is that trigger.

It is deliberately NOT a general Plex API wrapper. Two calls, one purpose:

- ``sections()`` — ``GET /library/sections``, lazily fetched once per process
  and cached. Sections are stable configuration; re-reading them per dispatched
  item would be a request per file for data that does not move.
- ``refresh(path)`` — ``GET /library/sections/{id}/refresh?path=<folder>``,
  a PARTIAL scan of one folder. The section is resolved by the LONGEST matching
  ``Location`` prefix of the folder, never by a hardcoded id: section ids differ
  per server and the operator's four disks each carry several libraries, so a
  hardcoded map would silently scan the wrong library after any reorganisation.

Fail-soft is the whole contract (NE-DOIT-PAS-5 applies to the CALLER, which
logs): every method returns a value instead of raising, because a dispatch that
really happened must never be reported as a failure by its notifier.

**The token never appears anywhere.** It travels in the ``X-Plex-Token``
header, never in a URL, and this module never logs, formats or re-raises a
value that contains it — including exception text, which is why the HTTP layer
here is raw ``requests`` rather than the shared transport (whose logging is not
in this module's control).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("api.plex")

#: Connect / read timeouts. A refresh trigger is best-effort: a Plex that does
#: not answer in a couple of seconds must not hold the dispatch step.
_TIMEOUT: tuple[float, float] = (2.0, 5.0)

#: One attempt. This is a trigger, not a business API — the next dispatch (or
#: the operator) retries naturally, and a retry loop against a dead server would
#: multiply the delay the pipeline pays for nothing.
_ATTEMPTS = 1


class PlexSection:
    """One Plex library section and the filesystem roots it indexes.

    Attributes:
        key: Section id as Plex reports it (a string, e.g. ``"3"``).
        title: Human title (``"Films"``) — logged, never used for matching.
        locations: Absolute folder roots the section indexes.
    """

    __slots__ = ("key", "locations", "title")

    def __init__(self, key: str, title: str, locations: list[str]) -> None:
        """Store the section identity and its roots.

        Args:
            key: Section id as reported by Plex.
            title: Human-readable section title.
            locations: Absolute paths the section indexes.
        """
        self.key = key
        self.title = title
        self.locations = locations

    def __repr__(self) -> str:
        """Return a debug repr (no credential is involved in a section)."""
        return f"PlexSection(key={self.key!r}, title={self.title!r}, locations={self.locations!r})"


class PlexClient:
    """Minimal Plex client: list sections, refresh one folder.

    Attributes:
        base_url: Plex server root, e.g. ``http://localhost:32400``.
    """

    provider_name = "plex"

    def __init__(self, base_url: str, token: str, *, session: requests.Session | None = None) -> None:
        """Store the server address and the token.

        Args:
            base_url: Plex server root (trailing slashes are trimmed).
            token: Plex auth token. Held in a private attribute, sent as the
                ``X-Plex-Token`` header, and never logged or embedded in a URL.
            session: Optional pre-built :class:`requests.Session` (tests inject
                a fake; production lets the client own one).
        """
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._session = session if session is not None else requests.Session()
        #: Lazily fetched once, then reused for the process lifetime.
        self._sections: list[PlexSection] | None = None

    def __repr__(self) -> str:
        """Return a repr that CANNOT leak the token (it is simply not included)."""
        return f"PlexClient(base_url={self.base_url!r})"

    # -- HTTP ---------------------------------------------------------------

    def _get(self, path: str, params: dict[str, str] | None = None) -> requests.Response:
        """Issue one GET with the token in the header.

        Args:
            path: Server-absolute path (``/library/sections``).
            params: Query parameters — NEVER the token.

        Returns:
            The raw :class:`requests.Response` (status not checked here).

        Raises:
            requests.RequestException: Propagated to the caller, which is
                responsible for the fail-soft behaviour. The exception text
                carries the URL, which is token-free by construction.
        """
        return self._session.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"X-Plex-Token": self._token, "Accept": "application/json"},
            timeout=_TIMEOUT,
        )

    # -- Sections -----------------------------------------------------------

    def sections(self) -> list[PlexSection]:
        """Return the server's library sections, fetching them at most once.

        Returns:
            The sections, or an empty list when Plex is unreachable, refuses the
            token, or answers something unparseable. An empty list is cached as
            « not available » only for THIS call — the next call retries, so a
            server that comes back up is picked up without a restart.
        """
        if self._sections is not None:
            return self._sections
        try:
            resp = self._get("/library/sections")
        except requests.RequestException as exc:
            log.warning("plex.sections_unreachable", base_url=self.base_url, error=type(exc).__name__)
            return []
        if resp.status_code != 200:
            # 401 lands here: the token is wrong. The status is logged, the
            # token is not — the operator has enough to act.
            log.warning("plex.sections_http_error", base_url=self.base_url, status=resp.status_code)
            return []
        try:
            payload: Any = resp.json()
        except ValueError:
            log.warning("plex.sections_unparseable", base_url=self.base_url)
            return []
        sections = _parse_sections(payload)
        self._sections = sections
        log.info("plex.sections_loaded", count=len(sections))
        return sections

    def section_for(self, target: Path) -> PlexSection | None:
        """Return the section indexing *target*, by longest ``Location`` prefix.

        Longest-prefix rather than first-match because a disk can host several
        libraries under nested roots (``…/medias`` and ``…/medias/series``): the
        deepest root that contains the folder is the one that indexes it, and a
        first-match would refresh the parent library instead.

        Args:
            target: The dispatched folder.

        Returns:
            The best-matching section, or ``None`` when no section indexes that
            path (a library Plex does not know about — the caller logs it).
        """
        target_str = str(target)
        best: PlexSection | None = None
        best_len = -1
        for section in self.sections():
            for location in section.locations:
                root = location.rstrip("/")
                if not root:
                    continue
                # Prefix match on a PATH BOUNDARY: "/a/medias" must not match
                # "/a/medias-old" (a real sibling naming pattern on these disks).
                if (target_str == root or target_str.startswith(f"{root}/")) and len(root) > best_len:
                    best, best_len = section, len(root)
        return best

    # -- Refresh ------------------------------------------------------------

    def refresh(self, target: Path) -> bool:
        """Trigger a PARTIAL scan of *target* in the section that indexes it.

        Args:
            target: The dispatched folder to scan.

        Returns:
            ``True`` when Plex accepted the refresh, ``False`` on any failure —
            unreachable server, wrong token, unknown path, non-2xx status. The
            caller treats ``False`` as « nothing happened », never as an error
            worth failing the dispatch over.
        """
        section = self.section_for(target)
        if section is None:
            log.warning("plex.no_section_for_path", path=str(target))
            return False
        try:
            resp = self._get(f"/library/sections/{section.key}/refresh", params={"path": str(target)})
        except requests.RequestException as exc:
            log.warning(
                "plex.refresh_unreachable",
                path=str(target),
                section=section.key,
                error=type(exc).__name__,
            )
            return False
        if resp.status_code >= 400:
            log.warning(
                "plex.refresh_http_error",
                path=str(target),
                section=section.key,
                status=resp.status_code,
            )
            return False
        log.info("plex.refresh_triggered", path=str(target), section=section.key, title=section.title)
        return True


def _parse_sections(payload: Any) -> list[PlexSection]:
    """Map a ``/library/sections`` JSON payload to :class:`PlexSection` objects.

    Tolerant by design: Plex nests the list under ``MediaContainer.Directory``
    and each entry's roots under ``Location[].path``. Anything missing or of the
    wrong shape yields fewer sections rather than an exception — a malformed
    payload must degrade the trigger, not break a dispatch.

    Args:
        payload: The decoded JSON body.

    Returns:
        The parsed sections (possibly empty).
    """
    container = payload.get("MediaContainer") if isinstance(payload, dict) else None
    directories = container.get("Directory") if isinstance(container, dict) else None
    if not isinstance(directories, list):
        return []
    sections: list[PlexSection] = []
    for entry in directories:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            continue
        locations = [
            loc.get("path")
            for loc in entry.get("Location", [])
            if isinstance(loc, dict) and isinstance(loc.get("path"), str)
        ]
        title = entry.get("title")
        sections.append(
            PlexSection(
                key=key,
                title=title if isinstance(title, str) else "",
                locations=[loc for loc in locations if isinstance(loc, str) and loc],
            )
        )
    return sections


__all__ = ["PlexClient", "PlexSection"]
