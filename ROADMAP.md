# ROADMAP

Deferred items from DESIGN §13. These are out of scope for v1.0 but are recognised as
desirable future enhancements.

## Genesis cutover — old PoC skill decommissioned — IMPLEMENTED (0.17.1, scuttle)

The final un-ticked bullet of genesis `DESIGN.md` §11 ("Decommission old location"). The old PoC
skill `skills/kanban/` (n8n dispatcher + a copy of the engine + helper bins + tests) was removed
from the **separate `.claude` portable-config repo** via `git rm -r skills/kanban` (backed up to
`~/kanban-poc-skill-backup-<date>.tgz` first). It is fully superseded by the `kanbanmate` daemon
and the live plugin skills (`plugin/skills/kanban`, `plugin/skills/kanban-monitor`). The other two
§11 bullets (global skill removed; launchd reaper plist + `.claude/CLAUDE.md` refs cleaned) were
already done. Genesis extraction cutover is now fully complete.

## Board repatriation (columns + card positions) — IMPLEMENTED (0.11.0, anchor / helm PR 3)

Shipped in the **anchor** feature (`docs/features/anchor/DESIGN.md`), the 3rd PR of the helm
config-interface arc (PR 1 `helm` #5/#33; PR 2 `bridge`). A per-project **`board_backend: github |
native`** switch (default `github` → every live daemon byte-identical until opt-in) routes the
board's read/move slots to a new **`NativeBoardBackend`** — a decorator over `GithubClient` that
keeps all forge ops (issues, comments, PRs) on GitHub but holds **columns + card placement + a new
intra-column ordering** natively in a `flock`-serialised, atomically-replaced
`<root>/board.json` (`BoardStateStore` port + `FsBoardStateStore` adapter, stdlib-only, no new
dependency). The snapshot becomes a **JOIN** of the GitHub issue set with native placement, and a
**combined `cheap_probe`** (native store version ⊕ forge issue probe) detects both native moves and
new/closed issues. A **one-way GitHub mirror** (default on) keeps the GitHub Projects board, status
pill and Health field reflecting native placement. Genuinely-new **`reorder`/`place`** capability
(GitHub withholds order from its API) is exposed via the interface-segregated `BoardOrdering` port
and the **`/api/board/{state,move,reorder,place,import}`** helm HTTP routes (the PR-2 SPA contract).
Cutover is a per-project, operator-run **`kanban board import`** that seeds `board.json` from the
live Projects v2 snapshot (idempotent). **Merge stays human-only; tickets stay GitHub Issues** —
only the board *view* repatriates.

## Optional webhook ingress adapter — IMPLEMENTED (0.5.0, ingress-multiproject)

Shipped in the **ingress-multiproject** feature (`docs/features/ingress-multiproject/DESIGN.md`).
A `kanban serve` HTTP receiver (the new `http/` entrypoint layer) verifies the GitHub webhook HMAC
(`X-Hub-Signature-256`), identifies which managed project the event hit, and **bumps that runtime
root's daemon-wake nudge sentinel** — the EXACT cockpit nudge mechanism. It does NOT synthesize
`Transition` objects (GitHub `projects_v2_item` payloads don't carry the Status column reliably);
the daemon then runs its normal `tick → snapshot → diff → decide → execute`, so the receiver "slots
in behind the same `BoardReader` boundary" by a sub-second wake, **idempotent by construction**
(a webhook nudge and the slow safety sweep converge on the same diff against persisted state).
**Polling is never removed** — it is the always-on fallback (webhook mode polls slowly as a safety
net). The webhook uses a **plain shared secret + the existing PAT** — no GitHub App (see below).

## GitHub App upgrade — DEFERRED (ticket #26)

Currently KanbanMate uses a **user PAT** (fine-grained, scoped `project` + `repo`); the webhook
(above) uses a plain shared secret, NOT a GitHub App. A GitHub App remains deferred to **ticket
#26** and would provide:

- **Identity-keyed anti-loop** — the bot's own identity rather than the user's, making it
  easier to distinguish bot moves from human moves in the GitHub UI.
- **Clean attribution** — comments and commits appear as the App, not the user.
- **Short-lived scoped tokens** — per-installation tokens with automatic expiry, removing the
  long-lived PAT from `~/.kanban/token`.

## Multi-org support — IMPLEMENTED (0.5.0, ingress-multiproject)

Shipped in the **ingress-multiproject** feature. `projects.json` generalises from "exactly one
project" to N entries (still keyed by project node id), each gaining `org` / `enabled` / `ingress` /
`token_ref`. One daemon now drives **N projects across N orgs**: the run loop sweeps each enabled
project sequentially with its own diff baseline + circuit-breaker + per-project store sub-root
(`<root>/projects/<safe(project_id)>/` — the issue-number collision fix), and the multi-org token
model loads either the shared `<root>/token` (`token_ref=""`) or a per-org `<root>/tokens/<ref>`
(no GitHub App). N=1 is the back-compat special case (legacy flat store layout, zero behaviour
change for the deployed single-project daemons).

## MCP helpers

The current agent helpers (`kanban-comment`, `kanban-move`, etc.) use the urllib GitHub
client directly. Future MCP (Model Context Protocol) helpers could expose the board as a
rich MCP resource, letting the agent reason about the board state without shelling out to
helper bins.

## Auto-merge

**Implemented (operator decision, 2026-06-18).** Originally listed as permanently forbidden, the
operator chose to make the `Review → Merge` transition an autonomous merge AGENT: under a dedicated
`merge` permission profile it brings the PR up to date with `main` (merge-main-in, intelligent
conflict resolution — never rebase/force-push), waits for CI to be fully green, then squash-merges
via `gh pr merge --squash`, self-routing the card to Done on success or back to Review on any
blocker. The `merge` profile is the SOLE profile whose deny-list lifts `gh pr merge` (all other
merge paths, force-push, history-rewrite, and direct-main pushes stay banned even there); a
pre-launch CI gate refuses to launch on a red PR; GitHub branch protection on the default branch
remains the authoritative boundary. See `docs/features/helm/DESIGN.md` §15 (V7 carve-out).
