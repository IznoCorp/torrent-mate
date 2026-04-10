# V6 — LOG + NOTIFY : Design

> Logging JSON structuré + notifications Telegram

## Architecture

### Fichiers

```
personalscraper/
├── logger.py          # Logger JSON structuré (implémenté en V0)
├── notifier.py        # Client Telegram (stub en V0, implémenté en V6)
└── models.py          # PipelineReport dataclass
```

### Dépendances

- `logging` (stdlib) — base du logger
- `requests` — appels API Telegram (déjà dans les deps)

Aucune dépendance supplémentaire.

## Interfaces

### `logger.py` — Logger JSON structuré

```python
import logging

class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Produce: {"timestamp": "...", "level": "...", "module": "...",
        "message": "...", "extra": {...}}"""

def get_logger(name: str, verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Configure a logger with JSON file handler + console handler.

    - File handler: writes to logs/personalscraper-YYYY-MM-DD.json
    - Console handler: human-readable colored output
    - verbose=True → DEBUG level
    - quiet=True → WARNING+ only
    - Default → INFO level
    """

def cleanup_old_logs(logs_dir: Path, retention_days: int = 30) -> int:
    """Delete log files older than retention_days. Returns count deleted."""
```

**Format JSON d'une entrée log :**

```json
{
  "timestamp": "2026-04-11T03:00:12.345",
  "level": "INFO",
  "module": "ingest",
  "message": "Torrent ingested",
  "extra": { "torrent": "The.Boys.S05E01", "action": "copied", "size_mb": 2400 }
}
```

**Fichier log :** `logs/personalscraper-2026-04-11.json` (1 par jour, JSON Lines)

### `notifier.py` — Client Telegram

```python
class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        ...

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """POST to Telegram API. Returns True on success.
        Never raises — catches all exceptions, logs warning."""

    def send_report(self, report: PipelineReport) -> bool:
        """Format a PipelineReport as HTML and send it."""

    @staticmethod
    def is_configured(settings: Settings) -> bool:
        """Check if bot_token and chat_id are set in config."""
```

### `models.py` — PipelineReport

```python
@dataclass
class StepReport:
    """Report for a single pipeline step."""
    name: str                          # "ingest", "sort", "scrape", "verify", "dispatch"
    success_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

@dataclass
class PipelineReport:
    """Aggregated report for a full pipeline run."""
    started_at: datetime
    steps: dict[str, StepReport] = field(default_factory=dict)
    finished_at: datetime | None = None

    def add_step(self, name: str) -> StepReport: ...
    def duration(self) -> timedelta: ...
    def has_errors(self) -> bool: ...
    def to_html(self) -> str:
        """Format report as Telegram HTML message."""
```

## Flux de données

```
V1 (ingest)  ──┐
V2 (sort)    ──┤
V3 (scrape)  ──┤── alimentent ──▶ PipelineReport ──▶ notifier.send_report()
V4 (verify)  ──┤                                          │
V5 (dispatch)──┘                                          ▼
                                                    Telegram API
     │
     └── Chaque étape log via ──▶ get_logger() ──▶ logs/YYYY-MM-DD.json
```

Chaque version crée un `StepReport` et l'ajoute au `PipelineReport`. À la fin du pipeline, le rapport est envoyé via Telegram (si configuré).

## Format du message Telegram

```html
📊 <b>PersonalScraper — Rapport</b> ━━━━━━━━━━━━━━━━━━━━━━ 📥 <b>Ingest</b> ✅ 3
torrents ingérés (2 copiés, 1 déplacé) ⏭️ 1 ignoré (déjà traité) 📂
<b>Sort</b> 🎬 2 films triés 📺 4 épisodes triés 🔍 <b>Scrape</b> ✅ 2 films
scrapés ✅ 1 série scrapée (4 épisodes) ⚠️ 1 film non matché 💾
<b>Dispatch</b> ✅ 2 films → Disk3 ✅ 4 épisodes → Disk2 (merge) ⚠️ 1 film
ignoré (espace insuffisant) ⏱️ Durée : 4min 32s 📅 2026-04-11 03:04:32
```

## Gestion d'erreurs

| Situation                          | Comportement                      |
| ---------------------------------- | --------------------------------- |
| Telegram non configuré (.env vide) | Silencieux, pas d'erreur          |
| Telegram API timeout               | Log WARNING, continue le pipeline |
| Telegram API erreur (401, 403)     | Log ERROR, continue le pipeline   |
| Dossier logs/ n'existe pas         | Créé automatiquement              |
| Écriture log échoue                | Fallback sur stderr               |
| Fichier log corrompu               | Nouveau fichier, log WARNING      |

**Principe : les notifications ne bloquent jamais le pipeline.**

## Protection contre les exécutions concurrentes

```python
LOCK_FILE = Path("~/.personalscraper/pipeline.lock").expanduser()

def acquire_lock() -> bool:
    """Créer un lock file avec le PID du processus courant.
    Si le lock existe déjà :
    - Lire le PID stocké
    - Vérifier si le processus est encore vivant (os.kill(pid, 0))
    - Si mort → supprimer le stale lock, prendre le nouveau
    - Si vivant → retourner False (un autre run est en cours)
    """

def release_lock() -> None:
    """Supprimer le lock file."""
```

La commande `run` appelle `acquire_lock()` au début et `release_lock()` à la fin (via try/finally).
Si le lock est pris, le pipeline log un WARNING et quitte sans erreur.
Ceci empêche les collisions entre le cron quotidien et un lancement manuel simultané.
