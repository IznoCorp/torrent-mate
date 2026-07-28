# Phase 02 — Filtre read-model + log

**Goal**: les jeux détectés ne remontent plus dans l'UI Medias (masquage item-level), sans
disparition silencieuse (log), sans masquer les autres items « other ».

## Surface

| Fichier                                                           | Action                                                                                                                                                                                                                                                                                                             |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `personalscraper/web/staging/read_model.py`                       | Dans `scan_staging_media`, boucle `for child in children` (catégories non terminales) : après le saut d'artefact, si `is_game_release(child)` ⇒ `continue` (ne pas construire l'item) ET `logger.debug("staging_game_hidden", category=category, folder=child.name)`. Import local de `is_game_release` (phase 1). |
| `tests/unit/web/staging/test_read_model_game_filter.py` (**NEW**) | Un dossier jeu (iso + token Mephisto) placé dans la catégorie OTHER n'apparaît PAS dans `scan_staging_media(...)` (ACC-03) ; un dossier « other » **non-jeu** (média non reconnu, ex. dossier avec un `.mkv` ambigu ou un nom sans signal) apparaît toujours ; le log `staging_game_hidden` est émis pour le jeu.  |

## Règles

- Le filtre s'applique **uniquement** dans les catégories non terminales déjà parcourues (le
  `continue` sur `_TERMINAL_KINDS` reste avant). Un jeu en OTHER est masqué ; un vrai média en
  OTHER reste visible (précision-first, garde phase 1).
- **Aucune disparition silencieuse** (§méthode) : chaque masquage émet `staging_game_hidden`.
- Aucun changement de contrat API (aucun champ Pydantic ajouté) ⇒ `make openapi` ne doit pas
  dériver ; le vérifier au gate.
- Pas de changement de config, pas de nouvelle `FileType`.

## Gate

`pytest tests/unit/web/staging/test_read_model_game_filter.py -q` vert ; `make openapi` sans
drift ; aucune régression des tests read-model existants (`pytest tests/unit/web/staging -q`).
