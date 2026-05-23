# Phase 9 — CLI Test Coverage (NEW)

**Effort** : 2-3 jours (garde-fou : escalade si dépassement > 50 % — voir §Risques)
**Theme** : combler le déficit de tests par-commande sur l'ensemble de la surface CLI
exposée (`personalscraper <command>`), avec une matrice de scenarios déterministe.
**Insertion** : entre Phase 8 (Polish) et l'ancienne Phase 9 (Archive-docs) qui devient
Phase 10. Phase 8.7 (Pin commands tests SH-25 / CL-S) est **absorbée** dans 9.1.

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phase 8 mergée (surface CLI stabilisée : `qbit-restart` 8.3, `clean`/`cleanup` 8.5,
  `trailers audit` 8.6 livrés)
- `make check` vert sur HEAD avant 9.1

## Coverage matrix

| Item                                                           | Sub-phase | Source              |
| -------------------------------------------------------------- | --------- | ------------------- |
| Infrastructure de test (fixtures, factories, helpers)          | 9.1       | NEW (absorbe SH-25) |
| Pipeline commands coverage (7 cmds)                            | 9.2       | NEW                 |
| Library mutators coverage (11 cmds)                            | 9.3       | NEW                 |
| Library diagnostic critiques coverage (6 cmds)                 | 9.4       | NEW                 |
| Trailers + Config mutators coverage (4 cmds)                   | 9.5       | NEW                 |
| Non-critiques smoke++ (~8 cmds)                                | 9.6       | NEW                 |
| Coverage matrix doc + report script + gate finale (ACC-50..54) | 9.7       | NEW                 |

## Scope & classification

### Critiques — matrice 23-points (B+A)

**Pipeline (7)** : `ingest`, `sort`, `process`, `verify`, `dispatch`, `enforce`, `run`

**Library mutators (11)** : `library-repair`, `library-relink`, `library-rescrape`,
`library-gc`, `library-scan`, `library-index`, `library-init-canonical`,
`library-backfill-ids`, `library-reconcile`, `library-clean`, `library-verify`

