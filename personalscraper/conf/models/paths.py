"""Path config model (non-disk paths)."""

from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models._base import _StrictModel

_PROJECT_ROOT: Path | None = None
"""Set by ``load_config_dir`` before validation. Resolves to ``config_dir.parent``
(the repo root). Relative paths in the config are resolved against this directory
rather than CWD, so that running ``personalscraper`` from a non-repo directory
(e.g. the staging directory) still resolves ``data_dir`` and similar paths correctly."""


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
        """Resolve relative paths against project root (or CWD as last resort).

        Args:
            v: Path value from the config.

        Returns:
            Absolute path.
        """
        if v.is_absolute():
            return v
        base = _PROJECT_ROOT if _PROJECT_ROOT is not None else Path.cwd()
        return (base / v).resolve()
