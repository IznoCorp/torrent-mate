# Phase 14 — Clone bootstrap + worktree skill provisioning (ensure_clone · provision skills · locks · launch argv · registry)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §4.3 (init steps), §4.4/§4.5 (1 clone per repo, worktree base), §4.6 (launch
> sequencing), §10 (security & autonomy — token isolation, manual-merge pin), §11 (port-from-PoC; the
> PoC is the source of truth). POC_PARITY_AUDIT.md "CLI command surface" (config_dir / dev_repo_path /
> init ensure_clone) + "engine adapters" (ensure_clone, credential-helper isolation, launch
> sequencing, provision_worktree_skills, per-repo flock locks).
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`):
> `<OLD>/engine/worktree.py:20-97` (`ensure_clone` — git init in place, idempotent origin, credential
> helper token isolation) ·
> `<OLD>/engine/launch.py:80-115` (`build_claude_argv`) · `:118-143`
> (`_default_claude_runner` — the `; kanban-session-end <issue>` wrapper) · `:171-244`
> (`start_session` provisioning + launch order) ·
> `<OLD>/engine/perms.py:351-391` (`provision_worktree_skills` — COPY skills/commands/agents) ·
> `:394-419` (`ensure_manual_merge_mode`) ·
> `<OLD>/engine/locks.py:18-44` (`resource_lock` — per-repo flock) ·
> `<OLD>/cli/registry.py:29-40` (`ProjectEntry.config_dir` + `dev_repo_path` fields) ·
> `<OLD>/cli/runners.py:128-129,165-190` (`config_dir` computed + `--dev-repo-path` threaded + the
> `ensure_clone` init step) · `<OLD>/cli/plan_init.py:52,74-76,93-94` (`ensure_clone` step ordered +
> config_dir / dev_repo_path into the registry) · `<OLD>/cli/executors.py:56-67,170-176`
> (`_default_clone` → `ensure_clone`).
> **NB the `bin/` dir is the kanban-skill root, a SIBLING of the `kanbanmate/` package** (i.e.
> `.../skills/kanban/bin/`, not `.../skills/kanban/kanbanmate/bin/`); OLD's `config_dir` resolved to
> the skill config root via `Path(__file__).resolve().parents[2].parent.parent`. NEW root:
> `/Users/izno/dev/KanbanMate/src/kanbanmate/`.

**Goal**: restore the LOCAL CLONE bootstrap + WORKTREE SKILL PROVISIONING the first extraction
dropped wholesale, so a fresh `kanban init` produces a working clone base AND a launched agent can
resolve the `/implement:*` skills its column prompt invokes. Five confirmed feature losses, all
unrelated to the n8n→polling pivot (POC_PARITY_AUDIT.md), all faithful ports:

1. **`ensure_clone`** (HIGH) — `init` bootstraps the per-repo clone IN PLACE (`git init`,
   non-destructive), idempotent origin add/set-url that self-heals a partial clone, and a
   `git fetch origin <base>`. NEW's `GitWorktreeWorkspace.ensure_worktree` blindly assumes the clone +
   origin already exist (`git -C <clone> fetch origin <base>` — POC_PARITY_AUDIT.md §engine).
2. **Credential-helper token isolation** (HIGH) — keep `origin` TOKENLESS and install a git
   credential helper that reads the PAT from a 600-mode file AT FETCH TIME, so the long-lived token is
   NEVER persisted in `<clone>/.git/config` (clears the inherited helper chain with an empty `""`
   reset first). A documented SECURITY control (DESIGN §10) NEW dropped entirely.
3. **`provision_worktree_skills` + `ensure_manual_merge_mode`** (MEDIUM) — COPY (never symlink) the
   project's `skills/`/`commands/`/`agents/` into `<worktree>/.claude/` so `/implement:*` resolves
   (the config repo is gitignored, absent from the clone checkout), and pin IMPLEMENTATION.md to
   `**PR merge**: manual` so an auto-triggered pr-review hands off to a human (defense-in-depth
   alongside the deny-list).
4. **Launch argv builder** (HIGH) — `claude --session-id <uuid> --permission-mode <mode>
--add-dir <worktree>` with `; kanban-session-end <issue>` appended (`;` not `&&` so the wrapper
   ALWAYS fires) and a UUID session id (restoring `claude --resume <uuid>` — a headline KanbanMate
   feature, DESIGN §8.3). NEW sends a single static `agent_command` with no flags and no session-end
   wrapper, so a cleanly-exited agent never frees its state until the reaper's 1800s TTL.
5. **Registry `config_dir` + `dev_repo_path`** (HIGH/MEDIUM) — `ProjectEntry` records the project's
   `.claude` dir (so the launcher provisions skills) AND the operator's dev-clone path (post-merge
   ff-only update target, DESIGN §10); `kanban init --dev-repo-path` persists the latter, and `init`
   runs `ensure_clone` so the clone is created at init time. Plus the per-repo flock
   (`resource_lock("repo__<repo>")`) serialising clone mutations.

> **Operator decision — FULL parity, NOT a subset.** Every behaviour the PoC produces is reproduced
> in NEW. The ONLY deliberate divergences (each documented in-code): the COPY-not-symlink provisioning
> (OLD already copies — verbatim), the breadcrumb/key changes are out of scope (phase 8 owns them),
> and the launch profile/prompt-fill is column-class-driven in NEW (the per-column prompt assembly is
> a SEPARATE runner-slice loss out of this phase — this phase restores the argv SHAPE + session-end
> wrapper + uuid + provisioning, not the per-column prompt pipeline). The credential-helper, the
> tokenless origin, and the `;`-wrapper are ported byte-faithful (they are SECURITY / correctness
> controls, never "simplified").

---

## Gate

Phases 1–11 complete; phase 8 (rich sticky + Cancel teardown) landed `TicketState` widening +
`upsert_stage_comment`; branch `feat/genesis`; `make check` green at start. Re-sync confirmed
(DESIGN §11 pre-implementation gate): `<OLD>/engine/worktree.py`, `launch.py`, `perms.py`, `locks.py`
and the `cli/registry.py`/`runners.py`/`plan_init.py`/`executors.py` chain are present in
`.claude/skills/kanban/` and read for this port. Clear `.mypy_cache` before the authoritative gate
check (its incremental cache has masked real errors in this repo).

---

## 14.1 — `ensure_clone` on the `Workspace` port + adapter (git init in place, idempotent origin, fetch)

**The gap.** NEW has NO clone-bootstrap anywhere (`rg --type py "ensure_clone|git init|remote add|
remote set-url|get-url" src` → zero matches). `GitWorktreeWorkspace.ensure_worktree`
(`adapters/workspace/worktree.py:74-90`) runs `git -C <clone> fetch origin <base>` + `worktree add`
ASSUMING the clone + origin already exist; `cli/init.py` only writes
`<clone>/.claude/kanban/columns.yml` (init.py:248-251) and never creates the clone. A fresh
`kanban init` cannot produce a working clone base — the daemon's first launch fails at
`git -C <clone> fetch` (POC_PARITY_AUDIT.md §engine, [HIGH] ensure_clone). This sub-phase ports the
NON-CREDENTIAL half of `ensure_clone`; 14.2 adds the credential helper.

