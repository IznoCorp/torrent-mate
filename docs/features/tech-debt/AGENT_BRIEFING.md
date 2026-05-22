# Tech-Debt 0.16.0 — Agent Briefing

> **READ FIRST** — Ce briefing complète le contexte fourni par `/implement:sub-phase`. Lis-le
> AVANT d'attaquer la sub-phase qu'on t'a assignée. Il couvre les règles cross-cutting +
> risques spécifiques à tech-debt 0.16.0 que le template `/implement:sub-phase` ne mentionne
> pas. Document statique : ne nécessite PAS de mise à jour entre phases.

---

## 1. Read order pour une sub-phase

Lis dans cet ordre :

1. **Ce briefing** (`AGENT_BRIEFING.md`) — règles transverses, baseline BDD, gotchas
2. **CLAUDE.md projet** (`/Users/izno/dev/PersonnalScaper/CLAUDE.md`) — règles dures
   (rg/curl safety, commit convention, phase gate checklist)
3. **Le phase file** entier (`plan/phase-NN-*.md`) — pas seulement la sub-phase, le contexte
   global de la phase aide à comprendre les dépendances inter-sub-phase
4. **La sub-phase target** uniquement (scope bound)
5. Pour comprendre le pourquoi : `audit/` et `DESIGN.md` (lecture optionnelle, généralement
   pas requise — le plan body explique le POURQUOI)

---

## 2. État courant de la branche (snapshot 2026-05-23)

