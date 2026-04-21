# Phase 10 — Documentation + finalization + PR

## Objectif

Mettre à jour toute la documentation utilisateur, finaliser `config.example.json5`, vérifier les critères d'acceptation, créer la PR.

## Sous-phases

### 10.1 — `config.example.json5` final + validation

- [ ] Revue finale de `config.example.json5` :
  - Commentaires `//` clairs et descriptifs (deviendront prompts `init-config`)
  - Exemples dans `category_rules` et `custom_categories` pour guider user
  - `genre_mapping` complet avec **tous** les IDs TMDB Movies (19) + TMDB TV (16) + TVDB (36) en commentaires, valeurs mappées vers IDs V15
  - Values par défaut cohérentes
- [ ] Test : `python -c "from personalscraper.conf.loader import load_config; load_config(Path('config.example.json5'))"` → valide
- [ ] Test : `personalscraper init-config --example config.example.json5 --yes` sur tmp dir → produit un `config.json5` qui passe `load_config`

**Commit** : `v15.10.1: Finalize config.example.json5 with full genre mapping comments`

### 10.2 — `.gitignore` + `.env.example`

- [ ] Ajouter à `.gitignore` :

  ```
  # V15 config-driven
  config.json5
  config.json5.v15.bak
  # TMDB keywords cache
  tmdb_keywords_cache.json
  ```

- [ ] Vérifier `.env.example` : retirer `DISK1_DIR`..`DISK4_DIR`, `TORRENT_COMPLETE_DIR`, `STAGING_DIR` (déménagés dans `config.json5`). Garder secrets + seuils numériques.

**Commit** : `v15.10.2: Update .gitignore and .env.example for V15`

### 10.3 — `MIGRATION.md` : procédure V14 → V15

- [ ] Créer `MIGRATION.md` à la racine du repo :
  - Contexte : pourquoi V15
  - Procédure en une commande : `personalscraper init-config --from-current`
  - Ce qui est migré : `.env` → `config.json5`, `library_*.json` → IDs, `.category` → NFO, `.personalscraper/` → `.data/`
  - Rollback : restaurer `.v14.bak` files
  - Troubleshooting : cas labels inconnus, cross-filesystem data_dir, V14 NFOs sans `<category>`
  - Checklist post-migration : review `spectacles → standup` mapping, fill missing folder_name aliases, test un run `--dry-run`

**Commit** : `v15.10.3: Add MIGRATION.md with V14→V15 procedure and rollback`

### 10.4 — `CLAUDE.md` : pointer vers V15, mettre à jour critiques

- [ ] `CLAUDE.md` :
  - Section "Current Version" : V15 in progress (en cours de développement)
  - Section "Configuration" : mention `config.json5` obligatoire, `.env` pour secrets seulement
  - Retirer toute référence en dur à `Disk1..Disk4`, `/Volumes/...`, labels FR
  - Section "Reference Index" mise à jour pour `docs/reference/*`
- [ ] `docs/reference/*.md` : mise à jour (architecture, commands, naming, storage, scraping, pipeline-internals)
  - `architecture.md` : ajouter section `conf/` package
  - `commands.md` : ajouter `init-config`, `--config` flag, `--category <id|alias>`
  - `storage.md` : expliquer que disks sont paramétrables via `config.json5`
  - `naming.md` : category IDs V15 + labels configurables

**Commit** : `v15.10.4: Update CLAUDE.md and docs/reference/ for V15`

### 10.5 — `INSTALLATION.md`, `CONFIGURATION.md`, `MANUAL.md`, `README.md`

- [ ] `INSTALLATION.md` :
  - Étape obligatoire : `personalscraper init-config` après install
  - Pour migration V14 : `personalscraper init-config --from-current`
- [ ] `CONFIGURATION.md` :
  - Refonte complète : documentation de `config.json5` (tous les champs)
  - Section séparée pour `.env` (secrets seulement)
  - Exemples de `category_rules`, `anime_rule`, `custom_categories`
