# Phase 8 — PoC parity port (rich sticky signaling + full Cancel teardown)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §8.1 (sticky comments — the rich two-zone subsystem), §8.2 (Cancel teardown +
> resume), §11 (port-from-PoC; the PoC is the source of truth).
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`):
> `<OLD>/engine/stage_comment.py`
> (8.1 render/upsert) · `<OLD>/runner.py` `_finalize_left_stage` (✅-on-advance) ·
> `<OLD>/state.py` (`set_item_column`/`get_item_column` + the `advances/`
> `record_agent_advance`/`recent_agent_advance`/`clear_agent_advance` breadcrumb) ·
> `<OLD>/cli/session_end.py::finalize_session` (⚠️-on-session-end — the ⚠️ LOGIC to port; the
> `kanban-session-end` shim is only a thin bash entry) ·
> `<OLD>/../bin/kanban-move` (the breadcrumb-writing shim) — **NB the `bin/` dir is the kanban-skill
> root, a SIBLING of the `kanbanmate/` package, NOT under `<OLD>`** (i.e.
> `.../skills/kanban/bin/`, not `.../skills/kanban/kanbanmate/bin/`); it writes the advance breadcrumb
> SYNCHRONOUSLY before the agent exits ·
> `<OLD>/engine/teardown.py` (8.2). NEW root: `/Users/izno/dev/KanbanMate/src/kanbanmate/`.

**Goal**: bring NEW to behavioural parity with the last PoC on the two features that shipped after
the first extraction snapshot: (8.1) the **rich, two-zone stage-comment subsystem** with the **FULL
status lifecycle 🟡 → ✅/⚠️/⛔ → ❌** (replacing NEW's one-line marker writer) and (8.2) the **full
Cancel teardown** (`--force` worktree removal, local `branch -D`, close the open PR but KEEP the
remote branch, flip open stage stickies to ❌, recap). Both fail-soft; teardown is
dispatcher-mechanical (no agent → the deny-list does not apply).

**Signaling lifecycle (operator decision — FULL parity, NOT a subset).** Every status the PoC
produces is reproduced in NEW, with all FIVE producers wired:

| Status      | Badge | English label | Producer (NEW)                                                               |
| ----------- | ----- | ------------- | ---------------------------------------------------------------------------- |
| running     | 🟡    | `in progress` | `LaunchAction` step 5 (8.1.c)                                                |
| done        | ✅    | `done`        | the daemon tick, on an accepted forward move OUT of a stickied stage (8.1.e) |
| interrupted | ⚠️    | `interrupted` | `kanban session-end`, when NO advance breadcrumb exists (8.1.f)              |
| blocked     | ⛔    | `blocked`     | the in-daemon reaper, on a stale agent (8.1.c)                               |
| cancelled   | ❌    | `cancelled`   | `TeardownAction`, flipping open stickies (8.2.c)                             |

> The ✅/⚠️ pair was previously flagged "defer-or-thread" in the old 8.1.c note. **Operator
> decision: thread it — full parity.** OLD's `TicketState`-equivalent carried the per-item column +
> an `advances/` breadcrumb AND the metadata `header_from_state` renders (session_uuid / profile /
> permission_mode / started_at / worktree); NEW's `TicketState` dropped ALL of these. 8.1.d
> re-threads them: it **WIDENS `TicketState`** to carry the launch `stage` PLUS the header
> metadata inputs (`profile` / `mode` / `started` / `worktree`), persisted by `LaunchAction` at
> launch, and adds the fs-store advance breadcrumb. 8.1.e adds the daemon's ✅-on-advance finalize
> (which PRE-READS the LEFT ticket's now-metadata-bearing `TicketState` BEFORE `LaunchAction`
> overwrites the slot), and 8.1.f adds the ⚠️-on-session-end finalize (from the loaded
> `TicketState`). With the widened state, NEW's ✅/⚠️ stickies reproduce OLD's metadata bullets
> (full parity) — not a bare badge. The breadcrumb is the proof, written SYNCHRONOUSLY before the
> agent exits — exactly OLD's race-closing design.

---

## Gate

Phases 1–7 complete; PR #1 open + CI green; branch `feat/genesis`; `make check` green at start.
Re-sync confirmed (DESIGN §11 pre-implementation gate): the two PoC features are present in
`.claude/skills/kanban/` and read for this port.

---

## 8.1 — Rich two-zone stage-comment subsystem (replace the one-line sticky)

> **The gap.** NEW's `src/kanbanmate/bin/kanban_comment.py` ships a _one-line_ sticky writer:
> `marker(step)` → `<!-- kanban:step=<key> -->`, `render_sticky` (marker + body), `upsert_sticky`
> (list → find marker → edit-or-create). The PoC long since superseded this with a **two-zone**
> subsystem (`engine/stage_comment.py`): a HEADER zone owned by producers-with-proof (dispatcher
> 🟡 running / session-end ⚠️ interrupted / reaper ⛔ blocked / teardown ❌ cancelled) and a BODY
> zone (`**Progression**`) the agent appends to via `kanban-progress`. A header update PRESERVES
> the body and vice-versa. NEW currently has NO header-zone concept, no status badges, and no
> producer/agent split — so a reaped/cancelled ticket leaves a stale 🟡-less one-line note.

### 8.1.a — Pure `core/stage_comment.py` (marker · render · split · compose)

**Layer**: `core/` — PURE, zero I/O (DESIGN §3.2). This is the port target for every PoC function
in `engine/stage_comment.py` that does NOT touch GitHub.

**Files**: `src/kanbanmate/core/stage_comment.py` (new), `tests/core/test_stage_comment.py` (new),
`tests/core/__init__.py` (exists).

- [ ] Port the PURE pieces verbatim-in-spirit from the PoC `engine/stage_comment.py` (adapt the
      marker to NEW's existing scheme so existing one-line stickies are NOT orphaned — see note):
  - `StageStatus = Literal["running", "done", "interrupted", "blocked", "cancelled"]`.
  - `BADGES` / `LABELS` — **ENGLISH user-facing badge labels (operator decision, confirmed).** NEW's
    English-only artifact rule (DESIGN/CLAUDE.md) governs the _user-facing GitHub sticky comments_,
    not just internal docs: the PoC labels are FRENCH and are NOT carried over. The exact, mandatory
    badge→label table baked into the sticky header (emoji + English label):
    `running 🟡 "in progress"`, `done ✅ "done"`, `interrupted ⚠️ "interrupted"`,
    `blocked ⛔ "blocked"`, `cancelled ❌ "cancelled"`. No French strings reach a GitHub comment.
    `_FINISHED_PREFIX` for the terminal ts line.
  - `@dataclass(frozen=True) HeaderInfo` (stage, status, session, profile, mode, started, finished,
    worktree, log_hint) — frozen, English docstrings.
  - `marker(stage) -> str`. **Keep NEW's existing marker prefix** `<!-- kanban:step=<stage> -->`
    (NOT the PoC's `<!-- kanbanmate-stage:<stage> -->`) so stickies created by the shipped one-line
    writer in 5.1 are still located after this upgrade. Document the divergence from the PoC.
  - `fmt_timestamp(epoch) -> str` (`""` on falsy), `render_header(info) -> str` (marker first line),
    `find_stage_comment_id(comments, stage) -> int | None` (exact marker match — returns the
    INTEGER comment id, matching NEW's `CommentRef.comment_id: int`; OLD returned a stringified id
    because its REST client carried string ids, NEW's does not), `split_sticky(body)
