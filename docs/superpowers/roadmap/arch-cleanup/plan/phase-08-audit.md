# Phase 8 Legacy Consumer Audit

Date: 2026-05-03

## Scope

Audited legacy compatibility surfaces from the arch-cleanup design:

- `library-scan` / `library_scan`
- `media_index.json` / `media-index.json`
- v1 single-file config loading
- already-deprecated CLI flags

## Results

### `library-scan`

Command still exists in `personalscraper/commands/library.py` and is documented in
`docs/reference/commands.md`. No external launchd consumer was found under
`~/Library/LaunchAgents`; `~/.config/launchd` is absent on this machine.

Decision for 0.9.0: keep the command, emit a visible CLI warning and a
`DeprecationWarning`, and schedule removal for 0.10.0.

### `media_index.json`

No external consumer was found under `~/Library/LaunchAgents` or
`~/.homeassistant`. Production references are limited to the SQLite-backed
compatibility shim in `personalscraper/dispatch/media_index.py` and migration
warnings in `personalscraper/conf/migration.py`. Tests and docs retain fixture
or historical references.

Decision for 0.9.0: keep the shim behavior, continue warning when a legacy JSON
file is found, and document removal for 0.10.0. No writer path remains.

### v1 Config

The v1 single-file path is still loaded by `personalscraper/conf/loader.py`.
Tests cover v1 loading and migration parity. No external caller path was found.

Decision for 0.9.0: keep v1 load support, normalize the warning text with the
0.10.0 removal target, and add a structured warning event.

### Deprecated CLI Flags

The active deprecated flags are:

- `personalscraper library-scan --disk`
- `personalscraper library-scan --category`
- `personalscraper verify --fix`

Decision for 0.9.0: keep the flags working/ignored as today, normalize user
messages with the 0.10.0 removal target, and document them in the command
reference.
