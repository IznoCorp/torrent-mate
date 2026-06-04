# Phase 10 — Reference Docs Updates

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Update `docs/reference/qbittorrent-api.md`, `docs/reference/transmission-api.md`, and `docs/reference/architecture.md` to document the new write capabilities, updated composition tables, and `AppContext.torrent_client`. 1 commit.

**Tech Stack:** Markdown

---

## Gate

- Inline fallbacks removed; `make check` passes with all tests green.

---

## Files

- Modify: `docs/reference/qbittorrent-api.md`
- Modify: `docs/reference/transmission-api.md`
- Modify: `docs/reference/architecture.md`

---

## Steps

- [ ] **1. Read current headings of each doc**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -n "^##" docs/reference/qbittorrent-api.md docs/reference/transmission-api.md docs/reference/architecture.md | head -30
```

- [ ] **2. Update `qbittorrent-api.md`**

Add a new section (following the existing heading style) documenting:

**`QBitClient.add(source, *, category, tags, paused, limits) → str`**

- Source routing: magnet → `urls=`, file bytes → `torrent_files=`
- Limits applied inline via `_limit_kwargs()`: `ratio_limit`, `seeding_time_limit` (minutes × 60), `upload_limit`, `download_limit`
- Returns `source.info_hash`; `"Fails."` response = duplicate → idempotent (D7)
- 401/403 → `ApiError`

**`QBitClient.apply_limits(info_hash, limits) → None`**

- `ratio` or `seed_time_minutes` → `torrents_set_share_limits` (sentinel `-2` = unchanged)
- `up_bytes_per_s` → `torrents_set_upload_limit`
- `down_bytes_per_s` → `torrents_set_download_limit`
- All-None = no-op

**Capability composition table** — add `TorrentAdder ✓`, `TorrentLimiter ✓` rows.

- [ ] **3. Update `transmission-api.md`**

Add a new section documenting:

**`TransmissionClient.add(source, *, category, tags, paused, limits) → str`**

- Labels encoding (D5): `labels = [category, *deduped_tags]`; read back: `category=labels[0]`, `tags=labels[1:]`
- `limits` must be `None`; raises `UnsupportedCapabilityError` if set (D8)
- Duplicate → `torrent-duplicate` exception → idempotent success (D7); returns `source.info_hash`
- Transmission echoes `hashString`; used as a cross-check in debug log

**Capability composition table** — add `TorrentAdder ✓`, `TorrentLimiter ✗` rows.

- [ ] **4. Update `architecture.md`**

Locate the torrent family section:

```bash
cd /Users/izno/dev/PersonnalScaper && rg -n "torrent\|AppContext" docs/reference/architecture.md | head -25
```

Update:

a. **Capability table for torrent family** — add `TorrentAdder` and `TorrentLimiter` rows with `QBitClient ✓` / `TransmissionClient ✓ or ✗`.

b. **`AppContext` field table** — add row: `torrent_client | QBitClient | TransmissionClient | None | Active torrent client; None when unconfigured (D9)`.

c. **Boot sequence description** — update to note that `_build_app_context()` now calls `build_active_torrent_client()` when `torrent.active` is set, asserts `TorrentAdder`, and raises `RegistryConfigError` on failure (D3).

d. **Module map** — confirm `api/torrent/_base.py` entry includes `TorrentSource`, `TorrentLimits`; `_contracts.py` entry includes `TorrentAdder`, `TorrentLimiter`.

- [ ] **5. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add docs/reference/qbittorrent-api.md docs/reference/transmission-api.md docs/reference/architecture.md && git commit -m "docs(torrent-write): document add/apply_limits, update capability tables and AppContext field"
```
