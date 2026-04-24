# Storage Reference

Storage disk layout, NTFS/macFUSE constraints, rsync flags, and disk space rules.

## Storage Disks

All 4 disks are **NTFS** formatted, mounted via **macFUSE** (ntfstool driver) over USB.

| Disk  | Mount                 | Filesystem | Categories                                                                                                                                    |
| ----- | --------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1 | /Volumes/Disk1/medias | NTFS       | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2 | /Volumes/Disk2/medias | NTFS       | series, series animes                                                                                                                         |
| Disk3 | /Volumes/Disk3/medias | NTFS       | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4 | /Volumes/Disk4/medias | NTFS       | films, films animations, series, series animations, series documentaires, emissions                                                           |

## Move Rules (dispatch)

- **Movies** (films, animations, documentaires, spectacles, theatre): if a folder with the same name already exists on a disk, **replace it** with the new version from staging area.
- **TV Shows** (series, animations, documentaires): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

## NTFS via macFUSE constraints

- **No Unix permissions** — `chmod`, `chown`, `chgrp` are no-ops or fail with EPERM. All files appear as `rwxrwxrwx` owned by the mounting user.
- **rsync must use `--no-perms --no-owner --no-group`** — `rsync -a` (which includes `-pgo`) fails with `Operation not permitted` on set times/permissions. The dispatcher uses `-a --no-perms --no-owner --no-group` to work around this.
- **Mount flags**: `macfuse, local, synchronous, noatime, nobrowse` — `synchronous` means every write is committed immediately (slower but safer for USB).
- **`_force_rmtree` limitation** — `os.chmod()` before retry has no effect on NTFS. Deletion failures on `.actors/` or `.DS_Store` are NTFS metadata issues, not permission issues.

## Disk Space Threshold

Unified formula:

```
free_space_gb >= max(min_free_gb, item_size_gb * 1.5)
```

`choose_disk(allow_create_category=True)` for new items: falls back to any disk with space if no disk has the category. Logs WARNING for overflow (category not in disk config).

## Paths

- Paths contain spaces (`/path/to/staging/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails; use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.
