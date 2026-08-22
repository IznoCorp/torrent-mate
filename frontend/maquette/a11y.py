#!/usr/bin/env python3
"""Does the maquette have an accessibility defect an automated audit can see?

Lot **L03** of `docs/reference/frontend-architecture.md` — Phase 1, the
instrument. The lot's own « Done when » requires an automated audit in the gate,
and this is it.

WHY AN EXTERNAL INSTRUMENT RATHER THAN A HOUSE RULE
---------------------------------------------------
A rule proves the list of criteria someone wrote into it, and nothing else. This
repository has paid for that twice: `check-no-french.py` reported « no
violation » because its word list had holes, and the correction was to turn the
question around rather than to lengthen the list. `axe-core` is a body of
accessibility criteria maintained by people who do nothing else — it finds what
we did not think of, which is the only kind of finding a gate is worth having.

WHAT IT DOES NOT SEE, SAID HERE RATHER THAN DISCOVERED LATER
-------------------------------------------------------------
An automated audit reads the markup of ONE MOMENT. Focus management is a
SEQUENCE — focus enters a layer, the background goes inert, focus comes back to
the trigger — and no static audit can observe it. That is measured by a harness
rule of its own, and the two instruments are not redundant. Neither can a
machine judge whether an announcement is USEFUL: this file proves a live region
is well formed, never that it says something worth hearing.

COLOUR CONTRAST IS MEASURED AND IS NOT THE FLOOR
-------------------------------------------------
Decision D-L03-4: `color-contrast` findings target the palette, which is L06's
subject. They are recorded in their own file and handed over; they never fail
this gate. « Not measured » would read as « no problem », which is what this
repository refuses — so it is measured, and separated.

WHY IT BORROWS THE ORACLE'S PLUMBING
-------------------------------------
`oracle.py` already knows how to open the prototype at the right viewport,
refuse to measure at the wrong one, neutralise the prototype's own chrome, and
wait until the frame is AT REST by fact rather than by duration. An audit taken
mid-animation reports a control that is not there yet. Importing it keeps ONE
recipe: a second copy would drift, and the drift would be silent.

Usage:
    python3 frontend/maquette/a11y.py --record    # write the debt files
    python3 frontend/maquette/a11y.py --check     # fail on any violation
    python3 frontend/maquette/a11y.py --check --rules button-name,label
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time

import oracle

ROOT = pathlib.Path(__file__).resolve().parent
AXE_BUNDLE = ROOT / "design" / "node_modules" / "axe-core" / "axe.min.js"
DEBT_FILE = ROOT / "a11y-debt.json"
CONTRAST_FILE = ROOT / "a11y-contrast.json"

# The rule whose findings are RECORDED and never enforced here (D-L03-4).
CONTRAST_RULE = "color-contrast"

# What the audit reads, and what it deliberately does not.
#
# `.hbtn` is the harness's own bar (the notes button and the scenario button):
# measuring apparatus, shipped in no application, and auditing it would put this
# floor at the mercy of a control the product does not have. The exclusion is
# WRITTEN DOWN for the same reason every other exemption in this repository is:
# an implicit one is indistinguishable from an oversight.
#
# THE CONTEXT IS THE WHOLE DOCUMENT, AND THAT IS NOT A DETAIL. The first version
# of this file scoped the audit to `.device`, the phone frame — the product, and
# an entirely reasonable-looking choice. Measured, it made FIVE page-level rules
# `inapplicable`: `landmark-one-main`, `page-has-heading-one`, `region`,
# `document-title` and `html-has-lang` evaluate against a DOCUMENT and silently
# stand down when handed a subtree. The gate reported « 0 violation » for
# `landmark-one-main` on a prototype with zero `<main>` elements. Audited whole,
# three of the five fall on the spot. A narrowed context does not narrow what is
# checked — it narrows what is CHECKABLE, and says nothing about the difference.
AXE_CONTEXT = {"exclude": [[".hbtn"]]}

# Only violations. `incomplete` is axe's « a human must look at this », and a
# gate that fails on those fails on questions rather than on defects.
AXE_OPTIONS = {"resultTypes": ["violations"]}

# TWO RULES DESCRIBE THE DOCUMENT AT REST, and a modal layer is not rest.
#
# `landmark-one-main` and `page-has-heading-one` ask a question about the whole
# page: is there a main region, is there a level-one heading. When a modal layer
# is open the answer is legitimately « not reachable » — the focus manager marks
# everything behind the layer `inert`, which removes it from the accessibility
# tree, and that is the correct behaviour rather than a defect. axe then reports
# a document with no main, on a document whose main is deliberately unreachable.
#
# THIS IS A CONDITION, NOT A LIST OF EXCEPTED STATES, and the difference is the
# whole reason it is acceptable. Nothing is named here — the audit asks the
# document whether a modal layer is open and answers accordingly, so a state
# that stops opening one is measured again with no edit to this file. And the
# split is PRINTED at the end of every run: a number nobody compares is a number
# nobody reads, and « quietly skipped » is how a floor becomes decorative.
DOCUMENT_RULES = ("landmark-one-main", "page-has-heading-one")

MODAL_OPEN = """()=>Boolean(document.querySelector('[role="dialog"][data-open],'
  + ' [aria-modal="true"][data-open], #drawer[data-open], #dlg[data-open]'))"""

RUN_AXE = """async ([options])=>{
  const result = await window.axe.run(options.context, options.run);
  return result.violations.map((violation)=>({
    rule: violation.id,
    impact: violation.impact,
    help: violation.help,
    targets: violation.nodes.map((node)=>String(node.target)).sort(),
  }));
}"""


def axe_bundle() -> str:
    """Returns the `axe-core` source, and says what to do when it is absent.

    Returns:
        The text of `axe.min.js`.

    Raises:
        SystemExit: When the bundle is not installed, naming the command rather
            than leaving a `FileNotFoundError` to be decoded.
    """
    if not AXE_BUNDLE.is_file():
        raise SystemExit(
            f"{AXE_BUNDLE} is missing — axe-core is not installed.\n"
            "    npm install --prefix frontend/maquette/design"
        )
    return AXE_BUNDLE.read_text(encoding="utf-8")


def split_contrast(findings: list) -> tuple[list, list]:
    """Separates the enforced findings from the ones handed to L06.

    Args:
        findings: What one state's audit returned.

    Returns:
        A `(enforced, contrast)` pair.
    """
    enforced = [f for f in findings if f["rule"] != CONTRAST_RULE]
    contrast = [f for f in findings if f["rule"] == CONTRAST_RULE]
    return enforced, contrast


async def audit_state(page, state: str, regions: dict, recipe: dict,
                      rules: list | None) -> list:
    """Drives one named state and audits it once it is at rest.

    Args:
        page: The page being driven.
        state: A state id `window.__go` accepts.
        regions: The region table — the geometry the settle signal watches.
        recipe: The oracle's `probe` block.
        rules: When given, the only axe rules to run.

    Returns:
        A `(modal, findings)` pair — whether a modal layer was open, which says
        which rules could be asked, and the findings sorted by rule so the
        output is stable.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    # The same two-pass neutralise-and-settle the oracle uses, and for the same
    # measured reason: the boot toast is raised asynchronously, so a single pass
    # loses the race on the first state driven.
    await oracle.neutralise(page, recipe)
    await oracle.settle(page, regions)
    await oracle.neutralise(page, recipe)
    await oracle.settle(page, regions)

    run = dict(AXE_OPTIONS)
    if rules:
        run["runOnly"] = {"type": "rule", "values": rules}
    modal = await page.evaluate(MODAL_OPEN)
    if modal:
        run["rules"] = {name: {"enabled": False} for name in DOCUMENT_RULES}
    findings = await page.evaluate(
        RUN_AXE, [{"context": AXE_CONTEXT, "run": run}])
    return modal, sorted(findings, key=lambda f: (f["rule"], f["targets"]))


