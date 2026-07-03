#!/usr/bin/env python3
"""Manual, real-environment E2E harness for the watch-seed feature.

NOT collected by CI: the filename lacks the ``test_`` prefix, so pytest never
imports it. It is a standalone script the operator runs against the LIVE
qBittorrent + real managed trackers + the real ``acquire.db``.

Purpose: exercise the *real* production code paths (RP10a parser, RP10b
list_files/properties, path-frame normalization, ``CrossSeedService.check``,
``WatcherService.evaluate``) against real data — the exact surface where
synthetic tests were vacuous (the cycle-1 path-frame bug only shows up against
a real multi-file qBittorrent layout vs a real tracker ``.torrent``).

Safety model — staged, read-only by default:
  * ``env``           config + qBit connectivity + acquire.db state (read-only)
  * ``layout``        real local TorrentLayout, raw vs normalized paths (read-only)
  * ``match``         REAL CrossSeedService.check() with a READ-ONLY torrent client
                      (inject/tag/resume/delete refused + logged) — full real search +
                      fetch + parse + structural_match; nothing injected, no obligation
                      written. Only benign cross_seed_history rows may be written.
  * ``watch-decide``  WatcherService.evaluate() on the live snapshot (read-only)
  * ``inject``        REAL injection (opt-in, requires --confirm-inject): injects into
                      qBittorrent, tags SEED_PURE, writes a SeedObligation. Prints cleanup.

The cross_seed / per-tracker kill-switches in the real config stay OFF; this
harness flips them ON *in memory only* (never touches config files) via
``--enable-tracker``.

Usage examples::

    python tests/manual/e2e_watch_seed.py env
    python tests/manual/e2e_watch_seed.py layout --hash f9afc9d9a271
    python tests/manual/e2e_watch_seed.py match --enable-tracker c411 --enable-tracker torr9 --limit 5
    python tests/manual/e2e_watch_seed.py watch-decide
    python tests/manual/e2e_watch_seed.py inject --hash <H> --enable-tracker c411 --confirm-inject
"""

from __future__ import annotations

# Manual harness (not shipped, not CI-collected): per-stage helper docstrings
# would be noise; the module docstring documents every stage. It is dynamically
# typed glue against borrowed app types (torrent_client union, Any read-only
# proxy) and is NOT part of the CI type-check surface (make lint only runs mypy
# on personalscraper/).
# ruff: noqa: D102, D103, D105, D107
# mypy: ignore-errors
import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.acquire._cross_seed_support import _normalize_qbit_files
from personalscraper.acquire.cross_seed import CrossSeedService
from personalscraper.acquire.watcher import (
    WatcherDecision,
    WatcherInput,
    WatcherService,
    WatcherState,
)
from personalscraper.api.torrent._errors import ApiError
from personalscraper.cli_helpers import _build_app_context
from personalscraper.conf.loader import load_config, resolve_config_path
from personalscraper.config import Settings
from personalscraper.core.tags import SEED_PURE
from personalscraper.ingest.tracker import IngestTracker

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.core.app_context import AppContext


# ── output helpers ──────────────────────────────────────────────────────────


def _h1(title: str) -> None:
    print(f"\n{'=' * 78}\n {title}\n{'=' * 78}")


def _kv(key: str, value: object) -> None:
    print(f"  {key:<28} {value}")


# ── config override (in-memory, never touches files) ────────────────────────


def _enable_cross_seed(config: Config, trackers: list[str], disable: list[str]) -> Config:
    """Return a config copy with cross_seed.enabled + the named trackers gated on.

    Uses pydantic ``model_copy`` (works on frozen models) — the real config on
    disk is never modified. Empty *trackers* → every enabled tracker (minus
    *disable*) is gated on. Trackers in *disable* are set ``enabled=False`` so
    they leave the registry entirely (e.g. a deprecated/unreachable tracker).
    """
    providers = dict(config.tracker.providers)
    for name in disable:
        if name in providers:
            providers[name] = providers[name].model_copy(update={"enabled": False})
    targets = trackers or [n for n, p in providers.items() if p.enabled]
    for name in targets:
        if name not in providers:
            print(f"  ! unknown tracker '{name}' — skipping", file=sys.stderr)
            continue
        providers[name] = providers[name].model_copy(update={"cross_seed": True})
    new_tracker = config.tracker.model_copy(update={"providers": providers})
    new_cross_seed = config.cross_seed.model_copy(update={"enabled": True})
    return config.model_copy(update={"tracker": new_tracker, "cross_seed": new_cross_seed})


