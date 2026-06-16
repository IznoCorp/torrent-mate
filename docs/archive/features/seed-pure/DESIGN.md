# DESIGN — Seed Safety O1: `seed-pure` tag + pipeline skip (+ manual tagger)

| Field                        | Value                                                                                                                                                                                                                                                                                |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Codename (proposed)**      | `seed-pure`                                                                                                                                                                                                                                                                          |
| **Roadmap item**             | Seed Safety O1 (P2, vague 3) — "tag « seed-pur » + skip à travers ingest/sort/process ; définit le contrat de skip que le Watcher consommera"                                                                                                                                        |
| **Type**                     | minor                                                                                                                                                                                                                                                                                |
| **Version bump**             | 0.32.0 → 0.33.0                                                                                                                                                                                                                                                                      |
| **Date**                     | 2026-06-15                                                                                                                                                                                                                                                                           |
| **Depends on (all shipped)** | `TorrentItem.tags` + `TorrentAdder.add(tags=)` (RP1), the qBittorrent/Transmission clients, the ingest completed-torrent loop + its ratio-skip pattern, `AppContext.torrent_client`, the `follow` Typer-group CLI pattern                                                            |
| **Unblocks**                 | Watcher Service (consumes the skip contract), Follow D3 + Ratio (produce the tag on seed-only grabs via the same tagger capability)                                                                                                                                                  |
| **Scope decisions**          | A (videur **and** colleur), B (skip at **ingest** always-on + opt-in **sort-side** real-exclusion guard, default off; clean-side flag reserved/not-enforced), C (tag vocab in `core/tags.py`), D (manual operator tagger CLI — automated producer is D3/Ratio), E (no DB/NFO change) |

> The system downloads torrents for two reasons: **to keep the content** (→ normal pipeline) or **just to
> seed** for ratio on a private tracker (→ must NOT enter the media library). O1 introduces a **`seed-pure`
> tag** on the torrent + teaches the triage pipeline to **skip** anything carrying it, plus a manual CLI to set
> the tag. The thing that _automatically decides_ a grab is seed-only is **Follow D3 / Ratio** (not shipped);
> O1 ships the **vocabulary + the skip + the tagging capability**, ready for them. Nothing changes for current
> usage until the tag is applied (no torrent is `seed-pure` today).

---

## 1. Responsibility boundary

O1 owns exactly:

1. **The tag vocabulary** — a centralized `seed-pure` constant (`core/tags.py`) every layer can import.
2. **The tagger capability (colleur)** — set/clear a tag on an **existing** torrent (qBittorrent + Transmission), plus a `seed` CLI group (`mark` / `unmark` / `list`) for the operator.
3. **The skip (videur)** — ingest skips any completed torrent tagged `seed-pure` (always on, the real guardrail); an **opt-in** real-exclusion guard at **sort** (config flag, default off). The clean-side flag is reserved/not-enforced (post-sort name-matching is unreliable).
4. **The skip contract** — documented semantics so the future Watcher consumes the same rule.

O1 does **NOT**:

- Decide _which_ grabs are seed-only automatically — that judgment belongs to **Follow D3 / Ratio** (they will call the same tagger capability). O1's producer side is **manual/operator-driven** today.
- Perform the seed/ratio download itself (Ratio C1).
- Change `library.db` / NFO / the media model (the `seed-pure` signal lives only on the torrent client + as the centralized constant).

---

## 2. The tag vocabulary (Decision C)

A new bottom-layer module `personalscraper/core/tags.py`:

```python
SEED_PURE = "seed-pure"   # torrent downloaded only to seed (ratio) — must be skipped by triage
__all__ = ["SEED_PURE"]
```

`core/` is the lowest layer, so `commands/`, `api/torrent/`, `ingest/`, `sorter/`, `process/`, `acquire/`, and a
future Watcher all import `SEED_PURE` without a layering violation. The complementary `content-useful` tag (the
tag a _content_ grab carries) is **Follow D3's** concern — out of scope here; only `SEED_PURE` is introduced.

---

