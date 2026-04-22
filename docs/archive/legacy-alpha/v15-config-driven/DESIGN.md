# V15 — CONFIG-DRIVEN ARCHITECTURE : Design

> Séparer totalement la nomenclature utilisateur (disques, dossiers, catégories) du code. Tout dans `config.json5`. Classification multi-niveaux avec override explicite dans NFO + règles pattern-based éditables.

## Architecture

### Fichiers créés

```
personalscraper/
├── conf/                                    # NEW package (nouveau, pas de collision avec config.py existant)
│   ├── __init__.py
│   ├── ids.py                              # Constantes d'IDs de catégories builtin
│   ├── models.py                           # Pydantic: Config, DiskConfig, CategoryConfig, CategoryRule, GenreMapping, AnimeRule, PathConfig, LibraryPrefs
│   ├── loader.py                           # Chargement JSON5 + validation Pydantic
│   ├── resolver.py                         # Résolution category_id → folder, pick disk
│   ├── classifier.py                       # Pipeline de classification multi-niveaux
│   ├── example_parser.py                   # Extraction commentaires-comme-prompts pour init-config
│   └── migration.py                        # V14 → V15: .env, library_*.json, .category → NFO
├── commands/                                # NEW (sous-commandes CLI extraites)
│   ├── __init__.py
│   └── init_config.py                      # personalscraper init-config [--from-current]
└── config.py                                # MODIFIED (pas renommé): Settings allégé — retire disk1_dir..disk4_dir ; garde secrets + seuils numériques

config.example.json5                        # NEW versionné, template avec commentaires-prompts
config.json5                                 # NEW gitignored, créé par init-config

tests/
├── fixtures/                                # NEW
│   ├── __init__.py
│   └── config.py                           # Fixture test_config (3 disques neutres, IDs abstraits)
└── conftest.py                              # MODIFIED — expose test_config
```

### Fichiers modifiés (dé-hardcoding complet)

| Fichier V14                                | Changement V15                                                                                            |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `personalscraper/config.py`                | Allégé (pas renommé) : **supprime** `disk1_dir..disk4_dir` ; garde uniquement secrets + seuils numériques |
| `personalscraper/dispatch/disk_scanner.py` | Supprime `DISK_CATEGORIES` ; lit depuis `Config.disks`                                                    |
| `personalscraper/dispatch/dispatcher.py`   | Utilise `resolver.folder_for(config, disk, category_id)` + IDs                                            |
| `personalscraper/dispatch/media_index.py`  | Index par `category_id` et `disk_id` ; migration du JSON existant                                         |
| `personalscraper/genre_mapper.py`          | Supprimé ; fonctionnalité → `conf/classifier.py`                                                          |
| `personalscraper/cli.py`                   | Ajoute top-level `--config` ; `init-config` command ; charge `Config` au callback                         |
| `personalscraper/pipeline.py`              | Injection de `Config`                                                                                     |
| `personalscraper/scraper/scraper.py`       | Utilise `classifier.classify(media, nfo, config)`                                                         |
| `personalscraper/scraper/nfo_generator.py` | Écrit `<category>{ID}</category>` dans le NFO                                                             |
| `personalscraper/sorter/matcher.py`        | Pattern matching agnostique (regex, pas de strings littéraux)                                             |
| `personalscraper/verify/*`                 | IDs partout ; résolution labels pour affichage Rich                                                       |
| `personalscraper/enforce/*`                | Idem                                                                                                      |
| `personalscraper/library/*`                | IDs partout ; migration `library_index.json`, `library_analysis.json`, `library_preferences.json`         |
| `personalscraper/library/preferences.py`   | Supprimé ; prefs fusionnées dans `Config.library`                                                         |

Tests : toutes références à `"films"`, `"series"`, `"Disk1"`, `/Volumes/...` → fixture `test_config` ou IDs de `personalscraper.conf.ids`.

### Dépendances

Ajout à `pyproject.toml` `[project]` :

- `json5>=0.9.14` — Parser JSON5 pur Python, éprouvé, supporte Python 3.10-3.13.

Parser maison (~40 lignes dans `example_parser.py`) pour extraire les commentaires précédant chaque clé JSON5.

## Interfaces

### `personalscraper/conf/ids.py`

```python
"""Abstract category IDs — stable identifiers used throughout the codebase.

Never user-facing labels. Folder names are in config.json5. Code uses only these
constants for routing, logging, filtering, validation.

Users may add custom IDs via Config.custom_categories.
"""

from typing import Final

MOVIES: Final[str] = "movies"
MOVIES_ANIMATION: Final[str] = "movies_animation"
MOVIES_DOCUMENTARY: Final[str] = "movies_documentary"
TV_SHOWS: Final[str] = "tv_shows"
TV_SHOWS_ANIMATION: Final[str] = "tv_shows_animation"
TV_SHOWS_DOCUMENTARY: Final[str] = "tv_shows_documentary"
ANIME: Final[str] = "anime"
AUDIOBOOKS: Final[str] = "audiobooks"
STANDUP: Final[str] = "standup"
THEATER: Final[str] = "theater"
TV_PROGRAMS: Final[str] = "tv_programs"

BUILTIN_CATEGORY_IDS: Final[frozenset[str]] = frozenset({
    MOVIES, MOVIES_ANIMATION, MOVIES_DOCUMENTARY,
    TV_SHOWS, TV_SHOWS_ANIMATION, TV_SHOWS_DOCUMENTARY,
    ANIME, AUDIOBOOKS, STANDUP, THEATER, TV_PROGRAMS,
})

# Label par défaut = ID avec underscores → espaces
def default_label(category_id: str) -> str:
    return category_id.replace("_", " ")
```

### `personalscraper/conf/models.py`

