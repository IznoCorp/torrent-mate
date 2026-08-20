#!/usr/bin/env python3
"""Does the maquette still render what it rendered at a known-good commit?

Lot **L01** of `docs/reference/frontend-architecture.md` — Phase 0, the safety
net. Nothing else in that plan may start without it, and the reason is blunt:
L02 moves 280 test anchors, L06 folds every declaration onto a scale, L07
replaces a 4 043-line stylesheet with utilities. Each one promises the rendering
is unchanged, and until this exists none of them can prove it.

WHAT IT MEASURES, AND WHAT IT REFUSES TO MEASURE
------------------------------------------------
Per *(named state x region)*: the bounding rectangle, plus a fixed subset of
computed style properties. Never a screenshot — decision D8, and it was measured
rather than believed: two captures of the same unmodified file diverge on 8 to
15 states, and one run of a screenshot oracle once « proved » twenty states had
changed after a deletion that was correct all along.

THE RECIPE IS RECOVERED, NOT REBUILT
------------------------------------
The `probe` block of `regions.json` — viewport, `assertBeforeMeasuring`, the 17
computed properties, `knownAbsent`, `neutralise`, `allowlist` — comes back from
`bd31d52b`, the commit before the untranslate merge removed it. It is the only
replayable measurement recipe this repository ever proved, and rebuilding the
list by judgement re-opens a question already settled by measurement. Its own
`$comment` carries the provenance and the single key that changed.

THIS IS A THIRD TIER, AND IT DUPLICATES NEITHER OF THE OTHER TWO
----------------------------------------------------------------
`harness/run.sh` runs the rules: `--contracts` (minutes, every pull request) and
the full suite (20-25 minutes, the gate before a wave merges). The rules say the
BEHAVIOUR still holds. This says the RENDERING did not move. It is too slow for
`make check`.

WHY IT DOES NOT IMPORT `harness/common.py`
------------------------------------------
Deliberate, and it is not duplication for its own sake. `common.open_page()`
ends on `await pg.wait_for_timeout(250)` — a delay in milliseconds, which is
exactly what this instrument may not depend on: a delay is a race that passes on
an idle machine and fails on a loaded one, and an oracle that flickers is an
oracle someone disables. The settle signal that replaces it is a fact about the
document, not a duration.

Usage:
    python3 frontend/maquette/oracle.py --smoke     # measure a few regions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
RECIPE_FILE = ROOT / "regions.json"

# The harness host: a plain `http.server` rooted on the COPY of the build. Never
# `serve.py`, which is the password-protected design host on 8712 — it answers
# 401 without a session, and this would then measure the sign-in screen: a green
# run over nothing.
PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"

# Rectangles are rounded before they are compared. `getBoundingClientRect()`
# returns fractions, and sub-pixel layout at DPR 2 produces legitimate halves —
# but it also produces noise below any threshold a human could see. One decimal
# keeps every real half-pixel and drops the noise. Declared here rather than
# buried in a helper, because a comparison's precision is part of what it means.
RECT_PRECISION = 1

# Five regions to exercise the core BEFORE a real region list exists, so the
# core cannot be quietly shaped to fit that list. Deleted in phase 2 — the name
# says so, and it is not a seed for the real inventory.
_SMOKE_REGIONS = {
    # NOT « the frame »: `#shell` is the mount node for migrated SCREENS —
    # the layers that open OVER a page — so it is legitimately 390x0 in every
    # state where no screen is open (`shell.tsx:696`). Kept in the smoke set
    # precisely because it is that case: a region can resolve and still measure
    # nothing, and the check below has to see the difference.
    "shell/screen-host": {"selector": "#shell"},
    "shell/nav": {"selector": "#nav"},
    "shell/viewport": {"selector": "#port"},
    "library/items": {"selector": "#libitems"},
    "library/count": {"selector": "#libcount"},
}

_SMOKE_STATES = ("lib-list", "acq-now-idle", "system")

# Reads one region. Returns `None` when the selector matches nothing, so an
# absent region is RECORDED rather than silently skipped — a region that
# resolves to zero elements is the main way this instrument goes green over
# nothing.
MEASURE = """([selector, properties, precision]) => {
  const nodes = document.querySelectorAll(selector);
  if (!nodes.length) return null;
  const node = nodes[0];
  const box = node.getBoundingClientRect();
  const factor = Math.pow(10, precision);
  const round = (value) => Math.round(value * factor) / factor;
  const style = getComputedStyle(node);
  const computed = {};
  for (const property of properties) computed[property] = style.getPropertyValue(property);
  return {
    matches: nodes.length,
    rect: {
      x: round(box.x), y: round(box.y),
      width: round(box.width), height: round(box.height),
    },
    style: computed,
  };
}"""


def load_recipe() -> dict:
    """Returns the recovered `probe` block of `regions.json`.

    Returns:
        The recipe dictionary, with its six keys.

    Raises:
        SystemExit: If the block is absent — which means someone removed the
            recipe again, and measuring without it would silently answer a
            different question (a geometry read at another width).
    """
    record = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))
    probe = record.get("probe")
    if not probe:
        raise SystemExit(
            f"{RECIPE_FILE} carries no `probe` block. Recover it from history "
            "(`git show bd31d52b:frontend/maquette/regions.json`) rather than "
            "rebuilding it by judgement."
        )
    return probe


def context_options(recipe: dict) -> dict:
    """Maps the recipe's `viewport` onto Playwright's context arguments.

    The appearance is pinned to dark on purpose. The document's « système » mode
    follows the browser's colour-scheme preference, and a headless browser's
    preference is an accident of its defaults — an oracle that inherits an
    accident measures a different document on a different machine.

    Args:
        recipe: The `probe` block.

    Returns:
        Keyword arguments for `browser.new_context()`.
    """
    viewport = recipe["viewport"]
    return {
        "viewport": {"width": viewport["width"], "height": viewport["height"]},
        "device_scale_factor": viewport["deviceScaleFactor"],
        "is_mobile": viewport["isMobile"],
        "has_touch": viewport["hasTouch"],
        "color_scheme": "dark",
    }


async def open_frame(browser, recipe: dict):
    """Opens the prototype, asserts the viewport, and neutralises the chrome.

    Args:
        browser: A launched Playwright browser.
        recipe: The `probe` block.

    Returns:
        The `(context, page)` pair, ready to be driven.

    Raises:
        SystemExit: If `assertBeforeMeasuring` is false. Refusing here is the
            point of that key: a geometry read at the wrong width answers a
            question nobody asked, and it answers it confidently.
    """
    context = await browser.new_context(**context_options(recipe))
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    # The startup screen covers the frame for as long as the load it stands for.
    # Nothing is fetched here, so it is closed through the seam the app uses.
    await page.evaluate("()=>window.__loadingDone?.()")

    assertion = recipe["assertBeforeMeasuring"]
    if not await page.evaluate(f"()=>Boolean({assertion})"):
        width = await page.evaluate("()=>document.documentElement.clientWidth")
        raise SystemExit(
            f"assertBeforeMeasuring is false ({assertion}); clientWidth is {width}. "
            "Refusing to measure — every figure taken here would be wrong."
        )

    for entry in recipe["neutralise"]:
        # REMOVED from the DOM, not merely dismissed. `harness/common.py` clicks
        # `#toastx`, which collapses the design note but leaves the node; left in
        # place while a stylesheet changes, it springs back to 75.6px and pushes
        # every region below it down — a probe reporting its own setup as a
        # divergence in each one.
        await page.evaluate(
            "(selector)=>document.querySelectorAll(selector)"
            ".forEach((node)=>node.remove())",
            entry["selector"],
        )
    return context, page


async def settle(page) -> None:
    """Waits until the frame is at rest, by fact rather than by duration.

    Phase 1 holds the floor: two consecutive animation frames. Phase 4 adds the
    rest of counter-measure 1 — decoded images, no running animation — and the
    escape hatch that demonstrates the need for it.

    Args:
        page: The page being measured.
    """
    await page.evaluate(
        "()=>new Promise((resolve)=>requestAnimationFrame("
        "()=>requestAnimationFrame(resolve)))"
    )


async def measure_state(page, state: str, regions: dict, recipe: dict) -> dict:
    """Drives one named state and reads every region in it.

    Args:
        page: The page being measured.
        state: A state id `window.__go` accepts.
        regions: The region table, keyed `<surface>/<part>`.
        recipe: The `probe` block.

    Returns:
        A mapping of region key to its measurement, or to `None` when the
        region's selector matched nothing in this state.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    await settle(page)
    reading = {}
    for key, region in sorted(regions.items()):
        reading[key] = await page.evaluate(
            MEASURE,
            [region["selector"], recipe["computedStyleSubset"], RECT_PRECISION],
        )
    return reading


