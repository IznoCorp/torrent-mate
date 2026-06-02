# Design — RP1: Torrent Write Capability (`torrent-write`)

> ROADMAP item **RP1** (Vague 1, `[P1, prérequis]`). Keystone of the acquisition epic:
> unblocks Orchestration, Follow, Ratio, Watcher, Trackers.
> Grounded against the code on **2026-06-02** via a multi-agent footprint survey.

## 1. Purpose

The torrent-client family in `personalscraper/api/torrent/` is today strictly **read /
control**: it can list, inspect, check seed-state, pause, resume and delete an _existing_
torrent — but it **cannot add one**, and the client-side item model carries a `category`
but no `tags`.

RP1 surfaces a **write capability** on the family so downstream acquisition features can
programmatically **add** a torrent (from `.torrent` bytes or a magnet URI) with a
**category + tags**, and **apply transfer limits** where the client supports them. RP1
delivers three things:

1. the **interface** (new atomic capability Protocols + value objects),
2. the **implementations** on both clients (qBittorrent, Transmission),
3. **boot-wiring** of the torrent client into the composition root with a **capability
   fail-fast**.

## 2. Non-goals

- **The `.torrent` fetch+POST plumbing** (authenticated download of the `.torrent`, the
  magnet exception, the routable 401) — that is **RP1a**. RP1 only defines the `add`
  interface so it _accommodates_ file-bytes vs magnet-url, and guarantees that a 401 from
  the add POST itself stays observable.
- **Limit policy** (ratio targets, bandwidth caps, seedtime rules) — that is RP2 / Ratio
  (C1–C3) / Seed-Safety (O4). RP1 ships only the _mechanism_ to set limits.
- Multi-tracker orchestration, dedup, ranking (RP5b and beyond).
- Removing or reworking the existing read/control protocols.

## 3. Grounded current state (2026-06-02)

| Area            | Reality                                                                                                                                                                                                                                                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Family contract | 5 atomic `@runtime_checkable` Protocols in `api/torrent/_contracts.py`: `TorrentLister`, `TorrentInspector`, `AuthenticatedClient`, `TorrentStateInspector`, `TorrentController` — 8 methods, all read/control.                                                                                                          |
| Item model      | `TorrentItem` `@dataclass` (mutable) in `api/torrent/_base.py` — 9 fields incl. `category: str \| None`, **no `tags`**.                                                                                                                                                                                                  |
| Native libs     | `qbittorrentapi.torrents_add()` and `transmission_rpc.add_torrent()` **already support add** — `tests/e2e/setup_torrents.py` calls `torrents_add`. RP1 is a **wrapping/surfacing** task, not from-scratch.                                                                                                               |
| Wiring          | Torrent client is **not boot-wired**. Built lazily per-step by `build_active_torrent_client()` (`api/torrent/_factory.py`) at `ingest/ingest.py:296` and `commands/pipeline.py:643`, each with an inline `QBitClient(...)` fallback. **Not** in `AppContext`. Failures are per-step `StepReport` errors, not boot-fatal. |
| Transport       | `HttpTransport` (`api/transport/_http.py`) is **JSON-only** (`json=data` hardcoded, no `files=`). Multipart `.torrent` upload **cannot** go through it → add delegates to the **native client objects**.                                                                                                                 |
| Capability gap  | qBit `torrents_add` does add+category+tags+limits (`upLimit/dlLimit/ratioLimit/seedingTimeLimit`) in one call. Transmission `torrent-add` has only `labels[]` + `peer_limit` — **no ratio/bandwidth/seedtime**. Limits are **not portable**.                                                                             |

### 3.1 ROADMAP corrections (incohérences actées)

The ROADMAP RP1 text (2026-06-01) diverges from the code; the design adopts the corrected
reading:

1. _"the client cannot add"_ — false at the lib level; it can, it is just **not exposed**.
2. _"add + categorize + limit (symmetric)"_ — **asymmetric**: Transmission cannot set
   ratio/bandwidth/seedtime. Limits are modelled as a **separate optional capability**.
3. _"Transmission must refuse to start if it cannot add"_ — Transmission **can** add (via
   `labels`), and there is **no boot phase** for the torrent client today. RP1 _creates_
   that boot phase (AppContext promotion) and makes the fail-fast a **capability gate**
   (refuse a client that cannot compose `TorrentAdder`), not a Transmission-specific block.
4. `tags` belongs on the **client-side `TorrentItem`** (daemon view), not the tracker
   search-result model (`TorrentResult`).
5. _"Pin Q4 here"_ — Q4's multipart plumbing is genuinely a different layer (native libs,
   not `HttpTransport`) → correctly **RP1a**. RP1 only pins the _interface shape_.

## 4. Frozen decisions (brainstorm 2026-06-02)

