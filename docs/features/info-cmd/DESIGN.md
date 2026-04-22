# `personalscraper info` Command — Design Spec

**Date**: 2026-04-22
**Scope**: Ajouter une nouvelle commande `personalscraper info` qui imprime un état synthétique du pipeline : version courante, chemins de configuration, disques détectés avec espace libre.

## 1. Motivation

Au quotidien l'utilisateur a besoin de vérifier rapidement :

- Quelle version du logiciel est installée (utile après bump SemVer)
- Où pointent les chemins de staging, archive, et disques de stockage
- Si chaque disque est monté et combien d'espace reste libre (évite les crashs mid-pipeline)

Actuellement ces informations sont dispersées : version dans `pyproject.toml`/`__init__.py`, chemins dans `config.json5`, espace disque via `df` manuel.

## 2. Comportement

```
$ personalscraper info
personalscraper 0.15.0

Config
  staging: /Volumes/IznoServer SSD/A TRIER
  archive: /Volumes/IznoServer SSD/A TRIER/Done

Disks (4 configured)
  DISK01  /Volumes/DISK01   1.2 TB / 2.0 TB (60% used)
  DISK02  /Volumes/DISK02   800 GB / 2.0 TB (40% used)
  DISK03  /Volumes/DISK03   MOUNTED BUT EMPTY
  DISK04  -                 NOT MOUNTED
```

Sortie structurée, lisible, texte brut (pas de JSON pour v1).

## 3. Architecture

**Nouveau module** : `personalscraper/info/run.py` contenant :

- `collect_info(config: Config) -> InfoReport` — rassemble version + paths + disk stats
- `format_info(report: InfoReport) -> str` — transforme en texte lisible

**CLI** : nouvelle commande dans `personalscraper/cli.py` :

```python
@app.command()
def info(ctx: typer.Context) -> None:
    """Display version, config paths, and disk status."""
    from personalscraper.info.run import collect_info, format_info
    config = ctx.obj["config"]
    report = collect_info(config)
    print(format_info(report))
```

**Version detection** : lire depuis `personalscraper.__version__` (fallback pyproject ou VERSION si absent).

**Disk stats** : utiliser `shutil.disk_usage(path)` pour chaque disque configuré. Gérer les cas :

- Disque non monté (le chemin n'existe pas) → `"NOT MOUNTED"`
- Disque monté mais vide → `"MOUNTED BUT EMPTY"` (juste les headers du FS, < 1 MB used)
- Disque avec données → `"{used} / {total} ({percent}% used)"` avec formatage humain (KB/MB/GB/TB)

**Types** :

```python
@dataclass(frozen=True)
class DiskStatus:
    name: str                    # e.g. "DISK01"
    path: Path | None            # mount point, None if not configured
    mounted: bool
    total_bytes: int             # 0 if not mounted
    used_bytes: int              # 0 if not mounted or empty

@dataclass(frozen=True)
class InfoReport:
    version: str
    staging_path: Path
    archive_path: Path
    disks: list[DiskStatus]
```

## 4. Scope

**Dans le scope** :

- `personalscraper/info/__init__.py` + `personalscraper/info/run.py` (nouveau module)
- CLI `info` command dans `personalscraper/cli.py`
- Tests unitaires `tests/info/test_run.py` couvrant : version detection, disk_usage mocking, not-mounted case, formatting
- Test CLI `tests/test_cli.py::test_info_command` (smoke : exit 0 + output contient `personalscraper`)

**Hors scope** :

- Format JSON (v2)
- Couleurs ANSI dans la sortie
- Détection de disques non configurés (auto-discovery) — on n'affiche que les disques déclarés dans la config

## 5. Phases

| #   | Phase                            | Scope                                                                                                               |
| --- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 1   | Core `info` module + CLI + tests | Créer `info/run.py` avec `collect_info` + `format_info` + types. Ajouter commande CLI. Unit tests + CLI smoke test. |

Une seule phase suffit : la feature est contenue (nouveau module isolé + 1 commande CLI).

## 6. Acceptance criteria

- `personalscraper info` exécute avec exit code 0
- Output contient "personalscraper" + version string
- Output contient au moins les chemins `staging:` et `archive:`
- Output liste les disques avec leur statut (monté ou non)
- Tests unitaires verts : version detection, disk_usage OK, not-mounted, empty, formatted output
- `make lint` + `make test` verts
- Aucune modif du code existant (purement additif)