## 3. The tagger capability (colleur)

### 3.1 New torrent-client capability — tag an existing torrent

Today both clients accept tags **only at add-time** via `TorrentAdder.add(tags=...)` (`_contracts.py:137-159`);
neither can tag a torrent **already in the client**. O1 adds a narrow capability protocol (mirroring the existing
`TorrentAdder`/`TorrentLimiter` atomic-protocol style in `_contracts.py`):

```python
# api/torrent/_contracts.py
class TorrentTagger(Protocol):
    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None: ...
    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None: ...
```

- **qBittorrent** (`qbittorrent.py`): wrap `qbittorrentapi`'s `torrents_addTags(torrent_hashes, tags)` /
  `torrents_removeTags(torrent_hashes, tags)`. Tags are a comma-delimited set internally (`_torrent_item`
  parses `raw_tags.split(',')` at ~`:400-416`).
- **Transmission** (`transmission.py`): **read-first** — Transmission stores category AND tags in one flat
  `labels=[category, *tags]` list (`_labels()` `:362-381`, `_torrent_item()` `:384-416`). To add/remove a tag:
  `get_torrent(info_hash)` → `category = labels[0]`, `existing_tags = labels[1:]` → compute new tag set →
  `set_torrent(info_hash, labels=[category, *new_tags])`. **Preserving `labels[0]` (category) is mandatory** —
  a naive overwrite wipes/misassigns the category.
- Torrent identity is the lowercase-hex `info_hash` (`TorrentItem.hash`, `_base.py:40`) throughout.

Both methods are **idempotent** (add an already-present tag = no-op; remove an absent tag = no-op) and **fail-soft
per the family convention** (raise the typed torrent-client error; the CLI surfaces it).

### 3.2 The `seed` CLI group (operator tagger)

New `personalscraper/commands/seed.py` — a Typer sub-group mirroring `follow.py` (`follow_app` `:47`,
`add_typer(..., name="follow")` `:407`, registered in `cli.py:111-115`):

```
personalscraper seed mark <info_hash>      # add the seed-pure tag to a torrent
personalscraper seed unmark <info_hash>    # remove it
personalscraper seed list                  # list torrents currently carrying seed-pure
```

- Uses `per_step_boundary(config, settings, build_torrent_client=True)` — **True** (unlike `follow`, which is
  read-only and uses False) because mark/unmark/list all touch the torrent client. Guard `torrent_client is not
None` and exit 1 with a clear message otherwise.
- `mark`/`unmark` call `torrent_client.add_tags/remove_tags(info_hash, [SEED_PURE])` and confirm via Rich output.
- `list` queries the client's completed/all torrents and filters those whose `tags` contain `SEED_PURE`, rendered
  as a Rich table `[Hash, Name, Tags, State]`.
- `log = get_logger("cli.seed")`; `@handle_cli_errors`.

---

## 4. The skip (videur)

### 4.1 Ingest skip — always on (primary guardrail)

In the ingest completed-torrent loop (`ingest/ingest.py:334 for torrent in torrents`), each `torrent` is a
`TorrentItem` whose `.tags: list[str]` is directly available (`_base.py:47`). Insert a skip check that mirrors the
existing **ratio-skip** pattern (`ingest.py:374-404`), placed **after** the ratio check and **before** content
resolution:

```python
if SEED_PURE in torrent.tags:
    log.info("ingest.seed_pure_skipped", name=name, tags=torrent.tags)
    report.skip_count += 1
    event_bus.emit(ItemProgressed(..., status="skipped", details={"reason": "seed_pure"}))
    continue
```

- Check order: skip-already-ingested → skip-ratio → **skip-seed-pure** → resolve content.
- Unconditional (no config gate — a `seed-pure` torrent must never be ingested).
- Inside the existing per-torrent `try/except` (`:340-535`) so one bad torrent can't abort the loop; the check
  itself raises nothing.
- Reuses the existing `ItemProgressed(status="skipped")` event (no new event type) — symmetric with ratio-skip.

### 4.2 Optional **sort-side** guard — opt-in, default off (Decision B, re-scoped)

