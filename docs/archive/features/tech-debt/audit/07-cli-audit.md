# Item 9 — Audit commandes CLI (bugs + design + améliorations)

**Date** : 2026-05-21
**Méthode** : inventaire exhaustif des 26 commandes top-level + sous-commandes, cross-vérification
help text vs implémentation, audit transversal (--dry-run, --format, telemetry, naming),
identification des bugs (DEV #20-#23) et patterns CLI (P18-P19).
**Output** : rapport CLI complet, items DESIGN pour l'item 10 (brainstorm CLI).

---

## 0. Inventaire des commandes

### Top-level (30 commandes + 2 groupes)

**Pipeline (8)** — flat, non-préfixées :

- `ingest` — Ingest completed torrents from qBittorrent.
- `sort` — Sort and clean media files.
- `scrape` — Scrape metadata and artwork from TMDB/TVDB.
- `verify` — Verify and qualify scraped media before dispatch.
- `enforce` — Enforce staging conventions: sanitize filenames, validate structure, check coherence.
- `dispatch` — Move media to storage disks.
- `process` — Run process phase only (reclean + dedup + scrape + cleanup).
- `run` — Run full pipeline (ingest -> sort -> process -> verify -> dispatch).

**Library (16)** — toutes préfixées `library-` :

- `library-index` — Run a full or quick media indexer scan.
- `library-reconcile` — Detect index ↔ filesystem divergences without a full rescan.
- `library-verify` — Re-stat every indexed file and mark mismatches for repair.
- `library-repair` — Drain the repair queue within a time budget.
- `library-status` — Show the latest completed indexer scan run summary.
- `library-search` — Search indexed media items with the flex-attr query language.
- `library-show` — Pretty-print all stored data for a single media item.
- `library-report` — Display library statistics and health report.
- `library-analyze` — Deep scan video files with ffprobe (codec, audio, subtitles).
- `library-recommend` — Generate re-download recommendations.
- `library-rescrape` — Targeted re-scrape of library items via TMDB/TVDB.
- `library-validate` — Validate NFO, artwork, naming conformity.
- `library-relink` — Relink `media_file` rows whose `release_id` is NULL.
- `library-clean` — Remove .actors/, empty dirs, junk files from storage disks.
- `library-ghost-audit` — Audit storage disks for NTFS-via-macFUSE ghost dirents.
- (16ᵉ : pas observé dans le help, peut-être j'ai miscounté — à vérifier)

**Utilities (3)** — flat :

- `info` — Display version, config paths, and disk status.
- `init-config` — Create ./config/ from the config.example/ template directory.
- `torrents-list` — List completed torrents from the active qBittorrent client.

**Groupes (2)** :

- `trailers` group avec 4 subs : `scan`, `download`, `verify`, `purge`
- `config` group avec 1 sub : `migrate-category`

### Total exposé en CLI

**26 commandes top-level** + **5 sub-commandes** (trailers + config) = **31 entry points CLI**.

---

## 1. Bugs identifiés

### DEV #20 — `qbit-restart` référencée mais inexistante (mineur)

Matrix v2.0 §INGEST recovery suggère `personalscraper qbit-restart` quand l'IP est bannie. Mais
cette commande N'EXISTE PAS :

```bash
$ personalscraper qbit-restart --help
Error: No such command 'qbit-restart'.
```

`rg "qbit-restart" --type py personalscraper/` retourne 0 résultat. La matrice référence une
commande qui n'a jamais été implémentée (ou qui l'a été et a été supprimée). Même pattern que
DEV #10 (`library-reconcile --dry-run`).

**Recommandation** :

- Soit implémenter `qbit-restart` (commande utile pour debugging IP-ban / lockout).
- Soit supprimer la mention dans la matrice + SKILL.md.

### DEV #21 — `--dry-run` coverage incohérente sur library-\* mutateurs (mineur—structurel)

Inventaire `--dry-run` support :

| Commande              | --dry-run ? | Mutate ?                              | Statut                                                                     |
| --------------------- | ----------- | ------------------------------------- | -------------------------------------------------------------------------- |
| `ingest`              | ✓           | OUI                                   | OK                                                                         |
| `sort`                | ✓           | OUI                                   | OK                                                                         |
| `scrape`              | ✓           | OUI                                   | OK                                                                         |
| `verify`              | ✓           | NON (read-only)                       | OK (legit, mais inutile)                                                   |
| `enforce`             | ✓           | OUI                                   | OK                                                                         |
| `dispatch`            | ✓           | OUI                                   | OK                                                                         |
| `process`             | ✓           | OUI                                   | OK                                                                         |
| `run`                 | ✓           | OUI                                   | OK                                                                         |
| `library-index`       | ✓           | OUI                                   | OK                                                                         |
| `library-rescrape`    | ✓           | OUI                                   | OK                                                                         |
| `library-reconcile`   | ✗           | NON (avec `--enqueue-repairs` mutate) | DEV #10 — matrix dit `--dry-run` mais flag est `--enqueue-repairs` inversé |
| `library-repair`      | ✗           | OUI                                   | **BUG** — devrait avoir `--dry-run`                                        |
| `library-relink`      | ✗           | OUI                                   | **BUG** — devrait avoir `--dry-run`                                        |
| `library-clean`       | ✗           | OUI                                   | **BUG** — devrait avoir `--dry-run`                                        |
| `library-verify`      | ✗           | OUI (marque pour repair)              | **BUG** ambigu — `--no-enqueue` peut-être ?                                |
| `library-validate`    | ✗           | NON                                   | OK                                                                         |
| `library-analyze`     | ✗           | NON                                   | OK                                                                         |
| `library-status`      | ✗           | NON                                   | OK                                                                         |
| `library-search`      | ✗           | NON                                   | OK                                                                         |
| `library-show`        | ✗           | NON                                   | OK                                                                         |
| `library-report`      | ✗           | NON                                   | OK                                                                         |
| `library-recommend`   | ✗           | NON                                   | OK                                                                         |
| `library-ghost-audit` | ✗           | NON ?                                 | OK ?                                                                       |
| `torrents-list`       | ✗           | NON                                   | OK                                                                         |
| `info`                | ✗           | NON                                   | OK                                                                         |
| `init-config`         | ✗           | OUI (créée FS)                        | **BUG** — devrait avoir `--dry-run`                                        |

**4 commandes mutent sans `--dry-run`** : `library-repair`, `library-relink`, `library-clean`,
`init-config` (+ ambigu `library-verify`).

### DEV #22 — Output format incohérent (mineur—UX)

| Commande                  | Output type        | --format support ? |
| ------------------------- | ------------------ | ------------------ |
| `info`                    | Typer rich         | ✗                  |
| `library-analyze`         | Typer rich         | ✗                  |
| `library-report`          | Typer rich         | **✓ (`--format`)** |
| `library-reconcile`       | **JSON hardcoded** | ✗                  |
| `library-status`          | Typer rich         | ✗                  |
| `library-search`          | Typer rich         | ✗                  |
| `library-show`            | Typer rich         | ✗                  |
| `library-index` (summary) | JSON hardcoded     | ✗                  |
| `torrents-list`           | Typer rich         | ✗                  |

3 patterns :

1. **Typer rich par défaut** (majorité)
2. **JSON hardcoded** (`library-reconcile`, `library-index` summary line)
3. **`--format` flag** (`library-report` seulement)

Inconsistance : pour scripting/cron, il faudrait `--format json|plain` partout. Currently grep
sur stdout est l'unique fallback.

### DEV #23 — Aucune télémétrie `cli.invoke.*` (mineur—observabilité)

```bash
$ rg -n "log\.info\(.cli\." --type py personalscraper/ | wc -l
0
```

Aucune commande n'émet un event `cli.invoke.<command> args={...}` au démarrage. Conséquence :

- Audit "qui a lancé quoi quand" impossible sans parsing des stdout files.
- Pas de compteur d'usage par commande.
- Pipeline-monitor host process ne capte pas un event "session start cli=X" pour le run dump.

**Recommandation** : decorator `@cli_telemetry` qui wrappe `@app.command` et émet l'event au start.

### DEV #6 (rappel item 5) — VERIFY n'émet aucun event INFO stdout

Confirmé en lisant `personalscraper/commands/pipeline.py:130-170` : la commande utilise
`console.print` (Typer rich) et non `log.info`. Les events `verify_item_done` référencés dans
matrix §VERIFY sont émis ailleurs (probablement dans `verify/run.py` via le bus, pas via stdout).

Code dans pipeline.py:159 :

```python
console.print(f"[bold]Verify:[/bold] {report.success_count} OK, {report.error_count} blocked")
console.print(f"  {len(dispatchable)} ready for dispatch")
if state["verbose"]:
    for detail in report.details:
        console.print(f"  {detail}")
```

`console.print` ≠ `log.info`. Le rich rendering est UX-friendly mais opaque pour les agents et
les pipes / grep.

---

## 2. Patterns systémiques (CLI-specific)

### P18 — UX rich vs telemetry structurée non-tracée

DEV #6 et DEV #23 = même cause : pas de séparation claire entre "ce que l'utilisateur voit"
(Typer rich) et "ce que la machine peut grep / parser" (structlog). Certaines commandes
font les 2 (ingest/sort via `run` modules qui appellent `log.info`), d'autres seulement
rich (verify, library-status).

→ **Item DESIGN** : règle "toute commande pipeline DOIT émettre au moins un event INFO par étape
clé + un event INFO 'cli.invoke.<cmd>' au start". Doc-as-contract dans `docs/reference/logging.md`.

### P19 — Inconsistance des conventions par groupe de commandes

- Pipeline : flat names (ingest, sort, ...)
- Library : `library-*` prefix
- Trailers : group (`trailers <sub>`)
- Config : group (`trailers <sub>`)

Pourquoi `library-*` plat mais `trailers <sub>` en groupe ? Probablement raison historique
(library-\* a été ajouté avant que Typer subgroups soient utilisés).

Conséquence : 16 commandes `library-*` polluent le help top-level. Refactor possible :
`personalscraper library index/status/search/...`. Mais c'est BREAKING — bash scripts/cron/launchd
plists existants se cassent.

→ **Item DESIGN** : NICE-TO-HAVE refactor pour 0.17+ (breaking, pas 0.16.0 tech-debt).

---

## 3. Améliorations brainstorm (CLI-specific)

### 3.1 — Bugs prioritaires

**CL-A. DEV #21 — Ajouter `--dry-run` à `library-repair`, `library-relink`, `library-clean`, `init-config`**

Pour chaque commande mutate-sans-dry-run :

- `library-repair --dry-run` : log les actions qu'il drainerait sans muter.
- `library-relink --dry-run` : log les media_file qu'il relinkerait.
- `library-clean --dry-run` : log les .actors/ / empty dirs / junk files qu'il supprimerait.
- `init-config --dry-run` : log les fichiers qu'il créerait dans `./config/`.
- `library-verify --no-enqueue` (alternatif) : verify sans toucher repair_queue.

**CL-B. DEV #20 — Implémenter `qbit-restart` (ou supprimer la mention)**

Si implémentée : commande qui force qBit à redémarrer (lance le script local, restart le service
launchd, etc.). Utile dans le runbook IP-ban / auth lockout.

**CL-C. DEV #10 — `library-reconcile`: clarifier `--enqueue-repairs` vs (matrix erroneously dit) `--dry-run`**

`library-reconcile` est read-only par défaut. La matrix v2.0 §3.4 référence `--dry-run` (qui
n'existe pas). Correction matrix v2.1 : retirer cette mention, mentionner `--enqueue-repairs`
comme opt-in mutation.

### 3.2 — Output format

**CL-D. DEV #22 — `--format json|plain|rich` global**

Option de niveau top : `personalscraper --format json <cmd>`. Implementation :

- `state["format"]` lu via `@app.callback`.
- Chaque commande respecte (console.print conditionné, ou émet un event final).
- `library-reconcile` retire son `print(json.dumps(...))` hardcodé, utilise le format flag.

**CL-E. Sérialisation summary unifiée**

Chaque commande pipeline + library finit par un "summary dict" (success count, errors, durée).
Sérialiser via `--format json` pour scripting/cron.

### 3.3 — Telemetry / observability

**CL-F. DEV #23 — Decorator `@cli_telemetry`**

Wrappe `@app.command` :

```python
def cli_telemetry(cmd_name):
    def deco(f):
        @functools.wraps(f)
        def wrapped(ctx, *args, **kwargs):
            log.info(f"cli.invoke.{cmd_name}", args=kwargs, version=__version__)
            try:
                ret = f(ctx, *args, **kwargs)
                log.info(f"cli.complete.{cmd_name}", exit_code=ret or 0)
                return ret
            except Exception as exc:
                log.error(f"cli.failed.{cmd_name}", error=str(exc))
                raise
        return wrapped
    return deco
```

À appliquer à chaque commande exposée.

**CL-G. DEV #6 — VERIFY structured events**

Modifier `verify/run.py` pour émettre `verify_item_done status=... errors=[...]` via `log.info`
(structlog) avec l'event-bus pour bonus. La commande peut toujours faire son rich rendering
en parallèle (les deux ne sont pas mutuellement exclusifs).

**CL-H. Test E2E "no console.print without log.info equivalent"**

Pour chaque commande pipeline ayant un summary console.print : verify qu'un event structlog
équivalent existe. Pytest custom collect ou simple grep.

### 3.4 — Doc référence

**CL-I. DEV #7 (rappel) — `run --help` introspection des steps**

Le help text de `run` liste 5 steps. Le pipeline en a 9. Le help text doit être généré à partir
de `Pipeline.STEPS` (ou équivalent introspectable), pas hardcodé.

**CL-J. `docs/reference/commands.md` exhaustif**

Audit qui couvre :

- Chaque commande CLI a une section dédiée
- Cas d'usage
- Paramètres (renvoyant au help text pour les détails)
- Side effects (mutate / read-only)
- Ordre canonique (post-dispatch, post-scrape, etc.)
- Dépendances (lock file, BDD, FS)

**CL-K. CLI coverage check dans CI**

Script `scripts/audit-cli-coverage.py` :

- Iterate `personalscraper/commands/*.py` + sub-cli files
- Pour chaque `@app.command`, vérifie qu'il est documenté dans `docs/reference/commands.md`
- Pour chaque module métier (`library/`, `indexer/`, etc.), vérifie qu'au moins UNE commande
  l'invoke en E2E.

### 3.5 — Missing commands

**CL-L. `library-scan` (DEV #16 / BD-G)**

Expose `library.scanner.scan_library()`. Voir item 8 BD-G.

**CL-M. `library-doctor` (BD-Y)**

Health check global. Voir item 8 BD-Y.

**CL-N. `library-gc` (BD-W)**

GC du `index_outbox` (purge `status='done' AND processed_at < cutoff`).

**CL-O. `qbit-restart` (CL-B)**

Recovery / debugging utility.

**CL-P. `library-backfill-ids` (alternative à `library-index --mode backfill-ids`)**

Si le mode driver est lourd, exposer une commande dédiée. Plus discoverable que via flag obscur.

### 3.6 — Naming / structure (non-breaking pour 0.16)

**CL-Q. Renommer `verify` → `library-quality-check` (NICE, breaking — 0.17+)**

`verify` est ambigu : 3 sites homonymes :

- `personalscraper verify` (pipeline step)
- `personalscraper library-verify` (re-stat indexed files)
- `personalscraper trailers verify` (audit trailers)

Sépare clairement par renommage : `pipeline-verify`, `library-restat`, `trailers-verify`.

**CL-R. Group library-\* en subgroup `library <sub>` (NICE, breaking — 0.17+)**

Refactor structure : `personalscraper library index` au lieu de `personalscraper library-index`.
Help text plus clean. Migration deprecation avec alias pendant 1 release.

### 3.7 — Tests / régression

**CL-S. Test pin chaque commande exposée**

Pour chaque commande dans le help : un test pin existence + signature de base. Évite que
`library-scan` disparaisse silencieusement en refactor.

**CL-T. Test "matrix v2.X references valid CLI"**

Lit le matrix.md, extrait toutes les commandes `personalscraper <cmd>` mentionnées, lance
`<cmd> --help` → assert exit 0. Aurait attrapé DEV #20 et DEV #10.

---

## 4. Catégorisation must / should / nice

### Must-have (DESIGN priorité 1)

- **CL-A** `--dry-run` pour les 4 commandes mutate manquantes (DEV #21)
- **CL-G** VERIFY structured events (DEV #6)
- **CL-I** `run --help` introspection (DEV #7)
- **CL-K** CLI coverage check dans CI
- **CL-L** `library-scan` (DEV #16)
- **CL-T** Test "matrix references valid CLI" (catch DEV #10 + #20 type)

### Should-have (priorité 2)

- **CL-B** Implémenter `qbit-restart` (ou supprimer mention matrix)
- **CL-C** Clarifier `library-reconcile` flags
- **CL-D** `--format json|plain|rich` global
- **CL-E** Sérialisation summary unifiée
- **CL-F** Decorator `@cli_telemetry`
- **CL-H** Test "no console.print without log.info"
- **CL-J** `docs/reference/commands.md` exhaustif
- **CL-M** `library-doctor`
- **CL-N** `library-gc`
- **CL-P** `library-backfill-ids` (ou doc le --mode existant)
- **CL-S** Test pin chaque commande exposée

### Nice-to-have (0.17+ — breaking changes)

- **CL-Q** Renommer `verify` → `pipeline-verify` (et autres ambigus)
- **CL-R** Group `library <sub>`

---

## 5. Cross-patterns (extension item 7 + 8)

| #               | Pattern                                      | Instance                                    | Levier CLI                                   |
| --------------- | -------------------------------------------- | ------------------------------------------- | -------------------------------------------- |
| **P12**         | CLI surface incomplète                       | DEV #16                                     | CL-L + CL-M + CL-N (item 8 BD-G, BD-Y, BD-W) |
| **P18**         | UX rich vs telemetry structurée non-tracée   | DEV #6, DEV #23                             | CL-F + CL-G + CL-H                           |
| **P19**         | Inconsistance des conventions par groupe     | flat vs prefix vs group                     | CL-Q + CL-R (0.17+)                          |
| **P8 (rappel)** | Doc rot CLI vs implémentation                | DEV #7                                      | CL-I + CL-J + CL-T                           |
| **(NEW) P20**   | Matrix/SKILL references non-existent CLI     | DEV #10 (--dry-run), DEV #20 (qbit-restart) | CL-T (test catches both)                     |
| **(NEW) P21**   | Mutate commands without --dry-run safety net | DEV #21                                     | CL-A                                         |
| **(NEW) P22**   | Output format hardcoded inconsistent         | DEV #22                                     | CL-D + CL-E                                  |

---

## 6. Implications DESIGN tech-debt (item 14)

### Section "CLI surface" (élargit §10 de l'item 6/7)

Règles à enforcer :

1. **CLI completeness** : chaque module métier critique expose ≥1 commande CLI documentée.
2. **Dry-run par défaut sur tout ce qui mute** : règle universelle, hook lint custom possible.
3. **Telemetry structlog obligatoire** : chaque commande émet ≥1 event `cli.invoke.<cmd>` au
   start + ≥1 event "domain progress" par étape clé.
4. **Output format unifié** : `--format json|plain|rich` global, default rich pour humain.
5. **Documentation référence par commande** : `docs/reference/commands.md` exhaustif.
6. **Matrix references CI-validated** : test "matrix mentionne uniquement des CLI existantes".

### Plan de phases CLI (intégré au plan global)

| Phase        | Items                                                             | Effort |
| ------------ | ----------------------------------------------------------------- | ------ |
| CLI-1        | CL-A (dry-run) + CL-I (run help) + CL-K + CL-T (tests)            | 1-2 j  |
| CLI-2        | CL-F (telemetry decorator) + CL-G (VERIFY events) + CL-H          | 1-2 j  |
| CLI-3        | CL-L (library-scan) + CL-M (library-doctor) + CL-P                | 2-3 j  |
| CLI-4        | CL-D + CL-E (format unification) + CL-J (doc)                     | 2 j    |
| CLI-5        | CL-B (qbit-restart) + CL-N (library-gc) + CL-C (reconcile clarif) | 1-2 j  |
| CLI-6 (nice) | CL-Q + CL-R (0.17+ rename/group)                                  | 1-2 j  |

Total CLI seul : **7-13 jours**, dont CLI-1..CLI-5 = 7-11 j must/should (intégrables à tech-debt
0.16.0), CLI-6 différé en 0.17.

---

## 7. Synthèse globale

- **31 entry points CLI** (26 top-level + 5 sub).
- **4 nouveaux DEVs** : #20-#23 (qbit-restart inexistante, --dry-run incohérent, format incohérent,
  pas de cli.invoke telemetry).
- **3 nouveaux patterns** : P20-P22 (références obsolètes, mutate-sans-dry-run, format hardcodé).
- **Items CL-A..CL-T (20 items)** triés must/should/nice.
- **5 nouvelles règles DESIGN** à intégrer à §10 (CLI completeness).
- **6 phases CLI**, 7-13 jours, must-have inclus dans 0.16.0.

## 8. Suite

L'item 10 (brainstorm CLI improvements) consolidera ce rapport en une liste DESIGN-ready
finale. Le brainstorm peut ajouter ses propres trouvailles (ex: completion auto-installable
améliorée, mode interactive `personalscraper repl`, etc.) mais les items CL-A..CL-T sont déjà
DESIGN-ready et alimentent directement item 14.

L'item 10 sera donc relativement court (consolidation + ajout d'idées "exploratoires").
