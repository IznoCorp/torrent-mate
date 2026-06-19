# Phase 04 — Productionize torr9 (added to PR #209 by operator decision 2026-06-19)

Four additions, grounded in a live API probe + a codebase investigation. Implement in the
ordered tasks below (Cocktail A: one commit per task, keep `make check` green at each).
Reference patterns live in `personalscraper/api/metadata/tvdb.py` (lazy transport) and
`personalscraper/api/tracker/lacale.py` / `c411.py` (api-key trackers).

**Operator decisions (locked):**

- Seeders enrichment: **top-K = 10, ON by default** (config flag), `min_seeders` unchanged.
- Download fallback: **real `.torrent` via `GET /api/v1/torrents/{id}/download`** (Bearer, bytes).

**Live-probed facts (authoritative):**

- `GET /api/v1/torrents/{id}/download` + Bearer → `200 application/x-bittorrent` (valid bencode .torrent). This is the real .torrent endpoint.
- `torrent_file_url` is DEAD: 404 at every host/auth, its hash ≠ info_hash, and the **detail** payload doesn't even return it. Do NOT use it.
- `magnet_link` is always present + auth-free (the preferred primary download, unchanged).
- Detail `GET /torrents/{id}` carries real `seeders`/`leechers` (e.g. id 305292 → seeders=1, leechers=4).

**Investigation facts (authoritative):**

- `config/ranking.json5` sets `min_seeders: 1` → `rank()` (`_ranking.py:64-66`) DROPS every torr9 result (seeders=0) BEFORE scoring → torr9 currently wins NO grab (`orchestrator.py:231-235` → `no_seeders`). Enrichment is what makes torr9 viable.
- `config/` is gitignored but `config/tracker.json5` is force-added (tracked); CI never loads it (no tracked master `config.json5` → `ConfigNotFoundError`; the only real-config consumer is e2e, deselected). lacale+c411 already ship `enabled:true` there. So enabling torr9 is **CI-safe**; it only fail-louds LOCALLY if creds absent (they are in `.env`).
- `resolve_source` (`_fetch.py:234-300`): magnet `download_url` → `TorrentSource.from_magnet` (no transport); else → `fetch_torrent_source(url, transports[provider])` → `transport.get_bytes(url)`. `get_bytes` (`_http.py:139-180`) joins a relative `url` onto `policy.base_url` and uses the authed session (`policy.auth.apply` at init). So `download_url = "/api/v1/torrents/{id}/download"` is fetched WITH Bearer via the provider transport.
- `TrackerRegistry.transports()` (`_registry.py:185-201`) does `getattr(client, "_transport", None)` per client — for torr9's lazy `_transport` PROPERTY this triggers a bootstrap login and PROPAGATES a login failure (breaks the grab seam). Must be made resilient.
- `TrackerResult` (`_base.py:57`) is a **mutable** `@dataclass` (`r.seeders = x` works; no `replace` needed).
- `TorrentDetailsProvider` Protocol (`_contracts.py:87-95`): `get_details(self, torrent_id: str) -> TrackerResult`.
- `TrackerProviderConfig(_StrictModel)` (`conf/models/api_config.py:227-236`): has `enabled` + `economy`; forbids extra keys → new flags MUST be declared on the model.

---

## Task 1 — Generic multi-cred construction protocol (`from_env`), replacing the `getattr(build_from_env)` hook

Files: `personalscraper/api/tracker/_contracts.py`, `lacale.py`, `c411.py`, `torr9.py`, `_factory.py`, `tests/unit/test_tracker_factory.py`, `tests/integration/api/tracker/test_composition_root.py`.

1a. In `_contracts.py`, add a `@runtime_checkable` Protocol (next to the others):

```python
@runtime_checkable
class TrackerConstructible(Protocol):
    """Capability — construct a tracker client from resolved env credentials.

    The factory dispatches construction UNIFORMLY through ``from_env`` (no
    provider-name literal, no cred-style branch). api-key trackers build an
    HttpTransport from ``policy(env[required[0]])``; login-style trackers
    (torr9) self-build their authed transport lazily and read extra options
    off ``provider_cfg``.
    """

    @classmethod
    def from_env(
        cls,
        *,
        env: "Mapping[str, str]",
        event_bus: "EventBus",
        required: list[str],
        provider_cfg: "TrackerProviderConfig",
    ) -> "TorrentSearchable": ...
```

