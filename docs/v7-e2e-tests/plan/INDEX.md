# V7 — E2E TESTS : Plan d'implémentation

> Tests end-to-end complets du pipeline V1→V6 avec de vrais fichiers torrents

## Phases

| #   | Phase                                    | Fichier                                                | Status |
| --- | ---------------------------------------- | ------------------------------------------------------ | ------ |
| 1   | Infrastructure test (registry, markers)  | [phase-01-test-infra.md](phase-01-test-infra.md)       | [x]    |
| ·   | _Contrôle de cohérence P1→P2_            |                                                        | [ ]    |
| 2   | Setup torrents + cleanup sécurisé        | [phase-02-setup-cleanup.md](phase-02-setup-cleanup.md) | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_            |                                                        | [ ]    |
| 3   | Assertions pipeline                      | [phase-03-assertions.md](phase-03-assertions.md)       | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_            |                                                        | [ ]    |
| 4   | Tests E2E films                          | [phase-04-e2e-movies.md](phase-04-e2e-movies.md)       | [ ]    |
| ·   | _Contrôle de cohérence P4→P5_            |                                                        | [ ]    |
| 5   | Tests E2E séries + test complet pipeline | [phase-05-e2e-tvshows.md](phase-05-e2e-tvshows.md)     | [ ]    |

## Dépendances entre phases

```
Prérequis : V6 complet (toutes les phases)
      ↓
Phase 1 (infra) ──┐
Phase 2 (setup) ──┤─→ Phase 4 (E2E movies)
Phase 3 (assert) ─┘         ↓
                     Phase 5 (E2E complet)
```

Phases 1-3 : modules de support (infra, setup, assertions).
Phase 4 : premier test E2E complet avec des films.
Phase 5 : test E2E séries + test pipeline complet (films + séries ensemble).

## Contrôles de cohérence

### Après Phase 1 (Infrastructure test)

- [x] `TestRegistry` persiste en JSON et se recharge correctement
- [x] `place_marker()` crée le fichier avec le bon contenu
- [x] `verify_marker()` retourne False si marker absent, UUID différent, ou chemin hors registre
- [x] `find_orphan_markers()` détecte les markers de sessions précédentes

### Après Phase 2 (Setup + Cleanup)

- [ ] `TorrentSetup` ajoute des magnets à qBit avec la catégorie "e2e-test"
- [ ] `wait_for_completion()` respecte le timeout et retourne les statuts
- [ ] `TestCleanup` en dry_run affiche le plan sans supprimer
- [ ] `cleanup_disks()` refuse de supprimer un dossier sans marker valide
- [ ] `cleanup_torrents()` supprime les torrents catégorie "e2e-test" uniquement
- [ ] `verify_clean()` confirme qu'aucun fichier de test ne reste

### Après Phase 3 (Assertions)

- [ ] Chaque fonction d'assertion vérifie les bons critères par étape
- [ ] Les assertions produisent des messages d'erreur clairs et exploitables
- [ ] Les assertions sont tolérantes aux timing issues (fichiers en cours d'écriture)

### Après Phase 4 (E2E films)

- [ ] Un film passe le pipeline complet : magnet → qBit → ingest → sort → scrape → verify → dispatch
- [ ] Le film est sur le bon disque avec NFO + artwork
- [ ] Le cleanup supprime le film du disque et de qBit
- [ ] Aucun fichier existant n'a été touché

### Après Phase 5 (E2E séries + pipeline complet)

- [ ] Une série passe le pipeline complet avec saisons et épisodes renommés
- [ ] Le test pipeline complet (films + séries ensemble) fonctionne
- [ ] Cleanup complet : rien ne reste nulle part
- [ ] Les tests sont exécutables via `pytest tests/e2e/ -m e2e`
- [ ] Les tests sont skippés proprement si qBit/disques/magnets non disponibles
