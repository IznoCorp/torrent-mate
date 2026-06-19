"""Tests for the shipped ``/implement:*`` prompt defaults + the hybrid default
transition table in :mod:`kanbanmate.core.transitions_defaults`.

These pin the port from the PoC ``cli/transitions_yaml.py``: every ``/implement:*``
slash-command lands in exactly the expected prompt, every ``{{placeholder}}``
survives the French→English translation, no French prose leaks through, the
default table round-trips through :func:`kanbanmate.core.transitions.load_transitions`
into a :class:`TransitionConfig` whose ``get`` resolves every shipped pair (and the
``PrepareFeature → InProgress`` vs ``PRCI → InProgress`` discriminator resolves to
DIFFERENT prompts), and — crucially — there is NO autonomous merge prompt (merge
stays human, DESIGN §10).
"""

from __future__ import annotations

from typing import Any

import yaml

import kanbanmate.core.transitions_defaults as defaults_mod
from kanbanmate.core.placeholders import fill
from kanbanmate.core.transitions import load_transitions
from kanbanmate.core.transitions_defaults import (
    DEFAULT_CONCURRENCY_CAP,
    DEFAULT_MOVE_RATE_LIMIT_PER_HOUR,
    DEFAULT_TRANSITIONS,
    _BRAINSTORM_PROMPT,
    _DESIGN_PROMPT,
    _DESYNC,
    _FIXCI_PROMPT,
    _IMPLEMENT_PROMPT,
    _PLAN_PROMPT,
    _PREPARE_PROMPT,
    _REVIEW_PROMPT,
    _REWORK_PROMPT,
    _STATE_CHECK_EARLY,
    _STATE_CHECK_LATE,
)


def _render_doc(project: str) -> str:
    """Render a transitions.yml document from the defaults (mirrors phase 12.7).

    The phase 12.7 ``render_transitions_yaml`` does not exist yet, so this test
    helper performs the equivalent ``yaml.safe_dump`` locally — the same shape
    the renderer will emit — so the round-trip assertions exercise the real
    :func:`load_transitions` parser against the shipped table.
    """
    doc: dict[str, Any] = {
        "project": project,
        "defaults": {
            "concurrency_cap": DEFAULT_CONCURRENCY_CAP,
            "move_rate_limit_per_hour": DEFAULT_MOVE_RATE_LIMIT_PER_HOUR,
        },
        "transitions": [dict(t) for t in DEFAULT_TRANSITIONS],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)


class TestSlashCommands:
    """Each ``/implement:*`` slash-command lands in exactly the expected prompt."""

    def test_brainstorm_prompt_has_brainstorm(self) -> None:
        """``_BRAINSTORM_PROMPT`` carries ``/implement:brainstorm`` (the interactive step)."""
        assert "/implement:brainstorm" in _BRAINSTORM_PROMPT

    def test_design_prompt_is_autonomous_design_no_brainstorm(self) -> None:
        """``_DESIGN_PROMPT`` is the AUTONOMOUS design step — it does NOT brainstorm.

        Genesis phase 26 split the front of the flow: the brainstorm slash-command
        moved to ``_BRAINSTORM_PROMPT`` (Backlog→Brainstorming). ``_DESIGN_PROMPT``
        (Brainstorming→Spec) writes design.md from the brainstorm output and carries
        no interactive brainstorming.
        """
        assert "/implement:brainstorm" not in _DESIGN_PROMPT
        # §29.4: the design is written to docs/features/<codename>/DESIGN.md.
        assert "DESIGN.md" in _DESIGN_PROMPT

    def test_plan_prompt_has_plan(self) -> None:
        """``_PLAN_PROMPT`` carries ``/implement:plan``."""
        assert "/implement:plan" in _PLAN_PROMPT

    def test_prepare_prompt_has_create_branch(self) -> None:
        """``_PREPARE_PROMPT`` carries ``/implement:create-branch``."""
        assert "/implement:create-branch" in _PREPARE_PROMPT

    def test_implement_prompt_has_phase(self) -> None:
        """``_IMPLEMENT_PROMPT`` carries ``/implement:phase``."""
        assert "/implement:phase" in _IMPLEMENT_PROMPT

    def test_fixci_prompt_has_no_slash_command(self) -> None:
        """``_FIXCI_PROMPT`` is the CI-fix prompt — it INVOKES no ``/implement:*`` slash-command.

        The bot fix-CI loop runs no skill, and the firm-exit clean-stop wording is now GENERIC ("the
        next-stage slash command", no literal ``/implement:…`` example), so the prompt must carry no
        ``/implement:`` substring at all.
        """
        assert "/implement:" not in _FIXCI_PROMPT

    def test_review_prompt_has_pr_review_without_merging(self) -> None:
        """``_REVIEW_PROMPT`` carries ``/implement:pr-review`` and ``WITHOUT merging``."""
        assert "/implement:pr-review" in _REVIEW_PROMPT
        assert "WITHOUT merging" in _REVIEW_PROMPT


class TestGroundingDiscipline:
    """The design + plan stages carry the grounding/self-verification discipline (helm #5 review).

    These two stages produced confident-but-wrong artifacts (a false layering-guard claim, a call
    with a non-existent signature, tests whose inputs resolved to None). The discipline forces
    source-verification, real-signature matching, layering respect, real-value tests, and a
    self-review pass — so an autonomous agent cannot ship those classes of defect unchecked.
    """

    _MARKER = "GROUND EVERY CLAIM IN THE SOURCE"

    # Every CODE-PRODUCING / code-reasoning stage carries the discipline — not just design+plan
    # (operator: "tout dois être fixé"). Brainstorm is excluded (interactive requirements-gathering,
    # writes no code).
    _CODE_STAGES = (
        "_DESIGN_PROMPT",
        "_PLAN_PROMPT",
        "_IMPLEMENT_PROMPT",
        "_FIXCI_PROMPT",
        "_REVIEW_PROMPT",
        "_REWORK_PROMPT",
    )

    def test_all_code_producing_stages_carry_grounding_discipline(self) -> None:
        """Design, plan, implement, fix-CI, review, and rework all carry the grounding discipline."""
        for name in self._CODE_STAGES:
            prompt = getattr(defaults_mod, name)
            assert self._MARKER in prompt, f"{name} missing grounding marker"
            assert "MATCH REAL SIGNATURES" in prompt, f"{name} missing signature rule"
            assert "TESTS MUST EXERCISE REAL VALUES" in prompt, (
                f"{name} missing real-value-tests rule"
            )
            assert "ENUMERATE THE COMPLETE SET" in prompt, (
                f"{name} missing complete-enumeration rule"
            )

    def test_brainstorm_does_not_carry_grounding_discipline(self) -> None:
        """The interactive brainstorm stage stays lean — it gathers requirements, writes no code."""
        assert self._MARKER not in defaults_mod._BRAINSTORM_PROMPT

    def test_grounding_discipline_keeps_the_clean_stop_and_french_guards(self) -> None:
        """The discipline carries no ``/implement:`` literal and no "end the session" prose.

        Both would trip sibling guards (the fix-CI no-slash-command assertion and the
        no-bare-end-the-session assertion), so the shared block must stay clean.
        """
        assert "/implement:" not in defaults_mod._GROUNDING_DISCIPLINE
        assert "end the session" not in defaults_mod._GROUNDING_DISCIPLINE.lower()


