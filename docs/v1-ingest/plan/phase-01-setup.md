# Phase 1 — Setup projet

## Objectif

Mettre en place la structure de fichiers, la configuration, et le .gitignore.

## Sous-phases

### 1.1 — Créer la structure `099-SCRIPTS/pipeline/`

- [ ] Créer le dossier `099-SCRIPTS/pipeline/`
- [ ] Créer `__init__.py` (package Python)
- [ ] Créer les fichiers vides : `ingest.py`, `qbit_client.py`, `tracker.py`

**Commit** : `v1.1.1: Scaffold pipeline package structure`

### 1.2 — Fichier .env et .env.example

- [ ] Créer `.env.example` avec toutes les variables documentées (sans valeurs sensibles)
- [ ] Créer `.env` avec les vraies valeurs (demander le mot de passe qBit à l'utilisateur)
- [ ] Ajouter `.env` et `ingested_torrents.json` au `.gitignore` racine
- [ ] Ajouter `099-SCRIPTS/pipeline/logs/` au `.gitignore`

**Commit** : `v1.1.2: Add pipeline config (.env.example) and update .gitignore`

### 1.3 — Vérifier les dépendances Python

- [ ] Vérifier que `requests` et `python-dotenv` sont installés
- [ ] Créer `099-SCRIPTS/pipeline/requirements.txt` si nécessaire

**Commit** : `v1.1.3: Add pipeline requirements.txt`
