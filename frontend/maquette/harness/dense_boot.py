"""B-572 — tm-design opens on the dense world, cold; every other build stays real.

The operator's cold boot showed nothing under « En cours »: `scen` starts
"real" (`app/arrival.ts`) and no door reached the dense world before the first
paint — every existing rule poses a world through `__go`, never through a cold
load. The fix is a build-time switch (`vite.config.mjs`, Vite's own `mode`)
that ONLY tm-design's build passes; this rule proves BOTH worlds COLD, with no
`__go` at all:

  * the harness's own build (`npm run build`, no mode — unchanged) stays REAL.
  * a scratch build made the way tm-design's build will (`--mode
    design-host`) opens on the DENSE world.

The scratch copy is built and served on its own — never through `serve.py`,
which always runs the plain `npm run build` and would silently measure the
real world twice.
"""
import asyncio
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, chrome_launch_args
from playwright.async_api import async_playwright
from server import start_server

# « En cours » COLD, not the page's own default landing tab — `follows` is
# (`lib/addresses.ts`, the `tab` dial's default), and B-572 is about the tab
# named in its own title, not about whichever one happens to open first.
COLD_PATH = "acquisition?tab=now"

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRATCH_HOME = pathlib.Path("/tmp/tm-refonte/_dense_boot")
SCRATCH = SCRATCH_HOME / "design"


def prepare_scratch() -> None:
    """Builds a scratch copy of the design root — a measurement never writes
    into the operator's source, and this build must run beside R73's own
    scratch copy without sharing a directory with it.
    """
    if SCRATCH_HOME.exists():
        shutil.rmtree(SCRATCH_HOME)
    SCRATCH.mkdir(parents=True)
    design = ROOT / "design"
    for name in ("index.html", "vite.config.mjs", "build-identity.mjs",
                 "package.json", "sw.js"):
        shutil.copy(design / name, SCRATCH / name)
    shutil.copytree(design / "src", SCRATCH / "src")
    (SCRATCH / "node_modules").symlink_to(design / "node_modules")
    (SCRATCH / "assets").symlink_to(design / "assets")
    # What the tree reaches for OUTSIDE itself — `mocks/declared-status.ts`
    # imports the contract from `frontend/maquette/`, one level above the
    # design root. Found by reading the sources, never by naming one file
    # here: a name typed into this rule is a second copy of R73's own guard,
    # and it would rot the day a second reach is allowed.
    for module in sorted(SCRATCH.glob("src/**/*.ts")) + sorted(SCRATCH.glob("src/**/*.tsx")):
        for match in re.finditer(r'from "((?:\.\./)+[^"]+)"', module.read_text()):
            target = (module.parent / match.group(1)).resolve()
            root = SCRATCH.resolve()
            if root in target.parents:
                continue
            step = os.path.relpath(target, root)
            landing = SCRATCH / step
            if not landing.exists():
                landing.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(design / step, landing)


def build_dense() -> pathlib.Path:
    """Builds the scratch copy in the DENSE mode tm-design's own build will use.

    Returns:
        The built `dist/` directory, with `wrapped.html` beside it so
        `start_server` can answer a cold "/" the way the harness host does.
    """
    prepare_scratch()
    subprocess.run(["npm", "run", "build", "--", "--mode", "design-host"],
                    cwd=SCRATCH, check=True, capture_output=True, text=True)
    dist = SCRATCH / "dist"
    shutil.copy2(dist / "index.html", dist / "wrapped.html")
    return dist


async def boot_cold(browser, base_url: str) -> dict:
    """Opens `<base_url>acquisition?tab=now` fresh, with no `__go` anywhere in it.

    Args:
        browser: A launched Playwright browser.
        base_url: The host's root address, trailing slash included.

    Returns:
        What the cold load drew, and the JS errors it raised.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(base_url + COLD_PATH, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.wait_for_timeout(400)
    reading = await page.evaluate("""()=>{
      const v = document.querySelector('#view');
      return {
        scen: window.__store.read().state.scen,
        page: window.__store.read().state.page,
        tab: window.__store.read().state.acqTab,
        cards: v ? v.querySelectorAll('[data-part="card"],[data-part="tile"]').length : 0,
        empty: !!(v && v.querySelector('[data-part="empty-state"]')),
        text: v ? v.textContent.replace(/\\s+/g, ' ').trim().length : 0,
      };
    }""")
    await context.close()
    return {**reading, "errors": errors}


async def main() -> None:
    journal = Journal("B-572 — tm-design opens on the dense world, cold")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome", args=chrome_launch_args())
        try:
            # THE REAL WORLD, COLD — the harness's own build, unmodified: the
            # rule that keeps `run.sh`'s copy and the unit suite untouched by
            # this switch.
            real = await boot_cold(browser, "http://127.0.0.1:8899/")
            journal.check(
                "a cold real-world boot lands on Acquisition › En cours, "
                "scen still real, no JS error",
                real["page"] == "acq" and real["tab"] == "now"
                and real["scen"] == "real" and not real["errors"],
                f"{real}")
            journal.check(
                "the real world's own cold state: « En cours » empty, "
                "as `movingReel`'s own seed is",
                real["cards"] == 0 and real["empty"] and real["text"] > 0,
                f"{real}")

            # THE DENSE WORLD, COLD — a scratch build made the way tm-design's
            # own build will be, never through `serve.py`.
            dist = build_dense()
            with start_server(dist) as port:
                dense = await boot_cold(browser, f"http://127.0.0.1:{port}/")
                journal.check(
                    "a cold tm-design boot (`--mode design-host`) opens dense, "
                    "with no __go, no JS error",
                    dense["scen"] == "loaded" and not dense["errors"],
                    f"{dense}")
                journal.check(
                    "« En cours » shows cards on the cold dense boot",
                    dense["cards"] > 0 and not dense["empty"], f"{dense}")
        finally:
            await browser.close()
            shutil.rmtree(SCRATCH_HOME, ignore_errors=True)
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