**Layer**: `ports/` (extend the `Workspace` Protocol — pure) · `adapters/workspace/` (implement on
`GitWorktreeWorkspace`, mirrors PoC `engine/worktree.py:20-97`).

**Files**: `src/kanbanmate/ports/workspace.py` (add `ensure_clone` to the `Workspace` Protocol),
`src/kanbanmate/adapters/workspace/worktree.py` (implement `ensure_clone`),
`tests/adapters/test_workspace.py` (extend — the adapter test lives here, NOT
`tests/adapters/workspace/test_workspace.py`).

- [ ] Add `ensure_clone(self, repo_url: str, base: str = "main", *, token_path: str | None = None)
    -> Path` to the `Workspace` Protocol. English Google-style docstring stating: bootstraps the
      per-repo clone (the base of all worktrees), idempotent + NON-DESTRUCTIVE (`git init` in place
      preserves untracked files such as the generated `columns.yml` — never re-clones), self-heals a
      partial clone (origin missing), and fetches `origin/<base>`. `token_path` (14.2) wires the
      credential helper; `None` → tokenless/public.
- [ ] Implement `ensure_clone` on `GitWorktreeWorkspace`, porting PoC `engine/worktree.py:59-97`
      verbatim-in-spirit against `self._clone` + `self._runner` (argv lists, never `shell=True`):
  - `self._clone.mkdir(parents=True, exist_ok=True)`; if `not (self._clone / ".git").exists()`:
    `runner(["git", "init", str(self._clone)], check=True)` — IN PLACE, never delete-and-reclone
    (preserves the `init`-written `columns.yml`).
  - **Idempotent origin, init-independent (self-heal):** probe
    `runner(["git", "-C", str(clone), "remote", "get-url", "origin"], capture_output=True, text=True,
check=False).returncode == 0`; `verb = "set-url" if has_origin else "add"`; then
    `runner(["git", "-C", str(clone), "remote", verb, "origin", repo_url], check=True)`. Document WHY
    the probe-then-branch (not init-coupled): it recovers a clone left partial by a crash between
    `git init` and `remote add` — the old branch-coupled logic would `set-url` a missing remote and
    fail every re-run (PoC comment worktree.py:63-67).
  - `token_path` branch: deferred to 14.2 (leave a `# 14.2: credential helper` placeholder calling a
    private helper that is a no-op until 14.2, OR fold the whole credential block in 14.2 — either way
    14.1 must not persist the token in config).
  - `runner(["git", "-C", str(clone), "fetch", "origin", base], check=True)`; `return
clone.resolve()`.
- [ ] Tests (mock `subprocess.run`, NO real git): a fresh dir with no `.git` → `git init` runs THEN
      `remote add origin` (not `set-url`) THEN `fetch origin <base>`; an existing clone WITH origin →
      NO `git init`, `remote set-url origin` (not `add`); a partial clone (`.git` present, origin
      missing) → `remote add` (self-heal, not `set-url`); the returned path is `clone.resolve()`. NO
      `--force` anywhere. Assert every git call is an argv list (no `shell=True`).
