"""Staging directory config model."""

from typing import Literal

from pydantic import Field, field_validator

from personalscraper.conf.models._base import _StrictModel


class StagingDirConfig(_StrictModel):
    """Configuration for one staging subdirectory.

    Folder name on disk is derived as ``f"{id:03d}-{name.upper()}"``,
    e.g. ``{"id": 1, "name": "movies"}`` → ``f"{id:03d}-{name.upper()}"``.

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
    role: Literal["ingest"] | None = Field(
        default=None,
        description=(
            "Functional role tag. Allowed value: 'ingest' (the only defined role). "
            "Exactly one staging_dirs entry must declare role='ingest' when staging_dirs is present."
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
