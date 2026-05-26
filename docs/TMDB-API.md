# TMDB API — Documentation de référence

> The Movie Database API v3 — référence complète pour le pipeline PersonalScraper (scrape step).
>
> Dernière mise à jour : 2026-04-10

---

## Table des matières

- [Authentification](#authentification)
- [URLs de base](#urls-de-base)
- [Rate limiting](#rate-limiting)
- [Langues et régions](#langues-et-régions)
- [Images — Configuration et URLs](#images--configuration-et-urls)
- [append_to_response](#append_to_response)
- [Endpoints — Films](#endpoints--films)
  - [Recherche de films](#recherche-de-films)
  - [Détails d'un film](#détails-dun-film)
  - [Crédits d'un film](#crédits-dun-film)
  - [Images d'un film](#images-dun-film)
  - [IDs externes d'un film](#ids-externes-dun-film)
  - [Discover films](#discover-films)
- [Endpoints — Séries TV](#endpoints--séries-tv)
  - [Recherche de séries](#recherche-de-séries)
  - [Détails d'une série](#détails-dune-série)
  - [Crédits agrégés d'une série](#crédits-agrégés-dune-série)
  - [Images d'une série](#images-dune-série)
  - [IDs externes d'une série](#ids-externes-dune-série)
- [Endpoints — Saisons](#endpoints--saisons)
  - [Détails d'une saison](#détails-dune-saison)
  - [Images d'une saison](#images-dune-saison)
- [Endpoints — Épisodes](#endpoints--épisodes)
  - [Détails d'un épisode](#détails-dun-épisode)
  - [Images d'un épisode](#images-dun-épisode)
- [Endpoints — Utilitaires](#endpoints--utilitaires)
  - [Configuration API](#configuration-api)
  - [Find by External ID](#find-by-external-id)
  - [Search Multi](#search-multi)
  - [Genres (films)](#genres-films)
  - [Genres (TV)](#genres-tv)
  - [Certifications](#certifications)
- [Gestion des erreurs](#gestion-des-erreurs)
- [Stratégie d'appels optimale](#stratégie-dappels-optimale)
- [Résumé des schémas de réponse](#résumé-des-schémas-de-réponse)
- [Certifications FR — Extraction](#certifications-fr--extraction)
- [Edge cases vérifiés](#edge-cases-vérifiés-tests-live-2026-04-10)

---

## Authentification

Deux méthodes équivalentes (même niveau d'accès) :

### Bearer Token (recommandé)

```
Authorization: Bearer <TMDB_API_KEY>
```

> TMDB appelle cette clé "API Read Access Token" (v4), mais le pipeline
> utilise `TMDB_API_KEY` (env var) comme Bearer token.

Fonctionne avec les endpoints v3 et v4. Token disponible sur https://www.themoviedb.org/settings/api.

### API Key (query parameter)

```
GET /3/movie/550?api_key=<TMDB_API_KEY>
```

Approche legacy, toujours supportée pour l'API v3.

### Emplacement des clés dans le pipeline

```
<project_root>/.env
  → TMDB_API_KEY=...    # Clé API v3 (Bearer token)
```

---

## URLs de base

| Usage        | URL                             |
| ------------ | ------------------------------- |
| API v3       | `https://api.themoviedb.org/3/` |
| API v4       | `https://api.themoviedb.org/4/` |
| Images HTTP  | `http://image.tmdb.org/t/p/`    |
| Images HTTPS | `https://image.tmdb.org/t/p/`   |

Toutes les réponses sont en `application/json`.

---

## Rate limiting

| Paramètre          | Valeur                          |
| ------------------ | ------------------------------- |
| Limite actuelle    | ~50 req/sec (plafond ~40 req/s) |
| Code HTTP          | `429 Too Many Requests`         |
| TMDB error code    | `25`                            |
| Header Retry-After | Non documenté officiellement    |

**Stratégie recommandée** : exponential backoff sur HTTP 429, maximum 3 retries.

> Note : l'ancienne limite de 40 req / 10 sec a été désactivée le 16/12/2019. La limite actuelle est plus souple mais toujours présente pour empêcher le scraping en masse.

---

## Langues et régions

### Format

ISO 639-1 + optionnellement ISO 3166-1 : `{langue}-{PAYS}`

Exemples : `fr-FR`, `en-US`, `pt-BR`, `de-DE`

### Paramètre `language`

- Présent sur la plupart des endpoints
- Défaut : `en-US`
- Affecte : titres, synopsis (overview), taglines, noms de genres, noms d'épisodes

### Champs NON traduisibles

- Noms de personnes (acteurs, réalisateurs)
- Noms de personnages

### Filtrage des images par langue

**⚠️ Piège important** : le paramètre `language` filtre aussi les images. Avec `language=fr-FR`, seules les images françaises sont retournées (souvent très peu).

**Solution** : utiliser `include_image_language` :

```
GET /3/movie/550/images?include_image_language=fr,en,null
```

- `fr` — images françaises
- `en` — images anglaises
- `null` — images sans langue (neutres, sans texte incrusté)

---

## Images — Configuration et URLs

### Construction d'URL

```
{secure_base_url}{size}{file_path}
```

Exemple :

```
https://image.tmdb.org/t/p/w500/1E5baAaEse26fej7uHcjOgEE2t2.jpg
```

### Tailles disponibles par type

| Type d'image | Tailles disponibles                                       |
| ------------ | --------------------------------------------------------- |
| **poster**   | `w92`, `w154`, `w185`, `w342`, `w500`, `w780`, `original` |
| **backdrop** | `w300`, `w780`, `w1280`, `original`                       |
| **logo**     | `w45`, `w92`, `w154`, `w185`, `w300`, `w500`, `original`  |
| **profile**  | `w45`, `w185`, `h632`, `original`                         |
| **still**    | `w92`, `w185`, `w300`, `original`                         |

- `w` = contrainte sur la largeur (hauteur proportionnelle)
- `h` = contrainte sur la hauteur (largeur proportionnelle)
- `original` = résolution originale telle qu'uploadée

### Tailles recommandées pour le pipeline

| Usage                | Taille recommandée | Raison                     |
| -------------------- | ------------------ | -------------------------- |
| Poster (affichage)   | `w500`             | Bon ratio qualité/taille   |
| Poster (NFO preview) | `w342`             | Utilisé par MediaElch/Kodi |
| Backdrop/Landscape   | `original`         | Qualité maximale           |
| Poster (original)    | `original`         | Téléchargement final       |
| Actor thumbnail      | `w185`             | Suffisant pour `.actors/`  |
| Episode still        | `w300`             | Thumbnail épisode          |

### Objet Image (structure commune)

```json
{
  "file_path": "/pEoqbqtLc4CcwDUDqxmEDSWpWTZ.jpg",
  "aspect_ratio": 0.667,
  "width": 2000,
  "height": 3000,
  "iso_639_1": "fr",
  "iso_3166_1": "FR",
  "vote_average": 5.312,
  "vote_count": 3
}
```

- `iso_639_1` = `null` pour les images neutres (sans texte incrusté) — la majorité des backdrops
- `iso_3166_1` = code pays (présent dans les réponses réelles, absent de la doc officielle TMDB)

### Cache de la configuration

Les données de `/3/configuration` changent rarement. TMDB recommande de les cacher et de les rafraîchir tous les quelques jours.

---

## append_to_response

Mécanisme pour combiner plusieurs sous-requêtes en un seul appel HTTP.

### Endpoints supportés

| Endpoint           | Supporte `append_to_response` |
| ------------------ | ----------------------------- |
| Movie Details      | Oui (max 20)                  |
| TV Series Details  | Oui (max 20)                  |
| TV Season Details  | Oui (max 20)                  |
| TV Episode Details | Oui (max 20)                  |
| Person Details     | Oui (max 20)                  |
| Search (tous)      | Non                           |
| Find               | Non                           |

### Syntaxe

```
GET /3/movie/550?append_to_response=credits,images,external_ids&language=fr-FR
```

### Règles clés

1. **Maximum 20 items** par requête
2. Chaque sous-requête apparaît comme une nouvelle clé JSON dans la réponse
3. Le paramètre `language` s'applique à toutes les sous-requêtes
4. Pour les images, utiliser `include_image_language` en complément
5. **Les sous-requêtes ne comptent PAS comme des appels séparés** pour le rate limiting

### Valeurs courantes

**Films** : `credits`, `images`, `external_ids`, `videos`, `release_dates`, `keywords`, `alternative_titles`, `translations`, `recommendations`, `similar`, `reviews`, `watch/providers`

**Séries TV** : `aggregate_credits`, `credits`, `external_ids`, `images`, `content_ratings`, `videos`, `keywords`, `alternative_titles`, `translations`, `recommendations`, `similar`, `reviews`, `watch/providers`, `episode_groups`

**Saisons** : `images`, `credits`, `videos`, `translations`

**Épisodes** : `images`, `credits`, `videos`, `translations`

---

## Endpoints — Films

### Recherche de films

```
GET /3/search/movie
```

| Paramètre              | Type    | Requis  | Défaut  | Description                                                     |
| ---------------------- | ------- | ------- | ------- | --------------------------------------------------------------- |
| `query`                | string  | **Oui** | —       | Texte de recherche                                              |
| `language`             | string  | Non     | `en-US` | Langue des résultats                                            |
| `page`                 | int     | Non     | `1`     | Page (1-500)                                                    |
| `year`                 | string  | Non     | —       | Booste la pertinence pour cette année (⚠️ pas un filtre strict) |
| `primary_release_year` | string  | Non     | —       | Booste la pertinence par année de sortie principale             |
| `region`               | string  | Non     | —       | ISO 3166-1 pour filtrer les dates locales                       |
| `include_adult`        | boolean | Non     | `false` | Inclure le contenu adulte                                       |

**Réponse** (paginée) — exemple réel (`Le Comte de Monte-Cristo`, year=2024, language=fr-FR) :

```json
{
  "page": 1,
  "total_pages": 1,
  "total_results": 3,
  "results": [
    {
      "id": 1084736,
      "title": "Le Comte de Monte-Cristo",
      "original_title": "Le Comte de Monte-Cristo",
      "original_language": "fr",
      "overview": "Victime d'un complot, le jeune Edmond Dantès est arrêté...",
      "release_date": "2024-06-28",
      "poster_path": "/oVOEhfRLPIuthVtV8x1yrjCcoFi.jpg",
      "backdrop_path": "/aswBReGLMBGBDrV2LZIIszCdSMZ.jpg",
      "genre_ids": [12, 18, 36],
      "popularity": 45.678,
      "vote_average": 8.1,
      "vote_count": 1800,
      "adult": false,
      "video": false
    }
  ]
}
```

> **⚠️ Edge case vérifié** : malgré `year=2024`, la recherche retourne aussi des versions de 1975 et 1943. Le paramètre `year` **booste la pertinence** mais **n'exclut PAS** les autres années. Le pipeline doit filtrer côté client par `release_date` si un filtrage strict est nécessaire.

**Réponse vide** (aucun résultat) — HTTP 200, pas d'erreur :

```json
{ "page": 1, "results": [], "total_pages": 1, "total_results": 0 }
```

> Le code doit vérifier `len(results)`, pas le status HTTP.

---

### Détails d'un film

```
GET /3/movie/{movie_id}
```

| Paramètre            | Emplacement | Type   | Requis  | Description                              |
| -------------------- | ----------- | ------ | ------- | ---------------------------------------- |
| `movie_id`           | Path        | int    | **Oui** | ID TMDB du film                          |
| `language`           | Query       | string | Non     | Défaut : `en-US`                         |
| `append_to_response` | Query       | string | Non     | Sous-requêtes (max 20, séparées par `,`) |

**Réponse** :

```json
{
  "id": 550,
  "title": "Fight Club",
  "original_title": "Fight Club",
  "original_language": "en",
  "overview": "Synopsis...",
  "tagline": "Tagline...",
  "status": "Released",
  "release_date": "1999-10-15",
  "runtime": 139,
  "budget": 63000000,
  "revenue": 100853753,
  "popularity": 61.416,
  "vote_average": 8.433,
  "vote_count": 28894,
  "adult": false,
  "video": false,
  "imdb_id": "tt0137523",
  "homepage": "http://...",
  "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
  "backdrop_path": "/hZkgoQYus5dXo3H8T7Uef6DNknx.jpg",
  "origin_country": ["US"],

  "genres": [
    { "id": 18, "name": "Drame" },
    { "id": 53, "name": "Thriller" }
  ],

  "belongs_to_collection": null,

  "production_companies": [
    {
      "id": 508,
      "name": "Regency Enterprises",
      "logo_path": "/7PzJdsLGlR7oW4J0J5Xcd0pHGRg.png",
      "origin_country": "US"
    }
  ],

  "production_countries": [
    { "iso_3166_1": "US", "name": "United States of America" }
  ],

  "spoken_languages": [
    { "iso_639_1": "en", "english_name": "English", "name": "English" }
  ]
}
```

**Champs clés pour le pipeline** : `id`, `title`, `original_title`, `overview`, `tagline`, `release_date`, `runtime`, `genres`, `imdb_id`, `poster_path`, `backdrop_path`, `vote_average`, `vote_count`, `production_companies`, `spoken_languages`.

---

### Crédits d'un film

```
GET /3/movie/{movie_id}/credits
```

| Paramètre  | Type   | Requis  | Description      |
| ---------- | ------ | ------- | ---------------- |
| `movie_id` | int    | **Oui** | ID TMDB du film  |
| `language` | string | Non     | Défaut : `en-US` |

**Réponse** :

```json
{
  "id": 550,
  "cast": [
    {
      "id": 819,
      "name": "Edward Norton",
      "original_name": "Edward Norton",
      "character": "The Narrator",
      "order": 0,
      "profile_path": "/5XBzD5WuTyVQZeS4VI25z2moMeY.jpg",
      "gender": 2,
      "known_for_department": "Acting",
      "popularity": 26.99,
      "adult": false,
      "cast_id": 4,
      "credit_id": "52fe4250c3a36847f80149f3"
    }
  ],
  "crew": [
    {
      "id": 7467,
      "name": "David Fincher",
      "original_name": "David Fincher",
      "department": "Directing",
      "job": "Director",
      "profile_path": "/tpEczFclQZeKAiCeKZZ0adRvtfz.jpg",
      "gender": 2,
      "known_for_department": "Directing",
      "popularity": 18.45,
      "adult": false,
      "credit_id": "52fe4250c3a36847f8014a11"
    }
  ]
}
```

**Champs `gender`** : 0 = non spécifié, 1 = femme, 2 = homme, 3 = non-binaire.

> **Astuce** : utiliser `append_to_response=credits` sur `/movie/{id}` pour éviter un appel séparé.

---

### Images d'un film

```
GET /3/movie/{movie_id}/images
```

| Paramètre                | Type   | Requis  | Description                         |
| ------------------------ | ------ | ------- | ----------------------------------- |
| `movie_id`               | int    | **Oui** | ID TMDB du film                     |
| `language`               | string | Non     | Filtre par langue (⚠️ restrictif)   |
| `include_image_language` | string | Non     | Langues à inclure, ex: `fr,en,null` |

**Réponse** :

```json
{
  "id": 550,
  "backdrops": [
    /* ImageObject[] */
  ],
  "logos": [
    /* ImageObject[] */
  ],
  "posters": [
    /* ImageObject[] */
  ]
}
```

Chaque tableau contient des objets Image (voir [structure commune](#objet-image-structure-commune)).

**⚠️ Impact vérifié du piège `include_image_language`** (film ID 278, Les Évadés) :

| Méthode                                   | Posters  | Backdrops | Logos    |
| ----------------------------------------- | -------- | --------- | -------- |
| `language=fr-FR` seul (PIÈGE)             | 15       | 2         | 6        |
| `include_image_language=fr,en,null` (BON) | 73       | 62        | 14       |
| **Ratio**                                 | **4.9x** | **31x**   | **2.3x** |

Les backdrops sont les plus affectés car la majorité n'ont pas de texte (`iso_639_1: null`) et sont donc exclus par `language=fr-FR`.

---

### IDs externes d'un film

```
GET /3/movie/{movie_id}/external_ids
```

**Réponse** :

```json
{
  "id": 550,
  "imdb_id": "tt0137523",
  "wikidata_id": "Q190050",
  "facebook_id": "FightClub",
  "instagram_id": null,
  "twitter_id": null
}
```

> **Note** : les films n'ont pas de `tvdb_id`. Utiliser `/find/{imdb_id}` pour le cross-reference inverse.

---

### Discover films

```
GET /3/discover/movie
```

Recherche par filtres (pas de texte). Principaux paramètres :

| Paramètre                       | Type   | Description                          |
| ------------------------------- | ------ | ------------------------------------ |
| `language`                      | string | Défaut : `en-US`                     |
| `page`                          | int    | Défaut : `1`                         |
| `sort_by`                       | string | Défaut : `popularity.desc`           |
| `year` / `primary_release_year` | int    | Année de sortie                      |
| `primary_release_date.gte`      | date   | Date min (YYYY-MM-DD)                |
| `primary_release_date.lte`      | date   | Date max (YYYY-MM-DD)                |
| `with_genres`                   | string | IDs genres (`,` = AND, `\|` = OR)    |
| `with_cast`                     | string | IDs personnes (`,` = AND, `\|` = OR) |
| `with_original_language`        | string | ISO 639-1                            |
| `vote_average.gte`              | float  | Note minimum                         |
| `vote_count.gte`                | float  | Nombre de votes minimum              |
| `with_runtime.gte`              | int    | Durée min (minutes)                  |
| `with_runtime.lte`              | int    | Durée max (minutes)                  |
| `include_adult`                 | bool   | Défaut : `false`                     |

**Tri disponible** : `popularity.desc`, `popularity.asc`, `revenue.desc`, `revenue.asc`, `primary_release_date.desc`, `primary_release_date.asc`, `vote_average.desc`, `vote_average.asc`, `vote_count.desc`, `vote_count.asc`, `original_title.asc`, `original_title.desc`, `title.asc`, `title.desc`

**Réponse** : même structure paginée que Search Movies.

---

## Endpoints — Séries TV

### Recherche de séries

```
GET /3/search/tv
```

| Paramètre             | Type    | Requis  | Défaut  | Description                             |
| --------------------- | ------- | ------- | ------- | --------------------------------------- |
| `query`               | string  | **Oui** | —       | Texte de recherche                      |
| `language`            | string  | Non     | `en-US` | Langue des résultats                    |
| `page`                | int     | Non     | `1`     | Page (1-500)                            |
| `first_air_date_year` | int     | Non     | —       | Filtrer par année de première diffusion |
| `year`                | int     | Non     | —       | Filtrer par année (plus large)          |
| `include_adult`       | boolean | Non     | `false` | Inclure le contenu adulte               |

**Réponse** (paginée) :

```json
{
  "page": 1,
  "total_pages": 1,
  "total_results": 5,
  "results": [
    {
      "id": 94997,
      "name": "Titre localisé",
      "original_name": "Original Name",
      "original_language": "en",
      "overview": "Synopsis...",
      "first_air_date": "2022-03-30",
      "poster_path": "/abc.jpg",
      "backdrop_path": "/def.jpg",
      "genre_ids": [10765, 18],
      "origin_country": ["US"],
      "popularity": 789.12,
      "vote_average": 8.7,
      "vote_count": 4567,
      "adult": false
    }
  ]
}
```

> **Différences vs films** : `name` au lieu de `title`, `original_name` au lieu de `original_title`, `first_air_date` au lieu de `release_date`, `origin_country` en plus.

---

### Détails d'une série

```
GET /3/tv/{series_id}
```

| Paramètre            | Emplacement | Type   | Requis  | Description            |
| -------------------- | ----------- | ------ | ------- | ---------------------- |
| `series_id`          | Path        | int    | **Oui** | ID TMDB de la série    |
| `language`           | Query       | string | Non     | Défaut : `en-US`       |
| `append_to_response` | Query       | string | Non     | Sous-requêtes (max 20) |

**Réponse** :

```json
{
  "id": 94997,
  "name": "House of the Dragon",
  "original_name": "House of the Dragon",
  "original_language": "en",
  "overview": "Synopsis...",
  "tagline": "...",
  "status": "Returning Series",
  "type": "Scripted",
  "in_production": true,
  "first_air_date": "2022-08-21",
  "last_air_date": "2024-08-04",
  "number_of_seasons": 2,
  "number_of_episodes": 18,
  "episode_run_time": [],
  "popularity": 789.12,
  "vote_average": 8.4,
  "vote_count": 4567,
  "adult": false,
  "homepage": "https://...",
  "poster_path": "/abc.jpg",
  "backdrop_path": "/def.jpg",
  "origin_country": ["US"],
  "languages": ["en"],

  "genres": [
    { "id": 10765, "name": "Science-Fiction & Fantastique" },
    { "id": 18, "name": "Drame" }
  ],

  "created_by": [
    {
      "id": 237053,
      "name": "Ryan Condal",
      "gender": 2,
      "profile_path": "/abc.jpg",
      "credit_id": "..."
    }
  ],

  "networks": [
    {
      "id": 49,
      "name": "HBO",
      "logo_path": "/tuomPhY2UtuPTqqFnKMVHo0WBfo.png",
      "origin_country": "US"
    }
  ],

  "production_companies": [
    /* ... */
  ],
  "production_countries": [
    /* ... */
  ],
  "spoken_languages": [
    /* ... */
  ],

  "seasons": [
    {
      "id": 134965,
      "name": "Saison 1",
      "overview": "...",
      "air_date": "2022-08-21",
      "season_number": 1,
      "episode_count": 10,
      "poster_path": "/abc.jpg",
      "vote_average": 8.2
    },
    {
      "id": 368923,
      "name": "Saison 2",
      "season_number": 2,
      "episode_count": 8,
      "poster_path": "/def.jpg"
    }
  ],

  "last_episode_to_air": {
    "id": 5261092,
    "name": "The Queen Who Ever Was",
    "air_date": "2024-08-04",
    "episode_number": 8,
    "season_number": 2,
    "episode_type": "finale",
    "runtime": 72,
    "still_path": "/abc.jpg",
    "vote_average": 7.3,
    "vote_count": 89
  },

  "next_episode_to_air": null
}
```

**Valeurs de `status`** : `Returning Series`, `Ended`, `Canceled`, `In Production`, `Planned`.

**Valeurs de `type`** : `Scripted`, `Reality`, `Documentary`, `Miniseries`, `News`, `Talk Show`.

**Champs clés pour le pipeline** : `id`, `name`, `original_name`, `overview`, `first_air_date`, `number_of_seasons`, `genres`, `seasons[]` (pour itérer), `status`, `created_by`, `poster_path`, `backdrop_path`.

> **⚠️ `episode_run_time` est vide/non fiable** pour les séries récentes. Pour la durée, utiliser le champ `runtime` **par épisode** dans les détails de saison (endpoint `/tv/{id}/season/{n}`).

---

### Crédits agrégés d'une série

```
GET /3/tv/{series_id}/aggregate_credits
```

| Paramètre   | Type   | Requis  | Description      |
| ----------- | ------ | ------- | ---------------- |
| `series_id` | int    | **Oui** | ID TMDB          |
| `language`  | string | Non     | Défaut : `en-US` |

**Réponse** :

```json
{
  "id": 94997,
  "cast": [
    {
      "id": 123,
      "name": "Matt Smith",
      "original_name": "Matt Smith",
      "order": 0,
      "total_episode_count": 18,
      "popularity": 45.6,
      "profile_path": "/abc.jpg",
      "gender": 2,
      "known_for_department": "Acting",
      "adult": false,
      "roles": [
        {
          "credit_id": "...",
          "character": "Daemon Targaryen",
          "episode_count": 18
        }
      ]
    }
  ],
  "crew": [
    {
      "id": 456,
      "name": "Ryan Condal",
      "department": "Production",
      "total_episode_count": 18,
      "jobs": [
        {
          "credit_id": "...",
          "job": "Executive Producer",
          "episode_count": 18
        }
      ]
    }
  ]
}
```

> **Différence avec `/credits`** : les crédits agrégés utilisent `roles[]` (cast) et `jobs[]` (crew) qui regroupent les apparitions multiples. `/credits` simple duplique les entrées par épisode.

---

### Images d'une série

```
GET /3/tv/{series_id}/images
```

| Paramètre                | Type   | Requis  | Description                       |
| ------------------------ | ------ | ------- | --------------------------------- |
| `series_id`              | int    | **Oui** | ID TMDB                           |
| `language`               | string | Non     | Filtre par langue (⚠️ restrictif) |
| `include_image_language` | string | Non     | Langues à inclure : `fr,en,null`  |

**Réponse** :

```json
{
  "id": 94997,
  "backdrops": [
    /* ImageObject[] */
  ],
  "logos": [
    /* ImageObject[] */
  ],
  "posters": [
    /* ImageObject[] */
  ]
}
```

---

### IDs externes d'une série

```
GET /3/tv/{series_id}/external_ids
```

**Réponse** :

```json
{
  "id": 94997,
  "imdb_id": "tt11198330",
  "tvdb_id": 371572,
  "tvrage_id": null,
  "freebase_mid": null,
  "freebase_id": null,
  "wikidata_id": "Q104108270",
  "facebook_id": "HouseoftheDragon",
  "instagram_id": "houseofthedragonhbo",
  "twitter_id": "HouseofDragon"
}
```

> **Note** : `tvdb_id` est un **integer** (pas un string), tandis que `imdb_id` est un string avec préfixe `tt`.

---

## Endpoints — Saisons

### Détails d'une saison

```
GET /3/tv/{series_id}/season/{season_number}
```

| Paramètre            | Emplacement | Type   | Requis  | Description                      |
| -------------------- | ----------- | ------ | ------- | -------------------------------- |
| `series_id`          | Path        | int    | **Oui** | ID TMDB de la série              |
| `season_number`      | Path        | int    | **Oui** | Numéro de saison (0 = spéciales) |
| `language`           | Query       | string | Non     | Défaut : `en-US`                 |
| `append_to_response` | Query       | string | Non     | Sous-requêtes (max 20)           |

**Réponse** :

```json
{
  "id": 134965,
  "_id": "62e...",
  "name": "Saison 1",
  "overview": "Synopsis de la saison...",
  "air_date": "2022-08-21",
  "season_number": 1,
  "poster_path": "/abc.jpg",
  "vote_average": 8.2,

  "episodes": [
    {
      "id": 1971015,
      "name": "Les Héritiers du Dragon",
      "overview": "Synopsis de l'épisode...",
      "air_date": "2022-08-21",
      "episode_number": 1,
      "season_number": 1,
      "episode_type": "standard",
      "runtime": 66,
      "still_path": "/abc.jpg",
      "production_code": "",
      "show_id": 94997,
      "vote_average": 7.8,
      "vote_count": 156,

      "crew": [
        {
          "id": 123,
          "name": "Miguel Sapochnik",
          "department": "Directing",
          "job": "Director",
          "profile_path": "/abc.jpg"
        }
      ],

      "guest_stars": [
        {
          "id": 456,
          "name": "Actor Name",
          "character": "Character Name",
          "order": 0,
          "profile_path": "/def.jpg"
        }
      ]
    }
  ]
}
```

**⚠️ Endpoint clé** : un seul appel par saison retourne **tous les épisodes** avec leur crew et guest stars. C'est la méthode la plus efficace — un appel par saison plutôt qu'un par épisode.

**Avec `append_to_response=images`** : ajoute `images: { posters: [ImageObject[]] }` (posters de saison).

---

### Images d'une saison

```
GET /3/tv/{series_id}/season/{season_number}/images
```

**Réponse** :

```json
{
  "id": 134965,
  "posters": [
    /* ImageObject[] — uniquement des posters */
  ]
}
```

> Les images de saison ne retournent que des `posters` (pas de backdrops ni logos).

---

## Endpoints — Épisodes

### Détails d'un épisode

```
GET /3/tv/{series_id}/season/{season_number}/episode/{episode_number}
```

| Paramètre            | Emplacement | Type   | Requis  | Description            |
| -------------------- | ----------- | ------ | ------- | ---------------------- |
| `series_id`          | Path        | int    | **Oui** | ID TMDB de la série    |
| `season_number`      | Path        | int    | **Oui** | Numéro de saison       |
| `episode_number`     | Path        | int    | **Oui** | Numéro d'épisode       |
| `language`           | Query       | string | Non     | Défaut : `en-US`       |
| `append_to_response` | Query       | string | Non     | Sous-requêtes (max 20) |

**Réponse** : même structure qu'un épisode dans la réponse saison (voir ci-dessus).

> **Usage** : généralement inutile si on utilise déjà l'endpoint saison. Utile uniquement pour récupérer les détails d'un seul épisode spécifique.

---

### Images d'un épisode

```
GET /3/tv/{series_id}/season/{season_number}/episode/{episode_number}/images
```

**Réponse** :

```json
{
  "id": 1971015,
  "stills": [
    /* ImageObject[] — uniquement des stills (thumbnails paysage) */
  ]
}
```

> Les images d'épisode ne retournent que des `stills` (pas de posters ni logos).

---

## Endpoints — Utilitaires

### Configuration API

```
GET /3/configuration
```

Retourne les URLs de base pour les images et les tailles disponibles. **À cacher** et rafraîchir tous les quelques jours.

**Réponse** :

```json
{
  "images": {
    "base_url": "http://image.tmdb.org/t/p/",
    "secure_base_url": "https://image.tmdb.org/t/p/",
    "backdrop_sizes": ["w300", "w780", "w1280", "original"],
    "logo_sizes": ["w45", "w92", "w154", "w185", "w300", "w500", "original"],
    "poster_sizes": ["w92", "w154", "w185", "w342", "w500", "w780", "original"],
    "profile_sizes": ["w45", "w185", "h632", "original"],
    "still_sizes": ["w92", "w185", "w300", "original"]
  },
  "change_keys": [
    /* liste des clés modifiables via /changes */
  ]
}
```

---

### Find by External ID

```
GET /3/find/{external_id}?external_source={source}
```

Trouve un contenu TMDB à partir d'un ID externe (IMDb, TVDB, etc.).

| Paramètre         | Emplacement | Type   | Requis  | Description                    |
| ----------------- | ----------- | ------ | ------- | ------------------------------ |
| `external_id`     | Path        | string | **Oui** | L'ID externe (ex: `tt0137523`) |
| `external_source` | Query       | string | **Oui** | Source de l'ID                 |
| `language`        | Query       | string | Non     | Défaut : `en-US`               |

**Sources supportées** : `imdb_id`, `tvdb_id`, `facebook_id`, `instagram_id`, `tiktok_id`, `twitter_id`, `wikidata_id`, `youtube_id`

**Réponse** :

```json
{
  "movie_results": [
    /* MovieObject[] */
  ],
  "tv_results": [
    /* TVObject[] */
  ],
  "person_results": [
    /* PersonObject[] */
  ],
  "tv_episode_results": [
    /* EpisodeObject[] */
  ],
  "tv_season_results": []
}
```

Un seul tableau sera non-vide selon ce que l'ID externe référence.

> **Usage pipeline** : essentiel pour cross-référencer IMDb ↔ TMDB et TVDB ↔ TMDB en un seul appel.

---

### Search Multi

```
GET /3/search/multi
```

Recherche unifiée (films + séries + personnes) en une seule requête.

| Paramètre       | Type    | Requis  | Défaut  | Description            |
| --------------- | ------- | ------- | ------- | ---------------------- |
| `query`         | string  | **Oui** | —       | Texte de recherche     |
| `language`      | string  | Non     | `en-US` | Langue des résultats   |
| `page`          | int     | Non     | `1`     | Page (1-500)           |
| `include_adult` | boolean | Non     | `false` | Inclure contenu adulte |

**Réponse** : paginée, avec `media_type` dans chaque résultat :

- `"movie"` → champs film standard
- `"tv"` → champs série standard
- `"person"` → champs personne + `known_for[]` (tableau de films/séries)

> **⚠️ Toujours vérifier `media_type`** pour parser correctement chaque résultat.

---

### Genres (films)

```
GET /3/genre/movie/list?language=fr-FR
```

**19 genres films** :

| ID    | Nom (fr)        |
| ----- | --------------- |
| 28    | Action          |
| 12    | Aventure        |
| 16    | Animation       |
| 35    | Comédie         |
| 80    | Crime           |
| 99    | Documentaire    |
| 18    | Drame           |
| 10751 | Familial        |
| 14    | Fantastique     |
| 36    | Histoire        |
| 27    | Horreur         |
| 10402 | Musique         |
| 9648  | Mystère         |
| 10749 | Romance         |
| 878   | Science-Fiction |
| 10770 | Téléfilm        |
| 53    | Thriller        |
| 10752 | Guerre          |
| 37    | Western         |

---

### Genres (TV)

```
GET /3/genre/tv/list?language=fr-FR
```

**16 genres TV** :

| ID    | Nom (fr)                      |
| ----- | ----------------------------- |
| 10759 | Action & Adventure            |
| 16    | Animation                     |
| 35    | Comédie                       |
| 80    | Crime                         |
| 99    | Documentaire                  |
| 18    | Drame                         |
| 10751 | Familial                      |
| 10762 | Kids                          |
| 9648  | Mystère                       |
| 10763 | News                          |
| 10764 | Reality                       |
| 10765 | Science-Fiction & Fantastique |
| 10766 | Soap                          |
| 10767 | Talk                          |
| 10768 | War & Politics                |
| 37    | Western                       |

> **⚠️ Les IDs de genres sont différents entre films et TV** pour des concepts similaires (ex: Action film = `28`, Action TV = `10759`). Certains IDs sont partagés (16, 35, 80, 99, 18, 10751, 9648, 37).

---

### Certifications

```
GET /3/certification/movie/list
GET /3/certification/tv/list
```

**Certifications FR (films)** : `NR` (0), `TP` (1), `12` (2), `16` (3), `18` (4)

**Certifications FR (TV)** : `NR`, `TP`, `10`, `12`, `16`, `18`

Le champ `order` indique la sévérité (0 = non classé, plus haut = plus restrictif).

---

## Gestion des erreurs

### Format de réponse d'erreur

> **⚠️ Le `status_code` est un code interne TMDB**, pas le code HTTP. Toujours vérifier les deux.

**Exemple réel — Clé API invalide** (HTTP 401) :

```json
{
  "status_code": 7,
  "status_message": "Invalid API key: You must be granted a valid key.",
  "success": false
}
```

**Exemple réel — Ressource non trouvée** (HTTP 404) :

```json
{
  "success": false,
  "status_code": 34,
  "status_message": "The resource you requested could not be found."
}
```

**Attention** : une recherche sans résultat retourne HTTP **200** avec `results: []`, pas une erreur 404. Le code 404 n'est retourné que pour un ID spécifique invalide (ex: `/movie/9999999`).

### Codes d'erreur principaux

| Code TMDB | HTTP | Description                         | Action pipeline                |
| --------- | ---- | ----------------------------------- | ------------------------------ |
| 7         | 401  | Clé API invalide                    | Vérifier config, abort         |
| 10        | 401  | Clé API suspendue                   | Vérifier compte, abort         |
| 25        | 429  | Rate limit dépassé                  | Retry avec exponential backoff |
| 34        | 404  | Ressource non trouvée               | Skip, log "not found"          |
| 6         | 404  | ID invalide                         | Skip, log warning              |
| 5         | 422  | Paramètres incorrects               | Fix la requête, log error      |
| 22        | 400  | Page invalide (1-500)               | Plafonner à 500                |
| 27        | 400  | Trop de append_to_response (max 20) | Réduire le nombre              |
| 9         | 503  | Service temporairement indisponible | Retry avec backoff             |
| 11        | 500  | Erreur interne TMDB                 | Retry avec backoff             |
| 24        | 504  | Timeout backend                     | Retry avec backoff             |
| 46        | 503  | Maintenance API                     | Retry plus tard                |

### Codes retryables

HTTP `429`, `500`, `502`, `503`, `504` → retry avec exponential backoff (max 3 tentatives).

### Codes fatals

HTTP `401`, `403` → problème d'authentification, ne pas retrier.

---

## Stratégie d'appels optimale

### Pour un film (1-2 appels)

```
1. GET /3/search/movie?query={title}&year={year}&language=fr-FR
   → Récupère l'ID TMDB

2. GET /3/movie/{id}?language=fr-FR
     &append_to_response=credits,images,external_ids,release_dates
     &include_image_language=fr,en,null
   → Détails + casting + images + IDs IMDb + classification
```

**Total : 2 appels** pour toutes les métadonnées d'un film.

### Pour une série TV (2 + N appels, N = nombre de saisons)

```
1. GET /3/search/tv?query={title}&first_air_date_year={year}&language=fr-FR
   → Récupère l'ID TMDB

2. GET /3/tv/{id}?language=fr-FR
     &append_to_response=aggregate_credits,images,external_ids,content_ratings
     &include_image_language=fr,en,null
   → Détails + casting + images + IDs IMDb/TVDB + classification

3. Pour chaque saison :
   GET /3/tv/{id}/season/{n}?language=fr-FR&append_to_response=images
   → Liste des épisodes (titres, dates, crew) + posters de saison
```

**Total : 2 + N appels** (N = nombre de saisons) pour toutes les métadonnées d'une série.

### Exemple concret : série avec 5 saisons

| Étape | Appel                                           | Données récupérées            |
| ----- | ----------------------------------------------- | ----------------------------- |
| 1     | `search/tv?query=...`                           | ID TMDB                       |
| 2     | `tv/{id}?append_to_response=...`                | Détails + cast + images + IDs |
| 3-7   | `tv/{id}/season/1..5?append_to_response=images` | Épisodes + posters saison     |

**7 appels au total** au lieu de potentiellement 50+ sans `append_to_response`.

### Sélection de la meilleure image

Prioriser par langue pour la pertinence :

1. `fr` (ou langue configurée) — image localisée
2. `en` — fallback anglais
3. `null` — image neutre (sans texte)
4. Autres langues

Au sein d'une même langue, trier par `vote_average` descendant.

---

## Résumé des schémas de réponse

### Objet Film (search/discover)

| Champ               | Type        | Description         |
| ------------------- | ----------- | ------------------- |
| `id`                | int         | ID TMDB             |
| `title`             | string      | Titre localisé      |
| `original_title`    | string      | Titre original      |
| `original_language` | string      | ISO 639-1           |
| `overview`          | string      | Synopsis localisé   |
| `release_date`      | string      | YYYY-MM-DD          |
| `poster_path`       | string/null | Chemin poster       |
| `backdrop_path`     | string/null | Chemin backdrop     |
| `genre_ids`         | int[]       | IDs de genres       |
| `popularity`        | float       | Score de popularité |
| `vote_average`      | float       | Note moyenne (0-10) |
| `vote_count`        | int         | Nombre de votes     |
| `adult`             | bool        | Contenu adulte      |
| `video`             | bool        | A du contenu vidéo  |

### Objet Série TV (search)

| Champ               | Type        | Description         |
| ------------------- | ----------- | ------------------- |
| `id`                | int         | ID TMDB             |
| `name`              | string      | Titre localisé      |
| `original_name`     | string      | Titre original      |
| `original_language` | string      | ISO 639-1           |
| `overview`          | string      | Synopsis localisé   |
| `first_air_date`    | string      | YYYY-MM-DD          |
| `poster_path`       | string/null | Chemin poster       |
| `backdrop_path`     | string/null | Chemin backdrop     |
| `genre_ids`         | int[]       | IDs de genres       |
| `origin_country`    | string[]    | ISO 3166-1          |
| `popularity`        | float       | Score de popularité |
| `vote_average`      | float       | Note moyenne (0-10) |
| `vote_count`        | int         | Nombre de votes     |
| `adult`             | bool        | Contenu adulte      |

### Objet Image

| Champ          | Type        | Description                         |
| -------------- | ----------- | ----------------------------------- |
| `file_path`    | string      | Chemin relatif (ajouter à base URL) |
| `aspect_ratio` | float       | Ratio largeur/hauteur               |
| `width`        | int         | Largeur en pixels                   |
| `height`       | int         | Hauteur en pixels                   |
| `iso_639_1`    | string/null | Langue (null = neutre)              |
| `vote_average` | float       | Note communautaire                  |
| `vote_count`   | int         | Nombre de votes                     |

### Objet Cast (crédits film)

| Champ                  | Type        | Description                   |
| ---------------------- | ----------- | ----------------------------- |
| `id`                   | int         | ID personne                   |
| `name`                 | string      | Nom                           |
| `original_name`        | string      | Nom original                  |
| `character`            | string      | Personnage joué               |
| `order`                | int         | Ordre d'affiche (0 = premier) |
| `profile_path`         | string/null | Photo de profil               |
| `gender`               | int         | 0=?, 1=F, 2=M, 3=NB           |
| `known_for_department` | string      | Département principal         |
| `popularity`           | float       | Score de popularité           |

### Objet Crew (crédits film)

| Champ          | Type        | Description                   |
| -------------- | ----------- | ----------------------------- |
| `id`           | int         | ID personne                   |
| `name`         | string      | Nom                           |
| `department`   | string      | Département (ex: "Directing") |
| `job`          | string      | Rôle (ex: "Director")         |
| `profile_path` | string/null | Photo de profil               |

### Objet Épisode (dans réponse saison)

| Champ            | Type        | Description                        |
| ---------------- | ----------- | ---------------------------------- |
| `id`             | int         | ID TMDB épisode                    |
| `name`           | string      | Titre localisé                     |
| `overview`       | string      | Synopsis localisé                  |
| `air_date`       | string      | YYYY-MM-DD                         |
| `episode_number` | int         | Numéro d'épisode                   |
| `season_number`  | int         | Numéro de saison                   |
| `episode_type`   | string      | `standard`, `finale`, `mid_season` |
| `runtime`        | int         | Durée en minutes                   |
| `still_path`     | string/null | Thumbnail paysage                  |
| `vote_average`   | float       | Note moyenne                       |
| `vote_count`     | int         | Nombre de votes                    |
| `crew`           | array       | Crew spécifique à l'épisode        |
| `guest_stars`    | array       | Guest stars de l'épisode           |

---

## Certifications FR — Extraction

Pour les **films**, la certification est dans `release_dates` (pas un champ direct) :

```
GET /3/movie/{id}?append_to_response=release_dates
```

Extraire la certification française :

```python
for entry in data["release_dates"]["results"]:
    if entry["iso_3166_1"] == "FR":
        for rd in entry["release_dates"]:
            if rd["type"] == 3 and rd["certification"]:  # 3 = theatrical
                return rd["certification"]  # ex: "TP", "12", "16", "18"
```

**Types de sortie** (`type`) : 1=Première, 2=Theatrical (limité), 3=Theatrical, 4=Digital, 5=Physical, 6=TV.

> Seule la sortie theatrale (type 3) porte généralement la certification. Les sorties physiques/TV ont souvent une certification vide.

Pour les **séries TV**, utiliser `content_ratings` :

```
GET /3/tv/{id}?append_to_response=content_ratings
```

```python
for entry in data["content_ratings"]["results"]:
    if entry["iso_3166_1"] == "FR":
        return entry["rating"]  # ex: "12", "16"
```

Structure plus simple que les films (pas de nesting par type de sortie).

---

## Edge cases vérifiés (tests live 2026-04-10)

| #   | Comportement                          | Détail                                                                                                      |
| --- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 1   | `year` n'est pas un filtre strict     | Booste la pertinence mais retourne des résultats d'autres années. Filtrer côté client.                      |
| 2   | Recherche vide = HTTP 200             | `{"results": [], "total_results": 0}` — pas de 404. Vérifier `len(results)`.                                |
| 3   | Apostrophes/accents dans la recherche | Fonctionnent avec URL encoding standard (`%27`, `%C3%A9`).                                                  |
| 4   | `episode_run_time` est vide/déprécié  | Tableau vide `[]` pour les séries récentes. Utiliser `runtime` par épisode dans season details.             |
| 5   | Piège images : 5x à 31x moins         | Sans `include_image_language`, backdrops sévèrement réduits (null = pas de texte = exclu).                  |
| 6   | Genres TV partiellement non traduits  | `language=fr-FR` : "Kids", "News", "Reality", "Soap", "Talk", "War & Politics" restent en anglais.          |
| 7   | `Find` retourne toujours 5 tableaux   | `movie_results`, `tv_results`, `person_results`, `tv_episode_results`, `tv_season_results` — même vides.    |
| 8   | Crédits TV agrégés ≠ crédits film     | TV `aggregate_credits` utilise `roles[]`/`jobs[]` (multi-rôles groupés). Film `credits` a des champs plats. |
| 9   | Certifications film vs TV             | Film : nested dans `release_dates` → filtre par `type==3`. TV : flat dans `content_ratings`.                |
| 10  | `_id` MongoDB dans réponse saison     | Champ `_id` (string ObjectID) unique aux réponses de saison, absent des autres endpoints.                   |
| 11  | `Search multi` : `media_type` requis  | Résultats mixtes — toujours vérifier `media_type` pour parser correctement (champs différents).             |
| 12  | `runtime` fiable par épisode seul     | Le `runtime` dans `/tv/{id}/season/{n}` → `episodes[]` est fiable (ex: 41 min pour Mandalorian S01E01).     |

---

## Annexe — Daily ID Exports

TMDB fournit des exports quotidiens de tous les IDs (sans auth) :

```
https://files.tmdb.org/p/exports/movie_ids_MM_DD_YYYY.json.gz
https://files.tmdb.org/p/exports/tv_series_ids_MM_DD_YYYY.json.gz
https://files.tmdb.org/p/exports/person_ids_MM_DD_YYYY.json.gz
```

- Format : gzippé, JSON délimité par lignes (un objet JSON par ligne, PAS un tableau)
- Champs : `id`, `original_title`/`original_name`, `popularity`, `adult`, `video`
- Mis à jour quotidiennement ~7:00 UTC, disponible ~8:00 UTC
- Retenus 3 mois puis supprimés
