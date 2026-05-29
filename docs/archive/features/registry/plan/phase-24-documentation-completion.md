# Phase 24 — Documentation completion

Created from `/pr-review-toolkit:pr-review` audit (2026-05-27). The RETROSPECTIVE
flagged "Capability protocols need usage examples" but it was never written.
`docs/reference/scraping.md` has **zero** mentions of `ProviderRegistry` or
the capability protocols. CHANGELOG 0.16.0 reflects only Phase 4 state — does
not mention Phases 7+11+14+15+16+17+18 work. `docs/reference/indexer.md` has
one passing mention (post Phase 11).

## Gate

- Phases 7–23 complete.
- All registry behavior shipped.

## Goal

- `docs/reference/scraping.md` contains a "Capability Cookbook" section with
  4–6 worked examples (one per Mode partition + cross_ref + locked).
- `CHANGELOG.md` 0.16.0 entry reflects every shipped phase (7-18).
- `docs/reference/indexer.md` contains a "Registry integration" section
  explaining how `backfill_ids` uses `fan_out(RatingProvider)` and
  `chain(MovieDetailsProvider|TvDetailsProvider)`.

## Scope

- `docs/reference/scraping.md` — add Capability Cookbook section.
- `CHANGELOG.md` — extend 0.16.0 entry.
- `docs/reference/indexer.md` — add Registry integration section.
- Optionally `docs/reference/architecture.md` if new cross-references are useful.

## Sub-phases

### 24.1 — Capability Cookbook in scraping.md

Add a section titled "Capability Cookbook" with worked examples (4–6 of them):

1. **chain (Searchable)** — search a title across all providers, return first
   non-empty result. Illustrate the for-loop + try/except blocks.
2. **chain (MovieDetailsProvider)** — fetch movie details with fallback. Show
   `ProviderFallbackTriggered` and `ProviderExhausted` flow.
3. **fan_out (RatingProvider)** — collect ratings from all eligible rating
   providers. Show `FanOutResult.values` / `.attempted`.
4. **locked (ArtworkProvider, match)** — fixed-source artwork fetch bound to
   a `ProviderMatch`. Show why locked is preferred over chain here.
5. **cross_ref (match, target=provider_name)** — translate a TMDB id to a
   TVDB id via the IDCrossRef escape hatch.
6. **direct (registry.get("tmdb"))** — for IDValidator / unscoped fetches
   where locked doesn't apply.

Each example: minimal runnable snippet + a one-paragraph "when to use this
over the alternatives" explanation.

Commit: `docs(reference): add Capability Cookbook to scraping.md (6 worked examples)`

### 24.2 — CHANGELOG.md 0.16.0 — extend with Phases 7–18

Current 0.16.0 entry reflects only Phase 4 state. Extend with sections
documenting:

- Phase 7 — chain semantics in production (movie_service + tv_service
  migrated; ProviderFallbackTriggered + ProviderExhaustedEvent emitted).
- Phase 8 — type design hardening (Mode → StrEnum, exhaustive @overload
  partition, Generic[C] preservation, Provider dual-name documented).
- Phase 9 — typed_settings_stub sweep (79 sites).
- Phase 10 — existing_validator extraction (drift + repair modules).
- Phase 11 — indexer backfill migrated to registry.fan_out + chain.
- Phase 14 — TVDB lazy bootstrap.
- Phase 15 — autouse CLI fixture removed; real ProviderRegistry boots on
  typed_settings_stub.
- Phase 16 — chain exhaustion raises ProviderExhausted (DESIGN §6.2 contract
  restored); ACC-13 anchor preserved.
- Phase 17 — Protocol provider_id widened to `int | str`; ACC-02 exemption
  tightened from 6 to 4 sites.
- Phase 18 — module-size extractions (tv_service_episodes,
  backfill_ids_canonical).

Use the existing section structure (Added / Changed / Internal).

Commit: `docs(changelog): extend 0.16.0 entry with Phases 7-18 (registry feature complete)`

### 24.3 — indexer.md — Registry integration section

Add a "Registry integration" subsection to `docs/reference/indexer.md`
explaining the Phase 11 migration:

- `run_backfill_ids` accepts `registry: ProviderRegistry` instead of typed
  clients.
- Ratings aggregation via `registry.fan_out(RatingProvider)`.
- Details lookup via `registry.chain(MovieDetailsProvider|TvDetailsProvider)`
  filtered to the canonical provider name.
- CLI `library backfill-ids` no longer extracts typed clients via
  try/except UnknownProviderError.

Commit: `docs(reference): add Registry integration section to indexer.md (Phase 11)`

### 24.4 — Cross-references between docs

Verify each reference is bidirectional:

- `architecture.md` → `scraping.md` Capability Cookbook.
- `scraping.md` → `indexer.md` Registry integration (for fan_out example).
- `indexer.md` → `scraping.md` (for chain/fan_out semantics).
- `external-ids-flow.md` → registry cross_ref helper.

Add the missing cross-links. Verify no broken markdown anchors.

Commit (optional): `docs(reference): cross-link registry sections across reference docs`

## Phase gate

- `rg "Capability Cookbook" docs/reference/scraping.md` returns 1 match.
- `rg "fan_out\|chain\|locked" docs/reference/scraping.md | wc -l` ≥ 12 (multiple mentions across examples).
- `grep -c "Phase 7\|Phase 11\|Phase 14\|Phase 15\|Phase 16\|Phase 17\|Phase 18" CHANGELOG.md` ≥ 7.
- `rg "ProviderRegistry\|registry.fan_out\|registry.chain" docs/reference/indexer.md` ≥ 3.
- No broken markdown anchors (manual review).

## ACC criteria touched

- ACC-11 (CHANGELOG entry) — extended, must still match the regex `^## \[0.16.0\]`.

## Cost estimate

- 24.1 Capability Cookbook: ~20–30 min Opus 1M (substantial writing).
- 24.2 CHANGELOG: ~10 min DeepSeek.
- 24.3 indexer.md: ~10 min DeepSeek.
- 24.4 cross-links: ~5 min DeepSeek.
- Total: ~50 min.

## Risk

None. Documentation-only.