class TestPlaceholdersSurvive:
    """Every ``{{placeholder}}`` survives the French→English translation."""

    def test_brainstorm_prompt_placeholders(self) -> None:
        """``_BRAINSTORM_PROMPT`` keeps every load-bearing source placeholder."""
        for token in ("{{code}}", "{{title}}", "{{ticket_body}}", "{{issue_body}}", "{{comments}}"):
            assert token in _BRAINSTORM_PROMPT

    def test_design_prompt_placeholders(self) -> None:
        """``_DESIGN_PROMPT`` (autonomous design) keeps ``{{code}}`` / ``{{codename}}`` / ``{{ticket_body}}``."""
        for token in ("{{code}}", "{{codename}}", "{{ticket_body}}"):
            assert token in _DESIGN_PROMPT

    def test_plan_prompt_placeholders(self) -> None:
        """``_PLAN_PROMPT`` keeps ``{{code}}`` / ``{{codename}}`` / ``{{design_path}}``."""
        for token in ("{{code}}", "{{codename}}", "{{design_path}}"):
            assert token in _PLAN_PROMPT

    def test_prepare_prompt_placeholder(self) -> None:
        """``_PREPARE_PROMPT`` keeps ``{{codename}}``."""
        assert "{{codename}}" in _PREPARE_PROMPT

    def test_implement_prompt_placeholder(self) -> None:
        """``_IMPLEMENT_PROMPT`` keeps ``{{codename}}``."""
        assert "{{codename}}" in _IMPLEMENT_PROMPT

    def test_fixci_prompt_placeholders(self) -> None:
        """``_FIXCI_PROMPT`` keeps ``{{codename}}`` / ``{{script_output}}``."""
        for token in ("{{codename}}", "{{script_output}}"):
            assert token in _FIXCI_PROMPT

    def test_review_prompt_placeholder(self) -> None:
        """``_REVIEW_PROMPT`` keeps ``{{codename}}``."""
        assert "{{codename}}" in _REVIEW_PROMPT


class TestNoFrenchProse:
    """The PoC's French prose is fully translated — no French verbs leak through."""

    _ALL_PROMPTS = (
        _BRAINSTORM_PROMPT,
        _DESIGN_PROMPT,
        _PLAN_PROMPT,
        _PREPARE_PROMPT,
        _IMPLEMENT_PROMPT,
        _FIXCI_PROMPT,
        _REVIEW_PROMPT,
    )

    def test_no_french_words(self) -> None:
        """No French token from the PoC prose survives in any shipped prompt."""
        # A representative set of the PoC's French verbs/words (cli/transitions_yaml.py).
        french_tokens = (
            "Conçois",
            "Corrige",
            "déplace",
            "Prépare",
            "Implémente",
            "Termine",
            "Lance",
            "commentaires",
            "SANS merger",
        )
        for prompt in self._ALL_PROMPTS:
            for token in french_tokens:
                assert token not in prompt, f"French token {token!r} leaked into a prompt"


class TestTerminalDoneStep:
    """Option 1 (#1): every shipped prompt ends with a concrete ``kanban-done {{code}}`` terminal
    step (replacing the no-op "End the session" prose), and no bare end-session prose remains."""

    _ALL_PROMPTS = (
        _BRAINSTORM_PROMPT,
        _DESIGN_PROMPT,
        _PLAN_PROMPT,
        _PREPARE_PROMPT,
        _IMPLEMENT_PROMPT,
        _FIXCI_PROMPT,
        _REVIEW_PROMPT,
        # _REWORK_PROMPT is a real registered transition (the PR/CI rework step) that ALSO gained the
        # ``kanban-done {{code}}`` terminal step — it must be covered by the terminal-done assertions
        # (review finding #6, it was missing from this tuple).
        _REWORK_PROMPT,
    )

    def test_every_prompt_runs_kanban_done(self) -> None:
        """Every shipped prompt instructs the agent to run ``kanban-done {{code}}`` as its terminal step."""
        for prompt in self._ALL_PROMPTS:
            assert "kanban-done {{code}}" in prompt

    def test_no_bare_end_the_session_prose(self) -> None:
        """No prompt carries the OLD no-op "end the session" prose without a kanban-done command.

        The Option-1 fix replaced every "End the session" / "end the session" line with a concrete
        ``kanban-done {{code}}`` command — a bare prose instruction is a no-op in the interactive REPL
        (the agent can only end its TURN), which is the bug this fixes.
        """
        for prompt in self._ALL_PROMPTS:
            assert "end the session" not in prompt.lower()


class TestAutonomyInstruction:
    """Genesis phase 26: only the brainstorm is interactive; every other agent prompt
    carries an explicit "run fully autonomously — do NOT ask the user any questions"
    instruction so an unattended orchestrated session never hangs on a clarifying
    question (the e2e interactive-hang fix).
    """

    # The marker substring the autonomy instruction always contains.
    _MARKER = "Run fully autonomously"

    def test_brainstorm_is_the_only_interactive_prompt(self) -> None:
        """``_BRAINSTORM_PROMPT`` does NOT carry the autonomy instruction — it is interactive."""
        assert self._MARKER not in _BRAINSTORM_PROMPT
        # It explicitly invites the user to be asked questions (the human attaches).
        assert "MAY ask the user" in _BRAINSTORM_PROMPT

    def test_every_other_agent_prompt_is_autonomous(self) -> None:
        """Every non-brainstorm agent prompt carries the no-questions autonomy instruction."""
        for prompt in (
            _DESIGN_PROMPT,
            _PLAN_PROMPT,
            _IMPLEMENT_PROMPT,
            _FIXCI_PROMPT,
            _REVIEW_PROMPT,
        ):
            assert self._MARKER in prompt
            assert "do NOT ask the user any questions" in prompt


