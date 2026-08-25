"""Plex media-server client — targeted library refresh after a dispatch (D2).

Why this exists: the storage disks are macFUSE/NTFS mounts, which deliver NO
filesystem events to Plex. A film could therefore land on disk, fully scraped
and indexed, and stay invisible in Plex until somebody triggered a scan by hand
(the Margin Call incident, 2026-07-28). This client is that trigger.

It is deliberately NOT a general Plex API wrapper. It serves two purposes, and
nothing else is added here without one.

**The post-dispatch refresh trigger:**

- ``sections()`` — ``GET /library/sections``, fetched lazily and cached for the
  process lifetime. Sections are stable configuration; re-reading them per
  dispatched item would be a request per file for data that does not move. The
  cache is an optimisation, not an invariant: the subscriber runs one thread per
  dispatched item, so a burst can race and fetch more than once (see
  ``sections()`` for why that is left unlocked).
- ``refresh(path)`` — ``GET /library/sections/{id}/refresh?path=<folder>``,
  a PARTIAL scan of one folder. The section is resolved by the LONGEST matching
  ``Location`` prefix of the folder, never by a hardcoded id: section ids differ
  per server and the operator's four disks each carry several libraries, so a
  hardcoded map would silently scan the wrong library after any reorganisation.

**The match coherence guard** (``maintenance.plex_guard``), because Plex matches
on names alone and its fuzzy match can pick the wrong entry — an empty IMDb stub
for a film the pipeline had identified exactly. Names are the settled Kodi
contract and are never bent to hint a match, so the correction happens over the
API instead:

- ``section_items(section)`` — the section listing, read for ``Media/Part.file``
  alone; it is how a dispatched folder finds its Plex item.
- ``item(rating_key)`` — one item WITH its provider ``Guid`` set, which the
  listing does not carry.
- ``matches(rating_key, hint)`` / ``match(rating_key, candidate)`` — resolve a
  provider id to Plex's own guid, then apply it.

Fail-soft is the whole contract (NE-DOIT-PAS-5 applies to the CALLER, which
logs): every method returns a value instead of raising, because a dispatch that
really happened must never be reported as a failure by its notifier.

**The token never appears anywhere.** It travels in the ``X-Plex-Token``
header, never in a URL, and this module never logs, formats or re-raises a
value that contains it — including exception text, which is why the HTTP layer
here is raw ``requests`` rather than the shared transport (whose logging is not
in this module's control). Three rules keep that true, and each one is load-
bearing:

1. failures log ``error=type(exc).__name__``, never the exception and never
   ``exc_info`` — the console renderer expands a traceback WITH FRAME LOCALS,
   and the frames of ``requests`` hold the header dict;
2. every caller of ``_get`` catches ``Exception``, not just
   ``requests.RequestException``, so no token-bearing stack can escape to a
   caller that might log it with a traceback;
3. redirects are not followed — ``requests`` strips only ``Authorization`` when
   a redirect changes host, so a 302 would hand ``X-Plex-Token`` to another
   origin.
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

#: Timeouts for the coherence-guard calls, deliberately LARGER than ``_TIMEOUT``.
#: The reason is the shape of the request, not a change of policy: a section
#: listing is one multi-megabyte body (the operator's movie section answers ~2.8
#: MB for ~1100 items), which a 5-second read budget sized for a fire-and-forget
#: refresh trigger can cut off mid-body. The guard is an operator-run maintenance
#: command, never on the dispatch path, so waiting is free here and a truncated
#: read would be reported as « Plex unreachable » — the worst possible answer,
#: because it is wrong AND actionable-looking.
_GUARD_TIMEOUT: tuple[float, float] = (5.0, 60.0)


class PlexItem:
    """One Plex library item, reduced to what the coherence guard compares.

    Attributes:
        rating_key: Plex's own item id (a string, e.g. ``"210743"``), the
            handle every metadata and match call takes.
        title: Item title as Plex holds it — logged, never used for matching.
        guids: Provider guids Plex has resolved for the item
            (``["imdb://tt8367814", "tmdb://522627", …]``). Empty in two very
            different situations the callers must not conflate: the section
            LISTING does not carry the ``Guid`` array at all (the item must be
            read again through ``item()``), while an item that exists but is
            unmatched comes back with a genuinely empty list — a legitimate
            state, not a read failure.
        files: Absolute paths of the item's media parts. The guard's only
            reliable join back to a dispatched folder — but ONLY movies carry
            them in the section listing; a show listing entry has no
            ``Media`` at all (verified live: 0/733 TV entries carry parts).
        locations: Absolute folder paths of the item (the ``Location`` array
            of the item endpoint). Shows carry their folder HERE and only
            here — the section listing does not include it either, so a show
            is located by reading its item endpoint, never by the listing.
        grandparent_key: For an EPISODE listing entry (``?type=4``), the
            show's rating key (``grandparentRatingKey``). Empty on show-level
            and movie entries. This is the join that lets the guard locate a
            show from its episode file paths in ONE listing request.
    """

    __slots__ = ("files", "grandparent_key", "guids", "locations", "rating_key", "title")

    def __init__(
        self,
        rating_key: str,
        title: str,
        guids: list[str],
        files: list[str],
        locations: list[str],
        grandparent_key: str = "",
    ) -> None:
        """Store the item identity, its provider guids and its media paths.

        Args:
            rating_key: Plex item id.
            title: Item title.
            guids: Provider guids Plex resolved.
            files: Absolute media part paths (movies; empty for shows).
            locations: Absolute folder paths (shows; empty for movies).
            grandparent_key: Show key for episode entries (``""`` otherwise).
        """
        self.rating_key = rating_key
        self.title = title
        self.guids = guids
        self.files = files
        self.locations = locations
        self.grandparent_key = grandparent_key

    def __repr__(self) -> str:
        """Return a debug repr (no credential is involved in an item)."""
        return f"PlexItem(rating_key={self.rating_key!r}, title={self.title!r}, guids={self.guids!r})"


class PlexMatchCandidate:
    """One entry of a ``/matches`` search result — a match Plex offers to apply.

    Attributes:
        guid: Plex's canonical guid for the candidate
            (``plex://movie/5d77704aad5437001f81e604``). This is what a
            ``match`` call applies; the provider guids appear afterwards.
        name: Candidate title, echoed back on the match call.
        year: Candidate year, echoed back on the match call. ``None`` when
            Plex omits it — the match call simply drops the parameter.
    """

    __slots__ = ("guid", "name", "year")

    def __init__(self, guid: str, name: str, year: int | None) -> None:
        """Store one candidate match.

        Args:
            guid: Plex canonical guid.
            name: Candidate title.
            year: Candidate year, or ``None``.
        """
        self.guid = guid
        self.name = name
        self.year = year

    def __repr__(self) -> str:
        """Return a debug repr (no credential is involved in a candidate)."""
        return f"PlexMatchCandidate(guid={self.guid!r}, name={self.name!r}, year={self.year!r})"


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

    def _get(
        self,
        path: str,
        parameters: dict[str, str] | None = None,
        *,
        timeout: tuple[float, float] = _TIMEOUT,
    ) -> requests.Response:
        """Issue one GET with the token in the header.

        Args:
            path: Server-absolute path (``/library/sections``).
            parameters: Query parameters — NEVER the token.
            timeout: Connect/read budget. Defaults to the refresh trigger's
                tight pair; the coherence guard passes ``_GUARD_TIMEOUT``
                because it reads multi-megabyte section listings off the
                dispatch path.

        Returns:
            The raw :class:`requests.Response` (status not checked here).

        Raises:
            Exception: Anything the transport throws is propagated to the
                caller, which is responsible for the fail-soft behaviour. It is
                NOT limited to ``requests.RequestException``: preparing a URL
                whose path carries a surrogate (an undecodable macFUSE/NTFS
                filename) raises ``UnicodeEncodeError``, so every caller here
                catches ``Exception`` and reports only ``type(exc).__name__``.
                A caller must never log the exception's traceback: the frames
                of ``requests`` hold this header dict, and a traceback rendered
                with locals would print the token in clear.

        ``allow_redirects=False`` is deliberate: ``requests`` strips only the
        ``Authorization`` header when a redirect changes host, so a 302 would
        forward ``X-Plex-Token`` to whatever origin the response names.
        """
        return self._session.get(
            f"{self.base_url}{path}",
            params=parameters,
            headers={"X-Plex-Token": self._token, "Accept": "application/json"},
            timeout=timeout,
            allow_redirects=False,
        )

    def _put(self, path: str, parameters: dict[str, str] | None = None) -> requests.Response:
        """Issue one PUT with the token in the header.

        The token-safety contract is identical to :meth:`_get`'s and for the
        same reason: the header dict lives in the ``requests`` frames, so a
        caller must never render this call's traceback.

        Args:
            path: Server-absolute path (``/library/metadata/210743/match``).
            parameters: Query parameters — NEVER the token.

        Returns:
            The raw :class:`requests.Response` (status not checked here).

        Raises:
            Exception: Anything the transport throws, propagated to the caller,
                which is responsible for the fail-soft behaviour and logs only
                ``type(exc).__name__``.
        """
        return self._session.put(
            f"{self.base_url}{path}",
            params=parameters,
            headers={"X-Plex-Token": self._token, "Accept": "application/json"},
            timeout=_GUARD_TIMEOUT,
            allow_redirects=False,
        )

    # -- Sections -----------------------------------------------------------

    def sections(self) -> list[PlexSection]:
        """Return the server's library sections, fetched once on the happy path.

        Caching is best-effort, NOT a guarantee of a single request: the
        subscriber runs one thread per dispatched item, so several threads can
        find the cache empty at once and each issue its own
        ``/library/sections``. That is bounded (they all store the same answer)
        and deliberately left unlocked — a lock here would serialise the worker
        threads for a best-effort trigger. For the same reason the shared
        :class:`requests.Session` is used concurrently, which ``requests`` does
        not guarantee to be thread-safe; the cost of a lost race is one missed
        refresh, which the next dispatch repairs.

        Returns:
            The sections, or an empty list when Plex is unreachable, refuses the
            token, or answers something unparseable. An empty list is cached as
            « not available » only for THIS call — the next call retries, so a
            server that comes back up is picked up without a restart.
        """
        if self._sections is not None:
            return self._sections
        try:
            response = self._get("/library/sections")
        except Exception as exc:  # noqa: BLE001 — fail-soft: never break a dispatch
            log.warning("plex.sections_unreachable", base_url=self.base_url, error=type(exc).__name__)
            return []
        if response.status_code != 200:
            # 401 lands here: the token is wrong. The status is logged, the
            # token is not — the operator has enough to act.
            log.warning("plex.sections_http_error", base_url=self.base_url, status=response.status_code)
            return []
        try:
            payload: Any = response.json()
            # Parsed INSIDE the guard: a payload whose shape surprises the
            # parser must degrade the trigger like an unreadable body does.
            sections = _parse_sections(payload)
        except Exception as exc:  # noqa: BLE001 — fail-soft: never break a dispatch
            log.warning("plex.sections_unparseable", base_url=self.base_url, error=type(exc).__name__)
            return []
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

        This method is TOTAL: every failure — including one the transport raises
        that is not a ``requests.RequestException`` — becomes ``False``. Only
        ``type(exc).__name__`` is ever logged, never the exception itself, whose
        traceback frames hold the token-bearing headers.
        """
        try:
            section = self.section_for(target)
        except Exception as exc:  # noqa: BLE001 — fail-soft: never break a dispatch
            log.warning("plex.section_resolution_failed", error=type(exc).__name__)
            return False
        if section is None:
            log.warning("plex.no_section_for_path", path=str(target))
            return False
        try:
            response = self._get(f"/library/sections/{section.key}/refresh", parameters={"path": str(target)})
        except Exception as exc:  # noqa: BLE001 — fail-soft: never break a dispatch
            log.warning(
                "plex.refresh_unreachable",
                path=str(target),
                section=section.key,
                error=type(exc).__name__,
            )
            return False
        if response.status_code >= 400:
            log.warning(
                "plex.refresh_http_error",
                path=str(target),
                section=section.key,
                status=response.status_code,
            )
            return False
        log.info("plex.refresh_triggered", path=str(target), section=section.key, title=section.title)
        return True

    # -- Match coherence ----------------------------------------------------

    def section_items(self, section: PlexSection) -> list[PlexItem]:
        """List a section's items with their media paths, in ONE request.

        What the listing carries depends on the media family, verified against
        the live server: MOVIE entries carry ``Media/Part.file`` for every entry
        (1132/1132), so a movie is located by the listing alone. SHOW entries
        carry NEITHER ``Media`` NOR ``Location`` (0/733) — a show's folder path
        exists only on its item endpoint. No listing parameter changes that
        (``includeDetails`` / ``includeMeta`` probed live). What neither family
        carries in the listing is the ``Guid`` array: the entries hold only
        Plex's opaque ``plex://…`` guid, never the provider ids. That is why the
        guard reads the section once to resolve *movie* paths and calls
        :meth:`item` per show — and for every item it has to compare.

        Args:
            section: The section to list.

        Returns:
            The items, each with ``files`` populated and ``guids`` EMPTY (the
            listing does not carry them — do not read an empty ``guids`` here as
            « unmatched »). An empty list on any failure.
        """
        try:
            response = self._get(f"/library/sections/{section.key}/all", timeout=_GUARD_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.section_items_unreachable", section=section.key, error=type(exc).__name__)
            return []
        if response.status_code != 200:
            log.warning("plex.section_items_http_error", section=section.key, status=response.status_code)
            return []
        try:
            items = _parse_items(response.json())
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.section_items_unparseable", section=section.key, error=type(exc).__name__)
            return []
        log.info("plex.section_items_loaded", section=section.key, count=len(items))
        return items

    def section_show_items(self, section: PlexSection) -> list[PlexItem]:
        """List a section's SHOWS with their episode file paths.

        One listing plus one item read per show.

        The show-level listing (``/all``) carries NO path of any kind — that is
        why the guard cannot locate a show the way it locates a movie. The
        EPISODE listing (``/all?type=4``) carries ``Media/Part.file`` for every
        episode (verified live: 26823/26823) plus ``grandparentRatingKey`` —
        the show's own key. So one listing plus one :meth:`item` read per
        distinct show yields, for every show: its episode paths (the join) AND
        its provider guids and folder ``Location`` (the comparison) — nothing
        the guard needed is requested twice.

        Args:
            section: The section to list (a show library).

        Returns:
            The show items, each with ``files`` (its episodes' paths),
            ``locations`` and ``guids`` populated. An empty list on any
            failure — including a listing whose entries surprise the parser.
        """
        try:
            response = self._get(f"/library/sections/{section.key}/all", {"type": "4"}, timeout=_GUARD_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.section_shows_unreachable", section=section.key, error=type(exc).__name__)
            return []
        if response.status_code != 200:
            log.warning("plex.section_shows_http_error", section=section.key, status=response.status_code)
            return []
        try:
            episodes = _parse_items(response.json())
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.section_shows_unparseable", section=section.key, error=type(exc).__name__)
            return []
        shows: dict[str, PlexItem] = {}
        for episode in episodes:
            if not episode.grandparent_key or not episode.files:
                continue
            show = shows.get(episode.grandparent_key)
            if show is None:
                full = self.item(episode.grandparent_key)
                if full is None:
                    continue
                show = PlexItem(full.rating_key, full.title, full.guids, [], full.locations)
                shows[episode.grandparent_key] = show
            show.files.extend(episode.files)
        log.info("plex.section_shows_loaded", section=section.key, count=len(shows))
        return list(shows.values())

    def item(self, rating_key: str) -> PlexItem | None:
        """Read one item's metadata, provider guids included.

        Args:
            rating_key: The Plex item id.

        Returns:
            The item, or ``None`` when Plex is unreachable, refuses the token,
            does not know the key, or answers something unparseable. ``None``
            means « could not read », never « not matched » — an item that
            exists but carries no provider guid comes back with an EMPTY
            ``guids`` list, and that distinction is the whole point of the
            guard's diagnosis.
        """
        try:
            response = self._get(f"/library/metadata/{rating_key}", timeout=_GUARD_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.item_unreachable", rating_key=rating_key, error=type(exc).__name__)
            return None
        if response.status_code != 200:
            log.warning("plex.item_http_error", rating_key=rating_key, status=response.status_code)
            return None
        try:
            items = _parse_items(response.json())
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.item_unparseable", rating_key=rating_key, error=type(exc).__name__)
            return None
        return items[0] if items else None

    def matches(self, rating_key: str, hint: str) -> tuple[bool, list[PlexMatchCandidate]]:
        """Ask Plex which entries a provider-id hint resolves to.

        ``manual=1`` is what turns ``title`` into a search term rather than a
        re-run of the automatic agent, and a ``tmdb-522627`` / ``tvdb-131524``
        hint resolves to exactly ONE candidate — that is the mechanism the guard
        relies on to repair an item without guessing.

        Args:
            rating_key: The Plex item id to search matches for.
            hint: The search term, already formed (``tmdb-522627``).

        Returns:
            ``(ok, candidates)`` — *ok* is False on any FAILURE (unreachable,
            non-200, unparseable), True on a real answer. The guard needs the
            distinction: a failed request is ``plex_error`` (transient), while
            a successful request that resolves to nothing is ``no_candidate``
            (permanent) — reporting one as the other would be wrong AND
            actionable-looking, the exact failure class this module warns
            against.
        """
        try:
            response = self._get(
                f"/library/metadata/{rating_key}/matches",
                {"manual": "1", "title": hint},
                timeout=_GUARD_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.matches_unreachable", rating_key=rating_key, error=type(exc).__name__)
            return False, []
        if response.status_code != 200:
            log.warning("plex.matches_http_error", rating_key=rating_key, status=response.status_code)
            return False, []
        try:
            candidates = _parse_match_candidates(response.json())
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.matches_unparseable", rating_key=rating_key, error=type(exc).__name__)
            return False, []
        log.info("plex.matches_resolved", rating_key=rating_key, hint=hint, count=len(candidates))
        return True, candidates

    def match(self, rating_key: str, candidate: PlexMatchCandidate) -> bool:
        """Apply *candidate* as the item's match.

        A prior ``unmatch`` is NOT needed: the PUT re-matches an already-matched
        (and even a wrongly-matched) item, proven on the live server against two
        mis-matched films. Doing it in one call also means the guard never leaves
        an item unmatched behind a failure.

        Args:
            rating_key: The Plex item id to re-match.
            candidate: The match to apply, as returned by :meth:`matches`.

        Returns:
            ``True`` when Plex accepted the match, ``False`` on any failure.
            ``False`` is « nothing happened » — the item keeps whatever match it
            had, so a failed repair is never a destructive outcome.
        """
        parameters = {"guid": candidate.guid, "name": candidate.name}
        if candidate.year is not None:
            parameters["year"] = str(candidate.year)
        try:
            response = self._put(f"/library/metadata/{rating_key}/match", parameters)
        except Exception as exc:  # noqa: BLE001 — fail-soft: the guard never raises
            log.warning("plex.match_unreachable", rating_key=rating_key, error=type(exc).__name__)
            return False
        if response.status_code >= 400:
            log.warning("plex.match_http_error", rating_key=rating_key, status=response.status_code)
            return False
        log.info("plex.match_applied", rating_key=rating_key, guid=candidate.guid, name=candidate.name)
        return True


def _parse_sections(payload: Any) -> list[PlexSection]:
    """Map a ``/library/sections`` JSON payload to :class:`PlexSection` objects.

    Tolerant by design: Plex nests the list under ``MediaContainer.Directory``
    and each entry's roots under ``Location[].path``. Anything missing or of the
    wrong shape yields fewer sections (or a section with no roots) rather than
    an exception — a malformed payload must degrade the trigger, not break a
    dispatch. ``Location`` in particular is type-checked before iteration: the
    key can be present and ``null``, in which case ``dict.get`` returns ``None``
    and the ``[]`` default never applies.

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
        raw_locations = entry.get("Location")
        locations = (
            [loc.get("path") for loc in raw_locations if isinstance(loc, dict) and isinstance(loc.get("path"), str)]
            if isinstance(raw_locations, list)
            else []
        )
        title = entry.get("title")
        sections.append(
            PlexSection(
                key=key,
                title=title if isinstance(title, str) else "",
                locations=[loc for loc in locations if isinstance(loc, str) and loc],
            )
        )
    return sections


def _parse_items(payload: Any) -> list[PlexItem]:
    """Map a ``Metadata``-bearing JSON payload to :class:`PlexItem` objects.

    Serves both ``/library/sections/{key}/all`` (many entries, no ``Guid``) and
    ``/library/metadata/{key}`` (one entry, ``Guid`` present) — the container
    shape is the same and the difference is only which keys are populated.

    Tolerant by design, exactly like :func:`_parse_sections`: a surprising shape
    yields fewer items rather than an exception, because a malformed payload
    must degrade the guard's diagnosis, never abort a maintenance run. An entry
    with no ``ratingKey`` is dropped — without it nothing can be read or
    repaired, so it is not an item as far as the guard is concerned.

    Args:
        payload: The decoded JSON body.

    Returns:
        The parsed items (possibly empty).
    """
    container = payload.get("MediaContainer") if isinstance(payload, dict) else None
    entries = container.get("Metadata") if isinstance(container, dict) else None
    if not isinstance(entries, list):
        return []
    items: list[PlexItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rating_key = entry.get("ratingKey")
        if not isinstance(rating_key, str) or not rating_key:
            continue
        raw_guids = entry.get("Guid")
        guids = (
            [g.get("id") for g in raw_guids if isinstance(g, dict) and isinstance(g.get("id"), str)]
            if isinstance(raw_guids, list)
            else []
        )
        raw_media = entry.get("Media")
        files: list[str] = []
        if isinstance(raw_media, list):
            for medium in raw_media:
                if not isinstance(medium, dict):
                    continue
                raw_parts = medium.get("Part")
                if not isinstance(raw_parts, list):
                    continue
                files.extend(
                    part["file"] for part in raw_parts if isinstance(part, dict) and isinstance(part.get("file"), str)
                )
        raw_locations = entry.get("Location")
        locations = (
            [loc.get("path") for loc in raw_locations if isinstance(loc, dict) and isinstance(loc.get("path"), str)]
            if isinstance(raw_locations, list)
            else []
        )
        raw_grandparent = entry.get("grandparentRatingKey")
        grandparent_key = raw_grandparent if isinstance(raw_grandparent, str) and raw_grandparent else ""
        title = entry.get("title")
        items.append(
            PlexItem(
                rating_key=rating_key,
                title=title if isinstance(title, str) else "",
                guids=[g for g in guids if isinstance(g, str) and g],
                files=files,
                locations=[loc for loc in locations if isinstance(loc, str) and loc],
                grandparent_key=grandparent_key,
            )
        )
    return items


def _parse_match_candidates(payload: Any) -> list[PlexMatchCandidate]:
    """Map a ``/matches`` JSON payload to :class:`PlexMatchCandidate` objects.

    A candidate with no ``guid`` is dropped: the guid IS the thing a match call
    applies, so an entry without one cannot be acted on and keeping it would
    only let a caller believe a repair was available.

    Args:
        payload: The decoded JSON body.

    Returns:
        The parsed candidates, in the order Plex returned them (possibly empty).
    """
    container = payload.get("MediaContainer") if isinstance(payload, dict) else None
    results = container.get("SearchResult") if isinstance(container, dict) else None
    if not isinstance(results, list):
        return []
    candidates: list[PlexMatchCandidate] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        guid = entry.get("guid")
        if not isinstance(guid, str) or not guid:
            continue
        name = entry.get("name")
        year = entry.get("year")
        candidates.append(
            PlexMatchCandidate(
                guid=guid,
                name=name if isinstance(name, str) else "",
                year=year if isinstance(year, int) else None,
            )
        )
    return candidates


__all__ = ["PlexClient", "PlexItem", "PlexMatchCandidate", "PlexSection"]
