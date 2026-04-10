# Phase 5 — Cron + alias CLI

## Objectif

Mettre en place l'exécution automatique (cron 3h) et l'alias pour le lancement manuel.

## Sous-phases

### 5.1 — Setup cron

- [ ] Créer le dossier `099-SCRIPTS/pipeline/logs/` (pour la sortie cron)
- [ ] Ajouter l'entrée crontab : `0 3 * * *` exécutant `ingest.py`
- [ ] Tester que le cron fonctionne (exécution ponctuelle via `crontab -l`)

**Commit** : `v1.5.1: Configure daily cron job at 3am`

### 5.2 — Alias shell

- [ ] Définir un alias `media-ingest` (dans BashMate ou .zshrc)
- [ ] Documenter l'usage dans CLAUDE.md (section Commands)

**Commit** : `v1.5.2: Add media-ingest shell alias and update docs`
