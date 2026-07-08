# Config Editor — Implementation Plan Index

**Codename**: `config-editor`
**Design**: `docs/features/config-editor/DESIGN.md`
**Branch**: `feat/config-editor`
**SemVer**: 0.42.0 → 0.43.0 (minor — already applied at create-branch)

## Phases

| #   | Phase                                       | File                                                           | Status |
| --- | ------------------------------------------- | -------------------------------------------------------------- | ------ |
| 1   | Config validation seam + envfile extraction | [phase-01-conf-seam.md](phase-01-conf-seam.md)                 | [ ]    |
| 2   | Backend config API routes                   | [phase-02-backend-routes.md](phase-02-backend-routes.md)       | [ ]    |
| 3   | Frontend SchemaForm + /config page          | [phase-03-frontend-editor.md](phase-03-frontend-editor.md)     | [ ]    |
| 4   | Integration gates + docs + acceptance       | [phase-04-integration-gates.md](phase-04-integration-gates.md) | [ ]    |

## Deliverables map (DESIGN §8)

| Deliverable                                                                                | Phase |
| ------------------------------------------------------------------------------------------ | ----- |
| `personalscraper/conf/`: ContextVar seam, `validate_candidate`, `envfile.py`               | 1     |
| `personalscraper/web/routes/config.py` + models + restart-impact map + tests               | 2     |
| `frontend/`: SchemaForm + `/config` page + nav enable + tests                              | 3     |
| `make openapi` regenerated (`frontend/openapi.json` + `schema.d.ts`)                       | 4     |
| `ecosystem.config.js`: staging `PERSONALSCRAPER_WEB_ROLE`, prod `PERSONALSCRAPER_PM2_NAME` | 4     |
| Docs: `web-ui.md`, `config-overlay-layout.md`, `runbook-post-merge.md`                     | 4     |
| ACCEPTANCE shell criteria                                                                  | 4     |

## Commit convention

All commits use scope `(config-editor)`. Format: `<type>(config-editor): <description>`.
Each sub-phase = 1 commit.
