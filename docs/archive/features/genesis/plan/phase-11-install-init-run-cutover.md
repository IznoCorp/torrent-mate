# Phase 11 — Install · init · run cutover (NEW activation)

> Operational / runbook phase: exact commands, not TDD steps. Design refs: DESIGN §4 (three-tier
> install), §4.1 (host tier + PM2), §4.3 (per-repo tier), §5 (daemon), §8.3 (in-daemon reaper),
> §11 (cutover & decommission). Operator decisions baked in: interpreter = pyenv 3.12 editable
> global; PM2 launches an ABSOLUTE pyenv-3.12 `kanban` via the first-class
> `kanban install --kanban-command <abs>` flag (§11.A — the operator supplies the path, nothing is
> hardcoded); NEW board is FRESH (new Project v2 + re-seed, NOT the OLD board); n8n stopped ENTIRELY;
> the PAT token is the ONE carry-over (board is fresh).

**Goal**: activate KanbanMate on the host — install the engine + Claude plugin, wire the PM2 daemon
to the pyenv-3.12 `kanban`, init a FRESH Project v2 board, paste the PAT, re-seed the roadmap, start
the polling daemon under PM2, and verify end-to-end (doctor, a real card-move launching an agent
that does NOT hang now that `auto` is the default, and the in-daemon reaper reaping correctly).

**Ordering (MANDATORY)**: the §11.A CLI-flag code commit is a normal `feat(genesis)` TDD change that
lands on phase 10's green 3.12 tree BEFORE host activation (see phase-10's closing forward-ref); the
host activation runs AFTER the _OLD-disable runbook_ below. The OLD PoC dispatch path
(n8n + launchd reaper + org webhook) MUST be fully stopped BEFORE the NEW daemon starts, or the two
double-dispatch on a shared board / shared `~/.kanban`. Sequence:
**phase 10 (3.12 green) → §11.A `--kanban-command` flag (code, `make check`) → §11.0 OLD-disable
runbook → §11.1+ NEW activation → decommission (IMPLEMENTATION.md §11, separate repo)**.

---

## Gate

Phase 10 complete; `make check` green under pyenv 3.12; PR #1 ready (CI green). The engine is the
version on `feat/genesis` (run from the working tree, editable). The host has pyenv 3.12.4, PM2,
tmux, git, and the `claude` CLI.

---

## §11.A — `kanban install --kanban-command <abs>` CLI flag (CODE sub-phase — TDD)

> **The one code commit in this phase** (operator decision). Everything else here is operational
> runbook (host ops, no engine change). This sub-phase is a normal `feat(genesis)` TDD change with a
> `make check` gate, run as part of phase 10's green tree BEFORE the §11.1 activation uses it.
>
> **The gap.** `host_install(...)` already accepts a `kanban_command` keyword (it threads into
> `_write_ecosystem` → `_ecosystem_body` → the PM2 `script:` line), but the `kanban install` Typer
> command (`cli/app.py::install`) exposes only `--root` / `--pm2` / `--repo` — there is NO way to set
> `kanban_command` from the CLI. So today the only way to pin PM2 to the ABSOLUTE pyenv-3.12 `kanban`
> is to side-call `_write_ecosystem(...)` by hand (the old §11.2 host override). Promote it to a
> first-class flag so the install command itself materialises the absolute-path ecosystem — no raw
> private-function call on the host, no hardcoded path in code (the abs path is an operator argument).

**Layer**: `cli/` (Typer surface only — the installer plumbing already exists). **Files**:
`src/kanbanmate/cli/app.py` (add the `--kanban-command` option to `install`, pass it through),
`tests/cli/test_install.py` (the install plumbing is tested here at the `host_install` level — extend;
there is no `tests/cli/test_app.py`, and the suite has no `CliRunner` pattern).

- [ ] Add a `--kanban-command` Typer option to the `install` command, defaulting to `"kanban"`
      (PATH-relative, unchanged behaviour when omitted), and pass it into the existing
      `host_install(..., kanban_command=kanban_command)` call:

      ```python
      kanban_command: str = typer.Option(
          "kanban",
          "--kanban-command",
          help="Console-script command PM2 runs (e.g. an ABSOLUTE pyenv path so PM2's boot "
               "environment need not have the pyenv shims on PATH). Default: the bare 'kanban'.",
      ),
      ```
      Keep it GENERIC: the help text describes the *use case* (absolute path for PM2) but the code
      hardcodes NO host path — the absolute path is whatever the operator passes (e.g.
      `$(pyenv which kanban)`). Update the command docstring's `Args:` for the new option.