class TestAutonomousMergeStage:
    """Review → Merge is the AUTONOMOUS merge stage (operator decision).

    Supersedes the historical merge=human-only floor for THIS transition only: a claude agent under
    the dedicated ``merge`` profile squash-merges a green, mergeable PR. The safety rails (squash
    via ``gh pr merge`` only, NEVER force-push/rebase/direct-main-push, success→Done/blocker→Review)
    live in ``_MERGE_PROMPT``; every OTHER prompt still bans merge.
    """

    def test_merge_prompt_is_exposed_and_carries_safety_rails(self) -> None:
        """``_MERGE_PROMPT`` exists and encodes the merge-stage safety contract."""
        assert hasattr(defaults_mod, "_MERGE_PROMPT")
        prompt = defaults_mod._MERGE_PROMPT
        # The squash-merge mechanism is the gh-pr-merge path, and only that.
        assert "gh pr merge <pr> --squash" in prompt
        # The forbidden mechanisms are spelled out.
        assert "NEVER rebase" in prompt or "NEVER rebase/force-push/rewrite history" in prompt
        assert "merge-main-IN" in prompt or "merge main INTO" in prompt
        assert "push to ``main`` directly" in prompt or "push to ``main``" in prompt
        # Explicit routing: success → Done, blocker → Review.
        assert "kanban-move {{code}} Done" in prompt
        assert "kanban-move {{code}} Review" in prompt

    def test_no_prompt_instructs_an_agent_to_merge(self) -> None:
        """No shipped prompt INSTRUCTS an agent to merge (§29.4: merge is human-only).

        The review prompt deliberately NAMES the pr-review skill's terminal squash-merge step in
        order to order it SKIPPED — so "squash" legitimately appears there. The discipline is that
        no prompt issues an affirmative merge instruction: none runs ``gh pr merge``, and the only
        prompt mentioning merge frames it as SKIPPED + bans the command.
        """
        all_prompts = (
            _BRAINSTORM_PROMPT,
            _DESIGN_PROMPT,
            _PLAN_PROMPT,
            _PREPARE_PROMPT,
            _IMPLEMENT_PROMPT,
            _FIXCI_PROMPT,
            _REVIEW_PROMPT,
        )
        for prompt in all_prompts:
            lowered = prompt.lower()
            # No prompt ever tells the agent to RUN a merge.
            assert "run `gh pr merge`" not in lowered or "never run `gh pr merge`" in lowered

    def test_review_prompt_names_the_merge_step_and_orders_it_skipped(self) -> None:
        """``_REVIEW_PROMPT`` names the pr-review terminal merge step, orders it SKIPPED, bans it.

        §29.4 verdict fix: prompt wording alone is the steering, so the review prompt must (a) name
        the skill's terminal squash-merge step, (b) order it SKIPPED, and (c) carry the verbatim
        ``gh pr merge`` ban — not merely omit a merge instruction.
        """
        assert "squash-merge step" in _REVIEW_PROMPT
        assert "SKIPPED" in _REVIEW_PROMPT
        assert "NEVER run `gh pr merge`" in _REVIEW_PROMPT

    def test_review_to_merge_is_an_autonomous_agent_stage(self) -> None:
        """``Review → Merge`` is an AGENT launch under the ``merge`` profile, not a script gate."""
        rows = [t for t in DEFAULT_TRANSITIONS if t["from"] == "Review" and t["to"] == "Merge"]
        assert len(rows) == 1
        row = rows[0]
        assert row.get("prompt") == defaults_mod._MERGE_PROMPT
        assert row["profile"] == "merge"
        # advance:stop — the agent routes itself (Done|Review); no engine auto-advance.
        assert row.get("advance") == "stop"
        # PRE-LAUNCH CI gate (audit §6 defense-in-depth): don't launch the merge agent on a red PR;
        # a failed gate bounces the card back to Review without starting a merge.
        assert row.get("script") == "bin/check-pr-ready.sh"
        assert row.get("on_fail") == "move:Review"

    def test_merge_route_edges_exist(self) -> None:
        """Both merge-agent routes are whitelisted: Merge→Done (success) and Merge→Review (blocker)."""

        def rows(frm: str, to: str) -> list[dict[str, object]]:
            # ``from``/``to`` may be a list (wildcard/multi-source rows) — compare by equality, never
            # hash, so a list-valued entry does not raise.
            return [t for t in DEFAULT_TRANSITIONS if t["from"] == frm and t["to"] == to]

        assert rows("Merge", "Done"), "success route Merge→Done must be whitelisted"
        review_rows = rows("Merge", "Review")
        assert len(review_rows) == 1, "blocker route Merge→Review must be whitelisted exactly once"
        # The blocker route is a plain no-op (no prompt) — it must NOT re-fire a launch.
        assert review_rows[0].get("prompt") is None


class TestDefaultTableRoundTrip:
    """The shipped table round-trips through ``load_transitions`` and resolves."""

    def test_round_trips_into_transition_config(self) -> None:
        """The rendered defaults parse into a populated ``TransitionConfig``."""
        cfg = load_transitions(_render_doc("owner/repo"))
        assert cfg.project == "owner/repo"
        assert cfg.concurrency_cap == DEFAULT_CONCURRENCY_CAP
        assert cfg.move_rate_limit_per_hour == DEFAULT_MOVE_RATE_LIMIT_PER_HOUR

    def test_every_explicit_pair_resolves(self) -> None:
        """Every non-wildcard shipped pair resolves via ``get`` (list entries expanded)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        for t in DEFAULT_TRANSITIONS:
            if t["from"] == "*" or t["to"] == "*":
                continue
            # A list-valued ``from``/``to`` (the skip-to-Done sugar) cartesian-expands
            # into concrete edges at load; expand it here too before resolving.
            from_cols = t["from"] if isinstance(t["from"], list) else [t["from"]]
            to_cols = t["to"] if isinstance(t["to"], list) else [t["to"]]
            for from_col in from_cols:
                for to_col in to_cols:
                    assert cfg.get(from_col, to_col) is not None, (
                        f"{from_col} → {to_col} did not resolve"
                    )

    def test_same_destination_different_prompts_discriminator(self) -> None:
        """``PrepareFeature → InProgress`` vs ``PRCI → InProgress`` resolve to DIFFERENT prompts.

        This is the load-bearing reason the model is per-(from,to) and not
        per-column: the SAME destination reached from two origins gets two
        prompts — the per-column model could not express it.
        """
        cfg = load_transitions(_render_doc("owner/repo"))
        implement = cfg.get("PrepareFeature", "InProgress")
        fixci = cfg.get("PRCI", "InProgress")
        assert implement is not None and fixci is not None
        assert implement.prompt == _IMPLEMENT_PROMPT
        assert fixci.prompt == _FIXCI_PROMPT
        assert implement.prompt != fixci.prompt

    def test_planned_to_ready_is_allowed_no_op(self) -> None:
        """``Planned → ReadyToDev`` is whitelisted with no action (allowed no-op)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("Planned", "ReadyToDev")
        assert t is not None
        assert not t.has_action

    def test_inprogress_to_prci_is_script_only(self) -> None:
        """``InProgress → PRCI`` is a script-only transition (run_script)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("InProgress", "PRCI")
        assert t is not None
        assert t.script == "bin/check-pr-ready.sh"
        assert t.prompt is None
        assert t.on_fail == "move:InProgress"

    def test_wildcard_parking_and_cancel_rows_resolve(self) -> None:
        """The ``*→Blocked`` / ``Blocked→*`` / ``*→Cancel`` / ``Cancel→Backlog`` rows resolve."""
        cfg = load_transitions(_render_doc("owner/repo"))
        # *→Blocked: any source parks.
        assert cfg.get("InProgress", "Blocked") is not None
        # Blocked→*: any un-park resolves.
        assert cfg.get("Blocked", "Backlog") is not None
        # *→Cancel: any source into Cancel is a KNOWN (not rolled back) transition.
        assert cfg.get("Review", "Cancel") is not None
        # Cancel→Backlog: the resume path.
        assert cfg.get("Cancel", "Backlog") is not None


class TestFrontFlowSplit:
    """Genesis phase 26: the brainstorm↔design split + the new Brainstorming/Plan edges."""

    def test_backlog_to_brainstorming_is_the_interactive_brainstorm(self) -> None:
        """``Backlog → Brainstorming`` carries the interactive ``_BRAINSTORM_PROMPT``."""
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("Backlog", "Brainstorming")
        assert t is not None
        assert t.prompt == _BRAINSTORM_PROMPT
        assert t.profile == "docs"

    def test_old_backlog_to_spec_edge_is_gone(self) -> None:
        """The former ``Backlog → Spec`` brainstorm+design edge no longer exists.

        The single step was split into Backlog→Brainstorming (interactive) and
        Brainstorming→Spec (autonomous design), so the direct Backlog→Spec move is
        now un-whitelisted (it would roll back).
        """
        cfg = load_transitions(_render_doc("owner/repo"))
        assert cfg.get("Backlog", "Spec") is None

    def test_brainstorming_to_spec_is_the_autonomous_design(self) -> None:
        """``Brainstorming → Spec`` carries the autonomous ``_DESIGN_PROMPT``."""
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("Brainstorming", "Spec")
        assert t is not None
        assert t.prompt == _DESIGN_PROMPT
        assert t.profile == "docs"

    def test_spec_to_plan_is_the_plan_step(self) -> None:
        """``Spec → Plan`` carries the autonomous ``_PLAN_PROMPT``."""
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("Spec", "Plan")
        assert t is not None
        assert t.prompt == _PLAN_PROMPT
        assert t.profile == "docs"

    def test_plan_to_planned_is_allowed_no_op(self) -> None:
        """``Plan → Planned`` is whitelisted with no action (autonomous work done; human review)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("Plan", "Planned")
        assert t is not None
        assert not t.has_action


