# DESIGN — decisions-spine (epic F2)

**Feature**: Project the scraping-decision / resolution state onto the provenance spine.
**Type**: feat · **Bump**: 0.68.0 → 0.69.0 (minor) · **Branch**: `feat/decisions-spine` · **Ticket**: #360
**Epic**: provenance tracking-spine (F0 → F5), roadmap `docs/archive/features/provenance/EPIC-ROADMAP.md`.

## 1. Intent (operator-ratified)

Epic roadmap §F2 (verbatim operator decision): **MIGRATE** the resolution state onto the
spine — "« médias en attente de résolution » devient un **état requêtable de première classe**
sur le spine (plus une dérivation de read_model)". Guard-rails: adversarial review +
anti-regression tests on the existing decisions flow ("ne rien casser").

The epic's "Ce que l'épic ne fait PAS" clause bounds this: **do NOT** merge `acquire.db` +
`library.db`; **do NOT** rewrite the decisions/read_model subsystems — **link** them; the
rapatriement is incremental and **fail-soft**.

## 2. The reconciliation (why projection, not consolidation)

The map (docs/analysis decisions-subsystem map) surfaced two hard constraints that a naïve
"move decisions into acquire.db" would violate:

1. **Coverage mismatch** — `staging_provenance` rows exist ONLY for follow-driven grabs
   (`upsert_grab` is the sole row-creator, ACC-06). Ambiguous decisions arise for _any_
   scrape, including manual/direct torrents with **no** spine row. **Decisions are the
   superset.** A resolution state that lived only on the spine would silently drop
   manual-item decisions → **regression** (the operator forbade regressions).
