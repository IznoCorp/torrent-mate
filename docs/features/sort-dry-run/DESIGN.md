# Dry-Run Flag for Sort Command — Design Spec

**Date**: 2026-04-22
**Status**: Smoke test pilot feature for implement:\* skills refactor
**Scope**: Ajouter un flag `--dry-run` à la commande `personalscraper sort` pour simuler le tri sans déplacer/renommer aucun fichier.

## 1. Motivation

Permettre à l'utilisateur de prévisualiser les actions du pipeline de tri avant exécution : quels dossiers seraient déplacés, renommés ou dispatchés vers quel disque. Utile pour vérifier la classification avant d'engager des mouvements irréversibles.

## 2. Comportement

- `personalscraper sort --dry-run` : imprime les actions qui SERAIENT effectuées, sans toucher au système de fichiers.
- Sortie : pour chaque item dans `097-TEMP/`, afficher `[DRY-RUN] {current_path} → {predicted_destination}` avec la catégorie déduite.
- Aucun écrit sur disque (pas de move, rename, mkdir).
- Exit code 0 si dry-run complet, 1 si erreur de classification.

## 3. Architecture

Un seul point d'injection : la fonction `sort()` de `personalscraper/sort/run.py` prend un nouveau paramètre `dry_run: bool = False`. Si `True`, les opérations `shutil.move` / `os.rename` sont remplacées par un `logger.info(f"[DRY-RUN] ...")`.

Le flag CLI est exposé via Click dans `personalscraper/cli.py` :

```python
@cli.command()
@click.option("--dry-run", is_flag=True, help="Simulate without moving files")
def sort(dry_run: bool) -> None:
    ...
```

## 4. Scope

**Dans le scope :**

- Flag CLI `--dry-run` sur la commande `sort` uniquement
- Branche `if dry_run:` dans `sort/run.py` pour intercepter les opérations filesystem
- Tests unitaires : appel avec/sans flag, vérifier aucun side effect en dry-run
- Tests E2E : smoke check `personalscraper sort --dry-run` sur dossier temp peuplé

**Hors scope :**

- Autres commandes (ingest, process, dispatch) — pourraient bénéficier du même flag mais pas dans cette feature
- Output format (JSON, etc.) — pour l'instant juste des logs texte
- Rollback / undo après un sort réel

## 5. Phases

| #   | Phase                             | Scope                                                                 |
| --- | --------------------------------- | --------------------------------------------------------------------- |
| 1   | CLI + core dry-run branch + tests | Modifier `cli.py`, `sort/run.py`, tests unitaires. Pas de E2E encore. |

Une seule phase, car le scope est contenu (un seul flag, un seul point d'injection). Pas de sous-phases lourdes attendues.

## 6. Acceptance criteria

- `personalscraper sort --dry-run` exécute sans toucher au filesystem
- Tests unitaires couvrent le branch `if dry_run:`
- `make test` et `make lint` verts
- Aucun fichier déplacé/renommé dans un test filesystem réel
