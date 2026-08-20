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
import os
import pathlib
import re
import subprocess
import sys
import time

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
RECIPE_FILE = ROOT / "regions.json"
SOURCE_DIR = ROOT / "design" / "src"
REFERENCE_FILE = ROOT / "oracle-reference.json"

# The two ways a `data-region` NAME reaches the markup. The second exists
# because the page host draws six pages' body wrapper itself and carries the
# name in its table (`pages/host.tsx`), so the attribute there is computed and
# no literal `data-region="…"` appears for those six.
EMITTED = (
    re.compile(r'data-region="([^"]+)"'),
    re.compile(r'\bregion:\s*"([^"]+)"'),
)

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

# The clock every measurement is taken at. Fixed rather than paused: pausing
# would stop `setTimeout` too, and the settle signal's own budget runs on it.
#
# HONESTLY REPORTED, because a counter-measure nobody can demonstrate is a
# counter-measure nobody should trust: sweeping all 82 states at 03:00 and at
# 23:30 produced NO difference this oracle can see. That is not luck, it is the
# shape of the instrument — it measures geometry and computed style, never TEXT,
# so « Prochaine recherche à 3 h 20 » changing says nothing until it wraps a
# line. The clock is fixed anyway: it costs one line, and it is the difference
# between « no dependency today » and « no dependency ».
FIXED_CLOCK = "2026-08-20T12:00:00Z"

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


def load_regions() -> dict:
    """Returns the region table, without its documentation key.

    Returns:
        A mapping of `<surface>/<part>` to its declaration.

    Raises:
        SystemExit: If the table is empty. An oracle with no region measures
            nothing and says so with a confident exit code 0 — the failure this
            instrument exists to prevent, one level up.
    """
    record = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))
    regions = {key: value for key, value in record.get("regions", {}).items()
               if not key.startswith("$")}
    if not regions:
        raise SystemExit(
            f"{RECIPE_FILE} declares no region. Measuring nothing and reporting "
            "success is exactly what this instrument is against."
        )
    return regions


def emitted_region_names() -> set[str]:
    """Returns every region name the maquette's sources emit.

    Returns:
        The set of names, from both the literal attribute and the page host's
        table.
    """
    names: set[str] = set()
    # `.ts` and `.js` too, and NOT only because a name might land there
    # tomorrow: the two directions of this check fail differently. A name
    # DECLARED and not emitted screams on its own, whatever the file type. A
    # name EMITTED and not declared is the silent one — the oracle simply never
    # reads that region — so the scan must cover every file a name can be
    # written in, or it holds only the half that was already loud.
    for suffix in ("*.tsx", "*.ts", "*.js"):
        for path in sorted(SOURCE_DIR.rglob(suffix)):
            text = path.read_text(encoding="utf-8")
            for pattern in EMITTED:
                names.update(pattern.findall(text))
    return names


def check_contracts() -> int:
    """Holds the THREE ENDS of every `data-region` contract.

    A `data-*` contract has three ends — the markup that emits it, the table
    that declares it, and the reader that taps it. Nothing tied them together
    before, and a rename that moved two of them left the third behind every
    time.

    `scripts/check-markup-contracts.py` does NOT cover this one, and that is
    worth writing down rather than assuming: it reads `data-*` values a handler
    forwards into a store field, and `data-region` is read by this file, in
    Python. Pointing that guard at it would pass for a reason unrelated to what
    it claims — a gate proves what it READS.

    Returns:
        A process exit code: 0 when both directions agree.
    """
    regions = load_regions()
    declared = set(regions)
    anchored = {key for key, value in regions.items()
                if value["selector"].startswith("[data-region=")}
    emitted = emitted_region_names()

    orphan_markup = sorted(emitted - declared)
    orphan_table = sorted(anchored - emitted)
    # D4, held rather than stated. A region anchored on a CSS class dies the day
    # its surface converts to utilities (L07) — which is the very wave this
    # instrument exists to watch, so it would lose its target at the moment it
    # is needed. Checked here rather than only in an ACCEPTANCE criterion: a
    # criterion runs once, a rule runs for ever.
    class_anchored = sorted(
        key for key, value in regions.items()
        if re.search(r"(^|[\s,])\.", value["selector"])
    )

    print(f"{len(declared)} regions declared, {len(anchored)} of them anchored on "
          f"data-region; {len(emitted)} names emitted by the sources")
    if orphan_markup:
        print("EMITTED BUT NOT DECLARED — the oracle would never read these: "
              + ", ".join(orphan_markup))
    if orphan_table:
        print("DECLARED BUT NOT EMITTED — these resolve to nothing, for ever: "
              + ", ".join(orphan_table))
    if class_anchored:
        print("ANCHORED ON A CSS CLASS — these die when their surface converts "
              "to utilities: " + ", ".join(class_anchored))
    return 1 if (orphan_markup or orphan_table or class_anchored) else 0


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
    if not os.environ.get("TM_ORACLE_NO_FROZEN_CLOCK"):
        await context.clock.set_fixed_time(FIXED_CLOCK)
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

    # A STALE SERVED COPY is the trap this repository has paid for three times,
    # and it is silent: `wrapped.html` copied without its `vite/` bundle 404s the
    # module, so nothing registers and every later call fails with a raw
    # TypeError about a function that « is not a function ». Said plainly here
    # instead, because the fix is a command rather than a debugging session.
    if await page.evaluate("()=>typeof window.__states") != "function":
        raise SystemExit(
            f"the prototype served at {PROTOTYPE} registered no state driver.\n"
            "The served copy is almost certainly stale — rebuild AND re-copy the "
            "bundle, not just the document:\n"
            "    cd frontend/maquette/design && npm run build\n"
            "    cp dist/index.html /tmp/tm-refonte/wrapped.html\n"
            "    rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite"
        )

    await neutralise(page, recipe)
    return context, page


