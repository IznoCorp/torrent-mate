# Phase 10 — Doc LaCale + C411

## Gate

**Prerequisites**: Phase 9 complete. `api/metadata/` package complete.

## Goal

Transfer and complete Tracker API docs from `~/dev/TorrentMaker/docs/` to `docs/reference/`.

## Sub-phases

### 10.1 — Transfer LaCale API docs

Read `~/dev/TorrentMaker/docs/LaCale/api/INDEX.md`, `search.md`, `meta.md`, `upload.md`. Consolidate into `docs/reference/lacale-api.md` covering:

- Auth mechanism (check TorrentMaker .env for credential format)
- Search endpoint, parameters, response format
- Rate limits, categories
- Torrent fields: title, size, seeders, leechers, download URL, freeleech/silverleech status
- Any gotchas from TorrentMaker experience

**Commit**: `docs(api-unify): add LaCale API reference`

### 10.2 — Transfer C411 API docs

Read `~/dev/TorrentMaker/docs/C411/api/INDEX.md`, `Reference.md`, `ArrStack.md`, `upload.md`. Consolidate into `docs/reference/c411-api.md` covering:

- Auth mechanism
- Search endpoint, parameters, response format
- Rate limits, categories
- Torrent fields
- Any gotchas

**Commit**: `docs(api-unify): add C411 API reference`

### 10.3 — Phase 10 gate

```bash
ls docs/reference/lacale-api.md docs/reference/c411-api.md
```

**Commit**: `chore(api-unify): phase 10 gate — lacale + c411 docs done`
