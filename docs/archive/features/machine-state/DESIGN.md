# DESIGN — machine-state (epic F5, capstone)

**Feature**: Unified « état de la machine » overview — acquisitions + pipeline + décisions + en-attente, one view.
**Type**: feat · **Bump**: 0.71.0 → 0.72.0 (minor) · **Branch**: `feat/machine-state` · **Ticket**: #366
**Epic**: provenance tracking-spine (F0 → F5), roadmap `docs/archive/features/provenance/EPIC-ROADMAP.md` (the capstone).

## 1. Intent (operator-ratified)

Roadmap §F5: _la vue web unifiée : acquisitions + pipeline + décisions + en-attente, une page,
consommant F0–F3. C'est l'aboutissement produit._

## 2. Product-intent constitution (BINDING — cited §)

Serves `docs/reference/product-intent.md`:

- **§2 Visibilité du pipeline** (`ce qui se passe` : intégré/renommé/scrapé/dispatché).
- **§5 Acquisitions / états visibles** (en attente / en cours / dispatché).
- **§8 « Le Dashboard est le poste de contrôle ; toute vue de détail est adressable par URL »** +
  DOIT-2 (montrer ce qui ne se passe pas) + NE-DOIT-PAS-2 (file invisible).
  The overview is a rollup of the F0–F4 spine; every tile deep-links to the addressable detail view.
  **§méthode rule 6**: counts must be an **uncapped SQL aggregate**, never a frontend count over the
  200-capped `list_journeys` (that would silently lie once the spine exceeds 200 rows).

## 3. Backend — a composed aggregate endpoint

`GET /api/acquisition/overview` → `AcquisitionOverviewResponse` (new Pydantic model). Pure-read,
fail-soft, fresh per-request connection, NOT staging-guarded (a read; writes nothing).

Composes the four pillars from the seams F0–F4 already provide:

| Field                                                          | Source                                                                                                                                                                     |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `by_status: dict[str,int]`                                     | new `_ProvenanceSubStore.stage_counts()` — uncapped `SELECT status, COUNT(*) … GROUP BY status` over `staging_provenance` (grabbed/ingested/scraped/dispatched/reconciled) |
| `in_flight: int`                                               | derived = grabbed + ingested + scraped (the non-terminal statuses)                                                                                                         |
| `stuck: int`                                                   | `len(list_stuck(older_than=now-STUCK_IDLE_SECONDS, exists_fn=os.path.exists))` (FS-truth, F4)                                                                              |
| `awaiting_resolution: int`                                     | the AUTHORITATIVE `scrape_decision` pending count (`COUNT WHERE status='pending'`), not the advisory spine mirror (decisions is source-of-truth)                           |
| `watcher_enabled: bool`, `last_successful_run_at: int \| None` | the acquire watch-state seam (echo of `GET /status`'s pillar)                                                                                                              |

New store method `stage_counts() -> dict[str,int]` — fail-soft (`{}` on error), mirrors the other
readers. The decisions pending count reads `library.db` (indexer) directly (fail-soft `0`), reusing
the decisions route's exact `COUNT(status='pending')` semantics — no cross-DB fusion.

## 4. Frontend — « Vue d'ensemble » tab on the Acquisition hub

Placement: a NEW first tab `apercu` (« Vue d'ensemble ») on `AcquisitionPage`, above `parcours`
(the F1–F4 detail). URL-addressable via `?tab=apercu` (§8). Rationale: the rollup and its detail
(`parcours`) live in one hub, the data is acquisition-spine-centric, and the already-dense Contrôle
dashboard stays uncluttered.

- `api/acquisition.ts`: `getOverview()` + `acqKeys.overview()`; `hooks/useAcquisition.ts`: `useOverview()`.
- `OverviewPanel.tsx`: `StatPanel` tiles (à la `AcquisitionSummaryCard`) — « En vol » (in_flight, split
  grabbed/ingested/scraped), « Bloqués » (stuck, warning tone), « En attente de résolution »
  (awaiting_resolution), « Dispatchés » (by_status.dispatched), plus a watcher/last-run line. Each
  actionable tile deep-links: stuck → `/acquisition?tab=parcours`, awaiting → `/medias`, dispatched →
  `/acquisition?tab=parcours`. Fail-soft em-dash on missing data; EmptyState when the spine is empty.
- Live: invalidate `acqKeys.overview()` on the same ACQ/pipeline WS events the hub already listens to.

## 5. Non-regression guarantees (tested)

- Counts are uncapped SQL (not capped by list_journeys' 200); `stage_counts` fail-soft (`{}`).
- `awaiting_resolution` uses the authoritative `scrape_decision` count (matches the decisions badge).
- The endpoint is read-only + not staging-guarded + writes nothing (staging-safe).
- No change to the spine schema (no migration), the existing endpoints, or the decisions/pipeline flows.
- OpenAPI regenerated (`make openapi`) — new model/route → `openapi.json` + `schema.d.ts` committed.

## 6. ACCEPTANCE (executable)

- **ACC-F5-01** — `stage_counts()` returns the per-status GROUP BY counts (grabbed/ingested/scraped/
  dispatched), uncapped, and `{}` fail-soft on a DB error.
- **ACC-F5-02** — `GET /api/acquisition/overview` returns `by_status` + `in_flight` (= sum of
  non-terminal) + `stuck` (matches list_stuck) + `awaiting_resolution` (= scrape_decision pending count).
- **ACC-F5-03** — the overview is auth-guarded (401 without session) and NOT staging-guarded (200 on staging).
- **ACC-F5-04** — the « Vue d'ensemble » tab renders the tiles from the endpoint and deep-links to the
  addressable detail views; empty spine → EmptyState.
- **ACC-F5-05** — `make check` green; `make openapi` no drift; frontend gates green.

## 7. Phases

1. **Backend aggregate** — `stage_counts()` store method + `AcquisitionOverviewResponse` model +
   `GET /api/acquisition/overview` composing the four pillars; `make openapi`; store + endpoint tests.
2. **Frontend « Vue d'ensemble »** — getOverview + acqKeys.overview + useOverview + OverviewPanel
   (StatPanel tiles + deep-links) + the `apercu` tab on AcquisitionPage; frontend tests. Gate + PR.
