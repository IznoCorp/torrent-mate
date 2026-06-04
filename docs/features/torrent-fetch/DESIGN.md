# Design — RP1a: Torrent fetch boundary (`torrent-fetch`)

> ROADMAP item **RP1a** (Vague 1, `[P1, prérequis]`). The fetch half of decision
> **Q4** ("PersonalScraper fetch + POST"): RP1 (`torrent-write`) shipped the **POST**
> half (`TorrentSource` → `client.add()`); RP1a closes the **fetch** half — turning a
> chosen `TrackerResult` into a `TorrentSource`. Unblocks Orchestration (RP5b), Follow,
> Ratio.
>
> Grounded against the code on **2026-06-04** via a 6-agent adversarial footprint survey
> (transport extensibility, the bencode gate, retry/401 surfacing, tracker URL/auth/magnet
> shapes, the no-factory leaf-scope claim + public surface, and a design-hole critic). Every
> code reference below was verified; corrections from that survey are folded in and marked.

## 1. Purpose

A downstream acquisition consumer (RP5b orchestrator / Follow / Ratio) chooses a
`TrackerResult` and must obtain a `TorrentSource` to hand to `client.add()`. Today
**nothing produces a `TorrentSource` from a `TrackerResult`** — that gap is RP1a.

RP1a delivers a **standalone, tracker-agnostic fetch boundary**:

1. a **binary GET** capability on `HttpTransport` (`get_bytes`) with its **own** download
   circuit breaker + rate limiter, absolute/relative-URL handling, a streamed size cap, and
   no auth-param re-merge;
2. a **fetcher module** (`api/tracker/_fetch.py`) that maps a download URL (or a chosen
   `TrackerResult`) to a validated `TorrentSource` — magnet → `from_magnet` (no fetch);
   HTTP `.torrent` URL → authenticated binary GET → strict-validated `from_file`;
3. **typed, observable errors** — `TrackerAuthError` on 401/403, `TorrentFetchError` on
   bad/empty/oversize content or a hash mismatch.

## 2. Non-goals

- **No pipeline / `AppContext` / registry wiring, and no transport construction.** RP1a is a
  leaf `prérequis`. The consumer is **RP5b**; building tracker transports from config + boot
  validation is **RP5a** (which the survey confirmed does not exist yet — see §3). RP1a's
  `resolve_source` **routes** over a caller-supplied `Mapping[str, HttpTransport]`, mirroring
  the existing `TrackerRegistry` dependency-injection style (`__init__` takes pre-built
  clients, never constructs them).
- **No URL re-resolution and no auth-failure event.** Re-resolving the download URL just
  before the add and emitting a tracker-auth-failure event is **RP7**. RP1a only makes the
  401/403 a typed, immediately-surfaced signal that RP7 will later route.
- **No limit / ratio / seedtime policy** — that is RP2 / Ratio (C1–C3) / Seed-Safety (O4).
- **No config change** — the download breaker/limiter derive from the existing tracker
  `TransportPolicy` values; no new config keys (RP2 owns tracker economy/policy).
- Multi-tracker orchestration, cross-tracker dedup, ranking (RP5b and beyond).

## 3. Grounded current state (2026-06-04)

