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

- `structlog` (already in deps) + `logging` (stdlib, used for handlers and foreign log capture)
- `requests` — appels API Telegram (déjà dans les deps)

Aucune dépendance supplémentaire.

## Interfaces

### `logger.py` — Logger structuré (structlog)

> Ref : [docs/structlog-reference.md](../structlog-reference.md) — configuration complète, processeurs, patterns

> **Points critiques structlog** (voir `docs/structlog-reference.md`) :
>
> - `cache_logger_on_first_use=True` — configurer AVANT le premier log
> - `ProcessorFormatter.wrap_for_formatter` DOIT être le dernier processeur structlog
> - `JSONRenderer` va dans `ProcessorFormatter`, PAS dans `structlog.configure()`
> - `foreign_pre_chain` pour capturer les logs stdlib (requests, urllib3, qbittorrent-api)

```python
import structlog

def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging pour dual output.

    Console handler: ConsoleRenderer coloré (dev/interactif)
    File handler: TimedRotatingFileHandler → logs/personalscraper.json (JSON Lines, rotation midnight)
    - verbose=True → DEBUG level
    - quiet=True → WARNING+ only
    - Default → INFO level
    - foreign_pre_chain pour les logs stdlib (requests, urllib3, qbittorrent-api)
    - Auto-detection TTY : console colorée si interactif, JSON si cron/pipe
    """

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name)

def cleanup_old_logs(logs_dir: Path, retention_days: int = 30) -> int:
    """Delete log files older than retention_days. Returns count deleted.
    Complément au backupCount de TimedRotatingFileHandler."""
```

**Format JSON d'une entrée log (JSON Lines) :**

```json
{
  "event": "torrent_ingested",
  "level": "info",
  "step": "ingest",
  "run_id": "2026-04-11T03:00:00",
  "torrent": "The.Boys.S05E01",
  "action": "copied",
  "size_mb": 2400,
  "timestamp": "2026-04-11T03:00:12.345"
}
```

**Fichier log :** `logs/personalscraper.json` (rotation quotidienne, 30 fichiers max)

**Context binding par étape :**

```python
log = structlog.get_logger().bind(step="ingest")
log.info("torrent_ingested", torrent="The.Boys.S05E01", action="copied", size_mb=2400)
# "step" apparaît dans tous les logs automatiquement

# Contexte global pipeline (run_id dans TOUS les logs)
structlog.contextvars.bind_contextvars(run_id=datetime.now().isoformat())
```

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

### `models.py` — StepReport + PipelineReport

> **StepReport et PipelineReport sont définis dans `personalscraper/models.py` (V0).**
> V6 ne les redéfinit pas — il les utilise tels quels.

```python
# Rappel (défini en V0 models.py) :
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

    def add_step(self, name: str, step: StepReport) -> None:
        """Add a completed StepReport to the pipeline report."""
    def duration(self) -> timedelta: ...
    def has_errors(self) -> bool: ...
    def to_html(self) -> str:
        """Format report as Telegram HTML message."""
```

### Intégration Settings (pydantic-settings)

Nouvelles clés de configuration (dans `.env`) :

- `TELEGRAM_BOT_TOKEN` : token du bot Telegram (vide = notifications désactivées)
- `TELEGRAM_CHAT_ID` : ID chat/utilisateur Telegram (vide = notifications désactivées)
- `HEALTHCHECK_URL` : endpoint healthchecks.io (optionnel, vide = pas de healthcheck)

## Flux de données

```
V1 (ingest)  ──┐
V2 (sort)    ──┤
V3 (scrape)  ──┤── alimentent ──▶ PipelineReport ──▶ notifier.send_report()
V4 (verify)  ──┤                                          │
V5 (dispatch)──┘                                          ▼
                                                    Telegram API
     │
     └── Chaque étape log via ──▶ get_logger() ──▶ logs/personalscraper.json
```

Chaque version crée un `StepReport` et l'ajoute au `PipelineReport`. À la fin du pipeline, le rapport est envoyé via Telegram (si configuré).

**Responsabilité** : chaque orchestrateur de version (run_ingest, run_sort, etc.) convertit ses résultats internes en StepReport. V6 ne fait qu'agréger et envoyer.

### Contrat StepReport — conversion list[*Result] → StepReport

> Chaque `run_*()` retourne un `StepReport`. La conversion depuis les types internes
> (`list[SortResult]`, etc.) se fait dans l'orchestrateur de chaque version, PAS dans V6.