class TestSkipToDone:
    """Genesis phase 26: the early skip-to-Done whitelist (bounded at ReadyToDev)."""

    # The six PRE-PrepareFeature columns that may skip straight to Done.
    _SKIP_SOURCES = ("Backlog", "Brainstorming", "Spec", "Plan", "Planned", "ReadyToDev")
    # The columns from which Done is NOT whitelisted (a worktree/branch exists → Cancel only).
    _NON_SKIP_SOURCES = ("PrepareFeature", "InProgress", "PRCI", "Review")

    def test_skip_to_done_is_a_single_list_expanded_entry(self) -> None:
        """The skip-to-Done ships as ONE list-expanded entry (six sources → Done, no action)."""
        rows = [t for t in DEFAULT_TRANSITIONS if t["to"] == "Done" and isinstance(t["from"], list)]
        assert len(rows) == 1
        row = rows[0]
        assert sorted(row["from"]) == sorted(self._SKIP_SOURCES)
        # No-op whitelist only: no prompt, no script.
        assert row.get("prompt") is None
        assert row.get("script") is None

    def test_six_skip_edges_resolve_to_no_op(self) -> None:
        """Each of the six skip sources → Done resolves to a whitelisted no-op (no rollback)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        for source in self._SKIP_SOURCES:
            t = cfg.get(source, "Done")
            assert t is not None, f"{source} → Done did not resolve (would roll back)"
            assert not t.has_action, f"{source} → Done must be a no-op, not a launch"

    def test_done_not_whitelisted_from_prepare_feature_onward(self) -> None:
        """Done is NOT whitelisted from PrepareFeature/InProgress/PRCI/Review (→ rollback)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        for source in self._NON_SKIP_SOURCES:
            assert cfg.get(source, "Done") is None, (
                f"{source} → Done must NOT be whitelisted (worktree exists → Cancel only)"
            )

    def test_prepare_feature_to_done_rolls_back_via_decide(self) -> None:
        """A live ``PrepareFeature → Done`` move yields ROLLBACK (the un-whitelisted bound).

        Exercises the real ``decide`` path against the shipped columns + default
        whitelist: the un-whitelisted pair bounces the card back to its origin.
        """
        import importlib.resources

        from kanbanmate.core.columns import load_columns
        from kanbanmate.core.decide import DecideContext, decide
        from kanbanmate.core.domain import ActionKind, Ticket, Transition
        from kanbanmate.core.transitions_defaults import default_transition_config

        text = (importlib.resources.files("kanbanmate.assets") / "columns.yml.tmpl").read_text(
            encoding="utf-8"
        )
        columns = load_columns(text)
        ticket = Ticket(item_id="i1", issue_number=1, title="t", column_key="Done")
        transition = Transition(ticket=ticket, from_column="PrepareFeature", to_column="Done")
        ctx = DecideContext(transitions=default_transition_config())
        action = decide(transition, columns, ctx)
        assert action.kind is ActionKind.ROLLBACK
        # ROLLBACK bounces back to the origin's DISPLAY NAME (defect 2): the baseline must equal
        # the snapshot NAME or the diff re-fires the rollback every poll.
        assert action.to_column == "Prepare feature"


# The production placeholder context — the EXACT 12 keys app/actions._launch_context supplies.
# Every shipped prompt must fill() cleanly against this (fail-loud on an unknown key).
# ``code`` is the BARE issue number (defect 3): helper calls like ``kanban-move {{code}} 'PR/CI'``
# require an int arg — a leading ``#`` makes ``#7`` a bash comment / fails ``int('#7')``.
_PROD_CTX: dict[str, object] = {
    "code": "7",
    "title": "[A1] My feature",
    "branch": "feat/my-feature",
    "ticket_body": "body",
    "script_output": "ci log",
    "issue_body": "linked",
    "comments": "c1\n---\nc2",
    "codename": "my-feature",
    "design_path": "docs/features/my-feature/DESIGN.md",
    "plan_paths": "docs/features/my-feature/plan/INDEX.md",
    "base_clone": "",
    "dev_repo_path": "",
}

_ALL_PROMPTS = (
    _BRAINSTORM_PROMPT,
    _DESIGN_PROMPT,
    _PLAN_PROMPT,
    _PREPARE_PROMPT,
    _IMPLEMENT_PROMPT,
    _FIXCI_PROMPT,
    _REVIEW_PROMPT,
)

# Every prompt EXCEPT the interactive brainstorm carries the hardening constants.
_NON_BRAINSTORM_PROMPTS = (
    _DESIGN_PROMPT,
    _PLAN_PROMPT,
    _PREPARE_PROMPT,
    _IMPLEMENT_PROMPT,
    _FIXCI_PROMPT,
    _REVIEW_PROMPT,
)


