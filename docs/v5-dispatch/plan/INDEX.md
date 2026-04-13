# V5 — DISPATCH : Plan d'implémentation

> Déplacement intelligent des médias vers Disk1-4

## Phases

| #   | Phase                           | Fichier                                                | Status |
| --- | ------------------------------- | ------------------------------------------------------ | ------ |
| 1   | Media index JSON + disk scanner | [phase-01-index-scanner.md](phase-01-index-scanner.md) | [x]    |
| ·   | _Contrôle de cohérence P1→P2_   |                                                        | [x]    |
| 2   | Dispatcher orchestrator         | [phase-02-dispatcher.md](phase-02-dispatcher.md)       | [x]    |
| ·   | _Contrôle de cohérence P2→P3_   |                                                        | [x]    |
| 3   | CLI command + tests end-to-end  | [phase-03-cli-tests.md](phase-03-cli-tests.md)         | [x]    |
| ·   | _Contrôle de cohérence V5→V6_   |                                                        | [x]    |

## Dépendances entre phases

```
Phase 1 (index + scanner) ──▶ Phase 2 (dispatcher, uses V4 genre_mapper) ──▶ Phase 3 (CLI + tests)
```

## Contrôles de cohérence

### Après Phase 1 (Index + Scanner → Dispatcher)

- [x] `MediaIndex.rebuild()` indexe correctement les 4 disques
- [x] `MediaIndex.find()` retourne le bon résultat (fuzzy matching)
- [x] `get_disk_status()` retourne l'espace libre correct
- [x] `choose_disk()` choisit le disque avec le plus d'espace parmi les compatibles

### Après Phase 2 (Dispatcher → CLI)

- [x] V4's `VerifyResult.category` est correctement importé et utilisé par le dispatcher
- [x] Films : replace fonctionne (ancien supprimé, nouveau en place)
- [x] Séries : merge fonctionne (nouveaux fichiers copiés, existants préservés)
- [x] Nouveaux médias : dispatched vers le disque avec le plus d'espace
- [x] `_verify_transfer()` détecte les transferts incomplets

### Après Phase 3 (CLI → V6)

- [x] `personalscraper dispatch --dry-run` fonctionne end-to-end
- [x] L'index est mis à jour après chaque dispatch
- [x] Les DispatchResult alimentent correctement le StepReport
- [x] Les médias skippés (espace insuffisant) sont reportés