- [ ] Verify: `make check` green; layering guard sees `ensure_clone` stays in `adapters/workspace/`
      (no upward import); the new Protocol method is pure in `ports/`.

```bash
git commit -m "feat(genesis): ensure_clone bootstraps the per-repo clone (git init in place, idempotent origin, fetch — port of engine/worktree.py)"
```

---

## 14.2 — `ensure_clone` credential-helper token isolation (tokenless origin, fetch-time PAT, security)

**The gap.** PoC `ensure_clone` (`engine/worktree.py:76-95`, tested at
`tests/test_worktree_cmd.py:92-130`) keeps `origin` TOKENLESS and installs a git credential helper
that reads the PAT from a 600-mode file AT FETCH TIME — the token is NEVER written into
`<clone>/.git/config`, raising the bar against an agent exfiltrating a long-lived credential from
inside its worktree. NEW has NO credential helper at all (`rg --type py "credential\.|x-access-token|
git-credential" src` → zero); token handling is solely `adapters/github/token.py` for the urllib
client. A documented SECURITY control (DESIGN §10) dropped without rationale (POC_PARITY_AUDIT.md
§engine, [HIGH] credential-helper).

**Layer**: `adapters/workspace/` (the credential block of `ensure_clone`).

**Files**: `src/kanbanmate/adapters/workspace/worktree.py` (the `token_path` branch),
`tests/adapters/test_workspace.py` (extend — the security assertions).

- [ ] Implement the `token_path` branch of `ensure_clone`, porting PoC `engine/worktree.py:76-95`
      byte-faithful (argv lists; `import shlex` + `from urllib.parse import urlparse` at module top):
  - `host = urlparse(repo_url).hostname or "github.com"`; `cred = f"credential.https://{host}"`.
  - The file-reading shell-function helper EXACTLY as OLD:
    ```python
    helper = (
        '!f() { test "$1" = get && printf "password=%s\\n" '
        f'"$(cat {shlex.quote(str(token_path))})"; }}; f'
    )
    ```
  - `runner(["git", "-C", str(clone), "config", "--replace-all", f"{cred}.username",
"x-access-token"], check=True)`.
  - **Clear the inherited helper chain FIRST** with an empty `""` value via `--replace-all` so a
    global/system helper (osxkeychain / git-credential-manager) cannot shadow ours, then `--add` our
    file helper — port OLD's two-step exactly (worktree.py:86-95):
    `runner(["git", "-C", str(clone), "config", "--replace-all", f"{cred}.helper", ""], check=True)`
    THEN `runner(["git", "-C", str(clone), "config", "--add", f"{cred}.helper", helper], check=True)`.
    Document WHY `--replace-all ""` then `--add` (not plain `config`): a RE-RUN finds the key
    multi-valued `["", helper]`; plain `config` aborts with exit 5, whereas `--replace-all` collapses
    to a single `""` so the subsequent `--add` always yields exactly `["", <file helper>]` (PoC
    comment worktree.py:86-94).
  - The branch runs BEFORE the `fetch` (so the first fetch authenticates) and only when
    `token_path` is truthy.
- [ ] **Security assertion (the load-bearing test, port of
      `tests/test_worktree_cmd.py:92-121`):** with a `token_path` pointing at a file containing a
      SECRET sentinel value, assert the secret token VALUE appears in NO git argv across all
      `runner` calls (the helper config stores the FILE PATH + a `cat`-at-fetch shell function, never
      the literal token); assert `origin`'s URL is the tokenless `repo_url` (no `x-access-token:<tok>@`
      embedded); assert `credential.https://<host>.username = x-access-token` is set; assert the
      `.helper` is set with an empty-string reset FOLLOWED BY the file helper (two calls, order
      matters). With `token_path=None` → NO credential config calls at all (port
      `tests/test_worktree_cmd.py:124-130`).
- [ ] Verify: `make check` green. Residual-security grep: `rg --type py "x-access-token@|://[^/]*:.*@"
    src` → zero (no tokenised origin URL constructed anywhere).

```bash
git commit -m "feat(genesis): ensure_clone keeps origin tokenless via a fetch-time credential helper (token isolation — port of engine/worktree.py:76-95)"
```