```python
"""Pydantic models for config.json5 validation.

All models use extra='forbid' to catch typos and prevent accidental secret placement.
"""

from pathlib import Path
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS, default_label


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryConfig(_StrictModel):
    """Personalisation du nom de dossier pour une catégorie."""
    folder_name: str = Field(..., min_length=1, description="Nom du dossier sur disque pour cette catégorie.")
    aliases: list[str] = Field(default_factory=list, description="Labels alternatifs acceptés par la CLI (--category).")

    @classmethod
    def default_for(cls, category_id: str) -> "CategoryConfig":
        return cls(folder_name=default_label(category_id))


class DiskConfig(_StrictModel):
    """Disque de stockage avec ses catégories acceptées."""
    id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$", description="Identifiant libre (disk_a, nas_main, ...).")
    path: Path = Field(..., description="Chemin monté absolu.")
    categories: list[str] = Field(..., min_length=1, description="IDs acceptés sur ce disque.")


class CategoryRule(_StrictModel):
    """Règle de classification pattern-based.

    Exactement un des champs 'match_*' doit être défini. Première règle qui match dans
    Config.category_rules détermine la catégorie (avant genre_mapping).
    """
    # Exactly-one pattern fields (mutually exclusive, validated below)
    path_contains: str | None = Field(default=None, description="Substring dans str(source_path.resolve()) (path du media en staging, avant dispatch). Case-sensitive.")
    path_regex: str | None = Field(default=None, description="Regex Python (re.search, non-anchored) sur str(source_path.resolve()). Case-sensitive sauf si tu mets (?i).")
    title_regex: str | None = Field(default=None, description="Regex Python (re.search, non-anchored) sur le titre — NFO <title> si existe, sinon filename.stem. Case-sensitive sauf (?i).")
    tmdb_genre_contains: str | None = Field(default=None, description="Substring dans un genre TMDB (nom tel que renvoyé par l'API — langue dépend de scraper_language). Match case-insensitive.")
    tmdb_keyword: list[str] | None = Field(default=None, description="Keyword(s) TMDB (API /keywords). Match si au moins un keyword présent. Nécessite scraper-side /keywords fetch (B4).")

    # Scoping par type de média (ajouté Phase 2 — évite collision rules entre movies et TV)
    applies_to: Literal["movie", "tv", "both"] = Field(default="both", description="Sur quel(s) type(s) de média appliquer cette rule.")

    category: str = Field(..., description="category_id résultat si cette règle match.")

    @model_validator(mode="after")
    def _exactly_one_pattern(self) -> "CategoryRule":
        # Traiter empty string et empty list comme "pas défini" (pour éviter validation
        # silencieuse avec rule qui ne match jamais).
        def _is_set(value: object) -> bool:
            if value is None:
                return False
            if isinstance(value, (str, list)) and len(value) == 0:
                return False
            return True

        fields = [self.path_contains, self.path_regex, self.title_regex, self.tmdb_genre_contains, self.tmdb_keyword]
        set_count = sum(1 for f in fields if _is_set(f))
        if set_count != 1:
            raise ValueError(
                f"CategoryRule must have exactly one non-empty match_* field (got {set_count}). "
                "Options: path_contains, path_regex, title_regex, tmdb_genre_contains, tmdb_keyword."
            )
        return self


class GenreMapping(_StrictModel):
    """Mapping genre ID → category_id par provider API.

    Les IDs genre sont stables (TMDB/TVDB ne les changent pas). Les noms entre // comments dans
    config.example.json5 servent juste d'aide à l'utilisateur.
    """
    tmdb_movies: dict[int, str] = Field(default_factory=dict, description="TMDB Movies genre_id → category_id.")
    tmdb_tv: dict[int, str] = Field(default_factory=dict, description="TMDB TV genre_id → category_id.")
    tvdb: dict[int, str] = Field(default_factory=dict, description="TVDB genre_id → category_id.")

    default_movies_category: str = Field(default="movies", description="Fallback si aucun genre movie match.")
    default_tv_category: str = Field(default="tv_shows", description="Fallback si aucun genre TV match.")


class AnimeRule(_StrictModel):
    """Règle spéciale anime (pour TMDB qui n'a pas de genre Anime dédié).

    Si genre_id=requires_genre_id ET origin_country ∈ requires_origin_country → maps_to.
    Mettre enabled=false pour désactiver la règle.
    """
    enabled: bool = Field(default=True)
    requires_genre_id: int = Field(default=16, description="TMDB Animation genre ID.")
    requires_origin_country: list[str] = Field(default_factory=lambda: ["JP"], description="Codes ISO origin_country.")
    maps_to: str = Field(default="anime", description="category_id résultat.")
    applies_to: Literal["movies", "tv", "both"] = Field(default="tv", description="Sur quels types de média appliquer.")


class PathConfig(_StrictModel):
    """Chemins non-disk utilisés par le pipeline."""
    torrent_complete_dir: Path = Field(..., description="Où qBittorrent dépose les torrents finis.")
    staging_dir: Path = Field(..., description="Dossier A TRIER intermédiaire.")
    data_dir: Path = Field(default=Path("./.data"), description="State du pipeline (index, locks, analyse). Défaut: .data/ à la racine du repo. Doit être ABSOLU après init-config (validator convertit).")

    @field_validator("torrent_complete_dir", "staging_dir", "data_dir", mode="after")
    @classmethod
    def _must_be_absolute_or_resolve(cls, v: Path) -> Path:
        """Résout les paths relatifs en absolus via Path.expanduser().resolve()."""
        return v.expanduser().resolve() if not v.is_absolute() else v


class VideoPrefs(_StrictModel):
    """Préférences vidéo (miroir V14 VideoPreferences)."""
    preferred_codec: str = Field(default="hevc")
    fallback_codecs: list[str] = Field(default_factory=lambda: ["av1"])
    rejected_codecs: list[str] = Field(default_factory=lambda: ["mpeg2", "mpeg4"])
    preferred_resolution: str = Field(default="1080p")
    max_size_movie_gb: float = Field(default=4.0)
    max_size_episode_gb: float = Field(default=2.0)

    @model_validator(mode="after")
    def _codecs_disjoint(self) -> "VideoPrefs":
        all_accepted = {self.preferred_codec} | set(self.fallback_codecs)
        rejected = set(self.rejected_codecs)
        overlap = all_accepted & rejected
        if overlap:
            raise ValueError(f"Codec sets overlap: {overlap}")
        return self


class AudioPrefs(_StrictModel):
    """Préférences audio (miroir V14 AudioPreferences)."""
    profile_priority: list[str] = Field(default_factory=lambda: ["multi", "vf", "vostfr", "vo"])
    min_channels: int = Field(default=2, ge=1)
    preferred_codec: str | None = Field(default=None)


class SubtitlePrefs(_StrictModel):
    """Préférences subtitles (miroir V14 SubtitlePreferences)."""
    required_languages: list[str] = Field(default_factory=lambda: ["fra"])
    preferred_languages: list[str] = Field(default_factory=lambda: ["fra", "eng"])
    warn_if_missing: bool = Field(default=True)

    @model_validator(mode="after")
    def _required_subset_of_preferred(self) -> "SubtitlePrefs":
        required, preferred = set(self.required_languages), set(self.preferred_languages)
        if not required.issubset(preferred):
            diff = required - preferred
            raise ValueError(f"required_languages must be a subset of preferred_languages, extra: {diff}")
        return self


class RuleCriteria(_StrictModel):
    """Critères encoding rule (miroir V14 RuleCriteria)."""
    genre: str | None = Field(default=None)
    title: str | None = Field(default=None)
    imdb_id: str | None = Field(default=None)
    tmdb_id: str | None = Field(default=None)

    @model_validator(mode="after")
    def _has_at_least_one(self) -> "RuleCriteria":
        if all(v is None for v in (self.genre, self.title, self.imdb_id, self.tmdb_id)):
            raise ValueError("RuleCriteria must have at least one non-None field")
        return self


class EncodingRule(_StrictModel):
    """Règle d'override encoding (miroir V14 EncodingRule)."""
    criteria: RuleCriteria
    resolution: str | None = Field(default=None)
    codec: str | None = Field(default=None)
    max_size_gb: float | None = Field(default=None)

    @model_validator(mode="after")
    def _has_at_least_one_target(self) -> "EncodingRule":
        if self.resolution is None and self.codec is None and self.max_size_gb is None:
            raise ValueError("EncodingRule must have at least one target (resolution, codec, or max_size_gb)")
        return self


class LibraryPrefs(_StrictModel):
    """Préférences library (fusion complète de V14 library_preferences.json)."""
    video: VideoPrefs = Field(default_factory=VideoPrefs)
    audio: AudioPrefs = Field(default_factory=AudioPrefs)
    subtitles: SubtitlePrefs = Field(default_factory=SubtitlePrefs)
    encoding_rules: list[EncodingRule] = Field(default_factory=list)


class Config(_StrictModel):
    """Top-level config.json5 parsed."""
    config_version: int = Field(default=1, description="Schéma version pour migration future.")

    paths: PathConfig
    disks: list[DiskConfig] = Field(..., min_length=1)

    # Categories: les 11 IDs builtin + les customs déclarés par l'user
    custom_categories: list[str] = Field(default_factory=list, description="IDs user-défini au-delà des builtin.")
    categories: dict[str, CategoryConfig] = Field(default_factory=dict)

    # Classification layers (ordre de priorité 2-5, cf § Classification pipeline)
    category_rules: list[CategoryRule] = Field(default_factory=list, description="Règles pattern-based, évaluées en ordre.")
    anime_rule: AnimeRule = Field(default_factory=AnimeRule)
    genre_mapping: GenreMapping = Field(default_factory=GenreMapping)

    library: LibraryPrefs = Field(default_factory=LibraryPrefs)

    @property
    def all_category_ids(self) -> frozenset[str]:
        """Union builtin + custom IDs."""
        return BUILTIN_CATEGORY_IDS | frozenset(self.custom_categories)

    @field_validator("custom_categories")
    @classmethod
    def _validate_custom_ids(cls, v: list[str]) -> list[str]:
        pattern = r"^[a-z][a-z0-9_]*$"
        import re
        for cid in v:
            if not re.match(pattern, cid):
                raise ValueError(f"Invalid custom category ID '{cid}'. Must match {pattern}")
            if cid in BUILTIN_CATEGORY_IDS:
                raise ValueError(f"Custom category '{cid}' conflicts with builtin ID")
        return v

    @model_validator(mode="after")
    def _validate_cross_references(self) -> "Config":
        known = self.all_category_ids

        # categories dict keys ⊆ known
        unknown_cats = set(self.categories.keys()) - known
        if unknown_cats:
            raise ValueError(f"Unknown category IDs in 'categories': {sorted(unknown_cats)}. Known: {sorted(known)}")

        # disks[*].categories ⊆ known
        for disk in self.disks:
            unknown = set(disk.categories) - known
            if unknown:
                raise ValueError(f"Disk '{disk.id}' references unknown categories: {sorted(unknown)}")

        # disk IDs unique
        dids = [d.id for d in self.disks]
        if len(dids) != len(set(dids)):
            raise ValueError(f"Duplicate disk IDs: {dids}")

        # genre_mapping values ⊆ known
        for provider, mapping in (("tmdb_movies", self.genre_mapping.tmdb_movies),
                                   ("tmdb_tv", self.genre_mapping.tmdb_tv),
                                   ("tvdb", self.genre_mapping.tvdb)):
            unknown = set(mapping.values()) - known
            if unknown:
                raise ValueError(f"genre_mapping.{provider} references unknown categories: {sorted(unknown)}")

        if self.genre_mapping.default_movies_category not in known:
            raise ValueError(f"default_movies_category '{self.genre_mapping.default_movies_category}' unknown")
        if self.genre_mapping.default_tv_category not in known:
            raise ValueError(f"default_tv_category '{self.genre_mapping.default_tv_category}' unknown")

        # anime_rule.maps_to ⊆ known
        if self.anime_rule.maps_to not in known:
            raise ValueError(f"anime_rule.maps_to '{self.anime_rule.maps_to}' unknown")

        # category_rules[*].category ⊆ known
        for i, rule in enumerate(self.category_rules):
            if rule.category not in known:
                raise ValueError(f"category_rules[{i}].category '{rule.category}' unknown")

        return self

    def category(self, category_id: str) -> CategoryConfig:
        """Lookup category config avec fallback sur default_label."""
        return self.categories.get(category_id) or CategoryConfig.default_for(category_id)

    def disk_by_id(self, disk_id: str) -> DiskConfig | None:
        return next((d for d in self.disks if d.id == disk_id), None)

    def disks_accepting(self, category_id: str) -> list[DiskConfig]:
        return [d for d in self.disks if category_id in d.categories]

    def resolve_category_alias(self, user_input: str) -> str | None:
        """--category input → category_id.

        Accepte: (1) un ID valide, (2) un alias explicite dans categories[id].aliases.
        N'accepte pas folder_name comme alias (collision many-to-one possible).
        """
        if user_input in self.all_category_ids:
            return user_input
        for cid, cfg in self.categories.items():
            if user_input in cfg.aliases:
                return cid
        return None
```