| #                                      | Decision                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1 — API shape**                     | A single method `add(source, *, category=None, tags=(), paused=False, limits=None) -> str` on a new atomic Protocol `TorrentAdder`. The source is a discriminated value object `TorrentSource{magnet \| file_bytes}` (exactly one set). Maps cleanly to Transmission's unified `torrent=` param and qBit's split `urls=`/`torrent_files=`.                                                  |
| **D2 — Limits as separate capability** | `TorrentLimiter` is a **separate** atomic `@runtime_checkable` Protocol (`apply_limits(info_hash, limits)`), composed by **qBit only**. `TorrentAdder` is composed by **both** clients (Transmission adds via `labels`).                                                                                                                                                                    |
| **D3 — Fail-fast placement**           | **Promote** the torrent client into `AppContext` and validate at boot in `_build_app_context()` (true boot fail-fast via `RegistryConfigError`), mirroring the metadata `ProviderRegistry`.                                                                                                                                                                                                 |
| **D4 — `tags` type**                   | `TorrentItem.tags: list[str] = field(default_factory=list)` (no `None`/empty ambiguity). The dataclass stays **mutable** (no frozen/slots churn).                                                                                                                                                                                                                                           |
| **D5 — Transmission round-trip**       | Write `labels = [category, *tags]` (deduped, category first). Read `category = labels[0] if labels else None`, `tags = labels[1:]`. Stable round-trip, no category duplication.                                                                                                                                                                                                             |
| **D6 — Return value**                  | `add(...) -> str` returns the **info_hash**, derived from the source (magnet → parse `xt=urn:btih:`; bytes → bencode infohash). Avoids qBit's missing hash echo and gives Watcher/Follow a handle. Transmission's echoed `hashString` is used as a cross-check.                                                                                                                             |
| **D7 — Idempotence**                   | A duplicate add is **success** (no-op): qBit `Fails.`-on-duplicate and Transmission `torrent-duplicate` both map to "already present → return the existing info_hash". RP1 unblocks re-adding consumers (Watcher/Follow).                                                                                                                                                                   |
| **D8 — Limits reconciliation (N2)**    | `add()` accepts `limits` (per D1), but it is honored **only** by a client also composing `TorrentLimiter`. Passing `limits` to a client without `TorrentLimiter` (Transmission) **raises** a clear error — **never a silent ignore** (project no-silent-failure norm). Callers gate via `isinstance(client, TorrentLimiter)`. qBit applies limits inline in the single `torrents_add` call. |
| **D9 — Boot validation scope (N1)**    | Validate **only when a torrent client is configured/enabled**: an _enabled-but-incapable_ client → boot fail-fast; _no torrent client configured_ → no error (read-only commands like `info` / `library` queries must not break on an absent torrent config).                                                                                                                               |
| **D10 — Config (N3)**                  | **No** limit defaults added to config now (policy = RP2). `TorrentClientEntry` gains a `save_path` field **only if** `add` needs a default save path; otherwise config is untouched.                                                                                                                                                                                                        |

## 5. Components

### 5.1 Value objects (new, `api/torrent/_base.py`)

- **`TorrentSource`** — frozen dataclass; exactly one of `magnet: str | None` /
  `file_bytes: bytes | None` (validated in `__post_init__`, else `ValueError`).
  Classmethods `from_magnet(uri)` / `from_file(data)`. Property/cached `info_hash: str`
  (magnet → parse `btih`; bytes → minimal stdlib bencode infohash helper, **no new heavy
  dependency**).
- **`TorrentLimits`** — frozen dataclass; `ratio: float | None`,
  `seed_time_minutes: int | None`, `up_bytes_per_s: int | None`,
  `down_bytes_per_s: int | None` (all optional; all-`None` = no-op).

### 5.2 New atomic Protocols (`api/torrent/_contracts.py`)

```python
@runtime_checkable
class TorrentAdder(Protocol):
    def add(self, source: TorrentSource, *, category: str | None = None,
            tags: Sequence[str] = (), paused: bool = False,
            limits: TorrentLimits | None = None) -> str: ...

@runtime_checkable
class TorrentLimiter(Protocol):
    def apply_limits(self, info_hash: str, limits: TorrentLimits) -> None: ...
```

`TorrentAdder` → composed by `QBitClient` **and** `TransmissionClient`.
`TorrentLimiter` → composed by `QBitClient` **only**. Update `__all__` and the family
docstring/legacy-mapping table.

### 5.3 Model change (`api/torrent/_base.py`)

Add `tags: list[str] = field(default_factory=list)` after `category` on `TorrentItem`.
Update both mappers:

- qBit `_torrent_item()` (`qbittorrent.py:259`): `tags = [t for t in t.tags.split(",") if t]`.
- Transmission `_torrent_item()` (`transmission.py:259`): `category = labels[0] if labels
else None`, `tags = list(labels[1:])` (per D5; ensure the request asks for `labels`,
  already at `transmission.py:104`).

### 5.4 Client implementations

- **`QBitClient`** — `add` → `self._client.torrents_add(urls=source.magnet |
torrent_files=source.file_bytes, category=category, tags=list(tags),
is_paused=paused, **_limit_kwargs(limits))`; returns `source.info_hash`; idempotent
  (D7); 401 → `ApiError` (observable). `apply_limits` → `torrents_set_*` /
  share-limit calls. Composes `TorrentAdder` + `TorrentLimiter`.