---

## 14.3 — Per-repo flock `resource_lock` serialising clone mutations

**The gap.** PoC wrapped the fetch + worktree-add critical section in an exclusive per-repo advisory
flock — `with resource_lock(kanban_root, f"repo__{repo}"): ensure_worktree(...); discover_branch(...)`
(`runner.py:580-582,643-645`, `engine/locks.py:18-44`). NEW's `LaunchAction.execute` calls
`ensure_worktree` with NO lock, and `GitWorktreeWorkspace` does no internal flock (`rg --type py
"repo__" src tests` → zero). The `_lock` primitive WAS ported (`fs_store.py:333-359`) but is private
to the store and used only for `"cap"`; its per-repo clone-serialisation USE was dropped
(POC_PARITY_AUDIT.md §engine, [MEDIUM] flock advisory locks). Single-daemon makes a race unlikely but
the per-repo serialisation guard is gone — restore it (ensure_clone + ensure_worktree both mutate the
same `.git`).

**Layer**: `adapters/workspace/` (the lock primitive + its use around clone/worktree mutations).
Keep the lock INSIDE the adapter so `LaunchAction` stays subprocess-/flock-free and speaks only the
`Workspace` port.

**Files**: `src/kanbanmate/adapters/workspace/worktree.py` (add a `resource_lock` helper +
`resource_name`, wrap the `ensure_clone`/`ensure_worktree` git mutations),
`tests/adapters/test_workspace.py` (extend).

- [ ] Add a small advisory-lock context manager to the worktree adapter, ported from PoC
      `engine/locks.py:18-44` (it is intentionally NOT in `ports/` — flock is an adapter concern; the
      store's private `_lock` is store-internal, so the worktree adapter owns its own copy to avoid an
      adapter→adapter import). Sanitise the resource name (`re.sub(r"[^A-Za-z0-9._-]+", "_", resource)`)
      so it cannot escape `<kanban_root>/locks/`; `flock(LOCK_EX)` on `__enter__`, `LOCK_UN` + close on
      `__exit__` (even on exception). The adapter needs a `kanban_root` (where `locks/` lives) — thread
      it through `GitWorktreeWorkspace.__init__` (new optional `kanban_root: str | Path | None = None`,
      defaulting to the clone's parent or `~/.kanban` so existing constructions still work; document
      the default).
- [ ] Compute the per-repo resource name as `f"repo__{repo}"` where `repo` is the `owner/name` slug
      sanitised to `owner_name` by the lock's own sanitiser (PoC used `repo__IznoCorp_demo`). The
      adapter does not currently hold the repo slug — thread it through `__init__` (new optional
      `repo: str = ""`; when `""`, fall back to the clone dir basename so the lock is still per-clone).
      Wire it in `wiring.py::build_deps` (`GitWorktreeWorkspace(config.clone_dir, repo=config.repo,
    kanban_root=config.kanban_root)`) and in any `bin/` construction.
- [ ] Wrap the git-mutating bodies of BOTH `ensure_clone` and `ensure_worktree` in
      `with self._resource_lock(self._repo_resource()):` so two paths never `git init` / `fetch` /
      `worktree add` the same clone concurrently. `discover_branch` (read-only) and `delete_branch`
      (teardown, dispatcher-serial) need NOT be locked — match the PoC scope (it locked the fetch +
      worktree-add section). Keep the lock acquisition fail-soft only insofar as it must not be
      swallowed silently (a flock failure is a real error) — but the lock dir is created on demand
      (`mkdir(parents=True, exist_ok=True)`).
- [ ] Tests: `ensure_worktree` and `ensure_clone` each acquire `<kanban_root>/locks/repo__<owner>_<name>.lock`
      (assert the lock file is created and an exclusive flock is taken — inject a fake lock or assert
      the path exists / use a real `tmp_path` flock that a second acquire would block on, kept
      offline); the resource name sanitises `owner/name` → `repo__owner_name`; a `repo=""` construction
      falls back to a per-clone lock name (no crash). The lock is released after the block (a second
      `with` succeeds).
- [ ] Verify: `make check` green; layering guard sees the lock stays in `adapters/`.

```bash
git commit -m "feat(genesis): per-repo flock serialises clone mutations (resource_lock around ensure_clone/ensure_worktree — port of engine/locks.py)"
```

---

## 14.4 — `provision_worktree_skills` + `ensure_manual_merge_mode` on the perms adapter

**The gap.** Neither function is ported (`rg --type py "provision|_PROVISION|copytree|manual.merge|
IMPLEMENTATION\.md" src` → zero relevant). NEW's perms adapter (`adapters/perms.py`) implements only
`build_settings`/`materialise_settings`; `LaunchAction.execute` materialises settings then launches
but NEVER copies the project's skills/commands/agents into the worktree (so a `/implement:*` column
prompt would not resolve — the config repo is gitignored, absent from the clone checkout) and never
pins IMPLEMENTATION.md to manual merge (so an auto-triggered pr-review could squash-merge unattended)
(POC_PARITY_AUDIT.md §engine, [MEDIUM] provision_worktree_skills).

