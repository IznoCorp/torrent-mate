# DESIGN — Provenance F1: journey view (« parcours »)

**Type**: feat · **Bump**: minor (0.67.0 → 0.68.0) · **Ticket**: kanban #358 · **Epic**: provenance F1

## 1. Purpose

Make the pipeline **legible** (product-intent §pipeline lisible): a read-only view of each
acquisition's **journey** through the pipeline — grabbed → ingested → scraped → dispatched —
read from the F0 provenance spine (`staging_provenance`). This proves the "spine as the join
key" pattern early. Read-only, additive, no new write mechanism.

## 2. Scope (bounded)

- **IN**: the provenance journey (from `staging_provenance`) joined with the **follow title**
  (from `followed_series` via `followed_id`) so a row is human-readable. A journey carries the
  grab identity (tvdb/tmdb), the scraped identity, the per-stage timestamps, the current status,
  and the staging/dispatch paths.
- **OUT (later epic features)**: the `pipeline_run` link (F3), the decisions/resolution state
  (F2). F1 references NEITHER — it is self-contained on `acquire.db`.

## 3. Backend

- `_ProvenanceSubStore.list_journeys(limit)` — SELECT all rows, most-recent (`grabbed_at`) first,
  fail-soft (empty on error).
- `GET /api/acquisition/journeys` (read-only, guarded by the single `guarded_api` perimeter,
  NOT staging-guarded — it mutates nothing). For each row, join `follow.get(followed_id).title`.
  Typed `JourneysResponse` (Pydantic → OpenAPI → `schema.d.ts`; `make openapi`).

## 4. Frontend

- A **"Parcours"** tab on the AcquisitionPage (meta.ts + AcquisitionPage render), a
  `ParcoursPanel` that lists each acquisition as a compact **stepper**: the 4 stages lit up to
  the current status, with the identity (title + tvdb/tmdb), timestamps (relative), and the
  destination. Mobile-first (390px). Empty-state when nothing is tracked yet.

## 5. ACCEPTANCE

- **ACC-01**: `GET /api/acquisition/journeys` returns the provenance rows as typed journeys,
  most-recent first, with the follow title joined — `pytest tests/unit/web/routes/test_journeys.py`.
- **ACC-02**: unauthenticated → 401/403 (guarded); it is read-only (works on staging role).
- **ACC-03**: the "Parcours" tab renders each journey's stage stepper from the API — vitest.

## 6. Phases

1. Backend — `list_journeys` + endpoint + models + openapi + tests.
2. Frontend — "Parcours" tab + `ParcoursPanel` stepper + vitest.
