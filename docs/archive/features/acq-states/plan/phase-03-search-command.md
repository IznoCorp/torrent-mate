# Phase 03 — Commande `search` + ordonnancement

**Goal**: exposer la passe `search` comme commande de premier rang et l'insérer dans
l'ordonnancement, entre `follow detect` et `grab`. Sans cette phase, la séparation de la
phase 2 ne s'exécuterait jamais en production.

**Constitution servie**: §5 (le watcher tourne sur cron **et** sur demande manuelle),
NE-DOIT-PAS-7 (autorité de déclenchement unique).

**Design**: `DESIGN.md` §4 D5.

## Surface

| Fichier                                 | Action                                                |
| --------------------------------------- | ----------------------------------------------------- |
| `personalscraper/commands/search.py`    | **NEW** — la commande, calquée sur `commands/grab.py` |
| `personalscraper/cli.py`                | enregistrement de la sous-commande                    |
| `ecosystem.config.js`                   | entrée `personalscraper-search`, cron `10 3,15 * * *` |
| `docs/reference/commands.md`            | documentation de la commande                          |
| `tests/commands/test_search_command.py` | **NEW** — options, filtrage, dry-run                  |

## La commande

```
personalscraper search [--limit N] [--followed-id ID] [--dry-run]
```

Mêmes options que `grab` pour rester prévisible. `--dry-run` affiche ce qui serait statué sans
rien écrire — indispensable puisque toute passe réelle est validée en dry-run d'abord.

**Tests CLI** : penser à patcher `personalscraper.conf.loader.load_config`, sans quoi la CI
sort en `SystemExit(2)` faute de `config.json5`.

## Ordonnancement

| Heure | Passe              | Effet                                            |
| ----- | ------------------ | ------------------------------------------------ |
| 03:00 | `follow detect`    | nouveaux épisodes diffusés enfilés → Non vérifié |
| 03:10 | `search` (nouveau) | disponibilité statuée → À récupérer / En attente |
| 03:20 | `grab`             | ce qui est disponible est pris                   |
| 15:10 | `search`           | re-vérification selon cadence                    |
| 15:20 | `grab`             | prise de ce qui est devenu disponible            |

L'entrée PM2 suit le modèle des jobs existants : binaire du clone **prod**
(`/Users/izno/deploy/torrentmate-venv/bin/personalscraper`), `cwd` prod,
`PERSONALSCRAPER_CONFIG` explicite, `autorestart: false`, `cron_restart`.

**Ne pas ajouter d'agent launchd** : PM2 est le gestionnaire de process cible, launchd est
décommissionné.

## Sous-phases

### 3.1 — La commande

**Commit**: `feat(acq-states): add the search command`

### 3.2 — Ordonnancement PM2

**Commit**: `build(acq-states): schedule the search pass between detect and grab`

### 3.3 — Documentation

**Commit**: `docs(acq-states): document the search pass in the command reference`

## Gate

1. `make lint` + `make test`.
2. `personalscraper search --help` répond ; `--dry-run` n'écrit rien (vérifié en comparant la
   base avant/après).
3. `node -e "require('./ecosystem.config.js')"` — le fichier reste valide.
4. L'entrée `personalscraper-search` pointe le binaire **prod**, pas le checkout de dev.
5. Une passe `search --dry-run` réelle sur la base partagée affiche des items sans rien muter.
6. `docs/reference/commands.md` décrit les trois passes et leur enchaînement.