**Layer**: `adapters/` (filesystem COPY + IMPLEMENTATION.md edit — both pure-fs, no network).

**Files**: `src/kanbanmate/adapters/perms.py` (add both functions + the `_PROVISION_DIRS`/`_COPY_IGNORE`
constants), `tests/test_perms.py` (extend — the perms tests live at the top-level `tests/test_perms.py`,
NOT `tests/adapters/test_perms.py`).

- [ ] Add `_PROVISION_DIRS = ("skills", "commands", "agents")` and a `_COPY_IGNORE`
      (`shutil.ignore_patterns(...)` excluding `.git`, caches, `__pycache__`, `*.pyc` — port OLD's
      exclusion set, perms.py:38) at module top. `import shutil` at the top.
- [ ] Port `provision_worktree_skills(worktree: str | Path, config_dir: str | Path | None)
    -> list[Path]` byte-faithful from PoC `engine/perms.py:351-391`:
  - No-op (`return []`) when `config_dir` is empty/None.
  - For each name in `_PROVISION_DIRS`: skip when `src_root / name` is not a dir; REFRESH the dest
    (drop any prior copy/symlink/file first — `dest.unlink()` for symlink/file, `shutil.rmtree(dest)`
    for a dir) so the agent runs CURRENT skills; then `shutil.copytree(src, dest, ignore=_COPY_IGNORE)`.
    COPY, never symlink — document WHY (a write the agent makes inside its worktree must NOT propagate
    through a symlink to mutate the shared config repo; PoC perms.py:358-359).
  - Return the list of provisioned dest paths (for logging/tests).
  - Keep the SECURITY CAVEAT docstring (perms.py:364-368): this is NOT a sandbox — the agent runs as
    the same OS user and can reach the real config by absolute path; the copy only closes the in-scope
    symlink-write-through.
- [ ] Port `ensure_manual_merge_mode(worktree: str | Path) -> bool` byte-faithful from PoC
      `engine/perms.py:394-419`: no-op (`return False`) when `<worktree>/IMPLEMENTATION.md` is absent
      (never create a malformed file — the deny-list still blocks the real merge path); otherwise set
      or append the `**PR merge**: manual` line (replace an existing `**PR merge**:` line in place,
      else append), write back, `return True`. Document it as defense-in-depth ALONGSIDE the deny-list
      (DESIGN §10: merge is human-only).
- [ ] Tests (port PoC `tests/test_perms.py:282-392` semantics, NEW paths): `provision_worktree_skills`
      copies the config dirs into `<worktree>/.claude/`; a write to the worktree copy does NOT
      propagate back to the config dir (copy, not symlink); a refresh (second call) re-copies and skips
      a missing subdir; cruft (`.git`/`__pycache__`) is excluded; no-op (`[]`) when `config_dir` is
      empty/None; `settings.json` (not a provisioned dir) is preserved across a refresh.
      `ensure_manual_merge_mode`: sets the field when IMPLEMENTATION.md exists (replaces an existing
      `**PR merge**:` line in place; appends when absent); no-op `False` when IMPLEMENTATION.md is
      absent.
- [ ] Verify: `make check` green; layering guard sees both functions stay in `adapters/perms.py`.

```bash
git commit -m "feat(genesis): provision_worktree_skills (COPY skills/commands/agents) + ensure_manual_merge_mode pin (port of engine/perms.py:351-419)"
```

---

## 14.5 — Launch argv builder (`--session-id <uuid> --permission-mode <mode> --add-dir <worktree>` + session-end wrapper)

**The gap.** NEW's launch sends a single static `deps.agent_command` (default `"claude"`,
`actions.py:136` → `sessions.py:44-73`) into the tmux session — NO `--session-id <uuid>` (so the
persisted `session_id` is just the tmux NAME `ticket-<n>`, breaking `claude --resume <uuid>`
resumability — a HEADLINE feature, DESIGN §8.3 lines 18/74), NO `--permission-mode`/`--add-dir`, and
CRITICALLY NO `; kanban-session-end <issue>` wrapper. Without the wrapper, a cleanly-exited agent does
NOT free its cap slot / running state — the only release paths are TeardownAction (Cancel) and the
reaper after the 1800s heartbeat TTL (POC_PARITY_AUDIT.md §engine, [HIGH] Launch sequencing). This
sub-phase ports the argv SHAPE + the `;`-wrapper + a UUID session id.

