# Phase 16 — GitHub ops + CLI/doctor parity (issue_context · REST pagination · branch-protection probe · sessions format)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §3.1/§3.3 (board adapter + read-model reports), §4 (doctor 3-tier), §11
> (port-from-PoC; the PoC is the source of truth). Restores the CONFIRMED non-pivot GitHub-adapter +
> CLI feature losses from the parity audit's "GitHub adapter" + "CLI command surface" sections.
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`):
> `<OLD>/github/client.py` `issue_context:191-212` / `close_pull_request:214-231` /
> `list_issue_comments:233-249` (the Link rel=next loop) · `<OLD>/github/_queries.py`
> `issue_context:289-319` (the GraphQL builder) · `<OLD>/github/_parsers.py`
> `parse_issue_context:226-261` · `<OLD>/github/_rest.py`
> `next_link_path:51-70` / `list_issue_comments:73-79` (`per_page=100`) /
> `list_open_pulls_for_branch:95-106` (`per_page=100`) / `parse_open_pull_number:118-123` ·
> `<OLD>/cli/probes.py` `parse_branch_protection_on:59-79` · `<OLD>/cli/runners.py`
> branch-protection probe `459-467` + `run_sessions:99-110` · `<OLD>/cli/plan_doctor.py`
> `branch_protection` WARNING `99-103` · `<OLD>/cli/reports.py` `build_sessions_report:42-59` +
> `SessionRow:17-23`. NEW root: `/Users/izno/dev/KanbanMate/src/kanbanmate/`.

**Goal**: bring NEW's GitHub adapter + CLI to behavioural parity with the PoC on the four CONFIRMED,
non-pivot losses the audit flagged (all unrelated to the n8n→polling pivot — pure hardening / feature
restorations):

1. **`issue_context`** (audit HIGH) — ENTIRELY ABSENT in NEW. The GraphQL query gathering an issue's
   body + up to 50 comment bodies + the FIRST cross-referenced/linked Issue body, used to assemble the
   rich agent-prompt context (placeholders `{{ticket_body}}` / `{{issue_body}}` / `{{comments}}`). No
   `issue_context` method, no GraphQL builder, no parser exist in NEW (16.1).
2. **REST `list_issue_comments` Link rel=next pagination** (audit MEDIUM) — NEW issues a SINGLE
   un-paginated GET; a sticky comment beyond page 1 is invisible → the upsert CREATES A DUPLICATE.
   Root cause: NEW's `UrllibTransport._request` does `resp.read()` and returns body ONLY — response
   headers (incl. `Link`) are never captured, so there is NO plumbing to paginate (16.2).
3. **`find_open_pr` / `list_open_pulls_for_branch` `per_page=100` + Link rel=next** (audit LOW) — NEW
   issues `?state=open&head={owner}:{branch}` with NO `per_page` and NO Link loop; the PoC paged at 100
   (16.3).
4. **doctor `branch_protection_on`** (audit MEDIUM) — the live `gh-api` probe of
   `repos/<repo>/branches/main/protection` is DEAD in NEW's production path (`app.py:183` calls
   `run_doctor()` with NO `branch_check`, so it always returns the advisory placeholder); restore the
   real REST probe wired from the registry + the GithubClient (16.4).
5. **`sessions` command output format** (audit LOW) — restore the PoC's TSV
   `#<issue>\t<tmux>\t<live|DEAD|stopped>\t<status>` and the THIRD `stopped` bucket
   (state-but-not-running-and-session-gone) that NEW collapsed (16.5).
6. **`issue_state` (GraphQL open/closed probe)** (audit MEDIUM — operator decision 2026-06-05) — the
   per-dependency LIVE state query the PoC used to resolve `Depends on #N` gates. NEW dropped it when it
   moved the dependency gate to the board snapshot; the phase-17 **#13 hybrid** restores it as the
   FALLBACK for off-board deps (closed-but-not-a-`Done`-card). Port the GraphQL query +
   `parse_issue_closed` + `GithubClient.issue_state(number) -> bool` (16.6). This sub-phase is a HARD
   PREREQUISITE of phase 17 #13 — phase 16 runs before 17.

**Layering invariants (every sub-phase).** `core/` imports nothing with I/O; `ports/` are Protocols;
`adapters/` implement `ports/`; `app/`/`cli/` compose; downward-only imports (enforced by
`tests/test_layering.py`). Every urllib request inherits the client's mandatory connect+read timeouts
(CLAUDE.md Network Timeout Safety). Every `rg` is type-filtered. mypy strict; module soft-cap ~800 LOC.
**Clear `.mypy_cache` before every gate check** (its incremental cache has masked real errors here):
`rm -rf .mypy_cache && make check`.