-> tuple[str, list[str]]` (split at `**Progress**` heading), `compose(header, progress) -> str`,
    `_stamp(line, *, now) -> str`.
  - `header_from_state(state, issue, stage, status, *, finished="") -> HeaderInfo` — the
    state→header builder. **Adapt the state shape to NEW**: PoC reads a raw `dict`; NEW persists a
    typed `TicketState` (no `session_uuid`/`profile`/`permission_mode`/`started_at`/`worktree`
    fields today). Accept a `Mapping[str, object]` so the adapter can pass a superset dict, and
    default every missing field to `""` (the header degrades gracefully when a field is absent).
  - Use `**Progress**` as the BODY heading constant (English; PoC uses `**Progression**`).
- [ ] `find_stage_comment_id` and the comment list type: in `core/` keep it I/O-free by typing the
      input as `list[CommentLike]` where `CommentLike` is a tiny `Protocol`/`TypedDict` with
      `id: int` and `body: str` — do NOT import the adapter `CommentRef` into `core/`
      (downward-import guard). The adapter side (8.1.b) maps NEW's `CommentRef.comment_id (int)` →
      `CommentLike.id`, so the integer id round-trips into `update_comment(comment_id: int, …)`.
- [ ] `tests/core/test_stage_comment.py`: pure unit tests, NO I/O — assert the EXACT English
      badge/label table (`running→"in progress"`, `done→"done"`, `interrupted→"interrupted"`,
      `blocked→"blocked"`, `cancelled→"cancelled"`) and that NO French label string (`en cours`,
      `terminé`, `interrompu`, `bloqué`, `annulé`) appears in any rendered header (English-only
      artifact guard); `render_header` puts the marker first and appends the finished line only for
      terminal statuses;
      `split_sticky`/`compose` round-trip (header-only, header+progress, no-heading body);
      `find_stage_comment_id` exact match (`"PR Ready"` ≠ `"PR"`); `header_from_state` fills from a
      mapping and degrades blanks; `fmt_timestamp("")==""`.
- [ ] Verify: `make test` pass; `make lint` (mypy strict on the new module) zero errors; the
      layering guard sees `core/stage_comment.py` import nothing with I/O.

```bash
git commit -m "feat(genesis): pure two-zone stage-comment core (marker/render/split/compose, ported from PoC)"
```

---

### 8.1.b — Adapter/app upsert via the GitHub port (replace `upsert_sticky`)

**The gap.** The PoC `upsert_stage_comment(gh, repo, issue, stage, *, header, append, now)` is the
single I/O orchestrator: list → find → split → swap-header-and/or-append → PATCH, with create-or-
no-op rules and a fail-soft wrapper (spec §10). NEW's `upsert_sticky` is the thin one-line analogue.
NEW's `GithubClient` already exposes `list_issue_comments(issue) -> list[CommentRef]`,
`update_comment(comment_id, body)`, and `comment(issue, body)` (repo is hidden — single-repo
client), but the `BoardWriter` port (`move_card` + `comment`) does NOT expose comment-read/edit, so
the app-layer producers (8.2 teardown / reaper finalize) cannot upsert through a port today.

**Files**: `src/kanbanmate/ports/board.py` (extend), `src/kanbanmate/adapters/github/client.py`
(no new method — it already satisfies the extended port), `src/kanbanmate/bin/kanban_comment.py`
(rewrite the sticky path onto the core helpers), `src/kanbanmate/app/stage_signal.py` (new — the
app-layer upsert orchestrator), `tests/ports/` (new — create with `tests/ports/__init__.py`; or
fold the port-conformance assertion into `tests/app/test_stage_signal.py` instead) +
`tests/app/test_stage_signal.py` (new), `tests/bin/test_kanban_comment.py` (extend).

- [ ] Extend the `BoardWriter` Protocol with the two read/edit methods the producers need (the
      concrete `GithubClient` ALREADY implements them, so this is a no-cost port widening):
      `list_issue_comments(self, issue_number: int) -> list[CommentRef]` and
      `update_comment(self, comment_id: int, body: str) -> None`. Keep `CommentRef` imported from
      the adapter types in `ports/` (ports may name adapter value objects; only `core/` may not).
- [ ] Add `src/kanbanmate/app/stage_signal.py` — the I/O orchestrator (port of PoC
      `upsert_stage_comment`, adapted to NEW's repo-less client):

      ```python
      def upsert_stage_comment(
          writer: BoardWriter,
          issue: int,
          stage: str,
          *,
          header: HeaderInfo | None = None,
          append: str | None = None,
          now: float | None = None,
      ) -> int | None:
          """Create-or-update the ``stage`` sticky on ``issue`` (DESIGN §8.1; port of the PoC).

          FOUND: split body, swap header (if given) else keep, append a stamped line (if given),
          PATCH. ABSENT + running-header-or-append: CREATE. ABSENT + finalize-only (terminal
          header, no append): SILENT NO-OP (nothing to finalize). FAIL-SOFT: any GitHub error is
          logged once and swallowed — signaling never breaks dispatch/teardown/reap (DESIGN §8.1).
          """
      ```
      Mirror the PoC control flow exactly: `find_stage_comment_id` → on hit read the body off the
      same listing (one `list_issue_comments` call), `split_sticky`, `render_header(header)` or keep
      `hdr`, append `_stamp(append, now)`, `compose`, `writer.update_comment(cid, body)`; on miss
      apply the create/no-op rules; wrap the whole thing in `try/except Exception` → log to the
      module logger + return `None` (NOT a raise — DESIGN §8.1 fail-soft). The `repo` arg is DROPPED
      (NEW's client is single-repo). **Create path (L6): on CREATE, NEW RETURNS `None`** — it does
      NOT re-locate the just-created comment id with a second `list_issue_comments` call (OLD did a
      best-effort post-create re-locate). Returning `None` after a successful create is acceptable
      per fail-soft: every caller treats the id as best-effort, and the NEXT upsert re-finds the
      sticky by its marker. Drop OLD's post-create re-locate round-trip.

- [ ] Rewrite `kanban_comment.py`'s sticky path onto the new core + app: `--sticky <STEP>` posts a
      RUNNING-header sticky when absent and an `--append`-style progress line when given a body;
      keep the existing `--append` free-form mode unchanged; keep the leaf entrypoint's fail-clean
      exit codes (2 usage / 1 other). Delete the now-superseded local `marker`/`render_sticky`/
      `find_marked_comment`/`upsert_sticky` (residual-import grep them in `src/` AND `tests/`).
- [ ] `kanban_progress.py`: point its sticky append at `app/stage_signal.upsert_stage_comment(...,
append=line)` with `header=None` (PoC `kanban-progress` semantics: preserve the dispatcher's
      running header, append a stamped line, create-with-minimal-running-header only if absent).
- [ ] Tests: `tests/app/test_stage_signal.py` — fake `BoardWriter` recording calls; assert the
      found path PATCHes (one list call, header swapped, body preserved); absent+running → create;
      absent+terminal-only → no-op (no create); a GitHub exception → returns `None`, no raise.
      Extend `tests/bin/test_kanban_comment.py` for the rewired sticky path. Add a `BoardWriter`
      conformance assertion (the concrete client satisfies the widened port).
- [ ] Verify: `make check` green. Residual-import grep: `rg --type py "upsert_sticky|render_sticky"
src tests` → zero matches.

```bash
git commit -m "feat(genesis): app-layer stage-comment upsert via widened BoardWriter port (rich sticky)"
```

---

### 8.1.d — Widen `TicketState` (launch stage + header metadata) + add the advance breadcrumb (re-thread NEW's dropped context)

> **Execution order (audit fix — 2026-06-05).** This sub-phase is intentionally placed **BEFORE
> 8.1.c**: the reaper ⛔ producer in 8.1.c reads `TicketState.stage` and calls `header_from_state(...)`,
> both introduced HERE — so the state widening + `header_from_state` + breadcrumb MUST land first or
> 8.1.c cannot pass its own `make check` gate. Execution sequence: 8.1.a → 8.1.b → **8.1.d → 8.1.c** →
> 8.1.e → 8.1.f.

**The gap.** OLD threaded THREE things the finalizers need: a per-item **current column**
(`Store.set_item_column`/`get_item_column`, the `columns/` marker), an **advance breadcrumb**
(`Store.record_agent_advance`/`recent_agent_advance`/`clear_agent_advance`, the `advances/` marker
with a TTL, written SYNCHRONOUSLY by `kanban-move` before the agent exits — `state.py`), AND the
**header metadata** `header_from_state` reads off the persisted state to render the terminal
sticky's bullets (`session_uuid` / `profile` / `permission_mode` / `started_at` / `worktree` —
`engine/stage_comment.py::header_from_state`). NEW's `TicketState` (`ports/store.py`) carries only
`issue_number / item_id / session_id / status / heartbeat` — **no stage, no header metadata** — and
the fs store (`adapters/store/fs_store.py`) has no `advances/` concept. Without these, the ✅ (8.1.e)
and ⚠️ (8.1.f) producers cannot resolve the stage to finalize, cannot distinguish "advanced" from
"interrupted", and would render bare badges with no metadata bullets. This sub-phase re-threads all
three (FULL parity), faithful to OLD's race-closing design: **the breadcrumb is the proof, written
before the agent exits**.

**Layer**: `ports/` (extend `TicketState` + `StateStore` Protocol — pure) · `adapters/store/` (fs
breadcrumb, mirrors the PoC `advances/` impl). **Files**: `src/kanbanmate/ports/store.py` (extend),
`src/kanbanmate/adapters/store/fs_store.py` (add breadcrumb methods), `src/kanbanmate/app/actions.py`
(`LaunchAction` persists the widened state), `tests/ports/` (new — create with
`tests/ports/__init__.py`, or fold the round-trip asserts into the fs-store test below),
`tests/adapters/test_fs_store.py` (extend — the test lives at `tests/adapters/test_fs_store.py`, NOT
`tests/adapters/store/test_fs_store.py`), `tests/app/test_actions.py` (extend).

- [ ] **WIDEN `TicketState`** (the FULL-parity decision) — extend the frozen dataclass with the
      launch stage AND the `header_from_state` metadata inputs, every new field defaulted so existing
      / old-format on-disk state still loads (the fs adapter's `TicketState(**data)` tolerates the
      new fields via the defaults; absent-field load must still succeed — assert it). English
      docstring on each new field:
  - `stage: str = ""` — the column key the launch entered (the stage the finalizers finalize).
  - `profile: str = ""` — the permission profile (`header_from_state`'s `profile` bullet).
  - `mode: str = ""` — the Claude permission mode (`header_from_state`'s `mode` bullet).
  - `started: float = 0.0` — the launch wall-clock epoch (`header_from_state` formats it via
    `fmt_timestamp` into the `started` bullet). (`session_id` already on `TicketState` supplies the
    session bullet; OLD's `session_uuid` maps to it.)
  - `worktree: str = ""` — the worktree path (`header_from_state` shows `Path(worktree).name`).
    NEW persists the stage + metadata IN `TicketState` (no separate `columns/` marker needed — the
    daemon already keeps the diff baseline `columns_by_item` in `PersistedState`; the per-ticket
    `stage`/metadata is what session-end (8.1.f, which has only the issue number) and the reaper
    (8.1.c) must read off disk to render the terminal header).
- [ ] Add `core/stage_comment.py::header_from_state` (8.1.a) an overload/adapter that accepts a
      `TicketState` (or a `Mapping` superset built from it) and maps its fields onto `HeaderInfo`
      (`session ← session_id`, `profile ← profile`, `mode ← mode`, `started ← fmt_timestamp(started)`,
      `worktree ← Path(worktree).name`). With the widened state every producer (launch 🟡 in 8.1.c,
      reaper ⛔ here, ✅ in 8.1.e, ⚠️ in 8.1.f) renders the SAME metadata bullets OLD did.
- [ ] Add the advance-breadcrumb methods to the `StateStore` Protocol + the fs adapter, ported from
      the PoC `state.py` but **RE-KEYED**: OLD keyed the breadcrumb by the **content node id**
      (`record_agent_advance(item, …)` / `_advance_path(item)`; `kanban-move` wrote it by
      content_node_id and `session_end` read it by content_node_id). NEW keys everything by **issue
      number** — so this is a deliberate divergence from OLD, NOT a verbatim port. The marker file
      is `<root>/advances/<issue>`:
  - `record_agent_advance(self, issue_number: int, *, now: float) -> None` — write
    `<root>/advances/<issue>` = `{"ts": now}`. Written SYNCHRONOUSLY before the agent exits (the
    NEW equivalent of OLD's `kanban-move`; the agent helper that lands the breadcrumb is wired in
    8.1.e). Document that this closes the fin/mort race exactly as the PoC does.
  - `recent_agent_advance(self, issue_number: int, *, now: float) -> bool` — `True` iff the
    breadcrumb exists and `now - ts <= _ADVANCE_TTL` (port the PoC's `_ADVANCE_TTL = 300.0`). NB
    `_ADVANCE_TTL` (300 s — advance-breadcrumb recency) is a DISTINCT knob from `HEARTBEAT_TTL`
    (1800 s — agent-liveness reap window, DESIGN §8.3); do not conflate the two TTLs.
  - `clear_agent_advance(self, issue_number: int) -> None` — unlink, no-op if absent (consumed by
    session-end). Mirror the PoC's `FileNotFoundError`-swallow.
  - `release_slot` must ALSO purge the breadcrumb (mirror the PoC's teardown purge of `advances/` —
    a cancelled ticket leaves no stale breadcrumb). Add `<root>/advances/<issue>` to the unlink set.
    Make the purge **unlink-if-exists / no-raise** (idempotent): on a clean exit, 8.1.f's
    `clear_agent_advance` already removed the breadcrumb, so the subsequent `release_slot` purge must
    no-op silently (swallow `FileNotFoundError`) — it is called on BOTH the cancel path and the
    clean-exit path.
- [ ] **Breadcrumb-keying INVARIANT (load-bearing — Fix 5).** Because the breadcrumb is the
      present/absent discriminator for the ✅/⚠️ split, the WRITER and the READERS must use the SAME
      key, and that key is the **issue number** — never a content node id. Specifically: the agent
      helper (8.1.e) MUST call `store.record_agent_advance(issue, …)`, and session-end (8.1.f) MUST
      call `store.recent_agent_advance(issue, …)` / `store.clear_agent_advance(issue)` with the
      identical issue key. A mismatch (one side keying by issue, the other by node id) would make the
      breadcrumb always look "absent" and finalize ⚠️ even after a clean advance. State this
      invariant in the docstrings of all three methods.
- [ ] `LaunchAction.execute` step 4: persist the WIDENED `TicketState` — set `stage=self.ticket`'s
      launch column key (`column_key`/`to_column`, the same value 8.1.c passes as the running
      header's `stage`), plus `profile=deps.profile`, `mode=<the materialised permission mode>`,
      `started=now`, `worktree=str(worktree)`. Single source of truth: the same launch column key
      feeds the 🟡 header AND the persisted stage, and the same metadata feeds the 🟡 header AND the
      persisted state — so the finalizers (✅/⚠️/⛔) reload the identical stage + metadata and render
      bullet-for-bullet identical terminal headers.
- [ ] Tests: a saved-then-loaded `TicketState` round-trips the new `stage` + metadata fields; an
      OLD-shaped state file WITHOUT the new fields still loads (defaults applied); `record_agent_advance`
      then `recent_agent_advance` is `True` within TTL and `False` past it; `clear_agent_advance`
      removes it (no-op when absent); `release_slot` purges the breadcrumb; `LaunchAction` saves the
      launch stage + the profile/mode/started/worktree metadata; the breadcrumb writer/readers all key
      by issue number (invariant above).
- [ ] Verify: `make check` green; layering guard sees the new fields/methods stay within
      `ports/`+`adapters/store/` (no upward import).

```bash
git commit -m "feat(genesis): widen TicketState (launch stage + header metadata) + fs-store advance breadcrumb (re-thread PoC context)"
```

---

### 8.1.c — Wire producers to the rich header (launch 🟡 · reaper ⛔)

**The gap.** With the rich subsystem in place, the producers must post the _header_ (the PoC's
"status posted by a producer with proof", spec §6/§7), not the current free-text comments.
`LaunchAction.execute` (actions.py step 5) posts `"agent launched for #…"`; the reaper
(`app/tick.py::_reap_stale_agents`) posts a `BlockAction` free-text comment. Both should write a
stage sticky header.

**Files**: `src/kanbanmate/app/actions.py` (`LaunchAction` step 5), `src/kanbanmate/app/tick.py`
(`_reap_stale_agents`), `tests/app/test_actions.py`, `tests/app/test_tick.py` (extend).

- [ ] `LaunchAction.execute` step 5: replace the free-text "started" comment with
      `app.stage_signal.upsert_stage_comment(deps.board_writer, issue, stage=<column key>,
header=HeaderInfo(stage=…, status="running", session=session_id, profile=deps.profile,
started=fmt_timestamp(now), worktree=Path(worktree).name, log_hint=f"kanban logs {issue}"))`.
      The launch ticket carries `column_key`; use it as the stage. Keep it fail-soft (the upsert
      already swallows).
- [ ] `_reap_stale_agents`: after the kill/teardown, flip the ticket's stage sticky to
      `status="blocked"` (⛔). **The stage comes from the persisted `TicketState` (8.1.d), NOT from
      a bare literal**: `_reap_stale_agents` already loops over `deps.store.list_running()`, so for
      each stale `state` read its `state.stage` (the widened field, 8.1.d) and build the header via
      `header_from_state(state, status="blocked", finished=fmt_timestamp(now))` — i.e.
      `upsert_stage_comment(deps.board_writer, state.issue_number, state.stage,
header=header_from_state(state, state.issue_number, state.stage, "blocked",
finished=fmt_timestamp(now)))`. Skip the flip when `state.stage == ""` (an old-format state
      file with no recorded stage — fail-soft, nothing to finalize). This is IN ADDITION to (or
      instead of) the `BlockAction` free-text. Keep the move-to-Blocked board write and slot
      release intact. (Without threading `state.stage` the ⛔ flip has no stage source — the upsert
      would have nothing to key the sticky on.)
- [ ] Tests: assert `LaunchAction` upserts a running header (badge 🟡) carrying session/worktree;
      assert the reaper flips the sticky to ⛔ blocked with a finished timestamp; both fail-soft when
      the writer raises.
- [ ] Verify: `make check` green.

> **Parity decision (session-end ⚠️ / done ✅) — THREADED, not deferred.** The PoC finalizes ✅ done
> on a successful forward advance and ⚠️ interrupted on `session-end` when the agent died without
> advancing. NEW dropped every input: `TicketState` carries no stage, no header metadata, and there
> is no advance breadcrumb. **Operator decision: thread them (FULL parity)** — 8.1.d WIDENS
> `TicketState` (launch stage + the `header_from_state` metadata: profile / mode / started /
> worktree) and adds the fs-store advance breadcrumb; 8.1.e adds the daemon's ✅-on-advance finalize
> (pre-reading the LEFT ticket's `TicketState` before the slot is overwritten); 8.1.f adds the
> ⚠️-on-session-end finalize. After 8.1.c–8.1.f + 8.2.c all FIVE producers exist
> (🟡 launch · ✅ advance · ⚠️ session-end · ⛔ reaper · ❌ teardown) and each terminal sticky carries
> the SAME metadata bullets OLD rendered.

```bash
git commit -m "feat(genesis): producers post rich stage headers (launch running, reaper blocked)"
```

---

### 8.1.e — ✅-on-advance: the daemon finalizes the LEFT stage on a forward move

**The gap.** OLD's `runner.py::_finalize_left_stage` flips the LEFT stage's sticky to ✅ done on an
**accepted, non-rollback FORWARD move** out of a stickied stage (and is a silent no-op when the left
column has no sticky — Backlog→Design finalizes nothing). It is INDEPENDENT of whether the
destination launches an agent (e.g. Plan→Ready-to-dev finalizes ✅ with no new launch). NEW's polling
tick already has the exact inputs: for every `Transition` from `diff(persisted_state.columns_by_item,
snapshot)` it knows `from_column` (the diff baseline) and `to_column`. The agent ALSO drops the
advance breadcrumb (8.1.d) synchronously, so the daemon can confirm the move was an agent advance.

**Layer**: `app/` (the imperative shell — needs the live diff + the writer port). **Files**:
`src/kanbanmate/app/tick.py` (finalize hook on accepted forward transitions; PRE-READ the LEFT
`TicketState` before `LaunchAction`), `src/kanbanmate/app/stage_signal.py` (reuse
`upsert_stage_comment`), `src/kanbanmate/bin/kanban_move.py` (the existing agent move helper — lands
the breadcrumb after `move_card`; NEW analog of OLD's `bin/kanban-move`),
`tests/app/test_tick.py` (extend), `tests/bin/test_kanban_move.py` (extend).

- [ ] Port `_finalize_left_stage` into the tick: when a `Transition` is an accepted FORWARD move
      (`from_column` set, not a reactive/rollback move, destination resolves to a real column),
      finalize `from_column`'s sticky to `status="done"` (✅). The upsert is a SILENT NO-OP when
      `from_column` has no running sticky (the PoC contract — Backlog→agent finalizes nothing) and is
      internally fail-soft, so this never breaks dispatch. Run it for BOTH the LAUNCH branch
      (finalize the left stage, then 8.1.c posts the new stage's 🟡) AND the NOOP forward branch
      (Plan→Ready-to-dev: finalize ✅, no launch).
  - **Header provenance — the concrete two-object resolution (Fix 4/6).** OLD pre-captures the LEFT
    stage's header from the PRE-launch state because `start_session` overwrites the single per-issue
    state slot. NEW's split is `tick(finalize)` ↔ `LaunchAction.execute(save)`: `LaunchAction`
    `deps.store.save(...)` likewise REPLACES the per-issue `TicketState` slot. So the tick MUST, on a
    LAUNCH transition, **PRE-READ the LEFT issue's `TicketState` via `deps.store.load(issue)` BEFORE
    dispatching `LaunchAction`** (i.e. before the slot is overwritten), then build the terminal
    header from that loaded LEFT state:
    `left_state = deps.store.load(issue)` →
    `header = header_from_state(left_state, issue, from_column, status="done",
finished=fmt_timestamp(now))` →
    `upsert_stage_comment(deps.board_writer, issue, from_column, header=header, now=now)`.
    The widened `TicketState` (8.1.d) makes `left_state` metadata-bearing, so the ✅ sticky keeps the
    LEFT stage's OWN session/profile/mode/started/worktree bullets — full parity, no "finalize
    before save" hand-wave. The finalize upsert itself may run after `LaunchAction` (it is fail-soft);
    only the `load` must precede it. For the NOOP forward branch there is no overwrite, so
    `deps.store.load(issue)` at finalize time still returns the LEFT state — read it the same way.
    **Drop any bare `HeaderInfo(stage=…, status=…, finished=…)` construction here — always build via
    `header_from_state(left_state, …)`** so the metadata bullets are present.
- [ ] Add the NEW agent advance helper in `bin/kanban_move.py` (OLD's `bin/kanban-move` analog): when
      the agent moves its own card forward, AFTER `client.move_card(...)` succeeds, call
      `store.record_agent_advance(issue, now=…)` SYNCHRONOUSLY before `claude` exits, keyed by the
      ISSUE number (8.1.d invariant). This is the proof the daemon's ✅-finalize and session-end's
      ⚠️/✅ split rely on. Wrap the breadcrumb write in its OWN try/except (warn-not-abort): a
      breadcrumb-write failure logs a warning to stderr but NEVER aborts the move (the move already
      landed on GitHub). **NO dedup is recorded** on the agent's own forward move (port OLD's bug-#2
      note — the move MUST still produce the next diff so the daemon reacts).
- [ ] Tests: a forward move out of a stickied stage flips the LEFT sticky to ✅ done (finished ts
      set); a move out of a NON-stickied stage (Backlog) is a no-op (no create); the LAUNCH branch
      finalizes the LEFT stage ✅ AND opens the new 🟡 — header provenance correct: the ✅ sticky shows
      the LEFT stage's OWN metadata bullets (profile/mode/started/worktree from the PRE-READ LEFT
      `TicketState`), NOT the new stage's (assert the tick `load`s the LEFT state before dispatching
      `LaunchAction`); a writer exception is swallowed (fail-soft); the agent helper writes the
      breadcrumb keyed by issue number after a successful `move_card`, and a breadcrumb-write failure
      does NOT fail the move.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): daemon finalizes left stage done on forward advance + agent breadcrumb (port _finalize_left_stage)"
```

