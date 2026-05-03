# Configuration

Guide complet de configuration pour PersonalScraper.

**Deux sources de configuration :**

- **`config/`** — Fichiers JSON5 (chemins, disques, seuils, préférences). Créé via `personalscraper init-config`.
- **`.env`** — Uniquement les credentials (clés API, mots de passe, tokens). Template : `.env.example`.

> Voir aussi : [INSTALLATION.md](INSTALLATION.md) (installation) | [MANUAL.md](MANUAL.md) (utilisation)

## Mise en place

```bash
# 1. Créer la configuration
personalscraper init-config

# 2. Configurer les credentials
cp .env.example .env
# Éditer .env pour renseigner les clés API
```

Le fichier `.env` est chargé automatiquement par le pipeline via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). Il contient **uniquement** les secrets (clés API, mots de passe). Toute la configuration structurelle (chemins, disques, seuils) est dans `config/`.

> **Ne jamais commiter `.env` ni `config/`** — ils sont dans `.gitignore`. Utiliser `.env.example` et `config.example/` comme templates de référence.

---

## qBittorrent

Variables de connexion à l'interface Web de qBittorrent (Ingest).

| Variable        | Défaut      | Description                           |
| --------------- | ----------- | ------------------------------------- |
| `QBIT_HOST`     | `localhost` | Hostname ou IP du serveur qBittorrent |
| `QBIT_PORT`     | `8081`      | Port de l'interface Web API           |
| `QBIT_USERNAME` | `""`        | Nom d'utilisateur Web UI              |
| `QBIT_PASSWORD` | _(vide)_    | Mot de passe Web UI                   |

### Comment configurer

1. Ouvrir qBittorrent > **Preferences** > **Web UI**
2. Cocher **"Enable the Web User Interface (Remote control)"**
3. Configurer le port (par défaut `8080`, ici `8081`)
4. Définir un nom d'utilisateur et un mot de passe
5. Reporter ces valeurs dans `.env`

```ini
QBIT_HOST=localhost
QBIT_PORT=8081
QBIT_USERNAME=admin
QBIT_PASSWORD=mon_mot_de_passe
```

> **Accès distant :** si qBittorrent tourne sur une autre machine, utiliser son IP (ex: `QBIT_HOST=192.168.1.100`).

---

## Chemins

> **Depuis la version 0.4.0**, tous les chemins du pipeline
> (`torrent_complete_dir`, `staging_dir`, `data_dir`, disques de stockage)
> sont définis dans `config.json5`. Les anciennes variables d'environnement
> `TORRENT_COMPLETE_DIR`, `STAGING_DIR`, `DISK1_DIR`…`DISK4_DIR` **ont été
> retirées** — les positionner dans `.env` n'a plus aucun effet.
>
> Voir la section [Configuration config.json5](#configuration-configjson5)
> ci-dessous pour la nouvelle disposition (`paths:` et `disks:`).

> **Attention aux espaces** dans les chemins définis dans `config.json5` :
> json5 accepte les espaces dans les valeurs de chaîne sans quoting
> supplémentaire, mais chaque invocation shell qui consomme ces chemins
> doit les placer entre guillemets.

---

## Configuration config/

Depuis la version 0.9.0, les chemins, la disposition du staging et les seuils
sont définis dans le dossier `config/` (format v2 split). Le `.env` ne contient
que les credentials.

### `paths.staging_dir`

Chemin vers le répertoire de staging racine où les médias arrivent pour traitement.

- **Exemple (config.example/paths.json5) :** `./staging/` (relatif, portable — se résout en `<repo>/staging/` en CI)
- **Pas de défaut en production** — à définir selon votre environnement (par exemple `/Volumes/<disk>/staging/`).
- Les chemins relatifs sont résolus en chemins absolus au chargement via `Path.expanduser().resolve()`.
- L'arborescence de staging est créée automatiquement au premier lancement — aucun `mkdir` manuel requis.

### `paths.data_dir`

Chemin vers le répertoire d'état du pipeline (index, locks, cache d'analyse).

- **Défaut :** `./.data` (résolu relativement à la racine de la config au chargement).
- **Exemple** : peut être déplacé vers `<staging_dir>/.data` ou tout autre emplacement via `config.json5`.
- Cette valeur est **explicite** dans `config.json5` — elle peut être déplacée avec
  une seule modification de config.