async def audit_everything(rules: list | None) -> tuple:
    """Drives every named state once and audits each of them.

    Returns:
        A `(per_state, states, seconds, modal_states)` tuple. `modal_states` is
        the set measured with a modal layer open, and therefore without the two
        document-level rules.
    """
    started = time.monotonic()
    recipe, regions = oracle.load_recipe(), oracle.load_regions()
    bundle = axe_bundle()
    async with oracle.browser_driver()() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await oracle.open_frame(browser, recipe)
        # Injected once per page, after the frame is open: `add_init_script`
        # would re-inject on every navigation, and the prototype navigates.
        await page.add_script_tag(content=bundle)
        states = await page.evaluate("()=>window.__states()")
        per_state, modal_states = {}, set()
        for state in states:
            modal, findings = await audit_state(
                page, state, regions, recipe, rules)
            per_state[state] = findings
            if modal:
                modal_states.add(state)
        await context.close()
        await browser.close()
    return per_state, states, time.monotonic() - started, modal_states


def tally(per_state: dict) -> dict:
    """Counts findings per rule across every state.

    Args:
        per_state: The audit's output, keyed by state id.

    Returns:
        A rule -> occurrence-count mapping, ordered by rule name.
    """
    counts: dict[str, int] = {}
    for findings in per_state.values():
        for finding in findings:
            counts[finding["rule"]] = counts.get(finding["rule"], 0) + len(
                finding["targets"])
    return dict(sorted(counts.items()))


def report(payload: dict, what: str) -> str:
    """Renders one debt file, deterministically.

    Args:
        payload: The `{state: findings}` mapping.
        what: The `$comment` this file carries about itself.

    Returns:
        The file's text, newline-terminated.
    """
    document = {
        "$comment": what,
        "takenAtCommit": oracle.base_commit(),
        "platform": oracle.fingerprint(),
        "counts": {"states": len(payload), "byRule": tally(payload)},
        "states": {state: payload[state] for state in sorted(payload)},
    }
    return json.dumps(document, indent=2, ensure_ascii=False,
                      sort_keys=False) + "\n"