# ── read-only torrent-client proxy ──────────────────────────────────────────


class ReadOnlyTorrentClient:
    """Delegates reads to the real qBit client; refuses + logs every write.

    ``inject`` logs the would-inject decision and raises :class:`ApiError` so
    the real ``CrossSeedService.check`` treats it as a per-candidate
    ``inject_failed`` and moves on — the entire real search/fetch/parse/match
    path runs, but nothing is ever written to qBittorrent.
    """

    def __init__(self, real: Any) -> None:
        self._real = real
        self.would_inject: list[tuple[str, str]] = []  # (info_hash, save_path)

    def __getattr__(self, name: str) -> Any:  # reads → pass through
        return getattr(self._real, name)

    def inject(self, torrent_bytes: bytes, *, save_path: str, recheck: bool = True, paused: bool = True) -> str:
        from personalscraper.api.torrent._base import _bencode_info_hash

        info_hash = _bencode_info_hash(torrent_bytes)
        self.would_inject.append((info_hash, save_path))
        print(f"    +-- DRY-RUN would inject {info_hash[:16]} at {save_path}")
        raise ApiError(provider="qbittorrent", http_status=0, message="dry-run: inject refused")

    def add_tags(self, info_hash: str, tags: Any) -> None:
        print(f"    |   DRY-RUN would add_tags {list(tags)} to {info_hash[:16]}")

    def remove_tags(self, info_hash: str, tags: Any) -> None:
        print(f"    |   DRY-RUN would remove_tags {list(tags)} from {info_hash[:16]}")

    def resume(self, info_hash: str) -> None:
        print(f"    |   DRY-RUN would resume {info_hash[:16]}")

    def delete(self, info_hash: str, *, delete_files: bool = False) -> None:
        print(f"    +-- DRY-RUN would delete {info_hash[:16]} (delete_files={delete_files})")


# ── shared builders ─────────────────────────────────────────────────────────


def _build_app(config: Config) -> AppContext:
    """Build the real AppContext (connects qBittorrent once, wires the registry)."""
    return _build_app_context(config, Settings(), build_torrent_client=True)


def _close(app: AppContext) -> None:
    try:
        app.provider_registry.close()
    except Exception:  # noqa: BLE001
        pass
    if app.acquire is not None:
        try:
            app.acquire.close()
        except Exception:  # noqa: BLE001
            pass


def _pick_torrent(client: Any, wanted_hash: str | None) -> Any:
    completed = client.get_completed()
    if wanted_hash:
        matches = [t for t in completed if t.hash.lower().startswith(wanted_hash.lower())]
        if not matches:
            sys.exit(f"No completed torrent matching hash prefix '{wanted_hash}'.")
        return matches[0]
    return max(completed, key=lambda t: _safe_file_count(client, t.hash))


def _safe_file_count(client: Any, info_hash: str) -> int:
    try:
        return len(client.list_files(info_hash))
    except Exception:  # noqa: BLE001
        return 0


# ── stages ──────────────────────────────────────────────────────────────────


def stage_env(config: Config) -> None:
    _h1("STAGE env - config + connectivity + acquire.db (read-only)")
    _kv("watch.enabled", config.watch.enabled)
    _kv("cross_seed.enabled", config.cross_seed.enabled)
    _kv("cross_seed.verify_timeout_s", config.cross_seed.verify_timeout_s)
    _kv("cross_seed.max_searches/day", config.cross_seed.max_searches_per_day)
    _kv("torrent.active", config.torrent.active)
    for name, p in config.tracker.providers.items():
        _kv(f"tracker[{name}]", f"enabled={p.enabled} cross_seed={getattr(p, 'cross_seed', 'NA')}")

    app = _build_app(config)
    try:
        completed = app.torrent_client.get_completed()
        _kv("qBit completed torrents", len(completed))
        _kv("already SEED_PURE-tagged", sum(1 for t in completed if SEED_PURE in (t.tags or [])))
        _kv("acquire.cross_seed service", "built" if (app.acquire and app.acquire.cross_seed) else "None")
    finally:
        _close(app)

    db_path = Path(config.acquire.db_path)
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            for tbl in ("cross_seed_history", "cross_seed_quota", "seed_obligation"):
                try:
                    n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]  # noqa: S608
                    _kv(f"acquire.db {tbl}", f"{n} rows")
                except sqlite3.OperationalError:
                    _kv(f"acquire.db {tbl}", "(table absent)")
        finally:
            conn.close()
    else:
        _kv("acquire.db", "(not yet created)")


