"""Category-related config models.

Includes: category config, pattern-based classification rules, genre mappings,
and the special anime detection rule.
"""

from typing import Literal

from pydantic import Field, model_validator

from personalscraper.conf.ids import default_label
from personalscraper.conf.models._base import _StrictModel


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

    # Optional media-type filter.
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
    ``//`` comments dans ``config.example/`` servent juste d'aide.

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
    applies_to: Literal["movie", "tv", "both"] = Field(default="tv", description="Sur quels types de média appliquer.")
