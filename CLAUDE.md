# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage pipeline**. Downloaded media files land in the staging area, get
renamed, cleaned of junk, scraped for metadata (TMDB/TVDB, MediaElch as manual fallback),
then moved to permanent storage on one of the configured disks.

Package name: `personalscraper`. CLI entry points: `torrentmate` (public command name) and
`personalscraper` (back-compat alias) — same Typer app.

All storage paths, staging layout (`001-MOVIES/`, `002-TVSHOWS/`, …) and category names are
config-driven, never hardcoded; `personalscraper init-config` seeds `config/` from
`config.example/`. Layout: `docs/reference/config-overlay-layout.md`. Module map:
`docs/reference/architecture.md`.

## Setup (per clone)

```bash
pip install -e ".[dev]"
./hooks/install.sh   # one-time per clone — sets core.hooksPath to hooks/ (never ~/.gitconfig)
```

The pre-commit hook regenerates `tests/feature_map/<codename>.json`; CI catches drift if it
is bypassed. Details: `docs/reference/testing.md` §Feature Map.

## Critical Rules

### Product Intent — product constitution (web-UI — BINDING)

**Every web-UI evolution must conform to `docs/reference/product-intent.md`** — the
application's raison d'être, dictated by the operator. **When an implementation conflicts
with this constitution, the implementation is wrong.** Read `product-intent.md` **before
coding** any web surface; every web PR **cites the §§ it serves**.

### Design Reference — the maquette is authoritative (web-UI — BINDING)

**`frontend/maquette/design/refonte.html` is the visual reference of the web UI** (§15 of the
constitution). Every design evolution **starts from the maquette, never from the code**.

**READ THIS BEFORE ANYTHING ELSE — the maquette is the NEXT version of the app, and it will
REPLACE it.** On switchover day `frontend/src` is ARCHIVED and the maquette takes its place. It
is not transposed into the app, not translated, not merged surface by surface. That is why every
page and every mechanism the app has must eventually be re-created IN the maquette: afterwards
there is nothing left to take from.

So a maquette/production difference is **never** a production bug, and never something to
"repair" by pointing a tool at the other side. The two differ because one replaces the other.

**A whole layer of tooling was built for the opposite model and is now void** (operator,
2026-08-20). The 2026-08-10 spec (§4.1, §7.2) planned to migrate the app towards the maquette
surface by surface, which required CSS extraction, a `.tm` scope so the two stylesheets could
coexist, a selector allowlist, a drift guard and a rendering-parity probe. The 2026-08-13
directive reversed that order and the tooling stayed. It has no subject: you do not make two
stylesheets coexist when one replaces the other, and you do not translate a CSS that BECOMES the
CSS. Retiring it is the correction, not a risk.

**The rule that follows, and it is the expensive lesson**: when a decision changes, the
implementation directives change IN THE SAME MOVE. What loses its subject is removed, not kept
"just in case" — machinery nobody can justify becomes machinery nobody dares delete.

**The method that survives, and it is the whole method:**

1. The **maquette is modified first**, verified with its harness (`frontend/maquette/harness/`).
   Nothing about a surface is decided anywhere else.
2. A surface is **drawn before it is coded**, with named states and a rule that bites.
3. The **harness is the proof**: a change lands with its rule, and the rule is mutation-tested —
   break the behaviour on purpose, confirm the rule falls and names the right defect, restore.
4. **The rule suite runs on a schedule, not on a hunch** — `frontend/maquette/harness/run.sh`:
   - `--contracts` (5 rules, minutes) runs **in CI on every PR touching the maquette**. These
     are the rules that fall when a NAME moves without all of its ends. A rule that reads
     the operator's live databases cannot be among them — `arrivals.py` was, and failed on
     the runner for want of `library.db`, which says nothing about the change under test.
   - no flag (51 rules, 20-25 min) is the **gate before a wave is merged**, and it is not
     optional. It ran nowhere automatically until 2026-08-20, and on that day a rename that
     looked contained broke SIX contracts — four of them visible to nothing else, including a
     dead pipeline stop button, while `lint`, `test` and `check` were all green.

   The script builds and re-copies the prototype first, because the harness reads a MANUAL copy
   at `/tmp/tm-refonte/wrapped.html` and a stale one measures the previous build in silence.