class TestHardenedPromptsFill:
    """§29.4: every prompt fills cleanly against the production placeholder context."""

    def test_every_prompt_fills_against_prod_context(self) -> None:
        """No shipped prompt references a placeholder absent from the launch context (fail-loud)."""
        for prompt in _ALL_PROMPTS:
            filled = fill(prompt, _PROD_CTX)  # raises KeyError on an unknown key
            assert "{{" not in filled, "a placeholder leaked unfilled"


class TestHardeningConstants:
    """§29.4: the shared constants land on the right prompts (IDENTITY-THEN-STATE, autonomy, …)."""

    def test_autonomy_on_all_non_brainstorm_incl_prepare(self) -> None:
        """The autonomy instruction is on EVERY non-brainstorm prompt, including prepare."""
        for prompt in _NON_BRAINSTORM_PROMPTS:
            assert "Run fully autonomously" in prompt
        # The interactive brainstorm is the one exception.
        assert "Run fully autonomously" not in _BRAINSTORM_PROMPT

    def test_identity_before_state_ordering(self) -> None:
        """IDENTITY-THEN-STATE: the IDENTITY block precedes the STATE CHECK in each prompt."""
        for prompt in _NON_BRAINSTORM_PROMPTS:
            assert "IDENTITY FIRST" in prompt
            assert "STATE CHECK" in prompt
            # Identity must appear BEFORE the state check (a misattributed agent must never verify
            # the wrong feature's shipped-ness).
            assert prompt.index("IDENTITY FIRST") < prompt.index("STATE CHECK")

    def test_absent_marker_self_backfill_rule(self) -> None:
        """The IDENTITY block carries the absent-marker self-backfill rule (title [CODE] wins)."""
        for prompt in _NON_BRAINSTORM_PROMPTS:
            assert "--set-field roadmap" in prompt

    def test_desync_protocol_on_all_non_brainstorm(self) -> None:
        """The DESYNC protocol (STOP, never guess, never touch another ticket) is present."""
        for prompt in _NON_BRAINSTORM_PROMPTS:
            assert "DESYNC PROTOCOL" in prompt

    def test_all_body_write_backs_via_kanban_update_body(self) -> None:
        """Every body-writing stage routes write-backs through kanban-update-body ONLY."""
        for prompt in (_BRAINSTORM_PROMPT, _DESIGN_PROMPT, _PLAN_PROMPT):
            assert "kanban-update-body" in prompt
            # The raw path is only ever mentioned to BAN it ("NEVER raw `gh issue edit`"), never as
            # an instruction.
            assert "gh issue edit" not in prompt or "NEVER raw `gh issue edit`" in prompt

    def test_brainstorm_appends_not_overwrites(self) -> None:
        """The brainstorm APPENDS under '## Brainstorm' and never overwrites the seed."""
        assert "--append-section '## Brainstorm'" in _BRAINSTORM_PROMPT
        assert "NEVER overwrite" in _BRAINSTORM_PROMPT

    def test_context_framed_as_not_the_spec(self) -> None:
        """{{issue_body}} AND {{comments}} are framed as related context — NOT the feature spec."""
        assert "NOT your feature spec" in _BRAINSTORM_PROMPT

    def test_design_and_plan_write_to_feature_folder(self) -> None:
        """Design/plan write to docs/features/<codename>/ (a rendered {{codename}} parameter)."""
        assert "docs/features/{{codename}}/" in _DESIGN_PROMPT
        assert "docs/features/{{codename}}/plan/" in _PLAN_PROMPT

    def test_fixci_labels_output_stale_and_rechecks(self) -> None:
        """_FIXCI_PROMPT labels {{script_output}} possibly-STALE + requires a live re-check."""
        assert "MAY BE STALE" in _FIXCI_PROMPT
        assert "ALREADY GREEN" in _FIXCI_PROMPT  # the green-already fast path

    def test_plan_and_prepare_preconditions(self) -> None:
        """_PLAN_PROMPT/_PREPARE_PROMPT guard an empty design/plan path as a DESYNC, not a guess."""
        assert "PRECONDITION" in _PLAN_PROMPT
        assert "{{design_path}}" in _PLAN_PROMPT
        assert "PRECONDITION" in _PREPARE_PROMPT
        assert "{{plan_paths}}" in _PREPARE_PROMPT

    def test_done_checklist_on_every_stage(self) -> None:
        """Each stage carries a 'DONE =' completion checklist + re-entry idempotence."""
        for prompt in _ALL_PROMPTS:
            assert "DONE =" in prompt
            assert "re-entry" in prompt.lower()


class TestDoneBlockedSplit:
    """§29.4: early stages exit shipped→Done; late stages (worktree exists) exit shipped→Blocked."""

    # Early stages: the agent's card lands in a pre-PrepareFeature column (Design→Spec,
    # Plan→Plan), where skip-to-Done IS whitelisted, so their prompt exits shipped→Done.
    _EARLY = (_DESIGN_PROMPT, _PLAN_PROMPT)
    # Late stages: the card sits in PrepareFeature onward and a worktree/branch/PR exists, so Done
    # is NOT whitelisted (would roll back) — they exit shipped→Blocked, never Cancel.
    _LATE = (_PREPARE_PROMPT, _IMPLEMENT_PROMPT, _FIXCI_PROMPT, _REVIEW_PROMPT)

    def test_early_stages_exit_shipped_to_done(self) -> None:
        """An early-stage shipped exit moves to Done (the skip-to-Done whitelist boundary)."""
        for prompt in self._EARLY:
            assert "kanban-move {{code}} Done" in prompt

    def test_early_shipped_move_is_mandatory_and_overrides_done_checklist(self) -> None:
        """Phase 39: the ALREADY_SHIPPED exit mandates the Done move and OVERRIDES the DONE checklist.

        Live #146 finding: the agent followed the literal ``DONE =`` checklist (which only listed the
        durable doc outputs) and ended WITHOUT moving the card. The shipped branch must now state the
        move is MANDATORY and overrides the normal checklist, and each ``DONE =`` line must spell out
        the ALREADY_SHIPPED completion so the two cannot be read as contradictory.
        """
        for prompt in self._EARLY:
            # The STATE CHECK marks the Done move MANDATORY and overriding the normal checklist.
            assert "MANDATORY" in prompt
            assert "OVERRIDES (replaces) the normal" in prompt
            # The DONE line restates the ALREADY_SHIPPED completion (no longer a contradiction).
            assert "ALREADY_SHIPPED case: DONE = evidence comment + card moved to Done" in prompt

    def test_late_stages_exit_shipped_to_blocked_not_cancel(self) -> None:
        """A late-stage shipped exit moves to Blocked (Cancel is operator-only)."""
        for prompt in self._LATE:
            assert "kanban-move {{code}} Blocked" in prompt
            assert "Cancel is operator-only" in prompt


