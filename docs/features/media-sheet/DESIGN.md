# [#388] media-sheet — fiche détail média, réutilisable et adressable

**Date**: 2026-08-04 · **Codename**: `media-sheet` · **Type**: feat · **Bump**: minor (0.77.4 → 0.78.0)

## 1. Problème

Un média affiché dans l'interface (poster + nom) est aujourd'hui un cul-de-sac : on ne peut
pas savoir **de quoi il s'agit**. L'opérateur veut pouvoir cliquer n'importe où et obtenir
une fiche — poster, titre, année, synopsis, réalisateur, bande-annonce ; et pour une série
le nombre de saisons, les épisodes par saison, et le statut (terminée / en cours / annulée).

Ce n'est pas une page de plus : **c'est une règle de constitution**. Toute surface qui
affiche un média sans permettre d'ouvrir sa fiche devient non conforme.

### État des lieux (exploration datée 2026-08-03, citée dans le ticket)

- `media_item` ne stocke **ni synopsis, ni réalisateur, ni genres, ni statut de série**.
- Le modèle pivot `MediaDetails` porte overview/genres/saisons mais **ni réalisateur ni
  statut** — explicitement abandonnés par les convertisseurs (`_tvdb_convert.py` note
  « MediaDetails does not preserve TVDB status.name ») ; le NFO les écrit donc vides.
- **Les bandes-annonces existent déjà** (`trailers_state.json` : URL YouTube + chemin local)
  mais aucun code web ne les lit.
- **Aucune route paramétrée n'existe** ; le repo utilise partout query-param + tiroir.
- **Aucun endpoint ne lit `media_item`** — la page « Médias » montre le staging.

## 2. Décisions (arbitrages opérateur pris le 2026-08-04)

