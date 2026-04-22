"""Pydantic models for config.json5 validation.

All models use extra='forbid' to catch typos and prevent accidental secret
placement in the config file.
"""

import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS, default_label


class _StrictModel(BaseModel):
    """Base model that forbids extra fields.

    All concrete config models inherit from this to catch typos early and
    prevent secrets from being accidentally placed in config.json5.
    """

    model_config = ConfigDict(extra="forbid")


class CategoryConfig(_StrictModel):
    """Personalisation du nom de dossier pour une catégorie.

    Attributes:
        folder_name: Folder name on disk for this category.
        aliases: Alternative labels accepted by the CLI (--category).
    """

    folder_name: str = Field(..., min_length=1, description="Nom du dossier sur disque pour cette catégorie.")
    aliases: list[str] = Field(default_factory=list, description="Labels alternatifs acceptés par la CLI (--category).")

    @classmethod
    def default_for(cls, category_id: str) -> "CategoryConfig":
        """Build a default CategoryConfig for a category ID.

        Args:
            category_id: A builtin or custom category ID.

        Returns:
            CategoryConfig with folder_name derived from the ID.
        """
        return cls(folder_name=default_label(category_id))


class DiskConfig(_StrictModel):
    """Disque de stockage avec ses catégories acceptées.

    Attributes:
        id: Free-form disk identifier (must match ``^[a-z][a-z0-9_]*$``).
        path: Absolute mounted path.
        categories: Category IDs accepted on this disk.
    """

    id: str = Field(
        ...,
        min_length=1,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Identifiant libre (disk_a, nas_main, ...).",
    )
    path: Path = Field(..., description="Chemin monté absolu.")
    categories: Annotated[list[str], Field(min_length=1)] = Field(..., description="IDs acceptés sur ce disque.")


class CategoryRule(_StrictModel):
    """Règle de classification pattern-based.

    Exactement un des champs ``match_*`` doit être défini. Première règle qui
    match dans ``Config.category_rules`` détermine la catégorie (avant
    ``genre_mapping``).

    Attributes:
        path_contains: Substring in str(source_path.resolve()). Case-sensitive.
        path_regex: Python regex (re.search, non-anchored) on source path. Case-sensitive.
        title_regex: Python regex on title (NFO <title> or filename stem). Case-sensitive.
        tmdb_genre_contains: Substring in a TMDB genre name. Case-insensitive.
        tmdb_keyword: TMDB keyword(s). Match if at least one is present.
        category: Result category_id if this rule matches.
        applies_to: Media type this rule applies to. Defaults to "both".
    """

    # Optional media-type filter (defaults to "both" for backward compatibility)
    applies_to: Literal["movie", "tv", "both"] = Field(
        default="both",
        description=(
            'Media type this rule applies to: "movie", "tv", or "both". '
            'Rules with applies_to="movie" are skipped for TV media and vice-versa.'
        ),
    )

    # Exactly-one pattern fields (mutually exclusive, validated below)
    path_contains: str | None = Field(
        default=None,
        description=(
            "Substring dans str(source_path.resolve()) (path du media en staging, avant dispatch). Case-sensitive."
        ),
    )
    path_regex: str | None = Field(
        default=None,
        description=(
            "Regex Python (re.search, non-anchored) sur str(source_path.resolve()). "
            "Case-sensitive sauf si tu mets (?i)."
        ),
    )
    title_regex: str | None = Field(
        default=None,
        description=(
            "Regex Python (re.search, non-anchored) sur le titre — NFO <title> si "
            "existe, sinon filename.stem. Case-sensitive sauf (?i)."
        ),
    )
    tmdb_genre_contains: str | None = Field(
        default=None,
        description=(
            "Substring dans un genre TMDB (nom tel que renvoyé par l'API — langue "
            "dépend de scraper_language). Match case-insensitive."
        ),
    )
    tmdb_keyword: list[str] | None = Field(
        default=None,
        description=(
            "Keyword(s) TMDB (API /keywords). Match si au moins un keyword présent. "
            "Nécessite scraper-side /keywords fetch (B4)."
        ),
    )

    category: str = Field(..., description="category_id résultat si cette règle match.")

    @model_validator(mode="after")
    def _exactly_one_pattern(self) -> "CategoryRule":
        """Validate that exactly one match pattern field is set.

        Returns:
            self after validation.

        Raises:
            ValueError: If zero or more than one pattern field is set.
        """

        # Treat empty string and empty list as "not set" to avoid rules that
        # parse but never match anything (silently wrong config).
        def _is_set(value: object) -> bool:
            if value is None:
                return False
            if isinstance(value, (str, list)) and len(value) == 0:
                return False
            return True

        fields = [
            self.path_contains,
            self.path_regex,
            self.title_regex,
            self.tmdb_genre_contains,
            self.tmdb_keyword,
        ]
        set_count = sum(1 for f in fields if _is_set(f))
        if set_count != 1:
            raise ValueError(
                f"CategoryRule must have exactly one non-empty match_* field (got {set_count}). "
                "Options: path_contains, path_regex, title_regex, tmdb_genre_contains, tmdb_keyword."
            )
        return self