> **Scope boundary (operator decision).** The trust-dialog poll
> (`poll_trust_dialog`/`build_sendkeys_sequence`, PoC launch.py:47-77,145-168) and the per-column
> filled prompt are SEPARATE runner-slice concerns out of this phase — NEW's `auto` permission mode
> (phase 9) means the agent is headless-safe and never hangs on the trust dialog, so the poll is not
> reachable here. This sub-phase restores ONLY: the `claude` argv shape, the UUID session id, the
> `; kanban-session-end <issue>` wrapper, and the bypass-ban guard. Document that the per-column prompt
> pipeline remains a known runner-slice gap (POC_PARITY_AUDIT.md §runner) NOT restored by this phase.

**Layer**: `core/` (PURE argv + command-line builder, unit-tested offline — the bypass-ban guard is a
pure decision) · `app/` (`LaunchAction` uses it) · `adapters/workspace/` (the session command is the
built command-line).

**Files**: `src/kanbanmate/core/launch_argv.py` (new — pure `build_claude_argv` + the session-end
command-line composition), `tests/core/test_launch_argv.py` (new),
`src/kanbanmate/app/actions.py` (`LaunchAction.execute` builds the argv + the session-end-wrapped
command, generates the UUID, persists it as `session_id`), `tests/app/test_actions.py` (extend).

- [ ] Add `core/launch_argv.py` (PURE — zero I/O; layering guard sees no I/O import):
  - `build_claude_argv(session_uuid: str, worktree: str, permission_profile: str, permission_mode:
str = "auto") -> list[str]` — port PoC `engine/launch.py:80-115` verbatim:
    `["claude", "--session-id", session_uuid, "--permission-mode", permission_mode, "--add-dir",
worktree]`. Raise `ValueError` if `"bypass" in permission_profile.lower()` OR
    `"bypass" in permission_mode.lower()` (bypass is banned, DESIGN §10) — port both guards.
  - `wrap_with_session_end(argv: list[str], issue: int, *, session_end_bin: str) -> str` — port PoC
    `_default_claude_runner`'s command composition (launch.py:137-140): join the argv with
    `shlex.quote` on EACH element (so a worktree path with a space does not split at `--add-dir
<path>`), then append `f" ; {shlex.quote(session_end_bin)} {issue}"`. Document that the `;` (NOT
    `&&`) ensures the wrapper ALWAYS fires whether `claude` exits cleanly or not, so the cap slot is
    always released and the ticket marked idle on exit (PoC comment launch.py:132-135). `import shlex`
    at module top. Keep it pure: the session-end bin PATH is INJECTED (resolved by the app layer), not
    discovered here.
- [ ] `LaunchAction.execute` (`actions.py`): replace the static `deps.agent_command` launch with the
      real argv:
  - Generate `session_uuid = str(uuid.uuid4())` (`import uuid` — the SINGLE SOURCE OF TRUTH for
    resumability, NO file scan; port launch.py:219).
  - `mode = pinned_mode(deps.profile)` (already imported); `argv = build_claude_argv(session_uuid,
str(worktree), deps.profile, mode)`; `command = wrap_with_session_end(argv, issue,
session_end_bin=deps.session_end_bin)`.
  - `deps.sessions.launch(session_name, str(worktree), command)` — the session command is now the
    real wrapped `claude` line, not `deps.agent_command`.
  - **Persist `session_id=session_uuid`** (the UUID, NOT the tmux name) so `claude --resume <uuid>`
    works. NB this changes the `session_id` semantics from "tmux name" to "uuid" — the tmux name stays
    `f"ticket-{issue}"` (the `Sessions` correlation key), and `session_uuid` is what the reaper passes
    to `claude --resume`. Document the split in the persisted `TicketState`.
  - Add `session_end_bin: str` to `Deps` (frozen) — the absolute path to the `kanban-session-end`
    shim. Default it to `"kanban-session-end"` (resolved on PATH) for tests; the real wiring passes
    the absolute installed path. Wire it in `wiring.py::build_deps`. **Drift note:** adding a field to
    the frozen `Deps` fans out to every test that constructs `Deps` — update the whitelisted
    `tests/app/test_actions.py` plus any `Deps(...)` construction in `tests/app/test_tick.py`,
    `tests/test_killswitch.py`, `tests/integration/`, `tests/local_real/` (default the new field so
    most need no change; assert mypy is genuinely rc=0 after clearing `.mypy_cache`).
  - Keep the existing `materialise_settings` + the 🟡 running-header sticky (8.1.c) intact; the
    provisioning calls land in 14.6.