| #   | Décision                                                                                                                                                                                | Raison                                                                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **Données via appel provider live, mises en cache**                                                                                                                                     | Seule source qui marche pour un média **non possédé** (un résultat de recherche n'existe dans aucune base). Impose d'étendre `MediaDetails`.                                 |
| D2  | **Adressage par ID provider** : `/media/:provider/:id` (ex. `/media/tmdb/27205`)                                                                                                        | Seul dénominateur commun aux surfaces ; stable, partageable, fonctionne hors médiathèque. Rupture assumée de la convention query-param (l'opérateur demande une vraie page). |
| D3  | **Posters via l'URL du provider** en v1                                                                                                                                                 | Zéro code serveur, marche disque démonté et pour les médias non possédés. Une route locale reste possible plus tard.                                                         |
| D4  | `MediaDetails` gagne `director`, `series_status`, `episode_count`, `trailer_url` — **champs optionnels** (`None` = inconnu), jamais inventés                                            | Un champ absent doit se voir comme absent, pas comme vide (§8 « rien en silence »).                                                                                          |
| D5  | **La fiche croise la médiathèque** : elle dit si le média est possédé, et pour une série ce qui l'est par saison — c'est ce qui la rend utile plutôt que décorative                     | §9 « la complétude exécutable est LA définition d'acquis ».                                                                                                                  |
| D6  | **Cache court côté serveur** (TTL, en mémoire process) sur `(provider, id)` — pas de nouvelle table                                                                                     | Le quota provider et le circuit-breaker existent déjà ; une fiche ré-ouverte ne doit pas re-payer l'appel.                                                                   |
| D7  | Un **composant React autonome** (`MediaSheet`) + une page fine qui lit la route et le monte                                                                                             | « autonome et réutilisable » : la page n'est qu'un hôte ; le composant pourra plus tard être monté en tiroir ailleurs sans réécriture.                                       |
| D8  | Le lien depuis les surfaces passe par **un seul helper** (`mediaSheetHref(ref)`)                                                                                                        | Une règle de constitution appliquée à 11 endroits doit avoir un seul point de vérité, sinon elle dérive.                                                                     |
| D9  | **Dégradation honnête** : provider injoignable → la fiche affiche ce qu'elle sait (titre/année locaux) + une raison en français, jamais un écran vide ni un faux « aucune information » | §8 / NE-DOIT-PAS-4.                                                                                                                                                          |
| D10 | La bande-annonce affiche le **lien YouTube** s'il est connu ; le fichier local n'est pas streamé en v1                                                                                  | Le streaming demande une route dédiée + le disque monté — hors périmètre v1, noté en §7.                                                                                     |

## 3. Composants

### 3.1 Backend — extension du modèle pivot

`api/metadata/_base.py` : `MediaDetails` gagne quatre champs optionnels
(`director: str | None`, `series_status: str | None`, `episode_count: int | None`,
`trailer_url: str | None`). Dataclass **frozen** — ajout en fin, valeurs par défaut `None`,
donc aucun appelant existant ne casse.

Parseurs :

- **TMDB** (`_tmdb_parsers.py`) : `append_to_response` gagne `credits` (films) /
  `aggregate_credits` (TV) ; `director` = premier `crew` avec `job == "Director"` (films) ou
  `created_by` (TV) ; `series_status` = champ `status` ; `episode_count` =
  `number_of_episodes` ; `trailer_url` = première vidéo `type == "Trailer"` et
  `site == "YouTube"`.
- **TVDB** (`_tvdb_parsers.py`) : `series_status` = `status.name` (celui que le shim jetait) ;
  `director` depuis les `characters`/`people` de type Director quand disponible.
- Les champs restent `None` quand le provider ne les donne pas — **jamais de chaîne vide**.

### 3.2 Backend — endpoint

`GET /api/media/{provider}/{provider_id}` → `MediaSheetResponse` (Pydantic, sous
`guarded_api`, lecture seule donc `def` simple, pas de `pipeline.lock`).

Contenu : identité (provider, id, titre, année, poster_url), `overview`, `director`,
`genres`, `trailer_url`, `series` (statut, nb saisons, saisons[numéro, nb épisodes]),
`ownership` (possédé oui/non ; pour une série : possédés/diffusés par saison), et
`degraded_reason: str | None` quand le provider n'a pas répondu.

Le croisement médiathèque réutilise l'`ownership` existant (`indexer/ownership.py`), déjà
utilisé par l'acquisition — pas de nouvelle logique de possession.

Cache : petit TTL en mémoire (`(provider, id) → (payload, expiry)`), taille bornée.

⇒ Toute modification de route impose `make openapi` + les fichiers régénérés commités.

### 3.3 Frontend — composant + page + helper

- `components/media/MediaSheet.tsx` — **autonome** : reçoit `{provider, providerId}`, fait sa
  propre requête, gère ses états chargement / erreur / dégradé (conventions DS existantes :
  `ds/ErrorState`, Skeletons).
- `pages/MediaSheetPage.tsx` — lit les params de route et monte le composant. Rien d'autre.
- `router.tsx` — `{ path: "media/:provider/:providerId", element: <MediaSheetPage /> }`,
  **plus son test miroir** dans `router.test.tsx` (toute route ajoutée y est testée).
- `lib/media-href.ts` — `mediaSheetHref({provider, providerId})`, **seul** constructeur de
  lien, testé.

### 3.4 Frontend — câblage des surfaces

Ordre de priorité (les trois premières ont l'identifiant sous la main, sans requête) :

1. Acquisition › recherche/ajout (`MediaSearchAdd`) — `provider` + `provider_id`.
2. Acquisition › Suivis (`FollowedPanel`) — `media_ref`.
3. Médias › Décisions / candidats (`CandidateCard`) — `provider` + `provider_id`.
4. Médias › Bibliothèque (`StagingLibrary`) — `provider_ids` du NFO **quand présents** ; le
   lien n'apparaît pas si le média n'est pas identifié (on ne fabrique pas un lien mort).

`MediaCard` du DS a déjà une prop `onOpen` qui rend la zone poster+titre cliquable — le
câblage passe par elle, pas par un nouveau motif.

## 4. Constitution — nouveau § CONTRAIGNANT

Ajout dans `docs/reference/product-intent.md` :

> **§11 — Tout média est consultable.** Un média affiché dans l'interface (poster, titre,
> ligne de liste, résultat de recherche) **doit** ouvrir sa fiche détail. Une fiche dit ce
> qu'est le média (titre, année, synopsis, réalisateur, bande-annonce ; pour une série :
> saisons, épisodes, statut) **et où il en est** chez nous (possédé ou non, complétude par
> saison). Une vignette qui ne mène nulle part est un cul-de-sac : l'opérateur voit un objet
> sans pouvoir savoir ce que c'est.
>
> **Exception unique** : un média **non identifié** (aucun ID provider connu) n'a pas de
> fiche — la surface doit alors mener à la **résolution**, jamais à un lien mort.

