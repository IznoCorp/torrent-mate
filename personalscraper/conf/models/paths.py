"""Path config model (non-disk paths)."""

from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models._base import _StrictModel


class PathConfig(_StrictModel):
    """Chemins non-disk utilisés par le pipeline.

    Attributes:
        torrent_complete_dir: Where qBittorrent deposits completed torrents.
        staging_dir: Intermediate staging folder before dispatch.
        data_dir: Pipeline state directory (index, locks, analysis).
    """

    torrent_complete_dir: Path = Field(..., description="Où qBittorrent dépose les torrents finis.")
    staging_dir: Path = Field(..., description="Dossier de staging intermédiaire avant dispatch.")
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