class GenreMapping(_StrictModel):
    """Mapping genre ID → category_id par provider API.

    Les IDs genre sont stables (TMDB/TVDB ne les changent pas). Les noms entre
    ``//`` comments dans ``config.example.json5`` servent juste d'aide.

    Attributes:
        tmdb_movies: TMDB Movies genre_id → category_id.
        tmdb_tv: TMDB TV genre_id → category_id.
        tvdb: TVDB genre_id → category_id.
        default_movies_category: Fallback if no movie genre matches.
        default_tv_category: Fallback if no TV genre matches.
    """

    tmdb_movies: dict[int, str] = Field(default_factory=dict, description="TMDB Movies genre_id → category_id.")
    tmdb_tv: dict[int, str] = Field(default_factory=dict, description="TMDB TV genre_id → category_id.")
    tvdb: dict[int, str] = Field(default_factory=dict, description="TVDB genre_id → category_id.")

    default_movies_category: str = Field(default="movies", description="Fallback si aucun genre movie match.")
    default_tv_category: str = Field(default="tv_shows", description="Fallback si aucun genre TV match.")


class AnimeRule(_StrictModel):
    """Règle spéciale anime (pour TMDB qui n'a pas de genre Anime dédié).

    Si ``genre_id == requires_genre_id`` ET ``origin_country ∈ requires_origin_country``
    → ``maps_to``. Mettre ``enabled=false`` pour désactiver.

    Attributes:
        enabled: Whether this rule is active.
        requires_genre_id: TMDB Animation genre ID (default 16).
        requires_origin_country: ISO origin_country codes that trigger the rule.
        maps_to: Result category_id.
        applies_to: Which media types to apply the rule to.
    """

    enabled: bool = Field(default=True)
    requires_genre_id: int = Field(default=16, description="TMDB Animation genre ID.")
    requires_origin_country: list[str] = Field(default_factory=lambda: ["JP"], description="Codes ISO origin_country.")
    maps_to: str = Field(default="anime", description="category_id résultat.")
    applies_to: Literal["movies", "tv", "both"] = Field(default="tv", description="Sur quels types de média appliquer.")