async def smoke() -> int:
    """Exercises the measuring core on five regions across three states.

    Returns:
        A process exit code: 0 when every region resolved in at least one state.
    """
    recipe = load_recipe()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_frame(browser, recipe)
        known = await page.evaluate("()=>window.__states()")
        print(f"states registered (by EXECUTION, never by regex): {len(known)}")

        resolved: dict[str, int] = {key: 0 for key in _SMOKE_REGIONS}
        with_area: dict[str, int] = {key: 0 for key in _SMOKE_REGIONS}
        for state in _SMOKE_STATES:
            if state not in known:
                raise SystemExit(f"unknown state {state!r} — the smoke list is stale")
            reading = await measure_state(page, state, _SMOKE_REGIONS, recipe)
            print(f"\n  {state}")
            for key, value in reading.items():
                if value is None:
                    print(f"    {key:18s} absent")
                    continue
                resolved[key] += 1
                rect = value["rect"]
                if rect["width"] and rect["height"]:
                    with_area[key] += 1
                print(
                    f"    {key:18s} {rect['width']:>6}x{rect['height']:<7}"
                    f" at ({rect['x']}, {rect['y']})"
                    f"  font-size={value['style']['font-size']}"
                    f"  matches={value['matches']}"
                )
        await context.close()
        await browser.close()

    # A region that resolves in NO state is either a stale selector or a block
    # only an interaction reaches. `knownAbsent` is where the second kind is
    # declared, with its reason; anything else is a hole, and a hole that does
    # not fail is a hole nobody fixes.
    declared_absent = {entry["region"] for entry in recipe["knownAbsent"]}
    never = [key for key, count in resolved.items()
             if not count and key not in declared_absent]
    excused = [key for key, count in resolved.items()
               if not count and key in declared_absent]
    # « Resolved » is not « measured ». A region that resolves to a node of zero
    # area contributes a rectangle that cannot move, so it can never report a
    # divergence — it is green over nothing, which is this instrument's main
    # failure mode. Reported apart, never folded into the resolution count.
    flat = [key for key, count in with_area.items() if not count]
    print("\n" + "-" * 62)
    print(f"regions resolved in at least one state : "
          f"{len(resolved) - len(never)}/{len(resolved)}")
    print(f"regions with a NON-ZERO area somewhere : "
          f"{len(with_area) - len(flat)}/{len(with_area)}")
    if excused:
        print(f"absent everywhere, declared in knownAbsent: {', '.join(excused)}")
    if never:
        print(f"NEVER RESOLVED and not in knownAbsent: {', '.join(never)}")
        return 1
    if flat:
        print(f"resolved but always zero-area (measures nothing): {', '.join(flat)}")
    return 0


def main() -> int:
    """Parses the arguments and runs the requested mode.

    Returns:
        A process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--smoke", action="store_true",
        help="exercise the measuring core on a temporary region set",
    )
    arguments = parser.parse_args()
    if arguments.smoke:
        return asyncio.run(smoke())
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