### `personalscraper/conf/classifier.py` (nouveau — pipeline de classification)

```python
"""Classification pipeline multi-niveaux.

Priorité (plus fort → plus faible):
1. NFO <category source="personalscraper">X</category>  — override explicite
2. Config.category_rules               — patterns user (path, title, genre-string, keyword)
3. Config.anime_rule                   — règle spéciale anime (Animation + JP)
4. Config.genre_mapping                — ID genre → category_id
5. default_movies_category / default_tv_category — fallback
6. None                                — caller doit skip + reporter (unreachable en pratique puisque defaults sont non-None)
"""

import logging
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from personalscraper.conf.models import Config

logger = logging.getLogger(__name__)


MediaType = Literal["movie", "tv"]


def classify(
    config: Config,
    *,
    media_type: MediaType,
    path: Path | None = None,
    title: str | None = None,
    tmdb_genres: list[str] | None = None,          # noms tel que l'API les renvoie
    tmdb_genre_ids: list[int] | None = None,
    tvdb_genre_ids: list[int] | None = None,
    tmdb_keywords: list[str] | None = None,
    origin_country: list[str] | None = None,
    nfo_path: Path | None = None,
) -> tuple[str | None, str]:
    """Return (category_id | None, reason_str).

    reason_str is a short string explaining which layer produced the result, useful
    for logs and the skip-report.
    """
    # 1. NFO override
    if nfo_path and nfo_path.exists():
        cid = _read_nfo_category(nfo_path)
        if cid:
            if cid in config.all_category_ids:
                return cid, "nfo_override"
            # Invalid / obsolete ID in NFO: log and fall through to next layers
            logger.warning("NFO %s has invalid <category>%s</category>, falling through", nfo_path, cid)

    # 2. category_rules
    for i, rule in enumerate(config.category_rules):
        if _rule_matches(rule, path=path, title=title, tmdb_genres=tmdb_genres, tmdb_keywords=tmdb_keywords):
            return rule.category, f"category_rules[{i}]"

    # 3. anime_rule
    ar = config.anime_rule
    if ar.enabled and ar.applies_to in (media_type, "both"):
        if tmdb_genre_ids and ar.requires_genre_id in tmdb_genre_ids:
            if origin_country and any(c in origin_country for c in ar.requires_origin_country):
                return ar.maps_to, "anime_rule"

    # 4. genre_mapping by IDs
    if media_type == "movie" and tmdb_genre_ids:
        for gid in tmdb_genre_ids:
            cid = config.genre_mapping.tmdb_movies.get(gid)
            if cid:
                return cid, f"genre_mapping.tmdb_movies[{gid}]"
    elif media_type == "tv":
        if tvdb_genre_ids:
            for gid in tvdb_genre_ids:
                cid = config.genre_mapping.tvdb.get(gid)
                if cid:
                    return cid, f"genre_mapping.tvdb[{gid}]"
        if tmdb_genre_ids:
            for gid in tmdb_genre_ids:
                cid = config.genre_mapping.tmdb_tv.get(gid)
                if cid:
                    return cid, f"genre_mapping.tmdb_tv[{gid}]"

    # 5. defaults
    if media_type == "movie":
        return config.genre_mapping.default_movies_category, "default_movies"
    if media_type == "tv":
        return config.genre_mapping.default_tv_category, "default_tv"

    # 6. skip
    return None, "no_match"


def _read_nfo_category(nfo_path: Path) -> str | None:
    """Read <category source="personalscraper">{ID}</category>.

    Prefer element with source=personalscraper attribute (disambiguates from any
    Kodi/Plex category element). If none has the attribute, fall back to the first
    <category> element without attribute (legacy V15.0 NFOs written before this
    rule).
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
    except (ET.ParseError, OSError):
        return None
    # Priority 1: element with source="personalscraper"
    for el in root.iter("category"):
        if el.get("source") == "personalscraper" and el.text:
            return el.text.strip()
    # Priority 2: any <category> without source attribute
    for el in root.iter("category"):
        if el.get("source") is None and el.text:
            return el.text.strip()
    return None


def _rule_matches(rule, *, path, title, tmdb_genres, tmdb_keywords) -> bool:
    import re
    if rule.path_contains is not None and path is not None:
        return rule.path_contains in str(path)
    if rule.path_regex is not None and path is not None:
        return bool(re.search(rule.path_regex, str(path)))
    if rule.title_regex is not None and title is not None:
        return bool(re.search(rule.title_regex, title))
    if rule.tmdb_genre_contains is not None and tmdb_genres:
        return any(rule.tmdb_genre_contains.lower() in g.lower() for g in tmdb_genres)
    if rule.tmdb_keyword is not None and tmdb_keywords:
        kws = rule.tmdb_keyword if isinstance(rule.tmdb_keyword, list) else [rule.tmdb_keyword]
        return any(kw in tmdb_keywords for kw in kws)
    return False
```