| Area                      | Reality (verified)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TorrentSource`           | `@dataclass(frozen=True)` in `api/torrent/_base.py:52`, fields `magnet \| file_bytes` (exactly-one, empty `""`/`b""` treated as not-set — `__post_init__:64`). `from_magnet`/`from_file` classmethods; `info_hash` `cached_property` (magnet → `_parse_magnet_hash` hex/base32; bytes → hardened `_bencode_info_hash`). **Shipped (RP1).** `from_file(b"")` raises at construction (`requires exactly one of …`), never reaching the bencode gate.                                                              |
| `add()` (POST half)       | `QBitClient.add()` / `TransmissionClient.add()` consume `TorrentSource`. **Shipped (RP1).**                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Fetch (this feature)      | **Does not exist anywhere.** No code produces a `TorrentSource` from a `TrackerResult`.                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `TrackerResult`           | `api/tracker/_base.py:57` — has `download_url: str \| None` (the **only** URL field) and `info_hash: str \| None`. **No magnet field anywhere** (`rg -i magnet -g '*.py' api/tracker/` → 0 hits). `provider` is set to `self.provider_name` = the **lowercase wire value** (`ProviderName.C411.value="c411"`, `…LACALE.value="lacale"`) — the docstring example (`"LaCale"`/`"C411"`) is **stale**.                                                                                                             |
| C411 download URL         | `enclosure[@url]` (`c411.py:243`), an **absolute** `https://c411.org/...` with the **apikey embedded inline** (self-authenticating; `c411.py:23` docstring). Policy auth = `ApiKeyAuth(param="apikey", location="query")`. `info_hash` = `attrs["infohash"] or guid` (40-char btih hex; can be `""` if both absent).                                                                                                                                                                                            |
| LaCale download URL       | `downloadLink` (`lacale.py:191`), a **relative** path `/api/download/<infoHash>?token=<JWT>` carrying a **per-request JWT** (self-authenticating). Policy auth = `ApiKeyAuth(param="X-Api-Key", location="header")` (applied to the session at transport init). `info_hash` = `infoHash` (lowercase 40-char hex; can be `None`).                                                                                                                                                                                |
| `HttpTransport`           | `api/transport/_http.py` — JSON/XML/text only (`response_format: Literal["json","xml","text"]`, `_policy.py:103`); **no binary path**. `_request_outer` (`:104`) holds the circuit/retry wrapper; `_do_request` (`:145`) is format-agnostic until the parse tail (`:207-215`). **One** circuit breaker (`:61`) + **one** rate limiter (`:62`) per instance. Non-2xx → `ApiError(http_status=…)` (`:200`). URL build has **no** scheme detection (`:160`). Auth params are merged on **every** request (`:159`). |
| Retry / 401               | `RetryPolicy.retryable_statuses` default = `{429,500,502,503,504}` (`_policy.py:28`); C411/LaCale do **not** override it → **401/403 are not retried** and surface on the first attempt (`_is_retryable`, `_http.py:229-232`).                                                                                                                                                                                                                                                                                  |
| Tracker factory           | **None.** No `api/tracker/_factory.py`; `rg 'build_active_tracker\|C411Client(\|LaCaleClient('` over `personalscraper/` → 0 production instantiations (only tests). `resolve_active` (`api/_activation.py:41`) returns enabled provider **names**, builds nothing. Confirms RP1a must not construct transports.                                                                                                                                                                                                 |
| `api/tracker/__init__.py` | **Empty (0 bytes)** — no `__all__`, no exports. Public symbols are imported from submodules today. RP1a creates the package's `__all__` from scratch.                                                                                                                                                                                                                                                                                                                                                           |
| `api/torrent/_errors.py`  | Imports `ApiError` via `from personalscraper.api._contracts import ApiError` (re-export of canonical `core._contracts.ApiError`). It is **not** a base-subclass pattern — it defines error **tuples** + a non-`ApiError` `UnsupportedCapabilityError`. New `api/tracker/_errors.py` (ApiError subclasses) is a **new** pattern; kept in a separate file to avoid the circular-import concern its docstring documents.                                                                                           |

## 4. Frozen decisions (brainstorm 2026-06-04, verified)

