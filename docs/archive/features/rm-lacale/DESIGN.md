# [#156] rm-lacale — complete removal of the LaCale tracker (+ Torr9 zero-remnant proof)

**Date**: 2026-08-03 · **Codename**: `rm-lacale` · **Type**: refactor · **Bump**: minor (0.76.0 → 0.77.0)

## 1. Problem

Operator changed the ticket scope from "deprecate" to **FULL REMOVAL**: la-cale.space is
dead (live config carries `lacale: { enabled: false }` with a CircuitOpenError incident
note). Dead code, dead config, dead docs, and dead sample data must go. Torr9 was removed
earlier; this feature also delivers the executable zero-remnant proof for it.

## 2. Decisions

| #   | Decision                                                                                                                                                                                                                                                                                                                                                                                           | Rationale                                                                         |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| D1  | Remove ALL LaCale code: `api/tracker/lacale.py`, the `_factory.py:30` registry entry, `_activation.py` cred/optional-secret entries (LACALE_API_KEY/LACALE_PASSKEY), `ProviderName.LACALE` enum member, every module-level reference (contracts/quality/fetch/torznab/errors docstrings included)                                                                                                  | Full removal is the operator scope; no deprecation shims before v1 (project rule) |
| D2  | Historic DB rows keep `source_tracker="lacale"` untouched and MUST stay readable. `source_tracker` is a free string column (no SQL CHECK — verified); design-time grep shows no runtime coercion of stored tracker strings into the `ProviderName` enum (`RegistryProviderName` is a NewType, no validation). Phase 1 re-verifies with a clean grep; full suite is the backstop. NO data migration | Truthful history; deleting rows would falsify obligations/provenance              |
| D3  | The `k != "lacale"` known-tracker exclusion in `web/models/acquisition.py:622` is deleted (dead once the registry no longer knows lacale) — behavior identical                                                                                                                                                                                                                                     | Simplification, not a behavior change                                             |
| D4  | The 12 ranking-preview samples (`web/routes/acquisition_ranking.py:96-110`, feature #374) using `provider="lacale"` are rewritten onto live trackers (c411/tr4ker), keeping the SAME quality/seed shapes so the preview stays representative                                                                                                                                                       | Preview must show real trackers only                                              |
| D5  | Frontend: remove LACALE from `SecretsTab.tsx`; any web model/docstring change ⇒ `make openapi` + commit regenerated `schema.d.ts` (CI drift guard)                                                                                                                                                                                                                                                 | Repo invariant                                                                    |
| D6  | Config: remove the lacale block + PROVIDER_CREDS comment mentions from `config.example/tracker.json5`; the LIVE config (`~/.torrentmate/config/tracker.json5`) is cleaned POST-MERGE (mini-repo commit) — never fails CI (CI never loads live config)                                                                                                                                              | config-drift rule; live config is post-merge operator action                      |
| D7  | Docs: delete `docs/reference/lacale-api.md`; purge lacale rows/mentions from `architecture.md`, `c411-api.md`, CLAUDE.md reference-index line (tracker list)                                                                                                                                                                                                                                       | Docs lie otherwise                                                                |
| D8  | Torr9: ACCEPTANCE criterion = `rg -i "torr9" -g '*.py' -g '*.json5' -g '*.ts' -g '*.tsx' personalscraper/ tests/ frontend/src/ config.example/` → zero hits outside the removed-tracker regression suite (single exemption: tests/acquire/test_removed_tracker_history.py). NOTE: all-glob form — on rg 15.1.0 a `-g` glob OVERRIDES `--type py`, silently searching zero .py files (verified empirically at plan time)                                                                                                                                                                                                                                        | Executable proof, per operator ask                                                |
| D9  | Tests referencing lacale (~10 files: e2e golden, torznab, registry except-scope, delete authority, filters, cross-seed…) are rewritten onto another tracker fixture (c411/tr4ker/torznab-generic) — NEVER deleted wholesale; each test keeps testing the same behavior with a different provider name. Tests that specifically pin "lacale exists in registry" flip to pin its ABSENCE             | Coverage must not shrink silently                                                 |
| D10 | Residual-import gate (Phase Gate rule): `rg -i "lacale" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.json5' -g '*.md' personalscraper/ tests/ frontend/src/ config.example/ docs/reference/` → zero hits at the final gate (exemptions: docs/archive/**, docs/features/rm-lacale/**, tests/acquire/test_removed_tracker_history.py — the removed-tracker regression suite; same all-glob form fix as D8)                                                                                     | The deletion IS the feature; the grep is its proof                                |

## 3. Removal map (verified against tree 2026-08-03)

- `personalscraper/api/tracker/lacale.py` — DELETE (client class).
- `personalscraper/api/tracker/_factory.py:30` — registry entry + docstring examples.
- `personalscraper/api/_activation.py:34,100` — cred maps + docstring examples.
- `personalscraper/api/_contracts.py:49` — `ProviderName.LACALE` member (+ grep every use).
- `personalscraper/api/tracker/{_contracts,_quality,_fetch,torznab,_errors}.py` — refs/docstrings.
- `personalscraper/api/metadata/registry/_types.py`, `acquire/{events,domain,_cross_seed_store}.py` — docstring mentions.
- `personalscraper/web/models/acquisition.py:586,622` — docstrings + dead exclusion (D3).
- `personalscraper/web/routes/acquisition_ranking.py:96-110` — sample rewrite (D4) ⇒ `make openapi`.
- `frontend/src/components/config/SecretsTab.tsx` + tests + `schema.d.ts` (regen).
- `config.example/tracker.json5` — block + comments.
- `docs/reference/lacale-api.md` DELETE; `architecture.md`, `c411-api.md`, root `CLAUDE.md` line — purge.
- Tests: rewrite per D9.

## 4. Testing

- Registry: activation/factory tests assert lacale is UNKNOWN (factory raises its
  standard unknown-tracker error) and absent from listings.
- Historic-data guard: regression test feeding a store row with
  `source_tracker="lacale"` through the read paths that render it (obligations
  read-model, provenance, cross-seed store) — renders as plain string, no crash.
- D8/D10 grep gates as executable ACCEPTANCE criteria.
- Full `make check` + frontend gates + openapi drift green.

## 5. Suggested phases

1. Backend removal (client, factory, activation, enum + all module refs) + test rewrites (D9) + historic-data regression test.
2. Web + frontend (models/routes samples, SecretsTab, `make openapi` regen) + config.example + docs purge.
3. ACCEPTANCE (grep gates D8/D10 + criteria) + full gate.

## 6. Out of scope

- Live-config cleanup (post-merge operator step, D6) and any DB row rewrite (D2).
- Adding/retiring any OTHER tracker; Torr9 gets only its zero-remnant proof.