Add the needed imports/`TYPE_CHECKING` entries (`Mapping`, `EventBus`, `TrackerProviderConfig`). Export `TrackerConstructible` in `__all__`.

1b. `lacale.py` — add (api-key shape):

```python
    @classmethod
    def from_env(cls, *, env, event_bus, required, provider_cfg):
        """Build LaCaleClient from its single API key (the uniform factory contract)."""
        del provider_cfg  # api-key tracker: no extra construction options
        api_key = env.get(required[0], "") if required else ""
        transport = HttpTransport(cls.policy(api_key), event_bus=event_bus)
        return cls(transport)
```

Add the `HttpTransport` import if not already a runtime import. Mirror EXACTLY in `c411.py` (use `C411Client`).

1c. `torr9.py` — RENAME `build_from_env` → `from_env` with the uniform signature; wire the enrich flags (Task 3) from `provider_cfg`:

```python
    @classmethod
    def from_env(cls, *, env, event_bus, required, provider_cfg):
        del required  # torr9 reads its own cred names from REQUIRED_CREDS
        return cls(
            username=env.get(cls.REQUIRED_CREDS[0], ""),
            password=env.get(cls.REQUIRED_CREDS[1], ""),
            event_bus=event_bus,
            enrich_seeders=getattr(provider_cfg, "enrich_seeders", True),
            enrich_seeders_top_k=getattr(provider_cfg, "enrich_seeders_top_k", 10),
        )
```

(`__init__` gains `enrich_seeders: bool = True, enrich_seeders_top_k: int = 10` — Task 3.)

1d. `_factory.py` — replace the `getattr(client_cls, "build_from_env", None)` if/else block with ONE uniform call (no name literal, no cred-style branch, no `# type: ignore` on policy):

```python
        client_cls = _resolve_tracker_class(name)
        # Uniform construction contract (TrackerConstructible.from_env): every
        # tracker builds itself from resolved env creds + its provider config.
        client = cast("type[TrackerConstructible]", client_cls).from_env(
            env=env, event_bus=event_bus, required=required, provider_cfg=provider_cfg,
        )
```

Import `TrackerConstructible` + `cast`. Keep the `isinstance(client, TorrentSearchable)` check. If mypy still complains about the classmethod on the cast type, prefer `getattr(client_cls, "from_env")(...)` with a narrow local annotation over scattering ignores — minimize ignores.

1e. Tests: in `tests/unit/test_tracker_factory.py`, the stub clients (`_StubSearchable`/`_NotSearchable` etc.) now need a `from_env` classmethod (the factory calls it uniformly). Add a minimal `from_env` to each stub that returns an instance. In `test_composition_root.py`, the existing `test_torr9_built_when_creds_present` already exercises the path — confirm it still passes. Add a test asserting all three real clients satisfy `isinstance(<client or class>, ...)` / expose `from_env` (a `TrackerConstructible` conformance check).

GATE: `python -m pytest tests/unit/test_tracker_factory.py tests/integration/api/tracker/test_composition_root.py tests/unit/test_torr9_client.py -q` green; `make lint` green.

COMMIT: `refactor(tracker): uniform from_env construction protocol (replaces torr9 build_from_env hook)`

---

## Task 2 — Enable torr9 in config

File: `config/tracker.json5` ONLY (NOT config.example/ — it stays all-disabled as the template).

2a. Flip `torr9: { enabled: false, economy: {...} }` → `enabled: true` (keep the economy block).

2b. Verify locally (do NOT commit if this fails): `TORR9_USERNAME`/`TORR9_PASSWORD` are in `.env`; confirm a real registry build boots:

```bash
python -c "
import os
from personalscraper.api.tracker._factory import build_tracker_registry
# build with os.environ — must NOT raise TrackerConfigError for torr9
"  # or run a real personalscraper acquire-context command that boots the registry
```

If creds are present it boots; if the operator removed them it will fail-loud locally (expected). This does NOT affect CI (CI never loads config/tracker.json5).

COMMIT: `feat(torr9): enable torr9 in config/tracker.json5 (creds in .env)`

---

## Task 3 — Seeders enrichment via TorrentDetailsProvider (top-K=10, default on)