**Signal-loss reality:** the `seed-pure` tag lives on the torrent in the client; once ingested, a staging item is a
plain filesystem path with **no seed-purity marker** (the ingest tracker records only hash/name/action/dest_path —
`ingest/tracker.py:40,131`). So this guard **cannot** read a staging marker — it must **re-query the torrent
client** and match the staging item to a torrent **by name**. This is **measurable latency** (a daemon round-trip)
and **only works in a full pipeline run** (standalone `sort` CLI builds no torrent client — `commands/pipeline.py`
builds it only for the full run).

**Re-scope (during implementation):** a guard that _counts_ a seed-pure item as skipped but still passes it to the
sorter is a **vacuous guard** — the item still lands in the library. A _real_ exclusion requires the sorter to
honour a skip-set. We therefore implement the guard **only on the sort side, with a genuine exclusion**, and
**drop the clean-side guard**: by clean time items are already sorted **and renamed**, so name-matching to torrent
names is unreliable — the marginal value does not justify the complexity. The always-on **ingest skip (§4.1)
remains the real guardrail**; this sort-side guard is the opt-in "ceinture + bretelles".

Mechanics (sort side, opt-in, default off):

- New config flag `config.sort.verify_seed_pure` (default `False`, enforced). A companion
  `config.process_clean.verify_seed_pure` flag is added for config symmetry but is **reserved / not yet enforced**
  (documented as such) — the clean-side guard is intentionally not implemented.
- `Sorter.process` gains a `skip_names: frozenset[str]` parameter: items whose name is in the set yield a
  **`skipped` `SortResult`** (`message="seed_pure"`) instead of being sorted — a **genuine exclusion**, counted by
  `run_sort`'s existing result-loop.
- `run_sort` gains an optional `torrent_client`; when `config.sort.verify_seed_pure` is True **and** a client is
  available, it builds the seed-pure name set from `torrent_client.get_completed()` and passes it as `skip_names`.
  When the flag is off (default), no client query and `skip_names` is empty — **zero added cost on the baseline
  pipeline**. The `SortStep` adapter threads `ctx.app.torrent_client` only when the flag is on.

---

## 5. The skip contract (for the Watcher)

Documented (architecture.md + a DESIGN note): **the `seed-pure` tag on a torrent is the single triage↔acquisition
seam** — acquisition writes it (D3/Ratio later, or the operator now via `seed mark`), triage reads it and skips,
and the **Watcher** (vague 4, replaces the 3h cron) must consult the **same** rule (ignore `seed-pure` torrents)
before triggering a pipeline run, so it never double-ingests a seed-only torrent. O1 freezes this contract;
the Watcher consumes it.

---

## 6. Layering, determinism, fail-soft invariants

- **Layering**: `core/tags.py` is the bottom layer (imports nothing project-internal). `api/torrent` gains the
  tagger; `ingest`/`sorter`/`process` import `SEED_PURE` from `core`. `commands/seed.py` lives at the boundary,
  composes the context via `per_step_boundary`, never declares `AppContext` directly (the
  `tests/architecture/test_app_context_boundary.py` rule).
- **Idempotent tagger**: add/remove are set operations — no duplicate tags, no error on absent removal.
- **Transmission category preservation**: the read-first write is the load-bearing correctness point (a test pins
  that tagging a Transmission torrent keeps its category).
- **Fail-soft**: the ingest skip raises nothing; a tagger error surfaces at the CLI (operator action), not mid-run.
- **Backward compatibility**: the sort/process flags default off; pre-existing configs load unchanged (pre-1.0 —
  schema evolves in place, no migration).

---

## 7. Verification (ACCEPTANCE — every criterion an executable command, SH-16)

1. **`SEED_PURE` constant** importable from `core.tags`, value `"seed-pure"`.
2. **qBittorrent tagger** — `add_tags`/`remove_tags` call the right `qbittorrentapi` endpoints (mock the client),
   idempotent.
