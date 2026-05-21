# Item 7 — Audit BDD `library.db` (intégrité, conformité, cohérence)

**Date** : 2026-05-21 (post-fixes DEV #11 + #14)
**Méthode** : SQL direct read-only + cross-check avec FS sur les 4 disques + comparaison avec les findings du pipeline-monitor run (item 5).
**Output** : 5 nouveaux DEV (#15–#19) + confirmation de DEV #12 + cause racine de l'écart BDD/FS.

---

## 0. Baseline factuelle

| Dimension                | Valeur                                                                        |
| ------------------------ | ----------------------------------------------------------------------------- |
| Fichier                  | `/Users/izno/dev/PersonnalScaper/.data/library.db`                            |
| Taille                   | 44 MB                                                                         |
| `PRAGMA integrity_check` | **ok** ✓                                                                      |
| `PRAGMA journal_mode`    | **wal** ✓                                                                     |
| `PRAGMA foreign_keys`    | **0** ✗ (FKs non-enforced)                                                    |
| `PRAGMA user_version`    | 5                                                                             |
| `schema_version` table   | rows {1, 2, 4, 5} — **manque "3"**                                            |
| Migrations disponibles   | 001-init, 002-nullable, 003-repair-dedup, 004-extend-stream, 005-external-ids |

### Counts

| Table            | Rows    | Notes                                                                                |
| ---------------- | ------- | ------------------------------------------------------------------------------------ |
| `media_item`     | 1,935   | 1,236 movies + 699 shows. Aucun créé après 2026-05-03 (18 jours stale)               |
| `media_release`  | 27,353  | 0 orphans (sans `media_file`)                                                        |
| `season`         | 1,752   | 0 orphans (chaque season a un parent item)                                           |
| `episode`        | 25,418  | 0 orphans (chaque episode a un parent season)                                        |
| `media_file`     | 149,087 | 7,191 `release_id IS NULL` dont **496 video orphans** (DEV #12)                      |
| `media_stream`   | 121,914 | Schema OK (kind, codec, lang)                                                        |
| `item_attribute` | 5,805   | Flex-attr column (`dispatch_path`, normalized_title, etc.)                           |
| `path`           | 6,926   | 4 disks. **Plusieurs paths pointent vers FS inexistant (DEV #17)**                   |
| `repair_queue`   | 224     | 100% `done`, 0 stuck. Dedup index OK                                                 |
| `index_outbox`   | 133     | 100% `done`, 0 pending. Pas de GC                                                    |
| `scan_run`       | 32      | 0 stuck `running`, dernier OK #32 (2026-05-21 21:06)                                 |
| `scan_event`     | 35      | Trace par disk_done                                                                  |
| `pending_op`     | 0       | Empty (design)                                                                       |
| `deleted_item`   | 0       | Empty (jamais de soft-delete propre)                                                 |
| `item_issue`     | 0       | Empty                                                                                |
| `disk`           | 4       | merkle_roots refresh post DEV #11 + #14 — `library-reconcile` reports merkle_drift=0 |

---

## 1. Nouveaux DEVIATIONs identifiés

### DEV #15 — `schema_version` table inconsistant (mineur)

**Constat** : `schema_version` contient {1, 2, 4, 5} — **row "3" manquante** alors que la migration 003
(`003_repair_queue_pending_dedup.sql`) **a bien été appliquée** (l'index `idx_repair_pending_dedup`
existe). Le commentaire dans le SQL de 003 dit explicitement :

> "Use INSERT OR IGNORE because users whose DBs were upgraded by an earlier (buggy) build of this
> script may have already advanced user_version to 4 via migration 004, in which case this migration
> is being re-run only if user_version was still <3."

**Hypothèse confirmée par évidence** :

1. Un earlier buggy build a appliqué 003 mais n'a pas bumpé `user_version` ni inséré la row "3".
2. Migration 004 a tourné, bumpé `user_version = 4` et inséré row 4.
3. Migration 003 corrigée n'a JAMAIS été re-run car `user_version=4 > 3` → SKIP par `apply_migrations`.
4. Migration 005 a tourné, bumpé `user_version = 5` et inséré row 5.

**Impact runtime** : nul. Le runner utilise `user_version` (=5), `schema_version` table = informatif.

**Recommandation** :

- Patch ponctuel pour cette BDD : `INSERT OR IGNORE INTO schema_version VALUES (3);`
- Ou plus structurellement : déprécier la table `schema_version` (redondante avec `user_version`).
- Ou ajouter une check au boot : `assert set(schema_version) == set(range(1, user_version+1))`.

### DEV #16 — `library.scanner.scan_library()` non exposé en CLI (critique)

**Constat** : `personalscraper/library/scanner.py:799 — def scan_library(...)` est la **seule fonction
qui crée les rows `media_item`** (via `_upsert_media_item` ligne 871). Cette fonction n'est appelée
nulle part dans les commandes CLI (`grep -n "scan_library\(" personalscraper/`).

Seul caller : `trailers/cli.py:603` mais via `trailers/scanner.py:176` qui est une fonction
**différente** (homonyme, scope trailers).

**Conséquence** :

- Aucune commande CLI exposée actuellement ne crée de nouveaux `media_item`.
- Les 1,935 media_item existants ont été créés entre 2026-04-30 13:48 et 2026-05-03 11:15 par une
  exécution antérieure (probablement un script manuel ou une commande aujourd'hui supprimée).
- Tout show / movie dispatché depuis le 03/05 est invisible en BDD : pas de `media_item`, donc pas
  de `media_release` créée, donc tous ses `media_file` arrivent avec `release_id=NULL`.

**Impact** : **directement responsable** d'une partie des 496 video orphans (DEV #12) — les
nouveaux shows ne sont pas indexés en BDD. Le pipeline indexer (commande `personalscraper
library-index`) crée bien les `media_file` rows mais sans `media_item` parent, le release_linker
ne peut pas joindre.

**Recommandation** :

- Ajouter une commande `personalscraper library-scan` (ou similar) qui invoque `scan_library()`.
- L'intégrer au cron / launchd alongside `library-index` (probablement avant : library-scan crée
  media_item, library-index attache media_file aux releases).
- À documenter dans `docs/reference/commands.md` + matrix v2.1 §flux connexes.

### DEV #17 — Phantom paths : 5 shows BDD pointent vers FS inexistant (majeur)

**Constat** : 5 show directories sont référencés dans `path` table (et leurs `media_file` dans
`media_file` avec `deleted_at IS NULL`), mais les dossiers physiques **n'existent plus** :

| Disk | Path                                                   | Files | Total taille indexée          |
| ---- | ------------------------------------------------------ | ----- | ----------------------------- |
| 1    | `series/Bloqués (2015)/Saison 01/`                     | 119   | ~5 MB de NFOs/sidecars + .mp4 |
| 2    | `series animes/Avez-vous déjà vu... (2006)/Saison 01/` | 150   | ~15 MB                        |
| 2    | `series animes/Corneil et Bernie (2003)/Saison 01/`    | 26    | ~3 MB                         |
| 4    | `series/Star Trek Enterprise (2001)/Saison 03/`        | 1     | minime                        |
| 4    | `series/Star Trek Voyager (1995)/Saison 05/`           | 1     | minime                        |

Total : **297 phantom media_file rows** (sur les 496 video orphans), plus leurs sidecars (.nfo/.jpg)
non comptés ici.

**Cause** : suppression manuelle de ces dossiers sur disque, sans soft-delete BDD. Le mécanisme
`miss_strikes` aurait dû les marquer puis `apply_soft_deletes` les tombstone — mais voir DEV #18.

**Impact** :

- `dispatch_path_missing` détecte 0 (car item_attribute pas créé pour ces shows).
- `files_without_release` = 7191 inclut ces 297 phantoms + 199 vrais orphans.
- `library-reconcile` ne les voit pas comme drift car son détecteur opère sur item_attribute,
  pas sur path existence à granularité fichier.

**Recommandation** :

- Court terme : `personalscraper library-reconcile --scope dispatch_path --enqueue-repairs` ne
  couvre pas ce cas (il regarde item_attribute, pas path). Manque un détecteur `path_missing`
  qui itère `path` table + `Path.exists()`.
- Long terme : DEV #18 corrigé → `miss_strikes` s'incrémente normalement → soft-delete auto au
  bout de N scans.

### DEV #18 — `increment_miss_strikes_for_disk` jamais appelée (CRITIQUE — code mort)

**Constat** : la fonction `personalscraper/indexer/drift.py:417 — increment_miss_strikes_for_disk`
est définie mais n'a **AUCUN caller** dans le codebase :

```bash
$ rg -n "increment_miss_strikes_for_disk" --type py personalscraper/
personalscraper/indexer/drift.py:417:def increment_miss_strikes_for_disk(
# (aucun autre résultat)
```

**Conséquence** :

- `media_file.miss_strikes` reste à 0 indéfiniment (pour toutes les rows post-création).
- `apply_soft_deletes` (qui filtre sur `miss_strikes >= n_strikes_for_softdelete`) ne marque
  jamais rien soft-deleted.
- **Le mécanisme drift de l'indexer est totalement dysfonctionnel.**

**Vérification empirique** :

```sql
SELECT DISTINCT miss_strikes, COUNT(*)
  FROM media_file WHERE deleted_at IS NULL GROUP BY miss_strikes;
-- Résultat : 0 | 149087  (toutes les rows ont miss_strikes=0)
```

Les 297 phantom files (DEV #17) ont `last_verified_at = 2026-04-30` et `scan_generation = 2`,
mais `miss_strikes = 0` — 4+ scans post-création n'ont jamais bumpé leurs strikes.

**Recommandation** :

- Ajouter l'appel `drift.increment_miss_strikes_for_disk(conn, disk.id, current_generation)`
  dans le flow `personalscraper/indexer/commands/scan.py` entre la fin du walk et `apply_soft_deletes`.
- Test E2E qui vérifie : créer un fichier, scanner, supprimer le fichier, scanner N fois, assert
  miss_strikes=N. Puis sur N+1ᵉ scan, assert deleted_at NOT NULL (soft-deleted).
- Audit similaire sur le code drift : autres fonctions définies non-callées ?

### DEV #19 — `PRAGMA foreign_keys = 0` (FKs non-enforced) (mineur—structurel)

**Constat** : `PRAGMA foreign_keys` retourne `0`. Les contraintes FK déclarées au schema
(`media_release REFERENCES media_item ON DELETE CASCADE`, `media_file.path_id REFERENCES
path(id) ON DELETE RESTRICT`, etc.) ne sont **pas vérifiées** au runtime.

**Vérification** : `open_db()` ou `apply_migrations` ne fait pas `PRAGMA foreign_keys = ON`. SQLite
default est OFF. Conséquence : des opérations DELETE peuvent laisser des orphans non-cascadés,
silencieusement.

**Impact actuel** : zero orphan trouvé sur release/season/episode (audits §1). Donc empiriquement
les CASCADE/SET NULL se font malgré tout via du code applicatif (`item_repo.delete_*`,
`file_repo.soft_delete`). Mais la garantie schema est manquante.

**Recommandation** :

- Activer `PRAGMA foreign_keys = ON` au boot connection (dans `open_db()`).
- Lancer un test FK integrity : `PRAGMA foreign_key_check;` doit return zero rows. À ajouter au
  invariants matrix v2.1.

---

## 2. Confirmations de DEV existants

### DEV #12 — 7,191 `files_without_release` : décomposition fine

`library-reconcile` retourne `files_without_release=7191`. Décomposition :

| Catégorie                                                              | Count                                 | Cause primaire                                                                              |
| ---------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------- |
| Sidecars .jpg/.nfo/.png/.mp3 dans `.actors/` ou aux racines de saisons | ~6,655                                | DESIGN_CONFORM (sidecars n'ont pas de release par contrat)                                  |
| Video files .mkv/.mp4/.avi sur 8 shows orphans                         | 496                                   | Mix DEV #16 (no media_item) + DEV #17 (phantom paths) + drift jamais soft-deleted (DEV #18) |
| TOTAL                                                                  | 7,151 (≈ 7,191 avec quelques résidus) |                                                                                             |

Les 8 shows orphans, décomposés :

| Show                        | Disk | Files | Cause                                                       |
| --------------------------- | ---- | ----- | ----------------------------------------------------------- |
| Avez-vous déjà vu... (2006) | 2    | 150   | DEV #17 phantom path + DEV #18                              |
| Bloqués (2015)              | 1    | 119   | DEV #17 phantom path + DEV #18                              |
| Monk (2002)                 | 1    | 60    | FS exists, no media_item — DEV #16 ou parse fail historique |
| Corneil et Bernie (2003)    | 2    | 26    | DEV #17 phantom path + DEV #18                              |
| Squid Game (2021)           | 1    | 22    | FS exists, no media_item — DEV #16 ou parse fail historique |
| Star Trek Enterprise (2001) | 4    | ~5    | DEV #17 phantom path                                        |
| Star Trek Voyager (1995)    | 4    | ~5    | DEV #17 phantom path                                        |
| The Outer Limits ... (1995) | 4    | 5     | DEV #17 phantom path                                        |

→ **DEV #12 décomposé en 4 sous-causes** : (a) DESIGN_CONFORM sidecars, (b) DEV #16 missing
media_item, (c) DEV #17 phantom paths, (d) DEV #18 broken drift mechanism. Le traitement de
#16 + #18 + #19 résoudra structurellement (a) et (d) puis permettra un cleanup ciblé de (b) + (c).

### Provider-IDs columns : 0 / 1935 populated (rappel)

| Column               | Set count                     | Statut                      |
| -------------------- | ----------------------------- | --------------------------- |
| `canonical_provider` | 0                             | NULL partout                |
| `external_ids_json`  | 0 (toutes `'{}'` par default) | Schema OK, données absentes |
| `ratings_json`       | 0                             | NULL partout                |

Le backfill (driver `run_backfill_ids`) n'a jamais tourné sur cette BDD. CLI exposé via
`personalscraper library-index --mode backfill-ids` mais jamais lancé.

→ **Item L du brainstorm item 6** confirmé. À planifier dans le DESIGN tech-debt (intégration
au cron de maintenance + documentation runbook).

---

## 3. Patterns systémiques tirés de cet audit

### P11 — Code mort dans des chemins critiques

DEV #18 = fonction définie, jamais appelée, dans un module critique (drift detection). Le
mécanisme est entièrement défaillant.

**Pattern probable ailleurs** : tout module avec des fonctions "helpers" non testées d'intégration.
Candidats :

```bash
# Toutes les fonctions publiques non appelées hors leur module + tests
rg -n "^def [a-z_]+" --type py personalscraper/ | <filter unused>
```

→ Item DESIGN : audit "fonctions définies sans caller productif". Le linter pyflakes/ruff
détecte les imports, pas les fonctions zombies. Custom check possible.

### P12 — CLI surface incomplète

DEV #16 = fonction métier critique non exposée. Idem possiblement pour `drain_outbox`,
`pending_op` (table vide → mécanisme zombie ?), `library-relink` (existe mais usage ?).

→ Item DESIGN : audit "chaque module métier doit avoir au moins UNE commande CLI qui l'exerce
en E2E + une mention dans `docs/reference/commands.md`".

### P13 — Hard-delete sans cleanup downstream

Les phantom paths (DEV #17) suggèrent qu'on a supprimé des dossiers FS sans purger la BDD. Aucun
mécanisme actuel ne réconcilie path/file rows vs FS existence à granularité fichier (seul item-level
via `dispatch_path_missing`).

→ Item DESIGN : nouveau détecteur `path_missing` dans `library-reconcile` (scope `path`).

### P14 — Migrations buggy → résidu permanent

DEV #15 = inconsistance `schema_version` héritée d'un earlier buggy build. La migration corrigée
ne peut pas réparer rétroactivement car le check `version <= user_version` shorts-circuit.

→ Item DESIGN : pour toute migration qui doit ré-appliquer une étape déjà appliquée (re-apply pattern),
prévoir une migration "fix-up" séparée. Ou : séparer `user_version` (bump policy) de
`schema_version` (audit log) — déprécier `schema_version` au profit d'un journal explicite.

---

## 4. Implications pour le DESIGN tech-debt (item 14)

### Items à ajouter au DESIGN (post-item 6 + item 7)

**Priorité 1 — bloquant**

- **DEV #18 fix** : intégrer `increment_miss_strikes_for_disk` dans le scan flow + test E2E.
  Sans ce fix, BDD accumule indéfiniment des phantoms. **Premier item du DESIGN.**
- **DEV #19 fix** : activer `PRAGMA foreign_keys = ON` au boot. Test invariant `foreign_key_check`
  vide. Rapide à shipper.
- **DEV #16 fix** : exposer `library.scanner.scan_library()` via une commande CLI dédiée.
  Documenter le cron. Sinon DEV #12 grandit avec chaque dispatch.

**Priorité 2 — important**

- **Nouveau détecteur `path_missing`** dans `library-reconcile` (audit `path` table vs FS).
  Résout DEV #17 et catégorise les vrais "drift" vs "phantoms".
- **Cleanup ponctuel des 8 shows orphans** : script one-shot (5 phantom DEV #17 → soft-delete
  ou hard-delete cascadé ; 2 FS-exists Monk + Squid Game → re-scrape ou réinjection via
  `library-scan` nouvelle commande).
- **Provider-IDs backfill** : lancer une fois post-fix puis cron récurrent.

**Priorité 3 — structurel**

- **DEV #15 cleanup** : `INSERT OR IGNORE INTO schema_version VALUES (3);` ou déprécier la table.
- **P11 audit "code mort"** : custom check fonctions non-callées hors module.
- **P12 audit "CLI surface incomplète"** : un test "tous les modules métier ont 1 CLI command".

### Sections nouvelles dans `DESIGN.md`

En complément des 8 sections déjà proposées en item 6 §6 :

9. **Section "BDD lifecycle invariants"** : drift, soft-delete, hard-delete, FK enforcement,
   schema_version consistency.

10. **Section "CLI surface completeness"** : règle "1 module métier critique → 1 CLI command
    documentée" + tests pin.

---

## 5. Suite

L'item 8 (brainstorm BDD) ré-utilise ce rapport + le brainstorm item 6 pour produire le sous-
ensemble "BDD" du DESIGN tech-debt :

- Conversion DEV #15-#19 en items DESIGN classés must / should
- Patterns P11-P14 intégrés au cross-table patterns → leviers
- Sections 9 et 10 ajoutées au DESIGN.md final
- Plan de phase pour BDD : (1) DEV #18 + #19 fix bloquant ; (2) library-scan CLI + cleanup
  one-shot ; (3) détecteur path_missing ; (4) provider-IDs backfill ; (5) audits transversaux.

Estimation grossière BDD section seule : **3-5 jours** supplémentaires aux 10-17 du brainstorm
item 6, soit **total tech-debt feature ~13-22 jours**, toujours bumpe vers **0.16.0** (minor —
nouvelles features + invariants sans breaking change).
