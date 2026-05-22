# Phase 2 — CLI gaps + backfill-ids first run

**Effort** : 2 jours
**Theme** : combler les commandes manquantes + fix bugs CLI critiques + backfill first run.

## Coverage matrix

| Item                                  | Sub-phase | Source pattern |
| ------------------------------------- | --------- | -------------- |
| MUST-3 / DEV #16 / BD-G / CL-L / CF-A | 2.1       | P12            |
| MUST-9 / DEV #21 / CL-A               | 2.2       | P21            |
| MUST-11 / DEV #7 / CL-I               | 2.3       | P8             |
| MUST-12 / CL-T                        | 2.4       | P20            |
| MUST-13 / CL-K                        | 2.5       | P12            |
| MUST-19 / BD-T (+DEV #28 partial)     | 2.6       | P23            |

DESIGN sections impacted : §10 CLI surface completeness, §13 promise lifecycle.

## Gate

- Phase 1 commited + gate vert
- `library-reconcile` produit `merkle_drift=[]`

## Sub-phases

### 2.1 `library-scan` CLI command (MUST-3 / DEV #16 / BD-G / CL-L / CF-A)

**Site** : `personalscraper/commands/library/scan.py` (nouveau) — exposé via Typer
sub-app library.

**Implementation** :

```python
@app.command("library-scan")
@cli_telemetry  # decorator from Phase 3.2
@handle_cli_errors
def library_scan(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", "-d"),
    mode: str = typer.Option("full", "--mode"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Scan media directories on disks, create media_item rows from NFOs."""
    config = ctx.obj.config
    from personalscraper.library.scanner import scan_library
    settings = cli_compat.get_settings()
    with per_step_boundary(config, settings) as app_context:
        scan_library(config, settings, disk_filter=disk, dry_run=dry_run, event_bus=app_context.event_bus)
```

**Commit** : `feat(tech-debt): expose library-scan CLI command (DEV #16)`

### 2.2 --dry-run on 4 mutating commands (MUST-9 / DEV #21 / CL-A)

**Sites** :

- `personalscraper/commands/library/maintenance.py` — `library-repair`, `library-relink`,
  `library-clean`, `library-verify`
- `personalscraper/commands/init_config.py` — `init-config`

**Implementation** : ajouter `dry_run: bool = typer.Option(False, "--dry-run", help="...")`
au sig + plumber jusqu'au repository / FS layer + log les actions au lieu de muter.

Pour `library-verify` : flag `--no-enqueue` au lieu de `--dry-run` (verify n'écrit pas la BDD
sauf `repair_queue`).

**Commits** : un par command :

- `feat(tech-debt): add --dry-run to library-repair`
- `feat(tech-debt): add --dry-run to library-relink`
- `feat(tech-debt): add --dry-run to library-clean`
- `feat(tech-debt): add --no-enqueue to library-verify`
- `feat(tech-debt): add --dry-run to init-config`

### 2.3 `run --help` introspection (MUST-11 / DEV #7 / CL-I)

**Site** : `personalscraper/commands/pipeline.py` — `run()` command docstring.

**Approach** : generate the docstring from `Pipeline.STEPS` (or équivalent) au runtime via
`@app.command()` `help` parameter computed.

```python
def _run_help() -> str:
    from personalscraper.pipeline import Pipeline
    steps = " → ".join(s.name for s in Pipeline.STEPS)
    return f"Run full pipeline ({steps})."

@app.command(help=_run_help())
def run(...): ...
```

**Commit** : `fix(tech-debt): generate run --help from Pipeline.STEPS (DEV #7)`

### 2.4 Test "matrix references valid CLI" (MUST-12 / CL-T)

**Site** : `tests/skill/test_matrix_cli_refs.py` (nouveau) ou si tests skill sont dans `.claude/`
le mettre là.

**Scenario** : lit `references/design-conformity-matrix.md`, extrait toutes les commandes
`personalscraper <cmd>` + leurs flags. Pour chacune, lance `personalscraper <cmd> --help` →
assert exit 0. Aurait attrapé DEV #10 + DEV #20.

**Commit** : `test(tech-debt): matrix references must point to valid CLI (MUST-12)`

### 2.5 CI coverage CLI test (MUST-13 / CL-K)

**Site** : `scripts/audit-cli-coverage.py` (nouveau) + CI hook.

**Scenario** : itère `personalscraper/commands/*.py` + sub-cli files. Pour chaque
`@app.command`, vérifie qu'il a une entrée dans `docs/reference/commands.md`. + pour chaque
module métier (`library/`, `indexer/`, `scraper/`, `trailers/`), vérifie qu'une commande CLI
l'invoke.

**Commit** : `test(tech-debt): CLI coverage audit script + CI hook (MUST-13)`

### 2.6 Backfill-ids first run (MUST-19 / BD-T) — one-shot

**Action** : lance `personalscraper library-index --mode backfill-ids` sur la BDD prod après
2.1 (library-scan crée les media_item manquants).

**Validation** : `SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL` tends
vers 0.

**Pas de commit code** — c'est une action ops, à noter dans `docs/pipeline-runs/` ou un runbook.

## Phase 2 Gate

- [ ] 2.1 `library-scan` exists + tests
- [ ] 2.2 4 commandes ont --dry-run
- [ ] 2.3 `run --help` mentions enforce + trailers
- [ ] 2.4 test matrix-CLI refs PASS
- [ ] 2.5 CI script passes on current matrix v2.0
- [ ] 2.6 backfill-ids first run done, canonical_provider populated > 0
- [ ] `make check` vert

**Phase gate commit** : `chore(tech-debt): phase 2 gate — CLI gaps`