---

## Gate

Phases 1–15 complete; branch `feat/genesis`; `make check` green at start (run
`rm -rf .mypy_cache && make check` to confirm a clean baseline — the incremental mypy cache has masked
breaks in this repo). Re-sync confirmed (DESIGN §11 pre-implementation gate): the PoC `github/` +
`cli/` modules cited above are present in `.claude/skills/kanban/` and read for this port.

---

## 16.1 — Port `issue_context` (GraphQL: body + ≤50 comments + first linked issue)

**The gap.** ENTIRELY ABSENT in NEW: no `issue_context` method on `GithubClient`, no GraphQL builder
in `_queries.py`, no parser in `_parsers.py` (audit "GitHub adapter" §1, lines 69-76). The PoC's
`issue_context` (OLD `client.py:191-212`) drives a GraphQL query (OLD `_queries.issue_context:289-319`)
fetching `issue.body`, `comments(first: 50) { nodes { body } }`, and
`timelineItems(first: 20, itemTypes: [CROSS_REFERENCED_EVENT])` for the FIRST linked Issue body, parsed
(OLD `_parsers.parse_issue_context:226-261`) into `{body, comments[], linked_issue_body}`. The PoC
runner consumed it to fill `{{ticket_body}}`/`{{issue_body}}`/`{{comments}}`. NEW's `LaunchAction`
launches a STATIC `agent_command` with no per-ticket placeholders, so there is NO consumer in NEW
today — this sub-phase restores the GITHUB-ADAPTER capability (the prompt-template pipeline that would
consume it is a separate loss, out of scope here). The restored method is a faithful adapter port with
no caller; document that explicitly so a reviewer does not flag it as dead code.

**Layer**: `adapters/github/` (GraphQL builder + parser + client method) and a typed value object the
parser returns. **Files**: `src/kanbanmate/adapters/github/_queries.py` (add `issue_context`),
`src/kanbanmate/adapters/github/_parsers.py` (add `parse_issue_context`),
`src/kanbanmate/adapters/github/types.py` (add the `IssueContext` frozen dataclass),
`src/kanbanmate/adapters/github/client.py` (add `issue_context(...)`),
`tests/adapters/github/test_client.py` (extend) + `tests/adapters/github/fixtures/` (add the
issue-context response fixture).

- [ ] Add `_queries.issue_context(owner: str, name: str, number: int) -> dict[str, Any]` — port OLD
      `_queries.py:289-319` VERBATIM-IN-SPIRIT (the GraphQL string is the contract): `repository(owner,
name) { issue(number) { body, comments(first: 50) { nodes { body } },
timelineItems(first: 20, itemTypes: [CROSS_REFERENCED_EVENT]) { nodes { ... on
CrossReferencedEvent { source { ... on Issue { body } } } } } } }`, returning
      `{"query": query, "variables": {"owner": owner, "name": name, "number": number}}`. Match NEW's
      existing `_queries` builder style (triple-quoted query + `variables` dict). Google-style docstring
      citing the source.
- [ ] Add `@dataclass(frozen=True) IssueContext` to `types.py` with English docstrings:
      `body: str`, `comments: tuple[str, ...]` (ordered comment bodies, ≤50),
      `linked_issue_body: str | None` (the first cross-referenced Issue body, or `None`). Use a
      `tuple` (not `list`) to keep the value object hashable/immutable, consistent with NEW's other
      frozen `types.py` records (`RawItem`, `CommentRef`, `StatusField`).
- [ ] Add `_parsers.parse_issue_context(data: dict[str, Any]) -> IssueContext` — port OLD
      `_parsers.py:226-261`: `raise_for_errors(data)` FIRST (a non-empty `errors` array raises
      `GraphQLError`, matching every other NEW parser); then drill
      `data["data"]["repository"]["issue"]` defensively (every level `or {}`); `body = str(issue.get
("body") or "")`; `comments` = the `nodes[].body` strings where `body is not None`; iterate
      `timelineItems.nodes`, take the FIRST node whose `source.body is not None` as
      `linked_issue_body`, else `None`. Return `IssueContext(...)`. Faithful to the PoC's None-guards.
- [ ] Add `GithubClient.issue_context(self, number: int) -> IssueContext` — repo-less (NEW's client
      carries `self._repo`, unlike the PoC which passed `repo`): split `self._repo` into `owner, name`,
      call `self._graphql(_queries.issue_context(owner, name, number))`, return
      `_parsers.parse_issue_context(data)`. Document in the docstring that NEW has NO in-tree consumer
      yet (the prompt-template pipeline is a separate restoration); the method exists for GitHub-adapter
      parity (audit HIGH) and the future launch-prompt enrichment.