- **`TransmissionClient`** — `add` → `self._client.add_torrent(torrent=source.magnet or
source.file_bytes, labels=_labels(category, tags), paused=paused)`; returns the echoed
  `hashString` (cross-checked vs `source.info_hash`); idempotent (D7); **raises**
  `UnsupportedCapabilityError` if `limits` is not `None` (D8). Composes `TorrentAdder`
  only.

### 5.5 Boot-wiring + fail-fast (D3, D9)

- `AppContext` (`core/app_context.py`) gains `torrent_client: TorrentClient | None`.
- `_build_app_context()` (`cli_helpers/__init__.py`) resolves the active client via
  `build_active_torrent_client(cfg.torrent, os.environ)` **when a torrent client is
  configured/enabled**, asserts it composes `TorrentAdder`, else raises
  `RegistryConfigError` (or a torrent `ConfigIssue` with a closed-enum code) at boot.
- The two lazy sites (`ingest/ingest.py:296`, `commands/pipeline.py:643`) read
  `ctx.torrent_client`; the inline `QBitClient(...)` fallbacks are removed.

### 5.6 Errors (`api/torrent/_errors.py`)

- New `UnsupportedCapabilityError` (or reuse `ApiError` with a capability code) for D8.
- Optional `TorrentAddError` tuple alongside `TORRENT_CONNECT_ERRORS` /
  `TORRENT_LISTING_ERRORS`. 401 surfaces as `ApiError(http_status=401)`.

### 5.7 Config (D10, `conf/models/api_config.py`)

`TorrentClientEntry` (currently `enabled/host/port`) gains `save_path: str | None = None`
**only if** `add` requires a default; **no** limit defaults (RP2 owns policy).

## 6. Data flow

```
RP1a (fetch .torrent / magnet, auth) ──▶ TorrentSource{file_bytes|magnet}
                                              │
future consumer (RP5b orchestrator / Watcher / Follow)
   ctx.torrent_client.add(source, category=…, tags=[…], limits=… if Limiter)
                                              │
                              ┌───────────────┴───────────────┐
                         QBitClient                     TransmissionClient
                  torrents_add(+category,tags,           add_torrent(labels=[cat,*tags])
                   limits inline)                         (raises if limits)
                                              │
                                       returns info_hash
```

## 7. Testing

Unit (mirroring `tests/unit/test_qbittorrent.py`, `test_transmission_client.py`,
`test_torrent_capabilities_composition.py`, `test_torrent_factory.py`):

- qBit: `add` (magnet + file), tags mapping, limits applied inline, idempotent duplicate,
  401 observable.
- Transmission: `add` (magnet + bytes), `labels` round-trip (D5), tags mapping,
  `limits` → raises, idempotent duplicate.
- Capability composition: `isinstance(QBitClient, TorrentAdder/TorrentLimiter)` True;
  `isinstance(TransmissionClient, TorrentAdder)` True, `TorrentLimiter` **False**.
- Boot fail-fast: enabled-but-incapable active client → `RegistryConfigError`; no client
  configured → no error (D9).
- `TorrentSource`: exactly-one validation, `info_hash` derivation (magnet + bytes).
- Factory: union still type-narrows the new capabilities.

Follow the project's design-contract pairing convention (`Design:` / `Contract:`) where the
repo already pairs them for the torrent family.

## 8. Acceptance (design-level; full executable `ACCEPTANCE.md` produced at plan time)

Each criterion becomes an executable shell command + expected output in `ACCEPTANCE.md`:

- `python -c "from personalscraper.api.torrent import TorrentAdder, TorrentLimiter, TorrentSource, TorrentLimits"` → exit 0.
- Capability composition (one-liners): a built `QBitClient` satisfies both `isinstance(c, TorrentAdder)` and `isinstance(c, TorrentLimiter)`; a built `TransmissionClient` satisfies `isinstance(c, TorrentAdder)` but **not** `isinstance(c, TorrentLimiter)` → asserts pass.
- A misconfigured (enabled, incapable) torrent client makes `_build_app_context()` raise `RegistryConfigError` → asserted in tests.
- `TorrentItem` exposes `tags: list[str]` defaulting to `[]` → asserted.
- `make check` green; `python -c "import personalscraper"` smoke OK.

## 9. Open items carried to planning

- Exact `info_hash` bencode helper (stdlib-only) shape and its unit coverage (D6).
- Whether `save_path` is actually needed on `TorrentClientEntry` (D10) — confirm during
  the implementation of qBit/Transmission `add`.
- Coordinate `lacale.py` importability with the in-flight-design `tech-debt-2` (unrelated
  to RP1 but in the same `api/tracker` neighborhood) — RP1 does not touch tracker code, so
  no collision expected.

## 10. Side artifact carried on this branch

The **LaCale Deprecation → Vague 2** ROADMAP reclassification (discovered during this
brainstorm: the tracker registry is never boot-wired, so LaCale deprecation depends on
RP5a) is staged in `ROADMAP.md` and will be committed on this feature branch
(`docs(roadmap): defer LaCale deprecation behind RP5a`), per the operator's choice to
carry it here rather than as a standalone PR.