- [ ] Tests (`tests/core/test_launch_argv.py`, pure, NO I/O): `build_claude_argv` emits exactly
      `claude --session-id <uuid> --permission-mode <mode> --add-dir <worktree>`; a `bypass` profile OR
      a `bypass` mode raises `ValueError`; `wrap_with_session_end` shlex-quotes each part AND appends
      `; <session-end-bin> <issue>` with `;` (not `&&`); a worktree path with a space round-trips
      un-split. `tests/app/test_actions.py`: `LaunchAction` launches a command that CONTAINS
      `--session-id`, `--add-dir <worktree>`, and `; ` + the session-end bin + the issue; the persisted
      `TicketState.session_id` is the UUID (matches the `--session-id` value), and the tmux session
      name is `ticket-<n>`.
- [ ] Verify: `make check` green. Residual grep: `rg --type py "agent_command" src` — confirm
      `LaunchAction` no longer launches the raw `agent_command` (it may remain on `Deps` as a
      vestigial knob, but the launch path uses the built command).

```bash
git commit -m "feat(genesis): launch builds claude argv (--session-id uuid / --permission-mode / --add-dir) wrapped with kanban-session-end (port of engine/launch.py)"
```

---

## 14.6 — Wire `ensure_clone` + provisioning into the launch + registry `config_dir`/`dev_repo_path` + `kanban init --dev-repo-path` + init's `ensure_clone`

**The gap (two halves).** (a) The launcher never provisions skills (14.4) into the worktree and the
clone is never created at init (14.1). (b) NEW's `ProjectEntry` (`cli/init.py:79-83`) dropped BOTH
`config_dir` (so the launcher cannot find the project's `.claude` to provision) AND `dev_repo_path`
(so the post-merge ff-only update has no persisted dev clone — `bin/kanban_update_main.py` now demands
the path positionally on every call); `kanban init` has no `--dev-repo-path` flag (POC_PARITY_AUDIT.md
§CLI, [HIGH] config_dir + [MEDIUM] dev_repo_path + [MEDIUM] init ensure_clone). This sub-phase threads
both registry fields, adds the init flag, runs `ensure_clone` at init, and wires
`provision_worktree_skills`/`ensure_manual_merge_mode` into `LaunchAction`.

**Layer**: `cli/` (registry shape + the init flag + the init `ensure_clone` step) · `app/`
(`LaunchAction` provisions) · `daemon/` (thread `config_dir` into the `WiringConfig`).

**Files**: `src/kanbanmate/cli/init.py` (`ProjectEntry` + `init` + `ensure_clone` step),
`src/kanbanmate/cli/app.py` (the `--dev-repo-path` flag), `src/kanbanmate/app/actions.py`
(`LaunchAction` provisions + `Deps.config_dir`), `src/kanbanmate/app/wiring.py` +
`src/kanbanmate/daemon/loop.py` (thread `config_dir` from the registry into `WiringConfig` → `Deps`),
`tests/cli/test_init.py` (extend), `tests/app/test_actions.py` (extend), `tests/app/test_wiring.py`
(extend).

- [ ] **Widen `ProjectEntry`** (`cli/init.py`) with the two dropped fields, each defaulted so existing
      `projects.json` still loads via `_load_registry`'s `ProjectEntry(...)` construction:
  - `config_dir: str = ""` — the project's `.claude` dir (skills/commands/agents source for the
    launcher's `provision_worktree_skills`). PoC computed it as the skill config root; in NEW it is the
    clone's `.claude` (or an operator-supplied path) — default to `str(Path(clone) / ".claude")` at
    init when not overridden, document the resolution.
  - `dev_repo_path: str = ""` — the operator's dev-clone path (post-merge ff-only update target,
    DESIGN §10). Update `_load_registry` to read both (`val.get("config_dir", "")`,
    `val.get("dev_repo_path", "")`) so an OLD-shaped entry without them still loads (assert it).
    `asdict` in `_upsert_project` already serialises the new fields.
- [ ] **`kanban init --dev-repo-path`** (`cli/app.py` + `cli/init.py::init`): add a
      `--dev-repo-path` typer Option (default `""`) and thread it into `init(..., dev_repo_path=...)`,
      persisted on the `ProjectEntry`. Port PoC `cli/app.py:62-65` (flag) + `registry.py:40` (field) +
      `runners.py:128-129,174` (threaded at init). Document: configure once at init; the daemon's
      post-merge update auto-resolves the dev clone from `projects.json` instead of demanding it on
      every `kanban-update-main` call.
