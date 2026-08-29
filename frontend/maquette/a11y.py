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
is well formed, never that it says something worth hearing. It used to measure the
theme the prototype renders BY DEFAULT and nothing else, so a finding that
existed only under the other one was outside what this floor claimed — B-055,
and 154 such findings were counted by hand during L06 by someone who set
`data-theme="light"` themselves.

BOTH THEMES ARE DRIVEN SINCE L10-bis, AND THE ALTERNATIVE WAS REFUSED FOR THIS
FILE'S OWN REASON. The other route on the table was a lighter arm auditing
palette PAIRS under the light theme — a house rule, proving the list of criteria
someone wrote into it and nothing else, which is exactly what the section above
argues against and exactly how `check-no-french.py` came to report « no
violation » over a hundred and forty French names. Driving axe twice costs a
second pass and buys the same body of criteria on both themes.

THE LIGHT THEME IS MEASURED AND RECORDED, NOT YET ENFORCED, and that split is
the one this file already took rather than a new indulgence: D-L03-4 measured colour
contrast, wrote it to a file of its own and kept it out of the enforced set,
because « not measured » would have read as « no problem ». The dark floor stays
a HARD ZERO. The light count is held by a RATCHET that may only go down —
`a11y-light-debt.json` — so the campaign that burns it down is a lot with its own
design, and nothing can quietly add to it in the meantime.

COLOUR CONTRAST IS PART OF THE FLOOR
-------------------------------------
It was not always. Decision D-L03-4 measured `color-contrast`, recorded it in a
file of its own and kept it out of the enforced set, because the repair was a
PALETTE decision and the palette belonged to a later lot. « Not measured » would
have read as « no problem », which is what this repository refuses — so it was
measured, and separated.

Decision D-L06-5 spent that handover: the palette was repaired and the count
reached zero, so the rule joined the floor. `--check` now counts contrast in the
same hard zero as every other rule. The separate file is still written by
`--record`, and it is worth more than a deletion would be: it proves the debt is
EMPTY rather than that nobody looked. An empty debt left unenforced is how it
comes back.

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
# THE LIGHT THEME'S RATCHET. It is a CEILING and never a floor: the count it
# holds may fall and may not rise, so the campaign that repairs the palette is a
# lot of its own while nothing can add to the debt in the meantime. Refreshed by
# `--record`, and READ by `--check`, which is the difference from
# `a11y-debt.json` — that one is a starting line the gate never consults,
# because a debt file a gate reads is a tolerance. This one is read on purpose
# and says so: a tolerance that only tightens is a ratchet.
LIGHT_DEBT_FILE = ROOT / "a11y-light-debt.json"

# How the prototype is put into the light theme. The engine's own seam, so the
# audit and the interface agree about what « light » means rather than each
# deciding — `legacy.js` sets exactly this attribute from the appearance
# control, and removing it is what the default (dark) is.
LIGHT_THEME = """(on) => {
  if (on) document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
  return document.documentElement.getAttribute("data-theme");
}"""

# The rule `--record` keeps in a file of its own (D-L06-5). It is NOT carved out
# of `--check`: the floor counts it like every other rule.
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
    """Separates the contrast findings from the rest, for `record()`'s files.

    This is a RECORDING split and not an enforcement one: `check()` counts
    every finding, contrast included.

    Args:
        findings: What one state's audit returned.

    Returns:
        A `(rest, contrast)` pair.
    """
    enforced = [f for f in findings if f["rule"] != CONTRAST_RULE]
    contrast = [f for f in findings if f["rule"] == CONTRAST_RULE]
    return enforced, contrast


