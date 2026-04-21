"""Pure functions: resolve category_id to folder path and pick best disk.

These functions are stateless — they take Config and current free-space data
(provided by the caller) and return deterministic results. No I/O, no
filesystem access.

Caller responsibilities:
- Build ``free_space_by_id`` by querying mounted disks (e.g. via
  ``dispatch.disk_scanner.get_disk_status``).
- Set ``free_space_by_id[disk.id] = 0.0`` for unmounted disks so they are
  filtered out by the threshold check automatically.
"""

from pathlib import Path

from personalscraper.conf.models import Config, DiskConfig


def folder_for(config: Config, disk: DiskConfig, category_id: str) -> Path:
    """Return the absolute folder path for a category on a given disk.

    Looks up ``config.category(category_id)`` (falling back to
    ``default_label`` if the category has no explicit entry) and returns
    ``disk.path / category_config.folder_name``.

    Args:
        config: The loaded and validated Config instance.
        disk: The target DiskConfig (must be one of ``config.disks``).
        category_id: A builtin or custom category ID (e.g. ``"movies"``).

    Returns:
        Absolute Path — ``disk.path / folder_name`` — not guaranteed to
        exist on the filesystem; callers should create it if needed.

    Example:
        >>> folder_for(cfg, disk, "movies")
        PosixPath('/mnt/drive_a/movies')
    """
    return disk.path / config.category(category_id).folder_name


def pick_disk_for(
    config: Config,
    category_id: str,
    free_space_by_id: dict[str, float],
    min_free_gb: float,
    item_size_gb: float,
) -> DiskConfig | None:
    """Pick the best disk to dispatch a media item of a given category.

    Threshold formula (preserved from V14):
        threshold = max(min_free_gb, item_size_gb * 1.5)

    The 1.5× multiplier leaves headroom for rsync temp files and partial
    writes. ``min_free_gb`` acts as an absolute floor regardless of item size.

    Eligibility filter:
        A disk is eligible if ``free_space_by_id.get(disk.id, 0.0) >= threshold``.

    Selection criterion:
        Among eligible disks, return the one with the **most** free space
        (greedy fill strategy — keeps disks balanced over time).

    Caller responsibility:
        - Pass ``free_space_by_id[disk.id] = 0.0`` for unmounted/offline disks
          so they are filtered out automatically (0.0 < any positive threshold).
        - Only disks listed in ``config.disks_accepting(category_id)`` are
          considered; disks that do not accept the category are ignored entirely.

    Args:
        config: The loaded and validated Config instance.
        category_id: A builtin or custom category ID (e.g. ``"movies"``).
        free_space_by_id: Mapping from disk ID to free space in GB. Missing
            keys default to 0.0 (treated as unmounted).
        min_free_gb: Absolute minimum free space required on the target disk
            after the move (from Settings or CLI override).
        item_size_gb: Estimated size of the item being dispatched in GB.

    Returns:
        The :class:`~personalscraper.conf.models.DiskConfig` with the most
        free space among eligible disks, or ``None`` if no disk qualifies.

    Example:
        >>> pick_disk_for(cfg, "movies", {"drive_a": 200.0, "drive_b": 50.0}, 100.0, 4.0)
        DiskConfig(id='drive_a', ...)
    """
    # V14 threshold: item_size_gb * 1.5 ensures write headroom; min_free_gb
    # is a policy floor independent of item size.
    threshold = max(min_free_gb, item_size_gb * 1.5)

    candidates = config.disks_accepting(category_id)
    eligible = [d for d in candidates if free_space_by_id.get(d.id, 0.0) >= threshold]

    if not eligible:
        return None

    # Return the disk with the most free space (greedy-fill, not round-robin).
    return max(eligible, key=lambda d: free_space_by_id[d.id])