class StagingDirConfig(_StrictModel):
    """Configuration for one staging subdirectory.

    Folder name on disk is derived as ``f"{id:03d}-{name.upper()}"``,
    e.g. ``{"id": 1, "name": "movies"}`` → ``"001-MOVIES"``.

    Attributes:
        id: Numeric directory prefix in [0, 999]. Must be unique across all entries.
        name: Kebab-case label (e.g. "movies", "tv-shows"). Used to build the folder name.
        file_type: Optional FileType enum value string this dir receives
            (e.g. "movie", "tvshow"). Duplicate values across entries are allowed —
            multiple dirs may share a FileType for domain-specific routing.
        role: Optional functional role. Currently only ``"ingest"`` is defined.
            Exactly one entry must declare ``role="ingest"`` when staging_dirs is present.
    """

    id: int = Field(..., ge=0, le=999, description="Numeric prefix [0-999]. Unique across entries.")
    name: str = Field(
        ...,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="Kebab-case label. Used to compute folder name via f'{id:03d}-{name.upper()}'.",
    )
    file_type: str | None = Field(
        default=None,
        description="FileType enum member string this dir receives (e.g. 'movie', 'tvshow').",
    )
    role: str | None = Field(
        default=None,
        description=(
            "Functional role. Only 'ingest' defined. Exactly one entry must have this when staging_dirs present."
        ),
    )

    @field_validator("file_type", mode="after")
    @classmethod
    def _validate_file_type(cls, v: str | None) -> str | None:
        """Validate file_type is a known FileType member.

        Args:
            v: The file_type string value, or None.

        Returns:
            The validated file_type string, or None.

        Raises:
            ValueError: If v is set but not a valid FileType member.
        """
        if v is None:
            return v
        from personalscraper.sorter.file_type import FileType  # local import avoids circular

        valid = {ft.value for ft in FileType}
        if v not in valid:
            raise ValueError(f"Invalid file_type '{v}'. Must be one of: {sorted(valid)}")
        return v


class PathConfig(_StrictModel):
    """Chemins non-disk utilisés par le pipeline.

    Attributes:
        torrent_complete_dir: Where qBittorrent deposits completed torrents.
        staging_dir: Intermediate staging folder (A TRIER) before dispatch.
        data_dir: Pipeline state directory (index, locks, analysis).
    """

    torrent_complete_dir: Path = Field(..., description="Où qBittorrent dépose les torrents finis.")
    staging_dir: Path = Field(..., description="Dossier A TRIER intermédiaire avant dispatch.")
    data_dir: Path = Field(
        default=Path("./.data"),
        description=(
            "State du pipeline (index, locks, analyse). "
            "Défaut: .data/ à la racine du repo. Doit être ABSOLU après init-config."
        ),
    )

    @field_validator("torrent_complete_dir", "staging_dir", "data_dir", mode="after")
    @classmethod
    def _must_be_absolute_or_resolve(cls, v: Path) -> Path:
        """Resolve relative paths to absolute via expanduser().resolve().

        Args:
            v: Path value from the config.

        Returns:
            Absolute path.
        """
        return v.expanduser().resolve() if not v.is_absolute() else v


class VideoPrefs(_StrictModel):
    """Préférences vidéo (reprend les champs de l'ancien VideoPreferences).

    Attributes:
        preferred_codec: Target codec for recommendations.
        fallback_codecs: Acceptable codecs (not flagged).
        rejected_codecs: Always-flagged codecs.
        preferred_resolution: Target resolution label.
        max_size_movie_gb: Maximum movie file size in GB.
        max_size_episode_gb: Maximum episode file size in GB.
    """

    preferred_codec: str = Field(default="hevc")
    fallback_codecs: list[str] = Field(default_factory=lambda: ["av1"])
    rejected_codecs: list[str] = Field(default_factory=lambda: ["mpeg2", "mpeg4"])
    preferred_resolution: str = Field(default="1080p")
    max_size_movie_gb: float = Field(default=4.0)
    max_size_episode_gb: float = Field(default=2.0)

    @model_validator(mode="after")
    def _codecs_disjoint(self) -> "VideoPrefs":
        """Validate that preferred/fallback and rejected codec sets don't overlap.

        Returns:
            self after validation.

        Raises:
            ValueError: If any codec appears in both accepted and rejected sets.
        """
        all_accepted = {self.preferred_codec} | set(self.fallback_codecs)
        rejected = set(self.rejected_codecs)
        overlap = all_accepted & rejected
        if overlap:
            raise ValueError(f"Codec sets overlap: {overlap}")
        return self


