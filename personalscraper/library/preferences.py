"""Pydantic models for library maintenance preferences.

Loaded from a JSON file (library_preferences.json in .personalscraper/).
Uses pydantic BaseModel (not @dataclass) because these are user-facing
configuration that benefits from validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class VideoPreferences(BaseModel):
    """Video encoding preferences.

    Attributes:
        preferred_codec: Target codec for recommendations.
        fallback_codecs: Acceptable codecs (not flagged).
        rejected_codecs: Always-flagged codecs.
        preferred_resolution: Target resolution label.
        max_size_movie_gb: Maximum movie file size in GB.
        max_size_episode_gb: Maximum episode file size in GB.
    """

    preferred_codec: str = "hevc"
    fallback_codecs: list[str] = Field(default_factory=lambda: ["av1"])
    rejected_codecs: list[str] = Field(default_factory=lambda: ["mpeg2", "mpeg4"])
    preferred_resolution: str = "1080p"
    max_size_movie_gb: float = 4.0
    max_size_episode_gb: float = 2.0

    @model_validator(mode="after")
    def codecs_are_disjoint(self) -> Self:
        """Ensure preferred, fallback, and rejected codec sets don't overlap."""
        all_codecs = {self.preferred_codec} | set(self.fallback_codecs)
        rejected = set(self.rejected_codecs)
        overlap = all_codecs & rejected
        if overlap:
            msg = f"Codec sets overlap: {overlap}"
            raise ValueError(msg)
        return self


class AudioPreferences(BaseModel):
    """Audio track preferences.

    Attributes:
        profile_priority: Ordered preference for audio profiles.
        min_channels: Minimum channel count (flags mono as suspect).
        preferred_codec: Preferred audio codec (None = no preference).
    """

    profile_priority: list[str] = Field(
        default_factory=lambda: ["multi", "vf", "vostfr", "vo"],
    )
    min_channels: int = Field(default=2, ge=1)
    preferred_codec: str | None = None


class SubtitlePreferences(BaseModel):
    """Subtitle track preferences.

    Language codes use ISO 639-2/T (fra, eng, jpn — NOT fre).

    Attributes:
        required_languages: Languages that must be present (ERROR if missing).
        preferred_languages: Languages that should be present (WARNING if missing).
        warn_if_missing: Whether missing subtitles produce warnings.
    """

    required_languages: list[str] = Field(default_factory=lambda: ["fra"])
    preferred_languages: list[str] = Field(default_factory=lambda: ["fra", "eng"])
    warn_if_missing: bool = True

    @model_validator(mode="after")
    def required_subset_of_preferred(self) -> Self:
        """Ensure required_languages is a subset of preferred_languages."""
        required = set(self.required_languages)
        preferred = set(self.preferred_languages)
        if not required.issubset(preferred):
            diff = required - preferred
            msg = f"required_languages must be a subset of preferred_languages, extra: {diff}"
            raise ValueError(msg)
        return self


class RuleCriteria(BaseModel):
    """Structured criteria for encoding override rules.

    String fields use case-insensitive substring matching.
    ID fields use exact matching.
    At least one field must be non-None.

    Attributes:
        genre: Genre substring to match (e.g. "Animation").
        title: Title substring to match.
        imdb_id: Exact IMDB ID (e.g. "tt4154796").
        tmdb_id: Exact TMDB ID (e.g. "12345").
    """

    genre: str | None = None
    title: str | None = None
    imdb_id: str | None = None
    tmdb_id: str | None = None

    @model_validator(mode="after")
    def has_at_least_one_criterion(self) -> Self:
        """At least one criterion must be set."""
        if all(v is None for v in (self.genre, self.title, self.imdb_id, self.tmdb_id)):
            msg = "RuleCriteria must have at least one non-None field"
            raise ValueError(msg)
        return self


class EncodingRule(BaseModel):
    """Override rule for specific media matching criteria.

    Attributes:
        criteria: What to match against.
        resolution: Override resolution (None = no override).
        codec: Override codec (None = no override).
        max_size_gb: Override max size in GB (None = no override).
    """

    criteria: RuleCriteria
    resolution: str | None = None
    codec: str | None = None
    max_size_gb: float | None = None

    @model_validator(mode="after")
    def has_at_least_one_target(self) -> Self:
        """At least one of resolution, codec, max_size_gb must be set."""
        if self.resolution is None and self.codec is None and self.max_size_gb is None:
            msg = "EncodingRule must have at least one target (resolution, codec, or max_size_gb)"
            raise ValueError(msg)
        return self


class LibraryPreferences(BaseModel):
    """Root preferences model for library maintenance.

    Loaded from library_preferences.json in .personalscraper/.

    Attributes:
        video: Video encoding preferences.
        audio: Audio track preferences.
        subtitles: Subtitle track preferences.
        encoding_rules: Override rules for specific media.
    """

    video: VideoPreferences = Field(default_factory=VideoPreferences)
    audio: AudioPreferences = Field(default_factory=AudioPreferences)
    subtitles: SubtitlePreferences = Field(default_factory=SubtitlePreferences)
    encoding_rules: list[EncodingRule] = Field(default_factory=list)