### `personalscraper/conf/loader.py`

```python
"""JSON5 config loader."""

import json5
import os
from pathlib import Path
from personalscraper.conf.models import Config


DEFAULT_CONFIG_PATH = Path("./config.json5")
ENV_CONFIG_PATH = "PERSONALSCRAPER_CONFIG"


class ConfigNotFoundError(FileNotFoundError):
    pass


class ConfigValidationError(ValueError):
    pass


def resolve_config_path(cli_override: Path | None = None) -> Path:
    """CLI > env > default."""
    if cli_override is not None:
        return cli_override.expanduser().resolve()
    env = os.environ.get(ENV_CONFIG_PATH)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_CONFIG_PATH.expanduser().resolve()


def load_config(path: Path | None = None) -> Config:
    resolved = path or resolve_config_path()
    if not resolved.is_file():
        raise ConfigNotFoundError(
            f"No config file at {resolved}. "
            "Run 'personalscraper init-config' or 'personalscraper init-config --from-current' to create one."
        )
    with resolved.open("r", encoding="utf-8") as f:
        try:
            raw = json5.load(f)
        except Exception as exc:
            raise ConfigValidationError(f"JSON5 parse error in {resolved}: {exc}") from exc
    try:
        return Config.model_validate(raw)
    except Exception as exc:
        raise ConfigValidationError(f"Validation error in {resolved}:\n{exc}") from exc
```

### `personalscraper/conf/resolver.py`

```python
"""Pure functions: resolve category_id → folder, pick disk."""

from pathlib import Path
from personalscraper.conf.models import Config, DiskConfig


def folder_for(config: Config, disk: DiskConfig, category_id: str) -> Path:
    return disk.path / config.category(category_id).folder_name


def pick_disk_for(
    config: Config,
    category_id: str,
    free_space_by_id: dict[str, float],
    min_free_gb: float,
    item_size_gb: float,
) -> DiskConfig | None:
    """Pick best disk for a category.

    Threshold formula preserved from V14: threshold = max(min_free_gb, item_size_gb * 1.5).
    Item_size_gb * 1.5 leaves headroom for rsync temp files and partial writes.

    Caller is responsible for passing free_space_by_id (typically built by iterating
    config.disks + disk_scanner.get_disk_status). Unmounted disks should have
    free_space_by_id[d.id] = 0.0.
    """
    threshold = max(min_free_gb, item_size_gb * 1.5)
    candidates = config.disks_accepting(category_id)
    eligible = [d for d in candidates if free_space_by_id.get(d.id, 0.0) >= threshold]
    if not eligible:
        return None
    return max(eligible, key=lambda d: free_space_by_id[d.id])
```

### `personalscraper/conf/example_parser.py`

