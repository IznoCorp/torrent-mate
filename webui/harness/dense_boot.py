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
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright
from served_copy import SERVED
from server import start_server

# « En cours » COLD, not the page's own default landing tab — `follows` is
# (`lib/addresses.ts`, the `tab` dial's default), and B-572 is about the tab
# named in its own title, not about whichever one happens to open first.
COLD_PATH = "acquisition?tab=now"

ROOT = pathlib.Path(__file__).resolve().parent.parent
# THE DESIGN HOST'S BUILD ASKS v1 FOR WHAT v1 SERVES (`mocks/passthrough.ts`),
# and this rule serves it with no v1 behind. On tm-design the real v1 answers:
# the owner signed in, the version read. The dense leg stands that v1 in at the
# browser — the seed's owner, a version, and a 404 problem for every other
# served operation — so what is measured is the boot tm-design really makes.
SEEDS = ROOT / "design" / "src" / "mocks" / "seeds"
SCRATCH_HOME = SERVED / "_dense_boot"
SCRATCH = SCRATCH_HOME / "webui" / "design"


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
                 "worker-source.mjs", "app-bundle.mjs", "package.json", "sw.js"):
        shutil.copy(design / name, SCRATCH / name)
    shutil.copytree(design / "src", SCRATCH / "src")
    (SCRATCH / "node_modules").symlink_to(design / "node_modules")
    (SCRATCH / "assets").symlink_to(design / "assets")
    # What the tree reaches for OUTSIDE itself — `mocks/declared-status.ts`
    # imports the contract from the repository's `contract/`, outside the
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


def v1_owner() -> dict:
    """The seed's owner, as v1 answers an account.

    Returns:
        The account, its role the seed's Admin.
    """
    seed = json.loads((SEEDS / "account.json").read_text(encoding="utf-8"))
    roles = json.loads((SEEDS / "accounts.json").read_text(encoding="utf-8"))["roles"]
    role = next(one for one in roles if one["id"] == seed["role"])
    return {"id": seed["id"], "name": seed["name"], "email": seed["email"], "role": role,
            "signInKind": seed["signInKind"], "forbiddenWrites": []}


async def stand_in_for_v1(route) -> None:
    """Answers one request the design host's build sends to v1.

    Args:
        route: The intercepted request.
    """
    path = route.request.url.split("?", 1)[0]
    if path.endswith("/api/v1/auth/me") or path.endswith("/api/v1/auth/login"):
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(v1_owner()))
    elif path.endswith("/api/v1/version"):
        await route.fulfill(status=200, content_type="application/json",
                            body=json.dumps({"version": "dense-boot", "commit": "dense-boot"}))
    else:
        await route.fulfill(status=404, content_type="application/json", body=json.dumps(
            {"status": 404, "title": "not stood in", "detail": f"{path} is not answered by this rule's v1"}))


async def boot_cold(browser, base_url: str, v1: bool = False) -> dict:
    """Opens `<base_url>acquisition?tab=now` fresh, with no `__go` anywhere in it.

    Args:
        browser: A launched Playwright browser.
        base_url: The host's root address, trailing slash included.
        v1: Whether v1 is stood in for, as the design host's build needs.

    Returns:
        What the cold load drew, and the JS errors it raised.
    """
    context = await browser.new_context(**PHONE)
    if v1:
        await context.route("**/api/v1/**", stand_in_for_v1)
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
            channel=browser_channel(), args=chrome_launch_args())
        try:
            # THE REAL WORLD, COLD — the harness's own build, unmodified: the
            # rule that keeps `run.sh`'s copy and the unit suite untouched by
            # this switch.
            real = await boot_cold(browser, PROTOTYPE)
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
                dense = await boot_cold(browser, f"http://127.0.0.1:{port}/", v1=True)
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
