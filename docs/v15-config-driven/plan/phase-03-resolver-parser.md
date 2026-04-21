# Phase 3 — Resolver + Example Parser

## Objectif

Implémenter les utilitaires purs : résolution `category_id → folder/disk` et extraction des commentaires JSON5 pour `init-config`.

## Sous-phases

### 3.1 — `conf/resolver.py` : folder_for + pick_disk_for

- [ ] Créer `personalscraper/conf/resolver.py` avec :
  - `folder_for(config, disk, category_id) -> Path`
  - `pick_disk_for(config, category_id, free_space_by_id, min_free_gb, item_size_gb) -> DiskConfig | None` avec formule V14 `threshold = max(min_free_gb, item_size_gb * 1.5)`
- [ ] Tests unitaires : folder_for avec category custom (default_label), pick_disk_for avec 0/1/N candidates, disques remplis, threshold V14

**Commit** : `v15.3.1: Add conf/resolver.py with folder_for and pick_disk_for`

### 3.2 — `conf/example_parser.py` : squelette + `Prompt` dataclass

- [ ] Créer `personalscraper/conf/example_parser.py` avec :
  - `@dataclass Prompt(key_path, comment, default_value)`
  - `parse_example(example_path: Path) -> list[Prompt]` (stub pour l'instant)
- [ ] Fixture `tests/conf/fixtures/example_simple.json5` : cas minimal (1 clé + 1 commentaire)

**Commit** : `v15.3.2: Add example_parser.py scaffold with Prompt dataclass`

### 3.3 — Parser ligne-par-ligne : extraction commentaires

- [ ] Implémenter `parse_example` :
  - Lit le fichier ligne par ligne
  - Track object/array depth (via `{`, `}`, `[`, `]` count — respect strings)
  - Accumule consecutive `//` comment lines dans `current_comment`
  - Gère `/* ... */` multi-line block comments
  - Sur une ligne "key: value" → émet `Prompt(key_path, current_comment, value_literal)` ; reset `current_comment`
  - Reset `current_comment` sur ligne blanche ou non-key/non-comment
  - Pour les arrays : émet un prompt synthétique par élément ou un seul pour le count
- [ ] Tests avec fixtures :
  - `example_simple.json5` : 1 clé, 1 commentaire
  - `example_nested.json5` : nested objects
  - `example_arrays.json5` : arrays
  - `example_comments.json5` : block comments, multiline, comments sans keys
  - `example_full.json5` : copy de `config.example.json5`

**Commit** : `v15.3.3: Implement line-based JSON5 comment extraction in example_parser`

### 3.4 — Tests d'intégration parser → valid prompts

- [ ] Test : parse_example(config.example.json5) retourne un Prompt par champ leaf
- [ ] Test : chaque Prompt a un `key_path` valide (navigable via `pydantic.Config.model_fields`)
- [ ] Test : chaque Prompt a un comment non-vide (tous les champs doivent être documentés)
- [ ] Test : default_value est un littéral JSON5 valide (roundtrip parseable)

**Commit** : `v15.3.4: Add integration tests for parser against config.example.json5`

## Tests de cohérence P3→P4

- [ ] `tests/conf/test_resolver.py` : tous passent
- [ ] `tests/conf/test_example_parser.py` : tous passent (min 5 fixtures)
- [ ] `parse_example('config.example.json5')` produit des Prompts pour chaque champ
- [ ] mypy strict : 0 erreur sur `conf/resolver.py`, `conf/example_parser.py`
- [ ] Aucune dépendance externe nouvelle au-delà de `json5` (déjà ajouté en P1)
