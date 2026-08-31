#!/usr/bin/env python3
"""A cached shell does not become a stale one.

R106 — P7's other half. The worker precaches the shell, so the application can
       now outlive the build it was made from. The update discipline is what
       keeps that from meaning « the operator judges yesterday's design »:
       the running build is compared against what the host serves, and a
       difference reloads the page ONCE.

WHY IT SERVES ITS OWN COPY. The rule has to make the served build MOVE, and the
only way to do that honestly is to change what a server answers with. Doing that
to `/tmp/tm-refonte` would rewrite the copy every other rule is reading at the
same moment — which is B-256 exactly, committed on purpose by the rule that is
supposed to catch it. It works on a duplicate, on a scratch port.

WHY « EXACTLY ONCE » IS THE PROPERTY AND NOT « IT RELOADS ». The check fires on
load, on every return to the foreground and on a timer, so a reload that did not
latch would fire again from the handler still queued behind it. A reload loop on
a design host is indistinguishable from a host that is down, and it is the one
failure mode this discipline can produce that is worse than staleness.
"""
import asyncio
import json
import pathlib
import shutil
import sys
import tempfile

from playwright.async_api import async_playwright
from server import start_server

SERVED = pathlib.Path("/tmp/tm-refonte")
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2,
         "is_mobile": True, "has_touch": True}


async def main():
    """Runs R106.

    Returns:
        0 when the discipline holds, 1 otherwise.
    """
    executed = 0
    failures = []

    def hold(name, condition, detail=""):
        nonlocal executed
        executed += 1
        print(("  PASS" if condition else "  FAIL") + f" {name}"
              + (f" — {detail}" if detail else ""))
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as scratch:
        root = pathlib.Path(scratch) / "served"
        # `copytree` and not a symlink: the point is to own a copy nobody else
        # reads, and `symlinks=True` keeps the assets link from being followed
        # into ten megabytes of artwork.
        shutil.copytree(SERVED, root, symlinks=True, ignore=shutil.ignore_patterns(".lock"))
        stamp = root / "build.json"
        hold("the served copy publishes a build at all", stamp.is_file(),
             stamp.read_text().strip() if stamp.is_file() else "absent")
        if not stamp.is_file():
            print(f"\n{executed} rules EXECUTED — 1 violation(s)")
            return 1
        running = json.loads(stamp.read_text())["build"]

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome")
            context = await browser.new_context(**PHONE)
            page = await context.new_page()
            loads = []
            page.on("load", lambda _: loads.append(1))

            with start_server(root) as port:
                await page.goto(f"http://127.0.0.1:{port}/", wait_until="load")
                await page.evaluate("()=>window.__loadingDone?.()")
                # The discipline runs on load. Let its first check settle
                # against an UNMOVED stamp: a reload here would be the
                # discipline reloading over nothing at all.
                await page.wait_for_timeout(1200)
                settled = len(loads)
                hold("an unchanged build reloads nothing",
                     settled == 1, f"{settled} load(s)")

                # THE BUILD MOVES. Nothing else changes — the bundles the page
                # is running from stay exactly as they are, so what is measured
                # is the comparison and not a broken page.
                stamp.write_text(json.dumps({"build": "moved-" + running[:8]}) + "\n")

                # Through the same door the application uses: a return to the
                # foreground. Not a timer — waiting fifteen minutes for a rule
                # is not a rule — and not a reload, which would be the rule
                # producing the effect it claims to measure.
                await page.evaluate(
                    """()=>document.dispatchEvent(new Event("visibilitychange"))""")
                # Bounded, and the bound is a NAVIGATION rather than a duration:
                # waiting a fixed time would pass on a slow machine only by
                # luck, and would say nothing about how many reloads followed.
                try:
                    await page.wait_for_event("load", timeout=8000)
                except Exception:
                    pass
                after = len(loads)
                hold("a moved build reloads the page", after >= 2,
                     f"{after} load(s)")

                # AND NOT AGAIN. The stamp is still moved — the host is still
                # serving a different build from the one the page was made
                # from, because the page reloaded into the same bundles. Every
                # later check therefore sees a difference too, and a discipline
                # that did not latch would reload forever.
                await page.evaluate(
                    """()=>document.dispatchEvent(new Event("visibilitychange"))""")
                await page.wait_for_timeout(2500)
                loops = len(loads)
                hold("and it does not reload again", loops == after,
                     f"{loops} load(s) after a second check")

            # THE HOST IS GONE from here, which is the ordinary state of an
            # installed application on a phone with no signal. Unreachable must
            # never read as « the build changed »: it would reload the
            # application every fifteen minutes, forever, offline.
            gone = len(loads)
            await page.evaluate(
                """()=>document.dispatchEvent(new Event("visibilitychange"))""")
            await page.wait_for_timeout(2500)
            hold("an unreachable host reloads nothing", len(loads) == gone,
                 f"{len(loads)} load(s) with the host down")

            await browser.close()

    print()
    print(f"{executed} rules EXECUTED — "
          + ("no violation" if not failures
             else f"{len(failures)} violation(s): {', '.join(failures)}"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
