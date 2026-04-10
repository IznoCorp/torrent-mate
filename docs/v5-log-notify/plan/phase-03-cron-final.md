# Phase 3 — Cron + alias + validation finale

## Objectif

Configurer l'exécution automatique et valider le projet complet.

## Sous-phases

### 5.3.1 — Setup cron

- [ ] Supprimer toute entrée cron legacy (media-ingest, ingest.py) — vérifier avec `crontab -l`
- [ ] Ajouter l'entrée crontab : `0 3 * * * personalscraper run`
- [ ] Vérifier qu'il n'y a qu'UNE seule entrée personalscraper dans le crontab
- [ ] Rediriger stdout/stderr vers les logs
- [ ] Tester l'exécution cron

**Commit** : `v5.3.1: Configure daily cron job at 3am`

### 5.3.2 — Documentation et CLAUDE.md

- [ ] Mettre à jour CLAUDE.md avec toutes les commandes finales
- [ ] Documenter le .env.example complet
- [ ] Mettre à jour le Directory Structure dans CLAUDE.md
- [ ] Mettre à jour IMPLEMENTATION.md : marquer V5 et toutes les versions complètes

**Commit** : `v5.3.2: Update CLAUDE.md and finalize documentation`

### 5.3.3 — Validation finale du projet

- [ ] `personalscraper run --dry-run --verbose` fonctionne end-to-end
- [ ] `make test` passe (tous les tests V0→V5)
- [ ] `make lint` passe
- [ ] Le cron est configuré
- [ ] Le .env contient toutes les valeurs nécessaires
- [ ] Git status propre, tout committé

**Commit** : `v5.3.3: Project complete — full pipeline validated`
