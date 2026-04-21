# Phase 5 — CLI integration : top-level `--config` + eager load

## Objectif

Intégrer `conf/` dans la CLI Typer : option globale `--config`, chargement eager au callback (sauf `init-config`), erreur claire immédiate si config invalide.

## Sous-phases

### 5.1 — `AppCtx` dataclass + imports

- [ ] Ajouter à `personalscraper/cli.py` :
  - `from dataclasses import dataclass`
  - `from personalscraper.conf.loader import load_config, resolve_config_path, ConfigNotFoundError, ConfigValidationError`
  - `from personalscraper.conf.models import Config`
  - `@dataclass class AppCtx: config: Config | None; config_override: Path | None`
- [ ] Tests : import path fonctionne, dataclass instantiable

**Commit** : `v15.5.1: Add AppCtx dataclass in cli.py`

### 5.2 — `@app.callback()` : eager load + init-config bypass

- [ ] Modifier le callback top-level existant :

  ```python
  @app.callback()
  def main(
      ctx: typer.Context,
      config: Path | None = typer.Option(None, "--config", "-c",
          help="Path to config.json5 (overrides ./config.json5 and $PERSONALSCRAPER_CONFIG). Position: BEFORE the subcommand."),
  ) -> None:
      if ctx.invoked_subcommand == "init-config":
          ctx.obj = AppCtx(config=None, config_override=config)
          return
      try:
          cfg = load_config(resolve_config_path(config))
      except (ConfigNotFoundError, ConfigValidationError) as exc:
          typer.echo(f"Config error: {exc}", err=True)
          raise typer.Exit(code=2) from exc
      ctx.obj = AppCtx(config=cfg, config_override=config)
  ```

- [ ] Tests : `personalscraper` sans config.json5 → exit 2 avec message ; `personalscraper init-config` sans config → OK (bypass)

**Commit** : `v15.5.2: Eager config load in CLI callback with init-config bypass`

### 5.3 — Brancher la commande `init-config`

- [ ] Ajouter dans `cli.py` :

  ```python
  @app.command("init-config")
  def init_config_cmd(
      example: Path = typer.Option(Path("config.example.json5")),
      output: Path = typer.Option(Path("config.json5")),
      non_interactive: bool = typer.Option(False, "--yes"),
      from_current: bool = typer.Option(False, "--from-current"),
      force: bool = typer.Option(False, "--force"),
  ) -> None:
      from personalscraper.commands.init_config import init_config
      init_config(example, output, interactive=not non_interactive, from_current=from_current, force=force)
  ```

- [ ] Tests : `personalscraper init-config --help` affiche les flags ; flow E2E depuis CLI (déjà en P4.8)

**Commit** : `v15.5.3: Wire init-config Typer command to commands module`

### 5.4 — Toutes les subcommands accèdent à `ctx.obj.config`

- [ ] Pour chaque commande V14 existante (`ingest`, `sort`, `scrape`, `verify`, `dispatch`, `run`, `library-scan`, `library-clean`, `library-validate`, `library-analyze`, `library-recommend`, `library-rescrape`, `library-report`, `enforce`, `process`) :
  - Ajouter `ctx: typer.Context` en premier param
  - Accéder `config = ctx.obj.config` (garanti non-None via callback)
  - Passer `config` en paramètre aux services (Pipeline, Scraper, Dispatcher — refactorés en P6-7)
- [ ] Pour l'instant, l'accès est fait même si les services ne consomment pas encore Config (P6-7 le brancheront)

**Commit** : `v15.5.4: Route Config through all subcommands via ctx.obj`

### 5.5 — `--category` accepte ID ou alias

- [ ] Pour chaque commande `library-*` qui prend `--category <name>` :
  - Après parsing du flag, appeler `ctx.obj.config.resolve_category_alias(category)` → `category_id`
  - Si `None` → error avec liste des IDs valides + aliases, exit 2
- [ ] Tests : `--category movies` (ID direct), `--category "Mon alias"` (alias défini), `--category inconnu` (error)

**Commit** : `v15.5.5: Accept category ID or alias in library-* CLI commands`

## Tests de cohérence P5→P6

- [ ] `personalscraper --help` n'ouvre pas `config.json5` (Click short-circuits `--help`)
- [ ] `personalscraper run -v` sans `config.json5` → exit 2 avec message pointant vers `init-config`
- [ ] `personalscraper init-config` sans `config.json5` → OK (bypass du callback)
- [ ] Erreur sur path `--config` invalide → message clair immédiat
- [ ] Toutes les subcommands recoivent `ctx.obj.config` non-None (via callback guarantee)
- [ ] mypy strict : 0 erreur sur `cli.py`
