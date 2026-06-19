# Phase 4 — Lifecycle wiring: `.mcp.json` + `enabledMcpjsonServers`

**Goal**: make each launched worktree auto-register the `kanban` MCP server so the headless agent loads
it without an approval prompt. This is the **only** change to the deployed startup path; the daemon, the
poll loop, and every existing bin are untouched (DESIGN §8).

## Sub-phase 4a — `write_mcp_registration` in `adapters/perms.py`

Add a new function following the write pattern of `materialise_settings` (`adapters/perms.py:560`) /
`write_issue_pin` (`adapters/perms.py:718`):

```python
def write_mcp_registration(
    worktree: str | Path, *, root: Path, issue: int, project_id: str | None, multi_project: bool
) -> Path:
    """Write ``<worktree>/.mcp.json`` registering the project-scoped ``kanban`` MCP server.

    Claude Code reads ``.mcp.json`` from the project root. ``--project <project_id>`` is appended to
    ``args`` only when ``multi_project`` is true (the per-project disambiguation the bins use).
    """
```

Emitted file (DESIGN §8.1):

```json
{
  "mcpServers": {
    "kanban": {
      "command": "kanban",
      "args": ["mcp", "--root", "<root>", "--issue", "<n>"]
    }
  }
}
```

When `multi_project` is true, append `"--project", "<project_id>"` to `args`. Match the JSON-write idiom
(indentation, `json.dump`, mkdir-parents, mode) used by the neighbouring perms writers — read
`materialise_settings` / `write_issue_pin` first and mirror them.

## Sub-phase 4b — Pre-trust the server in `settings.json`

Project `.mcp.json` servers are not trusted by default, and these agents run non-interactively. So
`build_settings` (`adapters/perms.py:465`) / `materialise_settings` (`adapters/perms.py:560`) must also
emit:

```json
"enabledMcpjsonServers": ["kanban"]
```

into the worktree `settings.json`, scoped to the single named server (**not** a blanket
`enableAllProjectMcpServers`) so the agent loads `kanban` without an approval prompt (DESIGN §8.2).
Read `build_settings` to find where the settings dict is assembled and add the key there; confirm there
is no existing `enabledMcpjsonServers`/`enableAllProjectMcpServers` key today (verified absent in
`adapters/perms.py`) so this is a clean addition.

## Sub-phase 4c — Call `write_mcp_registration` from the launch block

In `app/actions.py`, the `LaunchAction.execute` block that writes settings/skills/bin-symlinks/pins
(`app/actions.py:309-338`) calls `materialise_settings(profile, worktree, issue=issue,
permission_mode=self.permission_mode)` (`app/actions.py:316`), then `provision_worktree_skills`,
`provision_worktree_bin`, `ensure_manual_merge_mode`, `write_issue_pin(worktree, issue)`, and
conditionally `write_project_pin(worktree, deps.project_id)`.

Add a call to `write_mcp_registration(...)` in this same block (right after `materialise_settings`, per
DESIGN §8.1). Source the args from the already-available launch context:
- `root` — the runtime root used by the launch/deps (confirm the exact attribute on `deps`/the action
  that holds the runtime root; the existing pins already resolve a root);
- `issue` — `issue` (already in scope);
- `project_id` — `deps.project_id` (the same value `write_project_pin` uses);
- `multi_project` — `deps.multi_project` (the same flag guarding `write_project_pin` at
  `app/actions.py:~336`).

Mirror the existing conditional shape: `write_mcp_registration` is always called (the registration is
valid for N=1 too — it simply omits `--project`); only the `--project` arg is gated on `multi_project`
inside the function. Verify `deps.multi_project` / `deps.project_id` are the real attribute names
(they back the `write_project_pin` branch already in this block) before use.

## Tests — `tests/test_perms.py` (+ `tests/app/` if needed)

Per DESIGN §12:
- `write_mcp_registration` writes a well-formed `.mcp.json`:
  - N=1 (`multi_project=False`): `args == ["mcp", "--root", "<root>", "--issue", "<n>"]` (no
    `--project`).
  - N>1 (`multi_project=True`, `project_id="PVT_…"`): `args` ends with `"--project", "<project_id>"`.
  - `command == "kanban"`, server key is `"kanban"`.
- the materialised `settings.json` carries `enabledMcpjsonServers == ["kanban"]` (assert via the real
  `materialise_settings`/`build_settings` output, not a hand-built dict).
- (optional) an `app/actions` test asserting the launch block calls `write_mcp_registration` with the
  launch's issue/root — extend the existing `LaunchAction.execute` test harness rather than inventing a
  new one; locate it under `tests/app/`.

Place perms tests in `tests/test_perms.py` (the file DESIGN §12 names — confirm its actual path; if the
suite keeps perms tests under `tests/adapters/`, follow the real location).

## Gate for Phase 4

- `pytest tests/test_perms.py tests/app/ -q` green.
- Full `make check` green.
- Manual sanity (no live launch needed): `kanban mcp --help` still works; a unit-level
  `write_mcp_registration(tmp, root=…, issue=9, project_id=None, multi_project=False)` produces the
  exact JSON above.

## Commit

`feat(conduit): phase 4 — worktree .mcp.json registration + enabledMcpjsonServers pre-trust`
