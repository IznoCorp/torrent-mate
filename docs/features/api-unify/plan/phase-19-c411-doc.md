# Phase 19 — C411 API Doc (interactive)

**Type**: doc
**Goal**: Transfer C411 API knowledge from TorrentMaker, complete reference doc.

## Gate (prereq)

Phase 18 complete. LaCale implementation working as reference.

## Sub-phases

### 19.1 — Read TorrentMaker source material

Read `~/dev/TorrentMaker/docs/C411/api/`:

- `INDEX.md`, `Reference.md`, `ArrStack.md`, `upload.md`.

Note differences from LaCale: C411 is often Sonarr/Radarr (Arr-stack) compatible — exposes a Newznab-style or Torznab-style API. This may simplify the implementation (standardized format).

### 19.2 — Verify credentials format

Check `~/dev/TorrentMaker/.env` for `C411_API_KEY` format.

### 19.3 — Real test calls

If possible, with `C411_API_KEY`:

- Search "Inception 2010".
- Get categories.

Capture samples to `docs/reference/_samples/c411/`.

### 19.4 — Write `docs/reference/c411-api.md`

Sections:

- Auth: <to be confirmed>.
- API style: standard Torznab/Newznab vs custom REST? Affects implementation pattern.
- Search endpoint + parameters + response schema.
- Categories taxonomy (Newznab category numeric IDs are standardized: 2000=movies, 5000=TV).
- Rate limits.
- Torrent fields → `TrackerResult` mapping table.

### 19.5 — Particularities checklist

- Newznab/Torznab response is XML (RSS-style) — use `TransportPolicy.response_format="xml"` if the documented responses confirm this.
- Decision still needed on provider scope: use the shared XML transport path (preferred) or bypass transport if C411 requires non-standard raw handling beyond XML parsing.
- Category mapping standardized via Newznab IDs.
- Some fields embedded in title only (similar to LaCale — `_parse_title` reusable).

### 19.6 — Interactive user checkpoint

> Doc complete: `docs/reference/c411-api.md`.
> Particularities found: <list>
>
> Architectural decision needed:
>
> - C411 returns XML (Newznab/Torznab). HttpTransport supports `response_format="xml"` from Phase 1.
> - Option A: Use shared `HttpTransport` XML parsing.
> - Option B: C411-specific override that uses HttpTransport.get raw via session, parses XML in client.
>
> Recommendation: Option A unless the doc phase finds C411-specific raw handling needs that the shared transport cannot express.
>
> Proposed scope (Phase 20):
>
> - <pending option choice>
> - search() + get_categories() + reuse \_parse_title from LaCale.
>
> Confirm before next phase?

### 19.7 — Phase 19 gate

```bash
ls docs/reference/c411-api.md
```

**Commit**: `docs(api-unify): phase 19 gate — c411 api doc complete

User checkpoint captured:

- Transport option: <A|B>
- <decisions>`