---

### 8.1.f — ⚠️-on-session-end: finalize interrupted when no advance breadcrumb exists

**The gap.** OLD's `cli/session_end.py::finalize_session` (driven by `bin/kanban-session-end`, which
always runs after `claude` exits via `;`) reads the advance breadcrumb: PRESENT → the agent advanced,
consume the breadcrumb and DO NOT touch the sticky (the dispatcher already finalized ✅); ABSENT →
the agent ended WITHOUT advancing, finalize the current stage's sticky ⚠️ interrupted. It is fully
fail-soft (a GitHub error never breaks session-end) and never resurrects purged state (early-return
when state is absent — a Cancel teardown already cleaned up). NEW's `kanban_session_end.py` calls
`store.release_slot` ONLY — no ⚠️ finalize, because (pre-8.1.d) it had neither the stage nor the
breadcrumb. With 8.1.d those exist; this sub-phase ports the finalize.

**Layer**: `app/` + the `bin` session-end leaf. **Files**:
`src/kanbanmate/bin/kanban_session_end.py` (NEW's session-end leaf — `cli/session_end.py` does NOT
exist; port the finalize here), `src/kanbanmate/app/stage_signal.py` (reuse `upsert_stage_comment`),
`tests/bin/test_kanban_session_end.py` (extend — NOT `tests/cli/test_session_end.py`, which does not
exist), `tests/app/test_stage_signal.py` (extend).

