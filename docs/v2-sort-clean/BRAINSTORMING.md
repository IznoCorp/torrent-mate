# V2 — SORT + CLEAN : Brainstorming

> Tri automatique via FileMate (amélioré) + nettoyage des noms de fichiers

## Contexte

FileMate (`~/dev/FileMate/`) est déjà fonctionnel pour le tri par type de fichier.
Il faut l'intégrer au pipeline et potentiellement l'améliorer.

## État actuel de FileMate

- Architecture propre : strategy pattern, factory, config Pydantic
- Tri par type (MOVIE, TVSHOW, EBOOK, AUDIO, APP, ANDROID)
- Fuzzy matching récent (Feb 2026) pour éviter les doublons de dossiers
- Nettoyage via `clean_words.txt` / `clean_chars.txt`
- Support `--dry-run`, `--verbose`, `--clean`, `--sort`

## Améliorations potentielles

- [ ] Nettoyage plus agressif des noms de fichiers
- [ ] Renommage automatique des épisodes TV → `S01E01 - Titre.ext`
- [ ] Intégration comme module Python (import) plutôt que CLI subprocess
- [ ] Gestion des sous-titres (.srt, .sub) associés aux vidéos
- [ ] Meilleure détection films vs séries (cas ambigus)

## Questions ouvertes

- [ ] FileMate modifié dans son repo ou forké/copié dans ce projet ?
- [ ] Quels mots/patterns manquent dans clean_words.txt ?
- [ ] Faut-il créer les dossiers saison (Saison 01, etc.) à cette étape ?

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