- **Repo personalscraper** : `/Users/izno/dev/PersonnalScaper`, branche `fix/tech-debt`
- **Repo .claude/** : `/Users/izno/dev/PersonnalScaper/.claude` (sous-repo séparé), branche `personal-scraper`
- **4 commits fix déjà SHIPPED** sur `fix/tech-debt` (NE PAS re-fixer) :
  - `268cbee` DEV #9 — `repair_root_duplicate` inversion (data-loss)
  - `29c4953` DEV #11 — `compute_merkle_root` déterministe
  - `fc39f77` DEV #13 — `_recreate_indexes` C5 race idempotent
  - `3993487` DEV #14 — `_build_disk_fingerprints` oshash filter alignment
- **Baseline tests** : 4521 passed, 0 failed (mesuré 2026-05-22)
- **Baseline `make lint`** : clean
- **Baseline `library-reconcile`** : `merkle_drift=[]`, `dispatch_path_missing=0`,
  `enrich_stale=0`, `release_orphans=0`, `items_without_files=0`, mais
  `files_without_release=5376` + `season_count_drift=3` (dette connue, adressée Phase 4)

**Si tu trouves tes baseline différentes de ces chiffres** : check `git log` pour voir
les commits depuis 2026-05-23, ou run `personalscraper library-reconcile` pour comparer.
Si l'écart est important et non expliqué, STOP et reporter.

---

## 3. Cross-repo : Phase 0 manuelle

**Phase 0** (`phase-00-skill-safety.md`) commit sur `.claude/` branche `personal-scraper`,
PAS sur `fix/tech-debt`. `/implement:phase` ne sait pas faire de cross-repo dispatch. Si tu
es dispatché pour Phase 0 par erreur, STOP et reporter `BLOCKED: cross-repo dispatch not
supported, Phase 0 must be executed manually by operator on .claude/`. Voir banner dans
`phase-00-skill-safety.md` pour la procédure manuelle.

Tous les autres sub-phases (Phase 1.x à 9.x) sont sur `personalscraper/fix/tech-debt`.

---

## 4. Plan A backfill : action manuelle entre 1.9 et 1.10

Sub-phase 1.9 commit `init-canonical` CLI. **APRÈS** ton commit 1.9, l'opérateur (PAS toi)
lance Plan A en arrière-plan via une procédure manuelle documentée dans le phase file.
Ton report doit indiquer "DONE — Plan A launch pending operator" si la sub-phase 1.9 est
ta cible. NE PAS essayer de lancer Plan A toi-même via nohup.

`/implement:phase` qui orchestre va respecter cette dépendance (cf. handoff note dans
phase-01-foundations.md entre 1.9 et 1.10).

---

## 5. Phase 5 : ordre logique aligné numérique (post 2026-05-23 renumber)

L'ordre N.M est désormais l'ordre d'exécution correct :

- 5.1 : refactor tests Protocol (préparation)
- 5.2 : migrate TorrentClientFull callers (préparation)
- 5.3 : Pydantic ratings boundary (scope-creep indépendant)
- 5.4 : DROP monolithic Protocols (consomme 5.1 + 5.2)
- 5.5-5.8 : library-gc, library-doctor, docs

Si tu vois Phase 5.4 et que 5.1 + 5.2 ne sont pas commit, STOP — il y a une régression
dans l'orchestration.

---

## 6. Test discipline (rappels critiques)

### 6.1 — Test ERROR ≠ test FAILED

`make test` summary line peut ressembler à :

- `4521 passed, 0 failed, 4 skipped` ✓ OK
- `12 passed, 3 failed, 0 errors` → BLOCKED (3 vrais échecs)
- `5 passed, 0 failed, 1 error` → **CRITIQUE** : l'import a crashé, TOUT le reste est
  silencieusement skippé. Fix les imports AVANT de claim DONE.

**Toujours read the summary line + le bloc ERRORS si présent.**

### 6.2 — Regression test per bug (memory rule)

Chaque DEV fix DOIT avoir un test de régression dédié dans le même commit, qui :

1. **Reproduit** le bug s'il n'était PAS fixé (test fail sans le code fix)
2. **Pin** le contrat attendu (nom de fonction explicite, scenario clair)

Si tu fix DEV #18 sans test régression, ton report doit être `DONE_WITH_CONCERNS:
missing regression test`.

### 6.3 — Cross-caller grep AVANT claim "X supprimé / Y migré"

Pattern P2 (chaîne de découverte) : un fix qui passe ses propres tests unitaires n'est
PAS forcément complet. Pour tout refactor "drop" / "rename" / "migrate" :

```bash
rg -n --type py "<symbole_supprimé>" personalscraper/ tests/
# Expected: 0 hits hors-fichier de définition
```

**Joindre la commande + sortie dans le commit message** pour traçabilité.

### 6.4 — `make check` évolue durant les phases

- Avant Phase 1.10 : `make check` = lint + test + module-size + typed-api
- Après 1.10 : `make check` inclut aussi `check-pragma-discipline.py`
- Après 8.11 : `check-module-size.py` devient hard-block (était advisory)

Ne pas paniquer si `make check` n'inclut pas un check qui sera ajouté plus tard — ton job
est de faire passer le `make check` au moment où tu lances.

---

## 7. Hooks et règles dures (rappel CLAUDE.md)

Le harness Claude Code a des hooks PreToolUse qui bloquent certaines actions :

- `block_curl_without_timeout` — `curl/wget` MUST avoir `--connect-timeout 10 --max-time 30`
- `block_background_pipeline` — `personalscraper run` MUST être foreground (`timeout=600000`)
- `block_ai_attribution` — commits ne doivent PAS contenir "Co-Authored-By", "Claude",
  "Anthropic", "AI"

**`rg` MUST avoir `--type py` ou `-g '*.py'`** (machine crash safety — `tests/e2e/perf/.fixture/`
fait 14 GB de binaires, `rg` sans type filter peut consommer toute la RAM).

---

## 8. Memory rules à respecter (préférences user durables)

Issues de `~/.claude/projects/-Users-izno-dev-PersonnalScaper/memory/MEMORY.md` :

- **Communication en français** : si tu interagis avec l'utilisateur (rare en sub-phase
  dispatch). Code/docstrings en anglais.
- **Pipeline always --dry-run first** : pour chaque step pipeline (ingest/sort/process/...),
  dry-run avant real, show output, ask validation, puis real. **Ne PAS applicable à
  `library-index --mode backfill-ids`** (read-only contre API).
- **NO DEFERRAL absolu** : aucun DEV / SH / CF item ne peut être différé hors 0.16.0. Si
  tu rencontres un blocker, STOP et report — ne pas marquer "TODO 0.17+".
- **Test de régression par bug** : déjà couvert §6.2.
- **Pas de retro-compat avant v1.x** : 0.16.0 < 1.0 ⇒ pas de scripts de migration, pas
  de feature flags, pas de deprecation alias (sauf cas explicite comme `trailers verify`
  → `trailers audit` Phase 8.6, justifié dans le plan).

---

## 9. Validation post-commit obligatoire

Avant de marquer une sub-phase DONE :

1. **Smoke import** : `python -c "import personalscraper"` exit 0
2. **Quality gates** : `make check` vert (ou `make lint` + `make test` si check pas encore
   updated)
3. **Si tu as touché un module BDD/scanner/indexer/scraper/dispatch** : run
   `personalscraper library-reconcile` et compare aux baseline (§2). Toute régression =
   `DONE_WITH_CONCERNS` minimum.
4. **Si tu as supprimé / renommé une API publique** : cross-caller grep §6.3, joindre au commit
5. **Si tu as ajouté une migration SQL** : check `PRAGMA user_version` bump + `schema_version`
   row insert. Test que `apply_migrations()` peut tourner deux fois sans erreur (idempotence).

---

## 10. Quand reporter BLOCKED

- Une sub-phase dépend d'une autre non encore committée (orchestration glitch)
- `make check` échoue après 2 tentatives de fix
- Un test ERROR (collection cassée) que tu ne peux pas réparer
- Un audit FK orphan check (`PRAGMA foreign_key_check`) retourne des rows et tu ne
  comprends pas pourquoi (peut bricker le boot — voir Phase 1.2)
- Tu détectes un nouveau DEV non listé dans les 54 audités

Format : `Status: BLOCKED`, explique précisément l'obstacle, ne JAMAIS forcer le commit
"pour avancer". Le main session (Opus) reprendra avec toi.

---

## 11. Skills disponibles à invoquer si pertinent

Si la sub-phase implique :

- **Tests unitaires** : invoquer `superpowers:test-driven-development` (TDD discipline)
- **Bug debugging compliqué** : `superpowers:systematic-debugging`
- **Vérification finale avant DONE** : `superpowers:verification-before-completion`
- **Pattern matching dans codebase** : `norms:find-pattern` (avant impl) ou `norms:check`
  (après impl)

Ces skills sont déjà accessibles dans ton environnement Sonnet — utilise-les si ta
sub-phase matche leur description.

---

## 12. Fichiers de référence par domaine (lecture lazy)

Charge seulement si pertinent à ta sub-phase :

| Domaine                              | Reference                              |
| ------------------------------------ | -------------------------------------- |
| CLI commands, make targets           | `docs/reference/commands.md`           |
| Module map                           | `docs/reference/architecture.md`       |
| BDD schema, scan modes, repair queue | `docs/reference/indexer.md`            |
| EventBus, event catalog              | `docs/reference/event-bus.md`          |
| Logging conventions                  | `docs/reference/logging.md`            |
| Provider IDs flow                    | `docs/reference/external-ids-flow.md`  |
| Pipeline internals                   | `docs/reference/pipeline-internals.md` |
| Trailers                             | `docs/reference/trailers.md`           |

---

## 13. TL;DR pour les pressés

- Ne pas re-fixer DEV #9/#11/#13/#14 (shipped)
- Phase 0 = manual cross-repo, refuser si dispatché
- Phase 1.9 commit init-canonical + STOP, opérateur lance Plan A manuellement
- Phase 5 ordre N.M = ordre logique (post-renumber 2026-05-23)
- `make check` est la barre — `mypy` sur fichiers touchés ne suffit pas
- Test ERROR = collection cassée, tout après skippé silencieusement → fix imports
- Cross-caller `rg --type py` AVANT claim "supprimé"
- Regression test par bug fix, dans le même commit
- BLOCKED honnête > DONE faux
