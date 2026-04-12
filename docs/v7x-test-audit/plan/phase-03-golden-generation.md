# Phase 3 — Génération Golden Files (MANUELLE)

## Objectif

Exécuter le pipeline sur les 2 torrents de test (Jumanji + Malcolm S01), inspecter les résultats, et les figer en golden files JSON validés humainement.

## Prérequis

- qBittorrent en cours d'exécution
- `.env` configuré avec `TMDB_API_KEY` et `TVDB_API_KEY`
- Les `.torrent` files dans `assets/torrents/`
- Phase 2 terminée (format JSON défini)

## ⚠️ PHASE INTERACTIVE

Cette phase nécessite l'intervention de l'utilisateur pour valider les résultats. Ne PAS committer les golden files sans validation humaine.

## Sous-phases

### 7x.3.1 — Exécuter pipeline + capturer résultats Jumanji

- [ ] Ajouter un torrent Jumanji via qBittorrent (ou utiliser le test E2E existant en mode capture)
- [ ] Exécuter le pipeline : ingest → sort → scrape (movies_only) → verify → dispatch (dry-run)
- [ ] Capturer les résultats :
  - Lister les fichiers dans le dossier scrappé : `ls -la "001-MOVIES/Jumanji (1995)/"`
  - Lire le NFO : `cat "001-MOVIES/Jumanji (1995)/Jumanji.nfo"` (ou le nom exact)
  - Noter le DispatchResult retourné par run_dispatch(dry_run=True)
- [ ] **PRÉSENTER À L'UTILISATEUR** pour validation :
  - Titre, année, TMDB ID, IMDB ID corrects ?
  - Genres corrects ?
  - Catégorie correcte ?
  - Artwork présent et correct ?
  - Dispatch vers le bon disque ?
- [ ] Écrire les golden files dans `assets/torrents/expected/jumanji_1995/` :
  - `expected_nfo.json` — avec les invariants validés
  - `expected_artwork.json` — avec les fichiers artwork trouvés
  - `expected_structure.json` — avec l'arbre de fichiers
  - `expected_dispatch.json` — avec l'action et les disques éligibles
- [ ] Nettoyer les artefacts de staging

**Commit** : `v7x.3.1: Add golden files for Jumanji (1995) — validated by user`

### 7x.3.2 — Exécuter pipeline + capturer résultats Malcolm S01

- [ ] Même processus pour Malcolm In The Middle S01
- [ ] Points spécifiques TV :
  - Vérifier le nombre d'épisodes (16 pour S01)
  - Vérifier les noms d'épisodes renommés (S01E01 - Pilot, etc.)
  - Vérifier tvshow.nfo (TVDB ID, pas TMDB ID)
  - Vérifier les épisodes NFO (S01E01.nfo, etc.)
  - Vérifier la structure saison (Saison 01/)
- [ ] **PRÉSENTER À L'UTILISATEUR** pour validation
- [ ] Écrire les golden files dans `assets/torrents/expected/malcolm_in_the_middle_s01/`
- [ ] Nettoyer les artefacts de staging

**Commit** : `v7x.3.2: Add golden files for Malcolm In The Middle S01 — validated by user`