async def neutralise(page, recipe: dict) -> None:
    """Removes the prototype's own chrome, BEFORE EVERY MEASUREMENT.

    ONCE AT OPEN IS NOT ENOUGH, and believing it was made this instrument
    measure the prototype's scaffolding for a whole phase. Both entries come
    back on their own: `.note` is emitted by the page COMPONENTS, so it is
    re-created on every render — measured, it reappeared in 56 of the 82 states
    after being removed at open. And the boot toast is raised on a timer, so a
    single click at open is a race that loses: it was visible in 34 states.

    Args:
        page: The page being measured.
        recipe: The `probe` block.
    """
    for entry in recipe["neutralise"]:
        # Two ways, and the entry says which. `remove` takes the node out of the
        # DOM — the design note is prototype-only chrome, and left in place it
        # springs back to 75.6px and pushes every region below it down, a probe
        # reporting its own setup as a divergence in each one. `click` presses
        # the interface's own control instead, which keeps the region
        # measurable: the boot toast is dismissed the way a user dismisses it.
        if entry.get("how", "remove") == "click":
            await page.evaluate(
                "(selector)=>document.querySelector(selector)?.click()",
                entry["selector"],
            )
            continue
        await page.evaluate(
            "(selector)=>document.querySelectorAll(selector)"
            ".forEach((node)=>node.remove())",
            entry["selector"],
        )


# Two frames — the floor, and on its own NOT ENOUGH. Measured: driving
# `drawer-navigation` five times and reading `#drawer` returned x = -148.1,
# -141.8, -141.2, -140.4, -140.2, because the drawer was caught MID-SLIDE. At
# rest it is 0. `TM_ORACLE_NO_SETTLE=1` restores this floor alone, so the
# failure the rest of the signal prevents can be shown on demand.
TWO_FRAMES = ("()=>new Promise((resolve)=>requestAnimationFrame("
              "()=>requestAnimationFrame(resolve)))")

# Finish what ends; FREEZE what does not.
#
# Three animations in this stylesheet never finish — `pulse` (1.6s, opacity),
# `spin` (0.7s, a rotation) and `sh` (1.3s, a skeleton shimmer). Awaiting them
# would hang for ever, and leaving them running makes the six `*-loading` states
# non-deterministic: `pulse` moves OPACITY, which this oracle measures, and
# `spin` moves a bounding rectangle.
#
# So: await the finite ones, then pause every survivor at time 0. The cost is
# named rather than hidden — the computed `animation` property then reads
# `paused` for those three. It reads `paused` in the reference AND in every
# check, so the comparison is unaffected; what is lost is the ability of this
# oracle to notice an animation stopping, which is a behaviour question and
# belongs to the rule suite.
REST = """(budget)=>{
  const running = document.getAnimations();
  const finite = running.filter((a) => {
    const timing = a.effect && a.effect.getTiming();
    return timing && timing.iterations !== Infinity;
  });
  const guard = new Promise((resolve) => setTimeout(resolve, budget));
  return Promise.race([
    Promise.all(finite.map((a) => a.finished.catch(() => {}))),
    guard,
  ]).then(() => {
    for (const a of document.getAnimations()) {
      const timing = a.effect && a.effect.getTiming();
      if (timing && timing.iterations === Infinity) { a.pause(); a.currentTime = 0; }
    }
    // `complete` is load-bearing, and it was paid for: `decode()` on a LAZY
    // image that has not started loading never resolves — not rejects,
    // PENDS — so a `.catch()` does nothing and the signal hangs for ever.
    // The library's posters are lazy. Only already-loaded images are
    // decoded, and the batch is raced against the same budget so a single
    // pathological image cannot stall a measurement either.
    const decoded = [...document.images]
      .filter((img) => img.src && img.complete)
      .map((img) => img.decode().catch(() => {}));
    return Promise.race([
      Promise.all(decoded),
      new Promise((resolve) => setTimeout(resolve, budget)),
    ]);
  });
}"""

