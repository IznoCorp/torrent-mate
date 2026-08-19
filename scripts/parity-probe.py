#!/usr/bin/env python3
"""Proves the EXTRACTED stylesheet renders what the maquette renders.

WHAT THIS CLOSES. `scripts/extract-maquette-css.py --check` guards that
`frontend/src/styles/ps/app-surface.css` is textually what extraction produces
from `refonte.html`. That is necessary and it is not sufficient: extraction
SCOPES every selector under `.tm`, so `.topbar` becomes `.tm .topbar` and its
specificity goes from (0,1,0) to (0,2,0). A cascade outcome can change under
that rewrite while the text stays exactly what the extractor emits — and a
textual guard cannot see it. Rendering identity is a different claim from
textual identity, and this is the arm that makes it.

HOW. `regions.json` already declares the whole contract, and nothing here
invents any of it:

  probe.viewport             390 × 844, DPR 2, mobile, touch
  probe.assertBeforeMeasuring  refused unless the viewport really is 390
  probe.computedStyleSubset  the sixteen properties compared
  probe.allowlist            the accepted divergences, each with a justification
  regions                    53 selectors, each naming the states it appears in
  states                     49 named states, reached through `window.__go`

For every state, every region visible in it is measured TWICE against the same
DOM: once as the prototype dresses it (BLOCK 2 of `refonte.html`), then again
with BLOCK 2 replaced by the extracted sheet and the scope class applied. The
DOM never changes between the two reads — only the stylesheet does — so a
difference is a difference the extraction caused.

WHY NOT SCREENSHOTS. The README settled that: a shimmer, a header entrance and
an async WebP decode do not settle on a schedule you can wait out, and a run of
that oracle once « proved » twenty states had changed after a deletion that was
correct all along. `getBoundingClientRect` plus a fixed `getComputedStyle`
subset is deterministic, which is why it is what `probe` declares.

APPEND-ONLY. Every region is re-measured on every pass. The defect that rule
exists for has already been paid once: after a change to one view only that
view was checked, and another page shipped blank.

Usage:
    python3 scripts/parity-probe.py            # measure, report, exit 1 on divergence
    python3 scripts/parity-probe.py --state acq-encours-loaded   # one state
    python3 scripts/parity-probe.py --verbose  # print every region measured
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAQUETTE = ROOT / "frontend" / "maquette"
REGIONS = MAQUETTE / "regions.json"
SOURCE_HTML = MAQUETTE / "design" / "refonte.html"
EXTRACTED_CSS = ROOT / "frontend" / "src" / "styles" / "ps" / "app-surface.css"
PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"

sys.path.insert(0, str(ROOT / "scripts"))


def application_block_of(html: str) -> tuple[str, str]:
    """Splits the prototype's `<style>` into (harness block, application block).

    The split is the extractor's own: BLOCK 2 starts at the opener of the
    comment announcing it. Reusing that boundary rather than re-deriving one is
    the point — a probe that disagreed with the extractor about where the
    application CSS begins would be measuring a third thing.

    Args:
        html: The whole of `refonte.html`.

    Returns:
        The CSS before BLOCK 2, and BLOCK 2 itself.

    Raises:
        SystemExit: When the block markers are gone.
    """
    start = html.find("<style")
    end = html.find("</style>", start)
    if start < 0 or end < 0:
        raise SystemExit("parity-probe: no <style> in the maquette")
    css = html[html.find(">", start) + 1:end]
    marker = css.find("BLOCK 2")
    if marker < 0:
        raise SystemExit(
            "parity-probe: BLOCK 2 not found — the maquette has lost its "
            "harness / application split, and the probe cannot tell them apart")
    opener = css.rfind("/*", 0, marker)
    return css[:opener], css[opener:]


NEUTRALISE = """
(selectors) => {
  // Removed from the DOM, not hidden: `display:none` still leaves a rule able
  // to put it back, and the point is that BOTH passes read the same document.
  let removed = 0;
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) { node.remove(); removed++; }
  }
  return removed;
}
"""

MEASURE = """
(payload) => {
  const {selector, subset} = payload;
  const nodes = [...document.querySelectorAll(selector)];
  return nodes.map((node) => {
    const box = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    const computed = {};
    for (const property of subset) computed[property] = style.getPropertyValue(property);
    // Rounded to the tenth: sub-pixel noise from a fractional device ratio is
    // not a divergence, and comparing raw floats would report one every run.
    return {
      rect: {
        x: Math.round(box.x * 10) / 10,
        y: Math.round(box.y * 10) / 10,
        width: Math.round(box.width * 10) / 10,
        height: Math.round(box.height * 10) / 10,
      },
      computed,
    };
  });
}
"""

SWAP = """
(payload) => {
  const {harness, extracted, scope} = payload;
  const sheet = [...document.querySelectorAll('style')]
    .find((node) => node.textContent.includes('BLOCK 2'));
  // Named by its CONTENT, not by being first. `querySelector('style')` took
  // whichever sheet came first in the document: inject one decoy ahead of it
  // and the swap replaced the decoy, BLOCK 2 stayed live, both passes measured
  // the prototype against itself, and a deleted rule in the extracted sheet
  // reported zero divergences. The marker is the same one
  // `application_block_of` refuses to work without.
  if (!sheet) return {ok: false, why: 'no <style> carrying BLOCK 2 to swap'};
  // The DOM is untouched: only the dressing changes. BLOCK 1 stays, because it
  // is the phone frame the prototype lives inside and removing it would move
  // every region for a reason that has nothing to do with the extraction.
  sheet.textContent = harness;
  const injected = document.createElement('style');
  injected.id = 'parity-extracted';
  injected.textContent = extracted;
  document.head.appendChild(injected);
  // The extracted sheet is scoped: `.topbar` ships as `.tm .topbar`, so
  // without a scope root it would match nothing and every region would read as
  // unstyled — a probe that reported total divergence would be measuring its
  // own setup, not the app.
  document.body.classList.add(scope);
  return {ok: true, rules: injected.sheet ? injected.sheet.cssRules.length : -1};
}
"""


def differences(source, target, allowlist, selector):
    """Returns every measured difference that the allowlist does not excuse.

    Args:
        source: The prototype's measurements for one region.
        target: The same region measured under the extracted sheet.
        allowlist: `probe.allowlist`, each entry naming selector + property.
        selector: The region's selector, used to match allowlist entries.

    Returns:
        A list of human-readable differences.
    """
    excused = {
        entry["property"]
        for entry in allowlist
        if entry["selector"] == selector
    }
    found = []
    if len(source) != len(target):
        found.append(f"matched {len(source)} node(s) as source, {len(target)} as target")
        return found
    for index, (before, after) in enumerate(zip(source, target)):
        where = f"[{index}]" if len(source) > 1 else ""
        if before["rect"] != after["rect"]:
            found.append(f"{where} rect {before['rect']} → {after['rect']}")
        for property_, value in before["computed"].items():
            if property_ in excused:
                continue
            if after["computed"].get(property_) != value:
                found.append(
                    f"{where} {property_}: {value!r} → "
                    f"{after['computed'].get(property_)!r}")
    return found


async def run(only_state, verbose):
    """Measures every region in every state, twice, and reports divergence.

    Returns:
        0 when the extracted sheet renders what the prototype renders.
    """
    from playwright.async_api import async_playwright

    contract = json.loads(REGIONS.read_text(encoding="utf-8"))
    probe = contract["probe"]
    subset = probe["computedStyleSubset"]
    allowlist = probe.get("allowlist", [])
    # An entry naming a property the probe never compares excuses NOTHING while
    # reading as « seen and forgiven ». The single entry shipped that way:
    # `.bottombar`/`position`, with `position` absent from the subset. Refused
    # here rather than discovered by someone trusting it.
    for entry in allowlist:
        if entry["property"] not in subset:
            raise SystemExit(
                f"parity-probe: allowlist entry {entry['selector']} / "
                f"{entry['property']} names a property the probe does not "
                "compare — add it to probe.computedStyleSubset, or drop the "
                "entry: it excuses nothing as written.")
        if not any(region["selector"] == entry["selector"]
                   for region in contract["regions"].values()):
            raise SystemExit(
                f"parity-probe: allowlist entry {entry['selector']} matches no "
                "region selector — allowlist matching is exact, so this excuse "
                "can never apply.")
    neutralise = [entry["selector"] for entry in probe.get("neutralise", [])]
    # A region that matches nothing MEASURES nothing, which is the exact shape
    # of vacuity this whole contract exists to refuse. So absence fails —
    # except where it is declared, with its cause, and therefore bounded.
    known_absent = {entry["region"] for entry in probe.get("knownAbsent", [])}
    scope = contract["scope"].lstrip(".")
    harness_css, _application_css = application_block_of(
        SOURCE_HTML.read_text(encoding="utf-8"))
    extracted_css = EXTRACTED_CSS.read_text(encoding="utf-8")

    states = [s for s in contract["states"] if not only_state or s == only_state]
    if only_state and not states:
        raise SystemExit(f"parity-probe: no state named {only_state!r} in regions.json")
    by_state: dict[str, list[tuple[str, str]]] = {}
    for name, region in contract["regions"].items():
        for state in region.get("states", []):
            by_state.setdefault(state, []).append((name, region["selector"]))

    viewport = probe["viewport"]
    divergences: list[str] = []
    undeclared: list[str] = []
    measured = missing = 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context = await browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport["deviceScaleFactor"],
            is_mobile=viewport["isMobile"],
            has_touch=viewport["hasTouch"],
        )
        page = await context.new_page()
        try:
            for state in states:
                regions = by_state.get(state, [])
                if not regions:
                    continue
                await page.goto(PROTOTYPE, wait_until="load")
                await page.evaluate("()=>window.__loadingDone?.()")
                await page.evaluate("()=>document.querySelector('#toastx')?.click()")
                # The viewport is asserted from INSIDE the page, as `probe`
                # declares: a context created at 390 that lays out at another
                # width would make every measurement below meaningless.
                if not await page.evaluate(f"()=>{probe['assertBeforeMeasuring']}"):
                    raise SystemExit(
                        "parity-probe: "
                        f"{probe['assertBeforeMeasuring']} is false — refusing to measure")
                await page.evaluate("(id)=>window.__go(id)", state)
                await page.wait_for_timeout(420)
                # Prototype-only chrome goes BEFORE the first measurement, so
                # the two passes read the same document and a difference can
                # only come from the stylesheet.
                await page.evaluate(NEUTRALISE, neutralise)

                source = {}
                for name, selector in regions:
                    source[name] = await page.evaluate(
                        MEASURE, {"selector": selector, "subset": subset})

                swapped = await page.evaluate(
                    SWAP,
                    {"harness": harness_css, "extracted": extracted_css, "scope": scope})
                if not swapped["ok"]:
                    raise SystemExit(f"parity-probe: {swapped['why']}")
                await page.wait_for_timeout(120)

                for name, selector in regions:
                    target = await page.evaluate(
                        MEASURE, {"selector": selector, "subset": subset})
                    before = source[name]
                    if not before and not target:
                        # Absent under BOTH sheets: not a rendering difference,
                        # but not nothing either — the map claims a region is
                        # visible in a state where it cannot be seen.
                        missing += 1
                        if name in known_absent:
                            print(f"  {state:26} {name:34} absent (declared)")
                        else:
                            print(f"  {state:26} {name:34} ABSENT — UNDECLARED")
                            undeclared.append(
                                f"{state} · {name} ({selector}): matches nothing in "
                                "this state. Point it at the state it IS visible in, "
                                "fix the selector, or declare it in probe.knownAbsent "
                                "with its cause.")
                        continue
                    measured += 1
                    found = differences(before, target, allowlist, selector)
                    if found:
                        for line in found:
                            divergences.append(f"{state} · {name} ({selector}): {line}")
                        print(f"  {state:26} {name:34} DIVERGES ({len(found)})")
                    elif verbose:
                        print(f"  {state:26} {name:34} ok ({len(before)} node(s))")
        finally:
            await browser.close()

    print()
    # MEASURING NOTHING IS NOT PASSING. Emptying every region's `states` made
    # the probe skip every state, never launch a page — so `assertBeforeMeasuring`
    # never ran either — and exit 0. The per-region case was already refused;
    # the whole-probe case was not, which is the same vacuity one level up.
    if not measured:
        print("parity-probe: NOTHING WAS MEASURED — every region was skipped. "
              "A probe that measures nothing proves nothing.", file=sys.stderr)
        return 1
    print(f"parity-probe: {measured} region-in-state measurement(s), "
          f"{missing} not present, {len(divergences)} divergence(s)")
    if missing:
        print(f"  « absent » means the selector matched nothing under BOTH sheets — "
              f"a stale map, not a rendering difference. {len(known_absent)} declared "
              "in probe.knownAbsent, each with its cause.")
    if undeclared:
        print("\nRegions that measure nothing, and are not declared:")
        for line in undeclared:
            print(f"  {line}")
        return 1
    if divergences:
        print("\nThe extracted sheet does not render what the prototype renders:")
        for line in divergences[:40]:
            print(f"  {line}")
        if len(divergences) > 40:
            print(f"  … and {len(divergences) - 40} more")
        print("\nThe maquette is the reference (product-intent §15). Either the "
              "extractor must carry the difference, or it belongs in "
              "regions.json's probe.allowlist WITH its justification.")
        return 1
    return 0


def reachable() -> bool:
    """Says whether the prototype host is answering.

    Returns:
        True when a TCP connection to the prototype's port succeeds.
    """
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(PROTOTYPE)
    with socket.socket() as probe_socket:
        probe_socket.settimeout(2)
        return probe_socket.connect_ex(
            (parsed.hostname, parsed.port or 80)) == 0


def main() -> int:
    """Parses the arguments and runs the probe."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="measure a single state instead of all of them")
    parser.add_argument("--verbose", action="store_true", help="print every region measured")
    options = parser.parse_args()
    try:
        import playwright  # noqa: F401
    except ImportError:
        # Fail SOFT on a missing tool and LOUD on a real divergence: a machine
        # without Playwright must not report parity it never measured, and must
        # not block a commit either.
        print("parity-probe: playwright absent — nothing measured", file=sys.stderr)
        return 0
    if not reachable():
        # Same rule for the prototype host. `make check` must not turn red
        # because a static server is not up; it must not claim parity either,
        # which is why this says what it did NOT do.
        print(f"parity-probe: {PROTOTYPE} unreachable — nothing measured. "
              "Start the prototype host (frontend/maquette/harness) to run it.",
              file=sys.stderr)
        return 0
    return asyncio.run(run(options.state, options.verbose))


if __name__ == "__main__":
    raise SystemExit(main())
