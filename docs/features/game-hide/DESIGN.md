# DESIGN — game-hide : détecter les jeux (ISO) et les masquer de la médiathèque

**Codename** : `game-hide` · **Type** : `feat` · **Bump** : minor (0.60.0 → 0.61.0)
**Ticket** : #334 · **Merge** : auto

## Constitution produit (CONTRAIGNANT)

Sert `docs/reference/product-intent.md` **§2 (véridicité)** : la médiathèque doit dire la
vérité sur son contenu — un item listé « à trier » est un média. Un jeu (image disque `.iso`)
n'est pas un média ; le lister dans l'UII Medias est un **mensonge d'inventaire**. §méthode :
aucune disparition silencieuse — chaque item masqué est journalisé (auditable), et le masquage
est **précision-first** (ne jamais masquer un vrai média par erreur).

## Problème (terrain vérifié 2026-07-28)

`/Volumes/IznoServer SSD/A TRIER/098-AUTRES/Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto/`
contient `Marvels.Spider-Man.2-Mephisto.iso` + `msm2.nfo`. Le sorter classe ce dossier en
`FileType.OTHER` (l'extension `.iso` n'est ni vidéo ni app, aucun enfant vidéo, pas de token
video-release), donc → catégorie `098-AUTRES`. Or `other` n'est **pas** dans
`_TERMINAL_KINDS` (`personalscraper/web/staging/read_model.py:82`), donc l'item **remonte
comme item de pipeline** dans l'UI Medias, à trier — alors que ce n'est pas un média.

## Décision opérateur

Les jeux doivent être **détectés** puis **masqués** de la médiathèque (comme `ebook` / `audio`
/ `app`, des kinds terminaux). « Masqués » = ne remontent pas dans l'UI Medias. L'opérateur n'a
PAS demandé une étagère « jeux » navigable — seulement le masquage.

## Approche retenue : détection + filtre read-model (aucun changement de config partagée)

Deux mécanismes ont été pesés :

| Option                                                   | Mécanisme                                                                                                       | Verdict                                                                                                                                                                                                                                                                                                                                                                      |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — catégorie terminale dédiée**                       | `FileType.GAME` + entrée `staging_dirs` `099-JEUX` + `_TERMINAL_KINDS += "game"` + migration de l'item existant | **Écartée (pour l'instant)** : la config est partagée prod/staging ; ajouter une `staging_dirs` est un changement de config de boot (risque `project_config_drift_pattern`), impose de créer le dossier disque, et exige une migration/déplacement de l'item existant. Documentée ici comme **évolution différée** si l'opérateur veut plus tard une étagère jeux navigable. |
| **B — filtre item-level dans le read-model** _(retenue)_ | prédicat `is_game_release()` + saut de l'item dans `scan_staging_media`                                         | **Retenue** : satisfait l'intention littérale (masquer), **auto-gère l'item existant** (aucun déplacement — le filtre s'applique au prochain rendu), **zéro changement de config**, zéro risque de boot.                                                                                                                                                                     |

### Contrat de détection — `is_game_release(media_dir: Path) -> bool`

**Précision-first** (un faux positif masque un vrai média → interdit). Vrai **si et seulement si** :

1. Le dossier contient une **image disque** comme charge utile primaire — extension dans
   `DISC_IMAGE_EXTENSIONS = {iso, bin, mds, mdf, nrg, cue}` — ET
2. Aucun enfant **vidéo** (sinon c'est un rip média, pas un jeu) ET aucun marqueur TV
   (`_has_tvshow_markers`), ET
3. Le nom du dossier (ou du fichier image) **ne porte PAS** de token video-release
   (`_looks_like_video_release` : 1080p/BluRay/x264/WEB-DL… ⇒ image disque d'un FILM/rip, pas
   un jeu), ET
4. Le nom porte un **signal jeu** : groupe de repack connu (`GAME_RELEASE_GROUPS` =
   Mephisto/FitGirl/DODI/RUNE/CODEX/PLAZA/SKIDROW/TENOKE/RaZoR/EMPRESS/GOG/ElAmigos/…) **OU**
   un token de version `vX.Y[.Z]` (ex. `v1.526.0`) **OU** un token plateforme
   (`PS3/PS4/PS5/Switch/NSW/XBOX/PC`), collé au style scène.

Le point 3 est la garde anti-faux-positif clé : une image disque de film (`Movie.2009.1080p.
BluRay.iso`) porte un token video-release et n'est donc **jamais** un jeu ; un jeu
(`...v1.526.0.FRENCH-Mephisto`) porte un token jeu et **aucun** token video-release.

Le prédicat est **pur** (nom + extensions, pas d'I/O provider), donc golden-testable.

### Filtre read-model

Dans `scan_staging_media` (`read_model.py`), pour chaque catégorie **non terminale**, après la
détection d'artefact, si `is_game_release(child)` : **ne pas ajouter l'item** ET émettre un log
structuré `staging_game_hidden` (catégorie, dossier) — pas de disparition silencieuse (§méthode).
Les items « other » qui ne sont PAS des jeux (médias non reconnus à trier) restent visibles.

## Non-buts

- Pas d'étagère « jeux » navigable (option A différée).
- Pas de déplacement physique de l'item (le filtre suffit ; le jeu reste inerte en 098-AUTRES,
  non scrapable/dispatchable).
- Pas de nouvelle `FileType`, pas de changement de config, pas de migration.
- Pas de détection de jeux hors image-disque (installeurs `.exe` multi-parties) — hors périmètre.

## ACCEPTANCE (commandes exécutables)

- **ACC-01** — `python -c "from personalscraper.sorter.game import is_game_release; from pathlib import Path; ..."`
  sur un dossier golden `Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto/` (iso + nfo) ⇒ `True`.
  Exécuté par `pytest tests/sorter/test_game.py -q` → `passed`.
- **ACC-02** — un dossier golden image-disque de FILM (`Movie.2009.1080p.BluRay.iso`) ⇒ `False`
  (garde anti-faux-positif). `pytest tests/sorter/test_game.py -q` → `passed`.
- **ACC-03** — read-model : un dossier jeu placé dans la catégorie OTHER n'apparaît PAS dans
  `scan_staging_media(...)`, un dossier média non reconnu dans OTHER apparaît toujours.
  `pytest tests/unit/web/staging/test_read_model_game_filter.py -q` → `passed`.
- **ACC-04** — `make check` vert ; `make openapi` sans drift (aucun changement de contrat, mais
  on vérifie l'absence de dérive).
- **ACC-05** — preuve terrain : l'item existant `Marvels.Spider-Man.2` n'apparaît plus dans
  l'onglet Medias de `tm-staging.` (harnais Chrome 390 px) ; un autre item « other » (s'il y en
  a) reste visible. Log `staging_game_hidden` présent pour l'item masqué.

## Phases (indicatif — `/implement:plan` fait foi)

1. **Détection** — `personalscraper/sorter/game.py` : `DISC_IMAGE_EXTENSIONS`,
   `GAME_RELEASE_GROUPS`, `is_game_release()` + golden tests (ACC-01, ACC-02).
2. **Filtre read-model** — `scan_staging_media` saute les jeux + log `staging_game_hidden` +
   test d'intégration (ACC-03).
3. **ACC + preuve** — `make check`, `make openapi`, preuve Chrome 390 px sur staging (ACC-04, ACC-05).