#### The mission — dictated by the operator, 2026-08-19 (SUPERSEDES any narrower reading)

**The maquette is a NEW VERSION of the app, and EVERY screen is to be redrawn. All of them.**
It is not a reskin of the shipped surfaces and it is not bounded by what production happens to
have today. Its purpose is a new, COHERENT user experience, and the first objective is to
**freeze that interface**.

Four consequences, and none of them is optional:

1. **No surface is out of scope.** Any production screen with no page in the maquette is a page
   still to be drawn — never an arbitration to leave it out. This explicitly REVERSES the
   earlier ruling that `/control` (« Contrôle ») and `/pipeline` were deliberately page-less:
   the operator overturned it. Their redistribution into Arrivées / Système / Maintenance /
   Configuration remains a valid UX proposal, but it does not exempt anything from being drawn.
2. **What is already in the maquette is VALIDATED** by the operator. Do not relitigate it.
3. **What remains is not only pages.** The UX, the interaction language, the architecture of the
   prototype and the missing pages all have to be finished and consolidated. The interface is
   frozen when that work is done, not when the last page exists.
4. **The backend follows the interface, not the reverse.** The engine will be adapted to what
   the new interface needs. So a backend limitation is not a reason to draw less — record it and
   draw what the experience requires. Backend work comes AFTER the interface is frozen.

Read `frontend/maquette/README.md` before any design change — method, named states, verified
rule set, and the traps already paid for.

### Search Safety (MANDATORY — machine crash prevention)

`tests/e2e/perf/.fixture/` is **14 GB** of binary media files. `rg` without type
filters WILL consume all RAM and crash the machine (PID 39685 incident).

**Every `rg` command MUST include one of:**

- `--type py` (Python files only)
- `-g '*.py'` (glob filter)
- `-g '*.md'` or `-g '*.json5'` etc. for non-Python targets

**Examples:**

```bash
# CORRECT
rg "pattern" --type py personalscraper/ tests/
rg "pattern" -g '*.py' -g '*.md' .

# WRONG — will crash the machine
rg "pattern" personalscraper/ tests/
rg "pattern" .
```

`.rgignore` at the repo root excludes known heavy dirs as defense-in-depth,
but new fixtures can appear — the type filter is the primary safeguard.

### Network Timeout Safety (MANDATORY — machine hang prevention)

**curl, wget, and fetch can hang indefinitely** when a server accepts the TCP
connection but never sends an HTTP response (omdbapi.com/swagger.json incident,
11+ hours). A `block_curl_without_timeout` PreToolUse hook enforces this rule.

**Every network command MUST include both:**

- `--connect-timeout N` (TCP handshake timeout, recommended 10s)
- `--max-time N` (total transfer timeout, recommended 30s)

**Examples:**

```bash
# CORRECT
curl --connect-timeout 10 --max-time 30 "https://api.example.com/data"
wget --timeout 30 "https://example.com/file"

# WRONG — will hang indefinitely if server accepts TCP but never responds
curl "https://api.example.com/data"
```

**WebFetch caveat**: WebFetch has no configurable timeout. Prefer `Bash(curl)` with
explicit timeouts for API calls to hosts that may be slow or unreachable.

### Commit Convention

