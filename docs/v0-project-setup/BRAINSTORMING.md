# V0 — PROJECT SETUP : Brainstorming

> Mise en place du projet Python propre + intégration de FileMate dans le projet

## Contexte

Le projet actuel est un dossier de staging media avec des scripts Python legacy éparpillés dans `099-SCRIPTS/`.
Il faut le transformer en un vrai projet Python packagé, avec une structure moderne inspirée de TorrentMaker.

FileMate (`~/dev/FileMate/`) doit être intégré directement dans ce projet car il n'est utilisé que pour ça.

## Décisions prises

### Template de référence
- **TorrentMaker** (`~/dev/TorrentMaker/`) comme modèle de structure
- `pyproject.toml` PEP 621 avec setuptools
- Python >= 3.10

### Outillage
- **Ruff** pour linting + formatting (remplace Black/isort/flake8)
- **pytest** pour les tests
- **Click** pour le CLI (groups de commandes)
- **pydantic-settings** pour la config (type-safe, auto .env)
- **Makefile** pour l'automatisation (clean, test, lint, format, install-dev)

### Structure du package
- Layout plat (pas de `src/`) : `media_pipeline/` à la racine du projet
- CLI avec sous-commandes : `media-pipeline ingest`, `media-pipeline sort`, etc.
- Entry point dans `pyproject.toml` : `[project.scripts]`

### Intégration FileMate
- Copier le code source de FileMate dans le package (pas de dépendance externe)
- Adapter au nouveau système de config (pydantic-settings au lieu de .env custom)
- Conserver l'architecture strategy pattern
- Améliorer le nettoyage de noms (approche regex dynamique plutôt que fichiers statiques)

## Questions ouvertes

- [ ] Nom du package Python ? `media_pipeline` ? `mediasort` ? `media_triage` ?
- [ ] Les scripts legacy dans `099-SCRIPTS/` : on les garde en parallèle ou on les intègre/supprime ?
- [ ] Le `.env` du pipeline (V1) et le `.env` de FileMate doivent fusionner en un seul

## Ressources

- Template : `/Users/izno/dev/TorrentMaker/`
- FileMate : `/Users/izno/dev/FileMate/`

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
