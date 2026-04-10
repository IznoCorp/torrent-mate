# Phase 4 — Archivage scripts legacy + nettoyage

## Objectif

Archiver les scripts legacy de 099-SCRIPTS/ et nettoyer le repo.

## Sous-phases

### 0.4.1 — Archiver les scripts

- [ ] Copier `099-SCRIPTS/` vers `~/dev/099-SCRIPTS-archive/`
- [ ] Vérifier que la copie est complète
- [ ] Supprimer `099-SCRIPTS/` du repo avec `git rm -r`
- [ ] Supprimer les `.gitkeep` des dossiers de tri si `099-SCRIPTS/` les référençait

**Commit** : `v0.4.1: Archive legacy scripts to ~/dev and remove from repo`

### 0.4.2 — Mettre à jour CLAUDE.md

- [ ] Retirer les références à `099-SCRIPTS/` dans CLAUDE.md
- [ ] Ajouter la documentation du package `personalscraper`
- [ ] Mettre à jour la section Commands avec les nouvelles commandes CLI
- [ ] Mettre à jour le Directory Structure

**Commit** : `v0.4.2: Update CLAUDE.md for personalscraper package`

### 0.4.3 — Validation finale V0

- [ ] `make install-dev` fonctionne
- [ ] `personalscraper --help` affiche toutes les commandes
- [ ] `make test` passe (tous les tests)
- [ ] `make lint` passe
- [ ] `git status` est propre

**Commit** : `v0.4.3: V0 complete — project scaffolded and validated`
