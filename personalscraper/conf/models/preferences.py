"""Library preference models (video, audio, subtitles, encoding rules)."""

from pydantic import Field, model_validator

from personalscraper.conf.models._base import _StrictModel


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
    """Préférences audio.

    Attributes:
        profile_priority: Ordered preference for audio profiles.
    """

    profile_priority: list[str] = Field(default_factory=lambda: ["multi", "vf", "vostfr", "vo"])


class SubtitlePrefs(_StrictModel):
    """Préférences subtitles.

    Language codes use ISO 639-2/T (fra, eng, jpn — NOT fre).

    Attributes:
        required_languages: Languages that must be present.
    """

    required_languages: list[str] = Field(default_factory=lambda: ["fra"])


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