> **Wire a `GithubClient` for the finalize.** Today `kanban_session_end.py` is a network-free leaf
> (it only calls `FsStateStore.release_slot`). The ⚠️ finalize needs the board writer, so the leaf
> must now build a `GithubClient(load_token(), project_id=…, repo=…)` from the loaded token + the
> per-clone registry — mirror exactly how `bin/kanban_comment.py` / `bin/kanban_move.py` wire it
> (`_resolve_entry()` → `GithubClient(...)`). Keep it fail-soft: a missing token / unreachable API
> must not crash the always-run session-end (the leaf already swallows to a non-zero exit).

- [ ] Port `finalize_session` onto NEW's ports, keyed by issue number throughout.
  > **CRITICAL ORDERING FIX (2026-06-05).** The breadcrumb MUST be read BEFORE `release_slot`.
  > `fs_store.release_slot` PURGES the advance breadcrumb (`fs_store.py:155`, added in 8.1.d so a
  > torn-down ticket leaves no stale breadcrumb). If `release_slot` runs first, the breadcrumb is
  > already gone and `recent_agent_advance` always returns `False` → session-end ALWAYS finalizes
  > ⚠️ even after a clean ✅ advance, silently breaking the headline ✅/⚠️ split. The corrected
  > order below reads the breadcrumb first; `clear_agent_advance` is then redundant (the purge in
  > step 3 already removed the file).
  1. load `TicketState`; if `None` → state purged (Cancel teardown already cleaned up) → idempotent
     `release_slot` only, NO GitHub I/O, return (port OLD's no-resurrection early-return).
  2. `advanced = recent_agent_advance(issue, now)` — READ THE BREADCRUMB _BEFORE_ anything purges
     it. Use the ISSUE key (8.1.d invariant).
  3. `release_slot(issue)` — frees the cap slot + running state + the now-consumed breadcrumb
     (idempotent). This purge is now harmless because step 2 already read the breadcrumb.
  4. if `advanced` → the agent advanced; RETURN without touching the sticky (the daemon's 8.1.e
     already finalized ✅). This is the ✅/⚠️ split — the breadcrumb decides. `clear_agent_advance`
     is redundant now (step 3's `release_slot` purged the breadcrumb); you may call it for clarity
     but it is not required.
  5. else (no breadcrumb) → resolve the stage and build the header from the loaded `TicketState`:
     `stage = loaded_state.stage`; build the header via `header_from_state(loaded_state, issue,
stage, status="interrupted", finished=fmt_timestamp(now))` and
     `upsert_stage_comment(writer, issue, stage, header=…, now=now)` → ⚠️. The widened
     `TicketState` (8.1.d) makes the ⚠️ sticky carry the SAME metadata bullets OLD rendered (full
     parity) — drop any bare `HeaderInfo(stage=…, status=…)` construction. Skip silently if
     `stage == ""`.
  - **Stage resolution (L5):** NEW resolves the stage from `TicketState.stage` ALONE. OLD's
    `get_item_column(...) or st["column"]` two-source fallback is collapsed because 8.1.d persists
    the launch stage directly on `TicketState` — there is no separate `columns/` marker to consult.
  - FAIL-SOFT throughout: any GitHub error inside the finalize never breaks session-end (the upsert
    is already fail-soft; the leaf must not raise on a missing token / unreachable API).
- [ ] Tests: session-end WITH a recent breadcrumb → consumes it, sticky untouched (no ⚠️), slot
      released; session-end WITHOUT a breadcrumb → flips the stage sticky to ⚠️ interrupted (finished
      ts set), slot released; session-end on PURGED state (no `TicketState`) → idempotent slot
      release, NO GitHub I/O, no raise; a GitHub error during the ⚠️ finalize is swallowed.
- [ ] Verify: `make check` green. Cross-check the full lifecycle in tests: a launch posts 🟡, a
      forward advance flips it ✅, a reaped stale agent flips it ⛔, a session-end-without-advance
      flips it ⚠️, a teardown flips open stickies ❌ — all FIVE producers exercised.

```bash
git commit -m "feat(genesis): session-end finalizes interrupted when no advance breadcrumb (port finalize_session)"
```

---

## 8.2 — Full Cancel teardown parity (`--force` · `branch -D` · close-PR-keep-branch · ❌ · recap)

> **The gap.** NEW's `TeardownAction` (app/actions.py) does FOUR steps: kill session (guarded),
> `remove_worktree(force=False)`, `release_slot`, recap comment. The PoC `teardown_ticket`
> (`engine/teardown.py`) does SEVEN local steps + one remote step:
> 1 kill (guarded) · 2 release slot · 3 `remove_worktree(force=True)` · 4 local `git branch -D <feat>`
> (skip `""`/`HEAD`) · 5 purge state · 6 flip OPEN stage stickies to ❌ cancelled · 7 recap —
> plus the remote step: **close the open PR for the branch, KEEP the remote branch**.
> NEW is missing: `--force` removal, the local branch delete, the PR close, and the ❌ flip. This is
> the operator-decided Cancel semantics (close PR + keep remote branch — baked into this plan).

### 8.2.a — GitHub client: find + close the open PR (keep the remote branch)

**The gap.** NEW's `GithubClient` has NO PR method (`rg "def close_p|find_pr|pull" client.py` → only
`comment`/`move_card`/seed methods). The PoC teardown calls `gh.close_pull_request(repo, branch)`.

**Files**: `src/kanbanmate/adapters/github/client.py` (add the two REST methods),
`tests/adapters/github/test_client.py` (extend; fixtures for the PR list + patch).

- [ ] Add `find_open_pr(self, head_branch: str) -> int | None` — REST
      `GET /repos/{owner}/{repo}/pulls?state=open&head={owner}:{branch}`; return the first PR
      `number` or `None`. All requests inherit the client's mandatory connect+read timeouts
      (CLAUDE.md network-safety). Empty/`HEAD` branch → return `None` without a round-trip.
- [ ] Add `close_pr(self, number: int) -> None` — REST `PATCH /repos/{owner}/{repo}/pulls/{number}`
      with body `{"state": "closed"}`. **Closing a PR does NOT delete its head branch** — the
      remote branch is kept (the operator-decided Cancel semantics; DESIGN §8.2). Document this
      explicitly. This is NOT a merge — the deny-list bans merge for AGENTS, but teardown is the
      dispatcher (mechanical), and `close` ≠ `merge` regardless.
- [ ] Add a convenience `close_open_pr_for_branch(self, head_branch: str) -> int | None` that
      composes the two (find → close) and returns the closed PR number or `None` (no-op when no
      open PR). This is the single call the `TeardownAction` makes (keeps the action port-thin).
- [ ] Extend the `BoardWriter` port (or add a focused `PullRequests` port) with
      `close_open_pr_for_branch(head_branch: str) -> int | None`. Prefer a SMALL dedicated port so
      teardown depends only on what it uses; wire it through `Deps`.
- [ ] Tests: fixture with one open PR for the branch → `find_open_pr` returns its number, `close_pr`
      issues the PATCH `state=closed` (assert the branch is NOT touched — no delete-ref call); no
      open PR → `find_open_pr` returns `None` and `close_open_pr_for_branch` is a no-op; `""`/`HEAD`
      branch → no round-trip.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): github client close-open-PR-for-branch (close, keep remote branch)"