- Différent de `staging_dir`.

### `staging_dirs`

**Requis** (depuis la version 0.4.0). Définit la disposition des sous-répertoires de la zone de staging.

Chaque entrée :

| Champ       | Type         | Requis | Description                                                                                  |
| ----------- | ------------ | ------ | -------------------------------------------------------------------------------------------- |
| `id`        | int [0–999]  | oui    | Préfixe numérique. Utilisé pour calculer le nom du dossier : `f"{id:03d}-{name.upper()}"`.   |
| `name`      | string       | oui    | Label kebab-case (ex: `"movies"`, `"tv-shows"`). Mis en majuscules pour le dossier.          |
| `file_type` | string\|null | non    | Valeur enum FileType : `"movie"`, `"tvshow"`, `"ebook"`, `"audio"`, `"app"`, `"other"`.      |
| `role`      | string\|null | non    | Rôle fonctionnel. Seul `"ingest"` est défini. Exactement une entrée doit avoir cette valeur. |

**Règles de validation :**

- Les valeurs `id` doivent être uniques parmi toutes les entrées.
- Exactement une entrée doit avoir `role: "ingest"`.
- `file_type` doit être un membre valide de l'enum FileType si défini.

**Exemple :**

```json5
staging_dirs: [
  {id: 1,  name: "movies",  file_type: "movie"},
  {id: 97, name: "temp",    file_type: null,   role: "ingest"},
],
```

---

## TMDB (The Movie Database)

Clé API pour la recherche de métadonnées films et séries (Scrape).

| Variable       | Défaut   | Description               |
| -------------- | -------- | ------------------------- |
| `TMDB_API_KEY` | _(vide)_ | Clé API v3 (Bearer token) |

### Comment obtenir la clé