# How long a finite animation is given to end before the signal gives up on it.
# A budget, never a wait: the common path resolves as soon as the last one ends.
FINITE_ANIMATION_BUDGET_MS = 2000

# How many times the geometry is re-sampled before the frame is called unstable.
SETTLE_ATTEMPTS = 8


async def settle(page, regions: dict | None = None) -> None:
    """Waits until the frame is AT REST, by fact rather than by duration.

    A delay in milliseconds is a race that passes on an idle machine and fails
    on a loaded one, and an oracle that flickers is an oracle someone disables.
    Every step here is a fact about the document.

    `TM_ORACLE_NO_SETTLE=1` drops back to the two-frame floor, so the divergence
    the signal prevents can be produced on demand — a counter-measure that is
    merely coded is a claim, one that is demonstrated failing without it is a
    proof.

    Args:
        page: The page being measured.
        regions: When given, the geometry of these regions must be identical
            across two consecutive frames before the page is called at rest.
            This is the actual guarantee, and it is what L12's view transitions
            will need: the oracle reads at rest rather than hoping to.
    """
    if os.environ.get("TM_ORACLE_NO_SETTLE"):
        await page.evaluate(TWO_FRAMES)
        return

    await page.evaluate(REST, FINITE_ANIMATION_BUDGET_MS)
    await page.evaluate(TWO_FRAMES)
    if not regions:
        return

    selectors = [region["selector"] for region in regions.values()]
    previous = await page.evaluate(SAMPLE, selectors)
    for _ in range(SETTLE_ATTEMPTS):
        await page.evaluate(TWO_FRAMES)
        current = await page.evaluate(SAMPLE, selectors)
        if current == previous:
            return
        previous = current
    raise SystemExit(
        "the frame never came to rest: the measured geometry still moved after "
        f"{SETTLE_ATTEMPTS} samples. Measuring here would record noise."
    )


# The cheap geometry fingerprint the stability check compares. Deliberately not
# the full measurement: it is taken repeatedly, and reading 19 computed
# properties per region per attempt would make settling cost more than the
# measurement it protects.
SAMPLE = """(selectors)=>selectors.map((selector)=>{
  const node = document.querySelector(selector);
  if (!node) return null;
  const box = node.getBoundingClientRect();
  return [box.x, box.y, box.width, box.height];
})"""


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
    # BOTH SIDES of the settle, and the second pass is not belt-and-braces.
    # The boot toast is raised ASYNCHRONOUSLY, so on the very first state
    # measured a single pass loses the race — measured: `startup` carried a
    # visible toast on pass 1 and none on pass 2, which is a reference whose
    # first entry depends on how fast the machine is. Neutralising before
    # settling keeps the geometry stable while it settles; neutralising after
    # catches whatever arrived during it.
    await neutralise(page, recipe)
    await settle(page, regions)
    await neutralise(page, recipe)
    await settle(page, regions)
    reading = {}
    for key, region in sorted(regions.items()):
        reading[key] = await page.evaluate(
            MEASURE,
            [region["selector"], recipe["computedStyleSubset"], RECT_PRECISION],
        )
    return reading