- [ ] Tests (TDD — write first): invoking `install --kanban-command /abs/pyenv/3.12.4/bin/kanban
  --no-pm2` writes an `ecosystem.config.js` whose `script:` line is that absolute path (assert
      the generated file content); invoking `install` with NO `--kanban-command` keeps `script:
  "kanban"` (default preserved); the option is forwarded to `host_install` (assert via a spy /
      the generated file). **Audit fix:** there is NO existing `CliRunner` pattern in the suite — every CLI test drives the
      underlying function directly with injected deps (`tests/cli/test_install.py` calls
      `host_install(...)` with `tmp_path` + injected `geteuid`/`runner`). PREFER testing at the
      `host_install` level: `host_install(tmp_path, run_pm2=False,
    kanban_command="/abs/pyenv/3.12.4/bin/kanban")` writes the absolute `script:` line; the default
      `kanban_command="kanban"` keeps `script: "kanban"`. If a true `CliRunner` end-to-end test is
      wanted it MUST also `monkeypatch` `host_installer.claude_install` (and inject the PM2 runner),
      because `app.py::install` calls `claude_install(repo)` UNCONDITIONALLY (`--no-pm2` gates only
      PM2, not the Claude tier) — a naive invocation would shell out to the real `claude` binary. **CWD guard (M3):** `_write_ecosystem` writes
      `ecosystem.config.js` relative to the process CWD, so the test MUST `monkeypatch.chdir(tmp_path)`
      (or use a tmp-cwd fixture) BEFORE invoking the command — otherwise the generated file lands in
      the real repo working directory. Then assert the `script:` line by reading
      `tmp_path / "ecosystem.config.js"`.
- [ ] Verify: `make check` green (ruff + `mypy src tests` + test + size guard).

```bash
git commit -m "feat(genesis): kanban install --kanban-command flag (PM2 script path, absolute pyenv supported)"
```

---

## §11.0 — OLD-disable runbook (run BETWEEN phase 10 and §11.1 — BLOCKING)

> **Why first, why mandatory.** OLD and NEW would share the same GitHub board surface and the same
> `~/.kanban` root. If OLD's ingress (n8n webhook → dispatch) or OLD's launchd reaper is still live
> when NEW's polling daemon starts, BOTH react to the same card moves → double agent launches,
> double comments, racing teardowns. Stop OLD COMPLETELY first. These are HOST operations (no
> KanbanMate repo change); they are NOT the `kanban uninstall` path (that uninstalls the NEW
> daemon). NEW's installer DOES already remove the OLD reaper plist in `host_uninstall`, but here we
> disable OLD by hand, in order, BEFORE NEW exists on the host.

Run in THIS order:

1. **Stop + remove the OLD launchd reaper agent** (label `xyz.iznogoudatall.kanban-reaper`,
   installed by the PoC under `~/Library/LaunchAgents/`):

   ```bash
   launchctl bootout gui/$(id -u)/xyz.iznogoudatall.kanban-reaper 2>/dev/null || true
   # (legacy form on older macOS, harmless if the bootout above already succeeded)
   launchctl unload ~/Library/LaunchAgents/xyz.iznogoudatall.kanban-reaper.plist 2>/dev/null || true
   rm -f ~/Library/LaunchAgents/xyz.iznogoudatall.kanban-reaper.plist
   launchctl list | grep -i kanban-reaper || echo "OLD reaper agent gone"
   ```

2. **Stop + delete the OLD n8n PM2 app ENTIRELY** (the PoC's ingress; app name `n8n` in
   `~/dev/ecosystem.config.js`, host `n8n.iznogoudatall.xyz`). n8n is stopped completely (operator
   decision — KanbanMate has no webhook ingress; polling replaces it):

   ```bash
   pm2 stop n8n   || true
   pm2 delete n8n || true
   pm2 save                       # persist the now-n8n-less process list so a reboot does not revive it
   pm2 list | grep -i n8n || echo "OLD n8n app gone"
   ```

   Note: this leaves `~/dev/ecosystem.config.js` (the n8n app definition) on disk but unmanaged.
   NEW writes its own `ecosystem.config.js` at the KanbanMate repo root (§11.2) — a DIFFERENT file —
   so there is no collision. Optionally prune the n8n entry from `~/dev/ecosystem.config.js` later;
   not required for the cutover.