| #                                                  | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1 — Seam**                                      | A **standalone, tracker-agnostic fetcher** in `api/tracker/_fetch.py`, **not** a per-tracker capability. Rationale: fetching `.torrent` bytes is one job (SRP); the logic is identical across trackers (DRY); auth is satisfied by **passing the tracker's transport**, not by relocating fetch code into each client.                                                                                                                                                                                                                                                                      |
| **D2 — Mechanism**                                 | The fetcher goes **through `HttpTransport`**, extended with a binary GET `get_bytes`. It inherits the host-protecting resilience but on a **dedicated download breaker/limiter** (D3). The wrapper (`_request_outer`) is parameterized with `(circuit, rate_limiter, response_mapper)` so the binary path reuses the retry/circuit machinery with **zero duplication** (survey C1).                                                                                                                                                                                                         |
| **D3 — Isolated download resilience (signed off)** | `HttpTransport` gains a **second** circuit breaker + rate limiter (separate instances, **same** policy thresholds/cooldown/rps, name `"<provider>-download"`), used **only** by `get_bytes`. `get`/`post` keep the search breaker+limiter. **A download 5xx never opens the search circuit; downloads are not serialized behind searches.** No config change — derived from the existing `TransportPolicy`. (Eager construction in `__init__`; the per-transport cost is two cheap objects — plan may make it lazy.)                                                                        |
| **D4 — Error typing**                              | New `api/tracker/_errors.py`: `TrackerAuthError(ApiError)` (401/403 on a download) and `TorrentFetchError(ApiError)` (non-`.torrent` content / empty / oversize / hash mismatch / missing url / missing provider). Field-free subclasses inherit `ApiError`'s generated `__init__`/`__eq__` cleanly (survey F5).                                                                                                                                                                                                                                                                            |
| **D5 — Strict validation at fetch**                | `get_bytes` rejects an **empty body** explicitly and enforces the **size cap**. `fetch_torrent_source` validates structurally by deriving `TorrentSource.from_file(data).info_hash`, which runs the hardened `_bencode_info_hash` — it raises `ValueError` on HTML/JSON/plaintext (first byte ≠ `b"d"`) and on a bencode dict with no top-level `info` key. The fetcher **wraps that `ValueError` into `TorrentFetchError`** (carrying the download URL + a body-byte preview), so an HTML-200 login wall fails **here**, not later at `add()`.                                             |
| **D6 — Convenience `resolve_source`**              | `resolve_source(result, transports, *, cross_check=True) -> TorrentSource`: **magnet short-circuit before** the transport lookup (a magnet needs no auth); else look up `transports[result.provider]` (**keyed by the lowercase wire value**) → missing provider raises `TorrentFetchError` (message embeds the requested provider + available keys); missing `download_url` raises `TorrentFetchError`; delegates to `fetch_torrent_source(result.download_url, transport, expected_info_hash=result.info_hash if cross_check else None)`. Mirrors `TrackerRegistry`'s injected-map style. |
| **D7 — Hash cross-check normalization**            | Before comparing, **canonicalize both sides** to lowercase hex (decode 32-char base32 → hex, reusing the `_parse_magnet_hash` logic); the file hash is already lowercase hex (`hashlib…hexdigest()`). **Skip** the check when `expected_info_hash` is falsy (C411 can yield `""`, LaCale `None`). Prevents false mismatches on an uppercase C411 guid or a base32 hash.                                                                                                                                                                                                                     |
| **D8 — Magnet exception**                          | `download_url.lower().startswith("magnet:")` → `TorrentSource.from_magnet(url)`, no transport call. **Documented as forward-looking**: neither C411 nor LaCale emits magnets today (both always http) — the branch exists for robustness and future trackers, exercised in unit tests with a synthetic magnet.                                                                                                                                                                                                                                                                              |
| **D9 — No auth re-merge for downloads**            | `get_bytes` does **not** merge `auth.auth_params()` (verified: `requests` _appends_, so a C411 URL already carrying `apikey=` would get `?apikey=X&apikey=X`, which a server may reject). The tracker URL self-authenticates (C411 inline apikey, LaCale JWT). **Session header auth stays** (applied at init — needed for LaCale's `X-Api-Key`); only query-param re-appending is suppressed.                                                                                                                                                                                              |
| **D10 — Absolute + relative URLs**                 | `get_bytes` detects the scheme: `http(s)://…` is used **verbatim**; anything else is joined onto `base_url` (LaCale's `downloadLink` is relative). This is a brand-new branch — the existing URL build (`base_url + path`) is **not** reused as-is.                                                                                                                                                                                                                                                                                                                                         |

## 5. Components

### 5.1 `HttpTransport` extension (`api/transport/_http.py`)

- **`get_bytes(self, url, *, max_bytes=DEFAULT) -> bytes`** — binary GET.
  - Scheme detection (D10): absolute URL verbatim; relative joined onto `base_url`.
  - **No** `auth.auth_params()` merge (D9); session header auth retained.
  - Streamed read (`stream=True` + `iter_content`) with a **running byte counter**, aborting
    the instant total > `max_bytes` (don't trust `Content-Length`); rejects an **empty body**
    (D5). Default `max_bytes` ≈ 10 MiB (a `.torrent` is KB–few-MB).
  - Non-2xx → `ApiError(http_status=…)` (existing behavior); 401/403 not retried (verified).
  - Uses the **download** circuit breaker + rate limiter (D3), never the search ones.
  - **Refactor (survey C1):** extract `_do_request_raw(...) -> requests.Response` (rate-limit,
    URL build, request, log, non-2xx raise) and parameterize `_request_outer` with
    `(circuit, rate_limiter, response_mapper)`. `get`/`post` pass the search breaker/limiter +
    the format parser; `get_bytes` passes the download breaker/limiter + a `resp → bytes`
    mapper. Zero duplication of the retry/circuit logic.
- **`__init__`** gains `self._download_circuit` + `self._download_rate_limiter` (D3), named
  `"<provider>-download"`, built from the same policy thresholds/cooldown/rps.

### 5.2 Fetcher module (`api/tracker/_fetch.py`, new)

```python
def fetch_torrent_source(
    url: str, transport: HttpTransport, *, expected_info_hash: str | None = None,
) -> TorrentSource:
    """magnet → from_magnet (no fetch); else get_bytes → strict-validate → from_file.

    Raises TrackerAuthError on 401/403, TorrentFetchError on bad/empty content or
    a normalized hash mismatch.
    """

def resolve_source(
    result: TrackerResult, transports: Mapping[str, HttpTransport], *, cross_check: bool = True,
) -> TorrentSource:
    """Route by result.provider over a caller-supplied transport map (D6)."""
```

- `_is_magnet(url)` helper; a `_canonical_info_hash(s)` helper (hex/base32 → lowercase hex,
  reusing `_parse_magnet_hash` semantics) for D7 — or import/extract the existing one.
- `fetch_torrent_source` catches the transport's `ApiError` and re-raises `TrackerAuthError`
  when `http_status in (401, 403)`; wraps `_bencode_info_hash`'s `ValueError` into
  `TorrentFetchError` (D5).

### 5.3 Errors (`api/tracker/_errors.py`, new)

`TrackerAuthError(ApiError)`, `TorrentFetchError(ApiError)`. Import `ApiError` from
`personalscraper.api._contracts`. Separate file (circular-import hygiene, per the torrent
family's documented pattern).

### 5.4 Public surface (`api/tracker/__init__.py`)

Create `__all__ = ["fetch_torrent_source", "resolve_source", "TrackerAuthError",
"TorrentFetchError"]` (from scratch — the file is currently empty) with the matching imports.

### 5.5 Docstring fix (`api/tracker/_base.py`)

Correct the stale `TrackerResult.provider` example (`"LaCale"`/`"C411"`) to the lowercase
wire value (`"lacale"`/`"c411"`) to prevent future map-key mismatches.

## 6. Data flow

```
TrackerResult ──resolve_source(result, transports)──┐
   magnet? ── yes ─▶ TorrentSource.from_magnet(url)          (no fetch, no auth — D8)
   no ▼
   download_url None ─▶ TorrentFetchError
   transports[result.provider] missing ─▶ TorrentFetchError
   ▼ fetch_torrent_source(download_url, transport, expected_info_hash=result.info_hash)
        get_bytes(url)  ── 401/403 (ApiError) ─▶ TrackerAuthError      (download breaker/limiter — D3)
        │   (absolute|relative URL, no auth re-merge, streamed size-cap, empty→reject)
        ▼ TorrentSource.from_file(bytes)
        ▼ .info_hash  ── _bencode_info_hash ValueError ─▶ TorrentFetchError (HTML-200 / no-info)
        ▼ canonical(expected) ≠ canonical(derived) ─▶ TorrentFetchError      (skip if expected falsy — D7)
        ▼ TorrentSource  ──▶ (RP5b consumer) client.add(source, category=…, tags=[…])
```

## 7. Testing (unit, fake transport; design-contract paired per the tracker family convention)

- **`get_bytes`**: absolute URL passed verbatim; relative URL joined onto `base_url`; **no**
  second `apikey` query param appended (D9); size cap aborts an oversize body; empty body →
  error; non-2xx → `ApiError`; uses the **download** breaker (a download 5xx does **not** open
  the search breaker; a download is not blocked by the search rate limiter) (D3); a fake
  transport with `response_format="xml"` still returns **raw bytes** (no parse tail, survey F9).
- **`fetch_torrent_source`**: magnet short-circuit (transport never touched); valid `.torrent`
  → `from_file`; HTML-200 → `TorrentFetchError`; 401 & 403 → `TrackerAuthError`; hash
  cross-check passes for uppercase/base32 expected hashes (D7) and fails on a real mismatch;
  cross-check skipped when `expected_info_hash` is `""`/`None`.
- **`resolve_source`**: routes a real C411/LaCale `result` (lowercase provider key) to its
  transport; missing provider → `TorrentFetchError` (message lists available keys); missing
  `download_url` → `TorrentFetchError`; `cross_check=False` disables the hash check.

## 8. Acceptance (design-level; full executable `ACCEPTANCE.md` at plan time)

- `python -c "from personalscraper.api.tracker import fetch_torrent_source, resolve_source, TrackerAuthError, TorrentFetchError"` → exit 0.
- Fake-transport asserts: magnet bypass (no transport call); 401 → `TrackerAuthError`; HTML-200
  → `TorrentFetchError`; uppercase/base32 expected hash → cross-check passes; oversize → reject.
- A download-path 5xx leaves the search circuit **closed** (isolated breaker, D3) → asserted.
- `make check` green; `python -c "import personalscraper"` smoke OK.

## 9. Open items carried to planning

- **Redirect-to-magnet** (an HTTP endpoint 302 → `magnet:`): `requests` can't GET a magnet
  scheme → would raise. **Out of scope for RP1a** (handle in RP7/RP5b); RP1a branches only on
  the **initial** URL scheme.
- **LaCale JWT freshness**: `downloadLink`'s `?token=<JWT>` is per-request and may expire — its
  re-resolution is **RP7**. RP1a fetches whatever URL it is handed; an expired-token 401
  surfaces as `TrackerAuthError`.
- **Download breaker/limiter lifecycle**: eager vs lazy construction (and any thread-safety
  note) — settle at implementation; eager is the default for determinism.
- **`max_bytes` default value** and the exact streamed-read chunk size — settle at
  implementation.
- **Placement of the `_canonical_info_hash` helper** — reuse/extract `_parse_magnet_hash`
  vs a small tracker-local helper — settle at implementation.
