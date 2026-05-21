# Phase 2 — Design vs reality reconciliation

**Goal** : Close the gap between provider-ids documentation and code reality. Decide on monolithic Protocols, truth-up ACCEPTANCE.md, wire the post-process auto-backfill the DESIGN promised.

## Gate (in)

- Phase 1 complete (all 4 sub-phases committed, `make check` green)
- `personalscraper indexer backfill-ids` invokable from CLI
- Open questions Q1, Q2, Q4 from DESIGN §8 resolved (user decisions)

## Gate (out)

- ACCEPTANCE.md rows #3 / #6 / #9 rewritten with verifiable shell commands
- Each rewritten row re-runs cleanly on the live instance
- Monolithic Protocols either dropped (Option A) or formally documented as compat shims (Option B)
- Auto-backfill trigger fires after `process` when a gap is detected
- DEVIATIONS.md gitignore policy applied (committed transparent OR moved private)

## Sub-phases

### 2.1 — Monolithic Protocols decision (C3)

**Files** :

- `personalscraper/api/metadata/_base.py:267` (`class MetadataProvider(Protocol)`)
- `personalscraper/api/torrent/_contracts.py:124` (`class TorrentClientFull(Protocol)`)
- `tests/unit/test_api_metadata_base.py`
- DESIGN §4 doc + ACCEPTANCE #6 wording

**Decision required** (Q1) :

- **Option A — Drop both** : delete the Protocols, update the factory in `api/torrent/_factory.py` (currently returns `TorrentClientFull`), update tests, sweep callers. High blast radius, restores design conformity.
- **Option B — Keep as compat shims** : amend DESIGN §4 and ACCEPTANCE #6 to call them "umbrella Protocols for callers composing all atomic capabilities". Update stale module docstrings. Lower risk.

**Recommendation** : Option B for a PATCH release. Document the boundary clearly.

**Commit** : `refactor(tech-debt): document monolithic Protocols as compat shims` (Option B) OR `refactor(tech-debt): drop monolithic MetadataProvider + TorrentClientFull Protocols` (Option A)

### 2.2 — ACCEPTANCE.md truth-up + DEVIATIONS.md policy

**Files** :

- `docs/archive/features/provider-ids/ACCEPTANCE.md`
- `.gitignore` (DEVIATIONS.md entry)
- `docs/archive/features/provider-ids/plan/DEVIATIONS.md` (the file itself)

**ACCEPTANCE rewrite** : for each row, replace the prose evidence with a verifiable shell command. Examples :

```
| 3 | backfill-ids walks library | personalscraper indexer backfill-ids --dry-run → BackfillStats summary |
| 4 | DB schema unified | sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE external_ids_json != '{}'" returns > 0 after library-index |
| 6 | no monolithic Protocol | grep -rn "class MetadataProvider" personalscraper/ || echo "OK"  (after Option A) |
```

Re-run every command on the live instance ; record the actual output in a new `ACCEPTANCE-validation.md` sibling.

**DEVIATIONS.md policy** (Q4) :

- **Option A — Commit it** : remove from `.gitignore`, audit trail transparent in git history
- **Option B — Move to ~/.claude/projects/...** : private observer notes, no audit drift

**Commit** : `docs(tech-debt): truth-up provider-ids ACCEPTANCE + DEVIATIONS policy`

### 2.3 — Auto-backfill trigger after process (I5)

**File** : `personalscraper/process/run.py` or `personalscraper/commands/pipeline.py::process`

**Wiring** :

- After `run_process` completes (no error), check `media_item` for rows with empty `external_ids_json` or `ratings_json`
- If gap detected, invoke `run_backfill_ids` with `--ids-only` and `--ratings-only` flags as appropriate
- Trigger scope (Q2) : only on shows touched by this process run (narrow) OR full library sweep (broad)

**Recommendation** : narrow — only items whose NFO was just regenerated (track via `dispatch_path` or scan output).

**Regression test** :

- Process a fixture with broken external_ids_json
- Assert post-process : column populated correctly

**Commit** : `feat(tech-debt): auto-trigger backfill-ids after process when gap detected`

## Definition of done

- 3 commits on `fix/tech-debt`
- `make check` green
- `docs/archive/features/provider-ids/ACCEPTANCE.md` reviewed and updated — every row has a verifiable command
- `docs/archive/features/provider-ids/ACCEPTANCE-validation.md` new file with command outputs from live instance
- `make test` includes a new `tests/integration/test_auto_backfill.py`
