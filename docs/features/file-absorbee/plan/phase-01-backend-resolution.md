# Phase 01 — Backend : la route suit le pointeur

**Défaut visé** : `GET /api/acquisition/wanted` sert `wanted.status` verbatim
(`personalscraper/web/routes/acquisition.py:516`), donc `absorbed` pour 31 lignes dont
l'acquisition est terminée.

## 01.1 — Le test rouge d'abord

Fichier : `tests/unit/web/routes/test_wanted_absorbed_resolution.py` (nouveau).

Fixture : une base `acquire.db` temporaire portant la forme réelle du bug —

| ligne | kind    | saison | épisode | status     | absorbed_by |
| ----- | ------- | ------ | ------- | ---------- | ----------- |
| 5     | episode | 15     | 21      | `absorbed` | 88          |
| 6     | episode | 15     | 22      | `absorbed` | 88          |
| 7     | episode | 17     | 23      | `absorbed` | 89          |
| 8     | episode | 17     | 24      | `absorbed` | 89          |
| 88    | season  | 15     | —       | `done`     | NULL        |
| 89    | season  | 17     | —       | `done`     | NULL        |

Cas couverts (un test par cas, chacun nommé d'après ce qu'il prouve) :

1. **Le défaut rapporté** — les 4 lignes épisode sont servies `status="done"`, pas
   `"absorbed"`. **Ce test doit être écrit et vu ROUGE avant 01.2.**
2. **Saison vivante** — une ligne absorbée par une saison `pending` (resp. `searching`,
   `grabbed`) est servie avec ce statut : la ligne suit sa saison *aussi quand celle-ci est
   en vol*, pas seulement quand elle est terminée.
3. **Pointeur NULL** — `absorbed_by IS NULL` → servie `"absorbed"` (D3).
4. **Pointeur cassé** — `absorbed_by` désigne une ligne inexistante → servie `"absorbed"` (D3).
5. **Saison sur une autre page** — la ligne saison est hors de la page demandée
   (`page_size=2`) : la résolution la trouve quand même. Preuve que la résolution ne dépend
   pas de la pagination.
6. **Ligne non absorbée** — une ligne `pending` / `done` / `grabbed` ordinaire traverse la
   route inchangée (non-régression).

Contrainte de test connue du dépôt : les tests de commande CLI doivent patcher
`personalscraper.conf.loader.load_config`. Ici c'est une route — utiliser le TestClient et
pointer `app.state.config.acquire.db_path` sur la base temporaire. **Attention au piège
`check_same_thread`** : le TestClient exécute la route dans un threadpool, une assertion
sqlite cross-thread est vacueuse. Vérifier que les asserts portent sur le payload JSON
rendu, pas sur une connexion partagée.

## 01.2 — La résolution, par le seam

Fichier : `personalscraper/web/routes/acquisition.py`, fonction `get_wanted` (l.456-525).

1. Importer `substitute_absorbed_facts` depuis
   `personalscraper.web.acquisition.states`.
2. Après le `fetchall()` de la page (l.495-505) : collecter les `absorbed_by` non-NULL de la
   page, puis **une** requête
   `SELECT id, status, last_search_outcome, last_search_found FROM wanted WHERE id IN (…)`
   pour construire le `season_facts: dict[int, WantedFacts]`. La requête est nécessaire parce
   que la ligne saison peut être hors page (cas de test 5).
   - Si aucun `absorbed_by` : ne pas émettre la requête (garder le coût nul sur le cas courant).
   - Le paramétrage `IN (…)` doit être construit par placeholders, jamais par interpolation.
3. Passer les lignes de la page à `substitute_absorbed_facts` sous la forme
   `(id, status, last_search_outcome, last_search_found, absorbed_by)` ; récupérer le statut
   résolu par id.
4. `WantedItemResponse(status=…)` reçoit le statut **résolu**.

**Interdit** : réimplémenter la règle (« si absorbed et saison connue alors … ») dans la
route. La route appelle le seam et rien d'autre. Si le seam ne convient pas tel quel, c'est
le seam qu'on amende — avec ses tests — pas une copie locale.

**Non touché** : la clause `WHERE` (l.483-491) et le `COUNT(*)` (l.491). Le paramètre
`status=` continue de filtrer sur le statut stocké — écart assumé et consigné au DESIGN §3.4.

## 01.3 — Docstring et OpenAPI

La docstring de `get_wanted` décrit un comportement qui change : elle doit dire que le statut
servi est le statut **résolu** (une ligne absorbée porte celui de sa saison), et que le
paramètre `status` filtre, lui, sur le statut **stocké**. Ne pas taire l'asymétrie : elle est
le prix d'une décision, elle se documente.

Puis `make openapi` et **commiter les deux fichiers** générés : la CI échoue sur la dérive
du schéma dès qu'une signature ou une docstring de route bouge.

## Critères de sortie

- Les 6 tests passent ; le test 1 a été vu rouge avant le correctif.
- `make check` vert sur le périmètre backend.
- OpenAPI régénéré et commité, `git status` propre.