Plus la ligne correspondante dans « Ce que l'interface DOIT faire » (DOIT-11).

## 5. Tests

- **Parseurs** : golden fixtures TMDB/TVDB → `director`, `series_status`, `episode_count`,
  `trailer_url` extraits ; et `None` (jamais `""`) quand le provider ne les fournit pas.
- **Endpoint** : forme typée ; média possédé vs non possédé ; provider en erreur →
  `degraded_reason` rempli et la fiche reste servie (jamais 500) ; cache : deux appels
  successifs = **un** appel provider.
- **Helper de lien** : `mediaSheetHref` — forme exacte de l'URL, encodage des ids.
- **Route** : test miroir dans `router.test.tsx` (rendu de la route, et 404 propre sur
  provider inconnu).
- **Composant** : états chargement / erreur / dégradé ; série vs film ; absence de
  réalisateur affichée comme inconnue et non comme vide.
- **Constitution** : un test qui **échoue si une surface listée affiche un média sans lien**
  — c'est ce qui empêche le § de se périmer (les surfaces sont énumérées explicitement).
- **Mobile** : preuve 390 px sur la fiche avant clôture (règle mobile-truth).

## 6. Phases proposées

1. **Modèle + parseurs** : `MediaDetails` × 4 champs, TMDB + TVDB, tests golden.
2. **Endpoint + cache + croisement médiathèque** : route typée, `make openapi`, tests.
3. **Composant + page + route + helper** : `MediaSheet`, `MediaSheetPage`, `mediaSheetHref`,
   test miroir de route, tests de composant.
4. **Câblage des surfaces + § constitution + ACCEPTANCE + gate complet** : les 4 surfaces,
   le nouveau §11 dans `product-intent.md`, le test anti-dérive, preuve mobile.

## 7. Conformité §11 — écarts connus (2026-08-04)

Deux surfaces affichent des médias identifiés sans chemin vers leur fiche. Les câbler
demande une modification du modèle backend — hors périmètre de cette PR.

| Surface              | Composant source                     | Champ manquant                                      | Ce qui fermerait l'écart                                                                   |
| -------------------- | ------------------------------------ | --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **ObligationsPanel** | `ObligationItem` (openapi.json)      | Aucun `provider_id` (ni `tvdb_id`, ni `tmdb_id`)    | Ajouter `media_ref: {tvdb_id, tmdb_id, imdb_id}` au read-model `ObligationItem` backend    |
| **RecentResolutions** | `DecisionListItem` (openapi.json)   | Aucun `provider_id` (ni `tvdb_id`, ni `tmdb_id`)    | Ajouter `media_ref` ou un `provider_id` résolu au read-model `DecisionListItem` backend    |

`ObligationItem` porte uniquement `['accumulated_seed_time_s','added_at','breached_at',
'dispatched_path','hnr_count','info_hash','min_ratio','min_seed_time_s','observed_ratio',
'released_at','satisfied_at','source_tracker','title']` — **aucun identifiant provider**.

`DecisionListItem` porte `['candidates_count','created_at','extracted_title','extracted_year',
'id','media_kind','staging_path','status','trigger']` — **aucun identifiant provider**.

Aucun hack côté frontend (lookup par titre, devinette) n'est acceptable (§8). Ces deux
surfaces restent **non câblées** jusqu'à ce que le backend expose les identifiants.

## 8. Hors périmètre (explicite)

- Streaming du fichier de bande-annonce local (route dédiée + disque monté) — le lien
  YouTube suffit en v1.
- Route de service des posters locaux (D3 : URL provider en v1).
- Persistance en base du synopsis/réalisateur/statut (D1 : appel live + cache).
- Surface de navigation de la médiathèque permanente (« toutes mes séries ») — la fiche est
  atteignable par lien, pas par un nouvel index.
- Épisodes détaillés (titres/dates/synopsis par épisode) : la v1 donne le **compte** par
  saison, pas la liste.
