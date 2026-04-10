# V4 — VERIFY : Brainstorming

> Quality gate : vérification, correction et qualification des médias scrapés avant dispatch

## Contexte

Après V3 (scrape), les dossiers dans `001-MOVIES/` et `002-TVSHOWS/` devraient être au format
attendu : nommage correct, NFO valide, artwork présent, catégorie identifiée. Mais des erreurs
sont possibles : match API échoué, artwork manquant, nommage partiel, catégorie non détectée.

V4-VERIFY est un **quality gate** entre le scraping et le dispatch (V5). Il inspecte chaque dossier,
tente de corriger les problèmes auto-corrigeables, puis bloque les dossiers qui restent invalides.

Le dispatch (V5) ne traitera que les dossiers validés par V4.

## Décisions prises

### Scope de vérification

Chaque dossier média est vérifié sur ces critères :

| Critère                | Films                                                                                         | Séries                                                                                | Sévérité                               |
| ---------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------- |
| Fichier vidéo présent  | Au moins 1 `.mkv`/`.mp4`/etc.                                                                 | Au moins 1 fichier vidéo                                                              | ERROR                                  |
| Nommage dossier        | `Title (Year)/`                                                                               | `Show Name (Year)/`                                                                   | ERROR (auto-corrigeable si NFO existe) |
| NFO présent            | `Title.nfo` existe                                                                            | `tvshow.nfo` existe                                                                   | ERROR                                  |
| NFO valide             | XML parseable, tags obligatoires présents                                                     | XML parseable, tags obligatoires présents                                             | ERROR                                  |
| IDs dans le NFO        | `<uniqueid type="tmdb">` et `<uniqueid type="imdb">` présents                                 | `<uniqueid type="tvdb">` présent au minimum                                           | ERROR                                  |
| Artwork poster         | `Title-poster.jpg` existe                                                                     | `poster.jpg` existe                                                                   | WARNING                                |
| Artwork landscape      | `Title-landscape.jpg` existe                                                                  | `landscape.jpg` existe                                                                | WARNING                                |
| Season posters         | —                                                                                             | `season{NN}-poster.jpg` pour chaque saison                                            | WARNING                                |
| Structure saisons      | —                                                                                             | `Saison XX/` avec épisodes `S01E01 - Titre.ext`                                       | ERROR                                  |
| Épisodes NFO           | —                                                                                             | `.nfo` par épisode dans `Saison XX/`                                                  | WARNING                                |
| Streamdetails dans NFO | `<fileinfo><streamdetails>` présent                                                           | Idem dans les NFO épisode                                                             | WARNING                                |
| Catégorie identifiée   | Genre TMDB → catégorie dispatch (film, film animation, film documentaire, spectacle, theatre) | Genre → catégorie (série, série animation, série documentaire, série anime, emission) | ERROR                                  |

### Mode d'exécution : intégré au pipeline ET standalone

- **Intégré** : le pipeline appelle `verify()` après `scrape()` et avant `dispatch()`
- **Standalone** : commande CLI `personalscraper verify [--dry-run] [--verbose] [--fix]`
- La commande standalone permet de vérifier des dossiers à tout moment (ex: après ajout manuel)

### Stratégie "correct then gate"

**Passe 1 — Correction automatique** (si `--fix` ou mode pipeline) :

- Nommage dossier incorrect mais NFO avec titre/année → renommer le dossier
- Fichier vidéo mal nommé mais pattern reconnaissable → renommer selon NamingPatterns
- Artwork au mauvais emplacement (ex: `poster.jpg` au lieu de `Title-poster.jpg` pour un film) → renommer
- Épisodes non renommés mais pattern S01E01 reconnaissable → renommer via NamingPatterns

**Passe 2 — Validation** :

- Après corrections, re-vérifier tous les critères
- Si des ERRORs persistent → bloquer CE dossier (pas les autres)
- Les dossiers bloqués apparaissent dans le rapport et les notifications (V6)
- Les dossiers avec uniquement des WARNINGs passent quand même au dispatch

### Catégorisation (qualification)

La catégorie du média détermine le dossier de destination sur les disques :

**Films** (basé sur les genres TMDB) :

| Catégorie cible     | Genres TMDB déclencheurs                        |
| ------------------- | ----------------------------------------------- |
| films               | Tous les films par défaut                       |
| films animations    | Genre ID 16 (Animation)                         |
| films documentaires | Genre ID 99 (Documentaire)                      |
| spectacles          | Genre "spectacle" ou tag spécifique (à définir) |
| theatres            | Genre "théâtre" ou tag spécifique (à définir)   |

**Séries** (basé sur les genres TMDB/TVDB + origin_country) :

| Catégorie cible      | Critères                                 |
| -------------------- | ---------------------------------------- |
| series               | Toutes les séries par défaut             |
| series animations    | Genre ID 16 (Animation) — hors anime     |
| series documentaires | Genre ID 99 (Documentaire)               |
| series animes        | Animation + origin_country contient "JP" |
| emissions            | Genres Reality/Talk/News                 |

> Note : cette logique de catégorisation est partagée avec V5 (dispatch) qui l'utilise pour
> déterminer le dossier de destination. V4 vérifie juste que la catégorie EST identifiée.
> Le mapping genre → catégorie sera dans un module partagé `genre_mapper.py`.

### Résultat de vérification

Chaque dossier vérifié produit un `VerifyResult` :

```python
@dataclass
class VerifyResult:
    media_path: Path
    media_type: str            # "movie" | "tvshow"
    category: str | None       # "films", "series animes", etc. — None si non identifié
    status: str                # "valid", "fixed", "blocked"
    errors: list[str]          # Erreurs bloquantes restantes
    warnings: list[str]        # Avertissements non bloquants
    fixes_applied: list[str]   # Corrections automatiques effectuées
```

## Contraintes techniques

1. **Réutiliser `NamingPatterns`** de V3 pour vérifier les noms de fichiers
2. **Parser le XML NFO** avec `xml.etree.ElementTree` (stdlib, déjà utilisé par V3)
3. **Le genre_mapper doit gérer les genres TMDB ET TVDB** — les IDs sont différents (cf TMDB-API.md et TVDB-API.md)
4. **Dry-run** : `--dry-run` affiche les problèmes et corrections proposées sans rien modifier
5. **Pas de dépendance réseau** : V4 travaille uniquement sur les fichiers locaux (NFO, artwork, vidéo)
6. **Performance** : vérification d'un dossier doit être rapide (pas de re-scraping, juste check fichiers)