3. **Delete the OLD GitHub org webhook** (the one pointing at the n8n endpoint
   `https://n8n.iznogoudatall.xyz/webhook/kanban`). With no n8n running, the hook delivers to a dead
   endpoint; with NEW polling, no hook is needed at all (DESIGN §3.1, token scope drops
   `admin:org_hook`). Delete it via the GitHub UI (Org → Settings → Webhooks → the
   `n8n.iznogoudatall.xyz/webhook/kanban` hook → Delete) OR the API:

   ```bash
   # list org hooks to find the id (requires a token with admin:org_hook — the OLD token had it)
   curl --connect-timeout 10 --max-time 30 -sS \
     -H "Authorization: Bearer $OLD_ADMIN_TOKEN" \
     https://api.github.com/orgs/IznoCorp/hooks
   # delete the one whose config.url is the n8n kanban endpoint
   curl --connect-timeout 10 --max-time 30 -sS -X DELETE \
     -H "Authorization: Bearer $OLD_ADMIN_TOKEN" \
     https://api.github.com/orgs/IznoCorp/hooks/<HOOK_ID>
   ```

4. **Archive then clear the OLD `~/.kanban`** (it is OLD-format and disposable — DESIGN §11: existing
   PoC state is disposable, `kanban install` starts fresh). The current root holds OLD artifacts
   (`clones/`, `advances/`, `botmoves/`, `ROLLBACK-*.json`, OLD `state/`) keyed to the OLD board.
   Since the NEW board is FRESH (new Project v2 + re-seed), NONE of this state is reused — even the
   token is re-pasted into a fresh skeleton (the PAT VALUE may be reused; see §11.4). Archive for
   safety, then clear:

   ```bash
   ts=$(date +%Y%m%d-%H%M%S)
   mv ~/.kanban ~/.kanban.old-$ts          # archive the whole OLD root
   # NEW's host_install (§11.1) recreates ~/.kanban as a fresh 0700 skeleton with a token placeholder.
   ls -la ~/.kanban.old-$ts | head         # confirm the archive exists; the live root is now absent
   ```

5. **Confirm OLD is fully down** before proceeding to §11.1:
   ```bash
   launchctl list | grep -i kanban-reaper || echo "reaper: down"
   pm2 list | grep -i n8n || echo "n8n: down"
   test ! -e ~/.kanban && echo "old ~/.kanban: cleared"
   ```
   Only when all three confirm down → proceed to NEW activation.

> **The one carry-over**: the PAT VALUE may be reused (a `project + repo`-scoped token works on the
> fresh board too). EVERYTHING ELSE is fresh — new Project v2, fresh `~/.kanban`, re-seeded roadmap.
> The board is NOT reused from OLD. If the OLD PAT carried `admin:org_hook` (needed to delete the
> hook in step 3), prefer minting a fresh `project + repo`-only PAT for NEW (DESIGN §10 — no
> over-broad scope).

---

## §11.1 — Install the engine + Claude plugin (host tier + Claude tier)

```bash
pyenv local 3.12.4 && python --version                  # → 3.12.4 (the NEW interpreter)
pip install -e ".[dev]"                                  # editable under pyenv 3.12 (phase 10)
KANBAN_ABS=$(pyenv which kanban) && echo "$KANBAN_ABS"   # ABSOLUTE pyenv-3.12 kanban path (PM2 needs it)
kanban install --kanban-command "$KANBAN_ABS"            # host tier (~/.kanban 0700 + token skeleton +
                                                         # ecosystem.config.js with script: <abs pyenv kanban>
                                                         # + pm2 start/save/startup)
                                                         # + Claude tier (marketplace add + plugin install)
```

- [ ] `kanban install` refuses to run as root (DESIGN §10) — run as the operator user.
- [ ] It creates a FRESH `~/.kanban` (0700) with a `token` placeholder (NEVER a real secret), writes
      `ecosystem.config.js`, and registers the `/kanban` plugin (`claude plugin list | grep kanban`).
- [ ] `--kanban-command "$KANBAN_ABS"` (the flag added in §11.A) bakes the ABSOLUTE pyenv-3.12
      `kanban` straight into the generated `ecosystem.config.js` `script:` line — so PM2 runs the
      right interpreter even though its boot environment may lack the pyenv shims on PATH. The path is
      operator-supplied (`$(pyenv which kanban)`); nothing is hardcoded in the engine. This REPLACES
      the old hand-rolled `_write_ecosystem(...)` host override (see §11.2).