def base_commit() -> str:
    """Returns the commit the working tree is on.

    « Known-good » with no SHA means nothing, so the reference carries the one
    it was taken at.

    Returns:
        The full SHA, or `"unknown"` outside a repository.
    """
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def render_reference(measurements: dict, regions: dict, states: list) -> str:
    """Serialises the reference so a visual change is READ IN A PULL REQUEST.

    Sorted at every level and indented, which is the deliverable rather than a
    detail: an unsorted reference re-serialises differently on the next run and
    buries one real change under hundreds of moved lines. A reviewer must be
    able to see `font-size: 12px -> 13px` on `library/card` in the diff.

    Args:
        measurements: The reading, keyed by state then region.
        regions: The region table, for the header's counts.
        states: The states measured, for the header's counts.

    Returns:
        The file's text, newline-terminated.
    """
    if os.environ.get("TM_ORACLE_UNSORTED"):
        # The escape hatch for friction 4: same content, insertion order. It
        # exists to be run once and looked at — a diff nobody can read is a
        # gate nobody reads.
        body = measurements
    else:
        body = {state: dict(sorted(measurements[state].items()))
                for state in sorted(measurements)}
    document = {
        "$comment": (
            "The recorded oracle's reference — `frontend/maquette/oracle.py`. "
            "One entry per (named state x region): a bounding rectangle rounded "
            "to one decimal, and the computed properties of `regions.json`'s "
            "`probe.computedStyleSubset`. `null` means the region's selector "
            "matched nothing in that state, which is data rather than an "
            "omission. Regenerate with `--record`; entérine a REVIEWED change "
            "with `--accept`, never from a gate."
        ),
        "baseCommit": base_commit(),
        "counts": {"states": len(states), "regions": len(regions)},
        "measurements": body,
    }
    return json.dumps(document, ensure_ascii=False, indent=2,
                      sort_keys=False) + "\n"


def allowed(recipe: dict) -> set:
    """Returns the `(region, property)` pairs a divergence is excused on.

    Raises:
        SystemExit: If an entry carries no written reason. An allowlist without
            reasons is how an oracle is disarmed one entry at a time — nobody
            can review what nobody wrote down.
    """
    pairs = set()
    for entry in recipe["allowlist"]:
        if not entry.get("justification", "").strip():
            raise SystemExit(
                "an allowlist entry carries no justification: "
                f"{json.dumps(entry, ensure_ascii=False)}\n"
                "A reason or nothing — an excuse nobody wrote down is an "
                "excuse nobody can review."
            )
        pairs.add((entry.get("region", entry.get("selector")),
                   entry["property"]))
    return pairs


def compare(reference: dict, fresh: dict, excused: set) -> list:
    """Diffs a fresh reading against the reference, grouped by state.

    Args:
        reference: The committed measurements.
        fresh: What was just measured.
        excused: `(region, property)` pairs an allowlist entry covers.

    Returns:
        A list of `(state, region, what)` lines, in reading order.
    """
    findings = []
    for state in sorted(set(reference) | set(fresh)):
        before, after = reference.get(state, {}), fresh.get(state, {})
        for region in sorted(set(before) | set(after)):
            old, new = before.get(region), after.get(region)
            if old == new:
                continue
            if old is None or new is None:
                findings.append((state, region,
                                 f"present={old is not None} -> {new is not None}"))
                continue
            if old["rect"] != new["rect"]:
                findings.append((state, region,
                                 f"rect {old['rect']} -> {new['rect']}"))
            for key in sorted(set(old["style"]) | set(new["style"])):
                if old["style"].get(key) == new["style"].get(key):
                    continue
                if (region, key) in excused:
                    continue
                findings.append((state, region,
                                 f"{key}: {old['style'].get(key)!r} -> "
                                 f"{new['style'].get(key)!r}"))
    return findings


async def read_everything(recipe: dict, regions: dict) -> tuple:
    """Drives every named state once and measures every region in it.

    Returns:
        A `(measurements, states, seconds)` triple. The elapsed time is
        returned rather than printed so every mode can report it: friction
        cause 3 is slowness, and a counter-measure whose cost nobody sees is a
        counter-measure nobody defends.
    """
    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_frame(browser, recipe)
        states = await page.evaluate("()=>window.__states()")
        measurements = {}
        for state in states:
            measurements[state] = await measure_state(page, state, regions, recipe)
        await context.close()
        await browser.close()
    return measurements, states, time.monotonic() - started


async def record(to_stdout: bool = False) -> int:
    """Writes the reference.

    Args:
        to_stdout: Print it instead of writing, so a caller can prove the
            recording is byte-stable without touching the committed file.

    Returns:
        A process exit code.
    """
    recipe, regions = load_recipe(), load_regions()
    measurements, states, seconds = await read_everything(recipe, regions)
    text = render_reference(measurements, regions, states)
    if to_stdout:
        sys.stdout.write(text)
        return 0
    REFERENCE_FILE.write_text(text, encoding="utf-8")
    print(f"recorded {len(states)} states x {len(regions)} regions at "
          f"{base_commit()[:8]} in {seconds:.1f}s -> {REFERENCE_FILE.name}")
    return 0


