# Phase 01 — Generic Torznab extrait de C411 (comportement pinné)

**Goal**: `personalscraper/api/tracker/torznab.py` — client Torznab générique paramétré,
extrait de `c411.py` (329 lignes, éprouvé prod). `C411Client` devient une config nommée du
générique. **Comportement byte-identique pinné par les tests existants.**

**Design**: DESIGN §3 D1.

## Surface

| Fichier                                  | Action                                                                                              |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `personalscraper/api/tracker/torznab.py` | **NEW** — `TorznabDescriptor` (dataclass) + `TorznabClient`                                         |
| `personalscraper/api/tracker/c411.py`    | devient une sous-classe/config fine du générique (provider_name, base_url, particularités)          |
| `tests/unit/test_torznab_client.py`      | **NEW** — tests du générique (paramétrage, mapping attrs, erreurs)                                  |
| `tests/unit/test_c411_client.py`         | **INCHANGÉ** — c'est le pin ; toute modification = échec de phase sauf imports mécaniques justifiés |

## Sous-phases

### 1.1 — Extraction

**Commit**: `feat(torznab): extract the generic Torznab client from c411`

Le descriptor porte : `provider_name`, `base_url`, `api_path`, `apikey` (valeur résolue par
l'activation), mapping catégories, quirks documentés de c411 (pas d'élément `<category>` par
item, `torznab:attr` aplatis, pas d'endpoint détail). La logique HTTP/parsing/erreurs part
telle quelle dans le générique — pas de « nettoyage » opportuniste (règle : refactor
comportement-préservant, le diff de c411.py doit se lire comme une délégation).

### 1.2 — Tests du générique

**Commit**: `test(torznab): generic client behaviour — parametrization, attrs, fail-soft`

Réutiliser les fixtures XML de test_c411_client.py par import/partage (pas de copie). Cas :
deux descriptors différents → URLs/params corrects ; attrs aplatis ; XML malformé → l'erreur
attendue par le registry (fail-soft) ; timeout → idem.

## Gate

1. `pytest tests/unit/test_c411_client.py -q` — vert **sans modification du fichier** (git diff vide dessus, imports exceptés).
2. `pytest tests/unit/test_torznab_client.py tests/unit/test_tracker_factory.py tests/unit/test_tracker_parser_schema_drift.py -q` — vert.
3. `python3 -m mypy personalscraper/` — 0.
4. `pytest tests/acquire/ -q` — vert (la chaîne search/grab consomme le client via le registry).
