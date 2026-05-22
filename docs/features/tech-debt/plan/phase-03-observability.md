# Phase 3 — Observability (broadened DEV #6)

**Effort** : 2 jours
**Theme** : combler le gap "user-facing rich" vs "machine telemetry structurée" sur les
7 per-step CLI subcommands (pas seulement VERIFY).

## Coverage matrix

| Item                   | Sub-phase | Source pattern  |
| ---------------------- | --------- | --------------- |
| MUST-10 / DEV #6 + #40 | 3.1       | P7, P18, P25    |
| SH-10 / CL-F / DEV #23 | 3.2       | P18             |
| SH-11 / CL-H           | 3.3       | P18 enforcement |
| (doc only)             | 3.4       | P18             |

DESIGN sections impacted : §10 CLI surface (telemetry rule), §14 Success criteria.
DEV #40 = generalisation of DEV #6 to all 7 per-step subcommands (ingest, sort, scrape,
verify, enforce, dispatch, process).

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phase 1 commited + gate vert
- (Phase 2 peut tourner en parallèle ; pas de dépendance directe)

## Sub-phases

### 3.1 VERIFY structured events (MUST-10 / DEV #6 / CL-G)

**Sites** :

- `personalscraper/verify/run.py` — `run_verify()` retourne `report, dispatchable`
- `personalscraper/verify/checker.py` (ou équivalent) — boucle d'items

**Implementation** : à chaque item verify, émettre :

```python
log.info(
    "verify_item_done",
    item=item.name,
    status="valid" if ok else "blocked",
    errors=errors,
    checks_passed=N,
    checks_total=M,
)
```

- event au bus (`event_bus.emit(VerifyItemDone(item, status, errors))` si la classe Event
  existe ou la créer dans `personalscraper/core/events.py`).

La commande `verify` (pipeline.py) garde son rich rendering en plus.

**Commit** : `feat(tech-debt): emit verify_item_done structured events (DEV #6)`

### 3.2 cli.invoke telemetry decorator (SH-10 / DEV #23 / CL-F)

**Site** : `personalscraper/cli_helpers.py` ou nouveau `personalscraper/cli_telemetry.py`.

**Implementation** :

```python
import functools
from personalscraper.logger import get_logger

_log = get_logger("cli.telemetry")

def cli_telemetry(cmd_name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(ctx, *args, **kwargs):
            _log.info(f"cli.invoke.{cmd_name}", args={k: v for k, v in kwargs.items() if k != "ctx"})
            try:
                ret = fn(ctx, *args, **kwargs)
                _log.info(f"cli.complete.{cmd_name}", exit_code=ret or 0)
                return ret
            except Exception as exc:
                _log.error(f"cli.failed.{cmd_name}", error=str(exc), error_type=type(exc).__name__)
                raise
        return wrapped
    return deco
```

Appliquer à chaque commande exposée. Ordre : `@app.command()` puis `@cli_telemetry("name")`
puis `@handle_cli_errors` puis def.

**Commit** : `feat(tech-debt): add cli_telemetry decorator (DEV #23)`

- `feat(tech-debt): apply cli_telemetry to all commands`

### 3.3 Console + log parity test (SH-11 / CL-H)

**Site** : `tests/integration/test_console_log_parity.py` (nouveau)

**Scenario** : pour chaque commande pipeline qui fait un `console.print("[bold]X:[/bold]
...")` summary, vérifier qu'un event `cli.complete.<cmd>` ou un domain-specific event
structlog existe au même endroit (pas de "rich-only" summary).

Approach : regex grep AST-level via `ast.NodeVisitor` ou simple regex sur les fichiers.

**Commit** : `test(tech-debt): enforce console+log parity for pipeline commands (SH-11)`

### 3.4 Doc reference "logging conventions" (lié SH-12 mais ciblé observability)

**Site** : `docs/reference/logging.md` (existe — étendre)

**Sections à ajouter** :

- Frontière user-facing (Typer rich) vs machine telemetry (structlog)
- Convention event-names : `<step>_<action>_<state>` ex `verify_item_done`
- Conventions args : `item=...`, `disk_id=...`, `status=...`, `errors=...`
- `cli.invoke.*` decorator behavior

**Commit** : `docs(tech-debt): logging conventions for observability layer`

## Phase 3 Gate

- [ ] 3.1 commit + `personalscraper verify -v` émet `verify_item_done` events
- [ ] 3.2 commits + tous les `@app.command` ont `@cli_telemetry`
- [ ] 3.3 test console+log parity PASS
- [ ] 3.4 doc updated
- [ ] `make check` vert
- [ ] Pipeline-monitor host process peut désormais capter VERIFY events via le bus

**Phase gate commit** : `chore(tech-debt): phase 3 gate — observability`