| Version | Fonction         | Type interne           | Conversion → StepReport                                                                                                                                                                                                                                                                                      |
| ------- | ---------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| V1      | `run_ingest()`   | StepReport directement | Pas de conversion (déjà StepReport)                                                                                                                                                                                                                                                                          |
| V2      | `run_sort()`     | `list[SortResult]`     | `success_count = len([r for r in results if r.status == "moved"])`, `skip_count = len([r for r in results if r.status == "skipped"])`, `error_count = len([r for r in results if r.status == "error"])`, `details = [f"{r.title} → {r.destination}" for r]`                                                  |
| V3      | `run_scrape()`   | `list[ScrapeResult]`   | `success_count = len([r for r in results if r.action == "scraped"])`, `skip_count = len([r for r in results if r.action.startswith("skipped")])`, `error_count = len([r for r in results if r.action == "error"])`, `details = [f"{r.media_path.name}: {r.match.source if r.match else 'unmatched'}" for r]` |
| V4      | `run_verify()`   | `list[VerifyResult]`   | `success_count = len([r for r in results if r.status in ("valid", "fixed")])`, `error_count = len([r for r in results if r.status == "blocked"])`, `warnings = [w for r in results for w in r.warnings]`                                                                                                     |
| V5      | `run_dispatch()` | `list[DispatchResult]` | `success_count = len([r for r in results if r.action in ("replaced", "merged", "moved")])`, `skip_count = len([r for r in results if r.action == "skipped"])`, `error_count = len([r for r in results if r.action == "error"])`, `details = [f"{r.source.name} → {r.disk}" for r if r.disk]`                 |

> **`run_*()` wrapper functions** : chaque version (V2-V5) doit définir une fonction top-level
> dans son orchestrateur ou `__init__.py`. Pattern identique à V1 `run_ingest()`.
> Signatures :
>
> - `run_sort(settings, dry_run) -> StepReport`
> - `run_scrape(settings, dry_run, interactive=False) -> StepReport` (interactive pour CLI standalone)
> - `run_verify(settings, dry_run) -> tuple[StepReport, list[VerifyResult]]` (retourne aussi les résultats pour V5)
> - `run_dispatch(settings, dry_run, verified=None) -> StepReport` (verified=None → standalone mode)
>
> **V4→V5 handoff** : la commande `run` appelle `run_verify()` qui retourne le StepReport
> ET la liste des `VerifyResult` dispatchable. Le `run` passe ensuite `verified` à `run_dispatch()`.

La commande `run` (V6) appelle simplement `report.add_step("ingest", run_ingest(settings, dry_run))` pour chaque étape.
Chaque `run_*()` est responsable de construire son propre StepReport — V6 ne fait que les agréger.

## Format du message Telegram

```html
📊 <b>PersonalScraper — Rapport</b> ━━━━━━━━━━━━━━━━━━━━━━ 📥 <b>Ingest</b> ✅ 3
torrents ingérés (2 copiés, 1 déplacé) ⏭️ 1 ignoré (déjà traité) 📂
<b>Sort</b> 🎬 2 films triés 📺 4 épisodes triés 🔍 <b>Scrape</b> ✅ 2 films
scrapés ✅ 1 série scrapée (4 épisodes) ⚠️ 1 film non matché 💾
<b>Dispatch</b> ✅ 2 films → Disk3 ✅ 4 épisodes → Disk2 (merge) ⚠️ 1 film
ignoré (espace insuffisant) ⏱️ Durée : 4min 32s 📅 2026-04-11 03:04:32
```

## Résumé console

Le résumé console utilise `rich.panel.Panel` + `rich.table.Table` : colonnes (Étape, Statut, Succès, Erreurs, Durée). Affiché via `rich.console.Console`.

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

> **Module `personalscraper/lock.py`** — implémenté en V1, réutilisé par la commande `run`.
> Voir V1 DESIGN.md pour les détails d'implémentation (acquire_lock, release_lock, stale detection).

La commande `run` appelle `acquire_lock()` au début et `release_lock()` à la fin (via try/finally).
Si le lock est pris, le pipeline log un WARNING et quitte sans erreur.
Ceci empêche les collisions entre la tâche planifiée quotidienne et un lancement manuel simultané.

## Monitoring externe (healthchecks.io)

> Filet de sécurité : si le pipeline crash avant d'envoyer la notification Telegram
> (OOM, segfault, disque plein), personne n'est prévenu. Un service de monitoring externe
> détecte l'absence de signal.

Défini dans `personalscraper/notifier.py` (même module que TelegramNotifier).

```python
def ping_healthcheck(url: str, status: str = "") -> None:
    """Ping healthchecks.io (ou compatible). Non-bloquant, never raises.
    - url = settings.healthcheck_url (ex: 'https://hc-ping.com/{uuid}')
    - status = '' (success), '/start' (début run), '/fail' (erreur)
    """
    if not url:
        return
    try:
        requests.get(f"{url}{status}", timeout=5)
    except Exception:
        pass  # Le monitoring ne bloque jamais le pipeline
```

Flux dans la commande `run` :

1. `ping_healthcheck(url, "/start")` — début du run
2. Pipeline V1→V5
3. `ping_healthcheck(url, "" if not report.has_errors() else "/fail")` — fin du run

Configuration : `healthcheck_url` dans Settings (V0). Si vide → pas de ping (silencieux).
Service gratuit recommandé : [healthchecks.io](https://healthchecks.io) (plan gratuit = 20 checks).
