"""ProvidersConfig Pydantic model for config/providers.json5 (DESIGN §5.4).

Each field maps a capability Protocol name to a ``dict[str, PositiveInt]``
of provider-name → priority. Lower priority = higher precedence.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class ProvidersConfig(BaseModel):
    """Pydantic root model for config/providers.json5.

    Strict: unknown sections raise (``extra="forbid"``). Each section maps
    provider name (str) → priority (positive int). Priority uniqueness
    within a section is validated by ``_no_duplicate_priorities``.
    """

    model_config = ConfigDict(extra="forbid")

    Searchable: dict[str, PositiveInt] = Field(default_factory=dict)
    MovieDetailsProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    TvDetailsProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    EpisodeFetcher: dict[str, PositiveInt] = Field(default_factory=dict)
    RatingProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    ArtworkProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    KeywordProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    VideoProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    RecommendationProvider: dict[str, PositiveInt] = Field(default_factory=dict)
    IDValidator: dict[str, PositiveInt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _no_duplicate_priorities(self) -> ProvidersConfig:
        """Validate that no section contains duplicate priority values.

        Returns:
            self if all priorities are unique per section.

        Raises:
            ValueError: If any section has duplicate priority values.
        """
        for name, section in self.model_dump().items():
            priorities = list(section.values())
            if len(priorities) != len(set(priorities)):
                raise ValueError(f"Section {name!r} has duplicate priority values: {priorities}")
        return self