```python
"""Parse config.example.json5 to extract (comment, key-path, default-value) triples.

Used by `init-config` to turn example comments into interactive prompts.
Line-based parser — no third-party dep beyond json5 (which we use only for values).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Prompt:
    key_path: str             # ex: "paths.torrent_complete_dir", "disks[0].id"
    comment: str              # accumulated // lines preceding the key
    default_value: str        # source-code literal (JSON5 as-is)


def parse_example(example_path: Path) -> list[Prompt]:
    """Read example file line by line, accumulate // comments, emit Prompt per key."""
    # Implementation:
    # - Track object/array depth to compute key_path
    # - Accumulate consecutive // lines into current_comment buffer
    # - On a "key: value," line, emit Prompt(key_path, current_comment, raw_value); reset buffer
    # - On blank line or non-comment/non-key line: reset buffer
    # - Handle /* */ block comments: accumulate across lines
    # - Skip array items (emit prompt per array: "disks: N entries? [1]")
    ...
```

### `personalscraper/conf/migration.py`

```python
"""V14 → V15 migration utilities.

Three migration paths:
1. .env DISK*_DIR + disk_scanner.DISK_CATEGORIES → config.json5 (via init-config --from-current)
2. library_*.json files on disk: rewrite label strings ("films" → "movies") to IDs
3. .category files in media dirs → <category> element in corresponding NFO + delete .category
"""

from pathlib import Path

# Mapping V14 label → V15 ID (derived from the maintainer's current config)
V14_LABEL_TO_ID: dict[str, str] = {
    "films": "movies",
    "films animations": "movies_animation",
    "films documentaires": "movies_documentary",
    "series": "tv_shows",
    "series animations": "tv_shows_animation",
    "series documentaires": "tv_shows_documentary",
    "series animes": "anime",
    "spectacles": "standup",    # V14 "spectacles" = stand-up / one-man-show (pas concerts)
    "theatres": "theater",
    "emissions": "tv_programs",
    "livres audios": "audiobooks",
}


def generate_config_from_env(env_values: dict[str, str]) -> dict:
    """Build a config.json5-compatible dict from V14 .env variables.

    Reads DISK1_DIR..DISK4_DIR, STAGING_DIR, TORRENT_COMPLETE_DIR.
    Reuses disk_scanner.DISK_CATEGORIES mapping (fetched just-in-time since this
    is migration code — we know V14 structure).
    """
    ...


def migrate_library_json(file_path: Path, backup_suffix: str = ".v14.bak") -> None:
    """Read JSON, replace V14 labels with V15 IDs in known fields, write back. Create backup first."""
    ...


def migrate_category_files(staging_root: Path) -> int:
    """Walk staging_root, for each .category file: read content, insert <category> in
    sibling NFO, delete .category. Return count of migrated files.
    """
    ...
```

### `personalscraper/config.py` (allégé, pas renommé — Settings secrets-only)

```python
"""Pydantic Settings for SECRETS ONLY (loaded from .env).

Structural config (disks, categories, paths, preferences) is in config.json5.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API secrets
    tmdb_api_key: str = ""
    tvdb_api_key: str = ""

    # qBittorrent
    qbittorrent_url: str = "http://localhost:8080"
    qbittorrent_username: str = ""
    qbittorrent_password: str = ""

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Operational thresholds (numeric only, no user labels)
    min_free_space_disk_gb: float = 100.0
    # ... autres seuils numériques V14 préservés
```

### `personalscraper/cli.py` (callback + init-config)

```python
app = typer.Typer()


@app.callback()
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 (overrides ./config.json5 and $PERSONALSCRAPER_CONFIG). Position: BEFORE the subcommand."),
) -> None:
    """EAGER config validation: load and validate config.json5 immediately, except
    when the subcommand is `init-config` (which is precisely the bootstrap case).

    Any ConfigNotFoundError or ConfigValidationError crashes here with a clear
    message. Subcommands access `ctx.obj.config` as a plain attribute (no lazy wrap).
    """
    if ctx.invoked_subcommand == "init-config":
        ctx.obj = AppCtx(config=None, config_override=config)
        return

    try:
        cfg = load_config(resolve_config_path(config))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    ctx.obj = AppCtx(config=cfg, config_override=config)


@dataclass
class AppCtx:
    config: Config | None                  # None only if invoked_subcommand == "init-config"
    config_override: Path | None


@app.command("init-config")
def init_config_cmd(
    example: Path = typer.Option(Path("config.example.json5")),
    output: Path = typer.Option(Path("config.json5")),
    non_interactive: bool = typer.Option(False, "--yes"),
    from_current: bool = typer.Option(False, "--from-current", help="Migrer depuis V14 (.env + DISK_CATEGORIES + library_*.json + .category files)"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config.json5 (auto-backup to .v15.bak)"),
) -> None:
    """Create config.json5 from example or V14 migration.

    Behavior when output already exists:
      - Without --force: error and exit 2.
      - With --force: move existing to config.json5.v15.bak, then write new.

    Behavior of --from-current --yes when .env lacks DISK*_DIR:
      - Error (explicit, exit 2). --yes cannot guess paths.
    """
    from personalscraper.commands.init_config import init_config
    init_config(example, output, interactive=not non_interactive, from_current=from_current, force=force)
```

### `tests/fixtures/config.py`

```python
"""Synthetic test config — 3 neutral disks, builtin IDs, generic labels."""

from pathlib import Path
import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models import (
    Config, DiskConfig, CategoryConfig, GenreMapping, AnimeRule, PathConfig, LibraryPrefs,
)


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents_complete",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.MOVIES, CID.TV_SHOWS, CID.ANIME]),
            DiskConfig(id="drive_b", path=tmp_path / "drive_b", categories=[CID.MOVIES_ANIMATION, CID.TV_SHOWS_ANIMATION]),
            DiskConfig(id="drive_c", path=tmp_path / "drive_c", categories=[CID.MOVIES_DOCUMENTARY, CID.TV_SHOWS_DOCUMENTARY, CID.AUDIOBOOKS, CID.STANDUP, CID.THEATER, CID.TV_PROGRAMS]),
        ],
        categories={cid: CategoryConfig(folder_name=f"cat_{cid}") for cid in CID.BUILTIN_CATEGORY_IDS},
        genre_mapping=GenreMapping(
            tmdb_movies={16: CID.MOVIES_ANIMATION, 99: CID.MOVIES_DOCUMENTARY},
            tmdb_tv={16: CID.TV_SHOWS_ANIMATION, 99: CID.TV_SHOWS_DOCUMENTARY, 10764: CID.TV_PROGRAMS, 10767: CID.TV_PROGRAMS, 10763: CID.TV_PROGRAMS},
            tvdb={27: CID.ANIME, 17: CID.TV_SHOWS_ANIMATION, 3: CID.TV_SHOWS_DOCUMENTARY, 8: CID.TV_PROGRAMS, 10: CID.TV_PROGRAMS, 11: CID.TV_PROGRAMS},
        ),
        anime_rule=AnimeRule(enabled=True, requires_genre_id=16, requires_origin_country=["JP"], maps_to=CID.ANIME, applies_to="tv"),
    )
```

