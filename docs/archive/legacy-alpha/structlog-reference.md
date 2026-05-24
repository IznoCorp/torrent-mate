# structlog — Reference Documentation

> Date : 2026-04-10 | Contexte : V6 LOG+NOTIFY — logging JSON structuré pour le pipeline PersonalScraper

## Qu'est-ce que structlog ?

[structlog](https://github.com/hynek/structlog) (v25+) est une librairie de logging structuré pour Python.
Elle remplace le pattern classique `logging.getLogger()` + custom `JsonFormatter` par un système de
loggers avec contexte bindé et une pipeline de processeurs composables.

**Utilisé pour** : Remplacer le `JsonFormatter` custom prévu dans `logger.py` (V0/V6) par un système
natif JSON avec context binding, switch dev/prod automatique, et intégration stdlib pour la rotation.

**Version** : >= 25.5.0
**Licence** : MIT OR Apache-2.0 (double licence)
**Python** : >= 3.10
**Dépendances** : Aucune (optionnel : `orjson` ou `msgspec` pour du JSON plus rapide)

## Installation

```bash
pip install structlog
```

## Concepts fondamentaux

### Bound Loggers — Loggers avec contexte

```python
import structlog

log = structlog.get_logger()

# Bind ajoute du contexte (retourne un NOUVEAU logger, l'original est immuable)
log = log.bind(step="ingest")
log.info("torrent_detected", torrent="The.Boys.S05E01", state="completed")
# Output: {"event": "torrent_detected", "step": "ingest", "torrent": "The.Boys.S05E01", ...}

log.info("torrent_copied", torrent="The.Boys.S05E01", size_mb=2400)
# Output: {"event": "torrent_copied", "step": "ingest", "torrent": "The.Boys.S05E01", ...}
# "step" est automatiquement inclus dans tous les logs
```

Méthodes de binding :

- `log.bind(**kw)` — retourne un nouveau logger avec contexte additionnel
- `log.unbind(*keys)` — retourne un nouveau logger sans les clés spécifiées
- `log.new(**kw)` — retourne un nouveau logger avec UNIQUEMENT le nouveau contexte

### Processor Pipeline

Les processeurs sont des callables chaînés qui transforment l'event dict :

```python
def my_processor(logger, method_name, event_dict):
    """Chaque processeur reçoit le dict, le transforme, et le retourne."""
    event_dict["pipeline"] = "personalscraper"
    return event_dict
```

Exécution quand on appelle `log.info("hello", x=42)` :

1. Context dict copié en event_dict
2. kwargs mergés (`x=42`)
3. `"event"` key = `"hello"`
4. Processeurs appelés séquentiellement : `p3(p2(p1(event_dict)))`
5. Dernier processeur produit l'output

Pour **supprimer** un event silencieusement : `raise structlog.DropEvent`

### Context Variables — Contexte global par exécution

```python
import structlog

# Au début du pipeline run
structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(run_id="2026-04-11T03:00:00")

# Dans N'IMPORTE QUEL module, le run_id apparaît automatiquement
log = structlog.get_logger()
log.info("started")  # Output: {"event": "started", "run_id": "2026-04-11T03:00:00", ...}
```

Fonctions :

- `bind_contextvars(**kw)` — bind pour le contexte d'exécution courant
- `unbind_contextvars(*keys)` — supprimer des clés
- `clear_contextvars()` — tout réinitialiser (appeler au début de chaque run)
- `bound_contextvars(**kw)` — context manager pour du binding temporaire

**Attention** : Les contextvars sont isolés entre threads et tâches async.

## Configuration

### Configuration complète pour le pipeline

```python
import logging
import logging.config
import structlog

def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging pour le pipeline."""

    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "WARNING"
    else:
        log_level = "INFO"

    # Processeurs partagés (structlog ET stdlib)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Configuration stdlib (handlers, formatters)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
                "foreign_pre_chain": shared_processors,
            },
            "colored": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.dev.ConsoleRenderer(colors=True),
                ],
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "colored",
                "level": log_level,
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": "logs/personalscraper.json",
                "when": "midnight",
                "backupCount": 30,
                "formatter": "json",
                "level": "DEBUG",      # Tout dans le fichier
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": True,
            },
        },
    })

    # Configuration structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,  # DOIT être le dernier
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

### Points critiques de cette configuration

1. **`ProcessorFormatter.wrap_for_formatter` DOIT être le dernier** processeur structlog.
   NE PAS mettre `JSONRenderer` comme dernier processeur structlog — il va dans `ProcessorFormatter.processors`.

2. **`foreign_pre_chain`** : Appliqué aux logs venant de stdlib (pas structlog). Assure un format cohérent
   pour les deux systèmes (ex: logs de `requests`, `urllib3`, etc.).

3. **`remove_processors_meta`** : Supprime les clés internes `_record` et `_from_structlog` avant le rendu final.

4. **Dual output** : Console colorée (interactif) + fichier JSON (traçabilité). Les deux reçoivent les mêmes events.

## Processeurs clés

| Processeur               | Rôle                                                          |
| ------------------------ | ------------------------------------------------------------- |
| `merge_contextvars`      | Injecte les contextvars dans chaque event (DOIT être premier) |
| `add_log_level`          | Ajoute la clé `"level"`                                       |
| `TimeStamper(fmt="iso")` | Ajoute `"timestamp"` en ISO 8601                              |
| `StackInfoRenderer()`    | Ajoute `"stack"` quand `stack_info=True`                      |
| `format_exc_info`        | Formate les exceptions en string                              |
| `dict_tracebacks`        | Formate les exceptions en dict structuré (pour JSON)          |
| `ExtraAdder()`           | Ajoute les champs `extra={}` de stdlib logging                |
| `JSONRenderer()`         | Sérialise l'event dict en JSON string                         |
| `ConsoleRenderer()`      | Rendu coloré pour le terminal                                 |

### Écrire un processeur custom

```python
def add_pipeline_context(logger, method_name, event_dict):
    """Ajouter le contexte pipeline à chaque log."""
    event_dict.setdefault("pipeline", "personalscraper")
    return event_dict

# Processeur conditionnel (classe)
class DropNoisy:
    """Supprimer les events trop fréquents en mode non-verbose."""
    def __init__(self, noisy_events: set[str]):
        self._noisy = noisy_events

    def __call__(self, logger, method_name, event_dict):
        if event_dict.get("event") in self._noisy and method_name == "debug":
            raise structlog.DropEvent
        return event_dict
```

## Renderers

### `JSONRenderer` — Production/cron

```python
structlog.processors.JSONRenderer(
    serializer=json.dumps,     # ou orjson.dumps pour la perf
    sort_keys=True,
    indent=None,               # JSON compact (1 ligne)
)
```

Output :

```json
{
  "event": "torrent_copied",
  "level": "info",
  "step": "ingest",
  "torrent": "The.Boys.S05E01",
  "size_mb": 2400,
  "timestamp": "2026-04-11T03:00:12"
}
```

### `ConsoleRenderer` — Développement/interactif

```python
structlog.dev.ConsoleRenderer(
    colors=True,               # Auto-détecté
    pad_event_to=30,           # Aligner les clés
    sort_keys=True,
)
```

Output :

```
2026-04-11 03:00:12 [info     ] torrent_copied             step=ingest torrent=The.Boys.S05E01 size_mb=2400
```

### Switch automatique dev/prod

```python
import sys

is_interactive = sys.stderr.isatty()

if is_interactive:
    renderer = structlog.dev.ConsoleRenderer(colors=True)
else:
    renderer = structlog.processors.JSONRenderer()
```

Quand le pipeline tourne en cron (pas de TTY), on obtient du JSON automatiquement.
Quand lancé manuellement, on obtient des couleurs automatiquement.

## Patterns pour le pipeline

### Binding contexte par étape

```python
import structlog

log = structlog.get_logger()

def run_ingest(settings, dry_run=False):
    log = structlog.get_logger().bind(step="ingest", dry_run=dry_run)
    log.info("step_started")

    for torrent in torrents:
        log.info("torrent_processing", torrent=torrent.name, state=torrent.state)
        # ... process ...
        log.info("torrent_ingested", torrent=torrent.name, action="copied", size_mb=size)

    log.info("step_completed", count=len(torrents))
```

### Contextvars pour le run_id global

```python
def run_pipeline(settings, dry_run=False):
    """Pipeline complet V1-V5."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        run_id=datetime.now().isoformat(),
        dry_run=dry_run,
    )

    log = structlog.get_logger()
    log.info("pipeline_started")

    # Chaque étape a son propre logger bindé
    run_ingest(settings, dry_run)    # log.bind(step="ingest")
    run_sort(settings, dry_run)       # log.bind(step="sort")
    run_scrape(settings, dry_run)     # log.bind(step="scrape")
    # ...

    log.info("pipeline_completed")
    # run_id apparaît dans TOUS les logs automatiquement
```

### Format du fichier log (JSON Lines, 1 par jour)

Fichier : `logs/personalscraper.json` (rotation quotidienne via `TimedRotatingFileHandler`)

Fichiers rotés : `personalscraper.json.2026-04-10`, `personalscraper.json.2026-04-09`, etc.

Contenu (JSON Lines — une ligne JSON par event) :

```json
{"event": "pipeline_started", "level": "info", "run_id": "2026-04-11T03:00:00", "dry_run": false, "timestamp": "2026-04-11T03:00:00.123"}
{"event": "torrent_ingested", "level": "info", "run_id": "2026-04-11T03:00:00", "step": "ingest", "torrent": "The.Boys.S05E01", "action": "copied", "size_mb": 2400, "timestamp": "2026-04-11T03:00:05.456"}
{"event": "media_sorted", "level": "info", "run_id": "2026-04-11T03:00:00", "step": "sort", "title": "The Boys", "category": "002-TVSHOWS", "timestamp": "2026-04-11T03:00:06.789"}
```

### Cleanup des vieux logs

`TimedRotatingFileHandler(backupCount=30)` garde 30 fichiers automatiquement.

La fonction `cleanup_old_logs()` prévue dans le design reste utile en complément
(nettoyage plus agressif, ou nettoyage de logs orphelins).

### Intégration avec Click CLI

```python
import click
import structlog

@click.group()
@click.option("--verbose", "-v", is_flag=True)
@click.option("--quiet", "-q", is_flag=True)
@click.pass_context
def cli(ctx, verbose, quiet):
    """PersonalScraper — Media pipeline automation."""
    ctx.ensure_object(dict)
    configure_logging(verbose=verbose, quiet=quiet)
    ctx.obj["verbose"] = verbose
```

En mode `--quiet` : le filtering bound logger filtre debug/info **avant**
la création de l'event dict, donc un coût quasi-nul pour les messages filtrés.

## Comparaison avec le JsonFormatter custom prévu

| Aspect                  | Custom JsonFormatter            | structlog                                  |
| ----------------------- | ------------------------------- | ------------------------------------------ |
| Context binding         | `extra={}` manuel partout       | `log.bind(key=val)` composable             |
| Contexte global         | Thread-local via logging.Filter | `contextvars` natif, async-safe            |
| Pipeline de processeurs | Aucun (1 seul Formatter)        | Chaîne composable                          |
| Switch dev/prod         | 2 Formatters séparés            | Swap le dernier processeur                 |
| Filtrage niveau         | Après évaluation du format      | Avant création event dict (coût quasi-nul) |
| Exceptions structurées  | Override `formatException()`    | `dict_tracebacks` pour JSON parseable      |
| Testing                 | Mock handlers                   | `capture_logs()`, `LogCapture`             |

### Impact sur le design V0/V6

Le module `logger.py` (V0) passe de :

- Custom `JsonFormatter(logging.Formatter)` vers `structlog.configure()` + `ProcessorFormatter`
- `get_logger(name, verbose, quiet)` vers `configure_logging(verbose, quiet)` + `structlog.get_logger()`
- `cleanup_old_logs()` reste (complément à `backupCount`)

La fonction `get_logger()` reste l'interface publique mais en interne elle appelle `structlog.get_logger()`.

## Testing

### `capture_logs()` — Capturer les logs dans les tests

```python
import structlog
from structlog.testing import capture_logs

def test_ingest_logs_torrent():
    with capture_logs() as logs:
        run_ingest(settings, dry_run=True)

    assert any(
        log["event"] == "torrent_ingested" and log["torrent"] == "The.Boys.S05E01"
        for log in logs
    )
```

### `LogCapture` — Fixture pytest custom

```python
import pytest
import structlog

@pytest.fixture
def log_output():
    cap = structlog.testing.LogCapture()
    structlog.configure(processors=[cap])
    yield cap.entries
    structlog.reset_defaults()
```

### `reset_defaults()` — Nettoyage entre tests

```python
@pytest.fixture(autouse=True)
def reset_structlog():
    yield
    structlog.reset_defaults()
```

**Attention** : Avec `cache_logger_on_first_use=True`, les loggers déjà cachés ne voient PAS
les changements de config. Désactiver le cache dans les tests.

## Gotchas

### 1. `wrap_for_formatter` DOIT être le dernier processeur structlog

Si on met `JSONRenderer` comme dernier processeur structlog tout en utilisant `ProcessorFormatter`,
le rendu ne fonctionnera pas. `JSONRenderer` va dans `ProcessorFormatter(processors=[...])`.

### 2. `cache_logger_on_first_use=True` est irréversible

Tout appel à `structlog.configure()` après le premier log est ignoré pour les loggers déjà cachés.
**Configurer tôt, configurer une fois.**

### 3. `make_filtering_bound_logger` est statique

Le niveau de log ne peut pas être changé après création. Si besoin de changement dynamique,
utiliser `structlog.stdlib.BoundLogger` avec `logging.Logger.setLevel()`.

### 4. Sérialisation / multiprocessing

Avec `cache_logger_on_first_use=True`, les loggers ne sont PAS sérialisables.
Si multiprocessing nécessaire : désactiver le cache ou ré-initialiser dans chaque worker.

### 5. Fichiers partagés entre structlog et stdlib

Si `PrintLogger` et un `StreamHandler` écrivent sur le même stream (stderr),
les outputs peuvent s'entrelacer. Utiliser `WriteLoggerFactory` ou passer par stdlib uniquement.

### 6. `foreign_pre_chain` pour les libs tierces

Les logs de `requests`, `urllib3`, `qbittorrent-api` passent par stdlib, pas par structlog.
`foreign_pre_chain` dans `ProcessorFormatter` assure qu'ils sont formatés de la même manière.

## Utilisation dans le pipeline

| Version | Rôle                                                                     |
| ------- | ------------------------------------------------------------------------ |
| V0      | `configure_logging()` dans `logger.py`, `structlog.get_logger()` partout |
| V1-V5   | `log.bind(step=...)` par étape, contextvars pour `run_id`                |
| V6      | `TelegramNotifier` lit les `StepReport`, pas les logs directement        |
| V6      | `TimedRotatingFileHandler` pour rotation quotidienne 30 jours            |
| V7      | `capture_logs()` dans les tests E2E                                      |