---

## §11.2 — Confirm PM2 points at the absolute pyenv-3.12 `kanban`

> Because §11.1 ran `kanban install --kanban-command "$KANBAN_ABS"` (the §11.A flag), the
> `ecosystem.config.js` is ALREADY materialised with the absolute pyenv-3.12 path in its `script:`
> line — there is NO separate re-write step and NO raw `_write_ecosystem(...)` host call. PM2's boot
> environment need not have the pyenv shims on PATH because the script is the full path. This step
> only VERIFIES the result:

```bash
grep -n 'script:' ecosystem.config.js   # confirm script: is the absolute pyenv-3.12 path (set by the flag)
```

- [ ] Confirm `ecosystem.config.js` `script:` is the absolute `~/.pyenv/versions/3.12.4/bin/kanban`
      (not the bare `kanban`) — produced by `--kanban-command` in §11.1, not by a hand-edit. The app
      `name` stays `kanban` (DESIGN §5 per-name singleton) — note this is a DIFFERENT app from the
      now-deleted OLD `n8n` PM2 app, no collision.
- [ ] If the absolute path was NOT passed in §11.1 (e.g. a bare `kanban install` was run first), the
      fix is to RE-RUN `kanban install --kanban-command "$(pyenv which kanban)"` (idempotent) — NOT to
      side-call `_write_ecosystem` by hand. The flag is the single supported way to set the PM2 script.

---

## §11.3 — Init a FRESH Project v2 board + paste the PAT

```bash
# 1. Paste the PAT (project + repo scopes only — NOT admin:org_hook) into the fresh skeleton:
$EDITOR ~/.kanban/token        # paste the token on its own line; keep the file 600
chmod 600 ~/.kanban/token

# 2. Init the per-repo tier against a FRESH org Project v2 (NOT the OLD board). `kanban init`
#    find-or-creates the org Project v2 by title; since OLD's board is left as-is and we want a
#    fresh one, pass a NEW title so a clean board is materialised:
cd /path/to/the/target/clone           # the repo whose roadmap KanbanMate will drive
kanban init --repo IznoCorp/<repo>     # creates fresh Project v2, Status columns, wave:*/prio:* labels,
                                       # writes <clone>/.claude/kanban/columns.yml, registers projects.json
```

- [ ] `kanban init` writes the fresh project node id + Status field + option map into
      `~/.kanban/projects.json` (keyed by the project node id). Confirm exactly one entry (v1 = one
      repo per clone): `python -c "import json,pathlib;print(json.loads(pathlib.Path('~/.kanban/projects.json').expanduser().read_text()))"`.
- [ ] The board is NEW — no OLD card state is carried (the OLD `~/.kanban` was archived in §11.0).

---

## §11.4 — Re-seed the roadmap onto the fresh board

```bash
cd /path/to/the/target/clone
kanban seed ROADMAP.md         # creates issues (Backlog) + rewrites "Depends on #N" + applies labels
```

- [ ] Confirm the seeded issues land in **Backlog** (inert; no agent fires on seed) and that
      `Depends on #N` references were rewritten to the new issue numbers.

---

## §11.5 — Start the polling daemon under PM2

```bash
pm2 start ecosystem.config.js --only kanban     # start the NEW daemon (kanban run, pyenv-3.12)
pm2 save                                         # persist so a reboot restores it
pm2 list | grep kanban                           # status online
pm2 logs kanban --lines 50                       # confirm the loop is ticking (probe → snapshot → diff)
```

- [ ] The daemon holds `flock ~/.kanban/daemon.lock` (single instance), writes
      `~/.kanban/daemon.heartbeat` each tick, and logs JSONL to `~/.kanban/log/daemon.jsonl`.

---

## §11.6 — Verify the cutover end-to-end

- [ ] **doctor** — all three tiers green under the NEW interpreter:
      `bash
  kanban doctor
  `
      Expect: engine importable (3.12), PM2 daemon up + heartbeat fresh, plugin present, token
      reachable + scopes `project + repo` (NOT `admin:org_hook` — the deleted hook means the
      narrower scope suffices), non-root, tmux socket owned by the user.
- [ ] **Real e2e card-move launches an agent** — move a Backlog card into the first AGENT column
      (e.g. "In Progress") on the FRESH board and watch the daemon dispatch:
      `bash
  pm2 logs kanban --lines 80      # expect: diff → LAUNCH → tmux session ticket-<n> + worktree
  tmux ls | grep ticket-          # the agent session exists
  `