## Flux de données détaillé

```
┌──────────────────────────────────────────────────────────────┐
│   CLI entry                                                  │
│   1. Typer callback parses --config                          │
│   2. Subcommand starts:                                      │
│        init-config: lit example, prompt, write config.json5  │
│        other: ctx.obj.config() → load_config()               │
│           → Pydantic validation                              │
│           → inject Config + Settings into services           │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│   Scraper: classify(config, ...)                             │
│   1. Read NFO <category> if exists                           │
│   2. Walk config.category_rules (premier match gagne)        │
│   3. Check anime_rule (si applicable)                        │
│   4. Lookup genre_mapping by genre_id                        │
│   5. Fallback default_movies_category / default_tv_category  │
│   6. None → log "no_match" + append to skip_report           │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│   Dispatcher: route(category_id)                             │
│   - config.disks_accepting(category_id) → list[DiskConfig]   │
│   - resolver.pick_disk_for(config, cid, free_space, ...)     │
│   - resolver.folder_for(config, disk, cid) → final path      │
│   - rsync move                                               │
└──────────────────────────────────────────────────────────────┘
```

## Configuration

### `config.example.json5` (template, commentaires = prompts)

```json5
{
  // Version du schéma config (ne pas modifier sauf mise à jour V15.x → V15.y)
  config_version: 1,

  paths: {
    // Dossier où qBittorrent dépose les torrents terminés
    torrent_complete_dir: "/path/to/torrents/complete",
    // Dossier staging intermédiaire (A TRIER) avant dispatch
    staging_dir: "/path/to/staging",
    // State du pipeline (index, locks, analyse). Défaut: .data/ à la racine du repo.
    data_dir: "./.data",
  },

  // Catégories custom au-delà des 11 builtin (optionnel)
  // Chaque custom ID doit être une catégorie valide dans 'categories' et référencé par les disques/règles.
  custom_categories: [],

  // Liste des disques de stockage (nombre variable)
  disks: [
    {
      // Identifiant libre (utilisé dans CLI --disk et logs)
      id: "drive_a",
      // Chemin monté absolu
      path: "/path/to/drive_a",
      // IDs de catégories acceptées (parmi builtin + custom_categories)
      categories: ["movies", "tv_shows", "anime", "audiobooks"],
    },
  ],

  // Personnalisation du nom de dossier pour chaque catégorie
  // Défaut si non spécifié: ID avec underscores remplacés par espaces.
  // Plusieurs IDs peuvent pointer vers le même folder_name (merge dans le même dossier physique).
  categories: {
    movies: { folder_name: "movies" },
    movies_animation: {
      folder_name: "movies animation",
      aliases: ["Movies Animation"],
    },
    // ...
  },

  // Règles pattern-based (évaluées en ordre, premier match gagne, AVANT genre_mapping)
  // Supports: path_contains, path_regex, title_regex, tmdb_genre_contains, tmdb_keyword
  category_rules: [
    // Exemples:
    // { path_contains: "/standup/", category: "standup" },
    // { tmdb_keyword: "stand-up-comedy", category: "standup" },
  ],

  // Règle anime (TMDB n'a pas de genre Anime dédié, contrairement à TVDB)
  // Disable en passant enabled: false.
  anime_rule: {
    enabled: true,
    // TMDB Animation genre_id
    requires_genre_id: 16,
    // Liste de codes origin_country (ISO 3166) qui déclenchent la règle
    requires_origin_country: ["JP"],
    // category_id résultat
    maps_to: "anime",
    // Sur quels types de média: "movies", "tv", "both"
    applies_to: "tv",
  },

  // Mapping genre_id → category_id par provider API.
  genre_mapping: {
    // TMDB Movies API — https://developer.themoviedb.org/reference/genre-movie-list
    tmdb_movies: {
      // 16 = Animation
      "16": "movies_animation",
      // 99 = Documentary
      "99": "movies_documentary",
      // Autres genres (Action=28, Comedy=35, Drama=18, ...) → default_movies_category
    },
    // TMDB TV API — https://developer.themoviedb.org/reference/genre-tv-list
    tmdb_tv: {
      // 16 = Animation (sauf anime_rule qui override si JP)
      "16": "tv_shows_animation",
      // 99 = Documentary
      "99": "tv_shows_documentary",
      // 10764 = Reality
      "10764": "tv_programs",
      // 10767 = Talk
      "10767": "tv_programs",
      // 10763 = News
      "10763": "tv_programs",
    },
    // TVDB API — https://thetvdb.com/api-information
    tvdb: {
      // 27 = Anime (genre dédié)
      "27": "anime",
      // 17 = Animation
      "17": "tv_shows_animation",
      // 3 = Documentary
      "3": "tv_shows_documentary",
      // 8 = Reality, 10 = Talk, 11 = News
      "8": "tv_programs",
      "10": "tv_programs",
      "11": "tv_programs",
    },
    // Fallback quand aucun genre ne match
    default_movies_category: "movies",
    default_tv_category: "tv_shows",
  },

  // Préférences library (anciennement library_preferences.json V14)
  library: {
    min_video_resolution: "720p",
    preferred_codecs: ["h265", "h264"],
    preferred_audio_languages: ["fra", "eng"],
    preferred_subtitle_languages: ["fra"],
  },
}
```

### `.env` (secrets + seuils numériques uniquement)

```
TMDB_API_KEY=...
TVDB_API_KEY=...
QBITTORRENT_URL=http://localhost:8080
QBITTORRENT_USERNAME=...
QBITTORRENT_PASSWORD=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
MIN_FREE_SPACE_DISK_GB=100
```

### `.gitignore` ajouts

```
# V15: personal config
config.json5
```

## Ordre NFO write/read (contrat scraper ↔ classifier)

**Règle** :

1. Scraper fetch metadata TMDB/TVDB (genres, keywords via `/keywords` endpoint si `category_rules` utilise `tmdb_keyword`, sinon skip).
2. **Avant** d'écrire le NFO : `classifier.classify()` est appelé.
   - Si un NFO existe déjà (re-scrape, édition utilisateur) → priorité 1 `<category>` override déclenche.
   - Sinon les niveaux 2-5 s'appliquent.
3. `nfo_generator.write()` écrit le NFO avec `<category source="personalscraper">{ID}</category>` (attribut pour désambigüer vs un éventuel `<category>` Kodi/Plex).
4. Dispatch utilise l'ID retourné.