- [ ] **`ensure_clone` at init** (`cli/init.py::init`): BEFORE writing
      `<clone>/.claude/kanban/columns.yml` (so the clone exists to write into), bootstrap the clone via
      the workspace adapter — `GitWorktreeWorkspace(clone_path, repo=repo,
    kanban_root=resolved_root).ensure_clone(repo_url, base=..., token_path=<root>/token)`. Resolve
      `repo_url` as the tokenless `https://github.com/<repo>.git`; `token_path` is the 600-mode
      `<root>/token` so the credential helper (14.2) is installed at init. Port the PoC
      `plan_init.py:74-76`/`executors.py:170-176` ordering: `ensure_clone` runs UNCONDITIONALLY (it was
      outside OLD's `do_org_setup` n8n block) and BEFORE the columns.yml write. Make it injectable
      (accept an optional `workspace_factory`/`ensure_clone` callable defaulting to the real adapter)
      so `tests/cli/test_init.py` drives a fake and never shells out to git. Keep the existing
      project/columns/labels/registry steps unchanged.
- [ ] **`LaunchAction` provisions** (`actions.py`): after `materialise_settings(...)` and BEFORE the
      session launch (14.5), call `provision_worktree_skills(worktree, deps.config_dir)` then
      `ensure_manual_merge_mode(worktree)` (import both from `adapters.perms`, 14.4). Add
      `config_dir: str = ""` to the frozen `Deps`; an empty `config_dir` skips provisioning (offline
      tests / no config). Document the order: settings → provision skills → pin merge mode → launch
      (mirrors PoC `start_session` launch.py:230-244).
- [ ] **Thread `config_dir` into the wiring** (`wiring.py` + `daemon/loop.py`): add
      `config_dir: str = ""` to `WiringConfig`; `build_deps` passes it to `Deps(config_dir=...)`; the
      daemon's `_wiring_from_registry` reads `entry.config_dir` off the single registered project and
      fills `WiringConfig(config_dir=entry.config_dir, ...)`. Mirror exactly how `clone_dir`/`repo` are
      threaded. (`dev_repo_path` does not need to reach `Deps`/the tick — it is consumed only by the
      post-merge `kanban-update-main` path, which reads it from the registry directly; document that.)
- [ ] Tests: `ProjectEntry` round-trips `config_dir` + `dev_repo_path` through
      `_upsert_project`/`_load_registry`; an OLD-shaped entry WITHOUT the new fields still loads
      (defaults applied — assert); `kanban init --dev-repo-path /p` persists `dev_repo_path="/p"`;
      `init` calls `ensure_clone` (injected fake records the call with the tokenless repo_url + the
      `<root>/token` token_path) BEFORE writing columns.yml; `init` defaults `config_dir` to the
      clone's `.claude`. `LaunchAction` provisions the config dirs into the worktree (fake/real
      `config_dir`) and pins manual merge; an empty `config_dir` skips provisioning. `build_deps`
      threads `config_dir` onto `Deps`; `_wiring_from_registry` reads `entry.config_dir`.
- [ ] Verify: `make check` green. Residual grep: `rg --type py "config_dir|dev_repo_path" src` — the
      fields now thread through registry → wiring → Deps (config_dir) and registry → update-main
      (dev_repo_path), not just the vestigial `bin/kanban_update_main.py` positional arg.

```bash
git commit -m "feat(genesis): restore registry config_dir/dev_repo_path + init ensure_clone + launch-time skill provisioning (port of cli/registry+runners+launch)"
```

---

### Phase 14 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`; clear `.mypy_cache` first — its incremental
   cache has masked real errors in this repo).
2. `make test` — all pass (check the summary line; any ERROR = collection crash → fix imports first).
3. `make check` — clean (lint + test + module-size guards; the new `core/launch_argv.py` and the
   widened `worktree.py`/`perms.py`/`init.py` stay under the ~800 LOC soft cap).
4. Residual / security grep (all `--type py`):
   - `rg --type py "ensure_clone" src` → matches in `ports/workspace.py`, `adapters/workspace/worktree.py`,
     `cli/init.py` (the bootstrap is wired, not dead).
   - `rg --type py "provision_worktree_skills|ensure_manual_merge_mode" src` → matches in
     `adapters/perms.py` AND `app/actions.py` (provisioning is CALLED at launch, not orphaned).
   - `rg --type py "x-access-token@|://[^/]*:[^/]*@" src` → **zero** (no tokenised origin URL — the
     credential helper keeps the token out of `.git/config`).
   - `rg --type py "kanban-session-end|kanban_session_end" src` → the launch command appends the
     session-end wrapper (`; ... kanban-session-end`).
   - `rg --type py "config_dir|dev_repo_path" src` → both registry fields thread through (not the
     bare vestigial positional arg only).
5. Parity check — exercised in tests: a fresh `ensure_clone` (no `.git`) `git init`s in place + adds
   origin + fetches; the credential helper keeps the secret token out of every git argv; the per-repo
   `repo__<owner>_<name>.lock` serialises clone mutations; `provision_worktree_skills` COPIES (not
   symlinks) skills/commands/agents into the worktree; the launch command is
   `claude --session-id <uuid> --permission-mode <mode> --add-dir <worktree> ; kanban-session-end <n>`
   and the persisted `session_id` is the UUID; `kanban init --dev-repo-path` persists the field and
   `init` runs `ensure_clone`.
6. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 14 gate — clone bootstrap + worktree provisioning + launch argv + registry"
```
