"""Path config model (non-disk paths)."""

from contextvars import ContextVar
from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models._base import _StrictModel

_PROJECT_ROOT: ContextVar[Path | None] = ContextVar("_PROJECT_ROOT", default=None)
"""Set by ``load_config_dir`` before validation via ``ContextVar.set()``.
Resolves to ``config_dir.parent`` (the repo root). Relative paths in the config
are resolved against this directory rather than CWD, so that running
``personalscraper`` from a non-repo directory (e.g. the staging directory) still
resolves ``data_dir`` and similar paths correctly.

Thread-safe: each thread/async task sees its own value, so parallel config
validation (e.g. in the FastAPI threadpool) cannot cross-contaminate."""


class PathConfig(_StrictModel):
    """Non-disk paths used by the pipeline.

    Attributes:
        torrent_complete_dir: Where qBittorrent deposits completed torrents.
        staging_dir: Intermediate staging folder before dispatch.
        data_dir: Pipeline state directory (index, locks, analysis).
    """

    torrent_complete_dir: Path = Field(..., description="Where qBittorrent deposits completed torrents.")
    staging_dir: Path = Field(..., description="Intermediate staging folder before dispatch.")
    data_dir: Path = Field(
        default=Path("./.data"),
        description=(
            "Pipeline state directory (index, locks, analysis). "
            "Default: .data/ at the repo root. Must be ABSOLUTE after init-config."
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
        root = _PROJECT_ROOT.get()
        base = root if root is not None else Path.cwd()
        return (base / v).resolve()