Follows [Conventional Commits](https://www.conventionalcommits.org/) — globally enforced for
all projects using this `.claude/` config. Format: `<type>[(<scope>)]: <description>`.

Types: `feat | fix | chore | refactor | style | docs | test | perf | build | ci`
Examples: `feat(scraper): create TvShow nfo file` · `refactor(dispatch): extract folder_for to resolver`

**Forbidden**:

- Version prefixes (`vX.Y.Z: Description`) — version traceability lives in `IMPLEMENTATION.md`
  and subagent reports (sub-phase → SHA mapping), not in commit messages
- AI attribution: `Co-Authored-By`, `Claude`, `Anthropic` — enforced by `hooks/commit-msg`,
  which also holds the Conventional-Commit format and the version-prefix ban. It runs on
  every commit in this clone (`core.hooksPath = hooks`). **It cannot reach the squash-merge
  message composed on GitHub**, which is the message that lands on `main` — only a
  server-side check would. (The previously named `hooks/block_ai_attribution.py` never
  existed: the real file is a gitignored Claude-Code tool hook that sees only the agent's
  own `git commit` invocations.)

Milestone-commit format and the codename-as-scope rule: `docs/reference/feature-lifecycle.md` §7.

### Pipeline Monitoring Rules

When running `personalscraper run` or any long-running command with user observation:

1. **NEVER run in background** — foreground only, `timeout=600000`. A hook (`block_background_pipeline.py`) enforces this.
2. **Create TODO tasks BEFORE launching** — categories: bugs, inconsistencies, improvements. Update in real-time.
3. **Show output after each step** — read and display incrementally, don't wait for the end.
4. **Kill on 2 identical consecutive errors** — systemic failure = STOP immediately, don't keep trying.
5. **State limitations upfront** — if you can't guarantee something, say so BEFORE agreeing.
6. **After kill: check filesystem** — orphans, lock files, temp dirs. Clean or report what can't be cleaned.

Alternative: run steps individually (`personalscraper ingest`, then `personalscraper sort`, etc.) to maintain control between steps. Use `-v` only for debugging a specific step (generates 100× more output).

### Code Conventions

- **Google-style docstrings** mandatory on all modules, classes, functions, and methods
- Docstrings include: description, `Args:`, `Returns:`, `Raises:` (as applicable)
- **Inline comments** for non-trivial logic explaining the "why" (not the "what")
- Docstring/comment language: **English**
- **No French in the code, and no interface text in the code** — see §Language below. It is
  enforced, not remembered: `python3 scripts/check-no-french.py` (in `make check` and in CI).
- New tests: choose unit / integration / manual E2E — see `docs/reference/testing.md`.
- **Renaming an identifier goes through `scripts/rename-identifiers.py`** — never by hand,
  never with an ad-hoc regex. Every bypass has cost something: a rewritten route, eleven state
  ids, eight interface texts and five rule assertions in one wave alone. **But the tool is not
  the proof.** Its read-back check is skipped for `--values` runs and for Python files — and
  `--values` is the mode that rewrote 429 lines of prose. So every rename batch is verified by
  an oracle OUTSIDE the tool: re-read the diff (not the « N file(s) touched » line), and re-run
  the harness rule suite. Two corruptions in this repository were found by reading the diff
  after the tool reported success.
- **A bug fix carries a regression test**, and the test is shown to FAIL against the code as it
  stands before the fix. A test written after the fix that was never seen red proves only that
  it agrees with the fix.
- **Module size**: soft warning at 800 non-blank LOC, hard ceiling 1000 LOC (exit 1). Run `python3 scripts/check-module-size.py` (also wired into `make check`).

### Phase Gate Checklist (MANDATORY before every phase gate commit)

Every `chore(scope): phase N gate` commit MUST pass all of:

1. **`make lint`** — ruff + mypy (both wired in Makefile). Zero errors.
2. **`make test`** — all 9000+ tests pass. Check the summary line: `NNNN passed` with 0 failed/errors.
3. **`make check`** — lint + test + module-size + typed-api guardrails.
4. **Residual import grep** — for every module deleted in this phase, grep both `personalscraper/` AND `tests/` for the old import path. Zero matches.
5. **`python -c "import personalscraper"`** — smoke test.

An ERROR (not just FAILED) in `make test` means test COLLECTION crashed — everything after it
was skipped. Post-deletion and post-signature-change grep rules:
`docs/reference/feature-lifecycle.md` §7.

### Implementation Workflow (feature-oriented)

12 `implement:*` skills cover the feature lifecycle; **Sonnet is forbidden as a dispatch
target**. Entry point `/implement:feature` (brainstorm → codename + SemVer → branch → plan),
then `/implement:phase` until the PR. Branches `feat/{codename}` / `fix/{codename}`, commits
scoped with the codename, squash merge. Full flow, model allocation, milestone commits and the
KanbanMate claim procedure: `docs/reference/feature-lifecycle.md` §7.

**Claim a ticket that ALREADY EXISTS on the board before coding it** — `/kanban-work <ticket>`,
so the autonomous KanbanMate daemon stays out of the way, and advance the card as you go.

**Do NOT create a ticket for work you are about to do in this session** (operator, 2026-08-19).
The claim procedure exists to keep this session and the daemon off each other's cards; it is not
a bookkeeping ritual. Work that can be carried out in the session at hand is simply carried out
— inventing and claiming a card for it is counterproductive.

### Move Rules (dispatch)

- **Movies** (category IDs: `movies`, `movies_animation`, `movies_documentary`, `standup`, `theater`): if a folder with the same name already exists on a disk, **replace it** with the new version from the staging area.
- **TV Shows** (category IDs: `tv_shows`, `tv_shows_animation`, `tv_shows_documentary`, `anime`, `tv_programs`): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

### Security & Paths

- **qBittorrent: NEVER enable "Bypass authentication for clients on localhost"** (nor any "trust localhost" / IP-whitelist variant). qBittorrent sits behind the reverse proxy, so Internet traffic reaches it seen as localhost — the bypass would expose the qBittorrent WebUI to the whole world, passwordless. Details: `docs/reference/qbittorrent-api.md` (Auth).
- **Never include API keys** in documentation or brainstorming files — use `.env` references only.
- Storage/staging paths may contain spaces (e.g. `/Volumes/<disk>/<staging-dir>/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.

### Web-UI Environments (ENV-SEP) & Binding Invariants

Three checkouts share `library.db`, `.data/` and the storage disks: **dev** = `~/dev/PersonalScraper`
(feature branches, no PM2 daemons) · **prod** = `~/deploy/torrentmate` (tracks `main`, `torrentmate-web`
on 8710) · **staging** = `~/staging/torrentmate` (tracks `staging`, 8711, read-only role → 403 on
writes). Canonical config lives at `~/.torrentmate/config`, outside every working tree. Full topology
and deploy runbook: `docs/reference/web-ui.md`.

- **NEVER start a local server on 8710/8711** (Caddy routes `tm.`/`tm-staging.` there) — test the frontend via `tm-staging.iznogoudatall.xyz`.

Invariants enforced by tests (do not regress; details in `docs/reference/web-ui.md` + `maintenance.md`):

- Every mutating web endpoint is staging-guarded (`require_not_staging`) and typed (Pydantic `response_model` → OpenAPI → `schema.d.ts`; any route change ⇒ `make openapi` + commit the regenerated files).
- The web auth perimeter is the **single** `guarded_api` dependency (web-ui.md §6) — never add per-route `Depends(require_session)`.
- Write/destructive maintenance actions hold `pipeline.lock` for their runner's whole lifetime (maintenance.md §Pipeline lock).
- `pipeline_run` timestamps (run-level AND per-step `steps_json`) are Unix-epoch `time.time()`.
- `GET /api/version` serves the **boot-cached** BUILD_COMMIT; `scripts/deploy.sh` hard-asserts the running process serves the deployed sha.

### Language

The operator communicates in French or English — respond in French when they write in French.
Everything durable is **English only**: code comments, docstrings, maquette/harness sources, and
all engineering documentation (`docs/`, `BUGS.md`, `CHANGELOG.md`, `ROADMAP.md`,
`IMPLEMENTATION.md`, this file). **Never mix languages within a document.** Exceptions:

- **Operator-facing docs stay French**: `README.md`, `MANUAL.md`, `INSTALLATION.md`,
  `CONFIGURATION.md`, `docs/reference/product-intent.md` (the constitution, dictated by the
  operator).
- French inside an English document is allowed **only** to quote UI copy / app screens and
  sections named in French (in « guillemets »), media titles, or the operator verbatim.
- `docs/archive/` is frozen history — never translated, never restyled.
- Maquette/harness comments carry no reference to a session, a phase or a dated decision —
  they must still read years from now, out of context.

**The code itself contains NO French, and no interface text.** Two halves of one rule,
enforced by `scripts/check-no-french.py` (fourteen arms, in `make check` and in CI):

- **English names, everywhere and always**: identifiers, function/type/**class** names (code
  AND CSS), **file and directory names**, and every message the tools print. A new file, a new
  class, a new variable is named in English on the day it is written — this is not a cleanup
  someone does later.
- **No UI string lives in the code.** The French a reader of the interface sees lives in the
  i18n resources: `frontend/maquette/design/src/i18n/fr.json` for the shell — read through
  `useTranslation()` — and the same file's `server` namespace for the pages `serve.py` serves.
  Extract strings, never retype them: a retyped string is a defect, because it renders
  correctly while the reference is broken.
- **`frontend/src` is EXEMPT from that rule, deliberately.** The production React app has no
  i18n layer at all — no `i18n/` directory, no `useTranslation()` — and its French is written
  straight into the components. That is the app the maquette shell is being built to replace,
  so moving that copy into resources would be work thrown away with the app that holds it.
  The exemption is the operator's, and it is not a licence to relax: **it is a RATCHET.**
  `check_app_interface_text` reads that whole tree — JSX text nodes included, which carry no
  quotes — and **refuses the count going UP**, against the baseline pinned in
  `scripts/french-exemption-baseline.json`. It is counted in two figures, because they are not
  the same thing: French in PRODUCTION components (the debt, and the only one the ratchet
  guards) apart from French a TEST asserts, which is the app's rendered output and legitimate.
  A printed number was not enough — it drifted by 7 inside the very PR that introduced it as a
  control and nothing noticed, because a number nobody compares is a number nobody reads. An
  exemption nobody counts is indistinguishable from an oversight — which is precisely how 842 of those
  strings, three all-French shell scripts and `id="coquille"` each sat under a green gate.
- **`data-*` attribute NAMES are code and follow the rule.** They were carved out here once,
  and the operator overturned that: a `data-*` name is a name someone chose, so it is written
  in English like any other. Their VALUES are not — `data-go="profil"` names a page, and a
  page id is an address. A contract has three ends — the markup that emits it, the
  `dataset.X` that reads it, and the rules that tap it — and they move in ONE step or the
  interface half-works in a way no single file reveals.
- **What is NOT French-in-the-code**, and must stay as it is: the French a harness hold
  ASSERTS (that is the app's rendered output — translating it would silently stop measuring
  anything), i18n interpolation placeholders, form field names, and the config keys the
  settings dictionaries are keyed by. **« data VALUES » is not the escape hatch it was read
  as**: a NAMED STATE id is a name someone chose (`window.__go("acq-now-idle")`), and 51 of
  the maquette's 82 were French until 2026-08-20 because « it is a value » was accepted as
  an answer. A value is a datum the app STORES or DISPLAYS — a title, a folder, a status
  string from the backend. If a human typed it to designate something, it is a name. **Route paths are NOT on this list any more**
  — #456 struck them off on the operator's ruling (« une route et un paramètre sont des NOMS,
  pas des données ») and renamed the three French addresses, answering the old ones with
  redirects. This sentence kept exempting them for four days afterwards, which is why
  `/deconnexion` on the design host is still French: nothing reads a route the rule says is
  not its business. Each such literal
  carries a `# french-ok: <reason>` / `// french-ok: <reason>` pragma; a pragma with no reason
  is itself a violation. The frozen CSS-class exceptions live in
  `frontend/maquette/regions.json`'s `$vocabulary`, each with the reason it was kept.
- **The guard asks « is this word one we use? », not « is this word French? »** The second
  question is only ever as good as its list of French words, and that list had holes —
  `suivante`, `trier`, `fermer`, `chargement`, `compte`, `monde` were invisible to it, so
  « no violation » meant « none among the words we thought of » while a hundred and forty
  French names sat under it. `scripts/code-vocabulary.txt` holds the words this codebase's
  names are built from; a name built from a word nobody wrote down is refused, whatever
  language it comes from. **Adding a word is one line, and that is the point**: a French word
  can only enter by someone typing it into a file under review.
- **A vocabulary SEEDED from the codebase certifies the status quo.** The first version of
  that file was, so the twenty-five French words that twenty-nine names in
  `design/src/engine/legacy.js` still needed came in with the rest and the gate went green
  over them — the exact failure the arm was written to end. They live below a banner in the
  file now, named as French on purpose, and `check_french_debt` refuses them to every file
  but the dying engine, so the debt cannot spread while SP4-fin waits. **When the engine
  goes, that section goes with it.**
- **Every rule in this section has an ARM, or it is a sentence in a file.** `data-*` names
  were brought under the rule and nothing read them for a wave: nineteen moved by hand and
  four — `data-prendre`, `data-maintrub`, `data-qreg`, `data-apparence` — simply stayed.
  A scope is checked the same way: `frontend/scripts/` is not `scripts/`, and that one word
  of difference left an entire tool (`SORTIE`, `JAUNE`, `anneau_depuis_staging`) outside
  every arm while the gate reported no violation.

## Reference Index (lazy-load when relevant)

Load these docs on-demand based on your task — they are **not** auto-loaded:

| When working on... | Read |
| --- | --- |
| CLI commands, pipeline invocation, scheduling (PM2 crons), make targets | `docs/reference/commands.md` |
| Disks, NTFS/macFUSE, rsync flags, disk space rules, move rules details | `docs/reference/storage.md` |
| Directory layout, module map, shared utilities, dependencies, api/ contracts (HttpTransport, Protocols) | `docs/reference/architecture.md` |
| Movie/TV folder naming, episode patterns, filename sanitization | `docs/reference/naming.md` |
| Unit tests, E2E, roundtrip, golden files, test markers, timeouts, feature map | `docs/reference/testing.md` |
| TMDB/TVDB APIs, NFO invariants, artwork, ffprobe language codes | `docs/reference/scraping.md` |
| rapidfuzz, tenacity, structlog, rich, guessit gotchas | `docs/reference/libraries.md` |
| Circuit breaker, fast-skip, dispatch/verify internals, idempotence | `docs/reference/pipeline-internals.md` |
| EventBus internals, event catalog, subscriber recipes, AppContext boundary rule, ContextVar pattern | `docs/reference/event-bus.md` |
| Logging conventions, event-name style, structlog vs CLI vs typer channels | `docs/reference/logging.md` |
| Trailer discovery, download, state, CLI, Plex-conformant placement | `docs/reference/trailers.md` |
| Media indexer DB, scanner modes, query parser, outbox, cron setup, failure recovery | `docs/reference/indexer.md` |
| JSON column shapes (artwork_json, payload_json, stats_json) — Pydantic models and examples | `docs/reference/indexer-json-shapes.md` |
| Cross-provider IDs flow, ratings JSON, backfill mode, capability protocols | `docs/reference/external-ids-flow.md` |
| Any provider or client — TMDB/TVDB/OMDB/Trakt, qBittorrent/Transmission, C411/Tr4ker + Torznab, Telegram/healthchecks | `docs/reference/<provider>-api.md` |
| Plex refresh after dispatch (X-Plex-Token, partial scan, longest-prefix section, fail-soft) | `docs/reference/plex-api.md` |
| Provider naming — `ProviderName` Enum (transport) vs `RegistryProviderName` NewType (registry) | `docs/archive/features/registry/DESIGN.md` §5.3 |
| Insights layer — analytics, reporting, recommendations over the indexer DB | `docs/reference/insights.md` |
| Maintenance ops — disk cleaning, targeted re-scrape repairs, web-UI action catalog + runner | `docs/reference/maintenance.md` |
| ffprobe stream extraction, codec/language → Kodi NFO mapping | `docs/reference/ffprobe-api.md` |
| Config split layout, JSON5 overlay composition, per-file key ownership | `docs/reference/config-overlay-layout.md` |
| Config home relocation — canonical location, migration runbook | `docs/archive/features/config-home/DESIGN.md` |
| Feature lifecycle — ACCEPTANCE format, phase gates, implement:\* flow, KanbanMate claim | `docs/reference/feature-lifecycle.md` |
| Module-size budget tracking, BLOCK-threshold promise status | `docs/reference/promises.md` |
| Post-merge operator checklist (DB schema, config/CLI migrations, ACC re-exercise) | `docs/reference/runbook-post-merge.md` |
| TorrentMate web UI — architecture, auth, WS protocol, Redis relay, PWA, deploy runbook, REST conventions | `docs/reference/web-ui.md` |
| **Product intent — the product constitution (BINDING): §1–§15 + DOIT/NE-DOIT-PAS + §méthode** | `docs/reference/product-intent.md` |
| **Maquette — the VISUAL reference of the web UI (BINDING): it is modified BEFORE the code** | `frontend/maquette/README.md` |

Also check archived alpha versions under `docs/archive/legacy-alpha/` and archived features under `docs/archive/features/`.

## Current Feature

Tracked in `IMPLEMENTATION.md` at the repo root — feature, branch, phases, PR and next
action. Read that file, not this section: a copy here goes stale and contradicts it.