def stage_layout(config: Config, wanted_hash: str | None) -> None:
    _h1("STAGE layout - real local TorrentLayout + path-frame normalization (read-only)")
    app = _build_app(config)
    try:
        client = app.torrent_client
        t = _pick_torrent(client, wanted_hash)
        _kv("torrent", t.name)
        _kv("hash", t.hash)
        _kv("save_path", t.save_path)

        raw = client.list_files(t.hash)
        props = client.properties(t.hash)
        print("\n  RAW qBittorrent list_files (root-prefixed for multi-file):")
        for name, size in raw[:6]:
            print(f"    {size:>15,}  {name}")
        if len(raw) > 6:
            print(f"    ... {len(raw)} files total")
        _kv("\n  piece_size", props.get("piece_size"))

        norm, layout_name = _normalize_qbit_files(raw, t.name)
        print("\n  NORMALIZED to candidate frame (root stripped = what structural_match compares):")
        _kv("  layout name", layout_name)
        for name, size in norm[:6]:
            print(f"    {size:>15,}  {name}")
        if len(raw) > 1 and "/" in raw[0][0]:
            stripped = not any("/" in p for p, _ in norm)
            print(f"\n  [OK] multi-file root folder stripped from every path: {stripped}")
            print("       (before the cycle-1 fix, root-prefixed paths never matched a")
            print("        candidate .torrent's root-excluded paths -> no multi-file cross-seed)")
    finally:
        _close(app)


def stage_match(config: Config, wanted_hash: str | None, limit: int) -> None:
    _h1("STAGE match - REAL CrossSeedService.check() with READ-ONLY client")
    print("  (real search + fetch + parse + structural_match against live trackers;")
    print("   inject/tag/resume/delete refused. Only benign cross_seed_history writes.)")

    app = _build_app(config)
    try:
        if app.acquire is None:
            sys.exit("acquire context is None.")
        ro_client = ReadOnlyTorrentClient(app.torrent_client)
        service = CrossSeedService(
            registry=app.acquire.tracker_registry,
            lister=ro_client,
            injector=ro_client,
            controller=ro_client,
            tagger=ro_client,
            store=app.acquire.store,
            config=config,
            event_bus=app.event_bus,
        )

        completed = app.torrent_client.get_completed()
        if wanted_hash:
            targets = [t for t in completed if t.hash.lower().startswith(wanted_hash.lower())]
        else:
            targets = [t for t in completed if SEED_PURE not in (t.tags or [])][:limit]
        if not targets:
            sys.exit("No target torrents to check.")

        for t in targets:
            print(f"\n  > {t.name[:64]}  ({t.hash[:12]})")
            before = len(ro_client.would_inject)
            try:
                result = service.check(t.hash)
            except Exception as e:  # noqa: BLE001 - harness must survive one bad torrent
                print(f"    x check() raised {type(e).__name__}: {e}")
                continue
            matched = len(ro_client.would_inject) - before
            if result.skipped:
                print(f"    - skipped: {result.skip_reason}")
            elif matched:
                print(f"    [MATCH] {matched} candidate(s) structurally matched (would inject for real)")
            elif result.rejected:
                reasons: dict[str, int] = {}
                for _h, _tracker, reason in result.rejected:
                    reasons[reason] = reasons.get(reason, 0) + 1
                print(f"    . no match - {len(result.rejected)} candidate(s) rejected: {reasons}")
            else:
                print("    . no candidates found on the gated trackers")
    finally:
        _close(app)


