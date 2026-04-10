# V1 — INGEST : Plan d'implémentation

> Récupération automatique des fichiers depuis `torrents/complete` vers `A TRIER/`

## Phases

| #   | Phase                                        | Fichier                                            | Status |
| --- | -------------------------------------------- | -------------------------------------------------- | ------ |
| 1   | Setup projet (config, structure, .gitignore) | [phase-01-setup.md](phase-01-setup.md)             | [ ]    |
| ·   | _Contrôle de cohérence P1→P2/P3_             |                                                    | [ ]    |
| 2   | Client API qBittorrent                       | [phase-02-qbit-client.md](phase-02-qbit-client.md) | [ ]    |
| ·   | _Contrôle de cohérence P2→P4_                |                                                    | [ ]    |
| 3   | Tracker de torrents ingérés                  | [phase-03-tracker.md](phase-03-tracker.md)         | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_                |                                                    | [ ]    |
| 4   | Orchestrateur ingest                         | [phase-04-ingest.md](phase-04-ingest.md)           | [ ]    |
| ·   | _Contrôle de cohérence P4→P5_                |                                                    | [ ]    |
| 5   | Cron + alias CLI                             | [phase-05-cron.md](phase-05-cron.md)               | [ ]    |
| ·   | _Contrôle de cohérence V1→V2_                |                                                    | [ ]    |

## Dépendances entre phases

```
Phase 1 (setup) ──▶ Phase 2 (qbit_client) ──┐
                                              ├──▶ Phase 4 (ingest) ──▶ Phase 5 (cron)
                    Phase 3 (tracker) ────────┘
```

Phases 2 et 3 sont indépendantes l'une de l'autre mais dépendent de Phase 1.
Phase 4 dépend de 2 et 3. Phase 5 dépend de 4.

## Contrôles de cohérence

### Après Phase 1 (Setup → qBit Client / Tracker)

- [ ] La structure `099-SCRIPTS/pipeline/` est créée et importable
- [ ] Le `.env` charge correctement toutes les variables requises par P2 et P3
- [ ] Le `.gitignore` protège `.env`, `ingested_torrents.json`, `logs/`

### Après Phase 2 (qBit Client → Orchestrateur)

- [ ] `QBitClient` expose bien les méthodes attendues par `ingest.py` (design)
- [ ] Les types de retour sont cohérents (list[dict], set[str], Path, bool)
- [ ] Le context manager fonctionne (auto login/logout)
- [ ] Test réel validé contre l'API qBit locale

### Après Phase 3 (Tracker → Orchestrateur)

- [ ] `IngestTracker` expose bien les méthodes attendues par `ingest.py` (design)
- [ ] Le JSON se crée/charge/sauvegarde correctement
- [ ] Le cleanup accepte bien un `set[str]` (output de `get_all_torrent_hashes()`)

### Après Phase 4 (Orchestrateur → Cron)

- [ ] `ingest.py` est exécutable standalone (`python3 ingest.py`)
- [ ] `--dry-run` ne modifie rien sur le filesystem
- [ ] Les exit codes sont corrects (0/1/2)
- [ ] Le script gère correctement les chemins avec espaces
- [ ] Le résumé est clair et loggable

### Après Phase 5 (Cron → V2)

- [ ] Le cron s'exécute correctement à 3h
- [ ] Les logs sont écrits au bon endroit
- [ ] L'alias `media-ingest` fonctionne
- [ ] Les fichiers arrivent bien à la racine de A TRIER/ (prêts pour V2/FileMate)
- [ ] CLAUDE.md est à jour avec les nouvelles commandes