1. Créer un compte sur [themoviedb.org](https://www.themoviedb.org/signup)
2. Aller dans **Settings** > **API** ([lien direct](https://www.themoviedb.org/settings/api))
3. Cliquer **"Create"** > choisir **"Developer"**
4. Remplir le formulaire :
   - **Type of use** : Personal
   - **Application name** : PersonalScraper (ou autre)
   - **Application URL** : (n'importe quelle URL, ex: `https://github.com`)
   - **Application summary** : Personal media library management
5. Accepter les conditions d'utilisation
6. Copier la **"API Key (v3 auth)"** (pas le token Bearer v4)

```ini
TMDB_API_KEY=abcdef1234567890abcdef1234567890
```

> **Limites** : TMDB est gratuit et sans quota strict, mais respecte un rate limit d'environ 40 requetes/10 secondes. Le pipeline gère automatiquement les retries via `tenacity`.

> **Langue** : le pipeline utilise `fr-FR` par défaut pour les titres et descriptions. Les images sont toujours demandées avec `include_image_language=fr,en,null` pour maximiser les résultats.

---

## TVDB (TheTVDB)

Clé API pour la recherche de métadonnées séries, épisodes, et anime (Scrape).

| Variable       | Défaut   | Description                      |
| -------------- | -------- | -------------------------------- |
| `TVDB_API_KEY` | _(vide)_ | Clé API v4 (Negotiated Contract) |

### Comment obtenir la clé

1. Créer un compte sur [thetvdb.com](https://thetvdb.com/auth/register)
2. Aller dans **Dashboard** > **Account** > **API Keys** ([lien direct](https://thetvdb.com/dashboard/account/apikeys))
3. Cliquer **"Create a new API key"**
4. Remplir le formulaire :
   - **Name** : PersonalScraper
   - **API key type** : choisir **"Negotiated Contract"** (gratuit pour usage personnel < 50k$ revenus)
   - **PIN** : laisser vide (pas nécessaire pour Negotiated Contract)
5. Copier la clé API générée

```ini
TVDB_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

> **Important** : il existe deux types de clés TVDB :
>
> - **Negotiated Contract** (gratuit, pas de PIN) — c'est celui-ci qu'il faut
> - **User Subscription** (nécessite un PIN) — pas utilisé par le pipeline
>
> Le pipeline s'authentifie avec `{"apikey": "..."}` uniquement, sans champ `pin`.

> **Langue** : TVDB utilise des codes langue à 3 caractères (`fra`, `eng`). Le pipeline convertit automatiquement depuis le format TMDB (`fr-FR` → `fra`).

---

## Scraper

Configuration des langues pour les requêtes API.

Ces réglages sont dans `config/scraper.json5` (clés `language` et `fallback_language`), pas dans `.env`.

| Clé (scraper.json5) | Défaut  | Description                                                          |
| ------------------- | ------- | -------------------------------------------------------------------- |
| `language`          | `fr-FR` | Langue principale pour les titres, descriptions, noms d'épisodes     |
| `fallback_language` | `en-US` | Langue de repli si le contenu n'existe pas dans la langue principale |

### Comment configurer

Le format suit la convention TMDB : `{langue}-{PAYS}`.

Exemples courants :

- `fr-FR` — Francais (France)
- `en-US` — Anglais (USA)
- `de-DE` — Allemand (Allemagne)
- `es-ES` — Espagnol (Espagne)
- `ja-JP` — Japonais (Japon)

```json5
// config/scraper.json5
{
  language: "fr-FR",
  fallback_language: "en-US",
}
```

> Les valeurs par défaut conviennent pour une bibliothèque francophone. Le fallback anglais permet de récupérer les titres/descriptions quand la traduction française n'existe pas (fréquent pour les anime et les séries récentes).

---

## Telegram (optionnel)

Notifications en fin de pipeline via un bot Telegram.

| Variable             | Défaut   | Description                                         |
| -------------------- | -------- | --------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | _(vide)_ | Token d'authentification du bot                     |
| `TELEGRAM_CHAT_ID`   | _(vide)_ | ID du chat/utilisateur qui recoit les notifications |

Si ces variables sont vides, le pipeline fonctionne normalement mais n'envoie pas de notification.

### Etape 1 — Créer le bot

1. Ouvrir Telegram et chercher **@BotFather**
2. Envoyer `/newbot`
3. Choisir un nom (ex: "PersonalScraper Bot")
4. Choisir un username (ex: `personalscraper_bot`)
5. BotFather retourne un token du type : `123456789:ABCDefGhIjKlMnOpQrStUvWxYz`

```ini
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz
```

### Etape 2 — Obtenir le Chat ID

1. Envoyer un message au bot que vous venez de créer (n'importe quel texte)
2. Ouvrir dans un navigateur :
   ```
   https://api.telegram.org/bot<VOTRE_TOKEN>/getUpdates
   ```
3. Dans la réponse JSON, chercher `"chat":{"id": 123456789}` — c'est votre Chat ID

```ini
TELEGRAM_CHAT_ID=123456789
```

> **Chat de groupe** : pour envoyer les notifications dans un groupe, ajouter le bot au groupe, envoyer un message dans le groupe, puis récupérer le Chat ID (qui sera négatif, ex: `-1001234567890`).

### Etape 3 — Vérifier

```bash
# Envoyer un message de test
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=Test PersonalScraper" \
  -d "parse_mode=HTML"
```

---

## Monitoring (optionnel)

Ping de supervision pour le scheduling automatique (launchd).

| Variable          | Défaut   | Description                                                          |
| ----------------- | -------- | -------------------------------------------------------------------- |
| `HEALTHCHECK_URL` | _(vide)_ | URL de ping [Healthchecks.io](https://healthchecks.io) ou équivalent |

Si vide, aucun ping n'est envoyé. Le pipeline fonctionne normalement.

### Comment configurer

1. Créer un compte sur [healthchecks.io](https://healthchecks.io) (gratuit pour 20 checks)
2. Créer un nouveau check :
   - **Name** : PersonalScraper Pipeline
   - **Period** : 1 day
   - **Grace** : 1 hour
3. Copier l'URL du check (format : `https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

```ini
HEALTHCHECK_URL=https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

> Le pipeline envoie un ping au début (`/start`), en cas de succès, et en cas d'échec (`/fail`). Si le ping n'arrive pas dans les 24h + 1h de grâce, Healthchecks.io envoie une alerte (email, Telegram, Slack, etc.).

---

## Seuils d'espace disque

Protections contre le remplissage des disques. Ces réglages sont dans `config/thresholds.json5`, pas dans `.env`.

| Clé (thresholds.json5)      | Défaut | Description                                                               |
| --------------------------- | ------ | ------------------------------------------------------------------------- |
| `min_free_space_staging_gb` | `20`   | Espace libre minimum (Go) sur le SSD avant d'ingérer de nouveaux torrents |
| `min_free_space_disk_gb`    | `100`  | Espace libre minimum (Go) sur un disque de stockage avant d'y dispatcher  |

### Comment configurer

```json5
// config/thresholds.json5
{
  // SSD de 1 To → garder 20 Go de marge
  min_free_space_staging_gb: 20,

  // Disques de 4-8 To → garder 100 Go de marge
  min_free_space_disk_gb: 100,
}
```

> **Formule de dispatch** : un disque est éligible si `free_space_gb >= max(min_free_gb, item_size_gb * 1.5)`. Cela garantit une marge même pour les gros fichiers (ex: une série de 50 Go nécessite 75 Go libres minimum).

> Adapter ces valeurs à la taille de vos disques. Pour des disques plus petits (1-2 To), baisser `min_free_space_disk_gb` à 50.

---

## Circuit Breaker

Protection contre les pannes durables des APIs TMDB/TVDB. Le circuit breaker détecte quand un provider est durablement down et évite de le spammer. Ces réglages sont dans `config/thresholds.json5`, pas dans `.env`.

| Clé (thresholds.json5)      | Défaut | Description                                                  |
| --------------------------- | ------ | ------------------------------------------------------------ |
| `circuit_breaker_threshold` | `5`    | Nombre d'erreurs consécutives avant d'ouvrir le circuit      |
| `circuit_breaker_cooldown`  | `300`  | Temps d'attente (secondes) avant de retenter après ouverture |

### Fonctionnement

- **CLOSED** (normal) : les appels passent, les erreurs 5xx/timeout/connexion sont comptées
- **OPEN** (après N erreurs) : tous les appels échouent immédiatement (`CircuitOpenError`), le pipeline bascule sur le provider alternatif (TMDB↔TVDB)
- **HALF_OPEN** (après cooldown) : un seul appel de test est autorisé — succès → CLOSED, échec → retour OPEN

> Le circuit breaker ne compte PAS les erreurs 429 (rate limit, gérées par tenacity) ni les 4xx (erreurs client).

### Comment configurer

```json5
// config/thresholds.json5
{
  // Valeurs par défaut — adaptées à la plupart des cas
  circuit_breaker_threshold: 5,
  circuit_breaker_cooldown: 300,
}
```

> Pour un usage intensif avec beaucoup de médias, augmenter le seuil à 10 pour tolérer des erreurs transitoires. Pour un réseau instable, baisser le cooldown à 120 secondes.

---

## Exemple complet

### .env (credentials uniquement)

```ini
# ── qBittorrent ──────────────────────────────
QBIT_HOST=localhost
QBIT_PORT=8081
QBIT_USERNAME=admin
QBIT_PASSWORD=mon_mot_de_passe

# ── TMDB / TVDB ──────────────────────────────
TMDB_API_KEY=abcdef1234567890abcdef1234567890
TVDB_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# ── Telegram ─────────────────────────────────
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz
TELEGRAM_CHAT_ID=123456789

# ── Monitoring ───────────────────────────────
HEALTHCHECK_URL=https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### config/thresholds.json5

```json5
{
  min_free_space_staging_gb: 20,
  min_free_space_disk_gb: 100,
  circuit_breaker_threshold: 5,
  circuit_breaker_cooldown: 300,
}
```

### config/scraper.json5 (extrait)

```json5
{
  language: "fr-FR",
  fallback_language: "en-US",
}
```

---

## Dépannage

### Le pipeline ne trouve pas le .env

Le fichier `.env` doit être à la racine du projet (`/path/to/staging/.env`). Vérifier :

```bash
ls -la "/path/to/staging/.env"
```

### Les clés API ne fonctionnent pas

```bash
# Tester TMDB
curl -s "https://api.themoviedb.org/3/movie/550?api_key=VOTRE_CLE" | python -m json.tool

# Tester TVDB (authentification)
curl -s -X POST "https://api4.thetvdb.com/v4/login" \
  -H "Content-Type: application/json" \
  -d '{"apikey": "VOTRE_CLE"}' | python -m json.tool
```

### qBittorrent refuse la connexion

1. Vérifier que l'interface Web est activée (Preferences > Web UI)
2. Vérifier le port : `curl -s http://localhost:8081/api/v2/app/version`
3. Si "Unauthorized" : vérifier les credentials dans `.env`
4. Si timeout : vérifier que qBittorrent tourne (`pgrep -l qbittorrent`)