def stage_watch_decide(config: Config) -> None:
    _h1("STAGE watch-decide - WatcherService.evaluate() on the live snapshot (read-only)")
    app = _build_app(config)
    try:
        completed = app.torrent_client.get_completed()
        completed_hashes = frozenset(t.hash for t in completed)
        seed_pure_hashes = frozenset(t.hash for t in completed if SEED_PURE in (t.tags or []))

        tracker = IngestTracker(tracker_path=Path(config.paths.data_dir) / "ingested_torrents.json")
        try:
            ingested = frozenset(tracker.load().keys())
        except Exception:  # noqa: BLE001
            ingested = frozenset()

        svc = WatcherService(config.watch)
        new_completions = completed_hashes - ingested - seed_pure_hashes
        inp = WatcherInput(
            completed_hashes=completed_hashes,
            ingested_hashes=ingested,
            seed_pure_hashes=seed_pure_hashes,
            sentinel_present=(Path(config.paths.data_dir) / "watch.trigger").exists(),
            pipeline_lock_held=False,
            now=time.time(),
        )
        out = svc.evaluate(inp, WatcherState())

        _kv("watch.enabled", config.watch.enabled)
        _kv("completed torrents", len(completed_hashes))
        _kv("ingested (tracked)", len(ingested))
        _kv("SEED_PURE-tagged", len(seed_pure_hashes))
        _kv("NEW completions (work)", len(new_completions))
        _kv("=> DECISION (live config)", out.decision.name)
        if not config.watch.enabled:
            # Show what the daemon WOULD decide if the kill-switch were on.
            enabled_watch = config.watch.model_copy(update={"enabled": True})
            out = WatcherService(enabled_watch).evaluate(inp, WatcherState())
            _kv("=> DECISION (if enabled)", out.decision.name)
        if out.decision == WatcherDecision.FIRE_CROSS_SEED:
            _kv("  cross-seed hashes", [h[:12] for h in out.cross_seed_hashes[:6]])
        elif out.decision == WatcherDecision.FIRE_RUN:
            _kv("  run reason", out.run_reason)
        if not config.watch.enabled:
            print("\n  (config.watch.enabled=False -> the real daemon returns IDLE and exits.")
            print("   The 'if enabled' line shows what it would do on this live snapshot.)")
    finally:
        _close(app)


def stage_inject(config: Config, wanted_hash: str | None, confirm: bool) -> None:
    _h1("STAGE inject - REAL cross-seed injection (WRITES to qBittorrent + acquire.db)")
    if not confirm:
        sys.exit("Refusing to inject without --confirm-inject. Run `match` first to see candidates.")
    if not wanted_hash:
        sys.exit("--hash is required for inject.")

    app = _build_app(config)
    try:
        if app.acquire is None or app.acquire.cross_seed is None:
            sys.exit("cross_seed service unavailable (client lacks TorrentInjector capability?).")
        service = app.acquire.cross_seed
        t = _pick_torrent(app.torrent_client, wanted_hash)
        print(f"  injecting cross-seeds for: {t.name}  ({t.hash})")
        result = service.check(t.hash)
        _kv("injected", result.injected)
        _kv("rejected", [(h[:10], tr, rn) for h, tr, rn in result.rejected])
        _kv("skipped", result.skipped)
        if result.injected:
            print("\n  [!] CLEANUP: to undo, remove the injected torrents above in qBittorrent")
            print("      (KEEP the files - they are the shared source data), then if needed:")
            print(f"      sqlite3 {config.acquire.db_path} \\")
            print("        \"DELETE FROM seed_obligation WHERE info_hash IN ('<injected-hash>');\"")
    finally:
        _close(app)


# ── entrypoint ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual real-environment E2E for watch-seed.")
    parser.add_argument("stage", choices=["env", "layout", "match", "watch-decide", "inject"])
    parser.add_argument("--hash", dest="hash_prefix", default=None, help="target torrent hash prefix")
    parser.add_argument(
        "--enable-tracker",
        dest="trackers",
        action="append",
        default=[],
        help="gate cross_seed ON for this tracker (in-memory; repeatable). Empty = all enabled.",
    )
    parser.add_argument(
        "--disable-tracker",
        dest="disable",
        action="append",
        default=[],
        help="drop this tracker from the registry (in-memory; e.g. a deprecated/unreachable one)",
    )
    parser.add_argument("--limit", type=int, default=5, help="max torrents to check in `match`")
    parser.add_argument("--confirm-inject", action="store_true", help="required for the real `inject` stage")
    args = parser.parse_args()

    base = load_config(resolve_config_path())

    if args.stage == "env":
        stage_env(base)
    elif args.stage == "layout":
        stage_layout(base, args.hash_prefix)
    elif args.stage == "match":
        stage_match(_enable_cross_seed(base, args.trackers, args.disable), args.hash_prefix, args.limit)
    elif args.stage == "watch-decide":
        stage_watch_decide(base)
    elif args.stage == "inject":
        stage_inject(_enable_cross_seed(base, args.trackers, args.disable), args.hash_prefix, args.confirm_inject)


if __name__ == "__main__":
    main()
