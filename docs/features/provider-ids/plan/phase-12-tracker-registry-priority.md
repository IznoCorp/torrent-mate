# Phase 12 — Tracker Registry Priority-Aware par Type de Média

## Goal

Étendre `TrackerRegistry` (existant `api/tracker/_registry.py`) pour supporter une priorité par type de média via `priority_by_media_type` dans `config/tracker.json5`. Aujourd'hui la priorité est globale `["lacale", "c411"]`. Demain : `priority_by_media_type = { movie_french: ["c411", "lacale"], anime_jp: [...], ... }` avec fallback sur priorité globale si type non listé.

## Gate (prerequisites)

- Phase 11 mergée (TrackerRegistry typé par capability).

## Sub-phases

### 12.1 — Étendre `TrackerRegistry.__init__`

Nouveau param `priority_by_media_type: dict[str, list[str]] | None = None`. Stocké dans `self._priority_by_media_type`. Si `None` ou `{}` → comportement actuel (priorité globale only).

Commit : `feat(provider-ids): TrackerRegistry accepts priority_by_media_type`

### 12.2 — `search_all(query, media_type=None)`

Signature mise à jour. Logique :

- Si `media_type` fourni ET `media_type in self._priority_by_media_type` → utilise cet ordre.
- Sinon → utilise `self._priority` (comportement existant — fallback).

Commit : `feat(provider-ids): TrackerRegistry.search_all per-media-type priority`

### 12.3 — Schema config + parser

`personalscraper/conf/models/api_config.py.TrackerConfig` : ajouter le champ optionnel :

```python
class TrackerConfig(_StrictModel):
    providers: dict[str, TrackerProviderConfig]
    priority: list[str]
    priority_by_media_type: dict[str, list[str]] = Field(default_factory=dict)
    ...
```

Validation : chaque liste dans `priority_by_media_type.values()` doit être un sous-ensemble de `providers.keys()`.

Commit : `feat(provider-ids): TrackerConfig schema with priority_by_media_type`

### 12.4 — Update `config.example/tracker.json5`

Ajouter le champ avec exemples commentés :

```json5
{
  tracker: {
    providers: { lacale: {...}, c411: {...} },
    priority: ["lacale", "c411"],
    priority_by_media_type: {
      // override de la priorité par défaut pour ce type de média
      // tous types non listés → fall through sur `priority` global
      // movie_french: ["c411", "lacale"],
      // anime_jp: ["lacale", "c411"],
      // tv_show_us: ["lacale"],
    },
    max_total_results: 50,
    ...
  },
}
```

Aussi : adapter `config/tracker.json5` réel de l'instance si l'utilisateur veut des overrides actifs.

Commit : `docs(provider-ids): tracker.json5 example with priority_by_media_type`

### 12.5 — Update `_activation.py` wiring

`personalscraper/api/_activation.py` : passe `priority_by_media_type` à `TrackerRegistry(...)`.

Commit : `feat(provider-ids): activate priority_by_media_type in tracker registry`

## Tests to write

- `test_tracker_registry_uses_per_media_type_priority_when_match`
- `test_tracker_registry_falls_back_to_global_priority_when_media_type_missing_or_none`
- `test_tracker_registry_falls_back_to_global_when_media_type_not_in_map`
- `test_tracker_config_validates_priority_by_media_type_subset_of_providers`
- `test_tracker_config_rejects_unknown_provider_in_priority_by_media_type`
- `test_tracker_config_loads_empty_priority_by_media_type_as_default`
- `test_activation_wires_priority_by_media_type` (integration)

## Acceptance criteria

- `TrackerRegistry.search_all("Query", media_type="movie_french")` interroge dans l'ordre `["c411", "lacale"]` si défini, sinon fallback global.
- Si `priority_by_media_type` absent ou vide → comportement identique à pré-refactor.
- Tests pass à 100%.
- Validation config rejette les listes qui référencent un provider non déclaré dans `providers`.

## Migration / config touch

**OBLIGATOIRE** (memory `feedback_no_backcompat_before_v1`) :

- `config.example/tracker.json5` étendu (schema additif backward-compatible côté field absent).
- `config/tracker.json5` réel de cette instance : pas obligé d'avoir `priority_by_media_type` (champ optionnel default `{}`), mais doc encourage l'usage.

## DESIGN reference

§6.7 (Tracker registry priority-aware), §2 scope.