Files: `conf/models/api_config.py`, `personalscraper/api/tracker/torr9.py`, tests.

3a. `conf/models/api_config.py` — add to `TrackerProviderConfig` (declared because `_StrictModel` forbids extra keys):

```python
    enrich_seeders: bool = True
    enrich_seeders_top_k: int = 10
```

Document both in the class docstring. (config.example/tracker.json5 may show them commented for discoverability — optional; do NOT enable in the example.)

3b. `torr9.py`:

- `__init__` gains `enrich_seeders: bool = True, enrich_seeders_top_k: int = 10`; store as `self._enrich_seeders`, `self._enrich_top_k`.
- Add `TorrentDetailsProvider` to the class bases: `class Torr9Client(TorrentSearchable, CategoryListable, FreeleechAware, TorrentDetailsProvider)`. Import it from `_contracts`.
- Implement `get_details`:

```python
    def get_details(self, torrent_id: str) -> TrackerResult:
        """Fetch the per-torrent detail (GET /torrents/{id}) as a TrackerResult.

        Unlike the search payload, the detail carries real seeders/leechers. Used
        to enrich search results' swarm health for ranking. Reuses _authed_get
        (lazy login + re-login on 401) and wrap_parser_drift.
        """
        raw = self._authed_get(f"/api/v1/torrents/{torrent_id}")
        return wrap_parser_drift(self.provider_name, lambda: self._parse_item(cast("dict[str, Any]", raw)))
```

