# Phase 05 — PR fixes cycle 1 (review findings, PR #317)

## Sub-phase 5.1 — Code fixes

**Commit:** `fix(systeme-hub): honest outcome fallbacks, canonical redirects, valid DOM, gated auto-select`

1. **F1 (HIGH, §8)** — `lib/outcome-labels.ts`: `outcomeLabel()`/tone fallback for a NON-NULL unmapped
   token = the RAW TOKEN (neutral tone); « Jamais exécuté » ONLY for null/undefined. Docstring reworded.
2. **F2 (MEDIUM)** — `RunHistoryTable.tsx` + `RunDetail.tsx`: unmapped non-null outcome renders the
   raw token in the badge; « — » reserved for null.
3. **Cross-link (82)** — `RunDetail.tsx:400`: `to="/systeme?tab=maintenance"`; both stale comments
   (Maintenance.tsx references) rewritten; `RunDetail.test.tsx:316` retargeted.
4. **F3 (MEDIUM)** — redirects canonical + honest: router `/registry` → `LegacyRedirect to="/systeme"`
   (no query in `to` — kills the double-`?`); `MaintenanceRunRedirect` bare branch → `/systeme`
   (clean canonical, lands on default État). Update router tests: the /registry extra-param test must
   assert PARSED params (`searchParams.get("extra")`) — the current `toContain` certifies a broken URL.
5. **F4 (MEDIUM)** — `config/FileList.tsx`: no button-inside-button. Valid structure (row becomes
   `div role="button" tabIndex={0}` with key handling, or badge toggle moved out of the row button);
   tap disclosure + aria-expanded behavior preserved.
6. **F5 (MEDIUM)** — `Config.tsx` auto-select effect gated on `leftTab === "files"`; comment at ~572
   updated (the clear is now durable).
7. **CompactHealth** — 3 links `to="/systeme"` (direct, no redirect hop), « Registre → » relabelled
   « Fournisseurs → », docblock updated.

## Sub-phase 5.2 — Test hardening

**Commit:** `test(systeme-hub): pin unified labels, circuit badges, restart hint, FR secrets`

- `RunDetail.test.tsx`: error-run asserts « Échec » (exact), new killed-run case asserts « Interrompu »
  (kills the PROVEN surviving mutant).
- `SystemePage.test.tsx`: providers closed+open → « OK » and « Ouvert » badges (+ `/43 ms/`).
- New FileList test (or Config case): tap the restart chip → microcopy « Redémarrage requis après
  modification » visible + aria-expanded flips; second tap closes.
- `SecretsTab.test.tsx`: EN description in, FR (« Clé API TMDB ») rendered.
- outcome-labels suite: unknown non-null token → raw token (both label and consumers' contract);
  `STATUS_LABEL.killed === "Arrêté"` plan-mandated assertion (meta or module-neighbor test).
- `WatcherPanel.test.tsx`: recent-run outcome "error" renders « Échec » (third-surface consumer pin).
- Router tests: updated destinations (/systeme clean) + parsed-param assertions per 5.1.4.

## Sub-phase 5.3 — Docs sweep (comment + reference truth)

**Commit:** `docs(systeme-hub): comment accuracy sweep + reference docs truth pass`

- `Config.tsx`: module docblock (sibling tabs layout), ~200 « Left sidebar » misnomer, ~240 quoted
  dead copy.
- `nav.ts`: Configuration section comment (Registre gone), Système comment enriched.
- `SystemePage.tsx`: TAB_IDS parenthetical, ProvidersPanel inlined note, chronology fix.
- `MaintenanceRunRedirect.tsx`: rationale sentence + new target documented.
- `outcome-labels.ts`: exception note (acquisition STATUS_LABEL keeps `killed: "Arrêté"` — item
  status, not a run outcome) + fallback contract wording.
- `obligation_titles.py`: directory pass-through rationale corrected (endswith guard is the mechanism).
- `docs/reference/web-ui.md` (:569, :634+, :1054, :1123, :1129) + `docs/reference/maintenance.md`
  (:347): update the active present-tense claims to the /systeme reality (git add -f for docs/).

## Recorded open items (§méthode rule 4 — operator arbitrage)

- F6: journal read-failure copy « momentanément » + quiet styling (pre-existing DestructiveLogPanel).
- F7: État panel errors styled like calm notes; EventFeed can't distinguish WS-dead from no-events
  (pre-existing); legacy /maintenance journal bookmark lands on État (journal is one tab away).
- Stale `&run=` kept on tab switch (mirrors the sanctioned AcquisitionPage pattern).

## Sub-phase 5.4 — Arbitrated open items (operator directive 2026-07-17)

**Commit:** `fix(systeme-hub): loud read-error states + legacy /maintenance lands on the journal`

1. **Journal read failure (ex-F6)** — `DestructiveLogPanel.tsx`: the failure branch becomes a real
   error state: `role="alert"`, danger tone, honest wording without the unverifiable
   « momentanément » (e.g. « Impossible de lire le journal des suppressions. ») + the error detail
   or a retry affordance; still clearly distinct from the EmptyState. Tests updated.
2. **État panels read failure (ex-F7)** — `DisksPanel.tsx`, `LocksPanel.tsx`,
   `IndexHealthPanel.tsx`: « Erreur lors du chargement. » branches get `role="alert"` + danger
   styling so a dead API never reads at the same volume as a calm note. Tests updated.
3. **Legacy /maintenance bookmark (arbitrated)** — `MaintenanceRunRedirect.tsx`: the bare branch
   redirects to `/systeme?tab=journal` (the old page carried the journal inline; the operator's
   bookmark must land where the journal is). `?run=` teleport unchanged. Router tests + docblock
   updated (web-ui.md line if it states the bare destination).
