# Phase 07 — PR fixes cycle 1 (review findings, PR #311)

## Gate

- [ ] Phases 1–6 complete, PR #311 open, CI green on fadca5b3.
- [ ] Frontend + backend gates green at baseline.

Retained findings from 4 review agents (code CM-*, tests T#*, comments #N, silent-failures A/B/C/D/E),
filtered vs DESIGN. No design contradictions. NO route/nav additions beyond this wave's scope.

### Sub-phase 7.1 — Backend honesty + robustness (staging.py + models + tests)

**Commit:** `fix(control-medias): honest discard/continue failure surfaces + journal integrity`

1. **B1** — wrap the `shutil.move` in try/except: on failure best-effort-remove a partial destination,
   then raise HTTPException 500 with FR detail naming the path and error class (« Échec de la mise en
   quarantaine de <name> : <ErrClass>. Aucun journal écrit. »). Journal write stays strictly AFTER a
   successful move.
2. **B2+B3 (§7)** — journal `detail` becomes
   `f"Discard non-media artifact: {media_dir.name} -> {quarantine_path}"` (destination recorded; the
   collision-suffixed path is unique per request) and the read-back matches on `detail == that exact
   string` (no stale-row false positive) over `list_recent(..., limit=20)`.
3. **B4 (§6)** — refuse-before-destroy extended: before moving, probe the journal is actually writable
   (try `record_destruction`-style connect + `SELECT 1 FROM destructive_op LIMIT 1` in a helper; on
   failure → 503 FR « Journal des suppressions indisponible — suppression refusée. »). db_path None
   keeps its 503.
4. **A3** — distinguish unreadable NFO: when `find_nfo` returns a path but parsing yields empty
   metadata AND the file exists with content, log a WARNING (`staging.continue_nfo_unreadable`) and
   use 422 detail « NFO illisible pour ce média — vérifiez le fichier <name>.nfo. » (keep the current
   detail for genuinely-absent NFO/ids).
5. **A1 (§8, CRITICAL)** — durable deferral trace: when `spawn_pipeline_run` returns None, write a
   marker file `<media_dir>/.continuation-requested` containing the epoch ts (overwrite ok). Read
   model: expose `continuation_requested_at: float | None` on StagingMediaItem — value from the marker
   IF no pipeline_run with `started_at > marker_ts` has completed since (else treat as consumed and
   best-effort unlink the marker). The scanner/verify are NOT touched (display-only semantics).
6. **Docstrings/models (#1, #2, #6, CM-5)** — remove the `timeline_resumes` sentence
   (ContinueResponse); fix DiscardResponse prose (quarantine_path is ALWAYS set on success — no
   "emptied in-place" path; keep the field optional for schema stability, say why); discard docstring
   « the AUTRES category — items the sort could not type » + 404 wording notes non-eligible kinds;
   404 detail string stays but docstring names the eligible kind precisely.
7. **Tests** (extend tests/web/test_staging_media.py):
   - T#2: `PERSONALSCRAPER_WEB_ROLE=staging` → 403 for continue AND discard, folder untouched.
   - T#1: quarantine collision → `_1` suffix (and `_2` on second collision), folders land correctly.
   - T#5: NFO present but no provider ids → 422 (seed an NFO without uniqueids).
   - B1: move failure (monkeypatch shutil.move to raise) → 500 FR detail, no journal row.
   - B2: read-back matches the fresh row only (seed an OLD row with the same source path but a
     different destination in detail → journaled must still be True via the exact-detail match;
     and the journal-failure test keeps asserting the ATTENTION path).
   - A1: deferred continue writes the marker; read model exposes `continuation_requested_at`;
     a completed run started after the marker clears it.
   - discard 503 when db_path None (existing?) + when journal unwritable (new).
8. `make openapi` + commit regenerated files in the same commit (models changed).

**Gate:** `make lint && make test` + `python -c "import personalscraper"`.

### Sub-phase 7.2 — Frontend honesty (Contrôle/Médias error channels + §7 toasts + tests)

**Commit:** `fix(control-medias): error states on Contrôle panels + honest §7 toasts`

1. **C1 (CRITICAL)** — CompactHealth disks row reads `disksQuery.isError` → danger dot + « Disques —
   état indisponible » before the empty-state branch (mirror DisksPanel's error handling).
2. **C2** — providers row: registry query error → danger dot + « Fournisseurs — état indisponible »
   (never « aucun configuré » on error).
3. **C3** — redis/index rows: when the underlying query ERRORS (API unreachable), label
   « API injoignable » (danger) instead of « Redis hors ligne » / « Index dégradé ».
4. **C4/C5** — `useLastPipelineRun` exposes `isError`; Dashboard renders an error card
   (« Historique indisponible ») for the digest AND an explicit error line for « Ce qui n'a pas
   avancé » (StalledPanel absence must be distinguishable: only render nothing when the query
   SUCCEEDED with zero reasons).
5. **D1 (§7)** — IgnoreDiscardButton: branch on `data.journaled === false` → `toast.warning`
   (danger-tinted) with the verbatim ATTENTION detail; success stays `toast.success(detail)`.
6. **D2** — Medias `?decision` load failure (non-410): FR toast « Décision introuvable ou
   inaccessible. » before deselecting.
7. **D3** — `?media=` not found in the current page: render an explicit inline notice
   « Média introuvable sur cette page — ajustez les filtres ou la recherche. » (honest exit; do not
   silently ignore the param).
8. **A2** — after a non-deferred continue success, poll `GET /api/pipeline/history` (existing hook/
   query) for the promised `run_uid` for ~10s; if absent → `toast.warning` « Le run promis n'a pas
   démarré — consultez les journaux. »
9. **A1 UI** — sheet + ATraiterList row: when `continuation_requested_at` is set, show chip
   « Reprise demandée » (with relative time) — the §8 durable trace surfaced.
10. **Tests**: T#4 verbatim toast contracts (mock sonner; success + ATTENTION variants, continue
    both branches); T#3 Sidebar collapsed hides Version (+ assert the value renders when expanded);
    T#6 invalidation contracts (spy invalidateQueries: 3 keys continue / 1 key discard);
    T#7 useLastPipelineRun hook test (queue-step exclusion + counts + isError); LegacyRedirect
    « replace » test made real or its claim dropped; IgnoreDiscardButton asserts dialog closes;
    C1/C2/C4/C5 error-state tests; D3 notice test; A1 chip test.

**Gate:** `cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run`.

### Sub-phase 7.3 — Comment/doc corrections + records

**Commit:** `docs(control-medias): comment accuracy sweep from review cycle 1`

- #3 LegacyRedirect: fix the repo URL (IznoCorp/torrent-mate) and replace the fabricated quotation
  with the real DOIT-10 text (« Retrouvable. Chaque détail a son URL ; Retour ferme ce qu'il doit
  fermer. »).
- #4: the server-side `position` param follow-up is RECORDED in IMPLEMENTATION.md « Open items » in
  this commit; reword the 3 comments to point at that record.
- #5 Dashboard docblock renumbered (7 panels incl. LastRunDigest, DESIGN §2.1 order); dedupe the two
  « 4. » inline comments.
- #7 unify relocation origin phrasing (« from the former /scraping page (now /medias) ») in
  Dashboard.tsx + ScrapeActivityPanel.tsx.
- #8 PipelineControls « six actions » → five (run/pause/resume/kill/watcher).
- #9 nav.ts stale `(Registre → S6)` example reworded.
- #10 useAcquisition `queryOptions` doc: the AppShell badge DOES pass options — fix the claim.
- #11 nits: ATraiterList « contrary to the original plan » softened; LastRunDigest null claim;
  StagingMediaDetail « label is the only difference » precised; StalledPanel key comment fixed.
- CM-4 BottomTabBar stale « Scraping » comments (3×) → Médias.

**Gate:** frontend gates + `make lint` (comments only, but keep the loop honest).

## Open items recorded for operator arbitration (§méthode rule 4 — carried + new)

- Server-side `position`/`awaiting` filter param for /api/staging/media (pagination-correct segments;
  C6/CM-2 cap of 100 + page-scoped filtering) — recorded here as THE tracking record.
- B5 quarantine TOCTOU nesting (single-writer topology makes it theoretical).
- E: ScrapeActivityPanel drift-guard converts schema-drifted 200s to calm-null without logging
  (OpenAPI CI gate is the compensating control).
- A2 deeper variant: reconciling promised run_uids server-side (a web-side « promised runs » ledger).
