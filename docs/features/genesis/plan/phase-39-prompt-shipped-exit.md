# Phase 39 — Prompt shipped-exit mandates the Done move (early stages)

Live e2e on #146 surfaced a contradiction in the hardened early-stage launch prompts
(`src/kanbanmate/core/transitions_defaults.py`): the shared `_STATE_CHECK_EARLY` block told the
agent to post the ALREADY_SHIPPED evidence comment FIRST and then `kanban-move <issue> Done`, but
the prompt's trailing `DONE =` checklist only listed the durable doc outputs (DESIGN.md / plan files

- marker) and "End the session" — it OMITTED the Done move. The #146 agent posted the verdict +
  markers, followed the literal `DONE =` checklist, and ended WITHOUT moving the card, forcing an
  operator nudge. The fix is prompt-text only and surgical: `_STATE_CHECK_EARLY` (carried by
  `_DESIGN_PROMPT` and `_PLAN_PROMPT` — the only early-stage prompts that use it; the interactive
  `_BRAINSTORM_PROMPT` does not) now states the Done move is MANDATORY and OVERRIDES (replaces) the
  normal DONE checklist, so the shipped exit is not complete until the card is actually in Done; and
  each of those two `DONE =` lines now restates the ALREADY_SHIPPED completion ("DONE = evidence
  comment + card moved to Done — see STATE CHECK above, which OVERRIDES this checklist") so the two
  can no longer be read as contradictory. Placeholders are untouched (the existing
  `TestHardenedPromptsFill.test_every_prompt_fills_against_prod_context` fail-loud `fill()` test still
  passes), and a new `TestDoneBlockedSplit.test_early_shipped_move_is_mandatory_and_overrides_done_checklist`
  pins the wording. Gate: `rm -rf .mypy_cache && make check` green.

**39b (R2, live #146):** the interactive `_BRAINSTORM_PROMPT` — the FIRST stage, the cheapest place to
catch already-shipped work — gained a STATE CHECK FIRST block (placed before the interactive Q&A): if
repo-local evidence shows ALREADY_SHIPPED, post the evidence, set the **codename** marker, then the
MANDATORY `kanban-move {{code}} Done` (OVERRIDES the DONE checklist, same wording 39 added), then end
WITHOUT brainstorming; the non-shipped path is unchanged. New `TestBrainstormStateCheck` pins it.
