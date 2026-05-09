# Phase 17 — LaCale API Doc (interactive)

**Type**: doc
**Goal**: Transfer LaCale API knowledge from TorrentMaker, complete reference doc, surface tracker-specific particularities.

## Gate (prereq)

Phase 16 complete. Tracker base + ranking ready.

## Sub-phases

### 17.1 — Read TorrentMaker source material

Read every file under `~/dev/TorrentMaker/docs/LaCale/api/`:

- `INDEX.md` — overview.
- `search.md` — search endpoint.
- `meta.md` — metadata endpoint.
- `upload.md` — upload (out of scope — informational only).

Extract: endpoint URLs, parameters, response schemas, auth mechanism, rate limits, gotchas noted by TorrentMaker authors.

### 17.2 — Verify credentials format

Check `~/dev/TorrentMaker/.env` (carefully, **never copy** secrets) to confirm `LACALE_API_KEY` format (token? bearer? URL-style key?). Document format only.

### 17.3 — Real test calls

If possible, with `LACALE_API_KEY`:

- Search "Inception 2010" → list of torrents.
- Get categories.

Capture samples to `docs/reference/_samples/lacale/`.

### 17.4 — Write `docs/reference/lacale-api.md`

Sections:

- Auth: <to be confirmed from TorrentMaker — likely API key in query or header>.
- Search endpoint + parameters + response schema.
- Categories taxonomy.
- Rate limits + abuse policy.
- Torrent fields → `TrackerResult` field mapping table.
- Title parsing: which fields (resolution, codec, source, audio) need to be regex-extracted from the torrent title vs returned as separate fields.
- Freeleech/silverleech indicators (boolean flag? string in metadata?).

### 17.5 — Particularities checklist

- Title parsing: `[FreeLeech] Inception.2010.2160p.UHD.BluRay.x265.HDR.TrueHD.7.1.Atmos-NCmt.mkv` — fields (`resolution: 2160p`, `codec: x265`, `source: UHD.BluRay`, `audio: TrueHD`) inferable from title regex. Decision: build `_parse_title(title) -> dict` helper in `lacale.py`.
- Categories: tracker-specific IDs need normalization (`movies` vs `films` vs numeric).
- Date format: ISO 8601? Unix timestamp?
- Size: bytes, MB, or GB? → must coerce to `ByteSize`.
- Free/silver leech indicator location.

### 17.6 — Interactive user checkpoint

> Doc complete: `docs/reference/lacale-api.md`.
> Particularities found: <list>
>
> Implementation decisions to confirm:
>
> - Title-to-fields parsing strategy: regex on title? Or trust API-provided fields when present?
> - Category normalization mapping to internal `media_type`.
> - Default rps for RateLimitPolicy: <value, defensive>.
>
> Proposed scope (Phase 18):
>
> - search() returning list[TrackerResult] with all fields populated.
> - get_categories() returning dict[str, str].
> - \_parse_title helper for title-derived fields.
>
> Confirm before next phase?

### 17.7 — Phase 17 gate

```bash
ls docs/reference/lacale-api.md
ls docs/reference/_samples/lacale/ 2>/dev/null || echo "no live test calls — samples optional"
```

**Commit**: `docs(api-unify): phase 17 gate — lacale api doc complete

User checkpoint captured: <decisions>`
