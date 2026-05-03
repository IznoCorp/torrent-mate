"""Disk storage config model."""

from pathlib import Path
from typing import Annotated

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


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