**Library diagnostic (6)** : `library-doctor`, `library-validate`, `library-analyze`,
`library-recommend`, `library-report`, `library-ghost-audit`
(promus critiques par décision opérateur — bugs historiques côté diagnostic ont caché
des data-loss : BD-D, DEV #9, DEV #14)

**Trailers (2)** : `trailers download`, `trailers cleanup`

**Config (2)** : `init-config`, `config migrate-category`

→ **28 commandes critiques**

### Non-critiques — matrice 10-points (A étendu)

`library-status`, `library-search`, `library-show`, `torrents-list`, `trailers list`,
`trailers verify` (alias `audit` post-8.6), `info`, + read-only sub-commands résiduelles

→ **~8 commandes non-critiques**

## Matrice 23-points (référence)

Chaque commande critique doit cocher l'ensemble des points applicables (N/A explicites + justifiés).

**Args & flags (5)** :

1. `--help` exit 0 + texte non vide
2. Args obligatoires manquants → exit 2 + message Typer
3. Args valides minimaux → happy path exit 0
4. Tous les flags optionnels exercés ≥ 1 fois (parametrize)
5. Combinaisons exclusives → erreur (`--dry-run` + `--apply`, etc.)

**Config & env (3)** : 6. Config absente / corrompue → erreur explicite (pas de traceback Python brut) 7. `.env` manquant pour cmds qui exigent API keys → erreur claire 8. AppContext correctement injecté (pattern `tests/commands/*_app_context.py`)

**BDD (4)** : 9. BDD vide → exit 0 ou erreur claire (selon sémantique de la cmd) 10. BDD avec données seedées → résultat attendu sur fixtures 11. BDD corrompue (FK violation, schema_version invalide) → erreur claire 12. Idempotence : exécuter 2× → même état BDD (helper `bdd_diff_ignoring`)

**FS (3)** : 13. Path inexistant → erreur claire 14. Path read-only → erreur ou skip propre 15. `--dry-run` n'écrit rien (snapshot FS avant/après identique)

**Mutations (3)** : 16. `--apply` produit la mutation attendue (vérifier BDD ou FS post) 17. Échec partiel → état cohérent (rollback ou idempotent retry) 18. Lock concurrent / `pipeline.lock` présent → comportement défini

**Output (3)** : 19. `--format text` lisible (exit 0, mots-clés attendus) 20. `--format json` JSON parseable + schéma minimal (clés requises) 21. Exit code non-zero sur erreur (≠ exit 0 silent)

**Logging & events (2)** : 22. Events EventBus émis selon matrix v2.1 23. Logs structlog avec champs attendus (`step`, `outcome`, etc.)

**Non-critiques** : matrice réduite à #1-5, #9-10, #19-21 (10 points).

## Sub-phases

### 9.1 Infrastructure de test (absorbe SH-25 / CL-S)

**Sites** :

- `tests/commands/conftest.py` (étendu) — fixtures partagées :
  - `tmp_library_db` : SQLite réelle, migrations appliquées, seedable via factories
  - `tmp_staging_dir` : layout `001-MOVIES/` etc. selon `staging_dirs` config
  - `tmp_config_dir` : config valide minimale écrite dans tmp
  - `mock_tmdb_client`, `mock_tvdb_client`, `mock_omdb_client`, `mock_trakt_client` :
    faux clients réseau retournant des payloads canoniques
  - `mock_qbit_client`, `mock_transmission_client` : faux clients torrent
  - `cli_runner(app)` : helper retournant `(result, captured_logs, captured_events)`
    wrappant `typer.testing.CliRunner` + capture `structlog` + capture EventBus
  - `seed_factory` : produit `MediaItem`, `MediaFile`, `Disk` via API publique
    de l'indexer (pas SQL brut → respect des invariants)
- `tests/commands/_helpers.py` :
  - `assert_no_python_traceback(result)` : exit code non-zero MAIS message user-friendly
  - `assert_json_output(result, required_keys=...)` : parse + valide schéma minimal
  - `fs_snapshot(path) -> dict` : hash récursif pour assertion `--dry-run`
  - `assert_events_emitted(captured, [EventClass, ...])` : lit matrix v2.1 comme source
    de vérité (pas de liste hard-codée — réutilise mécanisme `pipeline-event-monitor`)
  - `bdd_diff_ignoring(before, after, cols=["updated_at", "last_seen"])` : exclut
    colonnes time-sensitive du diff (anti faux-positif idempotence)
- `tests/commands/test_fixtures_smoke.py` (nouveau) — sentinelle qui exerce chaque
  fixture isolément. Régression sur `conftest.py` ⇒ erreur localisée + rapide.

**Marker pytest custom** :

- Enregistrer `cli_scenario(N: int)` dans `pyproject.toml` (`[tool.pytest.ini_options]
markers = ["cli_scenario: scenario number from CLI coverage matrix"]`)
- Chaque test critique porte `@pytest.mark.cli_scenario(N)` avec N ∈ [1, 23]
- Permet à `scripts/cli-coverage-report.py` (9.7) d'agréger automatiquement

**Pin commands tests (ex-SH-25 / CL-S)** :

- `tests/commands/test_pin_existence.py` (nouveau) — un test paramétré sur la liste
  complète des commandes Typer exposées :
  - Extraction via `personalscraper --help` parsé (ou introspection `app.registered_commands`)
  - Assert `--help` exit 0 + signature de base présente
- Garantit zéro disparition silencieuse de commande au refactor

**Audit pré-écriture** :

- Liste des fixtures dupliquées entre `tests/conftest.py`, `tests/commands/conftest.py`,
  et tests individuels (pour ne pas réinventer la roue) → produit `audit/13-cli-test-fixtures.md`

**Commit** : `test(tech-debt): CLI test infrastructure — fixtures, factories, helpers, pin test (9.1, absorbe SH-25)`

---

### 9.2 Pipeline commands coverage (7 cmds)

**Sites** : `tests/commands/test_<cmd>_coverage.py` pour chacune des 7 commandes pipeline.

**Commandes** : `ingest`, `sort`, `process`, `verify`, `dispatch`, `enforce`, `run`

**Approche** :

- Matrice 23-points sur chaque cmd, parametrize agressif (1 test paramétré = N scenarios)
- Mock qBittorrent/Transmission (réseau), FS dans `tmp_path`, BDD réelle
- Test idempotence systématique (re-run `sort` / `process` = no-op via `bdd_diff_ignoring`)
- Test SIGINT mid-run pour `run` : interruption propre, lock libéré, pas d'orphelin
- Test `--dry-run` no-op via `fs_snapshot` avant/après
- Test `pipeline.lock` présent → comportement défini (point #18)
- Assertions events via matrix v2.1 (point #22)

**Module size** : si un fichier dépasse 800 LOC (warn) ou 1000 LOC (hard-block post 8.11),
splitter par groupe : `test_<cmd>_args.py`, `test_<cmd>_mutations.py`, `test_<cmd>_errors.py`.

**Régressions adressées** :

- BD-D (soft_delete_subtree régression 2026-05-23 — fixed `c5e2bbd`) → test dédié 9.3
  mais sentinelle pipeline si la cmd `dispatch` re-déclenche

**Commit** : `test(tech-debt): pipeline commands coverage (9.2)`

---

### 9.3 Library mutators coverage (11 cmds)

**Sites** : `tests/commands/test_<cmd>_coverage.py` pour chacune des 11 commandes mutators.

**Commandes** : `library-repair`, `library-relink`, `library-rescrape`, `library-gc`,
`library-scan`, `library-index`, `library-init-canonical`, `library-backfill-ids`,
`library-reconcile`, `library-clean`, `library-verify`

**Approche** :

- Matrice 23-points sur chaque, focus particulier sur points 16-17 (mutations + échec partiel)
- Mock TMDB/TVDB pour `library-rescrape`, `library-backfill-ids`
- Test FK enforcement (point #11) — exploite ACC-02 (PRAGMA `foreign_keys=ON`)
- Test UNIQUE(title, year, kind) post-DEV #53 sur `library-scan` (8.12)

**Régression tests obligatoires (per memory "Test de régression par bug")** :

- **DEV #9** (repair_root_duplicate inversion data-loss) : test reproduit la condition pré-fix
- **DEV #14** (oshash IS NOT NULL alignment) : test reproduit la NULL collision
- **BD-D** (soft_delete_subtree fermeture loop) : test reproduit l'incomplete prune
- **DEV #53** (`_upsert_media_item` lookup-key) : test reproduit le duplicate insert

**Snapshot BDD post-mutation** : pour chaque cmd `--apply`, snapshot du diff BDD attendu
(rows insérées/modifiées/supprimées) — détecte les drifts d'invariants.

**Commit** : `test(tech-debt): library mutators coverage + regression tests DEV#9/#14/BD-D/DEV#53 (9.3)`

---

### 9.4 Library diagnostic critiques coverage (6 cmds)

**Sites** : `tests/commands/test_<cmd>_coverage.py` pour chacune des 6 commandes diagnostic.

**Commandes** : `library-doctor`, `library-validate`, `library-analyze`,
`library-recommend`, `library-report`, `library-ghost-audit`

**Approche** :

- Matrice 23-points (promotion critique par décision opérateur 2026-05-23)
- **Golden files JSON canoniques** : pour chaque cmd qui produit un rapport,
  `tests/commands/golden/<cmd>_<scenario>.json` — détecte les drifts de format de sortie
- Test sur BDD seedée avec ghosts, orphans, FK breakages, missing files →
  assertions sur le diagnostic produit (chaque issue type doit être détecté)
- Test `--format json` (point #20) : schéma stable, clés documentées

**Anti-mocking rule** : ne PAS mocker le module testé (interdit
`@patch("personalscraper.commands.library.doctor.run_doctor")` dans le test de `library-doctor`).
Mocker uniquement les frontières externes.

**Commit** : `test(tech-debt): library diagnostic critiques coverage + golden files (9.4)`

---

### 9.5 Trailers + Config mutators coverage (4 cmds)

**Sites** :

- `tests/commands/test_trailers_download_coverage.py`
- `tests/commands/test_trailers_cleanup_coverage.py`
- `tests/commands/test_init_config_coverage.py` (étend l'existant si présent)
- `tests/commands/test_config_migrate_category_coverage.py`

**Commandes** : `trailers download`, `trailers cleanup`, `init-config`,
`config migrate-category`

**Approche** :

- Matrice 23-points
- Mock YouTube/yt-dlp pour `trailers download` (subprocess + network)
- Test `init-config` sur dir vide / dir existant non-vide / dir non-writable
- Test `config migrate-category` reverse-engineering des renames (BDD + FS sync)
- Test placement Plex-conformant trailers (movies flat vs TV `Trailers/` subfolder)
  → exploite invariants DEV #42, #43

**Commit** : `test(tech-debt): trailers + config coverage (9.5)`

---

### 9.6 Non-critiques smoke++ coverage (~8 cmds)

**Sites** : `tests/commands/test_<cmd>_smoke.py` pour chacune des ~8 cmds non-critiques.

**Commandes** : `library-status`, `library-search`, `library-show`, `torrents-list`,
`trailers list`, `trailers verify` (alias `audit`), `info`, sub-cmds read-only résiduelles

**Approche** :

- Matrice **10-points** (#1-5, #9-10, #19-21)
- Volume : 1 fichier par cmd, ~5-10 tests/fichier
- Réutilisation maximale des fixtures 9.1
- Pas de test mutation (N/A par construction)

**Commit** : `test(tech-debt): non-critical commands smoke++ coverage (9.6)`

---

### 9.7 Coverage matrix doc + report script + gate finale

**Sites** :

- `docs/features/tech-debt/cli-coverage-matrix.md` (nouveau) — tableau auto-généré :
  - Lignes : 28 critiques + 8 non-critiques = 36 commandes
  - Colonnes : 23 points (10 pour non-critiques, N/A explicites justifiés)
  - Cellules : ✅ / ❌ / N/A
- `scripts/cli-coverage-report.py` (nouveau) :
  - Parse `tests/commands/*.py` pour extraire les markers `@pytest.mark.cli_scenario(N)`
  - Agrège par commande × scenario
  - Génère le tableau Markdown
  - Mode `--check` : exit 1 si ≥ 1 ❌ sur critiques, exit 0 sinon
  - Mode `--write` : régénère `cli-coverage-matrix.md` (idempotent)
- `Makefile` : ajouter cible `make cli-coverage-check`

**Mise à jour `IMPLEMENTATION.md`** :

- Phase 9 ajoutée, Phase 9 (archive-docs) renommée Phase 10
- Sub-phase 8.7 marquée "folded into 9.1"

**Mise à jour `plan/INDEX.md`** :

- Idem table phases + renum
- Nouveau lien `phase-09-cli-coverage.md`

**Mise à jour `ACCEPTANCE.md`** — 5 nouveaux critères ACC-50..54 (voir §ACCEPTANCE).

**Commit gate** : `chore(tech-debt): phase 9 gate — CLI test coverage (ACC-50..54)`

## ACCEPTANCE (nouveaux critères)

### ACC-50 — CLI coverage report check 🟡

```bash
python3 scripts/cli-coverage-report.py --check
# Expected: exit 0 (0 ❌ sur critiques, N/A explicites OK)
```

### ACC-51 — Tests cli_scenario count threshold 🟡

```bash
make test -m cli_scenario 2>&1 | tail -1
# Expected: NNN passed (seuil minimum ≥ 28 × 15 = 420 tests sur critiques + 8 × 7 = 56 sur non-critiques)
```

### ACC-52 — Coverage matrix doc committed and synced 🟡

```bash
python3 scripts/cli-coverage-report.py --write
git diff --exit-code docs/features/tech-debt/cli-coverage-matrix.md
# Expected: exit 0 (matrix doc à jour vs dernière exécution des tests)
```

### ACC-53 — Each critical command has a mutation test (#16) 🟡

```bash
for cmd in ingest sort process verify dispatch enforce run \
           library-repair library-relink library-rescrape library-gc \
           library-scan library-index library-init-canonical \
           library-backfill-ids library-reconcile library-clean library-verify \
           library-doctor library-validate library-analyze library-recommend \
           library-report library-ghost-audit \
           trailers-download trailers-cleanup init-config config-migrate-category; do
  grep -lE "cli_scenario\(16\)" tests/commands/test_${cmd//-/_}*.py > /dev/null || echo "MISSING: $cmd"
done
# Expected: empty output (zero MISSING)
```

### ACC-54 — Each critical command has a dry-run no-op test (#15) 🟡

```bash
# Same list as ACC-53, grep for cli_scenario(15)
# Expected: empty output (zero MISSING) for cmds with --dry-run flag.
# Cmds without --dry-run (query-only diagnostic) : N/A justified in matrix doc.
```

## Risques & garde-fous

1. **Module size hard-block** (DEV #46 / Phase 8.11) : un fichier de tests dépassant
   1000 LOC bloque commit. Mitigation : split par groupe de scenarios
   (`test_<cmd>_args.py`, `test_<cmd>_mutations.py`, etc.). Pré-check :
   `python3 scripts/check-module-size.py tests/commands/`.

2. **Temps d'exécution `make test`** : risque d'allonger significativement la suite.
   Mitigation : marker `cli_scenario`, exécution dédiée via `pytest -m cli_scenario`.
   Benchmark après 9.2-9.3 : si > 180 s, parallélisation via `pytest-xdist`.

3. **Drift matrix v2.1 ↔ tests d'events (point #22)** : matrix v2.1 évolue post-Phase 7.
   Mitigation : `assert_events_emitted` lit la matrix comme source de vérité (pas de
   liste hard-codée) — réutilise mécanisme `pipeline-event-monitor` agent.

4. **Faux positifs sur tests d'idempotence (#12)** : `updated_at` et `last_seen` changent
   sur re-run. Mitigation : helper `bdd_diff_ignoring(cols=[...])` documenté dans `_helpers.py`.

5. **Régressions sur tests `tests/commands/*` existants** : refactor du conftest peut
   casser des tests existants. Mitigation : audit pré-écriture (9.1), migration
   progressive, runs intermédiaires `make test` entre chaque migration.

6. **Effort sous-estimé** : 2-3 j basé sur ~36 cmds × ~10 tests moyen = ~360 tests.
   Si chaque test prend 5-10 min → 30-60 h = plutôt 4-7 j. Mitigation : parametrize
   agressif. Escalade decision si dépassement > 50 % : réduire scope non-critiques
   ou splitter en Phase 9 + 9bis. **Trigger** : check à fin 9.3 ; si effort cumulé
   9.1+9.2+9.3 > 1.8 j, escalader.

## Garde-fous mandatoires (anti-pattern checks)

- Chaque sub-phase commence par `make test` (baseline) et finit par `make test`
  (no regression sur autres tests)
- Chaque test mutateur DOIT vérifier BDD post-état, pas juste exit code (anti-pattern :
  `assert result.exit_code == 0` sans assertion fonctionnelle)
- Aucun mock du module testé lui-même (interdit
  `@patch("personalscraper.commands.X.Y")` dans le test de la cmd `X-Y`)
- Tests `@patch` sur l'app : autorisés UNIQUEMENT sur frontières externes (network,
  subprocess) — aligne sur DEV #49 (test_cli @patch trim)
- Régression tests obligatoires en 9.3 : DEV #9, #14, BD-D, DEV #53 (per memory
  "Test de régression par bug")

## Dépendances

**Amont** :

- Phase 8 mergée : surface CLI stabilisée (`qbit-restart` 8.3, `clean`/`cleanup` 8.5,
  `trailers audit` 8.6, `_upsert_media_item` dedup 8.12)
- Phase 8.11 module-size hard-block : Phase 9 doit respecter le seuil 1000 LOC dès
  son premier commit

**Aval** :

- Phase 10 (ex-9, archive-docs) : pas de dépendance code, peut suivre
- PR gate ACC-final-\* : ACC-50..54 ajoutés au gate final

## Sub-phase checklist (gate)

- [ ] 9.1 infrastructure (fixtures + helpers + marker + pin test SH-25) commit + PASS
- [ ] 9.2 pipeline commands coverage commit + PASS
- [ ] 9.3 library mutators + 4 regression tests commit + PASS
- [ ] 9.4 library diagnostic + golden files commit + PASS
- [ ] 9.5 trailers + config commit + PASS
- [ ] 9.6 non-critiques smoke++ commit + PASS
- [ ] 9.7 matrix doc + report script + ACC-50..54 + gate commit
- [ ] `make check` vert
- [ ] `python3 scripts/cli-coverage-report.py --check` exit 0
- [ ] Effort réel logged dans IMPLEMENTATION.md (vs estimate 2-3 j)
