# TVDB API — Documentation de référence

> TheTVDB API v4 — référence complète pour le pipeline PersonalScraper (scrape step).
>
> Dernière mise à jour : 2026-04-10

---

## Table des matières

- [Authentification](#authentification)
- [URLs de base](#urls-de-base)
- [Rate limiting](#rate-limiting)
- [Format de réponse](#format-de-réponse)
- [Pagination](#pagination)
- [Langues et traductions](#langues-et-traductions)
- [Types de saisons](#types-de-saisons)
- [Endpoints — Recherche](#endpoints--recherche)
  - [Recherche globale](#recherche-globale)
  - [Recherche par ID externe](#recherche-par-id-externe)
- [Endpoints — Séries](#endpoints--séries)
  - [Série de base](#série-de-base)
  - [Série étendue](#série-étendue)
  - [Épisodes par saison](#épisodes-par-saison)
  - [Épisodes traduits par saison](#épisodes-traduits-par-saison)
  - [Artworks d'une série](#artworks-dune-série)
  - [Traduction d'une série](#traduction-dune-série)
  - [Filtrer les séries](#filtrer-les-séries)
  - [Statuts des séries](#statuts-des-séries)
- [Endpoints — Saisons](#endpoints--saisons)
  - [Saison de base](#saison-de-base)
  - [Saison étendue](#saison-étendue)
  - [Traduction d'une saison](#traduction-dune-saison)
  - [Types de saisons (référence)](#types-de-saisons-référence)
- [Endpoints — Épisodes](#endpoints--épisodes)
  - [Épisode de base](#épisode-de-base)
  - [Épisode étendu](#épisode-étendu)
  - [Traduction d'un épisode](#traduction-dun-épisode)
- [Endpoints — Films](#endpoints--films)
  - [Film de base](#film-de-base)
  - [Film étendu](#film-étendu)
  - [Filtrer les films](#filtrer-les-films)
- [Endpoints — Personnes](#endpoints--personnes)
- [Endpoints — Artworks](#endpoints--artworks)
  - [Artwork par ID](#artwork-par-id)
  - [Types d'artwork](#types-dartwork)
- [Endpoints — Utilitaires](#endpoints--utilitaires)
  - [Configuration API](#configuration-api)
  - [Source Types (IDs croisés)](#source-types-ids-croisés)
  - [Genres](#genres)
  - [Content Ratings](#content-ratings)
  - [Langues disponibles](#langues-disponibles)
  - [Pays disponibles](#pays-disponibles)
  - [Updates (changements)](#updates-changements)
- [Gestion des erreurs](#gestion-des-erreurs)
- [IDs croisés (IMDB, TMDB)](#ids-croisés-imdb-tmdb)
- [Stratégie d'appels optimale](#stratégie-dappels-optimale)
- [Résumé des schémas de réponse](#résumé-des-schémas-de-réponse)
- [Gotchas et notes importantes](#gotchas-et-notes-importantes)
- [Edge cases et vérifications](#edge-cases-et-vérifications-tests-live-2026-04-10)

---

## Authentification

### Mécanisme : JWT Bearer Token

Contrairement à TMDB (API key en query param), TVDB utilise un **token JWT** obtenu via un endpoint de login.

### Login

```
POST /login
```

**Corps de la requête** :

```json
{
  "apikey": "votre-clé-api",
  "pin": "pin-abonné"
}
```

| Champ    | Type   | Requis     | Description                                                              |
| -------- | ------ | ---------- | ------------------------------------------------------------------------ |
| `apikey` | string | **Oui**    | Clé API TVDB                                                             |
| `pin`    | string | Selon type | Requis pour clés "User Subscription", omettre pour "Negotiated Contract" |

> **Deux types de clés API** :
>
> - **Negotiated Contract** (gratuit, < $50k) : envoyer `{"apikey": "..."}` **sans le champ `pin`**. La clé actuelle du pipeline est de ce type.
> - **User Subscription** : chaque utilisateur doit s'abonner ($11.99/an) et fournir son PIN → `{"apikey": "...", "pin": "..."}`. Le PIN est dans Dashboard → Account → Subscription.
>
> Si l'API retourne `"pin required"`, la clé est de type User Subscription.

**Réponse succès** :

```json
{
  "status": "success",
  "data": {
    "token": "eyJhbGciOiJSUz..."
  }
}
```

**Réponses d'erreur login** (vérifié) :

```json
// PIN absent → HTTP 400
{"status": "failure", "message": "InvalidValueType: pin required", "data": null}

// PIN invalide → HTTP 401
{"status": "failure", "message": "InvalidAPIKey: pin invalid", "data": null}

// Clé API invalide → HTTP 401
{"status": "failure", "message": "InvalidAPIKey: apikey invalid", "data": null}
```

### Utilisation du token

Inclure dans **toutes** les requêtes suivantes :

```
Authorization: Bearer <token>
```

### Durée de validité

Le token est valide **1 mois**. Pas d'endpoint de refresh — re-authentifier via `/login` quand le token expire (HTTP 401).

### Clé API du pipeline

Définie dans `.env` à la racine du projet (fichier non versionné) :

```
TVDB_API_KEY=<votre-clé>
```

### Plans API

| Revenus société parente | Coût        | Type de clé         | PIN requis |
| ----------------------- | ----------- | ------------------- | ---------- |
| < $50k/an               | **Gratuit** | User-subscription   | Oui        |
| $50k - $250k/an         | $1,000/an   | Negotiated-contract | Non        |
| $250k - $1M/an          | $10,000/an  | Negotiated-contract | Non        |
| > $1M/an                | Sur devis   | Negotiated-contract | Non        |

> **Attribution obligatoire** : sauf exemption spécifique, afficher un lien vers TheTVDB.com.

---

## URLs de base

| Usage        | URL                                            |
| ------------ | ---------------------------------------------- |
| API v4       | `https://api4.thetvdb.com/v4`                  |
| Swagger UI   | `https://thetvdb.github.io/v4-api/`            |
| Swagger YAML | `https://thetvdb.github.io/v4-api/swagger.yml` |

**Version actuelle** : 4.7.10

**TLS minimum** : v1.2

---

## Rate limiting

TVDB **ne documente pas publiquement de limites de débit** spécifiques.

- Pas de seuils explicites dans la spec Swagger ni dans la documentation
- L'API génère des millions d'appels par jour pour l'ensemble des consommateurs
- Si un rate limit existe, HTTP **429** serait retourné (convention standard)

**Stratégie recommandée** :

- Implémenter un backoff préventif si HTTP 429 est reçu
- Utiliser l'endpoint `/updates` plutôt que de poll les records individuellement
- Cacher les données de référence (genres, artwork types, etc.)

---

## Format de réponse

Toutes les réponses suivent une enveloppe standardisée :

### Succès

```json
{
  "status": "success",
  "data": { ... }
}
```

### Succès avec pagination

```json
{
  "status": "success",
  "data": [ ... ],
  "links": {
    "prev": "https://...",
    "self": "https://...",
    "next": "https://...",
    "total_items": 12345,
    "page_size": 500
  }
}
```

### Erreur

```json
{
  "status": "failure",
  "message": "description de l'erreur"
}
```

---

## Pagination

- Le paramètre `page` est **indexé à partir de 0** (contrairement à TMDB qui commence à 1)
- La taille de page est fixée par l'API (non configurable côté client)
- L'objet `links` dans la réponse fournit la navigation (`prev`, `self`, `next`, `total_items`, `page_size`)
- L'endpoint `/search` utilise `offset` et `limit` au lieu de `page` (max 5 000 résultats)

---

## Langues et traductions

### ⚠️ Codes à 3 caractères

TVDB utilise des codes langue **à 3 caractères** (ISO 639-2/3), pas 2 comme TMDB :

| Langue   | TVDB  | TMDB    |
| -------- | ----- | ------- |
| Français | `fra` | `fr-FR` |
| Anglais  | `eng` | `en-US` |
| Espagnol | `spa` | `es-ES` |
| Allemand | `deu` | `de-DE` |
| Japonais | `jpn` | `ja-JP` |
| Italien  | `ita` | `it-IT` |

Les codes pays sont aussi à **3 caractères** : `usa`, `fra`, `jpn`, etc.

### Système de traduction

Chaque entité a deux tableaux indiquant les traductions disponibles :

- `nameTranslations` : langues avec un nom traduit
- `overviewTranslations` : langues avec un synopsis traduit

**Deux façons d'obtenir les traductions :**

1. **Endpoint dédié** : `GET /{entity}/{id}/translations/{language}`
   - Retourne le nom et synopsis traduits pour une langue spécifique

2. **Paramètre `meta`** : `GET /{entity}/{id}/extended?meta=translations`
   - Inclut toutes les traductions dans la réponse étendue

### Objet Translation

```json
{
  "language": "fra",
  "name": "Titre traduit",
  "overview": "Synopsis traduit...",
  "aliases": ["Alias 1"],
  "isAlias": false,
  "isPrimary": false,
  "tagline": "Tagline (films uniquement)"
}
```

---

## Types de saisons

TVDB supporte plusieurs systèmes d'ordonnancement des épisodes :

| Type        | Description                                      | Usage courant                    |
| ----------- | ------------------------------------------------ | -------------------------------- |
| `default`   | Ordre de diffusion (Aired Order)                 | **Standard — utiliser celui-ci** |
| `official`  | Ordre officiel                                   | Rarement différent               |
| `dvd`       | Ordre DVD                                        | Parfois différent                |
| `absolute`  | Numérotation absolue (toutes saisons confondues) | **Anime**                        |
| `alternate` | Ordre alternatif                                 | Cas spéciaux                     |
| `regional`  | Ordre régional                                   | Marchés spécifiques              |

Le type de saison est un paramètre **obligatoire** de l'endpoint d'épisodes : `/series/{id}/episodes/{season-type}`.

Pour le pipeline, utiliser `default` sauf cas spécial (anime → `absolute`).

---

## Endpoints — Recherche

### Recherche globale

```
GET /search
```

Recherche dans les séries, films, personnes et compagnies. Limite : **5 000 résultats**.

| Paramètre     | Type   | Requis | Description                                      |
| ------------- | ------ | ------ | ------------------------------------------------ |
| `query`       | string | Non\*  | Texte de recherche (inclut traductions et alias) |
| `q`           | string | Non    | Alias déprécié de `query`                        |
| `type`        | string | Non    | `movie`, `series`, `person`, `company`           |
| `year`        | number | Non    | Filtrer par année                                |
| `company`     | string | Non    | Nom de la société                                |
| `country`     | string | Non    | Code pays 3 caractères                           |
| `director`    | string | Non    | Nom du réalisateur                               |
| `language`    | string | Non    | Code langue 3 caractères                         |
| `primaryType` | string | Non    | Type de société (compagnies uniquement)          |
| `network`     | string | Non    | Nom du réseau (TV uniquement)                    |
| `remote_id`   | string | Non    | Recherche par ID IMDB ou EIDR                    |
| `offset`      | number | Non    | Décalage pour la pagination                      |
| `limit`       | number | Non    | Nombre de résultats max                          |

\*Au moins `query` ou `remote_id` doit être fourni.

**Réponse** :

```json
{
  "status": "success",
  "data": [
    {
      "objectID": "series-81189",
      "id": "81189",
      "tvdb_id": "81189",
      "type": "series",
      "name": "Breaking Bad",
      "slug": "breaking-bad",
      "status": "Ended",
      "year": "2008",
      "country": "usa",
      "network": "AMC",
      "primary_language": "eng",
      "overview": "...",
      "image_url": "https://artworks.thetvdb.com/...",
      "poster": "https://artworks.thetvdb.com/...",
      "thumbnail": "https://artworks.thetvdb.com/...",
      "first_air_time": "2008-01-20",
      "is_official": true,
      "remote_ids": [
        { "id": "tt0903747", "type": 2, "sourceName": "IMDB" }
      ],
      "aliases": ["..."],
      "genres": ["Drama", "Thriller"],
      "studios": ["Sony Pictures Television"],
      "translations": { "fra": "Breaking Bad", "eng": "Breaking Bad" },
      "overviews": { "fra": "Synopsis FR...", "eng": "Synopsis EN..." }
    }
  ],
  "links": { ... }
}
```

**Champs clés pour le pipeline** : `tvdb_id`, `type`, `name`, `year`, `remote_ids` (pour IMDB), `translations`, `overviews`.

---

### Recherche par ID externe

```
GET /search/remoteid/{remoteId}
```

Trouve une entité TVDB à partir d'un ID IMDB ou EIDR.

| Paramètre  | Emplacement | Type   | Requis  | Description                  |
| ---------- | ----------- | ------ | ------- | ---------------------------- |
| `remoteId` | Path        | string | **Oui** | ID externe (ex: `tt0903747`) |

**Réponse** : tableau de résultats contenant les entités correspondantes (série, film, personne, épisode).

> **Usage pipeline** : cross-référencer IMDB → TVDB en un seul appel.

---

## Endpoints — Séries

### Série de base

```
GET /series/{id}
```

| Paramètre | Emplacement | Type   | Requis  | Description         |
| --------- | ----------- | ------ | ------- | ------------------- |
| `id`      | Path        | number | **Oui** | ID TVDB de la série |

**Réponse** : `data` = `SeriesBaseRecord`

```json
{
  "status": "success",
  "data": {
    "id": 81189,
    "name": "Breaking Bad",
    "slug": "breaking-bad",
    "image": "https://artworks.thetvdb.com/banners/...",
    "firstAired": "2008-01-20",
    "lastAired": "2013-09-29",
    "nextAired": "",
    "score": 2538828,
    "status": { "id": 2, "name": "Ended" },
    "originalCountry": "usa",
    "originalLanguage": "eng",
    "year": "2008",
    "nameTranslations": ["eng", "fra", "deu", "spa", ...],
    "overviewTranslations": ["eng", "fra", "deu", "spa", ...],
    "aliases": [
      { "language": "eng", "name": "Breaking Bad" }
    ],
    "lastUpdated": "2024-03-15 12:00:00",
    "isOrderRandomized": false
  }
}
```

---

### Série étendue

```
GET /series/{id}/extended
```

| Paramètre | Emplacement | Type    | Requis  | Description                                                           |
| --------- | ----------- | ------- | ------- | --------------------------------------------------------------------- |
| `id`      | Path        | number  | **Oui** | ID TVDB                                                               |
| `meta`    | Query       | string  | Non     | `translations` (inclure traductions) ou `episodes` (inclure épisodes) |
| `short`   | Query       | boolean | Non     | `true` exclut characters, artworks, trailers                          |

**Réponse** : `data` = `SeriesExtendedRecord`

Inclut tous les champs de base **plus** :

```json
{
  "data": {
    "id": 81189,
    "name": "Breaking Bad",
    /* ... champs de base ... */

    "genres": [{ "id": 5, "name": "Drama", "slug": "drama" }],

    "seasons": [
      {
        "id": 27009,
        "seriesId": 81189,
        "number": 0,
        "name": "Specials",
        "image": "...",
        "year": "2009"
      },
      {
        "id": 27010,
        "seriesId": 81189,
        "number": 1,
        "name": "Season 1",
        "image": "...",
        "year": "2008"
      }
    ],

    "artworks": [
      {
        "id": 12345,
        "image": "https://artworks.thetvdb.com/banners/...",
        "thumbnail": "https://artworks.thetvdb.com/banners/..._t.jpg",
        "type": 2,
        "language": "eng",
        "score": 100150,
        "width": 680,
        "height": 1000,
        "includesText": true
      }
    ],

    "characters": [
      {
        "id": 67890,
        "name": "Walter White",
        "peopleId": 253341,
        "personName": "Bryan Cranston",
        "personImgURL": "...",
        "image": "...",
        "isFeatured": true,
        "type": 3,
        "sort": 0,
        "seriesId": 81189,
        "episodeId": null,
        "movieId": null
      }
    ],

    "companies": {
      /* companies grouped by type */
    },

    "contentRatings": [
      {
        "id": 245,
        "name": "TV-14",
        "country": "usa",
        "contentType": "series"
      }
    ],

    "remoteIds": [
      { "id": "tt0903747", "type": 2, "sourceName": "IMDB" },
      { "id": "18164", "type": 12, "sourceName": "TheMovieDB.com" }
    ],

    "trailers": [
      {
        "id": 1,
        "name": "Trailer",
        "url": "https://youtube.com/...",
        "language": "eng",
        "runtime": 120
      }
    ],

    "lists": [
      /* ... */
    ],
    "awards": [
      /* ... */
    ],
    "tagOptions": [
      /* ... */
    ]
  }
}
```

**Champs clés pour le pipeline** : `id`, `name`, `genres`, `seasons[]`, `remoteIds[]` (pour IMDB/TMDB), `artworks[]`, `characters[]`, `contentRatings[]`, `firstAired`, `status`.

---

### Épisodes par saison

```
GET /series/{id}/episodes/{season-type}
```

**⚠️ Endpoint clé** pour récupérer la liste des épisodes d'une série.

| Paramètre       | Emplacement | Type   | Requis  | Défaut | Description                                                       |
| --------------- | ----------- | ------ | ------- | ------ | ----------------------------------------------------------------- |
| `id`            | Path        | number | **Oui** | —      | ID TVDB de la série                                               |
| `season-type`   | Path        | string | **Oui** | —      | `default`, `official`, `dvd`, `absolute`, `alternate`, `regional` |
| `page`          | Query       | int    | **Oui** | `0`    | Numéro de page (indexé à 0)                                       |
| `season`        | Query       | int    | Non     | `0`    | Filtrer par numéro de saison                                      |
| `episodeNumber` | Query       | int    | Non     | `0`    | Filtrer par numéro d'épisode (requiert `season`)                  |
| `airDate`       | Query       | string | Non     | —      | Filtrer par date de diffusion (`yyyy-mm-dd`)                      |

**Réponse** :

```json
{
  "status": "success",
  "data": {
    "series": { /* SeriesBaseRecord */ },
    "episodes": [
      {
        "id": 349232,
        "seriesId": 81189,
        "name": "Pilot",
        "number": 1,
        "seasonNumber": 1,
        "seasonName": "Season 1",
        "absoluteNumber": 1,
        "aired": "2008-01-20",
        "runtime": 58,
        "image": "https://artworks.thetvdb.com/...",
        "imageType": 12,
        "overview": "High school chemistry teacher...",
        "finaleType": null,
        "isMovie": 0,
        "linkedMovie": null,
        "lastUpdated": "2024-01-15 10:00:00",
        "nameTranslations": ["eng", "fra", ...],
        "overviewTranslations": ["eng", "fra", ...],
        "year": "2008"
      }
    ]
  }
}
```

**Filtrer par saison** : `GET /series/81189/episodes/default?season=1` retourne uniquement les épisodes de la saison 1.

**⚠️ Attention** : `episodeNumber` ne peut pas être utilisé sans `season`.

**Pagination** : la réponse peut être paginée si la série a beaucoup d'épisodes. Utiliser `page=0`, `page=1`, etc.

---

### Épisodes traduits par saison

```
GET /series/{id}/episodes/{season-type}/{lang}
```

| Paramètre     | Emplacement | Type   | Requis  | Description                     |
| ------------- | ----------- | ------ | ------- | ------------------------------- |
| `id`          | Path        | number | **Oui** | ID TVDB                         |
| `season-type` | Path        | string | **Oui** | Type de saison                  |
| `lang`        | Path        | string | **Oui** | Code langue 3 chars (ex: `fra`) |
| `page`        | Query       | int    | **Oui** | Page (indexé à 0)               |

**Réponse** : épisodes avec noms et synopsis traduits dans la langue demandée.

---

### Artworks d'une série

```
GET /series/{id}/artworks
```

| Paramètre | Emplacement | Type   | Requis  | Description                              |
| --------- | ----------- | ------ | ------- | ---------------------------------------- |
| `id`      | Path        | number | **Oui** | ID TVDB                                  |
| `lang`    | Query       | string | Non     | Filtrer par langue (ex: `eng`, `fra`)    |
| `type`    | Query       | int    | Non     | Filtrer par type d'artwork (ex: `1,2,3`) |

**Réponse** : `data` = `SeriesExtendedRecord` avec artworks filtrés.

> **Astuce** : utiliser `type` pour ne récupérer que les posters ou que les fanarts (voir [Types d'artwork](#types-dartwork)).

---

### Traduction d'une série

```
GET /series/{id}/translations/{language}
```

| Paramètre  | Emplacement | Type   | Requis  | Description                 |
| ---------- | ----------- | ------ | ------- | --------------------------- |
| `id`       | Path        | number | **Oui** | ID TVDB                     |
| `language` | Path        | string | **Oui** | Code langue 3 chars (`fra`) |

**Réponse** : `data` = `Translation` (nom et synopsis traduits).

---

### Filtrer les séries

```
GET /series/filter
```

| Paramètre       | Type   | Requis  | Description                                |
| --------------- | ------ | ------- | ------------------------------------------ |
| `country`       | string | **Oui** | Code pays 3 chars (ex: `usa`)              |
| `lang`          | string | **Oui** | Code langue 3 chars (ex: `eng`)            |
| `company`       | number | Non     | ID de la société de production             |
| `contentRating` | number | Non     | ID du classement de contenu                |
| `genre`         | number | Non     | ID de genre (1-36)                         |
| `sort`          | string | Non     | `score`, `firstAired`, `lastAired`, `name` |
| `sortType`      | string | Non     | `asc`, `desc`                              |
| `status`        | number | Non     | 1, 2 ou 3                                  |
| `year`          | number | Non     | Année de sortie                            |

> **⚠️ `country` et `lang` sont obligatoires.**

---

### Statuts des séries

```
GET /series/statuses
```

Retourne les statuts possibles. Pas de paramètres.

---

## Endpoints — Saisons

### Saison de base

```
GET /seasons/{id}
```

| Paramètre | Type   | Requis  | Description          |
| --------- | ------ | ------- | -------------------- |
| `id`      | number | **Oui** | ID TVDB de la saison |

**Réponse** : `data` = `SeasonBaseRecord`

```json
{
  "id": 27010,
  "seriesId": 81189,
  "number": 1,
  "name": "Season 1",
  "image": "https://artworks.thetvdb.com/...",
  "imageType": 7,
  "year": "2008",
  "lastUpdated": "...",
  "type": { "id": 1, "name": "Aired Order", "type": "official" },
  "nameTranslations": ["eng", "fra", ...],
  "overviewTranslations": ["eng", "fra", ...]
}
```

---

### Saison étendue

```
GET /seasons/{id}/extended
```

Inclut les champs de base **plus** :

| Champ supplémentaire | Type                | Description                    |
| -------------------- | ------------------- | ------------------------------ |
| `artwork`            | ArtworkBaseRecord[] | Artworks de la saison          |
| `episodes`           | EpisodeBaseRecord[] | Tous les épisodes de la saison |
| `trailers`           | Trailer[]           | Bandes-annonces                |
| `translations`       | Translation[]       | Traductions complètes          |
| `tagOptions`         | TagOption[]         | Métadonnées                    |

> **Astuce pipeline** : cet endpoint donne tous les épisodes + artworks d'une saison en un seul appel.

---

### Traduction d'une saison

```
GET /seasons/{id}/translations/{language}
```

---

### Types de saisons (référence)

```
GET /seasons/types
```

Retourne la liste des types de saisons disponibles (voir [Types de saisons](#types-de-saisons)).

---

## Endpoints — Épisodes

### Épisode de base

```
GET /episodes/{id}
```

| Paramètre | Type   | Requis  | Description          |
| --------- | ------ | ------- | -------------------- |
| `id`      | number | **Oui** | ID TVDB de l'épisode |

**Réponse** : `data` = `EpisodeBaseRecord`

```json
{
  "id": 349232,
  "seriesId": 81189,
  "name": "Pilot",
  "number": 1,
  "seasonNumber": 1,
  "seasonName": "Season 1",
  "absoluteNumber": 1,
  "aired": "2008-01-20",
  "runtime": 58,
  "image": "https://artworks.thetvdb.com/...",
  "imageType": 12,
  "overview": "High school chemistry teacher...",
  "finaleType": null,
  "isMovie": 0,
  "linkedMovie": null,
  "lastUpdated": "2024-01-15 10:00:00",
  "nameTranslations": ["eng", "fra", ...],
  "overviewTranslations": ["eng", "fra", ...],
  "year": "2008",
  "airsAfterSeason": null,
  "airsBeforeEpisode": null,
  "airsBeforeSeason": null
}
```

**Champs importants pour le pipeline** : `name`, `number`, `seasonNumber`, `aired`, `runtime`, `overview`, `image`.

**Champ `finaleType`** : `null`, `"season"`, `"midseason"`, ou `"series"`.

**Champs `airsAfter/Before`** : utilisés pour positionner les épisodes spéciaux relatifs aux saisons.

---

### Épisode étendu

```
GET /episodes/{id}/extended
```

| Paramètre | Emplacement | Type   | Requis  | Description                             |
| --------- | ----------- | ------ | ------- | --------------------------------------- |
| `id`      | Path        | number | **Oui** | ID TVDB                                 |
| `meta`    | Query       | string | Non     | `translations` pour inclure traductions |

Ajoute aux champs de base :

| Champ supplémentaire | Type                | Description                          |
| -------------------- | ------------------- | ------------------------------------ |
| `characters`         | Character[]         | Cast et personnages                  |
| `companies`          | Company[]           | Sociétés de production               |
| `contentRatings`     | ContentRating[]     | Classifications                      |
| `networks`           | Company[]           | Réseaux de diffusion                 |
| `remoteIds`          | RemoteID[]          | IDs externes (IMDB, TMDB)            |
| `studios`            | Company[]           | Studios                              |
| `productionCode`     | string              | Code de production                   |
| `awards`             | AwardBaseRecord[]   | Prix                                 |
| `nominations`        | AwardNominee[]      | Nominations                          |
| `trailers`           | Trailer[]           | Bandes-annonces                      |
| `translations`       | TranslationExtended | Traductions (si `meta=translations`) |
| `tagOptions`         | TagOption[]         | Métadonnées                          |

---

### Traduction d'un épisode

```
GET /episodes/{id}/translations/{language}
```

| Paramètre  | Type   | Requis  | Description                 |
| ---------- | ------ | ------- | --------------------------- |
| `id`       | number | **Oui** | ID TVDB de l'épisode        |
| `language` | string | **Oui** | Code langue 3 chars (`fra`) |

**Réponse** : `data` = `Translation` (nom et synopsis traduits de l'épisode).

---

## Endpoints — Films

TVDB a aussi une base de données de films (moins complète que TMDB pour les films).

### Film de base

```
GET /movies/{id}
```

**Réponse** : `data` = `MovieBaseRecord`

```json
{
  "id": 12345,
  "name": "Movie Title",
  "slug": "movie-title",
  "image": "https://artworks.thetvdb.com/...",
  "year": "2024",
  "score": 5000,
  "runtime": 120,
  "status": { "id": 1, "name": "Released" },
  "aliases": [],
  "nameTranslations": ["eng", "fra"],
  "overviewTranslations": ["eng", "fra"],
  "lastUpdated": "..."
}
```

---

### Film étendu

```
GET /movies/{id}/extended
```

| Paramètre | Type    | Requis | Description                                  |
| --------- | ------- | ------ | -------------------------------------------- |
| `meta`    | string  | Non    | `translations` pour inclure les traductions  |
| `short`   | boolean | Non    | `true` exclut characters, artworks, trailers |

Ajoute : `artworks`, `characters`, `companies`, `contentRatings`, `genres`, `remoteIds`, `trailers`, `translations`, `releases`, `boxOffice`, `budget`, `audioLanguages`, `subtitleLanguages`, etc.

---

### Filtrer les films

```
GET /movies/filter
```

Mêmes paramètres que `/series/filter` (avec `country` et `lang` **obligatoires**), sauf :

- `sort` : `score`, `firstAired`, `name` (pas de `lastAired`)
- Pas de `sortType`

---

## Endpoints — Personnes

### Personne de base

```
GET /people/{id}
```

**Réponse** : `data` = `PeopleBaseRecord` (`id`, `name`, `image`, `score`, `aliases`, `nameTranslations`, `overviewTranslations`)

### Personne étendue

```
GET /people/{id}/extended
```

Ajoute : `biographies[]`, `birth`, `birthPlace`, `death`, `gender`, `characters[]`, `remoteIds[]`, `awards[]`, `translations`.

### Types de personnes

```
GET /people/types
```

Retourne les types : Actor, Director, Writer, etc.

---

## Endpoints — Artworks

### Artwork par ID

```
GET /artwork/{id}
```

**Réponse** : `data` = `ArtworkBaseRecord`

```json
{
  "id": 12345,
  "image": "https://artworks.thetvdb.com/banners/v4/series/81189/posters/5f148be2c4866.jpg",
  "thumbnail": "https://artworks.thetvdb.com/banners/v4/series/81189/posters/5f148be2c4866_t.jpg",
  "type": 2,
  "language": "eng",
  "score": 100150,
  "width": 680,
  "height": 1000,
  "includesText": true
}
```

### Artwork étendu

```
GET /artwork/{id}/extended
```

Ajoute : `thumbnailHeight`, `thumbnailWidth`, `updatedAt`, `status`, `tagOptions`, `seriesId`, `seasonId`, `episodeId`, `movieId`, `peopleId`, `networkId`.

### Types d'artwork

```
GET /artwork/types
```

**⚠️ Endpoint critique** : les IDs de types d'artwork sont **dynamiques** et doivent être récupérés à l'exécution.

**Réponse** : `data` = tableau de `ArtworkType`

```json
{
  "id": 2,
  "name": "Poster",
  "slug": "poster",
  "recordType": "series",
  "imageFormat": "jpg",
  "width": 680,
  "height": 1000,
  "thumbWidth": 170,
  "thumbHeight": 250
}
```

| Champ         | Type   | Description                                     |
| ------------- | ------ | ----------------------------------------------- |
| `id`          | int    | ID du type (utilisé pour filtrer)               |
| `name`        | string | Nom : Poster, Banner, Fanart, Clearlogo, etc.   |
| `slug`        | string | Slug URL                                        |
| `recordType`  | string | Entité applicable : series, movie, season, etc. |
| `imageFormat` | string | Format attendu : jpg, png                       |
| `width`       | int    | Largeur attendue en pixels                      |
| `height`      | int    | Hauteur attendue en pixels                      |
| `thumbWidth`  | int    | Largeur du thumbnail                            |
| `thumbHeight` | int    | Hauteur du thumbnail                            |

**27 types d'artwork** (vérifié via API 2026-04-10) :

| ID  | Nom            | RecordType | Dimensions  |
| --- | -------------- | ---------- | ----------- |
| 1   | Banner         | series     | 758 × 140   |
| 2   | Poster         | series     | 680 × 1000  |
| 3   | Background     | series     | 1920 × 1080 |
| 5   | Icon           | series     | 1024 × 1024 |
| 6   | Banner         | season     | 758 × 140   |
| 7   | Poster         | season     | 680 × 1000  |
| 8   | Background     | season     | 1920 × 1080 |
| 10  | Icon           | season     | 1024 × 1024 |
| 11  | 16:9 Screencap | episode    | 640 × 360   |
| 12  | 4:3 Screencap  | episode    | 640 × 480   |
| 13  | Photo          | actor      | 300 × 450   |
| 14  | Poster         | movie      | 680 × 1000  |
| 15  | Background     | movie      | 1920 × 1080 |
| 16  | Banner         | movie      | 758 × 140   |
| 18  | Icon           | movie      | 1024 × 1024 |
| 19  | Icon           | company    | 512 × 512   |
| 20  | Cinemagraph    | series     | 1280 × 720  |
| 21  | Cinemagraph    | movie      | 1280 × 720  |
| 22  | ClearArt       | series     | 1000 × 562  |
| 23  | ClearLogo      | series     | 800 × 310   |
| 24  | ClearArt       | movie      | 1000 × 562  |
| 25  | ClearLogo      | movie      | 800 × 310   |
| 26  | Icon           | award      | 1024 × 1024 |
| 27  | Poster         | list       | 680 × 1000  |

> **IDs manquants** : 4, 9, 17 n'existent pas.
> **Pas de "landscape" ni "discart"** — ces concepts sont propres à Kodi/MediaElch, pas à TVDB. Le `Background` (1920×1080) est l'équivalent le plus proche du "landscape".
> **Pas de ClearArt/ClearLogo pour les saisons** — seulement pour les séries et films.

**Types utiles pour le pipeline** :

| Usage pipeline             | Type ID | Nom        |
| -------------------------- | ------- | ---------- |
| Poster série               | 2       | Poster     |
| Background/landscape série | 3       | Background |
| Poster saison              | 7       | Poster     |
| Poster film                | 14      | Poster     |
| Background/landscape film  | 15      | Background |
| ClearLogo série            | 23      | ClearLogo  |

### Statuts d'artwork

```
GET /artwork/statuses
```

---

### Données à cacher

Les endpoints suivants retournent des données rarement modifiées. **Cacher pendant 1+ semaine** :

- `/artwork/types`
- `/artwork/statuses`
- `/content/ratings`
- `/countries`
- `/entities`
- `/genders`
- `/genres`
- `/inspiration/types`
- `/languages`
- `/movies/statuses`
- `/people/types`
- `/seasons/types`
- `/series/statuses`
- `/sources/types`

---

## Endpoints — Utilitaires

### Configuration API

Pas d'endpoint unique de configuration comme TMDB. Les données de référence sont réparties sur plusieurs endpoints (voir [Données à cacher](#données-à-cacher)).

### Source Types (IDs croisés)

```
GET /sources/types
```

> **⚠️ Chemin** : `/sources/types` (pluriel), pas `/source/types`.

Retourne la liste des sources d'IDs externes. **28 source types** (vérifié 2026-04-10) :

| ID  | Nom              | Slug             | Usage pipeline                 |
| --- | ---------------- | ---------------- | ------------------------------ |
| 2   | IMDB             | imdb             | **Cross-ref séries/films**     |
| 3   | TMS (Zap2It)     | zap2it           | —                              |
| 4   | Official Website | official-website | —                              |
| 10  | TheMovieDB.com   | tmdb             | **Cross-ref films → TMDB**     |
| 12  | TheMovieDB.com   | tmdbtv           | **Cross-ref séries TV → TMDB** |
| 15  | TheMovieDB.com   | tmdbperson       | Cross-ref personnes → TMDB     |
| 16  | IMDB             | imdbperson       | Cross-ref personnes → IMDB     |
| 18  | Wikidata         | wikidata         | —                              |
| 19  | TV Maze          | tvmaze           | —                              |
| 28  | TheMovieDB.com   | tmdbcollection   | Cross-ref collections → TMDB   |

> **⚠️ TMDB a 4 IDs différents** selon le type d'entité : films (10), séries TV (12), personnes (15), collections (28). Il faut utiliser le bon slug pour le cross-reference.

Utilisé pour interpréter le champ `type` dans les objets `RemoteID`.

---

### Genres

```
GET /genres
```

**Réponse** : tableau de `GenreBaseRecord`

```json
[
  { "id": 1, "name": "Action", "slug": "action" },
  { "id": 5, "name": "Drama", "slug": "drama" },
  { "id": 19, "name": "Science Fiction", "slug": "science-fiction" }
]
```

Un genre spécifique :

```
GET /genres/{id}
```

---

### Content Ratings

```
GET /content/ratings
```

**Réponse** : tableau de `ContentRating`

```json
{
  "id": 245,
  "name": "TV-14",
  "description": "...",
  "country": "usa",
  "contentType": "series",
  "order": 4,
  "fullName": "TV-14"
}
```

---

### Langues disponibles

```
GET /languages
```

**Réponse** :

```json
[
  {
    "id": "fra",
    "name": "French",
    "nativeName": "Français",
    "shortCode": "fr"
  },
  { "id": "eng", "name": "English", "nativeName": "English", "shortCode": "en" }
]
```

> **⚠️ `shortCode` est toujours `null`** dans les réponses actuelles (vérifié 2026-04-10). Le `id` (3 chars, ex: `fra`) est le seul identifiant fiable. Pour le mapping TVDB→TMDB, maintenir une table de conversion manuelle (`fra`→`fr-FR`, `eng`→`en-US`).

---

### Pays disponibles

```
GET /countries
```

**Réponse** :

```json
[
  { "id": "fra", "name": "France", "shortCode": "fr" },
  { "id": "usa", "name": "United States", "shortCode": "us" }
]
```

---

### Updates (changements)

```
GET /updates
```

Récupère les entités modifiées depuis un timestamp donné. Essentiel pour maintenir un cache à jour.

| Paramètre | Type   | Requis  | Description                                        |
| --------- | ------ | ------- | -------------------------------------------------- |
| `since`   | number | **Oui** | Timestamp Unix — uniquement les changements après  |
| `type`    | string | Non     | Type d'entité (ex: `series`, `episodes`, `movies`) |
| `action`  | string | Non     | `delete` ou `update`                               |
| `page`    | number | Non     | Pagination                                         |

**Réponse** : tableau de `EntityUpdate`

```json
{
  "entityType": "series",
  "methodInt": 2,
  "method": "update",
  "recordId": 81189,
  "timeStamp": 1710504000,
  "seriesId": 81189,
  "mergeToId": null,
  "mergeToEntityType": null,
  "userId": 12345,
  "extraInfo": "..."
}
```

| `methodInt` | Signification |
| ----------- | ------------- |
| 1           | Création      |
| 2           | Mise à jour   |
| 3           | Suppression   |

> **Gestion des fusions** : quand un doublon est supprimé, `mergeToId` et `mergeToEntityType` indiquent vers quel enregistrement les données ont été consolidées.

---

## Gestion des erreurs

### Codes HTTP

| HTTP | Description                              | Action pipeline          |
| ---- | ---------------------------------------- | ------------------------ |
| 200  | Succès                                   | Parser `data`            |
| 304  | Non modifié (avec `If-Modified-Since`)   | Utiliser le cache        |
| 400  | Requête invalide / paramètres incorrects | Corriger la requête      |
| 401  | Non autorisé (token invalide/expiré)     | Re-login (`POST /login`) |
| 404  | Ressource non trouvée                    | Skip, log "not found"    |
| 405  | Méthode non autorisée                    | Vérifier la méthode HTTP |
| 429  | Rate limit (inféré)                      | Retry avec backoff       |

### ⚠️ Deux formats de réponse d'erreur différents

**Erreurs login** (HTTP 400/401 sur `/login`) — inclut `status`, `message` et `data` :

```json
{
  "status": "failure",
  "message": "InvalidValueType: pin required",
  "data": null
}
```

**Erreurs générales** (HTTP 401/404/405 sur les autres endpoints) — structure minimale :

```json
{ "message": "Unauthorized" }
```

```json
{ "message": "Method Not Allowed" }
```

> **Attention** : le code doit gérer les deux formats. Ne pas compter sur la présence de `status` dans toutes les réponses d'erreur.

### Stratégie de retry

```
HTTP 401 → re-login automatique (token expiré) → retry
HTTP 429 → exponential backoff → retry (max 3 tentatives)
HTTP 5xx → exponential backoff → retry (max 3 tentatives)
HTTP 400 → ne PAS retrier (erreur de paramètres)
HTTP 404 → ne PAS retrier (ressource inexistante)
```

---

## IDs croisés (IMDB, TMDB)

### TVDB → IMDB/TMDB

Récupérer l'enregistrement étendu et lire `remoteIds[]` :

```
GET /series/{id}/extended
GET /movies/{id}/extended
```

Chaque objet `RemoteID` :

```json
{ "id": "tt0903747", "type": 2, "sourceName": "IMDB" }
```

Le `type` référence l'ID du `SourceType` (voir `/sources/types`).

### IMDB → TVDB

```
GET /search/remoteid/{imdb_id}
```

Exemple : `GET /search/remoteid/tt0903747` → retourne la série Breaking Bad.

### TMDB → TVDB

Pas d'endpoint direct. Utiliser TMDB `/find/{tmdb_id}?external_source=tvdb_id` pour le cross-reference inverse, ou chercher par nom.

---

## Stratégie d'appels optimale

### Pour une série TV (pipeline scrape step)

```
1. POST /login
   → Token JWT (cacher pour 1 mois)

2. GET /search?query={title}&type=series&year={year}
   → Récupère l'ID TVDB + année + remote_ids dans les résultats

3. GET /series/{id}/extended?short=true
   → Détails + genres + seasons[] + remoteIds[] + contentRatings[]
   → (short=true exclut artworks/characters/trailers pour réduire le payload)

4. GET /series/{id}/artworks?type={poster_type_id},{background_type_id}
   → Artworks filtrés par type (poster + background seulement)

5. Pour chaque saison :
   GET /series/{id}/episodes/default?season={n}
   → Liste des épisodes (nom, numéro, date, runtime, image, overview)

6. Pour les titres d'épisodes en français :
   GET /episodes/{id}/translations/fra
   → Nom et synopsis traduits
   (OU utiliser GET /series/{id}/episodes/default/fra?page=0 pour tout en un bloc)
```

### Nombre d'appels total

| Étape                | Appels                      |
| -------------------- | --------------------------- |
| Login                | 1                           |
| Search               | 1                           |
| Series extended      | 1                           |
| Artworks filtrés     | 1                           |
| Épisodes par saison  | N (= nombre de saisons)     |
| Traductions épisodes | N (ou 1 si endpoint groupé) |
| **Total**            | **4 + 2N**                  |

Pour une série avec 5 saisons : **14 appels**.

### Comparaison avec TMDB

| Opération              | TVDB        | TMDB                   |
| ---------------------- | ----------- | ---------------------- |
| Auth                   | 1 call/mois | 0 (API key)            |
| Search série           | 1           | 1                      |
| Détails + IDs + images | 2-3         | 1 (append_to_response) |
| Épisodes par saison    | N           | N                      |
| Traductions            | N ou 1      | Inclus dans `language` |
| **Total (5 saisons)**  | ~14         | ~7                     |

> TMDB est plus économe grâce à `append_to_response`. Mais TVDB est la source primaire pour les données TV car sa couverture des séries est plus complète.

---

## Résumé des schémas de réponse

### SeriesBaseRecord

| Champ                  | Type     | Description                      |
| ---------------------- | -------- | -------------------------------- |
| `id`                   | int64    | ID TVDB                          |
| `name`                 | string   | Nom de la série                  |
| `slug`                 | string   | Identifiant URL                  |
| `image`                | string   | URL de l'image principale        |
| `firstAired`           | string   | Date de première diffusion       |
| `lastAired`            | string   | Date de dernière diffusion       |
| `nextAired`            | string   | Prochaine diffusion prévue       |
| `score`                | number   | Score de popularité (relatif)    |
| `status`               | Status   | Statut (Continuing, Ended, etc.) |
| `originalCountry`      | string   | Pays d'origine (3 chars)         |
| `originalLanguage`     | string   | Langue d'origine (3 chars)       |
| `year`                 | string   | Année de sortie                  |
| `nameTranslations`     | string[] | Langues avec nom traduit         |
| `overviewTranslations` | string[] | Langues avec synopsis traduit    |
| `aliases`              | Alias[]  | Titres alternatifs               |
| `lastUpdated`          | string   | Dernière modification            |
| `isOrderRandomized`    | boolean  | Ordre aléatoire des épisodes     |

### EpisodeBaseRecord

| Champ                  | Type        | Description                          |
| ---------------------- | ----------- | ------------------------------------ |
| `id`                   | int64       | ID TVDB                              |
| `seriesId`             | int64       | ID de la série parente               |
| `name`                 | string      | Titre de l'épisode                   |
| `number`               | int         | Numéro d'épisode dans la saison      |
| `seasonNumber`         | int         | Numéro de saison                     |
| `seasonName`           | string      | Nom de la saison                     |
| `absoluteNumber`       | int         | Numéro absolu (toutes saisons)       |
| `aired`                | string      | Date de diffusion                    |
| `runtime`              | int/null    | Durée en minutes                     |
| `image`                | string      | URL de l'image (still)               |
| `imageType`            | int/null    | Type d'image                         |
| `overview`             | string      | Synopsis                             |
| `finaleType`           | string/null | `season`, `midseason`, `series`      |
| `isMovie`              | int64       | Indique si lié à un film             |
| `linkedMovie`          | int/null    | ID du film associé                   |
| `airsAfterSeason`      | int/null    | Spécial : diffusé après cette saison |
| `airsBeforeEpisode`    | int/null    | Spécial : diffusé avant cet épisode  |
| `airsBeforeSeason`     | int/null    | Spécial : diffusé avant cette saison |
| `year`                 | string      | Année                                |
| `nameTranslations`     | string[]    | Langues avec nom traduit             |
| `overviewTranslations` | string[]    | Langues avec synopsis traduit        |
| `lastUpdated`          | string      | Dernière modification                |

### SeasonBaseRecord

| Champ                  | Type       | Description                      |
| ---------------------- | ---------- | -------------------------------- |
| `id`                   | int        | ID TVDB                          |
| `seriesId`             | int64      | ID de la série parente           |
| `number`               | int64      | Numéro de saison (0 = spéciales) |
| `name`                 | string     | Nom de la saison                 |
| `image`                | string     | URL du poster de saison          |
| `imageType`            | int        | Type d'image                     |
| `year`                 | string     | Année                            |
| `type`                 | SeasonType | Type de saison                   |
| `lastUpdated`          | string     | Dernière modification            |
| `nameTranslations`     | string[]   | Langues avec nom traduit         |
| `overviewTranslations` | string[]   | Langues avec synopsis traduit    |

### ArtworkBaseRecord

| Champ          | Type    | Description                             |
| -------------- | ------- | --------------------------------------- |
| `id`           | int     | ID de l'artwork                         |
| `image`        | string  | URL complète de l'image                 |
| `thumbnail`    | string  | URL du thumbnail                        |
| `type`         | int     | ID du type (référence `/artwork/types`) |
| `language`     | string  | Code langue 3 chars                     |
| `score`        | number  | Score communautaire                     |
| `width`        | int     | Largeur en pixels                       |
| `height`       | int     | Hauteur en pixels                       |
| `includesText` | boolean | Image contient du texte incrusté        |

### RemoteID

| Champ        | Type   | Description                                |
| ------------ | ------ | ------------------------------------------ |
| `id`         | string | Valeur de l'ID externe (ex: `tt0903747`)   |
| `type`       | int    | ID du type de source                       |
| `sourceName` | string | Nom lisible (ex: `IMDB`, `TheMovieDB.com`) |

### Character

| Champ          | Type     | Description                      |
| -------------- | -------- | -------------------------------- |
| `id`           | int      | ID du personnage                 |
| `name`         | string   | Nom du personnage                |
| `peopleId`     | int      | ID de la personne                |
| `personName`   | string   | Nom de l'acteur/actrice          |
| `personImgURL` | string   | Photo de l'acteur                |
| `image`        | string   | Image du personnage              |
| `isFeatured`   | boolean  | Personnage principal             |
| `type`         | int      | Type (acteur, réalisateur, etc.) |
| `sort`         | int      | Ordre d'affichage                |
| `seriesId`     | int/null | Série associée                   |
| `movieId`      | int/null | Film associé                     |
| `episodeId`    | int/null | Épisode associé                  |

### Translation

| Champ       | Type     | Description                |
| ----------- | -------- | -------------------------- |
| `language`  | string   | Code langue 3 chars        |
| `name`      | string   | Nom traduit                |
| `overview`  | string   | Synopsis traduit           |
| `aliases`   | string[] | Alias traduits             |
| `isAlias`   | boolean  | Est un alias               |
| `isPrimary` | boolean  | Est la traduction primaire |
| `tagline`   | string   | Tagline (films uniquement) |

### SearchResult (champs principaux)

| Champ              | Type       | Description                                 |
| ------------------ | ---------- | ------------------------------------------- |
| `objectID`         | string     | ID interne                                  |
| `tvdb_id`          | string     | ID TVDB                                     |
| `type`             | string     | `series`, `movie`, `person`, `company`      |
| `name`             | string     | Nom principal                               |
| `slug`             | string     | Slug URL                                    |
| `year`             | string     | Année                                       |
| `status`           | string     | Statut                                      |
| `country`          | string     | Pays d'origine                              |
| `network`          | string     | Réseau de diffusion                         |
| `primary_language` | string     | Langue principale                           |
| `overview`         | string     | Synopsis                                    |
| `image_url`        | string     | URL de l'image principale                   |
| `poster`           | string     | URL du poster                               |
| `first_air_time`   | string     | Date de première diffusion                  |
| `is_official`      | boolean    | Entrée officielle                           |
| `remote_ids`       | RemoteID[] | IDs externes                                |
| `translations`     | object     | `{ "fra": "Titre FR", "eng": "..." }`       |
| `overviews`        | object     | `{ "fra": "Synopsis FR...", "eng": "..." }` |
| `genres`           | string[]   | Noms de genres                              |
| `aliases`          | string[]   | Titres alternatifs                          |

---

## Gotchas et notes importantes

### 1. Codes langue à 3 caractères

TVDB utilise **3 caractères** (`fra`, `eng`, `spa`), pas 2 comme TMDB (`fr`, `en`, `es`). L'endpoint `/languages` fournit la correspondance via le champ `shortCode`.

### 2. Pagination indexée à 0

Les pages commencent à **0** (pas 1 comme TMDB). La première page est `page=0`.

### 3. Artwork type IDs dynamiques

Les IDs des types d'artwork ne sont **pas documentés de manière stable**. Toujours récupérer `/artwork/types` au démarrage du pipeline et cacher le résultat.

### 4. PIN selon le type de clé

Le PIN n'est requis que pour les clés **User Subscription**. Les clés **Negotiated Contract** (gratuit, < $50k) fonctionnent avec `{"apikey": "..."}` seul — ne PAS inclure le champ `pin`. Si l'API retourne `"pin required"`, la clé est de type User Subscription.

### 5. Images d'épisodes en 4:3 ou 16:9

Les images d'épisodes peuvent être en **4:3 ou 16:9** selon le format de diffusion original. L'UI doit gérer les deux.

### 6. Score relatif

Le `score` est un score de popularité **relatif au type d'entité**. Ne pas comparer les scores de séries avec ceux de films.

### 7. Pas d'API en écriture

L'API TVDB v4 est **lecture seule**. Pas d'endpoint pour créer ou modifier des séries/films/épisodes.

### 8. Paramètre `short` pour les payloads lourds

Sur les endpoints extended, `?short=true` exclut `characters`, `artworks` et `trailers` pour réduire la taille de la réponse. Utile quand on n'a besoin que des métadonnées.

### 9. Suppression avec fusion

Quand un enregistrement est supprimé comme doublon, la réponse `updates` peut inclure `mergeToId` et `mergeToEntityType` indiquant vers quel enregistrement les données ont été consolidées.

### 10. `episodeNumber` requiert `season`

Sur l'endpoint d'épisodes par saison, le paramètre `episodeNumber` ne peut pas être utilisé seul — il requiert `season`.

### 11. Pas de `append_to_response`

Contrairement à TMDB, TVDB n'a pas de mécanisme `append_to_response`. Les endpoints `extended` avec `meta` et `short` sont l'équivalent le plus proche.

### 12. Deux formats de réponse d'erreur

Erreurs login : `{status, message, data}`. Erreurs endpoints : `{message}` seul. Voir [Gestion des erreurs](#gestion-des-erreurs).

### 13. Champs inexistants (vérification live 2026-04-10)

`audioLanguages`, `subtitleLanguages`, `spokenLanguages` **n'existent PAS** dans les réponses `SeriesExtendedRecord` (testé sur Breaking Bad). `studios` et `awards` n'existent que sur `EpisodeExtendedRecord`, pas sur `SeriesExtendedRecord`.

### 14. Champs SeriesExtended confirmés par le Swagger mais absents de notre doc initiale

Présents dans le schéma Swagger et ajoutés ci-dessous pour référence :

| Champ               | Type           | Description                                              |
| ------------------- | -------------- | -------------------------------------------------------- |
| `abbreviation`      | string         | Abréviation de la série                                  |
| `airsDays`          | object         | Jours de diffusion : `{monday: bool, ..., sunday: bool}` |
| `airsTime`          | string         | Heure de diffusion (ex: `"21:00"`)                       |
| `averageRuntime`    | int (nullable) | Durée moyenne d'un épisode en minutes                    |
| `defaultSeasonType` | int64          | Type de saison par défaut (ID)                           |
| `latestNetwork`     | Company        | Réseau de diffusion actuel                               |
| `originalNetwork`   | Company        | Réseau de diffusion original                             |
| `seasonTypes`       | SeasonType[]   | Types de saisons disponibles pour cette série            |

### 15. `/series/{id}/nextAired` — endpoint à préférer

Le champ `nextAired` était inclus dans le record de base mais sera **déprécié**. TVDB recommande d'utiliser l'endpoint dédié `/series/{id}/nextAired` à la place.

---

## Edge cases et vérifications (tests live 2026-04-10)

| #   | Comportement                                         | Détail                                                                                                           |
| --- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1   | PIN non requis pour clés Negotiated Contract         | `{"apikey": "..."}` suffit. Seules les clés User Subscription exigent un PIN.                                    |
| 2   | Deux formats de réponse d'erreur                     | Login : `{status, message, data}`. Endpoints : `{message}` seul. Le code doit gérer les deux.                    |
| 3   | HTTP 405 sur GET /login                              | Seul POST est accepté. Retourne `{"message": "Method Not Allowed"}`.                                             |
| 4   | Recherche vide = HTTP 200                            | `{"status":"success","data":[],"links":{...}}` — pas de 404. Vérifier `len(data)`.                               |
| 5   | Search en snake_case, entities en camelCase          | `image_url`, `first_air_time`, `tvdb_id` (search) vs `imageUrl`, `firstAired` (entities). Incohérence API.       |
| 6   | `artwork` (singulier) pour saisons                   | `SeasonExtended` utilise `artwork`, `SeriesExtended` utilise `artworks` (pluriel). Incohérence API.              |
| 7   | `short=true` met les arrays à `null`                 | `artworks`, `characters`, `episodes` deviennent `null` (pas des arrays vides). Vérifier avec `is not None`.      |
| 8   | `audioLanguages` etc. n'existent pas                 | `audioLanguages`, `subtitleLanguages`, `spokenLanguages` absents de `SeriesExtendedRecord`.                      |
| 9   | `shortCode` des langues toujours null                | Le champ existe sur `/languages` mais vaut `None` pour toutes les langues. Ne pas s'en servir pour le mapping.   |
| 10  | 4 IDs TMDB différents dans source types              | films=10, séries TV=12, personnes=15, collections=28. Utiliser le bon pour le cross-reference.                   |
| 11  | Épisodes traduits : toutes saisons par défaut        | `/series/{id}/episodes/default/fra` retourne TOUS les épisodes (spéciaux inclus). Filtrer avec `?season=N`.      |
| 12  | Updates : `entityType` pas `recordType`              | `recordType` est toujours vide dans les réponses `/updates`. Utiliser `entityType` à la place.                   |
| 13  | 404 = `{status:"failure", message:"...", data:null}` | Inclut le type d'exception : `"NotFoundException: error fetching series"`.                                       |
| 14  | Content ratings FR split par contentType             | "episode" et "movie" ont des ratings FR séparés : TP, -10, -12, -16 (épisodes) vs TP, -10, -12, -16, UR (films). |
| 15  | Pas de landscape/discart dans TVDB                   | Ces concepts sont propres à Kodi/MediaElch. `Background` (1920×1080) est l'équivalent le plus proche.            |

---

## Annexe — Inventaire complet des endpoints (~67)

| Catégorie       | Endpoints                                                                                                                                                                                                                                                                         |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth            | POST `/login`                                                                                                                                                                                                                                                                     |
| Artwork         | GET `/artwork/{id}`, `/artwork/{id}/extended`, `/artwork/statuses`, `/artwork/types`                                                                                                                                                                                              |
| Awards          | GET `/awards`, `/awards/{id}`, `/awards/{id}/extended`, `/awards/categories/{id}`, `/awards/categories/{id}/extended`                                                                                                                                                             |
| Characters      | GET `/characters/{id}`                                                                                                                                                                                                                                                            |
| Companies       | GET `/companies`, `/companies/{id}`, `/companies/types`                                                                                                                                                                                                                           |
| Content Ratings | GET `/content/ratings`                                                                                                                                                                                                                                                            |
| Countries       | GET `/countries`                                                                                                                                                                                                                                                                  |
| Entities        | GET `/entities`                                                                                                                                                                                                                                                                   |
| Episodes        | GET `/episodes`, `/episodes/{id}`, `/episodes/{id}/extended`, `/episodes/{id}/translations/{lang}`                                                                                                                                                                                |
| Genders         | GET `/genders`                                                                                                                                                                                                                                                                    |
| Genres          | GET `/genres`, `/genres/{id}`                                                                                                                                                                                                                                                     |
| Inspiration     | GET `/inspiration/types`                                                                                                                                                                                                                                                          |
| Languages       | GET `/languages`                                                                                                                                                                                                                                                                  |
| Lists           | GET `/lists`, `/lists/{id}`, `/lists/{id}/extended`, `/lists/{id}/translations/{lang}`, `/lists/slug/{slug}`                                                                                                                                                                      |
| Movies          | GET `/movies`, `/movies/{id}`, `/movies/{id}/extended`, `/movies/{id}/translations/{lang}`, `/movies/filter`, `/movies/slug/{slug}`, `/movies/statuses`                                                                                                                           |
| People          | GET `/people`, `/people/{id}`, `/people/{id}/extended`, `/people/{id}/translations/{lang}`, `/people/types`                                                                                                                                                                       |
| Search          | GET `/search`, `/search/remoteid/{remoteId}`                                                                                                                                                                                                                                      |
| Seasons         | GET `/seasons`, `/seasons/{id}`, `/seasons/{id}/extended`, `/seasons/{id}/translations/{lang}`, `/seasons/types`                                                                                                                                                                  |
| Series          | GET `/series`, `/series/{id}`, `/series/{id}/artworks`, `/series/{id}/extended`, `/series/{id}/episodes/{type}`, `/series/{id}/episodes/{type}/{lang}`, `/series/{id}/nextAired`, `/series/{id}/translations/{lang}`, `/series/filter`, `/series/slug/{slug}`, `/series/statuses` |
| Source Types    | GET `/sources/types`                                                                                                                                                                                                                                                              |
| Updates         | GET `/updates`                                                                                                                                                                                                                                                                    |
| User            | GET `/user`, `/user/{id}`, `/user/favorites`, POST `/user/favorites`                                                                                                                                                                                                              |