**Workflow user re-route manuel** :

- User édite `<category>` dans le NFO existant → lance `personalscraper scrape --force` ou `personalscraper verify` → niveau 1 NFO override gagne → routage via nouvelle catégorie.

**TMDB keywords fetch** :

- Nouvelle fonctionnalité scraper-side (Phase dédiée dans le plan).
- Endpoint : `GET /movie/{id}/keywords` ou `GET /tv/{id}/keywords`.
- Cache : par `tmdb_id`, dans `<data_dir>/tmdb_keywords_cache.json` (TTL 30 jours).
- Fail-soft : API down / 404 → liste vide, les `CategoryRule.tmdb_keyword` ne match pas (niveau suivant évalué).

## Classification pipeline (détail)

```
Input: media item (file/folder) + optional NFO + optional TMDB/TVDB metadata
Output: (category_id | None, reason: str)

Priority chain (**order adjusted in Phase 2** — anime before rules, mirroring V14 GenreMapper behavior):
  ┌─────────────────────────────────────────────┐
  │ 1. NFO <category> element                    │  → "nfo_override"
  └─────────────────────────────────────────────┘
                   │ (else)
                   ▼
  ┌─────────────────────────────────────────────┐
  │ 2. Config.anime_rule                         │  → "anime_rule"
  │    (if enabled AND applies_to matches)       │
  │    Runs BEFORE category_rules to preserve    │
  │    V14 priority: origin-country-gated anime  │
  │    wins over generic "Animation" matching.   │
  └─────────────────────────────────────────────┘
                   │ (else)
                   ▼
  ┌─────────────────────────────────────────────┐
  │ 3. Config.category_rules (ordered, first wins)│  → "category_rules[i]"
  │    - path_contains / path_regex              │
  │    - title_regex                             │
  │    - tmdb_genre_contains / tmdb_keyword      │
  │    - rule.applies_to ∈ {movie, tv, both}     │
  └─────────────────────────────────────────────┘
                   │ (else)
                   ▼
  ┌─────────────────────────────────────────────┐
  │ 4. Config.genre_mapping                      │  → "genre_mapping.X[id]"
  │    - tmdb_movies / tmdb_tv / tvdb by ID      │
  └─────────────────────────────────────────────┘
                   │ (else)
                   ▼
  ┌─────────────────────────────────────────────┐
  │ 5. default_movies_category / default_tv_category │  → "default_movies" / "default_tv"
  └─────────────────────────────────────────────┘
                   │ (else — shouldn't normally happen)
                   ▼
  ┌─────────────────────────────────────────────┐
  │ 6. Return None                               │  → caller skips + reports
  └─────────────────────────────────────────────┘
```

## Migration V14 → V15

Au premier run de `personalscraper init-config --from-current` :

1. **Lire `.env` V14** : `DISK1_DIR`..`DISK4_DIR`, `STAGING_DIR`, `TORRENT_COMPLETE_DIR`.
2. **Récupérer `DISK_CATEGORIES` V14** (inline dans le code de migration).
3. **Générer `config.json5`** :
   - `paths.*` depuis `.env`
   - `disks[]` : 4 entrées `{id: "disk_N", path: DISK_N_DIR, categories: [ids_mapped]}` — labels V14 → IDs via `V14_LABEL_TO_ID`
   - `categories.*` : `folder_name` = label V14 original (pour que les dossiers restent nommés en français sur disque)
   - `genre_mapping` : pré-rempli avec le mapping extrait de `genre_mapper.py` V14 (IDs TMDB/TVDB → ids V15)
   - `anime_rule` : activé, applies_to="tv", mirror V14 behavior