class TestBrainstormStateCheck:
    """Phase 39b (R2, live #146): the FIRST stage gains a state-check-first shipped exit."""

    def test_brainstorm_has_state_check_first(self) -> None:
        """``_BRAINSTORM_PROMPT`` carries a STATE CHECK FIRST block (the cheapest catch)."""
        assert "STATE CHECK FIRST" in _BRAINSTORM_PROMPT

    def test_state_check_precedes_the_interactive_brainstorm(self) -> None:
        """The state check is placed BEFORE the interactive Q&A invitation."""
        assert _BRAINSTORM_PROMPT.index("STATE CHECK FIRST") < _BRAINSTORM_PROMPT.index(
            "MAY ask the user"
        )

    def test_shipped_exit_moves_to_done_and_is_mandatory(self) -> None:
        """The ALREADY_SHIPPED exit mandates the Done move and OVERRIDES the DONE checklist."""
        assert "kanban-move {{code}} Done" in _BRAINSTORM_PROMPT
        assert "MANDATORY" in _BRAINSTORM_PROMPT
        assert "OVERRIDES (replaces) the normal" in _BRAINSTORM_PROMPT
        # Posts the evidence FIRST, sets the codename marker, then ends WITHOUT brainstorming.
        assert "already shipped: <evidence>" in _BRAINSTORM_PROMPT
        assert "--set-field codename <the-shipped-codename>" in _BRAINSTORM_PROMPT
        assert "WITHOUT starting the interactive brainstorm" in _BRAINSTORM_PROMPT

    def test_done_line_restates_already_shipped_completion(self) -> None:
        """The DONE line spells out the ALREADY_SHIPPED completion (no contradiction)."""
        assert (
            "ALREADY_SHIPPED case: DONE = evidence comment + **codename** marker + card moved to "
            "Done" in _BRAINSTORM_PROMPT
        )

    def test_brainstorm_stays_interactive_on_the_non_shipped_path(self) -> None:
        """The non-shipped path is unchanged: the interactive Q&A is still allowed."""
        assert "MAY ask the user" in _BRAINSTORM_PROMPT
        assert "Run fully autonomously" not in _BRAINSTORM_PROMPT


class TestRecoveryEdges:
    """#12: the three operator-recovery edges — Review→InProgress, Planned→Spec, Done→Backlog."""

    def test_review_to_inprogress_rework_edge(self) -> None:
        """Review→InProgress is a LAUNCH (rework prompt) mirroring fix-CI: profile dev, advance auto:PRCI."""
        cfg = load_transitions(_render_doc("owner/repo"))
        rework = cfg.get("Review", "InProgress")
        assert rework is not None
        assert rework.prompt == _REWORK_PROMPT
        assert rework.profile == "dev"
        assert rework.advance == "auto:PRCI"
        # It mirrors the fix-CI pattern (advance auto:PRCI re-runs the CI gate after the push).
        fixci = cfg.get("PRCI", "InProgress")
        assert fixci is not None
        assert rework.advance == fixci.advance

    def test_rework_prompt_is_hardened_and_autonomous(self) -> None:
        """The rework prompt carries the hardened constants (scope guard, identity, autonomy)."""
        # Same hardening fingerprints the other hardened launch prompts carry.
        assert "ONLY" in _REWORK_PROMPT  # scope guard
        # BUG B: the rework prompt no longer self-moves into the SCRIPT-gate PR/CI column — that move
        # would slip the agent re-fire guard + suppress the gate diff. The engine's advance:auto:PRCI
        # backstop (asserted above) re-runs the CI gate after kanban-done; the do-not-move guard is explicit.
        assert "kanban-move {{code}} 'PR/CI'" not in _REWORK_PROMPT
        assert "DO NOT MOVE THE CARD" in _REWORK_PROMPT
        assert "kanban-done {{code}}" in _REWORK_PROMPT
        assert "{{codename}}" in _REWORK_PROMPT and "{{code}}" in _REWORK_PROMPT

    def test_planned_to_spec_is_a_noop(self) -> None:
        """Planned→Spec is a plain no-op (no agent launches on the edge — re-plan via Spec→Plan)."""
        cfg = load_transitions(_render_doc("owner/repo"))
        edge = cfg.get("Planned", "Spec")
        assert edge is not None
        assert edge.prompt is None
        assert edge.script is None

    def test_done_to_backlog_is_a_plain_noop_not_a_reset(self) -> None:
        """Done→Backlog is a PLAIN no-op whitelist edge — NOT a RESET (rank-7 correction).

        The whitelist schema has no `action:` field and RESET is hard-wired to the reactive Cancel
        column, so Done→Backlog cannot BE a RESET. It is a known no-op edge (no rollback) that does
        NOT wipe stale state — acceptable per the verdict (residual Done state is already rare).
        """
        cfg = load_transitions(_render_doc("owner/repo"))
        edge = cfg.get("Done", "Backlog")
        assert edge is not None
        assert edge.prompt is None
        assert edge.script is None
        # The only RESET path stays Cancel→Backlog (a reactive-column route, not this whitelist edge).
        assert cfg.get("Cancel", "Backlog") is not None

    def test_recovery_edges_added_nothing_else_changed(self) -> None:
        """The three recovery edges are present; the pre-existing edges are all still resolvable."""
        cfg = load_transitions(_render_doc("owner/repo"))
        # The three NEW edges resolve.
        assert cfg.get("Review", "InProgress") is not None
        assert cfg.get("Planned", "Spec") is not None
        assert cfg.get("Done", "Backlog") is not None
        # A spot-check of pre-existing edges still resolves (nothing was removed/broken).
        assert cfg.get("Backlog", "Brainstorming") is not None
        assert cfg.get("PrepareFeature", "InProgress") is not None
        assert cfg.get("Review", "Merge") is not None
        assert cfg.get("Merge", "Done") is not None


