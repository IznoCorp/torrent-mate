# Phase 19 — Fix `config.example/providers.json5` template

Created from `/pr-review-toolkit:pr-review` audit (2026-05-27). The template
triggers `locked_capability_orphan` when used as-is:

```
$ personalscraper info providers --config config.example/providers.json5
RegistryConfigError — provider config is invalid:
  [locked_capability_orphan] section=KeywordProvider provider=tvdb: …
```

Phase 15 fixed this in `tests/fixtures/config.py` (with explanatory comment) but
the fix was never propagated to the user-facing template.

## Gate

- Phases 7–18 complete.
- `personalscraper init-config` exists.

## Goal

Make `config.example/providers.json5` boot cleanly with dummy credentials so
`personalscraper init-config && personalscraper info providers` succeeds out of
the box on a fresh clone.

## Scope

- `config.example/providers.json5` (1 file).
- Optional: `config.example/.env.example` if it needs updating to mention which
  envvars unblock which providers.

## Sub-phases

### 19.1 — Patch the template

Set `KeywordProvider: {}` (matching the fix Phase 15 applied to test fixtures),
and add a one-paragraph comment explaining why a non-empty locked section
without IDCrossRef triggers `locked_capability_orphan`. Reference the test
fixture decision for traceability.

Commit: `fix(config): empty KeywordProvider in template avoids locked_capability_orphan`

### 19.2 — Verify the template boots end-to-end

```bash
rm -rf /tmp/registry-template-smoke
mkdir /tmp/registry-template-smoke
cp -r config.example /tmp/registry-template-smoke/config
TMDB_API_KEY=dummy TVDB_API_KEY=dummy personalscraper info providers \
    --config /tmp/registry-template-smoke/config/providers.json5
```

Expected: exit 0, lists all configured providers with circuit state CLOSED.

If the smoke test reveals additional template gaps (e.g. missing IDCrossRef
section): patch + commit again in this sub-phase.

Commit (only if additional changes needed): `docs(config): document template
smoke-test procedure in plan`

## Phase gate

- `personalscraper info providers --config config.example/providers.json5`
  exits 0 with dummy credentials.
- No new `RegistryConfigError` surfacing when the template is used directly.

## ACC criteria touched

- ACC-04a + ACC-05b indirectly (Phase 20 re-pins these to use the template).

## Cost estimate

- 5 min DeepSeek (single file edit + smoke test).

## Risk

Minimal. One-line config change validated by smoke test.
