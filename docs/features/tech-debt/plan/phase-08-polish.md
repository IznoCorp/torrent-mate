# Phase 8 — Polish + nice + ACCEPTANCE.md

**Effort** : 2-3 jours
**Theme** : completer les should-have restants + produire ACCEPTANCE.md exécutable.

## Gate

- Phase 1-7 commited + gates verts
- Branch prête pour PR / merge

## Sub-phases

### 8.1 Cron backfill-ids (SH-3 / BD-S)

**Site** : `launchd-plists/` (existant) — ajouter `com.personalscraper.backfill-ids.plist`

**Contenu** : invocation hebdomadaire `personalscraper library-index --mode backfill-ids
--budget-seconds 1800`. Log dans `~/.cache/personalscraper/backfill-ids.log`.

**Commit** : `feat(tech-debt): launchd plist for weekly backfill-ids (SH-3)`

### 8.2 Audit `pending_op` + `item_issue` (SH-6 / BD-U + BD-V)

**Action** : grep callers.

- Si `pending_op` 0 callers → DROP via migration 007 (ou laisser, low priority).
- Si `item_issue` 0 callers ou seulement les sites mentionnés en item 7 (`release_linker.py:322`,
  `library/analyzer.py:112`+282) qui DOCUMENT le pattern mais n'insèrent rien → marquer comme
  "design intent, not yet wired" + créer issue 0.17+ pour câbler.

**Commit** : `chore(tech-debt): audit pending_op + item_issue tables (SH-6)`

### 8.3 `qbit-restart` command (SH-14 / CL-B / DEV #20)

**Option A** : implémenter — invoke `launchctl unload + launchctl load
~/Library/LaunchAgents/com.qbittorrent.plist` (ou équivalent).

**Option B** : supprimer la mention dans matrix v2.1 § INGEST recovery, remplacer par
"operator manual qBit restart via launchctl".

Décision pendant Phase 8 selon difficulté A.

**Commit** (option A) : `feat(tech-debt): qbit-restart CLI command (DEV #20)`
ou (option B) : `docs(pipeline-monitor): matrix v2.1.1 — remove qbit-restart reference (DEV #20)`

### 8.4 Audit dead infrastructure (SH-17 / CF-G / P11)

**Script** : `scripts/audit-dead-infrastructure.py` (nouveau)

**Scope** :

- Tables avec 0 rows depuis init (`deleted_item` post-Phase 1 fix : devrait avoir des rows ;
  `item_issue` ; `pending_op`)
- Colonnes never populated (sortie : col + table + count NULL)
- Functions définies, jamais appelées : grep + AST analysis
- Protocols définis, jamais utilisés

Sortie : rapport markdown `docs/features/tech-debt/audit/12-dead-infrastructure.md` listant
chaque candidat à drop ou à câbler.

**Commit** : `chore(tech-debt): audit dead infrastructure script + report (SH-17)`

### 8.5 Expose `clean` + `cleanup` CLI sub-commands (SH-21 / AR-C)

**Site** : `personalscraper/commands/pipeline.py` — ajouter deux nouvelles commandes.

**Implementation** : wrappers Typer qui invoquent les sous-fns de `process/run.py`. Coût
faible. Permet debugging + composition.

**Commit** : `feat(tech-debt): expose clean + cleanup CLI sub-commands (AR-C)`

### 8.6 Trailers verify rename alias (SH-22 / AR-D)

**Site** : `personalscraper/trailers/cli.py`

**Implementation** : ajouter `@app.command("audit")` + alias deprecation `@app.command("verify")`
qui print warning + redirige vers `audit`. Retirer dans 0.17+.

**Commit** : `feat(tech-debt): trailers audit alias for trailers verify (AR-D)`

### 8.7 Pin commands tests (SH-25 / CL-S)

**Site** : `tests/cli/test_pinned_commands.py` (nouveau)

**Scenario** : pour chaque commande exposée (extraite via `personalscraper --help` parse),
un test pin existence + signature de base (1 param obligatoire / option ; --help exit 0).

Évite régressions silencieuses (commande qui disparaît en refactor).

**Commit** : `test(tech-debt): pin existence + help of every exposed CLI command (SH-25)`

### 8.8 Audit modules sans CLI (SH-26 / BD-H / CL-K extension)

**Script** : `scripts/audit-cli-coverage.py` (étendu de la version Phase 2.5)

Pour chaque module métier critique (`library/`, `indexer/`, `scraper/`, `trailers/`,
`ingest/`, `sorter/`, `dispatch/`, `verify/`, `enforce/`), vérifier qu'au moins UNE commande
CLI l'invoke en E2E.

**Commit** : `test(tech-debt): audit modules CLI coverage (SH-26)`

### 8.9 Produce ACCEPTANCE.md

**Site** : `docs/features/tech-debt/ACCEPTANCE.md` (nouveau)

**Format** : reprend les 15 criteria de DESIGN.md §6, expand chacun en :

```markdown
### ACCEPTANCE-N : <description>

**Criterion** : <human readable>
**Validation command** : `<exact shell command>`
**Expected output** : <expected result>
**Source items** : MUST-X, SH-Y, CF-Z (provider-ids), etc.

✅ / ❌ / 🟡 — status post-Phase 8
```

À cocher au moment de la phase gate de chaque phase.

**Commit** : `docs(tech-debt): ACCEPTANCE.md executable criteria (CF-J)`

## Phase 8 Gate (= PR gate)

- [ ] 8.1 cron entry present
- [ ] 8.2 pending_op + item_issue audit done
- [ ] 8.3 qbit-restart decided (A or B)
- [ ] 8.4 dead infrastructure audit report committed
- [ ] 8.5 `personalscraper clean` + `cleanup` exposed
- [ ] 8.6 `trailers audit` alias works
- [ ] 8.7 pin commands test PASS
- [ ] 8.8 audit-cli-coverage exit 0
- [ ] 8.9 ACCEPTANCE.md complete with all 15 criteria ✅
- [ ] `make check` vert
- [ ] `personalscraper library-doctor` exit 0 sur DB prod post-toutes-phases
- [ ] PR ready

**Phase gate commit** : `chore(tech-debt): phase 8 gate — polish + ACCEPTANCE complete`

**PR creation** : suite Phase 8 gate, lancer `/implement:feature-pr` (auto par
`/implement:phase` à la last phase) puis `/implement:pr-review`.
