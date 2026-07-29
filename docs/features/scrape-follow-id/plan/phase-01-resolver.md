# Phase 01 — Résolveur `resolve_followed_tvdb`

**Goal**: un résolveur pur, fail-soft, qui rend l'ID TVDB du suivi pour un dossier de show
provenant d'une série suivie, sinon `None`.

## Surface

| Fichier                                                    | Action                                                                                                                                                                                                                         |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `personalscraper/scraper/follow_provenance.py` (**NEW**)   | `resolve_followed_tvdb(show_dir: Path, grabbed: list[WantedItem], follows_by_id: dict[int, str]) -> int                                                                                                                        | None`. Parse `(saison, épisode)`du dossier (réutiliser`NameCleaner.extract_season_episode`/ le parseur d'épisodes du scraper). Sélectionne les`grabbed`(kind='episode',`media_ref.tvdb_id`défini) dont`(season, episode)`∈ épisodes du dossier. Garde titre :`rapidfuzz`entre le titre nettoyé du dossier et le titre du suivi (seuil ~80). Renvoie l'unique`tvdb_id`recouvrant, sinon`None` (ambiguïté / dissemblance / rien). |
| `personalscraper/scraper/orchestrator.py` (ou composition) | (préparé phase 2) — signature de `follow_tvdb_resolver`. Rien d'implémenté ici en phase 1 hormis, si utile, un helper de construction pur.                                                                                     |
| `tests/scraper/test_resolve_followed_tvdb.py` (**NEW**)    | ACC-01 (Rooster S01E06-E10 grabbed tvdb 457770 titre « Rooster » ⇒ 457770) ; ACC-02 (deux suivis tvdb A/B partageant S01E06 ⇒ None ; titre dissemblable ⇒ None) ; ACC-03 (liste vide / exception interne ⇒ None). Rouge-avant. |

## Règles

- **Pur** : le résolveur reçoit les données (grabbed wanted + titres de suivis) en argument — pas
  d'I/O DB dans la fonction cœur (le wiring lira le store en phase 2). Facile à golden-tester.
- **Fail-soft** : toute exception interne (parse, fuzzy) → `None`.
- **Anti-collision** : n'affirme un id QUE si un seul tvdb recouvre le dossier ET la garde titre
  passe. Sinon abstention (`None`) → le match libre reprend la main.
- Séparation multi-provider : uniquement `media_ref.tvdb_id` du suivi ; pas de tmdb/imdb ici.

## Gate

`pytest tests/scraper/test_resolve_followed_tvdb.py` vert ; `ruff`/`mypy` sur les fichiers ; rouge-avant vérifié.