- [ ] `MANUAL.md` :
  - Commandes mises à jour avec IDs vs aliases
  - Workflow user : NFO override manuel pour re-route
- [ ] `README.md` :
  - Mention quickstart : `init-config`, `run --dry-run`
  - Lien vers MIGRATION.md pour users V14

**Commit** : `v15.10.5: Rewrite INSTALLATION/CONFIGURATION/MANUAL/README for V15`

### 10.6 — Critères d'acceptation : validation finale

Pour chaque critère du DESIGN §Critères d'acceptation V15, vérifier et cocher :

- [ ] #1 : `grep -rE "Disk[1-4]|/Volumes/|\"films\"|\"series\"|..."` dans `personalscraper/` → seul `conf/migration.py::V14_LABEL_TO_ID`
- [ ] #2 : `grep -rE "/Volumes/|\"films\"|\"series\"|\"Disk[1-4]\""` dans `tests/` → 0 (hors fixtures migration)
- [ ] #3 : `init-config` + `config.example.json5` → `config.json5` fonctionnel (test)
- [ ] #4 : `init-config --from-current` sur `.env` V14 fixture → config équivalente (test E2E P4.9)
- [ ] #5 : 1270+ tests V14 passent avec fixture `test_config`
- [ ] #6 : mypy strict 0 erreur (toute la codebase)
- [ ] #7 : CI green sur Python 3.10, 3.11, 3.12, 3.13 (local check, CI execution comes after push)
- [ ] #8 : User externe peut cloner + init-config + run sans toucher `.py` (test manuel ou documenter steps)
- [ ] #9 : Classification pipeline 6 niveaux tous testés (P2.6)
- [ ] #10 : `MIGRATION.md` créé + script auto testé (P4.9)
- [ ] #11 : Golden-table equivalence passe (P2.6)
- [ ] #12 : Validation warnings (dead custom_category, default_label, disk unmounted) émises au load

**Commit** : `v15.10.6: Validate all V15 acceptance criteria (#1-#12)`

### 10.7 — Push + PR + finalize IMPLEMENTATION.md

- [ ] `git push -u origin feat/v15-config-driven`
- [ ] Créer PR via `gh pr create` avec titre `feat(v15): config-driven architecture — remove all hardcoded user values`
- [ ] Body de PR :
  - Résumé scope (DESIGN highlights)
  - Breaking changes : users V14 doivent `init-config --from-current`
  - Migration path détaillé avec lien `MIGRATION.md`
  - Liste commits clés
  - Test plan (checklist acceptance criteria)
- [ ] Mise à jour `docs/IMPLEMENTATION.md` :
  - Marquer toutes les phases P1-P10 comme DONE
  - Ajouter URL de la PR dans le header `**PR:**`
  - Summary final : `**10 phases, 70 sous-phases**`
- [ ] Attendre CI green sur 3.10-3.13
- [ ] Request review

**Commit** : `v15.10.7: Mark V15 as DONE in IMPLEMENTATION.md and link PR`

## Tests de cohérence P10 → DONE

- [ ] Tous les critères d'acceptation #1-#12 validés (P10.6)
- [ ] PR créée avec CI en cours ou green
- [ ] Documentation complète : MIGRATION.md + CONFIGURATION.md + CLAUDE.md + docs/reference/\*
- [ ] `config.example.json5` validé comme source de vérité
- [ ] `IMPLEMENTATION.md` à jour, pointant vers la PR

## Post-merge (manuel, hors PR)

- [ ] Merge PR après review + CI green
- [ ] Sur la machine mainteneur : `git pull`, backup local de `.env` + `.personalscraper/`, `personalscraper init-config --from-current`
- [ ] Smoke test : `personalscraper run --dry-run`
- [ ] Lancer `/archive-version` pour archiver V15 et initialiser V16 (si besoin d'une V16)
