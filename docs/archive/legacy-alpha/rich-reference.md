# rich — Reference Documentation

> Date : 2026-04-10 | Contexte : V0 PROJECT SETUP — CLI output pour le pipeline PersonalScraper

## Qu'est-ce que rich ?

[rich](https://github.com/Textualize/rich) (v14+) est une librairie Python pour du texte riche
dans le terminal : couleurs, styles, progress bars, tables, tracebacks, panels, etc.

**Utilisé pour** : Améliorer l'output CLI de `personalscraper` — progress bars pendant le scraping,
tables de résumé en dry-run, status spinners, tracebacks lisibles.

**Version** : >= 14.0.0
**Licence** : MIT
**Python** : >= 3.8
**Dépendances** : `markdown-it-py`, `pygments`
**Stars** : 56k+

## Installation

```bash
pip install rich
```

Vérifier l'installation : `python -m rich` (affiche une démo complète).

## Console — `rich.console.Console`

Point d'entrée principal. Remplace `click.echo()` / `print()`.

### Création

```python
from rich.console import Console

# Console standard
console = Console()

# Mode quiet (supprime TOUT l'output)
console = Console(quiet=True)

# Sortie vers stderr
console = Console(stderr=True)
```

### Méthodes principales

```python
console.print("Hello [bold red]World[/]")           # Texte avec markup
console.print(table)                                  # N'importe quel renderable Rich
console.log("Processing...", style="dim")             # Avec timestamp + file:line
console.rule("[bold]Section Title")                   # Ligne horizontale avec titre

# Spinner pendant une opération
with console.status("[bold green]Querying TMDB API...") as status:
    result = tmdb_search(query)
    status.update("[bold green]Fetching details...")
    details = tmdb_details(result.id)
```

### Intégration avec Click

Pattern recommandé — Console partagée via `click.Context` :

```python
import click
from rich.console import Console

@click.group()
@click.option("--quiet", "-q", is_flag=True)
@click.option("--verbose", "-v", is_flag=True)
@click.pass_context
def cli(ctx, quiet, verbose):
    """PersonalScraper — Media pipeline automation."""
    ctx.ensure_object(dict)
    ctx.obj["console"] = Console(quiet=quiet)
    ctx.obj["verbose"] = verbose
```

`Console(quiet=True)` supprime tout l'output nativement — pas besoin de `if not quiet:` partout.

## Progress — `rich.progress.Progress`

### Pattern simple : `track()`

```python
from rich.progress import track

for movie in track(movies, description="Scraping TMDB..."):
    scrape_movie(movie)
```

### Pattern complet : `Progress()` context manager

```python
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    MofNCompleteColumn, TimeElapsedColumn, TimeRemainingColumn,
    DownloadColumn, TransferSpeedColumn,
)
```

### Scraping media (réseau, nombre d'items connu)

```python
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeElapsedColumn(),
    console=console,
    transient=True,       # Effacer la barre à la fin
) as progress:
    task = progress.add_task("Scraping TMDB...", total=len(movies))
    for movie in movies:
        scrape_movie(movie)
        progress.update(task, advance=1)
```

### Déplacement fichiers (taille connue)

```python
with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    DownloadColumn(),           # Affiche la taille (Mo/Go)
    TransferSpeedColumn(),      # Vitesse de transfert
    TimeRemainingColumn(),
    console=console,
) as progress:
    task = progress.add_task(f"Moving to {disk}...", total=total_bytes)
    # Mettre à jour avec les bytes écrits
    progress.update(task, advance=bytes_written)
```

### Tâches multiples simultanées

```python
with Progress(console=console) as progress:
    scrape_task = progress.add_task("Scraping...", total=50)
    art_task = progress.add_task("Artwork...", total=None)  # Indéterminé (pulsating)

    # Chaque tâche se met à jour indépendamment
    progress.update(scrape_task, advance=1)
    progress.update(art_task, completed=30, total=100)  # Switch en déterminé
```

### Spinner indéterminé (API calls)

```python
with console.status("[bold green]Connexion à qBittorrent...") as status:
    client.login()
    status.update("[bold green]Récupération des torrents...")
    torrents = client.get_completed()
```

### Paramètres clés de `Progress`

| Paramètre            | Défaut | Description                        |
| -------------------- | ------ | ---------------------------------- |
| `console`            | None   | Console custom                     |
| `transient`          | False  | True = effacer la barre à la fin   |
| `disable`            | False  | True = désactiver (pour `--quiet`) |
| `expand`             | False  | True = pleine largeur              |
| `refresh_per_second` | 10     | Fréquence de rafraîchissement      |

### Paramètres de `add_task()`

| Paramètre     | Description                                 |
| ------------- | ------------------------------------------- |
| `description` | Texte à gauche                              |
| `total`       | Nombre total (None = indéterminé/pulsating) |
| `visible`     | True/False pour montrer/cacher              |
| `start`       | True = démarrer immédiatement               |

## Table — `rich.table.Table`

### Dry-run summary

```python
from rich.table import Table
from rich import box

table = Table(title="Dry Run — Pending Moves", box=box.ROUNDED)
table.add_column("Source", style="cyan")
table.add_column("Destination", style="green")
table.add_column("Size", justify="right", style="yellow")
table.add_column("Action", style="magenta")

for item in plan:
    table.add_row(str(item.source), str(item.dest), item.size, item.action)

console.print(table)
```

### Résultats de vérification (V4)

```python
table = Table(title="Verification Results", box=box.ROUNDED)
table.add_column("Media", style="bold")
table.add_column("NFO", justify="center")
table.add_column("Poster", justify="center")
table.add_column("Category", style="magenta")
table.add_column("Status", justify="center")

for m in results:
    nfo = "[green]OK[/]" if m.has_nfo else "[red]MISSING[/]"
    poster = "[green]OK[/]" if m.has_poster else "[red]MISSING[/]"
    status = {"valid": "[green]PASS[/]", "fixed": "[yellow]FIXED[/]", "blocked": "[red]FAIL[/]"}[m.status]
    table.add_row(m.name, nfo, poster, m.category or "?", status)

console.print(table)
```

### Résumé dispatch (V5)

```python
table = Table(title="Dispatch Summary", box=box.ROUNDED, row_styles=["", "dim"])
table.add_column("Media", style="bold")
table.add_column("Disk", style="cyan")
table.add_column("Category", style="magenta")
table.add_column("Action", style="yellow")
table.add_column("Size", justify="right")

for r in dispatch_results:
    action_style = {"replaced": "yellow", "merged": "blue", "moved": "green", "skipped": "dim"}
    table.add_row(r.name, r.disk or "-", r.category, f"[{action_style.get(r.action, '')}]{r.action}[/]", r.size)
```

### Paramètres principaux de `Table`

| Paramètre    | Description                                                         |
| ------------ | ------------------------------------------------------------------- |
| `title`      | Titre du tableau                                                    |
| `box`        | Style de bordure (`box.ROUNDED`, `box.SIMPLE`, `box.MINIMAL`, etc.) |
| `row_styles` | Styles alternés (`["", "dim"]` pour zebra)                          |
| `expand`     | True = pleine largeur                                               |
| `show_lines` | True = lignes entre les rangées                                     |

### Styles de bordure (`rich.box`)

Principaux : `ROUNDED`, `SIMPLE`, `MINIMAL`, `HEAVY_HEAD`, `DOUBLE`, `ASCII`.
Voir tous : `python -m rich.box`

## Panel — `rich.panel.Panel`

Boîte avec bordure pour les résumés.

```python
from rich.panel import Panel

# Résumé pipeline
summary = (
    "[green]Ingest[/]: 3 torrents (2 copied, 1 moved)\n"
    "[green]Sort[/]: 2 movies, 4 episodes\n"
    "[green]Scrape[/]: 2 movies, 1 series\n"
    "[yellow]Dispatch[/]: 2 movies → Disk3, 4 episodes → Disk2\n"
    "[dim]Duration: 4min 32s[/]"
)
console.print(Panel(summary, title="Pipeline Report", expand=False))
```

## Markup — Syntaxe de style

```python
console.print("[bold]Gras[/bold]")
console.print("[red]Rouge[/red]")
console.print("[bold red on white]Gras rouge sur blanc[/]")
console.print("[link=https://tmdb.org]TMDB[/link]")       # Lien cliquable
console.print(":thumbs_up: Success!")                       # Emoji

# SÉCURITÉ : Toujours escaper l'input utilisateur
from rich.markup import escape
console.print(escape(user_provided_string))
```

## Traceback — `rich.traceback`

Tracebacks colorés et lisibles avec variables locales.

```python
from rich.traceback import install
install(
    show_locals=False,    # True = afficher les variables locales (debug)
    suppress=[click],     # Masquer les frames de Click
    max_frames=100,
)
```

**Installation globale** : Appeler `install()` au démarrage du CLI. Toutes les exceptions non catchées
seront formatées avec Rich automatiquement.

```python
# Ou manuellement dans un except :
try:
    something()
except Exception:
    console.print_exception(show_locals=True)
```

## Logging — `rich.logging.RichHandler`

Remplace le handler console de stdlib logging par un output Rich coloré.

```python
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(
        rich_tracebacks=True,
        tracebacks_suppress=[click],
        markup=False,            # IMPORTANT : False par défaut pour éviter les faux markup
    )],
)
```

**Attention** : Si `markup=True`, tout texte entre `[crochets]` dans les logs sera interprété
comme du markup Rich. Laisser à `False` sauf si on contrôle tous les messages.

**Note** : Dans le pipeline, `RichHandler` sera utilisé pour le handler console uniquement.
Le handler fichier utilisera `structlog` avec `JSONRenderer` (V6).

## Theming

Définir un thème cohérent pour tout le pipeline :

```python
from rich.theme import Theme

PIPELINE_THEME = Theme({
    "info": "dim cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "success": "bold green",
    "path": "underline blue",
    "size": "yellow",
    "media.title": "bold magenta",
    "media.year": "cyan",
    "disk.name": "bold cyan",
    "action.move": "green",
    "action.replace": "yellow",
    "action.merge": "blue",
    "action.skip": "dim",
    "dryrun": "italic dim",
})

console = Console(theme=PIPELINE_THEME)
console.print("[success]Done![/success]")
console.print("[action.replace]REPLACE[/] [media.title]Fight Club[/] [media.year](1999)[/]")
```

Le thème hérite des styles Rich par défaut (progress bars, tables, etc.) — on override uniquement ce qu'on veut.

## Comportement automatique TTY/pipe

Rich détecte automatiquement l'environnement :

| Contexte                       | Comportement                                     |
| ------------------------------ | ------------------------------------------------ |
| Terminal interactif            | Couleurs, animations, progress bars              |
| Pipe (`\| less`, `> file.txt`) | Texte brut, pas d'escape codes, pas d'animations |
| CI/CD (pas de TTY)             | Texte brut, largeur 80 colonnes                  |
| `--quiet`                      | `Console(quiet=True)` supprime tout              |

**Variables d'environnement** :

| Variable      | Effet                                         |
| ------------- | --------------------------------------------- |
| `NO_COLOR`    | Supprime les couleurs (pas gras/italic)       |
| `FORCE_COLOR` | Force les couleurs même en pipe               |
| `COLUMNS`     | Largeur du terminal (défaut 80 si pas de TTY) |
| `TERM=dumb`   | Désactive tout styling                        |

## rich-click (optionnel)

`rich-click` améliore automatiquement le `--help` de Click avec Rich.

```bash
pip install rich-click
```

```python
import rich_click as click  # Drop-in replacement

@click.command()
def my_command():
    ...
```

**Verdict** : Cosmétique pure. Utile pour un joli `--help` mais pas nécessaire au lancement.
Peut être ajouté plus tard sans changement de code (juste changer l'import).

## Gotchas

### 1. Markup dans les logs

Si `markup=True` sur `RichHandler`, les messages contenant `[text]` seront interprétés comme
du markup et peuvent lever `MarkupError`. Laisser `markup=False` par défaut.

### 2. Escape de l'input utilisateur

```python
from rich.markup import escape
console.print(f"Processing: {escape(user_filename)}")
```

Les noms de fichiers avec des crochets (`[2024]`, `[MULTi]`) seraient interprétés comme du markup.

### 3. Performance

~2-5 ms d'overhead par invocation CLI. Import ~50-100 ms. **Négligeable** pour un pipeline qui
tourne pendant des secondes à minutes.

### 4. `NO_COLOR=""` depuis v14.0.0

Une variable `NO_COLOR` vide est maintenant traitée comme **non définie** (pas activée).
Avant v14.0, toute valeur (même vide) l'activait.

### 5. Progress + print

Pour afficher du texte au-dessus d'une progress bar active, utiliser `progress.console.print()`
(pas `console.print()` directement, sinon la barre clignote).

## Utilisation dans le pipeline

| Version | Composant                 | Usage                                 |
| ------- | ------------------------- | ------------------------------------- |
| V0      | Console, Theme, Traceback | Setup de base, thème, tracebacks      |
| V1      | Status spinner            | Connexion qBittorrent, copie torrents |
| V2      | Progress track            | Tri des fichiers                      |
| V3      | Progress multi-task       | Scraping TMDB/TVDB + artwork download |
| V4      | Table                     | Résultats de vérification             |
| V5      | Table, Progress           | Résumé dispatch, progress déplacement |
| V6      | Panel, RichHandler        | Rapport pipeline, logging console     |