- [ ] Tests (`tests/adapters/github/test_client.py` + a fixture): inject a fake GraphQL transport
      returning a fixture with a body, two comments, and one cross-referenced Issue source — assert
      `issue_context(N)` returns `IssueContext(body=…, comments=("a", "b"), linked_issue_body=…)`; a
      response with NO `timelineItems` → `linked_issue_body is None`; a response whose only
      cross-reference source has no `body` → `None`; an `errors`-bearing response → raises
      `GraphQLError` (the parser's `raise_for_errors`). Add a `parse_issue_context` direct unit test on
      a raw dict (no client) for the None-guards.
- [ ] Verify: `rm -rf .mypy_cache && make check` green; layering guard sees the new code stay in
      `adapters/github/` (no upward import; `IssueContext` lives in `types.py`, not `core/`).

```bash
git commit -m "feat(genesis): port GitHub issue_context (body + comments + linked-issue GraphQL context)"
```

---

## 16.2 — REST issue-comments Link rel=next pagination (headers seam + pager)

**The gap.** NEW's `list_issue_comments` (`client.py:344-366`) issues a SINGLE GET with NO `per_page`
and NO Link following. The ROOT CAUSE (audit "GitHub adapter" §2/§4, lines 77-96): NEW's
`UrllibTransport._request` (`client.py:91-131`) does `resp.read()` and returns ONLY
`json.loads(raw)` — `resp.headers` is never captured, so the `Link` header is STRUCTURALLY
inaccessible. On an issue with >30 comments (GitHub REST default page size) a sticky on page 2+ is
invisible → `find_stage_comment_id` returns `None` → the §8.1 upsert CREATES A DUPLICATE STICKY each
tick instead of editing in place. The PoC followed `Link rel=next` via `_rest.next_link_path:54-70`
(OLD `client.py:233-249`), tested at OLD `test_client.py:295-307`. This sub-phase adds the
headers-bearing transport seam and the pager.

**Layer**: `adapters/github/` ONLY. **Files**:
`src/kanbanmate/adapters/github/_rest.py` (NEW module — port the pure REST builders + `next_link_path`),
`src/kanbanmate/adapters/github/client.py` (add a headers-returning REST seam +
rewrite `list_issue_comments` to loop), `tests/adapters/github/test_pagination.py` (extend with the
REST-comments page-2 test) + `tests/adapters/github/fixtures/` if a fixture is helpful.

- [ ] Add `src/kanbanmate/adapters/github/_rest.py` — port ONLY the pure pieces NEW needs (NOT the
      org-webhook builders, which are pivot-removed):
  - `_PER_PAGE = 100` (the page-1 max so a small issue's comments fit one page).
  - `next_link_path(link_header: str | None, *, base: str = "https://api.github.com") -> str | None`
    — port OLD `_rest.py:51-70` VERBATIM (the `_LINK_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')`
    regex + the base-strip). Returns the path+query of the `rel="next"` URL, or `None`. **This is the
    only Link-parsing helper; both 16.2 and 16.3 use it.**
  - `list_issue_comments(repo: str, number: int) -> tuple[str, str, None]` — port OLD `_rest.py:73-79`:
    `("GET", f"/repos/{repo}/issues/{number}/comments?per_page={_PER_PAGE}", None)`.
  - `list_open_pulls_for_branch(repo: str, branch: str) -> tuple[str, str, None]` — port OLD
    `_rest.py:95-106`: owner-qualified head + `&per_page={_PER_PAGE}` (consumed by 16.3).
  - `parse_open_pull_number(items: list[dict[str, Any]] | None) -> int | None` — port OLD
    `_rest.py:118-123` (consumed by 16.3).
  - English Google-style docstrings; the module docstring states it carries the PURE REST request
    builders + the Link pager helper (the org-webhook builders are intentionally NOT ported — pivot).
- [ ] Add a headers-bearing seam to `UrllibTransport`. The MINIMAL faithful change: add a private
      `_request_with_headers(...) -> tuple[Any, dict[str, str]]` that returns BOTH the decoded body
      AND `dict(resp.getheaders())`, then make the existing `_request` call it and discard the headers
      (keep `_request`'s `-> Any` signature so every current caller is unchanged). Add a public
      `rest_with_headers(method, path, body) -> tuple[Any, dict[str, str]]` next to `rest(...)` that
      the pager calls. **Both paths apply the SAME connect-then-read timeout discipline** (the
      `HTTPSConnection(timeout=connect)` + `conn.sock.settimeout(read)` dance) — do NOT introduce a
      second, untimed read path (CLAUDE.md MANDATORY). The default `rest` seam stays body-only so the
      board/seeder callers are untouched.
- [ ] Extend the `RestTransport` type or add a parallel `RestHeadersTransport =
Callable[[str, str, "dict[str, Any] | None"], tuple[Any, dict[str, str]]]` and a
      `self._rest_headers` handle on `GithubClient` (defaulting to `default.rest_with_headers`, or a
      shim wrapping an injected `rest_transport` to `(body, {})` so existing tests that inject a
      body-only fake still work). Keep the no-header fallback explicit: an injected legacy
      `rest_transport` yields empty headers → the loop terminates after page 1 (graceful).
- [ ] Rewrite `GithubClient.list_issue_comments(issue_number)` to LOOP (port OLD `client.py:233-249`):
      build the page-1 path via `_rest.list_issue_comments(self._repo, issue_number)`; while `path is
not None`: `raw, headers = self._rest_headers("GET", path, None)`; extend an accumulator with
      `_parsers.parse_issue_comments(raw if isinstance(raw, list) else [])`; advance
      `path = _rest.next_link_path(headers.get("Link") or headers.get("link"))`. Return the
      accumulated `list[CommentRef]`. The accumulated ids stay `int` (NEW's `CommentRef.comment_id:
int`) — no `str` regression.
- [ ] Tests (`tests/adapters/github/test_pagination.py`): a fake `rest_with_headers` returning page 1
      (with a `Link: <…&page=2>; rel="next"` header) then page 2 (no Link) — assert `list_issue_comments`
      issues TWO GETs, the second path is `…/comments?per_page=100&page=2`, and a sticky marker living
      ONLY on page 2 is present in the returned list (the exact PoC regression
      `test_list_issue_comments_follows_link_to_page_2`); a single-page response (no Link) → ONE GET;
      an empty-headers transport → ONE GET (graceful fallback). Add a `next_link_path` unit test
      (rel=next present / absent / base-relative strip).
- [ ] Verify: `rm -rf .mypy_cache && make check` green. Timeout-safety: assert (or reuse the existing
      `test_timeout_preservation_is_inherited` pattern) that `rest_with_headers` inherits the
      client's connect+read timeouts (no new untimed read path).

```bash
git commit -m "feat(genesis): REST issue-comments Link rel=next pagination (headers seam + pager, no duplicate sticky)"
```

---

## 16.3 — `find_open_pr` per_page=100 + Link rel=next pagination

**The gap.** NEW's `find_open_pr` (`client.py:389-415`) issues
`GET /pulls?state=open&head={owner}:{branch}` with NO `per_page` (GitHub default 30) and NO Link loop
(audit "GitHub adapter" §3, lines 81-84). The PoC's `list_open_pulls_for_branch` (OLD `_rest.py:95-106`)
appended `&per_page=100`; tested at OLD `test_rest.py:85`. Severity is cosmetic (a single owner-qualified
head yields 0-or-1 open PR), but a faithful extraction keeps the `per_page=100` contract and reuses the
16.2 pager so the behaviour matches the PoC exactly.

**Layer**: `adapters/github/` ONLY. **Files**: `src/kanbanmate/adapters/github/client.py` (rewrite
`find_open_pr` onto the `_rest` builders + the pager), `tests/adapters/github/test_pagination.py`
(extend) / `tests/adapters/github/test_client.py` (extend the existing PR tests).

- [ ] Rewrite `GithubClient.find_open_pr(head_branch)` to use `_rest.list_open_pulls_for_branch
(self._repo, head_branch)` (the `per_page=100`, owner-qualified path from 16.2) and the SAME
      Link-rel=next loop seam (`self._rest_headers` + `_rest.next_link_path`). Keep the existing
      short-circuit: empty / `"HEAD"` branch → return `None` with NO round-trip (preserve NEW's guard
      at `client.py:405-406`). Resolve the first PR number via `_rest.parse_open_pull_number(page)`
      per page; return on the first hit; `None` when exhausted. The owner-qualified head guard
      (`{owner}:{branch}`) is preserved (fork-safety).
- [ ] `close_pr` / `close_open_pr_for_branch` are UNCHANGED (they already exist in NEW from phase 8 —
      `client.py:417-…`; `close ≠ merge`, remote branch kept). Do NOT touch them.
- [ ] Tests: a fixture with one open PR for the branch → `find_open_pr` returns its number from page 1
      (path asserts `…/pulls?state=open&head={owner}:{branch}&per_page=100`); an empty page-1 with a
      `Link rel=next` to page 2 carrying the PR → follows the link and finds it (proves the pager is
      shared, not duplicated); no open PR → `None`; `""` / `"HEAD"` → `None` with NO GET (assert the
      transport recorded zero calls).
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "feat(genesis): find_open_pr per_page=100 + Link rel=next pagination (reuse the REST pager)"
```

---

## 16.4 — doctor `branch_protection_on`: real REST probe wired from the registry

**The gap.** NEW's `_check_branch_protection` (`cli/doctor.py:268-295`) takes an injectable
`branch_check` that is ALWAYS `None` in production: `app.py:183` calls `doctor_mod.run_doctor()` with NO
args → `run_doctor(branch_check=None)` (`doctor.py:366-446`) → the no-checker branch ALWAYS returns
`("branch protection", True, "skipped — no target repo specified (advisory)")` and NEVER touches GitHub
(audit "CLI command surface" §branch_protection, lines 26-33). The PoC ran a LIVE probe (OLD
`runners.py:459-467`): resolve `target_repo` from the registry, run
`gh api repos/<repo>/branches/main/protection`, parse via `probes.parse_branch_protection_on:59-79`,
emit a WARNING when off (OLD `plan_doctor.py:99-103`). This sub-phase ports the parser + a REST probe
method on the client and WIRES a real `branch_check` from `projects.json` + the GithubClient into the
production `doctor` command, so the probe is live (not a hollow placeholder).

**Layer**: `core/` (the pure parser — zero I/O) · `adapters/github/` (the REST probe method) · `cli/`
(wire the real checker). **Files**:
`src/kanbanmate/core/probes.py` (NEW — the pure `parse_branch_protection_on`),
`tests/core/test_probes.py` (NEW),
`src/kanbanmate/adapters/github/client.py` (add `branch_protection_on(branch="main") -> bool`),
`tests/adapters/github/test_client.py` (extend),
`src/kanbanmate/cli/doctor.py` (a `_resolve_branch_check(...)` helper that builds the real callable),
`src/kanbanmate/cli/app.py` (the `doctor()` command passes the resolved checker),
`tests/cli/test_doctor.py` (extend).

- [ ] Add `core/probes.py::parse_branch_protection_on(payload: object) -> bool` — port OLD
      `probes.py:59-79` but adapt the input to NEW's JSON-decoding client (the PoC parsed a raw
      `gh api` STRING; NEW will pass an already-decoded dict). Accept a decoded `Mapping`/`dict` (or a
      JSON string for back-compat — `json.loads` it if `str`): a dict carrying any of
      `required_status_checks` / `enforce_admins` / `required_pull_request_reviews` → `True`; a
      message-only body (a `message` key WITHOUT any protection field, i.e. the 404 "Branch not
      protected") → `False`; anything else → `False`. PURE, zero I/O (it goes in `core/` so the
      layering guard sees no import with I/O — mirror the PoC's `probes.py` purity).
- [ ] Add `GithubClient.branch_protection_on(self, branch: str = "main") -> bool` — REST
      `GET /repos/{owner}/{repo}/branches/{branch}/protection`, fail-soft: on a `GitHubHTTPError`
      (404 = not protected, or 403/permission) RETURN `False` (the endpoint 404s when protection is
      off — the PoC treated a message-only/404 as "off"); on a 2xx pass the decoded body to
      `core.probes.parse_branch_protection_on`. The request inherits the client's mandatory
      connect+read timeouts. Document the 404→False contract explicitly.
- [ ] Wire the real checker in `cli/doctor.py`: add a `_resolve_branch_check(root: Path) ->
BranchProtectionCheck | None` that (a) loads `projects.json` via the registry helper
      (`cli/init.py::_load_registry` / `_projects_path`) and resolves the FIRST registered project's
      `repo` (the PoC's `_first_registered_repo`); (b) on no registered repo → return `None` (the
      existing advisory skip — UNCHANGED for the no-config case); (c) otherwise build a
      `GithubClient(load_token(), repo=<repo>)` and return a zero-arg lambda
      `() -> (client.branch_protection_on("main"), f"{repo}@main")` matching the
      `BranchProtectionCheck = Callable[[], tuple[bool, str]]` contract. Keep it FAIL-SOFT: a missing
      token / unreachable API must not crash doctor — `_check_branch_protection` already wraps the
      callable in `try/except` and downgrades to a skip-with-error WARN (`doctor.py:284-287`).
- [ ] `cli/app.py::doctor()`: pass the resolved checker:
      `code = doctor_mod.run_doctor(root=_DEFAULT_ROOT, branch_check=doctor_mod._resolve_branch_check
(_DEFAULT_ROOT))` (or expose a public `resolve_branch_check`). The check STAYS ADVISORY
      (`_check_branch_protection` always returns `True` for the overall pass/fail) — restoring the
      LIVE probe, not making it blocking, exactly matches the PoC WARNING-only semantics.
- [ ] Tests: `tests/core/test_probes.py` — `parse_branch_protection_on` returns `True` for a body
      with `required_status_checks` / `enforce_admins` / `required_pull_request_reviews`, `False` for a
      message-only 404 body, `False` for `{}` / a non-dict / invalid JSON string. `test_client.py` —
      `branch_protection_on` returns `True` on a fixture protection body, `False` on a `GitHubHTTPError
(404)` (assert no raise). `test_doctor.py` — `_resolve_branch_check` returns `None` when the
      registry is empty (advisory skip preserved), and returns a callable that yields
      `(True, "...")` when a registered repo + a fake client report protection; the production
      `doctor()` path now passes a non-`None` checker (assert via the wired call, e.g. a monkeypatched
      `_resolve_branch_check` is invoked).
- [ ] Verify: `rm -rf .mypy_cache && make check` green; layering guard sees `core/probes.py` import
      nothing with I/O (the REST call lives in the adapter; the CLI does the wiring).

```bash
git commit -m "feat(genesis): live branch-protection doctor probe wired from registry (port parse_branch_protection_on)"
```

---

## 16.5 — `sessions` command: TSV format + the `stopped` bucket

**The gap.** The PoC `run_sessions` (OLD `runners.py:99-110`) renders a TSV
`#<issue>\t<tmux>\t<flag>\t<status>` where `flag = live | DEAD | stopped`, iterating EVERY persisted
ticket (`_known_issues` = every `state/<n>.json` regardless of status; OLD `reports.build_sessions_report
:42-59`). NEW's `render_sessions` (`cli/sessions.py:107-127`) renders a prose table
(`#N name alive/gone DEAD (reaper candidate)`) and only ever shows running + DEAD rows: it iterates
`store.list_running()` (`sessions.py:76`), whose fs adapter HARD-FILTERS to `status == RUNNING`
(`adapters/store/fs_store.py:200-201`), so the THIRD `stopped` bucket (has state, not running, session
gone — an idle/finished-but-not-torn-down ticket) is STRUCTURALLY UNREACHABLE (audit "CLI command
surface" §sessions, lines 42-51). This sub-phase restores BOTH the PoC's TSV rendering AND the
`stopped` bucket by iterating all known persisted tickets and computing the three-way flag.

> **Scope decision (faithful + minimal).** The PoC's `stopped` bucket only appears for tickets whose
> state was kept-and-marked-idle on session-end. NEW's `kanban-session-end` PURGES state via
> `release_slot` (the documented §8.1.f flow). To restore the bucket WITHOUT reverting the purge
> behaviour (which is a separate, intentional design choice), this sub-phase makes the SESSIONS REPORT
> iterate ALL known persisted state files (the PoC's `_known_issues`), not just `list_running()`, and
> classifies each row `live | DEAD | stopped`. A ticket that persists with a non-running status and a
> gone session renders `stopped`. This is a pure read-model change (no state-lifecycle change), so it
> is faithful to the PoC report and orthogonal to the purge-on-session-end design.

**Layer**: `cli/` (the read-model report) + a tiny `ports/store` addition if needed (a method to list
ALL persisted states, not just running). **Files**:
`src/kanbanmate/cli/sessions.py` (add the `stopped` bucket + TSV rendering),
`src/kanbanmate/ports/store.py` (add `list_all() -> list[TicketState]` to the `StateStore` Protocol —
the PoC `_known_issues` analogue; pure),
`src/kanbanmate/adapters/store/fs_store.py` (implement `list_all` — iterate every `state/<n>.json`
regardless of status, NOT the RUNNING-only filter),
`tests/cli/test_status.py` (the existing sessions tests live here — extend) or a new
`tests/cli/test_sessions.py`, `tests/adapters/test_fs_store.py` (extend for `list_all`).

- [ ] Add `StateStore.list_all(self) -> list[TicketState]` to `ports/store.py` (English docstring:
      "every persisted ticket regardless of status — the PoC `_known_issues` analogue, distinct from
      `list_running` which returns only running tickets"). Implement on the fs adapter by iterating
      every `state/<n>.json` and loading each `TicketState` (mirror `list_running` but DROP the
      `status == RUNNING` filter). This resolves the port/impl contradiction the audit flagged
      (`store.py:138-146` docstring vs the RUNNING-only impl) by giving the report the all-states
      source it needs WITHOUT changing `list_running`'s running-only contract.
- [ ] Extend `build_sessions` (or add a `build_sessions_all`) to iterate `store.list_all()` and
      compute the THREE-way flag per the PoC (`reports.build_sessions_report:42-59`):
  - `live` — `agent_sessions.is_alive(name)` is `True`.
  - `DEAD` — `status == RUNNING and not alive` (the reaper candidate; NEW's existing `dead`).
  - `stopped` — has state, NOT running, and the session is gone (`status != RUNNING and not alive`).
    Widen `SessionRow` with a `stopped: bool` flag (or a single `flag: Literal["live","DEAD",
"stopped"]`). Keep issue-number-ascending ordering.
- [ ] Rewrite `render_sessions` to emit the PoC TSV: one line per row
      `f"#{row.issue_number}\t{row.session_name}\t{flag}\t{row.status}"` where
      `flag = "live" if row.alive else ("DEAD" if row.dead else "stopped")` (port OLD `runners.py:108`
      EXACTLY). Keep an explicit empty-report line (the PoC printed nothing for an empty board; NEW may
      keep a "(none)" sentinel — preserve whichever the existing test asserts, but the per-row format
      MUST be the TSV). Drop the prose `alive/gone DEAD (reaper candidate)` rendering.
- [ ] Tests: a running ticket with a live session → `live`; a running ticket with a gone session →
      `DEAD`; a NON-running persisted ticket with a gone session → `stopped` (the restored bucket — the
      PoC parity assertion); the rendered line is the exact TSV `#N\ttmux\tflag\tstatus`; issue-number
      ascending; `list_all` returns running AND non-running states (extend `test_fs_store.py`:
      save a running + an idle/non-running record → `list_all` returns both, `list_running` returns
      only the running one).
- [ ] Verify: `rm -rf .mypy_cache && make check` green; layering guard sees the new port method/impl
      stay within `ports/`+`adapters/store/`.

```bash
git commit -m "feat(genesis): sessions report restores stopped bucket + TSV format (port build_sessions_report)"
```

---

## 16.6 — Port `issue_state` (GraphQL open/closed probe; the #13 dependency-gate fallback)

**The gap.** NEW dropped the PoC's per-dependency LIVE state query when it moved the `Depends on #N`
gate to the board snapshot. The phase-17 **#13** operator decision (2026-06-05) restores it as a HYBRID
fallback: the snapshot stays primary; this query resolves ONLY the deps the snapshot cannot decide
(absent from the board). The PoC `issue_state` (OLD `client.py:182-189`) drove a GraphQL query (OLD
`_queries.issue_state`) fetching `issue.state` (OPEN/CLOSED), parsed (OLD `_parsers.parse_issue_closed`)
to a bool. So a closed-but-off-board dependency is satisfiable WITHOUT the per-tick N queries of the
common all-on-board case.

**Layer**: `adapters/github/` (GraphQL builder + parser + client method) + the board-read port seam.
**Files**: `src/kanbanmate/adapters/github/_queries.py` (add `issue_state`),
`src/kanbanmate/adapters/github/_parsers.py` (add `parse_issue_closed`),
`src/kanbanmate/adapters/github/client.py` (add `issue_state(...)`),
`src/kanbanmate/ports/board.py` (add `issue_state` to the SAME board-read Protocol `app/tick` already
calls for `snapshot`, so the #13 fallback can reach it through the port — no layering break),
`tests/adapters/github/test_client.py` (extend) + `tests/adapters/github/fixtures/`.

- [ ] Add `_queries.issue_state(owner: str, name: str, number: int) -> dict[str, Any]` — port OLD
      `_queries.issue_state` VERBATIM-IN-SPIRIT: `repository(owner, name) { issue(number) { state } }`,
      returning `{"query": query, "variables": {"owner": owner, "name": name, "number": number}}`. Match
      NEW's existing `_queries` builder style (triple-quoted query + `variables` dict). Google-style
      docstring citing the source.
- [ ] Add `_parsers.parse_issue_closed(data: dict[str, Any]) -> bool` — port OLD `parse_issue_closed`:
      `raise_for_errors(data)` FIRST (a non-empty `errors` array raises `GraphQLError`, like every NEW
      parser); drill `data["data"]["repository"]["issue"]` defensively (each level `or {}`); return
      `str(issue.get("state") or "").upper() == "CLOSED"`. A missing/empty `state` → `False`
      (open/unknown — conservative: an undecidable issue is NOT treated as done). Faithful to the PoC.
- [ ] Add `GithubClient.issue_state(self, number: int) -> bool` (True iff CLOSED) — repo-less (NEW's
      client carries `self._repo`): split `self._repo` into `owner, name`, call
      `self._graphql(_queries.issue_state(owner, name, number))`, return
      `_parsers.parse_issue_closed(data)`. The request inherits the client's mandatory connect+read
      timeouts. Document that the phase-17 #13 dependency-gate fallback is the consumer.
- [ ] Add `issue_state(self, number: int) -> bool` to the board-read Protocol in `ports/board.py` (the
      seam `app/tick` already uses for `snapshot`; the `GithubClient` board adapter satisfies it).
      English docstring: "True iff the issue is CLOSED — the live fallback for an off-board dependency
      in the #13 dependency gate." If `app/tick` reaches the board reader by a different handle than the
      writer, wire `issue_state` onto that read seam (NOT `board_writer`).
- [ ] Tests (`tests/adapters/github/test_client.py` + a fixture): inject a fake GraphQL transport — a
      `state: CLOSED` response → `issue_state(N) is True`; a `state: OPEN` response → `False`; a missing
      `state` → `False`; an `errors`-bearing response → raises `GraphQLError`. Add a `parse_issue_closed`
      direct unit test on a raw dict (the CLOSED/OPEN/missing matrix + None-guards).
- [ ] Verify: `rm -rf .mypy_cache && make check` green; layering guard sees the new code stay in
      `adapters/github/` (the Protocol addition lives in `ports/`, no upward import).

```bash
git commit -m "feat(genesis): port GitHub issue_state open/closed probe (the #13 dependency-gate fallback seam)"
```

---

### Phase 16 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`). Run `rm -rf .mypy_cache` FIRST (the incremental
   cache has masked real errors in this repo).
2. `make test` — all pass (check the summary line; any ERROR = collection crash → fix imports first).
3. `make check` — clean (lint + test + module-size guards; the new `_rest.py` / `core/probes.py` stay
   well under the ~800 LOC soft cap).
4. Residual-import / parity greps (all type-filtered):
   - `rg --type py "issue_context" src` → matches `_queries.py`, `_parsers.py`, `client.py` (the
     restored capability), NEVER an org-webhook builder.
   - `rg --type py "next_link_path|per_page" src` → present in `adapters/github/_rest.py` +
     `client.py` (the restored REST pager), and NOWHERE re-introduces the pivot-removed org-webhook
     builders (`rg --type py "ensure_org_webhook|create_org_webhook|orgs/.*/hooks" src` → ZERO).
   - `rg --type py "branches/.*protection|branch_protection_on|parse_branch_protection_on" src` →
     present in `client.py` + `core/probes.py` + `cli/doctor.py` (the live probe wired), and
     `run_doctor()` in `app.py` is NO LONGER called with a bare no-arg signature (the production
     `doctor` passes a resolved `branch_check`).
   - `rg --type py "stopped" src/kanbanmate/cli/sessions.py` → the restored third bucket is present.
   - `rg --type py "issue_state|parse_issue_closed" src` → present in `_queries.py` + `_parsers.py` +
     `client.py` + `ports/board.py` (the #13 fallback seam restored — 16.6).
5. Parity check — exercised in tests:
   - `issue_state` returns `True` for a CLOSED issue, `False` for OPEN / missing-state, and raises
     `GraphQLError` on a GraphQL-errors response; it is exposed on the board-read port for the phase-17
     #13 fallback (16.6).
   - `issue_context` returns `{body, comments (≤50), linked_issue_body}` and is fail-loud on GraphQL
     errors (16.1).
   - a sticky comment on REST page 2 is FOUND (no duplicate created) via the Link rel=next loop, and
     the second GET path is `…/comments?per_page=100&page=2` (16.2).
   - `find_open_pr` issues `…&per_page=100` and follows `rel=next` (16.3).
   - the production `doctor` runs a LIVE branch-protection probe resolved from `projects.json` (not the
     hollow advisory placeholder), staying advisory/WARNING-only (16.4).
   - `kanban sessions` renders the TSV `#N\ttmux\t<live|DEAD|stopped>\t<status>` and the `stopped`
     bucket is reachable for a non-running persisted ticket whose session is gone (16.5).
6. Timeout-safety check: every new urllib path (the headers-bearing REST seam in 16.2, the
   branch-protection GET in 16.4) inherits the client's connect+read timeouts — no new untimed read
   path (asserted in `tests/adapters/github/`).
7. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 16 gate — GitHub ops + CLI/doctor parity (issue_context, issue_state, pagination, branch-protection, sessions)"
```