async def check(accept: bool = False) -> int:
    """Compares the maquette against the reference, or entérines a change.

    Args:
        accept: Overwrite the reference with what was measured. Never reachable
            from a gate — an oracle that can accept its own divergence is not
            an oracle.

    Returns:
        A process exit code: 0 when nothing moved that was not excused.
    """
    recipe, regions = load_recipe(), load_regions()
    excused = allowed(recipe)
    if not REFERENCE_FILE.exists():
        raise SystemExit(
            f"no reference at {REFERENCE_FILE}. Record one first: "
            "`python3 frontend/maquette/oracle.py --record`."
        )
    stored = json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))
    measurements, states, seconds = await read_everything(recipe, regions)

    if accept:
        REFERENCE_FILE.write_text(
            render_reference(measurements, regions, states), encoding="utf-8")
        print(f"accepted: reference rewritten at {base_commit()[:8]}. "
              "Read the diff — that is where the change is reviewed.")
        return 0

    findings = compare(stored["measurements"], measurements, excused)
    print(f"{len(states)} states x {len(regions)} regions, "
          f"{len(states) * len(regions)} measurements in {seconds:.1f}s")
    print(f"reference taken at {stored.get('baseCommit', 'unknown')[:8]}")
    if not findings:
        print("no divergence")
        return 0
    current = None
    for state, region, what in findings:
        if state != current:
            print(f"\n  {state}")
            current = state
        print(f"    {region:24s} {what}")
    print(f"\n{len(findings)} divergence(s)")
    return 1


async def coverage() -> int:
    """Drives every named state and reports what each region actually resolved.

    « Declared » is not « resolved », and « resolved » is not « measured ». The
    three counts are printed apart because collapsing them is how a region list
    grows a hole nobody sees: a stale selector and an interaction-gated block
    look identical from the inside.

    Returns:
        A process exit code: 0 when every region resolves somewhere, or is
        declared in `knownAbsent` with its reason.
    """
    recipe = load_recipe()
    regions = load_regions()
    declared_absent = {entry["region"] for entry in recipe["knownAbsent"]}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_frame(browser, recipe)
        states = await page.evaluate("()=>window.__states()")
        resolved = {key: 0 for key in regions}
        with_area = {key: 0 for key in regions}
        for state in states:
            reading = await measure_state(page, state, regions, recipe)
            for key, value in reading.items():
                if value is None:
                    continue
                resolved[key] += 1
                if value["rect"]["width"] and value["rect"]["height"]:
                    with_area[key] += 1
        await context.close()
        await browser.close()

    print(f"{len(regions)} regions x {len(states)} states\n")
    for key in sorted(regions):
        mark = "" if with_area[key] else "   <- resolves but never has an area"
        print(f"  {resolved[key]:3d}/{len(states)} resolved,"
              f" {with_area[key]:3d} with an area   {key}{mark}")

    never = [k for k, n in resolved.items() if not n and k not in declared_absent]
    flat = [k for k, n in with_area.items() if not n]
    print("\n" + "-" * 62)
    print(f"regions resolving somewhere : {len(regions) - len(never)}/{len(regions)}")
    print(f"regions measuring something : {len(regions) - len(flat)}/{len(regions)}")
    if never:
        print(f"NEVER RESOLVED and not in knownAbsent: {', '.join(sorted(never))}")
        return 1
    return 0


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
    parser.add_argument(
        "--coverage", action="store_true",
        help="drive every named state and report what each region resolved",
    )
    parser.add_argument(
        "--contracts", action="store_true",
        help="hold the three ends of every data-region contract (no browser)",
    )
    parser.add_argument("--record", action="store_true",
                        help="write the reference")
    parser.add_argument("--stdout", action="store_true",
                        help="with --record: print instead of writing")
    parser.add_argument("--check", action="store_true",
                        help="compare against the reference; non-zero on divergence")
    parser.add_argument("--accept", action="store_true",
                        help="entérine a REVIEWED change into the reference")
    arguments = parser.parse_args()
    if arguments.contracts:
        return check_contracts()
    if arguments.record:
        return asyncio.run(record(arguments.stdout))
    if arguments.check:
        return asyncio.run(check())
    if arguments.accept:
        return asyncio.run(check(accept=True))
    if arguments.smoke:
        return asyncio.run(smoke())
    if arguments.coverage:
        return asyncio.run(coverage())
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
