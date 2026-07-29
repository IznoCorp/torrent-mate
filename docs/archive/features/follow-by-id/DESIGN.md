# DESIGN — follow-by-id : suivre par ID IMDB et TMDB (en plus de TVDB)

**Codename** : `follow-by-id` · **Type** : `feat` · **Bump** : minor (0.61.0 → 0.62.0)
**Ticket** : #336 · **Merge** : auto

## Constitution produit (CONTRAIGNANT)

Sert `docs/reference/product-intent.md` **§2 (véridicité)** : une série suivie **détecte
réellement** ses épisodes — un suivi ne doit jamais être silencieusement inerte. Le formulaire
« Ajouter par ID » ne proposait que TVDB ; l'opérateur veut aussi IMDB et TMDB. Mais comme la
détection d'épisodes (`poll_known`) **saute toute série sans `tvdb_id`**
(`airing.py:131` → `skip_no_tvdb_id`), un simple ajout par TMDB/IMDB créerait un suivi qui ne
télécharge jamais rien : **demi-fonctionnalité silencieuse interdite** (§méthode).

## Problème (terrain vérifié 2026-07-29)

- `CreateFollowRequest` accepte déjà `tvdb_id` / `tmdb_id` / `imdb_id` (validateur ≥ 1), et
  `_resolve_follow_metadata` remplit poster/titre/année par n'importe quel ID.
- **MAIS** `_resolve_follow_metadata` ne rétro-remplit PAS le `tvdb_id` croisé, et
  `poll_known` saute les séries sans `tvdb_id`. Une **série** suivie par TMDB/IMDB seul est donc
  inerte pour la détection.
- Le formulaire `FollowedPanel.tsx` (« Ajouter par ID TVDB ») n'a qu'un champ TVDB (int).

## Approche

### Backend — résolution TVDB au moment du suivi (séries)

Au `create_follow`, pour une **série** (`kind='show'`) dont le `media_ref` n'a pas de `tvdb_id`,
résoudre le TVDB via le registry, avant l'insertion, et le stocker dans `media_ref` :

- **TMDB → TVDB** : `tmdb_client.get_tv(tmdb_id).external_ids["tvdb"]` (déjà peuplé par le parser
  TMDB, `_tmdb_parsers.py` — `external_ids.tvdb_id`).
- **IMDB → TVDB** : `tmdb_client.find_by_imdb(imdb_id)` (**nouvelle** méthode fine :
  `GET /find/{imdb}?external_source=imdb_id` → `tv_results[0].id` = tmdb) → `get_tv(tmdb)` →
  `external_ids["tvdb"]`.

Séparation stricte multi-provider respectée : **TVDB reste le primaire de scrape/détection** ;
TMDB/IMDB ne servent qu'à le résoudre (info+fallback). Pas de cross-contamination.

**Fail-soft NON silencieux** (§méthode) : si le TVDB d'une série ne peut être résolu, le suivi
est **quand même créé** (l'opérateur ne perd pas son geste), mais la réponse porte
`tvdb_unresolved: true` et le front **prévient** (« Série ajoutée, mais l'ID TVDB n'a pas pu être
résolu — la détection d'épisodes est indisponible tant qu'un ID TVDB n'est pas fourni. »).
Jamais un suivi inerte muet.

**Films** (`kind='movie'`) : le cycle §5 (une ligne wanted film, grab par titre) ne dépend PAS
du TVDB → aucun changement, un film par TMDB/IMDB fonctionne tel quel.

Worst-case borné : la résolution ajoute ≤ 2 appels provider synchrones (find + get_tv), sous le
même seam `scoped_provider_clients` (`max_attempts=1`) que l'enrichissement métadonnées.

### Frontend — sélecteur de provider dans le formulaire « Ajouter par ID »

`FollowedPanel.tsx` : le champ « ID TVDB » devient un **sélecteur de provider** (TVDB / TMDB /
IMDB) + un champ ID typé :

- TVDB / TMDB : entier (`ex: 255968`).
- IMDB : chaîne `tt\d+` (`ex: tt0137523`), validée côté client.

Le hook `useFollowedPanel` (`handleAdd`) envoie le bon champ (`tvdb_id`/`tmdb_id`/`imdb_id`) selon
le provider choisi. L'accordéon est renommé « Ajouter par ID » ; le titre optionnel reste.

## Non-buts

- Pas de recherche plein-texte par ID (la recherche titre existe déjà, `MediaSearchAdd`).
- Pas de résolution TVDB pour les **films** (inutile — cycle titre).
- Pas de re-résolution rétroactive des suivis TMDB/IMDB existants inertes (aucun n'existe
  aujourd'hui ; hors périmètre, mentionné comme évolution possible).

## ACCEPTANCE (commandes exécutables)

- **ACC-01** — `tmdb_client.find_by_imdb("tt...")` (nouvelle méthode) : golden fixture →
  `tv_results` mappés, renvoie le tmdb id. `pytest tests/api/metadata/test_tmdb_find.py` → passed.
- **ACC-02** — résolution série : une série suivie par `tmdb_id` seul se voit rétro-remplir son
  `tvdb_id` (via get_tv external_ids) avant insertion ; par `imdb_id` seul via find→get_tv.
  `pytest tests/web/acquisition/test_follow_resolve_tvdb.py` → passed (mock provider).
- **ACC-03** — fail-soft non silencieux : série sans TVDB résoluble ⇒ suivi créé +
  `tvdb_unresolved=true` dans la réponse (pas d'exception, pas de suivi muet).
- **ACC-04** — film par `tmdb_id`/`imdb_id` : suivi créé sans résolution TVDB (aucun appel de
  résolution), cycle film intact.
- **ACC-05** — front : le sélecteur TVDB/TMDB/IMDB envoie le bon champ ; IMDB validé `tt\d+`.
  `vitest` FollowedPanel. Preuve Chrome 390 px : les 3 providers sélectionnables, ajout OK.
- **ACC-06** — `make check` vert ; `make openapi` régénéré (`tvdb_unresolved` +
  `find_by_imdb` n'affecte pas le contrat public sauf le champ réponse) et commité.

## Phases (indicatif — `/implement:plan` fait foi)

1. **Backend résolution** — `tmdb.find_by_imdb` + `resolve_series_tvdb()` + intégration
   `create_follow` + `tvdb_unresolved` sur la réponse + tests (ACC-01→04, ACC-06 openapi).
2. **Frontend sélecteur** — `FollowedPanel.tsx` provider selector + `useFollowedPanel` +
   validation IMDB + toast fail-soft + tests (ACC-05).
3. **ACC + preuve 390 px + gate** — `make check`, `make openapi`, preuve Chrome, real-data.
