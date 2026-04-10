# V1 — INGEST : Plan d'implémentation

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

## Phases

| #   | Phase                                        | Fichier                                            | Status |
| --- | -------------------------------------------- | -------------------------------------------------- | ------ |
| 1   | Setup projet (config, structure, .gitignore) | [phase-01-setup.md](phase-01-setup.md)             | [ ]    |
| 2   | Client API qBittorrent                       | [phase-02-qbit-client.md](phase-02-qbit-client.md) | [ ]    |
| 3   | Tracker de torrents ingérés                  | [phase-03-tracker.md](phase-03-tracker.md)         | [ ]    |
| 4   | Orchestrateur ingest                         | [phase-04-ingest.md](phase-04-ingest.md)           | [ ]    |
| 5   | Cron + alias CLI                             | [phase-05-cron.md](phase-05-cron.md)               | [ ]    |

## Dépendances entre phases

```
Phase 1 (setup) ──▶ Phase 2 (qbit_client) ──┐
                                              ├──▶ Phase 4 (ingest) ──▶ Phase 5 (cron)
                    Phase 3 (tracker) ────────┘
```

Phases 2 et 3 sont indépendantes l'une de l'autre mais dépendent de Phase 1.
Phase 4 dépend de 2 et 3. Phase 5 dépend de 4.