class AudioPrefs(_StrictModel):
    """Préférences audio (reprend les champs de l'ancien AudioPreferences).

    Attributes:
        profile_priority: Ordered preference for audio profiles.
        min_channels: Minimum channel count (flags mono as suspect).
        preferred_codec: Preferred audio codec (None = no preference).
    """

    profile_priority: list[str] = Field(default_factory=lambda: ["multi", "vf", "vostfr", "vo"])
    min_channels: int = Field(default=2, ge=1)
    preferred_codec: str | None = Field(default=None)


class SubtitlePrefs(_StrictModel):
    """Préférences subtitles (reprend les champs de l'ancien SubtitlePreferences).

    Language codes use ISO 639-2/T (fra, eng, jpn — NOT fre).

    Attributes:
        required_languages: Languages that must be present (ERROR if missing).
        preferred_languages: Languages that should be present (WARNING if missing).
        warn_if_missing: Whether missing subtitles produce warnings.
    """

    required_languages: list[str] = Field(default_factory=lambda: ["fra"])
    preferred_languages: list[str] = Field(default_factory=lambda: ["fra", "eng"])
    warn_if_missing: bool = Field(default=True)

    @model_validator(mode="after")
    def _required_subset_of_preferred(self) -> "SubtitlePrefs":
        """Validate required_languages is a subset of preferred_languages.

        Returns:
            self after validation.

        Raises:
            ValueError: If any required language is not in preferred_languages.
        """
        required, preferred = set(self.required_languages), set(self.preferred_languages)
        if not required.issubset(preferred):
            diff = required - preferred
            raise ValueError(f"required_languages must be a subset of preferred_languages, extra: {diff}")
        return self


class RuleCriteria(_StrictModel):
    """Critères encoding rule (reprend les champs de l'ancien RuleCriteria).

    String fields use case-insensitive substring matching.
    ID fields use exact matching. At least one field must be non-None.

    Attributes:
        genre: Genre substring to match (e.g. "Animation").
        title: Title substring to match.
        imdb_id: Exact IMDB ID (e.g. "tt4154796").
        tmdb_id: Exact TMDB ID (e.g. "12345").
    """

    genre: str | None = Field(default=None)
    title: str | None = Field(default=None)
    imdb_id: str | None = Field(default=None)
    tmdb_id: str | None = Field(default=None)

    @model_validator(mode="after")
    def _has_at_least_one(self) -> "RuleCriteria":
        """Validate that at least one criterion field is set.

        Returns:
            self after validation.

        Raises:
            ValueError: If all fields are None.
        """
        if all(v is None for v in (self.genre, self.title, self.imdb_id, self.tmdb_id)):
            raise ValueError("RuleCriteria must have at least one non-None field")
        return self


class EncodingRule(_StrictModel):
    """Règle d'override encoding (reprend les champs de l'ancien EncodingRule).

    Attributes:
        criteria: What to match against.
        resolution: Override resolution (None = no override).
        codec: Override codec (None = no override).
        max_size_gb: Override max size in GB (None = no override).
    """

    criteria: RuleCriteria
    resolution: str | None = Field(default=None)
    codec: str | None = Field(default=None)
    max_size_gb: float | None = Field(default=None)

    @model_validator(mode="after")
    def _has_at_least_one_target(self) -> "EncodingRule":
        """Validate that at least one target field is set.

        Returns:
            self after validation.

        Raises:
            ValueError: If all target fields are None.
        """
        if self.resolution is None and self.codec is None and self.max_size_gb is None:
            raise ValueError("EncodingRule must have at least one target (resolution, codec, or max_size_gb)")
        return self


class LibraryPrefs(_StrictModel):
    """Préférences library (reprend la structure de l'ancien library_preferences.json).

    Attributes:
        video: Video encoding preferences.
        audio: Audio track preferences.
        subtitles: Subtitle track preferences.
        encoding_rules: Override rules for specific media.
    """

    video: VideoPrefs = Field(default_factory=VideoPrefs)
    audio: AudioPrefs = Field(default_factory=AudioPrefs)
    subtitles: SubtitlePrefs = Field(default_factory=SubtitlePrefs)
    encoding_rules: list[EncodingRule] = Field(default_factory=list)