2. **Durability contract** — the provenance spine is **advisory** (a wiped registry
   degrades to exactly today's behaviour, ACC-01). `scrape_decision` carries **fail-loud
   operator verdicts** whose loss causes a duplicate scrape. Making an advisory table the
   system-of-record for those verdicts would break both contracts.

**Therefore F2 = an advisory PROJECTION of the resolution lifecycle onto the spine.**
`scrape_decision` (library.db) stays the **authoritative, fail-loud** store — untouched.
The spine gains a **resolution-state column** that MIRRORS the decision lifecycle for the
follow-driven items it already tracks, written best-effort by the decisions flow. This is
"first-class queryable state on the spine" (a stored column returned by the journey query,
not a read_model derivation) **while** preserving the advisory invariant: wipe acquire.db →
the column is gone, `scrape_decision` still holds the truth → degrade to today.

## 3. Data model (migration 011 — additive ALTER)

`ALTER TABLE staging_provenance ADD COLUMN` ×4 + one partial index, one transaction,
`user_version` 10 → 11. Fully additive; every predating reader/writer ignores the new
columns; a wiped/rolled-back column leaves the spine at F0/F1 behaviour.

| Column               | Type                                                    | Meaning                                                                                                                                      |
| -------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `resolution_state`   | `TEXT CHECK (… IN ('awaiting','resolved','dismissed'))` | NULL = no decision raised (confident scrape). `awaiting` = enqueued in the decision queue. `resolved`/`dismissed` = operator verdict landed. |
| `decision_id`        | `INTEGER`                                               | Advisory cross-DB pointer to `scrape_decision.id` (deep-link target). No FK (cross-DB; mirrors 010's no-FK rule).                            |
| `resolution_trigger` | `TEXT`                                                  | `below_threshold`/`mid_band`/`ambiguous` — carried for display.                                                                              |
| `resolution_at`      | `INTEGER`                                               | Epoch of the last resolution-state transition.                                                                                               |

Partial index `idx_provenance_resolution_state ON staging_provenance(resolution_state)
WHERE resolution_state IS NOT NULL` — cheap "what is awaiting resolution" queries.

## 4. Write path (advisory, fail-soft, path-keyed)

New advisory method `_ProvenanceSubStore.set_resolution(staging_path, *, state, decision_id,
trigger, resolved_at)` — path-keyed `UPDATE` (keyed on `current_path`, the same live-folder
join the sort/dispatch hooks use). UPDATE-only ⇒ **no-op when the folder is untracked**
(a manual/direct item never gets a spine row → its decision lives only in `scrape_decision`,
ACC-06 preserved). Wrapped in `_safe_write` (an error is logged + swallowed, never raised
to a step). Extends the `StagingProvenanceWriter` core port + the `ProvenanceSubStore` port.

Three hook sites (mirror of F0's ingest/sort/dispatch hooks):

| Moment      | Site                                                                       | Write                                                                                                                                       |
| ----------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Enqueue** | `scraper/run.py` decision loop (reuses the already-open `prov_store`)      | `set_resolution(r.media_path, state='awaiting', decision_id=None, trigger=r.decision_trigger)` for each `_is_enqueued(r)` item              |
| **Resolve** | `commands/scrape_resolve.py` after the authoritative `writer.resolve`      | wire `provenance` into the resolve `Scraper` (tracks the canonical rename, F0 Fix A/B), then `set_resolution(final_path, state='resolved')` |
| **Dismiss** | `web/routes/decisions.py::dismiss_decision` after `DecisionWriter.dismiss` | build the acquire store, `set_resolution(row['staging_path'], state='dismissed')`                                                           |

`decision_id` is stamped where known: the enqueue loop upserts the decision first, so the
loop re-reads the decision id (or leaves it NULL if the row-id read fails — advisory). The
UI deep-link falls back to a path match when `decision_id` is NULL.

**Not rewired**: the `read_model.py` "à résoudre" derivation and `stages.py` `compute_position`
stay AS-IS — the authoritative "À traiter" control list keeps reading `scrape_decision`
directly (no regression). The spine projection is a PARALLEL, advisory view for the
acquisition timeline.

## 5. Read surface

- `web/models/acquisition.py::JourneyItem` gains `resolution_state`, `decision_id`,
  `resolution_trigger` (all optional). `web/routes/acquisition.py::get_journeys` carries them
  from the `ProvenanceRow`. ⇒ `make openapi` (route response-model change → OpenAPI + schema.d.ts).
- Frontend `ParcoursPanel.tsx` badges the resolution state on the journey card: `awaiting`
  → an actionable "En attente de résolution" chip deep-linking to `/medias?decision=<id>`
  (or `/medias` when id is NULL); `resolved`/`dismissed` → a subtle terminal marker. Product-intent:
  the operator sees _where each acquisition stands in resolution_ and can act (§ acquisition
  visibility). Mobile 390px verified.

## 6. Non-regression guarantees (tested)

- **Decisions authoritative & unchanged**: `scrape_decision` schema, `DecisionWriter`
  resolve/dismiss fail-loud semantics, the decisions REST shapes + `?decision=<id>` ids —
  all byte-for-byte unchanged. Existing decisions tests stay green.
- **Manual items**: an ambiguous decision on an item with no spine row writes NOTHING to the
  spine (the `set_resolution` UPDATE no-ops) and remains fully resolvable via the existing
  decisions UI.
- **Advisory**: a wiped `staging_provenance` (or a wiped `resolution_*` column) ⇒ the
  decisions flow, scrape, resolve, dismiss all behave exactly as today.
- **Direct/manual grab unaffected** (ACC-06, both senses) — no new code path executes.

## 7. ACCEPTANCE (executable)

- **ACC-F2-01** — migration applies, version 11, columns present:
  `python -c "import sqlite3,tempfile,os; …; assert user_version==11 and {'resolution_state','decision_id','resolution_trigger','resolution_at'} ⊆ columns"` → prints `OK`.
- **ACC-F2-02** — advisory write projects onto a tracked row: seed a grabbed+ingested row,
  `set_resolution(path, state='awaiting', trigger='mid_band')`, read back → `resolution_state=='awaiting'`.
- **ACC-F2-03** — untracked (manual) item no-ops: `set_resolution('/no/such/path', …)` on an
  empty table changes 0 rows and never raises.
- **ACC-F2-04** — wiped registry degrades: with `staging_provenance` empty, a full scrape that
  enqueues an ambiguous item still writes `scrape_decision` and the item is resolvable
  (decisions flow unchanged).
- **ACC-F2-05** — journeys endpoint carries the resolution fields: seed an `awaiting` row,
  `GET /api/acquisition/journeys` → the item exposes `resolution_state=='awaiting'`.
- **ACC-F2-06** — `make check` green; `make openapi` leaves no drift; frontend lint+typecheck+vitest green.

## 8. Phases

1. **Spine schema + store** — migration 011, `ProvenanceRow` fields, `set_resolution`, port
   extensions; unit tests rouge-avant (ACC-01/02/03), migration-test version bump.
2. **Write hooks** — enqueue/resolve/dismiss; anti-regression tests (ACC-04, manual-item
   no-op, decisions flow unchanged, resolve rename-tracked).
3. **Read surface** — JourneyItem fields + endpoint + `make openapi`; ParcoursPanel badge +
   deep-link; frontend tests (ACC-05). Phase gate + PR.