async def audit_state(page, state: str, recipe: dict,
                      rules: list | None, light: bool = False) -> tuple:
    """Drives one named state and audits it once it is at rest.

    Args:
        page: The page being driven.
        state: A state id `window.__go` accepts.
        recipe: The oracle's `probe` block.
        rules: When given, the only axe rules to run.
        light: Re-apply the light theme after driving the state. It is done
            AFTER `__go` and not before, because several scenarios re-render the
            shell and put the appearance back.

    Returns:
        A `(modal, findings)` pair — whether a modal layer was open, which says
        which rules could be asked, and the findings sorted by rule so the
        output is stable.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    # AFTER `__go`, NEVER BEFORE. Several scenarios call `applyState`, which
    # re-renders the shell and re-applies the appearance the state declares; a
    # theme set once before the loop is a theme the audit believes it is
    # measuring while the interface has put it back.
    if light:
        await page.evaluate(LIGHT_THEME, True)
    # The same two-pass neutralise-and-settle the oracle uses, and for the same
    # measured reason: the boot toast is raised asynchronously, so a single pass
    # loses the race on the first state driven.
    #
    # WITHOUT THE REGIONS, AND THAT IS THE WHOLE DIFFERENCE FROM THE ORACLE.
    # Handed a region table, `settle()` additionally requires the measured
    # GEOMETRY to be identical across two consecutive samples, and refuses
    # outright when it is not — the right demand for an instrument that records
    # rectangles, and the wrong one here. This audit reads the accessibility
    # tree: a control has its name and its role whether or not its box has
    # stopped moving to the last sub-pixel.
    #
    # It is not a theoretical distinction. This tier runs in CI, where the
    # oracle deliberately never does, so its geometry loop had never been
    # exercised on a Linux runner — and there the frame does not come to rest
    # within eight samples. The audit failed with « the measured geometry still
    # moved », about a difference it does not measure. What is still waited for
    # is the finite animations and two frames, which is what stops a control
    # being audited before it exists.
    await oracle.neutralise(page, recipe)
    await oracle.settle(page)
    await oracle.neutralise(page, recipe)
    await oracle.settle(page)

    run = dict(AXE_OPTIONS)
    if rules:
        run["runOnly"] = {"type": "rule", "values": rules}
    modal = await page.evaluate(MODAL_OPEN)
    if modal:
        run["rules"] = {name: {"enabled": False} for name in DOCUMENT_RULES}
    findings = await page.evaluate(
        RUN_AXE, [{"context": AXE_CONTEXT, "run": run}])
    return modal, sorted(findings, key=lambda f: (f["rule"], f["targets"]))


async def audit_everything(rules: list | None, light: bool = False) -> tuple:
    """Drives every named state once and audits each of them.

    Args:
        rules: When given, the only axe rules to run.
        light: Drive the LIGHT theme instead of the default. The attribute is
            re-applied after every state, because `window.__go` re-renders and
            several scenarios reset the appearance — a theme set once at the
            start is a theme the audit believes it is measuring.

    Returns:
        A `(per_state, states, seconds, modal_states)` tuple. `modal_states` is
        the set measured with a modal layer open, and therefore without the two
        document-level rules.

    Raises:
        RuntimeError: When the light theme was asked for and the attribute did
            not take. An audit that silently measured the dark theme twice would
            report the dark theme's zero and call it two themes clean — which is
            the whole defect B-055 records, arriving by a new road.
    """
    started = time.monotonic()
    recipe = oracle.load_recipe()
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
            modal, findings = await audit_state(page, state, recipe, rules,
                                                light=light)
            per_state[state] = findings
            if modal:
                modal_states.add(state)
        if light:
            applied = await page.evaluate(LIGHT_THEME, True)
            if applied != "light":
                raise RuntimeError(
                    "the light theme was asked for and `data-theme` reads "
                    f"{applied!r}. Measuring the dark theme twice and reporting "
                    "it as two themes is B-055 arriving by a new road.")
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
        "counts": {"states": len(payload), "byRule": tally(payload),
                   # THE TOTAL, written down rather than re-derived. The
                   # ratchet reads this file, and a reader that has to sum a
                   # map to learn the number is a reader that can sum it
                   # differently from the writer.
                   "total": sum(tally(payload).values())},
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

    `a11y-contrast.json` is the opposite kind of file: refreshed every time,
    because what matters there is what is owed NOW. What is owed is nothing —
    the rule is enforced — and the file is what says so.

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
        "The `color-contrast` findings, kept in a record of their own. D-L03-4 "
        "measured them and left them out of the floor, because the repair was "
        "a palette decision; D-L06-5 made the repair and armed the rule, so "
        "`--check` now counts contrast in the same hard zero as everything "
        "else. THIS IS NOT A TOLERANCE — it is the proof that the debt is "
        "empty, which « no file » could never be."),
        encoding="utf-8")

    print(f"measured {len(states)} states in {seconds:.1f}s")
    print(f"  {len(states) - len(modal)} state(s) asked the document rules "
          f"{DOCUMENT_RULES}; {len(modal)} had a modal layer open and could not")
    print(f"  measured now: {sum(tally(enforced).values())} violation(s) over "
          f"{len(tally(enforced))} rule(s)")
    print(f"  {CONTRAST_FILE.name}: "
          f"{sum(tally(contrast).values())} contrast finding(s)")

    # THE LIGHT THEME'S RECORD, and the number in it is what `--check`'s ratchet
    # reads. Refreshed on every `--record`, unlike `a11y-debt.json`, because it
    # is a CEILING to be lowered rather than a starting line to be preserved.
    light_per_state, _, light_seconds, _ = await audit_everything(None, light=True)
    light_total = sum(tally(light_per_state).values())
    LIGHT_DEBT_FILE.write_text(report(
        light_per_state,
        "The accessibility findings under `data-theme=\"light\"`, which this "
        "tier drove for nobody until L10-bis: it measured the DEFAULT theme "
        "only, so 154 findings counted by hand during L06 were invisible to it "
        "(B-055). THIS FILE IS READ BY `--check` AND THAT IS DELIBERATE — it is "
        "a RATCHET, a ceiling that may fall and may not rise, not the tolerance "
        "`a11y-debt.json` refuses to be. The dark floor stays a hard zero; "
        "remediating this list is a campaign with its own design, and what is "
        "held here meanwhile is that nothing is ADDED to it."),
        encoding="utf-8")
    print(f"  {LIGHT_DEBT_FILE.name}: {light_total} finding(s) under the light "
          f"theme, in {light_seconds:.1f}s — this is the ceiling `--check` reads")
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

    for state in sorted(per_state):
        findings = per_state[state]
        if not findings:
            continue
        print(f"■ {state}")
        for finding in findings:
            print(f"    {finding['rule']} ({finding['impact']}) — "
                  f"{len(finding['targets'])}× — {finding['help']}")
            for target in finding["targets"][:4]:
                print(f"        {target}")

    counts = tally(per_state)
    total = sum(counts.values())
    scope = f", rules: {','.join(rules)}" if rules else ""
    print(f"a11y: {len(states)} states{scope}, {total} violation(s) over "
          f"{len(counts)} rule(s), in {seconds:.1f}s")
    print(f"a11y: {len(states) - len(modal)} state(s) asked "
          f"{'/'.join(DOCUMENT_RULES)}; {len(modal)} had a modal layer open, "
          "whose `inert` background is correct and makes those two unanswerable")
    if total:
        if enforce:
            return 1
        print("a11y: --record-only, so this run REPORTS and does not refuse. "
              "The floor is zero.")

    # THE SECOND THEME, and it is measured whatever the first one said. Running
    # it only when the dark theme is clean would make the light count invisible
    # on exactly the runs where something is already wrong, which is when a
    # reader most needs to know whether one repair caused the other.
    light_per_state, _, light_seconds, _ = await audit_everything(rules, light=True)
    light_total = sum(tally(light_per_state).values())
    ceiling = light_ceiling()
    print(f"a11y[light]: {light_total} violation(s) under `data-theme=light`, "
          f"in {light_seconds:.1f}s, against a ceiling of "
          f"{'none recorded' if ceiling is None else ceiling}")
    if ceiling is None:
        print(f"a11y[light]: {LIGHT_DEBT_FILE.name} is absent — run `--record` "
              "to write it. Until it exists this count is REPORTED and holds "
              "nothing, and a reported number nobody compares is a number "
              "nobody reads.", file=sys.stderr)
        return 1
    if light_total > ceiling:
        print(f"a11y[light]: {light_total} against a ceiling of {ceiling}. This "
              "is a RATCHET and only falls: the 154 findings L06 counted by "
              "hand are a campaign with its own design (B-055), and what is "
              "refused here is ADDING to them. Repair the new one, or lower "
              "nothing and explain.", file=sys.stderr)
        return 1
    if light_total < ceiling:
        print(f"a11y[light]: {light_total} is BELOW the ceiling of {ceiling} — "
              f"lower it, with `--record`. A ceiling nobody lowers becomes room "
              "for a defect nobody notices.")
    return 0


def light_ceiling():
    """Returns the recorded light-theme count, or None when nothing is recorded.

    Returns:
        The ceiling as an integer, or None — which the caller refuses rather
        than treats as zero or as infinity.
    """
    if not LIGHT_DEBT_FILE.exists():
        return None
    return json.loads(LIGHT_DEBT_FILE.read_text(encoding="utf-8"))["counts"]["total"]


def main(argv=None) -> int:
    """Parses the command line and dispatches to a mode."""
    parser = argparse.ArgumentParser(
        description="axe-core over the maquette's named states.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true",
                      help="write a11y-debt.json, a11y-contrast.json and "
                           "a11y-light-debt.json")
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