- [ ] **Confirm NO acceptEdits→hang now that `auto` is the default** (the phase-9 payoff, validated
      at RUNTIME here): the launched agent's `<worktree>/.claude/settings.json` pins
      `"defaultMode": "auto"`, and the agent makes progress UNATTENDED (does not park on a permission
      prompt). Check:
      `bash
  cat <worktree>/.claude/settings.json | grep -A1 defaultMode   # → "auto" (NOT "acceptEdits")
  tmux capture-pane -pt ticket-<n> | tail -20                   # agent acting, not waiting on a prompt
  `
      Sticky comment on the issue shows the 🟡 running header (phase 8.1.c) and progresses, never
      stalls on an edit/permission prompt.
- [ ] **Confirm the reaper (folded into the daemon) reaps correctly** — the in-daemon reap step runs
      every tick (DESIGN §8.3); there is NO separate launchd reaper anymore (deleted in §11.0). To
      validate: let an agent finish (heartbeat refreshed by the PostToolUse hook → never reaped while
      working) OR simulate staleness on a test ticket and confirm the daemon moves it to **Blocked**,
      kills the dead session, releases the slot, and flips its sticky to ⛔ (phase 8.1.c):
      `bash
      pm2 logs kanban | grep -i reap # the reap step is logged each tick (reaped count)
  # a genuinely stale (>30 min no-tool) agent → daemon parks it in Blocked with a ⛔ sticky
  `
- [ ] **Deny still holds under `auto`** (phase-9 payoff): the agent CANNOT `gh pr merge` /
      `git push --force` / `git branch -D` — the worktree deny-list blocks them regardless of the
      `auto` mode (merge stays human-only).

---

## §11.7 — Decommission OLD (reference, not duplicated here)

The final destructive decommission of the OLD PoC skill — `git rm -r skills/kanban/` in
`PersonnalScaper/.claude` (branch `personal-scraper`), cleaning its `CLAUDE.md` refs, commit
`chore: decommission kanban skill (extracted to KanbanMate)` — is a separate-repo operation already
tracked in **IMPLEMENTATION.md §11 / the Notes "Deferred post-merge cutover" block** (and DESIGN
§11). It is NOT part of KanbanMate's git history and is performed only AFTER this PR merges and the
NEW daemon is verified live (§11.6). Do not duplicate it here — follow the IMPLEMENTATION.md note.

> **§11.0 vs §11.7**: §11.0 (this phase) _disables_ OLD operationally on the host (stop n8n, remove
> the launchd reaper, delete the org webhook, archive `~/.kanban`) so NEW can run without
> double-dispatch. §11.7 (IMPLEMENTATION.md §11) _deletes_ the OLD source code from the external
> portable-config repo. Disable first (operational, reversible), delete later (source, post-merge).

---

### Phase 11 Gate (mostly operational — §11.A is the one `make check` code commit)

0. §11.A done: `kanban install --kanban-command <path>` exists, is covered by tests, `make check`
   green — the install command bakes the supplied path into `ecosystem.config.js` `script:` (default
   `kanban` preserved when the flag is omitted).
1. §11.0 confirmed: OLD reaper down, OLD n8n PM2 app deleted, org webhook deleted, OLD `~/.kanban`
   archived + cleared.
2. `kanban doctor` — all three tiers green under pyenv 3.12.
3. A real Backlog→agent-column move launches a tmux agent in a worktree whose settings pin
   `defaultMode: auto`; the agent progresses unattended (no acceptEdits→hang).
4. The in-daemon reaper logs each tick and parks a stale agent in Blocked with a ⛔ sticky; no
   separate launchd reaper exists.
5. Deny holds under `auto` (merge / force-push / branch-delete blocked for the agent).
6. PM2 `kanban` app online (its `script:` the absolute pyenv-3.12 path, set via §11.A's flag),
   `pm2 save` persisted; daemon heartbeat fresh.

> The ONLY `git commit` in this phase is §11.A (`feat(genesis): kanban install --kanban-command flag`,
> `make check` green). The activation itself (§11.0–§11.7) is host ops with no commit; its committed
> artifact is the runbook (this file). PM2 is pinned to the absolute pyenv-3.12 `kanban` via the
> §11.A flag passed in §11.1 — NOT a hand-rolled `_write_ecosystem(...)` call.
