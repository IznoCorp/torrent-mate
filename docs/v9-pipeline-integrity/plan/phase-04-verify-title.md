# Phase 4 — Verify renforce + titre local FR

## Objectif

Renforcer les checks verify (poster, episodes renommes, dossiers vides) et implementer `_resolve_title()` pour le titre FR. Corrige #28 (Jury Duty EN → FR).

## Sous-phases

### 9.4.1 — Verify checks renforces

- [x] Ajouter check `poster_present` dans `check_movie()` : `Title-poster.jpg` existe
- [x] Ajouter check `poster_present` dans `check_tvshow()` : `poster.jpg` existe
- [x] Ajouter check `episode_renamed` dans `check_tvshow()` : videos dans `Saison XX/` matchent `S\d{2}E\d{2} - .+\.\w+`
- [x] Ajouter check `no_empty_dirs` dans `check_movie()` et `check_tvshow()` : recursif
- [x] Tous les checks en severity ERROR (bloquants pour dispatch)
- [x] Mettre a jour les tests existants verify pour les nouveaux checks
- [x] Tests : film sans poster → blocked
- [x] Tests : serie avec episode non-renomme → blocked
- [x] Tests : dossier avec sous-dossier vide → blocked
- [x] Tests : film/serie valide avec poster + episodes renommes → valid

**Commit** : `v9.4.1: Reinforce verify checks — poster, episodes, empty dirs`

### 9.4.2 — \_resolve_title titre local FR

- [x] Ajouter `scraper_prefer_local_title: bool = True` dans `config.py` Settings
- [x] Ajouter dans docstring Attributes de Settings
- [x] `Scraper._resolve_title(match, api_data, fallback) -> str`
- [x] Quand `prefer_local_title=True` : utilise `api_data["name"]` (series) ou `api_data["title"]` (films) qui sont deja en FR via `scraper_language`
- [x] Fallback sur `match.api_title` si le titre local est vide ou identique au titre original
- [x] Utiliser `_resolve_title` dans `_scrape_movie` et `_scrape_tvshow` pour le rename
- [x] Tests : titre FR disponible → utilise FR
- [x] Tests : titre FR absent → fallback sur titre API
- [x] Tests : `prefer_local_title=False` → utilise titre API toujours
- [x] Tests : config setting lu depuis .env

**Commit** : `v9.4.2: Add _resolve_title() for local FR title preference`

### 9.4.3 — Fixer check_tvshow pour tvshow.nfo valide

- [x] Verifier que `check_tvshow` valide `tvshow.nfo` contient `<uniqueid>` (comme pour films)
- [x] S'assurer que le check existant `nfo_valid` est bien present et fonctionnel
- [x] Ajouter test explicite : tvshow.nfo sans `<uniqueid>` → blocked

**Commit** : `v9.4.3: Verify tvshow.nfo uniqueid check is enforced`
