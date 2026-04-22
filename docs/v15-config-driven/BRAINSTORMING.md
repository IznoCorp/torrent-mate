# V15 — CONFIG-DRIVEN ARCHITECTURE : Brainstorming

> Séparer totalement la nomenclature utilisateur (noms de disques, dossiers, catégories) du code source. Code manipule uniquement des IDs abstraits ; taxonomie réelle dans `config.json5`.

## Contexte

**État actuel après V14** :

- `personalscraper/dispatch/disk_scanner.py` : `DISK_CATEGORIES` dict hardcodant "Disk1..Disk4" + catégories en français ("films", "series animations"...).
- `personalscraper/config.py` : défauts `/Volumes/Disk{1..4}/medias` dans `Settings`.
- `personalscraper/genre_mapper.py` : mapping TMDB/TVDB → noms de catégories en dur.
- Noms de catégories référencés en dur dans la logique de dispatch, scraper, verify, enforce.
- Tests : 33 occurrences `/Volumes/Disk*`, 156 noms de disques, 245 noms de catégories — tous en lien avec la config perso du mainteneur.

**Conséquences** :

- Repo non partageable : un autre utilisateur qui renommerait ses dossiers casse le code.
- Nomenclature française ou structure de disques figées dans le code.
- Tests non portables en CI (ont nécessité un fix d'urgence `tmp_path`/`get_disk_status` mock récemment).

**Objectif V15** :
Le code source ne contient aucun nom de dossier, chemin, ou catégorie spécifique à l'utilisateur. Toute la nomenclature est centralisée dans un `config.json5` unique, avec un `config.example.json5` versionné comme template.

## Décisions prises

### D1 — Format de config : JSON5

Choisi : **JSON5** (`config.json5`).

- Support des commentaires `//` et `/* */` (impossible en JSON strict).
- Parsing via le package `json5` (PyPI, stable).
- Les commentaires du `config.example.json5` servent de **source des prompts** pour la commande `init-config` interactive (voir D7).
- Décliné vs YAML : l'utilisateur préfère la syntaxe JSON ; JSON5 donne le meilleur des deux mondes.

### D2 — Emplacement du fichier config

- **Défaut** : `./config.json5` à la racine du repo (comme `.env`/`.env.example`).
- **Override CLI** : `personalscraper --config /path/to/config.json5 <command>`.
- **Override env** : variable `PERSONALSCRAPER_CONFIG=/path/to/config.json5`.
- `config.example.json5` est versionné ; `config.json5` est **gitignored** (peut contenir des chemins absolus, structure personnelle).

### D3 — Séparation config / secrets

- `.env` garde **uniquement les secrets** : `TMDB_API_KEY`, `TVDB_API_KEY`, tokens Telegram/qBittorrent, etc.
- `config.json5` garde **toute la structure** : disques, catégories, mappings de genres, paths staging/torrents, seuils.
- Aucun secret dans `config.json5` (fichier destiné à être partageable/commité par l'utilisateur si privé).

### D4 — IDs abstraits dans le code

**Liste validée** (IDs internes, stables, en anglais) :

| ID                     | Label par défaut       |
| ---------------------- | ---------------------- |
| `movies`               | `movies`               |
| `movies_animation`     | `movies animation`     |
| `movies_documentary`   | `movies documentary`   |
| `tv_shows`             | `tv shows`             |
| `tv_shows_animation`   | `tv shows animation`   |
| `tv_shows_documentary` | `tv shows documentary` |
| `anime`                | `anime`                |
| `audiobooks`           | `audiobooks`           |
| `concerts`             | `concerts`             |
| `theater`              | `theater`              |
| `tv_programs`          | `tv programs`          |

**Règle** : label par défaut = ID avec `_` → espace. L'utilisateur peut override chaque label via `config.json5`.

**Many-to-one** : plusieurs IDs peuvent pointer vers le même dossier physique. Exemple utilisateur qui ne sépare pas animés et films classiques :

```json5
{
  categories: {
    movies: { folder_name: "Films" },
    movies_animation: { folder_name: "Films" }, // même dossier
    movies_documentary: { folder_name: "Films documentaires" },
  },
}
```

Le code utilise l'ID pour la logique (quel genre TMDB → quel ID), puis résout l'ID vers le dossier via config.

### D5 — Structure disques : nombre variable

- Pas de limite figée à 4 disques.
- Configuration sous forme de **liste** dans `config.json5` :

```json5
{
  "disks": [
    { "id": "disk_a", "path": "/path/to/disk_a", "categories": ["movies", "tv_shows", ...] },
    { "id": "disk_b", "path": "/path/to/disk_b", "categories": ["tv_shows", "anime"] }
  ]
}
```

- L'`id` est choisi librement par l'utilisateur (clef de lecture dans logs, référence dans CLI `--disk disk_a`).
- Les IDs de catégories dans `categories[]` doivent exister dans la section `categories` globale.

### D6 — Genre mapping dans config

- Le mapping TMDB genre → `category_id` et TVDB genre → `category_id` vit dans `config.json5`.
- Permet à l'utilisateur de choisir comment router les genres :

```json5
{
  genre_mapping: {
    tmdb: {
      Animation: "movies_animation", // ou "anime" au choix
      Documentary: "movies_documentary",
      Action: "movies",
      // ...
    },
    tvdb: {
      Anime: "anime",
      Documentary: "tv_shows_documentary",
      // ...
    },
  },
}
```

- Le code n'a aucune table TMDB/TVDB codée en dur — seulement la logique de résolution.

### D7 — `init-config` command

Deux chemins de setup pour nouvel utilisateur :

**Automatique interactive** :

```bash
personalscraper init-config
```

- Lit `config.example.json5`.
- Extrait les commentaires `//` (qui deviennent les descriptions/prompts).
- Pose chaque question dans l'ordre, avec la valeur par défaut du template.
- Écrit `config.json5` personnalisé.

**Manuel** :

```bash
cp config.example.json5 config.json5
# édite à la main
```

### D8 — CLI output hybride

- **Logs structurés** (`structlog` → fichier JSON) : IDs uniquement (`"category_id": "movies_animation"`).
- **Affichage Rich humain** : labels utilisateur depuis config (`Films animations`) + ID en tag discret si utile.
- Rationale : logs machine-parseables, affichage humain personnalisé.

### D9 — Tests : fixture pytest

- Une fixture `test_config` fournit un `Config` synthétique :
  - Disques : `drive_a`, `drive_b`, `drive_c` (IDs neutres, 3 disques pour tester variable count).
  - Catégories : les IDs de la liste D4, labels = `"cat_movies"`, `"cat_tv_shows"`... (ou similaires).
  - Paths : rootés dans `tmp_path`.
- Tous les tests utilisent cette fixture — aucune valeur en rapport avec la config perso.
- `tests/conftest.py` expose la fixture ; fichiers par fixture optionnels si complexité.

### D10 — Scope complet

Audit intégral du projet. Tous les fichiers contenant :

- Noms de dossiers (`"films"`, `"series"`, ...) → remplacés par IDs ou lectures de config.
- Noms de disques (`"Disk1"`, `/Volumes/Disk1/medias`) → lecture de config.
- Références hardcodées à la structure 4-disques → logique agnostique.
- Tests référençant ces valeurs → fixture.

Inclut : code source, tests, docs (CLAUDE.md, INSTALLATION.md, CONFIGURATION.md, MANUAL.md, README.md, reference docs), `Makefile`, scripts auxiliaires.

## Contraintes techniques

1. **JSON5 parsing** : nouvelle dépendance `json5>=0.9.0` (ou `pyjson5` plus rapide).
2. **Pydantic** : le modèle `Config` remplace/complète `Settings` de Pydantic Settings. Validation stricte (IDs de catégories référencées dans `disks` doivent exister).
3. **Backward compatibility** : `config.json5` doit être créé à partir de la config actuelle avant premier run post-V15. Script de migration `init-config --from-current` ?
4. **Performance** : config parsée une fois au démarrage, injectée dans les modules. Pas de re-parsing répété.
5. **Test isolation** : jamais lire `config.json5` réel en test — fixture uniquement.
6. **CLI override** : `--config` doit être positionné avant la sous-commande (Typer top-level option).
7. **Migration progressive impossible** : V15 est un breaking change complet — `config.json5` devient obligatoire.

## Flux proposé

### Chargement de la config au démarrage

```
CLI invoked
    → parse global --config flag OR PERSONALSCRAPER_CONFIG env OR ./config.json5
    → if not found: error + hint "run: personalscraper init-config"
    → load .env (secrets only)
    → validate Config via Pydantic (IDs cohérents, paths accessibles si strict mode)
    → pass Config + Settings (secrets) to CLI commands
```

### Résolution ID → label / path

```
dispatch_movie("movies_animation", file)
    → config.categories["movies_animation"].folder_name  → "Films animations"
    → find disk where "movies_animation" in disk.categories
    → dest = disk.path / folder_name
```

### init-config flow

```
user runs: personalscraper init-config
    → read config.example.json5 (parsed with comment retention)
    → for each entry in example:
        → print comment (question)
        → show default value
        → prompt user, accept empty to use default
    → write config.json5
    → warn if secrets still in .env.example (prompt to fill .env too)
```

### Tests setup

```
pytest
    → conftest.py: test_config fixture (synthetic Config)
    → tests import IDs from personalscraper.categories (constants module)
    → fixtures provide tmp_path-based disks
    → no test ever reads real config.json5 or mentions "films"/"Disk1"
```

## Points de design à trancher

_(Vide — tout tranché en brainstorming.)_
