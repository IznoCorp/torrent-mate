# Phase 2 — Installer + Plugin Marketplace

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Architecture: see DESIGN §4 (install model), §5 (PM2 wiring).

**Goal**: Implement the 3-tier installer (`install/uninstall/doctor`) + PM2 daemon wiring +
Claude plugin marketplace + `validate` gate. All `kanban` CLI commands functional.

---

## Gate

Phase 1 complete: `make check` green, `python -c "import kanbanmate"` exits 0,
daemon loop + CLI stub committed.

---

### 2.1 — `~/.kanban/` skeleton + host tier (`kanban install` host)

**Files**: `src/kanbanmate/cli/install.py`, `src/kanbanmate/cli/app.py` (extend stubs),
`tests/cli/__init__.py`, `tests/cli/test_install.py`.

- [ ] `install.py`: host-tier idempotent setup — create `~/.kanban/` with mode 0o700,
      write `~/.kanban/token` skeleton (0o600), seed kill-switch primitives (`PAUSE` absent by default).
      No secret, no webhook, no n8n (DESIGN §4.1).
- [ ] PM2 wiring: write `ecosystem.config.js` at repo root; run
      `pm2 start kanban -- run`, `pm2 save`, `pm2 startup` (suppress output on re-run).
      `kanban uninstall`: `pm2 delete kanban` + host teardown. Both idempotent.
- [ ] Wire `kanban install` / `kanban uninstall` commands in `cli/app.py`.
- [ ] Tests: `tmp_path` for `~/.kanban/`; assert dir mode 700; token file mode 600;
      mock `subprocess.run` for PM2 calls; assert idempotent on second call.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): host-tier installer (kanban install/uninstall, PM2 wiring)"
```

---

### 2.2 — Claude tier (`kanban install` claude)

**Files**: `src/kanbanmate/cli/install.py` (extend), `tests/cli/test_install_claude.py`.

- [ ] Drive `claude` CLI non-interactively per DESIGN §4.2:
      `claude plugin marketplace add <repo-path> --scope user` then
      `claude plugin install kanban@kanbanmate --scope user [--config engine_path=…]`.
      Detect if already installed via `claude plugin list` output; skip if present (idempotent).
- [ ] `kanban uninstall`: run `claude plugin uninstall kanban` + `claude plugin marketplace remove`.
- [ ] Tests: mock `subprocess.run`; assert correct CLI args; assert skip on already-installed.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): claude-tier installer (plugin marketplace add + install, non-interactive)"
```

---

### 2.3 — Per-repo tier (`kanban init` + `kanban seed`)

**Files**: `src/kanbanmate/cli/init.py`, `src/kanbanmate/cli/seed.py`,
`tests/cli/test_init.py`, `tests/cli/test_seed.py`.
**Plus (plan-drift correction, see below)**: `src/kanbanmate/ports/board.py` (`Seeder` Protocol),
`src/kanbanmate/adapters/github/{client,_queries,_parsers}.py` (Seeder methods),
`tests/adapters/github/test_client.py` (Seeder tests).

> **Plan-drift correction (Seeder addition).** The original plan said "create project via adapter"
> but the github adapter (sub-phase 1.10) only implemented `BoardReader`/`BoardWriter`; the `Seeder`
> capability (DESIGN §3.3: `Seeder{create_issue, add_to_project, ensure_labels}` + project/label/
> column creation) was explicitly DEFERRED from sub-phase 1.7. This sub-phase therefore ALSO adds:
> a `Seeder` Protocol in `ports/board.py` (`ensure_project`, `ensure_columns`, `ensure_labels`,
> `create_issue`, `update_issue_body`, `add_to_project`) and its `GithubClient` implementation
> (new GraphQL builders/parsers: `org_id`, `find_org_project`, `create_project`,
> `update_status_field_options` + orphan-safe count, `repo_id`, `create_label`, `create_issue`,
> `update_issue_body`, `add_item_to_project`). All new urllib requests reuse the existing
> `UrllibTransport` (mandatory connect+read timeouts). The CLI speaks the `Seeder` Protocol
> (injectable for tests; concrete `GithubClient` in production).

- [ ] `kanban init --repo org/repo`: create fresh GitHub Projects v2 (GraphQL mutation via adapter),
      reuse auto Status field, ensure columns per `columns.yml`, create `wave:*`/`prio:*` labels,
      write `<clone>/.claude/kanban/columns.yml`, register in `~/.kanban/projects.json`
      (keyed by project node id). No webhook/n8n step (DESIGN §4.3).
- [ ] `kanban seed <ROADMAP.md>`: parse roadmap, create issues, rewrite `Depends on #N` refs,
      add to project in Backlog. Port from PoC `cli/plan_seed.py` + `cli/roadmap.py`.
- [ ] Add the `Seeder` Protocol + `GithubClient` Seeder methods (plan-drift correction above).
- [ ] Wire both commands in `cli/app.py`.
- [ ] Tests: fake Seeder (no network); assert `projects.json` written; assert `columns.yml` written;
      assert seed creates issues in dependency order + rewrites Depends-on refs; adapter Seeder tests.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): per-repo tier (kanban init + kanban seed)"
