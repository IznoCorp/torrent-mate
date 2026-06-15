"""Top-level Config model with all validators and helper methods."""

import re
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator

from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS
from personalscraper.conf.models._base import _StrictModel
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import (
    MetadataConfig,
    NotifyConfig,
    RankingConfig,
    TorrentConfig,
    TrackerConfig,
)
from personalscraper.conf.models.categories import (
    AnimeRule,
    CategoryConfig,
    CategoryRule,
    GenreMapping,
)
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.fuzzy import FuzzyMatchConfig
from personalscraper.conf.models.indexer import IndexerConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.preferences import LibraryPrefs
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.conf.models.scraper import (
    IngestConfig,
    ProcessCleanConfig,
    ScraperConfig,
    SortConfig,
    ThresholdsConfig,
)
from personalscraper.conf.models.staging import StagingDirConfig
from personalscraper.conf.models.trailers import TrailersConfig

# ---------------------------------------------------------------------------
# Type alias re-exported for consumers that import from conf.models
# ---------------------------------------------------------------------------

#: Mapping of arbitrary extra attributes for future schema extensions.
#: Not used internally; declared here so mypy is happy when code passes
#: ``dict[str, Any]`` payloads to validators.
_AnyDict = dict[str, Any]


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
        ingest: Ingest step tunables (min_ratio threshold, etc.).
        sort: Sort step tunables (verify_seed_pure opt-in guard, enforced).
        process_clean: Process clean sub-step tunables (verify_seed_pure flag is
            reserved — not yet enforced; see ``ProcessCleanConfig``).
        trailers: Trailer download feature configuration. Disabled by default (enabled=False).
        indexer: Media indexer sub-system configuration.
        acquire: Acquisition lobe SQLite store configuration (RP3).
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

    fuzzy_match: FuzzyMatchConfig = Field(default_factory=FuzzyMatchConfig)

    scraper: ScraperConfig = Field(default_factory=ScraperConfig)

    ingest: IngestConfig = Field(default_factory=IngestConfig)

    sort: SortConfig = Field(default_factory=SortConfig)

    process_clean: ProcessCleanConfig = Field(default_factory=ProcessCleanConfig)

    library: LibraryPrefs = Field(default_factory=LibraryPrefs)

    staging_dirs: list[StagingDirConfig] = Field(
        ...,
        description=("Staging subdirectory layout. Required. See MANUAL.md §Staging layout for migration steps."),
    )

    trailers: TrailersConfig = Field(default_factory=TrailersConfig)

    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)

    indexer: IndexerConfig = Field(default_factory=IndexerConfig)

    acquire: AcquireConfig = Field(default_factory=AcquireConfig)

    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    torrent: TorrentConfig = Field(default_factory=TorrentConfig)
    tracker: TrackerConfig = Field(default_factory=TrackerConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)

    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

    @model_validator(mode="after")
    def _resolve_derived_paths(self) -> "Config":
        """Resolve derived paths from ``paths.data_dir`` when not explicitly set.

        - ``indexer.db_path`` → ``paths.data_dir / 'library.db'``
        - ``acquire.db_path`` → ``paths.data_dir / 'acquire.db'``
        - ``trailers.state_file`` → ``paths.data_dir / 'trailers_state.json'``

        Returns:
            self with derived paths resolved.
        """
        if self.indexer.db_path is None:
            object.__setattr__(self.indexer, "db_path", self.paths.data_dir / "library.db")
        if self.acquire.db_path is None:
            object.__setattr__(self.acquire, "db_path", self.paths.data_dir / "acquire.db")
        if self.trailers.state_file is None:
            object.__setattr__(self.trailers, "state_file", str(self.paths.data_dir / "trailers_state.json"))
        return self

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

    @model_validator(mode="before")
    @classmethod
    def _check_staging_dirs_present(cls, data: dict[str, object]) -> dict[str, object]:
        """Emit a friendly error when staging_dirs is missing.

        Args:
            data: Raw config dict[str, object] before field validation.

        Returns:
            data unchanged (validation continues normally).

        Raises:
            ValueError: With a human-readable migration hint if staging_dirs is absent.
        """
        if isinstance(data, dict) and "staging_dirs" not in data:
            raise ValueError(
                "`staging_dirs` missing from config.json5 — see MANUAL.md §Staging layout for migration steps."
            )
        return data

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
                "One entry (the ingest staging dir) must declare role='ingest'."
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