```

---

### 8.2.b — Extend `TeardownAction` to full parity (mechanical, fail-soft, idempotent)

**Files**: `src/kanbanmate/ports/workspace.py` (add `delete_branch` to the `Workspace` Protocol),
`src/kanbanmate/adapters/workspace/` (implement `delete_branch` on `GitWorktreeWorkspace`),
`src/kanbanmate/app/actions.py` (`Deps` + `TeardownAction`), `src/kanbanmate/app/wiring.py`
(`build_deps` constructs/injects the PR port + the branch discovery), `tests/app/test_actions.py`
(extend), `tests/adapters/test_workspace.py` (extend — the `delete_branch` adapter),
`tests/cli/test_cancel.py` (the `kanban cancel` path reuses the action — assert parity).

- [ ] **Branch-`-D` seam (L2):** add `delete_branch(self, ticket: int, branch: str) -> None` to the
      `Workspace` Protocol and implement it on the `GitWorktreeWorkspace` adapter as a FORCE delete
      (`git branch -D <branch>` in the clone), fail-soft (a missing branch / rc 128 is swallowed).
      Keeping the subprocess in the adapter keeps `TeardownAction` pure of `subprocess` — the action
      calls `deps.workspace.delete_branch(issue, branch)` instead of shelling out itself. No-op on
      `""`/`"HEAD"`.
- [ ] Add to `Deps`: the PR port (8.2.a) and reuse the existing `workspace.discover_branch(issue)`
      to resolve the local feature branch (NEW's `TicketState` carries no `branch`; `Workspace`
      already exposes `discover_branch`). Keep `Deps` frozen.
- [ ] **Wire the PR port (L3):** `app/wiring.py::build_deps` MUST construct/inject the PR port — the
      SAME `GithubClient` instance that already backs `board_writer` satisfies it (8.2.a adds the
      `close_open_pr_for_branch` method to that client), so pass the existing client through to the
      new `Deps` field; mirror exactly how `board_writer` is wired (one client, two ports).
- [ ] `TeardownAction.execute` — port the PoC's seven-step + remote sequence onto NEW's ports, each
      step in its own try/except (fail-soft, mirroring the PoC `_soft`; NEW already uses
      `logger.exception(...)` per step). Final order (independent steps not gated on prior success): 1. kill the tmux session IF alive (`sessions.is_alive` guard — `kill` is check=True). 2. `workspace.remove_worktree(issue, force=True)` — **change `force=False` → `force=True`**
      (a cancelled worktree is almost always dirty; PoC step 3). Fail-soft on a replay (rc 128). 3. resolve `branch = workspace.discover_branch(issue)`; if `branch and branch != "HEAD"`, call
      `deps.workspace.delete_branch(issue, branch)` (the L2 seam — force `git branch -D` lives in
      the adapter, fail-soft). **Deny-list note**: the worktree settings ban `Bash(git branch -D*)`
      for LAUNCHED AGENTS; teardown runs in the dispatcher (no agent, no `.claude/settings.json`),
      so the ban does not apply — this single mechanical transition is the only path that deletes
      (DESIGN §8.2; PoC module docstring). The action stays subprocess-free; the adapter owns the
      argv-list `git` call (never `shell=True`). 4. `store.release_slot(issue)` (idempotent; purges the fs state record). 5. flip OPEN stage stickies to ❌ cancelled (8.2.c) — best-effort. 6. `close_open_pr_for_branch(branch)` when `branch and branch != "HEAD"` (no-op otherwise) —
      close the PR, KEEP the remote branch. 7. recap comment (English; replace the current 🗑️ recap with parity text: "Ticket cancelled —
      worktree / local branch / session removed. PR closed, remote branch kept. Resume: move the
      card to Backlog.").
- [ ] Tests: assert ALL of kill / `remove_worktree(force=True)` / `branch -D` (skipped for `""` and
      `HEAD`) / `release_slot` / sticky-flip / `close_open_pr_for_branch` / recap fire; each step's
      failure is isolated (inject a raiser per step → the remaining steps still run); a second
      teardown (replay) destroys nothing and never raises. `kanban cancel` reuses `TeardownAction`,
      so its test inherits parity — assert the manual path also closes the PR + keeps the branch.
- [ ] Verify: `make check` green.

> **Drift note (8.2.b execution, 2026-06-05).** Adding the **required** `pull_requests` field to the
> frozen `Deps` and the `delete_branch` method to the `Workspace` Protocol fans out to every test
> that constructs `Deps` or fakes `Workspace`/`BoardWriter` — beyond the whitelisted
> `tests/app/test_actions.py` / `tests/cli/test_cancel.py`. The mechanical compile-fixes also touched
> `tests/app/test_tick.py` (force=False→True on the teardown-driven reaper/Cancel paths +
> `pull_requests=MagicMock()`), `tests/test_killswitch.py`, `tests/integration/test_poll_real_board.py`
> (`_FakeBoard.close_open_pr_for_branch` + `_SpyWorkspace.delete_branch`), and
> `tests/local_real/test_tick_local.py` (`_FakeBoard` PR + comment stubs). The PR seam is a small
> dedicated `PullRequests` port in `ports/board.py` (8.2.a's preferred option, deferred to here),
> satisfied by the same `GithubClient` instance. **Pre-existing masked break corrected:** `mypy src
tests` was already RED at the 8.2.b baseline (48b5fda) — `_FakeStore` in `tests/cli/test_status.py`
> never gained 8.1.d's `record/recent/clear_agent_advance`, and `_FakeBoard` in
> `tests/local_real/test_tick_local.py` never gained 8.1.b's `list_issue_comments`/`update_comment`
> (10 errors total, masked by reading only the pytest tail). Both fakes are updated here so the gate
> is genuinely rc=0 with a clean mypy line.

```bash
git commit -m "feat(genesis): full Cancel teardown parity (--force worktree, branch -D, close PR keep branch, recap)"
```

---

### 8.2.c — Flip open stage stickies to ❌ on teardown (the `_cancel_open_stickys` port)

**Files**: `src/kanbanmate/app/stage_signal.py` (add the helper next to the upsert),
`src/kanbanmate/app/actions.py` (call it from `TeardownAction` step 5),
`tests/app/test_stage_signal.py` (extend).

- [ ] Port the PoC `_cancel_open_stickys(gh, repo, issue)` onto NEW's port + core helpers:
      list the issue's comments via `writer.list_issue_comments(issue)`; for each comment, FIRST
      apply an explicit membership pre-filter — `if "kanban:step=" not in body: continue` — so
      non-stage comments are skipped before any parse. For a stage comment, extract the stage
      (`body.split("kanban:step=", 1)[1].split("-->", 1)[0].strip()`), `split_sticky` the HEADER
      only and skip unless the RUNNING label ("in progress") is in the header (so a terminal
      ✅/⚠️/⛔ sticky is left as-is), then `upsert_stage_comment(writer, issue, stage,
header=HeaderInfo(stage=stage, status="cancelled", finished=fmt_timestamp(now)))`.
      Best-effort: any error logged + swallowed (the upsert is already fail-soft; wrap the listing
      too).
- [ ] **Marker-prefix note**: BOTH the membership pre-filter (`"kanban:step=" not in body`) AND the
      stage split (`body.split("kanban:step=", 1)`) key off NEW's marker prefix `kanban:step=` — NOT
      OLD's `kanbanmate-stage:`. (8.1.a deliberately kept NEW's existing `<!-- kanban:step=<stage> -->`
      prefix so the shipped one-line stickies are still located after the upgrade; this port must use
      the same prefix or it will never match a NEW sticky.)
- [ ] **Header-only note**: keying off the header status line ONLY (not the `**Progress**` body) is
      load-bearing — an agent progress line containing "in progress" must NOT mis-classify a terminal
      sticky as open. Port the PoC's exact `split_sticky`-then-check-header logic.
- [ ] Tests: a running sticky → flipped to ❌ cancelled (finished ts set); a terminal sticky
      (✅/⚠️/⛔) → untouched; a body whose ONLY "in progress" occurrence is in the progress zone →
      untouched (header-only check); a non-stage comment → ignored; a GitHub error → swallowed.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): teardown flips open stage stickies to cancelled (port of _cancel_open_stickys)"
```

