"""Executable media-completeness read-model — ONE composition of on-disk signals.

DESIGN §5 T4 / §9: the single, filesystem-only read-model of how "complete"
(i.e. dispatchable / acquired) a media directory is, composed from four
independently-owned presence signals:

* **artwork** — :func:`personalscraper.core.artwork_naming.artwork_status`
  (canonical poster/fanart/landscape detection across bare, media-prefixed and
  Kodi ``folder.jpg`` spellings).
* **NFO** — :func:`nfo_status`, the ONE strict NFO-validity verdict. It
  delegates ``complete`` to :func:`personalscraper.nfo_utils.is_nfo_complete`
  (parseable XML + at least one non-placeholder ``<uniqueid>``) so there is a
  single definition of "valid NFO" the scraper fast-skip, verify and indexer all
  converge onto (P5.5).
* **renamed video** (movies) — the main video file renamed to the canonical
  ``{Title}`` stem, the library convention ``verify`` does not itself enforce
  (mirrors ``verify.completeness.video_rename_gap``).
* **trailer** — filesystem presence only. Ownership of trailer placement stays
  with ``personalscraper.trailers`` (DESIGN P6); this module merely *reads* the
  path, so the placement rule is duplicated here as a small read-only copy
  (``core/`` must not import ``trailers/``).

Import direction: this module lives in ``core/`` and imports only stdlib, other
``core/`` modules, and two verified clean-leaf helpers —
``personalscraper.nfo_utils`` (transitively stdlib + ``logger`` only) and
``personalscraper.naming_patterns``. It imports NOTHING from ``indexer/``,
``scraper/``, ``acquire/``, ``verify/``, ``trailers/`` or ``web/``, so it can be
consumed from every layer without a cycle (enforced by
``tests/architecture/test_layering.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from personalscraper.core.artwork_naming import ArtworkStatus, artwork_status
from personalscraper.core.media_types import VIDEO_EXTENSIONS
from personalscraper.naming_patterns import PATTERNS
from personalscraper.nfo_utils import is_nfo_complete, parse_title_year

#: ``media_item.nfo_status`` tri-state, mirroring the indexer schema alias so
#: the read-model and the DB column speak the same vocabulary.
NfoState = Literal["missing", "invalid", "valid"]

MediaType = Literal["movie", "tvshow"]

# Trailer placement rule mirrored from ``personalscraper.trailers.placement``
# (the canonical owner — DESIGN P6). Kept as a local read-only copy because
# ``core/`` must not import ``trailers/`` (layering guard). Movies use the flat
# ``{name}-trailer.{ext}`` form; TV shows use the ``Trailers/{name}.{ext}``
# subfolder. Extensions mirror ``_KNOWN_TRAILER_EXTENSIONS`` in that module.
_TRAILER_EXTENSIONS: tuple[str, ...] = ("mp4", "mkv", "webm")
_TV_TRAILER_SUBFOLDER: str = "Trailers"


@dataclass(frozen=True)
class NfoStatus:
    """Strict NFO-validity verdict for one ``.nfo`` path (the ONE definition).

    ``complete`` is exactly the historical
    :func:`personalscraper.nfo_utils.is_nfo_complete` contract — present +
    parseable XML + at least one non-placeholder ``<uniqueid>``. ``has_title`` is
    surfaced for consumers (e.g. a drift check) but is deliberately NOT part of
    ``complete``: the live definition never required a title, and tightening it
    here would silently change the rescrape predicate — a P5.5 concern, not a
    read-model one.

    Attributes:
        present: Whether the ``.nfo`` file exists on disk.
        complete: The strict validity verdict (``is_nfo_complete``).
        has_title: Whether the NFO carries a non-empty ``<title>`` (informational).
    """

    present: bool
    complete: bool
    has_title: bool

    @property
    def status(self) -> NfoState:
        """Return the tri-state matching ``media_item.nfo_status``.

        Returns:
            ``"missing"`` when absent, ``"valid"`` when present + complete, else
            ``"invalid"`` (present but not strictly valid).
        """
        if not self.present:
            return "missing"
        return "valid" if self.complete else "invalid"


@dataclass(frozen=True)
class Completeness:
    """Composed on-disk completeness read-model for one media directory.

    Read-only composition of the four presence signals. Consumers may weigh the
    components themselves (``verify`` blocks on a missing poster but only warns on
    a missing landscape) via the component fields, or use the strict aggregate
    :attr:`complete` (all applicable components present — the operator's "acquired"
    definition: valid NFO + poster + landscape + trailer + renamed video).

    Attributes:
        media_type: ``"movie"`` or ``"tvshow"``.
        artwork: Poster/fanart/landscape presence.
        nfo: Strict NFO-validity verdict.
        has_renamed_video: Whether the movie's main video carries the canonical
            ``{Title}`` stem; ``None`` for TV shows (episode renaming is governed
            by ``verify``'s episode checks, not this movie-only component).
        has_trailer: Whether a trailer file is present on disk (filesystem only).
    """

    media_type: MediaType
    artwork: ArtworkStatus
    nfo: NfoStatus
    has_renamed_video: bool | None
    has_trailer: bool

    @property
    def missing(self) -> tuple[str, ...]:
        """Return the names of the applicable components that are absent.

        Returns:
            An ordered tuple drawn from ``("nfo", "poster", "landscape",
            "renamed_video", "trailer")`` — only components that apply and are
            missing. ``renamed_video`` is skipped for TV shows (not applicable).
        """
        gaps: list[str] = []
        if not self.nfo.complete:
            gaps.append("nfo")
        if not self.artwork.poster:
            gaps.append("poster")
        if not self.artwork.landscape:
            gaps.append("landscape")
        if self.has_renamed_video is False:
            gaps.append("renamed_video")
        if not self.has_trailer:
            gaps.append("trailer")
        return tuple(gaps)

    @property
    def complete(self) -> bool:
        """Whether every applicable completeness component is present.

        Returns:
            ``True`` iff :attr:`missing` is empty (the strict "acquired" verdict).
        """
        return not self.missing


def _nfo_has_title(nfo_path: Path) -> bool:
    """Return whether *nfo_path* parses and carries a non-empty ``<title>``.

    Fail-soft: an unparseable or unreadable NFO yields ``False`` (never raises),
    matching the tolerance of the other NFO readers in the pipeline.

    Args:
        nfo_path: Path to the ``.nfo`` file (existence not assumed).

    Returns:
        ``True`` iff the NFO parses as XML and its ``<title>`` is non-empty.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314 — trusted NFO we wrote
    except (ET.ParseError, OSError):
        return False
    return bool((root.findtext("title") or "").strip())


def nfo_status(nfo_path: Path) -> NfoStatus:
    """Return the strict NFO-validity verdict for *nfo_path* (the ONE definition).

    ``complete`` delegates to :func:`personalscraper.nfo_utils.is_nfo_complete`
    so this read-model and every other consumer share a single definition of a
    valid NFO (parseable XML + a non-placeholder ``<uniqueid>``); ``has_title`` is
    computed independently as informational context.

    Args:
        nfo_path: Path to the ``.nfo`` file (need not exist).

    Returns:
        An :class:`NfoStatus`. When the file is absent, ``complete`` /
        ``has_title`` are ``False`` and :attr:`NfoStatus.status` is ``"missing"``.
    """
    if not nfo_path.exists():
        return NfoStatus(present=False, complete=False, has_title=False)
    return NfoStatus(
        present=True,
        complete=is_nfo_complete(nfo_path),
        has_title=_nfo_has_title(nfo_path),
    )


def _nfo_path_for(directory: Path, media_type: MediaType) -> Path:
    """Return the canonical NFO path for a media directory.

    Mirrors the strict resolution used by the indexer full-scan
    (``_item_stage._nfo_metadata_for_dir``) and the rescraper
    (``rescraper._detect_needs``): the fixed ``tvshow.nfo`` for shows, and the
    raw ``{Title}.nfo`` (folder title with the trailing year stripped) for movies.

    Args:
        directory: The media directory.
        media_type: ``"movie"`` or ``"tvshow"``.

    Returns:
        The path where the canonical NFO is expected.
    """
    if media_type == "tvshow":
        return directory / "tvshow.nfo"
    title = parse_title_year(directory.name)[0]
    return directory / f"{title}.nfo"


def _main_video(directory: Path) -> Path | None:
    """Return the largest top-level non-trailer video file, or ``None``.

    Mirrors ``verify.completeness.main_video`` but uses the canonical
    :data:`personalscraper.core.media_types.VIDEO_EXTENSIONS` SSOT (a strict
    superset of that helper's ad-hoc set). AppleDouble sidecars (``._*``) and
    files whose stem contains ``trailer`` are skipped.

    Args:
        directory: The movie directory.

    Returns:
        The largest eligible video file directly in *directory*, or ``None``.
    """
    best: Path | None = None
    best_size = -1
    try:
        entries = list(directory.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.is_file() or entry.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
            continue
        if "trailer" in entry.stem.lower() or entry.name.startswith("._"):
            continue
        try:
            size = entry.stat().st_size
        except OSError:
            continue
        if size > best_size:
            best, best_size = entry, size
    return best


def _renamed_video_present(directory: Path, media_type: MediaType) -> bool | None:
    """Return whether the movie's main video carries the canonical ``{Title}`` stem.

    Mirrors ``verify.completeness.video_rename_gap`` (a movie-only convention
    ``verify`` does not itself enforce). The expected stem is
    ``PATTERNS.format("movie_video", Title=<folder title>)`` — the folder title
    with the year stripped, sanitized. Returns ``None`` for TV shows (episode
    renaming is a ``verify`` episode-check concern, not this component).

    Args:
        directory: The media directory.
        media_type: ``"movie"`` or ``"tvshow"``.

    Returns:
        ``True`` when renamed, ``False`` when a video is present but misnamed (or
        absent), ``None`` when not applicable (TV show).
    """
    if media_type != "movie":
        return None
    video = _main_video(directory)
    if video is None:
        return False
    title = parse_title_year(directory.name)[0]
    expected = PATTERNS.format("movie_video", Title=title)
    return video.stem == expected


def _trailer_present(directory: Path, media_type: MediaType) -> bool:
    """Return whether a trailer file exists on disk for this media directory.

    Filesystem read only (no size/content validation): the Plex-conformant
    placement — flat ``{name}-trailer.{ext}`` for movies, ``Trailers/{name}.{ext}``
    for TV shows — mirrored from ``trailers.placement`` (ownership stays P6).

    Args:
        directory: The media directory.
        media_type: ``"movie"`` or ``"tvshow"``.

    Returns:
        ``True`` iff a trailer file exists at the expected placement.
    """
    name = directory.name
    for ext in _TRAILER_EXTENSIONS:
        if media_type == "tvshow":
            candidate = directory / _TV_TRAILER_SUBFOLDER / f"{name}.{ext}"
        else:
            candidate = directory / f"{name}-trailer.{ext}"
        if candidate.is_file():
            return True
    return False


def media_completeness(directory: Path, media_type: MediaType) -> Completeness:
    """Compose the on-disk completeness read-model for one media directory.

    Reads (never mutates) the four presence signals — artwork, NFO validity,
    canonical video rename (movies), and trailer placement — and returns them as
    one :class:`Completeness`. This is DESIGN §9's executable completeness: the
    single filesystem definition of "acquired" the consumers converge onto.

    Args:
        directory: The media directory (``Title (Year)`` for movies, show root for
            TV shows).
        media_type: ``"movie"`` or ``"tvshow"``.

    Returns:
        The composed :class:`Completeness` read-model.
    """
    return Completeness(
        media_type=media_type,
        artwork=artwork_status(directory, media_type),
        nfo=nfo_status(_nfo_path_for(directory, media_type)),
        has_renamed_video=_renamed_video_present(directory, media_type),
        has_trailer=_trailer_present(directory, media_type),
    )


__all__ = [
    "Completeness",
    "NfoState",
    "NfoStatus",
    "media_completeness",
    "nfo_status",
]
