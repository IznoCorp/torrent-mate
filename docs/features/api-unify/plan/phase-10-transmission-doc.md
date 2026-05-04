# Phase 10 — Transmission API Doc (interactive)

**Type**: doc
**Goal**: Study Transmission RPC, write reference doc, surface RPC-specific particularities.

## Gate (prereq)

Phase 9 complete. qBit migration verified, factory works.

## Sub-phases

### 10.1 — Study Transmission RPC

Sources: <https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md> and the `transmission-rpc` Python library (`pip show transmission-rpc`).

Note: Transmission RPC is **not REST**. It's a single endpoint accepting a JSON-RPC-style payload with `method` + `arguments`. CSRF protection via `X-Transmission-Session-Id` header (server returns 409 with new session id on stale).

### 10.2 — Real test calls

If a Transmission instance is available locally or in lab:

- `torrent-get` (with `fields=["id","hashString","name","totalSize","percentDone","status","downloadDir","addedDate"]`).
- `torrent-add`, `torrent-remove`, `torrent-stop`, `torrent-start`.

Capture samples to `docs/reference/_samples/transmission/`.

### 10.3 — Write `docs/reference/transmission-api.md`

Sections:

- Architecture: single endpoint `/transmission/rpc` accepting POST JSON.
- Auth: HTTP Basic (`LoginAuth`).
- CSRF dance: 409 with `X-Transmission-Session-Id` header → retry with new session id.
- Method catalog: `torrent-get`, `torrent-add`, `torrent-remove`, `torrent-stop`, `torrent-start`.
- Status enum: 0=stopped, 1=check-wait, 2=check, 3=download-wait, 4=download, 5=seed-wait, 6=seed.
- Response wrapping: `{"result": "success", "arguments": {...}, "tag": ...}`.
- Library `transmission-rpc` handles CSRF + serialization.

### 10.4 — Particularities checklist

- CSRF session id management — handled by `transmission-rpc` library.
- `percentDone` is float 0.0–1.0 (vs qBit's 0–100).
- `totalSize` is int bytes.
- `downloadDir` may differ from actual content path until torrent fully renamed.
- `seedRatioMode` and seed limits: optional, may be wanted for parity with qBit.
- "Completed" detection differs from qBit — Transmission has separate `seed` vs `seed-wait` states; both count as completed.

### 10.5 — Decision: TransportPolicy needed?

`transmission-rpc` library has its own session/retry. Does `HttpTransport` add value here?

**Recommendation for the user**: For consistency with qBit (which uses `qbittorrentapi` + a separate pre-check via `HttpTransport`), Transmission can have a **pre-check** via `HttpTransport(LoginAuth)` hitting `/transmission/rpc`. The doc phase must confirm the exact request method, expected response format, and acceptable status codes (notably the CSRF 409 flow) before Phase 11 hardcodes it. This mirrors the qBit pattern without assuming the Web UI HTML page is JSON-compatible.

Alternative: bypass `HttpTransport` entirely for Transmission since the library handles HTTP. Risk: less observability (logging, circuit breaker) for Transmission RPC errors.

### 10.6 — Interactive user checkpoint

> Doc complete: `docs/reference/transmission-api.md`.
> Particularities found: <list>
>
> Architectural decision needed:
> Option A: HttpTransport(LoginAuth) for pre-check, transmission-rpc for ops (parity with qBit).
> Option B: transmission-rpc only, no HttpTransport involvement.
>
> Recommendation: Option A (consistency, observability).
>
> Proposed implementation scope (Phase 11):
>
> - <pending user choice>
>
> Confirm option + scope before next phase?

### 10.7 — Phase 10 gate

```bash
ls docs/reference/transmission-api.md
ls docs/reference/_samples/transmission/ 2>/dev/null || echo "no live instance — samples optional"
```

**Commit**: `docs(api-unify): phase 10 gate — transmission api doc complete

User checkpoint captured:

- HttpTransport option: <A|B>
- <decisions>`