4. **Migration du `data_dir`** (V14 `<staging>/.personalscraper/` → V15 `<staging>/.data/`) :
   - Si `<staging>/.personalscraper/` existe et contient des fichiers → move intégral vers `<staging>/.data/` (opération atomique via `shutil.move` avec backup du target s'il existe).
   - Le nouveau `paths.data_dir` écrit dans `config.json5` = `<staging>/.data` (absolu, pas de CWD dependency).
   - L'ancien répertoire `.personalscraper/` est supprimé après move réussi.
5. **Migration des JSON library** (dans le nouveau `data_dir`) :
   - Fichiers : `library_index.json`, `library_analysis.json`, `library_rescrape.json`, `library_recommendations.json`, `library_validation.json`
   - **NB** : `library_preferences.json` N'EST PAS traité ici — c'est l'étape 7 qui le fusionne dans `config.library` (pour éviter double processing).
   - Pour chaque : backup `.v14.bak`, puis rewrite des label strings en IDs via `V14_LABEL_TO_ID`.
   - Le schema de chaque fichier est introspecté dans `migration.py` (fonction par fichier, champs listés explicitement).
   - Si un label V14 inconnu apparaît : log WARN + laisse tel quel (pas de crash).
6. **Migration des fichiers `.category`** :
   - Scan `<staging>/` récursif pour tous `.category`.
   - Pour chaque : lire le label V14 → mapper vers V15 ID → insérer `<category source="personalscraper">{ID}</category>` dans NFO sibling.
   - Si pas de NFO sibling : laisser `.category` en place + log WARN (user-action required).
   - Si label V14 non mappable : laisser `.category` en place + log WARN.
   - Sinon : supprimer `.category`.
   - Lock file check avant migration : si `data_dir/lock.json` existe → refuser migration (pipeline tourne).
7. **`library_preferences.json`** : lu et intégré dans `config.library` du résultat (pas juste rewrite). Backup `.v14.bak`, puis supprimer.
8. **Écrire `config.json5`** résultat (ou `.v15.bak` si `--force`).

Documenté dans `docs/v15-config-driven/MIGRATION.md` (créé en Phase 1 du plan).

## Gestion d'erreurs

| Situation                                                        | Comportement                                                               |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `config.json5` absent (sauf `init-config`)                       | `ConfigNotFoundError`, message → lancer `init-config [--from-current]`     |
| JSON5 syntax invalide                                            | `ConfigValidationError` avec message du parser (ligne si dispo)            |
| Champ requis manquant (Pydantic)                                 | `ConfigValidationError` avec chemin du champ                               |
| Clé inattendue (`extra="forbid"`)                                | `ConfigValidationError` listant les champs valides                         |
| `custom_categories[i]` doesn't match pattern `^[a-z][a-z0-9_]*$` | Validation error avec pattern attendu                                      |
| `custom_categories[i]` collision avec builtin                    | Validation error                                                           |
| `disks[*].categories` référence un ID inconnu                    | Validation error listant IDs connus                                        |
| `categories` contient un ID inconnu                              | Validation error                                                           |
| `genre_mapping.X` valeur est un ID inconnu                       | Validation error                                                           |
| `default_movies_category` / `default_tv_category` inconnu        | Validation error                                                           |
| `anime_rule.maps_to` inconnu                                     | Validation error                                                           |
| `category_rules[i].category` inconnu                             | Validation error                                                           |
| `category_rules[i]` avec zéro ou plusieurs match\_\* fields      | Validation error "exactly one match\_\* field required"                    |
| IDs de disques dupliqués                                         | Validation error                                                           |
| `disk.path` n'existe pas                                         | Warning au démarrage, `skipped` lors du dispatch (V14 behavior)            |
| `--config /invalid/path`                                         | `ConfigNotFoundError` avec path exact                                      |
| `PERSONALSCRAPER_CONFIG=/invalid`                                | Idem                                                                       |
| Classification : `classify()` retourne `None`                    | Log WARN + append to `skip_report` (V14 error-reporting style)             |
| Classification : NFO `<category>` contient un ID inconnu         | Log WARN "invalid nfo category 'X', falling back to next layer" + continue |
| Migration : `.env` V14 manquant des DISK\*\_DIR                  | Prompter interactive avec valeurs par défaut, pas d'erreur                 |
| Migration : JSON library corrompu                                | Skip + warn, laisse tel quel                                               |

## Sécurité

- `config.json5` contient des paths système → **gitignored**.
- `.env` inchangé (gitignored, secrets uniquement).
- Aucun secret dans `config.json5` — `extra="forbid"` rejette les clés inconnues qui pourraient contenir un secret collé par erreur.
- `config.example.json5` ne contient que placeholders (`/path/to/drive_a`) → safe à commiter.
- `Config.load()` lit depuis un path user-fourni → risque path traversal ? Non : Pydantic valide que les paths sont des `Path`, pas d'exécution.

## Critères d'acceptation V15

1. **Zéro hardcoded paths/disks/categories dans le code prod** :

   ```
   grep -rE "Disk[1-4]|/Volumes/|\"films\"|\"series\"|\"films animations\"|\"series animations\"|\"series documentaires\"|\"series animes\"|\"emissions\"|\"livres audios\"|\"spectacles\"|\"theatres\"" personalscraper/
   ```

   → Seuls résultats acceptés : `personalscraper/conf/migration.py::V14_LABEL_TO_ID` (migration one-shot).

2. **Zéro hardcoded paths/labels dans les tests** :

   ```
   grep -rE "/Volumes/|\"films\"|\"series\"|\"Disk[1-4]\"" tests/
   ```

   → Zéro résultat.

3. **`config.example.json5` + `init-config` génèrent un `config.json5` fonctionnel** (test E2E dédié).

4. **`config.example.json5` + `init-config --from-current` migre** un `.env` V14 fixture → `config.json5` équivalent sémantiquement (test E2E dédié).

5. **1270+ tests V14 passent avec la fixture `test_config`** (aucun fail, éventuelle évolution des numéros de tests acceptée).

6. **mypy strict : 0 erreur** (incluant `personalscraper/conf/*`).

7. **CI green sur Python 3.10, 3.11, 3.12, 3.13**.

8. **Un utilisateur externe peut cloner** → `cp config.example.json5 config.json5` → édite → `pipeline run` **sans modifier aucun fichier `.py`**.

9. **Classification pipeline testée** à 6 niveaux : NFO > rules > anime_rule > genre_mapping > defaults > skip. Test pour chaque transition.

10. **Migration documentée** dans `MIGRATION.md` + script automatique testé.

11. **Suite d'équivalence comportementale V14↔V15** (Phase 1 gate) : golden table de 50+ inputs couvrant toutes les branches de `GenreMapper.categorize_movie` et `categorize_tvshow`, asserts que `classifier.classify(...)` V15 produit le `category_id` équivalent (via `V14_LABEL_TO_ID`). Cette suite DOIT passer avant toute suppression de `genre_mapper.py`.

    **Structure** :
    - Fichier : `tests/equivalence/test_classifier_v14_vs_v15.py`
    - Golden table : `tests/equivalence/golden/classifier_cases.json` (liste de dicts avec `media_type`, `genres`, `genre_ids`, `origin_country`, `source`, `expected_v14_label`)
    - Les inputs couvrent : 11 catégories V14 × min 4 scenarios chacune (ID match, name fallback, anime rules, default fallback)
    - Le test : pour chaque case, invoke V14 `GenreMapper.categorize_*` → assert result = expected_v14_label ; puis invoke V15 `classify()` → assert result_id = V14_LABEL_TO_ID[expected_v14_label]
    - Génération initiale : script `scripts/generate_classifier_golden.py` qui exerce V14 et dumps le JSON

### Testing strategy — TMDB keywords cache

- Fichier : `tests/scraper/test_keywords_cache.py`
- Fixtures : mock TMDB responses, temp cache dir (`tmp_path`)
- Cas testés :
  - Cache miss → API call → write cache
  - Cache hit dans TTL → pas d'API call
  - Cache expired (> 30j) → API call → refresh
  - API 404 → cached as empty list → rule.tmdb_keyword ne match jamais
  - API down (timeout/5xx) → return empty list (fail-soft), no cache write

### Testing strategy — Migration V14 → V15

- Fichier : `tests/migration/test_v14_to_v15.py`
- Fixtures (dans `tests/migration/fixtures/`) :
  - `v14_env_sample` : `.env` V14 avec DISK1_DIR..DISK4_DIR + secrets
  - `v14_library_index.json`, `v14_library_analysis.json`, `v14_library_preferences.json`, etc. : samples réalistes avec labels V14
  - `v14_category_files.tar` : arborescence avec `.category` + NFO siblings
- Tests :
  - `generate_config_from_env` : input `.env` → assert disks[].categories contient IDs V15 corrects ; assert paths correctement mappés
  - `migrate_library_json` : assert labels FR remplacés par IDs ; backup `.v14.bak` créé ; V14 labels inconnus → WARN sans crash
  - `migrate_category_files` : `.category` → `<category source="personalscraper">` dans NFO + `.category` supprimé ; pas de NFO sibling → skip + WARN
  - `init-config --from-current --force` : overwrite + backup `.v15.bak` créé
  - `--force` idempotent : second appel overwrite le `.v15.bak` précédent (semantic confirmée)

12. **Validation warnings non-blocking** pour config cohérente mais sous-optimale :
    - `custom_categories[id]` déclaré mais absent de tout `disks[*].categories` → warn "dead category"
    - `categories[id]` absent pour un ID référencé → warn "using default label"
    - `disk.path` inexistant → warn "disk unmounted at startup"
