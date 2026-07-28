# Phase 01 — Détection : `is_game_release`

**Goal**: un prédicat pur, précision-first, qui reconnaît une release de jeu (image disque +
signal jeu) et rejette tout média (film/série), y compris une image disque de FILM.

## Surface

| Fichier                                    | Action                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/sorter/game.py` (**NEW**) | `DISC_IMAGE_EXTENSIONS = frozenset({"iso","bin","mds","mdf","nrg","cue"})` ; `GAME_RELEASE_GROUPS` (frozenset minuscules : mephisto, fitgirl, dodi, rune, codex, plaza, skidrow, tenoke, razor, empress, gog, elamigos, flt, hoodlum, …) ; `_GAME_VERSION_RE` (`(?i)\bv\d+\.\d+(?:\.\d+)*\b`) ; `_PLATFORM_RE` (`(?i)\b(ps[345]                                                                                     | nsw | switch | xbox | pc)\b`) ; `is_game_release(media_dir: Path) -> bool` (contrat DESIGN §détection). |
| `personalscraper/sorter/file_type.py`      | Réutiliser `_looks_like_video_release` (déjà présent) pour la garde anti-faux-positif (film ISO). Aucune modif de classification en phase 1 (le sorter continue de router les jeux en OTHER — le masquage est phase 2).                                                                                                                                                                                             |
| `tests/sorter/test_game.py` (**NEW**)      | Golden : dossier `Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto/` (iso+nfo) ⇒ `True` (ACC-01) ; dossier `Movie.2009.1080p.BluRay.iso` (image disque + token video-release) ⇒ `False` (ACC-02, garde) ; dossier vidéo `Show.S01.1080p/` ⇒ `False` ; dossier ebook/pdf ⇒ `False` ; iso nu **sans** signal jeu (`disc.iso` seul) ⇒ `False` (précision — pas de signal = pas un jeu). Tests **rouge-avant** documentés. |

## Règles

- **Précision-first** : `is_game_release` = (a) contient une image disque, (b) aucun enfant vidéo
  ni marqueur TV, (c) le nom NE porte PAS de token video-release, (d) le nom porte un signal jeu
  (groupe repack OU version `vX.Y[.Z]` OU plateforme). Les 4 conditions sont requises.
- Prédicat **pur** : nom + extensions des enfants uniquement, aucun I/O réseau/provider.
- Utiliser `pathlib.Path.iterdir()` en tolérant l'`OSError` (fail-soft → `False`).
- Docstrings Google-style ; commentaires « pourquoi » sur la garde video-release.

## Gate

`pytest tests/sorter/test_game.py -q` vert ; `ruff check` + `mypy` sur `personalscraper/sorter/game.py`
verts ; rouge-avant vérifié (le test échoue sans l'implémentation).
