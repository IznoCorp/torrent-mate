# V5 — DISPATCH : Plan d'implémentation

> Déplacement intelligent des médias vers Disk1-4

## Phases

| #   | Phase                           | Fichier                                                | Status |
| --- | ------------------------------- | ------------------------------------------------------ | ------ |
| 1   | Media index JSON + disk scanner | [phase-01-index-scanner.md](phase-01-index-scanner.md) | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_   |                                                        | [ ]    |
| 2   | Dispatcher orchestrator         | [phase-02-dispatcher.md](phase-02-dispatcher.md)       | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_   |                                                        | [ ]    |
| 3   | CLI command + tests end-to-end  | [phase-03-cli-tests.md](phase-03-cli-tests.md)         | [ ]    |
| ·   | _Contrôle de cohérence V5→V6_   |                                                        | [ ]    |

## Dépendances entre phases

```
Phase 1 (index + scanner) ──▶ Phase 2 (dispatcher, uses V4 genre_mapper) ──▶ Phase 3 (CLI + tests)
```

## Contrôles de cohérence

### Après Phase 1 (Index + Scanner → Dispatcher)

- [ ] `MediaIndex.rebuild()` indexe correctement les 4 disques
- [ ] `MediaIndex.find()` retourne le bon résultat (fuzzy matching)
- [ ] `get_disk_status()` retourne l'espace libre correct
- [ ] `choose_disk()` choisit le disque avec le plus d'espace parmi les compatibles

### Après Phase 2 (Dispatcher → CLI)

- [ ] V4's `VerifyResult.category` est correctement importé et utilisé par le dispatcher
- [ ] Films : replace fonctionne (ancien supprimé, nouveau en place)
- [ ] Séries : merge fonctionne (nouveaux fichiers copiés, existants préservés)
- [ ] Nouveaux médias : dispatched vers le disque avec le plus d'espace
- [ ] `_verify_transfer()` détecte les transferts incomplets

### Après Phase 3 (CLI → V6)

- [ ] `personalscraper dispatch --dry-run` fonctionne end-to-end
- [ ] L'index est mis à jour après chaque dispatch
- [ ] Les DispatchResult alimentent correctement le StepReport
- [ ] Les médias skippés (espace insuffisant) sont reportés
