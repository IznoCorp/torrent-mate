"""Tests for the ``follow detect`` command (criteria 5-6, 8-9).

The first seven tests drive ``follow_detect`` over a fully-mocked AppContext
to exercise the golden enqueue / skip-owned / skip-dup / dry-run / empty-set /
boundary / layering branches.  They use the REAL attribute names
(``app_context.provider_registry`` and ``app_context.event_bus``) so they do
not paper over the registry-source / event-bus-source wiring.

The final test (``test_detect_integration_enqueues_into_real_store``) is
NON-VACUOUS: it wires a REAL :class:`ConcreteAcquireStore` behind a real
:class:`AcquireContext` and asserts the enqueued row round-trips through the
real DB.  It fails if anyone reverts the command to ``acquire.provider_registry``
or to the per-series ``poll_known(fs, ...)`` signature, because those bugs are
invisible to the all-mock tests.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.acquire.context import AcquireContext
from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, SeriesCatalog, WantedItem
from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import NullOwnershipChecker


def _catalogs(episodes: list[AiredEpisode], *, series_status: str | None = None) -> list[SeriesCatalog]:
    """Wrap a flat episode list the way ``poll_catalog`` returns it.

    The detect pass reads catalogues (episodes + the series' production status)
    rather than a flat episode list: « Terminé » needs a positive end-of-series
    fact, and the poll already had it in hand. These tests still describe their
    input as « the episodes the provider returns », so the shape conversion
    lives here instead of in twenty call sites.

    Args:
        episodes: The episodes the fake provider returns, any series.
        series_status: The production status to attribute to every series.

    Returns:
        One :class:`SeriesCatalog` per distinct ``media_ref``.
    """
    by_ref: dict[MediaRef, list[AiredEpisode]] = {}
    for ep in episodes:
        by_ref.setdefault(ep.media_ref, []).append(ep)
    return [
        SeriesCatalog(followed_id=None, media_ref=ref, series_status=series_status, episodes=eps)
        for ref, eps in by_ref.items()
    ]


def _fs(followed_id: int = 1, tvdb_id: int = 99) -> FollowedSeries:
    """Build an active followed series VO."""
    return FollowedSeries(
        id=followed_id,
        media_ref=MediaRef(tvdb_id=tvdb_id),
        title="Test Show",
        added_at=1_000_000,
        active=True,
    )


def _ep(
    tvdb_id: int = 99,
    season: int = 1,
    ep: int = 1,
    air_date: date = date(2024, 1, 1),
) -> AiredEpisode:
    """Build an aired-episode VO whose media_ref maps back to ``_fs``."""
    return AiredEpisode(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        season=season,
        episode=ep,
        air_date=air_date,
        title="Episode Title",
    )


def _make_ctx(
    series: list[FollowedSeries],
    owned: bool = False,
    existing: WantedItem | None = None,
) -> tuple[Any, MagicMock, MagicMock]:
    """Build a minimal stub AppContext for follow detect tests.

    Exposes the REAL AppContext attribute names: ``provider_registry`` and
    ``event_bus`` live on the app_context (NOT on ``acquire``), and ``acquire``
    carries only ``store`` + ``ownership``.

    Args:
        series: Active followed series returned by ``store.follow.list_active``.
        owned: Whether ``ownership.owns`` reports the episode as owned.
        existing: A duplicate wanted row returned by ``store.wanted.find``.

    Returns:
        A ``(app_context, store, bus)`` triple.
    """
    store = MagicMock()
    store.follow.list_active.return_value = series
    store.wanted.find.return_value = existing
    store.wanted.add.return_value = 42

    ownership = MagicMock()
    ownership.owns.return_value = owned

    acquire = MagicMock()
    acquire.store = store
    acquire.ownership = ownership

    bus = MagicMock()

    app_context = MagicMock()
    app_context.acquire = acquire
    app_context.event_bus = bus
    app_context.provider_registry = MagicMock()
    return app_context, store, bus


@contextmanager
def _pinned_today(fixed: date) -> Any:
    """Pin ``personalscraper.commands.follow.date.today()`` to *fixed*.

    ``follow_detect`` reads the wall clock via ``date.today()`` (module-level
    import). A real ``date`` subclass keeps every other ``date`` behavior
    (comparisons with the AiredEpisode air_dates) intact, so a test can anchor
    « today » next to its hardcoded air-date literals and pass on ANY system
    date (review F3 — the previous recent-air-date trick expired with the
    wall clock).
    """

    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return fixed

    with patch("personalscraper.commands.follow.date", _FixedDate):
        yield


def _run_detect(
    app_context: Any,
    aired_eps: list[AiredEpisode],
    dry_run: bool = False,
    series_filter: str | None = None,
) -> None:
    """Drive ``follow_detect`` with ``per_step_boundary`` + ``poll_known`` patched.

    Args:
        app_context: The app context to yield from the boundary.
        aired_eps: The known-date episodes ``poll_known`` returns.
        dry_run: ``--dry-run`` flag value.
        series_filter: ``--series`` filter value.
    """
    from personalscraper.commands.follow import follow_detect

    @contextmanager
    def _boundary(config: Any, settings: Any, *, build_torrent_client: bool = False) -> Any:
        yield app_context

    with (
        patch("personalscraper.commands.follow.per_step_boundary", _boundary),
        patch("personalscraper.acquire.detect.poll_catalog", return_value=_catalogs(aired_eps)),
    ):
        ctx = MagicMock()
        ctx.obj.config = MagicMock()
        follow_detect(ctx, dry_run=dry_run, series=series_filter)


def test_detect_golden_enqueues_unowned_episode() -> None:
    """GOLDEN: non-owned, non-dup episode → add() once, WantedEnqueued once.

    « today » is PINNED 2 days after the episode's air date (deterministic —
    passes on any system date, review F3): within 7 days, so the season-grab
    R1 post-pass skips this single-episode season — the golden's intent is
    verifying the per-episode enqueue path, not exercising season detection.
    """
    from personalscraper.acquire.events import WantedEnqueued

    fs = _fs(followed_id=1, tvdb_id=99)
    ep = _ep(tvdb_id=99, season=1, ep=1, air_date=date(2024, 1, 10))
    app_context, store, bus = _make_ctx([fs], owned=False, existing=None)

    with _pinned_today(date(2024, 1, 12)):
        _run_detect(app_context, [ep])

    store.wanted.add.assert_called_once()
    added: WantedItem = store.wanted.add.call_args[0][0]
    assert added.followed_id == 1  # mapped back via by_ref
    assert added.kind == "episode"
    assert added.status == "pending"
    assert added.season == 1
    assert added.episode == 1
    assert added.media_ref == ep.media_ref

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedEnqueued)
    assert emitted.kind == "episode"
    assert emitted.season == 1
    assert emitted.episode == 1


def test_detect_skips_owned_episode() -> None:
    """owned=True → add() NOT called, WantedEnqueued NOT emitted."""
    fs = _fs()
    ep = _ep()
    app_context, store, bus = _make_ctx([fs], owned=True)

    _run_detect(app_context, [ep])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def _movie_fs(followed_id: int = 7, tmdb_id: int = 1184918) -> FollowedSeries:
    """Build an active MOVIE follow (§5 film flow)."""
    return FollowedSeries(
        id=followed_id,
        media_ref=MediaRef(tmdb_id=tmdb_id),
        title="Le Robot sauvage",
        added_at=1_000_000,
        active=True,
        kind="movie",
    )


def test_detect_movie_follow_enqueues_movie_wanted() -> None:
    """§5 GOLDEN (guard-test): a non-owned movie follow produces ONE movie wanted row.

    Red on the previous implementation: `follow detect` hardcoded kind='episode'
    and only walked aired episodes, so a followed FILM never produced a wanted
    row — the §5 film acquisition flow could not start.
    """
    from personalscraper.acquire.events import WantedEnqueued

    mf = _movie_fs()
    app_context, store, bus = _make_ctx([mf], owned=False, existing=None)

    _run_detect(app_context, [])

    store.wanted.add.assert_called_once()
    added: WantedItem = store.wanted.add.call_args[0][0]
    assert added.kind == "movie"
    assert added.followed_id == 7
    assert added.season is None and added.episode is None
    assert added.status == "pending"
    assert added.media_ref == mf.media_ref
    # Ownership was checked as a MOVIE, not an episode.
    ownership = app_context.acquire.ownership
    assert ownership.owns.call_args.kwargs.get("kind") == "movie"
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedEnqueued)
    assert emitted.kind == "movie"


def test_detect_movie_follow_owned_closes_and_unfollows() -> None:
    """§5 closure (guard-test): an OWNED movie follow is auto-removed with a trace.

    "Film : une fois récupéré et acquis (pipeline terminé), il est retiré des
    suivis automatiquement." The detect reconciliation must close the live
    wanted row (done), deactivate the follow, and emit FilmAcquired — never
    enqueue a new wanted row.
    """
    from personalscraper.acquire.events import FilmAcquired

    existing = WantedItem(
        media_ref=MediaRef(tmdb_id=1184918),
        kind="movie",
        status="grabbed",
        enqueued_at=1,
        followed_id=7,
        id=99,
    )
    app_context, store, bus = _make_ctx([_movie_fs()], owned=True, existing=existing)

    _run_detect(app_context, [])

    store.wanted.add.assert_not_called()
    store.wanted.set_status.assert_called_once_with(99, "done")
    # REMOVED, not paused (operator 2026-08-08): the follow leaves the list.
    store.follow.delete.assert_called_once_with(7)
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, FilmAcquired)
    assert emitted.title == "Le Robot sauvage"
    assert emitted.followed_id == 7


def test_detect_movie_follow_skipped_on_duplicate() -> None:
    """A movie follow with a live wanted row is not re-enqueued (skipped-dup)."""
    existing = WantedItem(
        media_ref=MediaRef(tmdb_id=1184918),
        kind="movie",
        status="pending",
        enqueued_at=1,
        followed_id=7,
    )
    app_context, store, bus = _make_ctx([_movie_fs()], owned=False, existing=existing)

    _run_detect(app_context, [])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_skips_duplicate_episode() -> None:
    """Existing row found by find() → add() NOT called, WantedEnqueued NOT emitted."""
    fs = _fs()
    ep = _ep()
    existing = WantedItem(
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="pending",
        enqueued_at=1_000_000,
        followed_id=1,
        season=1,
        episode=1,
    )
    app_context, store, bus = _make_ctx([fs], owned=False, existing=existing)

    _run_detect(app_context, [ep])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_dry_run_no_writes_no_emits() -> None:
    """--dry-run: add() NOT called, bus.emit NOT called regardless of eligibility."""
    fs = _fs()
    ep = _ep()
    app_context, store, bus = _make_ctx([fs], owned=False, existing=None)

    _run_detect(app_context, [ep], dry_run=True)

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_empty_active_set_no_crash() -> None:
    """Empty active followed set → no crash, no adds, no emits."""
    app_context, store, bus = _make_ctx([])

    _run_detect(app_context, [])

    store.wanted.add.assert_not_called()
    bus.emit.assert_not_called()


def test_detect_boundary_no_grab_calls() -> None:
    """BOUNDARY (criterion 8): detect never drives the grab orchestrator.

    The command reads only ``store`` / ``ownership`` off ``acquire``; the grab
    sub-handle (``acquire.grab``) must stay untouched.
    """
    fs = _fs()
    ep = _ep()
    app_context, store, bus = _make_ctx([fs])
    # Replace the auto-speccing MagicMock attribute with an explicit grab mock
    # so we can assert it was never touched (a bare MagicMock auto-creates
    # attributes, so .called on an unaccessed child is False by construction).
    grab_mock = MagicMock()
    app_context.acquire.grab = grab_mock

    _run_detect(app_context, [ep])

    grab_mock.assert_not_called()
    assert not grab_mock.method_calls, "detect must not invoke any grab orchestrator method"


def test_detect_layering_no_indexer_import() -> None:
    """LAYERING (criterion 9): commands/follow.py must not import indexer."""
    import ast

    src = Path("personalscraper/commands/follow.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in getattr(node, "names", [])]
            module = getattr(node, "module", "") or ""
            assert "indexer" not in module, f"Forbidden indexer import: {module}"
            for n in names:
                assert "indexer" not in n, f"Forbidden indexer import: {n}"


def test_detect_integration_enqueues_into_real_store(tmp_path: Path) -> None:
    """NON-VACUOUS: detect enqueues a real WantedItem through a REAL store.

    Wires a real :class:`ConcreteAcquireStore` behind a real
    :class:`AcquireContext` and a lightweight app-context stub exposing the
    REAL attribute names (``provider_registry`` / ``event_bus`` on the
    app_context).  ``poll_known`` is patched to return one aired episode whose
    ``media_ref`` equals the followed series' ``media_ref`` so the command's
    ``by_ref`` map resolves it.

    This test fails if someone reverts the command to
    ``acquire.provider_registry`` (AttributeError on the real AcquireContext —
    it has no such field) or to the per-series ``poll_known(fs, ...)`` call
    (the patched poll_known asserts it is invoked once over the Sequence).  The
    final DB round-trip proves ``store.wanted.add`` ran through the real store
    and persisted with ``status='pending'`` and the mapped ``followed_id``.
    """
    db_path = tmp_path / "acquire.db"
    store = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        # Seed a real followed series and capture its rowid.
        series = FollowedSeries(
            media_ref=MediaRef(tvdb_id=81189),
            title="Breaking Bad",
            added_at=1_700_000_000,
            active=True,
        )
        followed_id = store.follow.add(series)

        # Real AcquireContext with the REAL store + null ownership; a MagicMock
        # tracker_registry satisfies the frozen-dataclass field (unused here).
        acquire = AcquireContext(
            tracker_registry=MagicMock(),
            store=store,
            ownership=NullOwnershipChecker(),
        )

        # Lightweight app-context stub exposing the REAL attribute names. Using
        # a real EventBus exercises the actual emit path.
        bus = EventBus()
        app_context = SimpleNamespace(
            acquire=acquire,
            event_bus=bus,
            provider_registry=MagicMock(),  # stub — poll_known is patched
        )

        aired = AiredEpisode(
            media_ref=MediaRef(tvdb_id=81189),  # equals the followed media_ref
            season=2,
            episode=5,
            # Aired 2 days before the PINNED today below — within 7d so the R1
            # season gate skips; deterministic on any system date (review F3).
            air_date=date(2024, 1, 10),
            title="Better Call Saul",
        )

        from personalscraper.acquire.airing import poll_known as _real_poll  # noqa: F401
        from personalscraper.commands.follow import follow_detect

        @contextmanager
        def _boundary(config: Any, settings: Any, *, build_torrent_client: bool = False) -> Any:
            yield app_context

        poll_spy = MagicMock(return_value=_catalogs([aired]))
        with (
            _pinned_today(date(2024, 1, 12)),
            patch("personalscraper.commands.follow.per_step_boundary", _boundary),
            patch("personalscraper.acquire.detect.poll_catalog", poll_spy),
        ):
            ctx = MagicMock()
            ctx.obj.config = MagicMock()
            follow_detect(ctx, dry_run=False, series=None)

        # poll_known was called ONCE over the active Sequence (not per series):
        # the first positional arg is a list/sequence containing our series.
        poll_spy.assert_called_once()
        passed_series = poll_spy.call_args[0][0]
        assert isinstance(passed_series, (list, tuple))
        assert any(s.media_ref == series.media_ref for s in passed_series)

        # REAL DB round-trip: the row was persisted through the real store.
        found = store.wanted.find(followed_id=followed_id, kind="episode", season=2, episode=5)
        assert found is not None, "detect must enqueue a real wanted row through the real store"
        assert found.status == "pending"
        assert found.followed_id == followed_id
        assert found.media_ref == MediaRef(tvdb_id=81189)
    finally:
        store.close()


def test_detect_row_renders_season_action_without_none() -> None:
    """F9 REGRESSION: a season action renders an em-dash episode cell.

    ``_detect_row`` only special-cased movies, so a season action fell into
    the episode branch and printed ``str(None)`` == "None" in the Episode
    column. The season row must render like the movie special-case style:
    real season number, em-dash episode, last air date, empty title cell.
    """
    from personalscraper.acquire.detect import DetectAction, DetectOutcome
    from personalscraper.commands.follow import _detect_row

    action = DetectAction(
        kind="season",
        title="Severance",
        season=2,
        episode=None,
        air_date="2024-06-01",
        episode_title=None,
        outcome=DetectOutcome.ENQUEUED,
    )

    row = _detect_row(action, dry_run=False)

    assert row == ("Severance", "2", "—", "2024-06-01", "", "[green]enqueued[/green]")
    assert "None" not in row, "a season row must never print the literal 'None'"

    # Episode rows keep their exact pre-existing shape (no regression).
    ep_action = DetectAction(
        kind="episode",
        title="Severance",
        season=2,
        episode=3,
        air_date="2024-05-01",
        episode_title="Ep3",
        outcome=DetectOutcome.ENQUEUED,
    )
    assert _detect_row(ep_action, dry_run=False) == (
        "Severance",
        "2",
        "3",
        "2024-05-01",
        "Ep3",
        "[green]enqueued[/green]",
    )


def test_detect_resurrects_wrongfully_abandoned_episode() -> None:
    """B.4: an abandoned aired-unowned episode within cutoff goes back to pending.

    The House-of-the-Dragon shape: S03E04 was terminally abandoned 20 minutes
    after its enqueue because the tracker had nothing yet. Detect must re-open
    such a row (status → pending, clock restarted) instead of skipping it as a
    dup forever.
    """
    import time as _time

    from personalscraper.conf.models.acquire import CadenceConfig

    fs = _fs(followed_id=1, tvdb_id=99)
    ep = _ep(tvdb_id=99, season=3, ep=4)
    abandoned = WantedItem(
        id=22,
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="abandoned",
        enqueued_at=int(_time.time()) - 3600,  # 1h old — well within any cutoff
        followed_id=1,
        season=3,
        episode=4,
    )
    app_context, store, bus = _make_ctx([fs], owned=False, existing=abandoned)
    store.wanted.resurrect.return_value = True

    from contextlib import contextmanager

    from personalscraper.commands.follow import follow_detect

    @contextmanager
    def _boundary(config: Any, settings: Any, *, build_torrent_client: bool = False) -> Any:
        yield app_context

    ctx = MagicMock()
    ctx.obj.config.acquire.cadence = CadenceConfig()
    with (
        patch("personalscraper.commands.follow.per_step_boundary", _boundary),
        patch("personalscraper.acquire.detect.poll_catalog", return_value=_catalogs([ep])),
    ):
        follow_detect(ctx, dry_run=False, series=None)

    store.wanted.resurrect.assert_called_once()
    assert store.wanted.resurrect.call_args[0][0] == 22
    store.wanted.add.assert_not_called()


def test_detect_past_cutoff_abandoned_stays_abandoned() -> None:
    """An abandoned row past its cadence cutoff is NOT resurrected (no flip-flop)."""
    from personalscraper.conf.models.acquire import CadenceConfig

    fs = _fs(followed_id=1, tvdb_id=99)
    ep = _ep(tvdb_id=99, season=3, ep=4)
    abandoned = WantedItem(
        id=23,
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="abandoned",
        enqueued_at=1_000_000,  # ancient — far past any cutoff
        followed_id=1,
        season=3,
        episode=4,
    )
    app_context, store, _bus = _make_ctx([fs], owned=False, existing=abandoned)

    from contextlib import contextmanager

    from personalscraper.commands.follow import follow_detect

    @contextmanager
    def _boundary(config: Any, settings: Any, *, build_torrent_client: bool = False) -> Any:
        yield app_context

    ctx = MagicMock()
    ctx.obj.config.acquire.cadence = CadenceConfig()
    with (
        patch("personalscraper.commands.follow.per_step_boundary", _boundary),
        patch("personalscraper.acquire.detect.poll_catalog", return_value=_catalogs([ep])),
    ):
        follow_detect(ctx, dry_run=False, series=None)

    store.wanted.resurrect.assert_not_called()
    store.wanted.add.assert_not_called()


def test_detect_writes_aired_catalog_cache() -> None:
    """P0-B.1: detect persists the polled aired catalog per followed series."""
    fs = _fs(followed_id=1, tvdb_id=99)
    eps = [_ep(tvdb_id=99, season=1, ep=1), _ep(tvdb_id=99, season=1, ep=2)]
    app_context, store, _bus = _make_ctx([fs], owned=True)

    _run_detect(app_context, eps)

    store.aired.replace_for_followed.assert_called_once()
    args, kwargs = store.aired.replace_for_followed.call_args
    assert args[0] == 1
    assert [(s, e) for (s, e, _t, _d) in args[1]] == [(1, 1), (1, 2)]
    assert "now" in kwargs


def test_detect_dry_run_does_not_write_cache() -> None:
    """--dry-run leaves the aired catalog cache untouched."""
    fs = _fs(followed_id=1, tvdb_id=99)
    app_context, store, _bus = _make_ctx([fs], owned=True)

    _run_detect(app_context, [_ep(tvdb_id=99)], dry_run=True)

    store.aired.replace_for_followed.assert_not_called()