async def record() -> int:
    """Writes the debt record, once, and refreshes the contrast handover.

    `a11y-debt.json` IS A STARTING LINE AND NOT A SNAPSHOT, so this refuses to
    overwrite one that exists. The distinction is not pedantry: run on a tree
    where the wave has done its work, `--record` writes zeros over the only
    record of what the wave found — measured, by walking into it — and the
    figure a future reader needs is gone with no trace that it ever existed.

    `a11y-contrast.json` is the opposite kind of file: a live handover to L06,
    refreshed every time, because what matters there is what is owed NOW.

    Returns:
        A process exit code.
    """
    per_state, states, seconds, modal = await audit_everything(None)
    enforced = {s: split_contrast(f)[0] for s, f in per_state.items()}
    contrast = {s: split_contrast(f)[1] for s, f in per_state.items()}

    if DEBT_FILE.exists():
        print(f"{DEBT_FILE.name} exists and is LEFT ALONE — it is a starting "
              "line, not a snapshot. Delete it deliberately if a new wave is "
              "opening its own record.")
    else:
        DEBT_FILE.write_text(report(
            enforced,
            "The accessibility debt of the maquette as L03 found it — one entry "
            "per named state, listing every axe-core violation and the elements "
            "it names. THIS IS A RECORD, NEVER A TOLERANCE: `--check` compares "
            "against zero, not against this file. `color-contrast` is not here; "
            "it is in a11y-contrast.json, handed to L06 by D-L03-4."),
            encoding="utf-8")
    CONTRAST_FILE.write_text(report(
        contrast,
        "The `color-contrast` findings, measured and deliberately NOT enforced "
        "by L03's gate: they target the palette, which is L06's subject. "
        "Recorded rather than skipped, because « not measured » reads as « no "
        "problem »."),
        encoding="utf-8")

    print(f"measured {len(states)} states in {seconds:.1f}s")
    print(f"  {len(states) - len(modal)} state(s) asked the document rules "
          f"{DOCUMENT_RULES}; {len(modal)} had a modal layer open and could not")
    print(f"  measured now: {sum(tally(enforced).values())} violation(s) over "
          f"{len(tally(enforced))} rule(s)")
    print(f"  {CONTRAST_FILE.name}: "
          f"{sum(tally(contrast).values())} contrast finding(s)")
    return 0


async def check(rules: list | None, enforce: bool) -> int:
    """Audits every state and reports, failing when the floor is armed.

    Args:
        rules: When given, the only axe rules to run — how a phase enforces the
            part it owns before the rest is clean.
        enforce: Exit non-zero on any enforced violation. THE FLOOR IS A HARD
            ZERO — no threshold, no tolerated list, no baseline file to compare
            against. `a11y-debt.json` records where the wave started and is
            never consulted here: a debt file a gate reads is a tolerance, and
            a tolerance is how a floor stops being one.

    Returns:
        A process exit code.
    """
    per_state, states, seconds, modal = await audit_everything(rules)
    enforced = {s: split_contrast(f)[0] for s, f in per_state.items()}
    contrast_total = sum(
        len(f["targets"]) for findings in per_state.values()
        for f in findings if f["rule"] == CONTRAST_RULE)

    for state in sorted(enforced):
        findings = enforced[state]
        if not findings:
            continue
        print(f"■ {state}")
        for finding in findings:
            print(f"    {finding['rule']} ({finding['impact']}) — "
                  f"{len(finding['targets'])}× — {finding['help']}")
            for target in finding["targets"][:4]:
                print(f"        {target}")

    counts = tally(enforced)
    total = sum(counts.values())
    scope = f", rules: {','.join(rules)}" if rules else ""
    print(f"a11y: {len(states)} states{scope}, {total} violation(s) over "
          f"{len(counts)} rule(s), in {seconds:.1f}s")
    print(f"a11y: {len(states) - len(modal)} state(s) asked "
          f"{'/'.join(DOCUMENT_RULES)}; {len(modal)} had a modal layer open, "
          "whose `inert` background is correct and makes those two unanswerable")
    if contrast_total and not rules:
        print(f"a11y: {contrast_total} colour-contrast finding(s) — recorded "
              f"for L06, not part of this floor (D-L03-4)")
    if total and enforce:
        return 1
    if total:
        print("a11y: --record-only, so this run REPORTS and does not refuse. "
              "The floor is zero.")
    return 0


def main(argv=None) -> int:
    """Parses the command line and dispatches to a mode."""
    parser = argparse.ArgumentParser(
        description="axe-core over the maquette's named states.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true",
                      help="write a11y-debt.json and a11y-contrast.json")
    mode.add_argument("--check", action="store_true",
                      help="audit every state and report what was found")
    parser.add_argument("--rules", metavar="R1,R2",
                        help="restrict the audit to these axe rules")
    parser.add_argument("--record-only", action="store_true",
                        help="report without failing. Nothing in this "
                             "repository passes it: it exists so a wave can "
                             "SEE a count while it burns one down, and a run "
                             "that uses it says so on its own last line")
    arguments = parser.parse_args(argv)
    rules = ([r.strip() for r in arguments.rules.split(",") if r.strip()]
             if arguments.rules else None)
    if arguments.record:
        return asyncio.run(record())
    return asyncio.run(check(rules, not arguments.record_only))


if __name__ == "__main__":
    sys.exit(main())