NOTE on the shared `_parse_item` (used by BOTH search items and get_details' detail item):

- **seeders/leechers**: currently hardcoded `0`. Refactor to read them when present: `seeders=int(item.get("seeders", 0) or 0)`, `leechers=int(item.get("leechers", 0) or 0)`. Search items lack the keys → 0 (search golden tests stay green); detail items have them → real values. (int() runs inside wrap_parser_drift so a bad type drifts.)
- **category**: the SEARCH payload has numeric `category_id`; the DETAIL payload has NO `category_id` but a human `category_name` label instead. Make `_parse_item` handle both: `category = _CATEGORY_MAP.get(int(category_id))` when `category_id` is numeric, ELSE `item.get("category_name")` (detail's label, e.g. "Séries TV"). This keeps search golden tests green (id 5 → "Séries TV") AND makes get_details return a real category from the detail's `category_name`.
- Everything else (title/size/info_hash/magnet/is_freeleech/upload_date) is present in both payloads and parses unchanged.

- Enrichment in `search()` — AFTER `results = wrap_parser_drift(...)`, BEFORE return:

```python
        if self._enrich_seeders and results:
            for r in results[: self._enrich_top_k]:
                try:
                    detail = self.get_details(r.tracker_id)
                    r.seeders = detail.seeders
                    r.leechers = detail.leechers
                except ApiError as exc:  # fail-soft: leave seeders=0, never abort search
                    log.warning("torr9_enrich_failed", tracker_id=r.tracker_id, error=str(exc))
        return results
```

(TrackerResult is mutable — direct assignment is fine.) Enrichment is fail-soft per result so a detail error or circuit trip never kills the search.

3c. Tests (`tests/unit/test_torr9_client.py` + capabilities):

- `get_details` golden test from `torr9_detail.json`: asserts `seeders == 1`, `leechers == 4`, title/category from the real detail.
- search-enrich test: mock `get_details` (or the transport) so the first K results get real seeders; assert results[:K] enriched, results[K:] stay 0, and `get_details` called ≤ K times.
- enrich-OFF test: `Torr9Client(..., enrich_seeders=False)` → search does NOT call get_details; all seeders=0.
- fail-soft test: `get_details` raises ApiError → search still returns results (seeders stay 0), warning logged.
- capabilities (`test_tracker_capabilities_composition.py`): assert `isinstance(_torr9(), TorrentDetailsProvider)`.

GATE: torr9 tests green; `make lint` green.

COMMIT: `feat(torr9): enrich top-K seeders from detail endpoint (TorrentDetailsProvider, default on)`

---

## Task 4 — Real `.torrent` download fallback + resilient transports() seam

Files: `personalscraper/api/tracker/torr9.py`, `personalscraper/api/tracker/_registry.py`, tests.

4a. `torr9.py` `_parse_item` — download_url: prefer the auth-free magnet; FALLBACK to the authed `.torrent` endpoint (NOT the dead torrent_file_url):

```python
        magnet = item.get("magnet_link")
        tracker_id = str(item.get("id", ""))
        if isinstance(magnet, str) and magnet.startswith("magnet:"):
            download_url: str = magnet
        else:
            # Magnet absent/malformed → fall back to the real .torrent endpoint
            # (GET /torrents/{id}/download, Bearer). resolve_source fetches it via
            # the provider's authed transport (get_bytes joins base_url + Bearer).
            log.warning("torr9_missing_magnet", tracker_id=tracker_id, title=title)
            download_url = f"/api/v1/torrents/{tracker_id}/download"
```

download_url is now NEVER None. Update the module docstring's download note accordingly (magnet primary; `/torrents/{id}/download` authed-bytes fallback; torrent_file_url unused/dead).

4b. `_registry.py` `transports()` — make resilient to a lazy `_transport` that triggers/raises on access (torr9's TVDB-lazy property):

```python
        result: dict[str, HttpTransport] = {}
        for name, client in self._trackers.items():
            try:
                transport = getattr(client, "_transport", None)
            except Exception as exc:  # noqa: BLE001  # a lazy login may fail; don't break the grab seam
                log.warning("tracker_transport_unavailable", tracker=name, error=str(exc))
                continue
            if transport is not None:
                result[name] = transport
        return result
```

(Add a module logger if absent: `from personalscraper.logger import get_logger`.) This both surfaces torr9's authed transport for the .torrent fallback AND prevents a torr9 login failure from killing every grab.

4c. Tests:

- `test_torr9_client.py`: `_parse_item` with NO magnet → `download_url == "/api/v1/torrents/{id}/download"` (REPLACES the cycle-1 `test_missing_magnet_leaves_download_url_none` — rename + update assertion; download_url is no longer None).
- A fetch test (unit, mocked): a torr9 TrackerResult with the `/download` download_url + a transports map `{"torr9": <mock transport whose get_bytes returns valid .torrent bytes>}` → `resolve_source(result, transports)` returns a `TorrentSource` (from the bytes). This pins the authed-bytes fallback wiring. (Use a real minimal bencoded .torrent or mock TorrentSource.from_file — inspect `_fetch.py` for the exact validation.)
- `test_registry.py` (or wherever TrackerRegistry is tested): a client whose `_transport` getter raises → `transports()` skips it (no exception), logs the warning. And a normal client is still included.

GATE: torr9 + registry + fetch tests green; `make lint` green.

COMMIT: `feat(torr9): .torrent download fallback via /download + resilient transports() seam`

---

## Task 5 — DESIGN reconciliation + full gate

5a. `docs/features/torr9/DESIGN.md`: reconcile — the construction now uses the uniform `from_env` (TrackerConstructible) contract (not the torr9-only `build_from_env` hook); seeders enrichment (top-K=10, default on, config flag) via the detail endpoint; download fallback is the real `.torrent` via `/torrents/{id}/download` (torrent_file_url is dead — note it); torr9 ships `enabled:true` in config/. Add ACC-9 (enrichment) + ACC-10 (download fallback) executable probes if it fits the SH-16 style.

5b. Full gate (must all hold):

- `make check` → lint + test (NNNN passed, 0 failed) + module-size + typed-api all green.
- `rg -t py 'build_from_env' personalscraper/ tests/` → no match (fully renamed to from_env).
- `python -c "from personalscraper.api.tracker.torr9 import Torr9Client; from personalscraper.api.tracker._contracts import TorrentDetailsProvider, TrackerConstructible; print(issubclass(Torr9Client, TorrentDetailsProvider))"` → True (or isinstance on an instance).
- `python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; print(TrackerProviderConfig().enrich_seeders, TrackerProviderConfig().enrich_seeders_top_k)"` → `True 10`.
- `grep -A2 'torr9:' config/tracker.json5 | grep enabled` → `enabled: true`.

DO NOT make a phase-gate/empty commit (the orchestrator does the milestone gate + IMPLEMENTATION.md). DO NOT push.

COMMIT: `docs(torr9): reconcile DESIGN for enrich + from_env + .torrent download + enable`