```

---

### 2.4 — `kanban doctor`

**Files**: `src/kanbanmate/cli/doctor.py`, `tests/cli/test_doctor.py`.

- [ ] Validate all three tiers (DESIGN §4): engine importable; PM2 daemon up + daemon heartbeat
      fresh; plugin present (`claude plugin list`); GitHub token reachable + scopes `project`+`repo`
      (not `admin:org_hook`); branch protection on; non-root; tmux socket owned by user.
- [ ] Output: structured pass/fail table per check; exit 1 if any check fails.
- [ ] Wire `kanban doctor` in `cli/app.py`.
- [ ] Tests: mock each check (subprocess, token, PM2); assert exit 0 all-pass; exit 1 on failure.
- [ ] Verify: `make test` pass. `make lint` zero errors.

```bash
git commit -m "feat(genesis): kanban doctor (3-tier health check)"
```

---

### 2.5 — Remaining CLI commands

**Files**: `src/kanbanmate/cli/{status,sessions,cancel,logs,reset,poll}.py`,
`tests/cli/test_{status,cancel,logs,poll}.py`.

- [ ] Port from PoC: `kanban status` (board summary), `kanban sessions` (list tmux sessions),
      `kanban cancel <issue>` (teardown — shared with TeardownAction), `kanban logs [issue]`
      (structured JSONL reader, DESIGN §5), `kanban reset` (archive old `~/.kanban/`),
      `kanban poll --once` (single tick, no loop — useful for debugging).
- [ ] Wire all in `cli/app.py`.
- [ ] Tests: mock adapters; assert correct output format for `status`; assert `cancel` calls
      TeardownAction; `poll --once` runs tick and exits.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): remaining CLI commands (status, sessions, cancel, logs, reset, poll)"
```

---

### 2.6 — Plugin marketplace + `/kanban` skill

**Files**: `.claude-plugin/marketplace.json`, `plugin/skills/kanban/SKILL.md`,
`tests/test_plugin_manifest.py`.

- [ ] `.claude-plugin/marketplace.json`: marketplace entry for `kanbanmate` — name, version,
      install command, skill list. Repo root is the plugin source (DESIGN §2).
- [ ] `plugin/skills/kanban/SKILL.md`: thin wrapper — SKILL frontmatter + body that shells out to
      `kanban <args>`. All logic stays in the engine; the skill only invokes `kanban …`.
- [ ] `test_plugin_manifest.py`: load JSON, assert required fields; validate SKILL.md has correct
      frontmatter keys.
- [ ] Verify: `claude plugin validate . --strict` (marketplace) AND
      `claude plugin validate ./plugin --strict` (plugin) both exit 0 (run manually; add to CI).
      `make test` pass.

```bash
git commit -m "feat(genesis): plugin marketplace + /kanban skill (thin CLI wrapper)"
```

---

### Phase 2 Gate

1. `make lint` — zero errors
2. `make test` — all pass
3. `make check` — clean
4. `python -c "import kanbanmate"` — exits 0
5. `claude plugin validate . --strict` (marketplace) AND
   `claude plugin validate ./plugin --strict` (plugin) — both exit 0

```bash
git commit --allow-empty -m "chore(genesis): phase 2 gate — installer + plugin marketplace"
```

---

### 2.7 — Gate hardening

> Added by the orchestrator to close two installability gaps and one wrong gate
> command the Phase 2 gate surfaced. Phase 2's deliverable is an **installable**
> engine + plugin (DESIGN §2), so these are in-scope corrections, not new scope.

**Files**: `pyproject.toml`, `src/kanbanmate/assets/columns.yml.tmpl` (moved from
`assets/`), `src/kanbanmate/cli/init.py`, `tests/core/test_columns.py`,
`plugin/.claude-plugin/plugin.json`, `tests/test_plugin_manifest.py`, and the
three plan files (this one, phase-04, phase-05).

- [x] **Assets as package data.** `git mv assets/columns.yml.tmpl
    src/kanbanmate/assets/columns.yml.tmpl`; add it to
      `[tool.setuptools.package-data]`
      (`kanbanmate = ["py.typed", "assets/*.tmpl", "assets/*.yml"]`) so a
      wheel / `pip install` ships it. Rewrite `cli/init.py`
      `_engine_assets_template()` to load the template via
      `importlib.resources.files("kanbanmate.assets") / "columns.yml.tmpl"`
      (returns text), NOT a computed repo-root path; the `template_path`
      override stays for tests. Point `tests/core/test_columns.py` at the
      packaged resource via `importlib.resources` (wheel-installability guard:
      proves the bundled template is loadable as package data and parses to the
      11 columns).
- [x] **Plugin manifest.** Add `plugin/.claude-plugin/plugin.json` (the PLUGIN
      manifest, distinct from the marketplace manifest): `name: "kanban"`,
      `version` (matches VERSION/0.1.0), `description`, `author`. Extend
      `tests/test_plugin_manifest.py` to assert its required fields and that its
      version matches the VERSION file + the marketplace entry.
- [x] **Validate-command correction.** The plan wrote
      `claude plugin validate .claude-plugin --strict`, which is WRONG (claude
      looks for a nested plugin manifest and fails with "No manifest found").
      The working commands are `claude plugin validate . --strict` (marketplace)
      AND `claude plugin validate ./plugin --strict` (plugin). Corrected in this
      file (2.6 Verify + Gate item #5), phase-04 (4.4 + its commit example), and
      phase-05 (Gate item #7).
- [x] Verify: `pip install -e ".[dev]"` succeeds;
      `python -c "import importlib.resources as r; print((r.files('kanbanmate')/'assets'/'columns.yml.tmpl').read_text()[:20])"`
      works; `make check` clean; both `claude plugin validate` commands exit 0.

```bash
git commit -m "fix(genesis): bundle columns template as package data (wheel-installable)"
git commit -m "feat(genesis): plugin manifest (plugin.json) for installable /kanban plugin"
git commit -m "docs(genesis): correct plugin-validate gate command"
```
