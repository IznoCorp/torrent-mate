"""Tests for ``journey_release_name`` — what was ACTUALLY grabbed (§13).

Regression anchor: on 2026-08-05 the Parcours card for « Spider-Man : Brand New Day »
showed the followed FILM's title above a stepper reading « Ingéré », while the release
sitting in staging was `Michael Giacchino … (Original Motion Picture Soundtrack) … FLAC`.
The operator could not see the mismatch from the interface — the card never showed the
release name at all, so a soundtrack and the film it is named after were indistinguishable.
"""

from __future__ import annotations

from personalscraper.acquire._provenance_store import ProvenanceRow, journey_release_name
from personalscraper.core.identity import MediaRef

RELEASE = "Michael Giacchino Spider-Man_ Brand New Day (Original Motion Picture Soundtrack).2026.WEB.FLAC"


def _row(
    *,
    status: str | None = "ingested",
    ingest_path: str | None = None,
    current_path: str | None = None,
    scraped_at: int | None = None,
) -> ProvenanceRow:
    return ProvenanceRow(
        info_hash="1329fe9e",
        followed_id=24,
        media_ref=MediaRef(tmdb_id=969681),
        kind="movie",
        ingest_path=ingest_path,
        current_path=current_path,
        scraped_ref=None,
        dispatch_path=None,
        grabbed_at=1,
        ingested_at=2,
        scraped_at=scraped_at,
        dispatched_at=None,
        status=status,
    )


def test_the_live_incident_shows_the_soundtrack_name() -> None:
    """The card must be able to say « FLAC soundtrack », not just the film's title."""
    row = _row(ingest_path=f"/Volumes/SSD/A TRIER/097-TEMP/{RELEASE}")

    assert journey_release_name(row) == RELEASE


def test_ingest_path_wins_over_current_path() -> None:
    """LOAD-BEARING: ingest_path is the release VERBATIM as it landed.

    ``current_path`` is renamed by the scrape to the canonical media folder, so it
    stops being the release name the moment identification succeeds.
    """
    row = _row(
        ingest_path=f"/staging/097-TEMP/{RELEASE}",
        current_path="/staging/002-TVSHOWS/Ted Lasso (2020)",
        scraped_at=3,
    )

    assert journey_release_name(row) == RELEASE


def test_current_path_is_used_before_the_scrape_renames_it() -> None:
    """A row with no recorded ingest_path still knows its release — until the rename."""
    row = _row(ingest_path=None, current_path=f"/staging/004-AUDIO/{RELEASE}", scraped_at=None)

    assert journey_release_name(row) == RELEASE


def test_current_path_is_refused_after_the_scrape() -> None:
    """LOAD-BEARING: post-scrape, current_path is the MEDIA folder.

    Reporting it as the release name would be a lie (§13), so the answer is
    « unknown » instead.
    """
    row = _row(ingest_path=None, current_path="/staging/002-TVSHOWS/Ted Lasso (2020)", scraped_at=3)

    assert journey_release_name(row) is None


def test_no_path_at_all_is_unknown_never_invented() -> None:
    """Older rows carry no paths; the interface must say « inconnu », not guess."""
    assert journey_release_name(_row()) is None


def test_trailing_separator_does_not_yield_an_empty_name() -> None:
    """A stored path with a trailing slash must not degrade to an empty string."""
    row = _row(ingest_path=f"/staging/097-TEMP/{RELEASE}/")

    assert journey_release_name(row) == RELEASE


def test_none_row_is_unknown() -> None:
    """The helper is shared with the stalled-grab surface, which may hold no journey."""
    assert journey_release_name(None) is None