class Config(_StrictModel):
    """Top-level config.json5 parsed model.

    Attributes:
        config_version: Schema version for future migrations.
        paths: Non-disk paths used by the pipeline.
        disks: Storage disks with accepted categories.
        custom_categories: User-defined category IDs beyond the 11 builtins.
        categories: Category configuration (folder name, aliases).
        category_rules: Pattern-based classification rules, evaluated in order.
        anime_rule: Special anime detection rule (TMDB has no dedicated Anime genre).
        genre_mapping: Genre ID → category_id mapping by API provider.
        library: Library maintenance preferences.
    """

    config_version: int = Field(default=1, description="Schéma version pour migration future.")

    paths: PathConfig
    disks: Annotated[list[DiskConfig], Field(min_length=1)]

    # Categories: the 11 builtin IDs + user-declared customs
    custom_categories: list[str] = Field(
        default_factory=list,
        description="IDs user-défini au-delà des builtin.",
    )
    categories: dict[str, CategoryConfig] = Field(default_factory=dict)

    # Classification layers (priority 2-5, see DESIGN §Classification pipeline)
    category_rules: list[CategoryRule] = Field(
        default_factory=list,
        description="Règles pattern-based, évaluées en ordre.",
    )
    anime_rule: AnimeRule = Field(default_factory=AnimeRule)
    genre_mapping: GenreMapping = Field(default_factory=GenreMapping)

    library: LibraryPrefs = Field(default_factory=LibraryPrefs)

    staging_dirs: list[StagingDirConfig] | None = Field(
        default=None,
        description=(
            "Staging subdirectory layout. Required from Phase 2 onward. "
            "See MANUAL.md §Staging layout for migration steps."
        ),
    )

    @property
    def all_category_ids(self) -> frozenset[str]:
        """Return union of builtin and custom category IDs.

        Returns:
            Frozenset of all known category IDs.
        """
        return BUILTIN_CATEGORY_IDS | frozenset(self.custom_categories)

    @field_validator("custom_categories")
    @classmethod
    def _validate_custom_ids(cls, v: list[str]) -> list[str]:
        """Validate custom category IDs format and no builtin collision.

        Args:
            v: List of custom category ID strings.

        Returns:
            Validated list of custom category IDs.

        Raises:
            ValueError: If any ID has invalid format or conflicts with a builtin.
        """
        pattern = r"^[a-z][a-z0-9_]*$"
        for cid in v:
            if not re.match(pattern, cid):
                raise ValueError(f"Invalid custom category ID '{cid}'. Must match {pattern}")
            if cid in BUILTIN_CATEGORY_IDS:
                raise ValueError(f"Custom category '{cid}' conflicts with builtin ID")
        return v

    @model_validator(mode="after")
    def _validate_cross_references(self) -> "Config":
        """Validate all category ID references are consistent.

        Checks: categories dict keys ⊆ known, disks[*].categories ⊆ known,
        disk IDs unique, genre_mapping values ⊆ known, anime_rule.maps_to ⊆ known,
        category_rules[*].category ⊆ known.

        Returns:
            self after validation.

        Raises:
            ValueError: If any cross-reference is invalid or inconsistent.
        """
        known = self.all_category_ids

        # categories dict keys must be known IDs
        unknown_cats = set(self.categories.keys()) - known
        if unknown_cats:
            raise ValueError(f"Unknown category IDs in 'categories': {sorted(unknown_cats)}. Known: {sorted(known)}")

        # disks[*].categories must be known IDs
        for disk in self.disks:
            unknown = set(disk.categories) - known
            if unknown:
                raise ValueError(f"Disk '{disk.id}' references unknown categories: {sorted(unknown)}")

        # disk IDs must be unique
        dids = [d.id for d in self.disks]
        if len(dids) != len(set(dids)):
            raise ValueError(f"Duplicate disk IDs: {dids}")

        # genre_mapping values must be known IDs
        for provider, mapping in (
            ("tmdb_movies", self.genre_mapping.tmdb_movies),
            ("tmdb_tv", self.genre_mapping.tmdb_tv),
            ("tvdb", self.genre_mapping.tvdb),
        ):
            unknown = set(mapping.values()) - known
            if unknown:
                raise ValueError(f"genre_mapping.{provider} references unknown categories: {sorted(unknown)}")

        if self.genre_mapping.default_movies_category not in known:
            raise ValueError(f"default_movies_category '{self.genre_mapping.default_movies_category}' unknown")
        if self.genre_mapping.default_tv_category not in known:
            raise ValueError(f"default_tv_category '{self.genre_mapping.default_tv_category}' unknown")

        # anime_rule.maps_to must be a known ID
        if self.anime_rule.maps_to not in known:
            raise ValueError(f"anime_rule.maps_to '{self.anime_rule.maps_to}' unknown")

        # category_rules[*].category must be known IDs
        for i, rule in enumerate(self.category_rules):
            if rule.category not in known:
                raise ValueError(f"category_rules[{i}].category '{rule.category}' unknown")

        return self

    @model_validator(mode="after")
    def _validate_staging_dirs(self) -> "Config":
        """Validate staging_dirs entries when present.

        Checks: unique IDs, exactly one role='ingest' entry, all file_type
        values reference valid FileType members (already checked at field level,
        but cross-entry uniqueness of IDs is checked here).

        Returns:
            self after validation.

        Raises:
            ValueError: If IDs are duplicated or ingest role count != 1.
        """
        if self.staging_dirs is None:
            return self

        # Unique IDs
        seen_ids: set[int] = set()
        for entry in self.staging_dirs:
            if entry.id in seen_ids:
                raise ValueError(f"Duplicate staging_dirs id={entry.id}. Each entry must have a unique id.")
            seen_ids.add(entry.id)

        # Exactly one ingest role
        ingest_entries = [e for e in self.staging_dirs if e.role == "ingest"]
        if len(ingest_entries) != 1:
            raise ValueError(
                f"staging_dirs must have exactly one entry with role='ingest' "
                f"(found {len(ingest_entries)}). "
                "One entry (typically 097-TEMP) must declare role='ingest'."
            )

        return self

    def category(self, category_id: str) -> CategoryConfig:
        """Return category config for an ID, falling back to default label.

        Args:
            category_id: A builtin or custom category ID.

        Returns:
            CategoryConfig from ``self.categories`` if present, otherwise a
            default constructed from ``default_label(category_id)``.
        """
        return self.categories.get(category_id) or CategoryConfig.default_for(category_id)

    def disk_by_id(self, disk_id: str) -> DiskConfig | None:
        """Look up a disk by its ID.

        Args:
            disk_id: The disk identifier.

        Returns:
            Matching DiskConfig, or None if not found.
        """
        return next((d for d in self.disks if d.id == disk_id), None)

    def disks_accepting(self, category_id: str) -> list[DiskConfig]:
        """Return all disks that accept a given category.

        Args:
            category_id: Category ID to filter by.

        Returns:
            List of DiskConfig instances whose categories include category_id.
        """
        return [d for d in self.disks if category_id in d.categories]

    def resolve_category_alias(self, user_input: str) -> str | None:
        """Resolve a CLI --category input to a category_id.

        Accepts: (1) a valid ID directly, (2) an explicit alias in
        ``categories[id].aliases``. Does NOT accept folder_name as alias
        (many-to-one collision possible).

        Args:
            user_input: The --category argument value.

        Returns:
            Resolved category_id, or None if no match.
        """
        if user_input in self.all_category_ids:
            return user_input
        for cid, cfg in self.categories.items():
            if user_input in cfg.aliases:
                return cid
        return None