class TestHybridAdvanceDirectives:
    """Hybrid flow (DESIGN §13): the doc + build transitions carry the advance:auto:<col> directives
    the engine now honours; the two HUMAN gates (Planned, Review) MUST carry no auto-advance."""

    # Each forward transition's expected ``advance`` directive (the HYBRID table).
    _EXPECTED_ADVANCE = {
        ("Backlog", "Brainstorming"): "auto:Spec",
        ("Brainstorming", "Spec"): "auto:Plan",
        ("Spec", "Plan"): "auto:Planned",
        ("ReadyToDev", "PrepareFeature"): "auto:InProgress",
        ("PrepareFeature", "InProgress"): "auto:PRCI",
        ("InProgress", "PRCI"): "auto:Review",
        ("PRCI", "InProgress"): "auto:PRCI",
        ("PRCI", "Review"): "stop",
        ("Review", "InProgress"): "auto:PRCI",
    }

    def test_each_transition_advance_matches_the_hybrid_table(self) -> None:
        """Every forward transition carries exactly its HYBRID-table advance directive."""
        cfg = load_transitions(_render_doc("owner/repo"))
        for (from_col, to_col), expected in self._EXPECTED_ADVANCE.items():
            t = cfg.get(from_col, to_col)
            assert t is not None, f"{from_col} → {to_col} did not resolve"
            assert t.advance == expected, (
                f"{from_col} → {to_col} advance is {t.advance!r}, expected {expected!r}"
            )

    def test_human_gates_carry_no_auto_advance(self) -> None:
        """SAFETY ASSERTION: Plan→Planned and Planned→ReadyToDev MUST NOT auto-advance.

        Auto-advancing either would bypass the single pre-build HUMAN review gate (the core HYBRID
        property). They are no-ops, so their advance defaults to ``stop`` — which :func:`auto_advance_target`
        maps to ``None`` (no engine move).
        """
        from kanbanmate.bin._clone_config import auto_advance_target

        cfg = load_transitions(_render_doc("owner/repo"))
        for from_col, to_col in (("Plan", "Planned"), ("Planned", "ReadyToDev")):
            t = cfg.get(from_col, to_col)
            assert t is not None
            # No auto directive → the card STOPS at the human gate.
            assert auto_advance_target(t.advance) is None, (
                f"{from_col} → {to_col} must NOT carry an auto-advance directive (human gate)"
            )

    def test_review_stops_for_human(self) -> None:
        """PRCI→Review carries advance:stop — the Review human gate (no auto-advance past it)."""
        from kanbanmate.bin._clone_config import auto_advance_target

        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("PRCI", "Review")
        assert t is not None
        assert t.advance == "stop"
        assert auto_advance_target(t.advance) is None

    def test_inprogress_to_prci_script_gate_advances_to_review(self) -> None:
        """The InProgress→PRCI SCRIPT gate carries advance:auto:Review (green CI → fires pr-review).

        This directive is consumed by ``app/script_route._route_success`` (already wired) — the only
        SCRIPT-gate advance in the build arc.
        """
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("InProgress", "PRCI")
        assert t is not None
        assert t.script == "bin/check-pr-ready.sh"
        assert t.advance == "auto:Review"

    def test_default_config_still_parses_no_duplicate_pair(self) -> None:
        """``default_transition_config()`` still parses the hybrid table (no duplicate-pair error)."""
        from kanbanmate.core.transitions_defaults import default_transition_config

        cfg = default_transition_config()
        # Spot-check a hybrid directive landed through the real parser.
        assert cfg.get("Backlog", "Brainstorming").advance == "auto:Spec"  # type: ignore[union-attr]


class TestImplementStagePromptGuards:
    """Change 4 (DESIGN §13): _IMPLEMENT_PROMPT + _FIXCI_PROMPT carry the stop-at-PR / never-merge /
    CI-not-green-terminal / do-not-idle guards so the auto-chain stall at the source is reduced."""

    def test_implement_prompt_stops_at_pr_creation(self) -> None:
        """_IMPLEMENT_PROMPT carries an explicit STOP-AT-PR-CREATION guard."""
        assert "STOP AT PR CREATION" in _IMPLEMENT_PROMPT
        assert "STOP as soon as the PR is created" in _IMPLEMENT_PROMPT

    def test_implement_prompt_never_runs_gh_pr_merge(self) -> None:
        """_IMPLEMENT_PROMPT bans `gh pr merge` verbatim (merge is human-only)."""
        assert "NEVER run `gh pr merge`" in _IMPLEMENT_PROMPT

    def test_implement_prompt_ci_not_green_terminal_branch(self) -> None:
        """_IMPLEMENT_PROMPT carries a CI-not-green terminal branch (end on red/running, don't idle).

        BUG B: the agent must NOT idle waiting on CI, but it must ALSO NOT move the card itself —
        InProgress→PR/CI is a SCRIPT-gated transition the engine owns. On red/running CI the agent
        comments the failing checks then ENDS; the engine's advance:auto:PRCI backstop moves the card.
        """
        assert "CI-NOT-GREEN TERMINAL BRANCH" in _IMPLEMENT_PROMPT
        assert "do NOT idle waiting on CI" in _IMPLEMENT_PROMPT
        # On red/running: comment the failing checks, then END (no kanban-move). The gate owns retry.
        assert "you are DONE even if CI is still running or red" in _IMPLEMENT_PROMPT

    def test_implement_prompt_does_not_move_the_card_into_pr_ci(self) -> None:
        """BUG B: _IMPLEMENT_PROMPT no longer instructs the agent to move the card into PR/CI.

        InProgress→PR/CI is a SCRIPT-gate transition: an agent move into it would slip the
        prompt-only re-fire guard, advance the diff baseline past the edge, and skip the gate +
        auto:Review + ✅-finalize. The agent must STOP at PR creation + ``kanban-done`` only; the
        engine's ``advance:auto:PRCI`` backstop advances the card.
        """
        # The OLD instruction to move into PR/CI is GONE (any form: bare or ANYWAY).
        assert "kanban-move {{code}} 'PR/CI'" not in _IMPLEMENT_PROMPT
        # The explicit do-not-move guard is present, naming the script-gated ownership.
        assert "DO NOT MOVE THE CARD" in _IMPLEMENT_PROMPT
        assert "SCRIPT-gated" in _IMPLEMENT_PROMPT
        # The agent still ends via kanban-done (the engine then advances it).
        assert "kanban-done {{code}}" in _IMPLEMENT_PROMPT

    def test_fixci_prompt_never_merge_and_does_not_idle(self) -> None:
        """_FIXCI_PROMPT carries the never-merge + do-not-idle-on-CI terminal discipline."""
        assert "NEVER run `gh pr merge`" in _FIXCI_PROMPT
        assert "Do NOT idle waiting on CI" in _FIXCI_PROMPT
        # End via kanban-done even if CI is still running/red — the engine advances + re-gates.
        assert "even if CI is still running or still red" in _FIXCI_PROMPT
        # BUG B: the fix-CI prompt no longer self-moves into the SCRIPT-gate PR/CI column (the move
        # would slip the agent re-fire guard + suppress the gate diff); advance:auto:PRCI re-runs it.
        assert "kanban-move {{code}} 'PR/CI'" not in _FIXCI_PROMPT
        assert "DO NOT MOVE THE CARD" in _FIXCI_PROMPT