3. **Transmission tagger** — `add_tags`/`remove_tags` **preserve the category** (`labels[0]`) via read-first
   (golden: a torrent with category + 1 tag → add a 2nd tag → labels = `[category, tag1, tag2]`, category intact).
4. **`seed mark`/`unmark`** — call the tagger with `[SEED_PURE]` for the given hash; `seed list` filters by tag.
5. **Ingest skip golden** — a completed torrent tagged `seed-pure` is skipped (not ingested): `skip_count`
   incremented, `ItemProgressed(status="skipped", reason="seed_pure")` emitted, no content resolution; a
   non-tagged torrent is **not** skipped by this check.
6. **Skip ordering** — the seed-pure skip sits after ratio, before content resolution (a torrent that is both
   below-ratio and seed-pure is counted once, no double-processing).
7. **Sort-side guard off by default + real exclusion** — with `config.sort.verify_seed_pure` unset, `run_sort`
   behaves exactly as before (no torrent-client query, `Sorter.process` `skip_names` empty); with the flag set + a
   client carrying a seed-pure torrent matching a staging item, the item is **genuinely excluded** — `Sorter.process`
   receives the name in `skip_names` and yields a `skipped` result (the item is NOT sorted), counted in `skip_count`.
   (Clean-side `process_clean.verify_seed_pure` flag exists but is reserved/not-enforced.)
8. **Layering guard** — `core/tags.py` imports nothing project-internal; `ingest`/`sorter`/`process` import
   `SEED_PURE` from `core` (not a local literal).
9. **`make check`** green; `python -c "import personalscraper"` smoke.

---

## 8. Decisions

- **A** — Ship both the **videur** (skip) and the **colleur** (tagger capability + manual CLI). The automated
  producer (decide seed-only) is deferred to D3/Ratio.
- **B** — Skip at **ingest, always on** (primary guardrail); opt-in **sort-side** guard with a **genuine exclusion**
  (`Sorter.process` `skip_names` → `skipped` result, not a vacuous count), default off (re-query cost stays off the
  baseline). The clean-side guard is **dropped** (post-sort name-matching unreliable); a `process_clean.verify_seed_pure`
  flag is added for symmetry but reserved/not-enforced.
- **C** — Tag vocabulary in `core/tags.py` (bottom layer, no layering violation).
- **D** — Manual operator tagger (`seed mark/unmark/list`) + the reusable client capability; D3/Ratio call the
  same capability later.
- **E** — No `library.db` / NFO / media-model change; the `seed-pure` signal lives on the torrent client + the
  centralized constant only.
- **F** — Reuse the existing `ItemProgressed(status="skipped")` event for the ingest skip (no new event type).

---

## 9. Phase decomposition (for `implement:plan`)

1. **Tag vocab + tagger capability** — `core/tags.py` (`SEED_PURE`), `TorrentTagger` protocol in
   `api/torrent/_contracts.py`, qBittorrent + Transmission `add_tags`/`remove_tags` (Transmission read-first
   category-preserving) + tests (criteria 1-3).
2. **`seed` CLI group** — `commands/seed.py` (`mark`/`unmark`/`list`, `build_torrent_client=True`) + registration +
   tests (criterion 4).
3. **Ingest skip** — the always-on `SEED_PURE` skip in `ingest/ingest.py` mirroring the ratio-skip pattern +
   tests (criteria 5-6).
4. **Opt-in sort-side guard (real exclusion)** — `SortConfig.verify_seed_pure` (enforced) +
   `ProcessCleanConfig.verify_seed_pure` (reserved/not-enforced) config flags (default off); `Sorter.process` gains a
   `skip_names` param (genuine exclusion → `skipped` result); `run_sort` builds the seed-pure name set + threads it;
   `SortStep` wires `ctx.app.torrent_client` only when the flag is on + non-vacuous tests (criterion 7). Clean-side
   guard dropped.
5. **Docs + ACCEPTANCE + gate** — `architecture.md` (`core/tags.py` + the `seed-pure` skip-contract note for the
   Watcher), `ACCEPTANCE.md` (criteria 1-9 executable), `make check` + design-gaps local run.