---

### 8.2.d — `ResetAction` parity (Cancel → Backlog re-arm)

**The gap.** NEW's `ResetAction.execute` calls only `store.release_slot(issue)`. The PoC
`reset_ticket` ALSO records the card's column as "Backlog" (`store.set_item_column(content_node_id,
"Backlog")`) so the NEXT move (Backlog → agent column) actually triggers — without it the first
post-reset move can no-op (the PoC seed→Store fix). NEW's diff is column-class-aware against the
persisted state, so verify whether NEW needs the equivalent.

**Files**: `src/kanbanmate/app/actions.py` (`ResetAction`), `tests/app/test_actions.py`,
`tests/app/test_tick.py` (the diff re-trigger seam).

- [ ] Investigate NEW's diff: after `release_slot` purges the state, does the next Backlog→agent
      move produce a `LAUNCH` transition? NEW's `diff(persisted, snapshot)` compares against
      persisted state; a purged ticket re-appears as a fresh item, so the move SHOULD re-trigger.
      If a residual "last column" must be recorded for the re-trigger (parity with the PoC fix),
      record it; if NEW's diff already re-triggers from a clean purge, document that NEW does not
      need `set_item_column` (a genuine simplification the polling pivot bought) and keep
      `ResetAction` as the idempotent purge.
- [ ] Tests: a Cancel→Backlog reset leaves the GitHub issue metadata untouched, clears runtime
      state, launches NO agent (Backlog inert), and a SUBSEQUENT move into an agent column
      re-launches fresh (assert the re-trigger end-to-end through `tick`).
- [ ] Verify: `make check` green.

> **Commit-type fallback (audit fix).** If the investigation concludes NEW's polling diff already
> re-triggers from a clean purge (no production change — `ResetAction` stays the idempotent purge),
> the only artifact is the re-trigger test; commit it as
> `test(genesis): assert ResetAction purge re-arms the next agent move` instead of the behavioural
> `fix(...)` subject below (a `fix:` subject must not front a test-only/no-op commit).

```bash
git commit -m "fix(genesis): ResetAction re-arms a cancelled ticket so the next agent move re-triggers"
```

---

### Phase 8 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`).
2. `make test` — all pass.
3. `make check` — clean (lint + test + size guard).
4. Residual-import grep (split — audit fix): `rg --type py "upsert_sticky|render_sticky" src tests` →
   **zero matches** (the one-line writer is fully superseded). The OLD marker prefix `kanbanmate-stage`
   may appear ONLY in divergence DOCSTRINGS (8.1.a was required to "document the divergence from the
   PoC", so a blanket ban contradicts that mandate): `rg --type py "kanbanmate-stage" src tests` must
   match only explanatory docstring/comment lines, NEVER an active marker — verify `marker()` returns
   the `kanban:step=` form and no code constructs a `kanbanmate-stage` marker.
5. Parity check — the FULL signaling lifecycle is exercised in tests: the rich sticky subsystem
   renders 🟡 `in progress` (launch) → ✅ `done` (forward advance) → ⚠️ `interrupted` (session-end
   without an advance breadcrumb) → ⛔ `blocked` (reaper) → ❌ `cancelled` (teardown), ALL FIVE
   producers wired; the advance breadcrumb is written synchronously and is the ✅/⚠️ discriminator;
   `TeardownAction` exercises all seven local steps + the remote PR close; `kanban cancel` inherits
   the full teardown.
6. English-only artifact check: no French badge label string reaches a rendered sticky header
   (asserted in `tests/core/test_stage_comment.py`).
7. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 8 gate — PoC parity port (rich sticky + full Cancel teardown)"
```