class TestDurableCarryPromptWording:
    """Change 3 (DESIGN §13): the design/plan prompts COMMIT their artifacts to the WIP branch and
    record REPO-RELATIVE markers (so the next worktree sees + can `cat` them)."""

    def test_design_prompt_commits_and_records_repo_relative(self) -> None:
        """_DESIGN_PROMPT commits DESIGN.md to the per-ticket branch + records a repo-relative marker."""
        assert "git add docs/features/{{codename}}/" in _DESIGN_PROMPT
        assert 'git commit -m "docs({{codename}}): design"' in _DESIGN_PROMPT
        # The recorded **design** marker is the REPO-RELATIVE path (not an absolute worktree path).
        assert "--set-field design docs/features/{{codename}}/DESIGN.md" in _DESIGN_PROMPT
        assert "REPO-RELATIVE" in _DESIGN_PROMPT

    def test_plan_prompt_commits_and_records_repo_relative(self) -> None:
        """_PLAN_PROMPT commits the plan files to the per-ticket branch + records repo-relative paths."""
        assert "git add docs/features/{{codename}}/" in _PLAN_PROMPT
        assert 'git commit -m "docs({{codename}}): plan"' in _PLAN_PROMPT
        assert "--set-field plans docs/features/{{codename}}/plan/" in _PLAN_PROMPT
        assert "REPO-RELATIVE" in _PLAN_PROMPT

    def test_commit_uses_separate_add_and_commit_not_compound(self) -> None:
        """Finding 1: the carry uses TWO SEPARATE commands, NOT a compound ``git add … && git commit``.

        The ``docs`` permission profile allows ``Bash(git add*)`` and ``Bash(git commit*)`` as
        DISTINCT allow-patterns under ``permission_mode: auto``; a single compound
        ``git add … && git commit …`` matches NEITHER and is denied headlessly, silently breaking
        the carry. Lock the separate form in for both doc prompts.
        """
        for prompt in (_DESIGN_PROMPT, _PLAN_PROMPT):
            assert "&& git commit" not in prompt
            # The numbered ADD step comes before the numbered COMMIT step (staged tree → commit).
            assert prompt.index("1. `git add docs/features/{{codename}}/`") < prompt.index(
                '2. `git commit -m "docs({{codename}}):'
            )

    def test_commit_guards_empty_codename(self) -> None:
        """Finding 3: the prompt guards against an empty codename (would stage the whole tree)."""
        for prompt in (_DESIGN_PROMPT, _PLAN_PROMPT):
            # The add/commit is gated on the codename'd dir existing — prose-level guard.
            assert "empty codename" in prompt
            assert "docs/features/{{codename}}/ exists" in prompt

    def test_plan_precondition_validates_carried_design_path(self) -> None:
        """_PLAN_PROMPT's precondition now describes a repo-relative, cat-able carried design path."""
        assert "{{design_path}}" in _PLAN_PROMPT
        assert "cat {{design_path}}" in _PLAN_PROMPT


class TestCleanStopInstruction:
    """firm-exit: the ``_CLEAN_STOP`` discipline lands in every prompt whose terminal step is
    ``kanban-done`` (8 prompts), so the reaper's end_session lands on an EMPTY idle prompt with no
    background shells — reducing the helm #5 leftover-box + "N shells running" condition at the source."""

    # Every prompt template whose terminal step is ``kanban-done {{code}}``.
    _DONE_PROMPTS = (
        _BRAINSTORM_PROMPT,
        _DESIGN_PROMPT,
        _PLAN_PROMPT,
        _PREPARE_PROMPT,
        _IMPLEMENT_PROMPT,
        _FIXCI_PROMPT,
        _REVIEW_PROMPT,
        _REWORK_PROMPT,
    )

    def test_clean_stop_present_in_all_done_prompts(self) -> None:
        """The clean-stop instruction appears in each of the 8 done-prompts (substring check)."""
        for prompt in self._DONE_PROMPTS:
            assert "END your turn IMMEDIATELY" in prompt
            assert "do NOT leave background shells running" in prompt

    def test_clean_stop_lands_after_kanban_done(self) -> None:
        """The clean-stop text comes AFTER the prompt's ``kanban-done`` line (run, THEN stop)."""
        for prompt in self._DONE_PROMPTS:
            assert "kanban-done" in prompt
            assert prompt.index("kanban-done") < prompt.index("END your turn IMMEDIATELY")

    def test_default_transitions_prompts_still_carry_kanban_done(self) -> None:
        """Regression: every done-prompt still ENDS the agent with ``kanban-done {{code}}`` and the
        ``_CLEAN_STOP`` text did not drop OR inflate any ``/implement:*`` slash-command in the prompts.

        The clean-stop wording is now GENERIC ("the next-stage slash command", no literal
        ``/implement:…`` example), so it must NOT change the per-prompt slash-command counts that
        :class:`TestSlashCommands` pins. We assert the ``kanban-done {{code}}`` terminal step survives
        and the brainstorm/plan/prepare/implement prompts keep exactly their own slash-command.
        """
        for prompt in self._DONE_PROMPTS:
            assert "kanban-done {{code}}" in prompt
        # The slash-command-bearing prompts keep THEIR command; _CLEAN_STOP no longer injects any
        # /implement: substring (the literal example is gone — adversarial-review fix).
        assert "/implement:brainstorm" in _BRAINSTORM_PROMPT
        assert "/implement:plan" in _PLAN_PROMPT
        assert "/implement:create-branch" in _PREPARE_PROMPT
        assert "/implement:phase" in _IMPLEMENT_PROMPT
        assert "/implement:pr-review" in _REVIEW_PROMPT
        # _DESIGN_PROMPT carries NO next-stage slash-command — back to its ORIGINAL count of 0 now
        # that the illustrative /implement:plan is removed from the clean-stop wording.
        assert _DESIGN_PROMPT.count("/implement:") == 0

    def test_clean_stop_wording_carries_no_literal_implement_command(self) -> None:
        """Adversarial-review fix: the clean-stop wording is GENERIC — no literal ``/implement:…``.

        The old ``(e.g. /implement:plan)`` example was ironic in a "don't type the next command"
        instruction and injected a spurious /implement: substring into prompts (e.g. _DESIGN_PROMPT)
        that legitimately carry none. The generic phrase "next-stage slash command" replaces it.
        """
        assert "(e.g. /implement:plan)" not in _DESIGN_PROMPT
        for prompt in self._DONE_PROMPTS:
            assert "next-stage slash command" in prompt

    def test_alternative_terminal_exits_carry_clean_stop_discipline(self) -> None:
        """firm-exit consistency (Finding 4): EVERY path that ends a session with ``kanban-done``
        then stops carries the clean-stop discipline — not just the 8 main stage prompts.

        The shared STATE-CHECK (early/late) shipped-exits and the DESYNC protocol all terminate with
        ``kanban-done`` then stop, so they MUST also tell the agent to END its turn (do NOT run the
        next-stage slash command) and leave no trailing-`&` background shells.
        """
        for exit_block in (_STATE_CHECK_EARLY, _STATE_CHECK_LATE, _DESYNC):
            assert "kanban-done {{code}}" in exit_block
            assert "END your turn" in exit_block
            assert "next-stage slash command" in exit_block
            assert "background shells" in exit_block
        # The brainstorm prompt's inline STATE-CHECK-FIRST shipped-exit also ends in kanban-done +
        # stop, so it carries the discipline too (it is not built from the shared constants above).
        assert "WITHOUT starting the interactive brainstorm" in _BRAINSTORM_PROMPT
        assert "next-stage slash command" in _BRAINSTORM_PROMPT
