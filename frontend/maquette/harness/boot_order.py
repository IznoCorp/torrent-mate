"""R88 — the boot installs five seams, in the one order they can be installed in.

L09 split `app/shell.tsx` onto five subjects. What the shell kept is the ORDER,
and the order is the only thing the split could have broken silently: each of
the four extracted modules is a function the boot calls, so nothing about their
content depends on where the call sits — and everything about the running
application does.

WHAT THE ORDER IS, AND WHY EACH STEP CANNOT MOVE:

  installHistoryBridge()      the panel host pushes a layer entry through it,
                              and `openPanel`'s own error branch is written on
                              the bridge being real before any producer calls
                              `open`
  installScrollRestoration()  subscribes to the same history instance
  installNavigation(...)      hands `go()` the router and the history
  installScreenBridge()       every opener it installs navigates through `go()`
  createStore()               the panel host receives it as an ARGUMENT
  installPanelHost(store)     must exist before the seams are handed over
  installSeams({...})         the engine imports these three names
  window.__startEngine(...)   the engine runs, and everything above must be real

READ AT THE SOURCE, AND THEN IN THE BROWSER, because neither alone is enough.
The source says the calls are in order; it cannot say the application survived
it. The browser says the seams answer; it cannot say WHY, and a boot that
happened to work with two steps swapped would be a green run over a contract
nobody is holding any more.

WHAT THIS RULE DOES NOT READ, said before it says what it does:

  - It does not read whether each extracted module is CORRECT. Its content is
    sliced out of the shell byte for byte and the oracle is what holds the
    rendering; this rule holds only that the pieces are called in order.
  - It does not read the engine's own boot writes. Those are `bridge.py`'s.
  - It reads the ORDER of the call sites, not the order they EXECUTE in. A
    conditional wrapping one of them would satisfy this rule and change the
    boot — so the rule also refuses a call site that is not at the top level
    of the module, which is the shape that difference would take.
"""
import asyncio
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, ROOT, Journal, open_page, without_comments

SOURCE_ROOT = ROOT / "design" / "src"

# The file the boot lives in, relative to `design/src`. Named once: read
# inline, a move of the shell would make this rule crash rather than quietly
# hold nothing.
BOOT_FILE = "app/shell.tsx"

# The four subjects the shell was split onto, and the shell itself. A file that
# stops existing fails this rule rather than being skipped.
SPLIT_MODULES = (
    "app/shell.tsx",
    "app/router-tree.tsx",
    "app/history-bridge.ts",
    "app/scroll-restoration.ts",
    "app/panel-host.ts",
)

# Invariant 6's hard ceiling. The split exists to satisfy it; a rule that did
# not read it would let the shell grow back one wave at a time.
CEILING = 400

# The boot's steps, in the order they must appear. Each entry is the pattern
# that finds the call site, and the name a fallen hold is read by.
BOOT_STEPS = (
    (r"^installHistoryBridge\(\);", "installHistoryBridge()"),
    (r"^installScrollRestoration\(\);", "installScrollRestoration()"),
    (r"^installNavigation\(", "installNavigation(router, history)"),
    (r"^installScreenBridge\(\);", "installScreenBridge()"),
    (r"^const store = createStore\(\);", "createStore()"),
    (r"^installPanelHost\(store\);", "installPanelHost(store)"),
    (r"^installSeams\(\{", "installSeams({…})"),
    (r"^const start = window\.__startEngine;", "the engine handshake"),
)


def step_positions(boot_source):
    """Finds each boot step's line number, at the module's top level.

    A call site indented by anything at all is inside a block — a condition, a
    callback, a function — and a boot step inside a block is a boot step that
    may not run. Anchoring every pattern on the start of a line is what refuses
    that without having to parse the file.

    Args:
        boot_source: The boot file's text, comments already blanked.

    Returns:
        A list of (line number, step name) for every step found, in the order
        they appear in the file, and a list of the steps not found at all.
    """
    found, missing = [], []
    for pattern, name in BOOT_STEPS:
        match = re.search(pattern, boot_source, re.MULTILINE)
        if match is None:
            missing.append(name)
            continue
        found.append((boot_source[: match.start()].count("\n") + 1, name))
    found.sort()
    return found, missing


def hold_the_source(journal):
    """Holds the split itself: the five files, their size, and the boot order."""
    for relative in SPLIT_MODULES:
        path = SOURCE_ROOT / relative
        exists = path.is_file()
        journal.check(f"{relative} exists", exists,
                      "" if exists else "the split has been undone or a file moved")
        if not exists:
            continue
        non_blank = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                        if line.strip())
        journal.check(f"{relative} is under invariant 6's ceiling",
                      non_blank <= CEILING,
                      f"{non_blank} non-blank against {CEILING}")

    boot = without_comments((SOURCE_ROOT / BOOT_FILE).read_text(encoding="utf-8"))
    found, missing = step_positions(boot)
    journal.check("every boot step is at the module's top level",
                  not missing,
                  f"{len(found)}/{len(BOOT_STEPS)} found"
                  + (f" — missing or indented: {', '.join(missing)}" if missing else ""))

    # THE ORDER ITSELF. Compared as the sequence of NAMES the file yields
    # against the sequence the contract declares — never as « each one is after
    # the previous », which reports the same failure once per pair and buries
    # which pair actually moved.
    wanted = [name for _, name in BOOT_STEPS]
    actual = [name for _, name in found]
    in_order = actual == [name for name in wanted if name in actual]
    journal.check(
        "the boot's steps are in the one order they can be in",
        in_order,
        " → ".join(actual) if not in_order else f"{len(actual)} steps, as declared")


async def hold_the_browser(journal):
    """Holds that the boot the source declares actually produced a live one."""
    async with async_playwright() as playwright:
        # `channel="chrome"` like every other rule here: the harness measures
        # in the browser the operator actually runs, and the bundled headless
        # shell is not installed on this machine.
        browser = await playwright.chromium.launch(channel="chrome")
        _context, page = await open_page(browser, **PHONE)

        seams = await page.evaluate(
            """() => ({
                bridge: typeof window.__bridge?.record,
                screens: typeof window.__screens?.mediaSheet,
                panel: typeof window.__panel?.open,
                store: typeof window.__store?.read,
                router: typeof window.__routeur?.navigate,
            })""")
        for name, kind in seams.items():
            journal.check(f"the boot published a live {name} seam",
                          kind == "function", f"typeof = {kind}")

        # THE ORDERING THE SPLIT CHANGED, read behaviourally. The panel host
        # receives the store as an argument now; before the split it closed
        # over a `const` declared below its own use. `isOpen()` answers FROM
        # THE STORE, so a panel host holding anything else answers with a
        # thrown reference rather than a boolean — which is the whole reason
        # this is asked of the running application and not of the source.
        answered = await page.evaluate(
            """() => {
                try { return { ok: true, value: window.__panel.isOpen() }; }
                catch (error) { return { ok: false, value: String(error) }; }
            }""")
        journal.check("the panel host answers from the store it was handed",
                      answered["ok"] and answered["value"] is False,
                      f"isOpen() → {answered['value']}")

        # The engine reaches the same three objects by IMPORT, filled by
        # `installSeams`. Calling it a second time is refused, and that refusal
        # is the only observable proof from outside that it ran at all.
        refused = await page.evaluate(
            """() => {
                const seams = window.__seamsInstalledProbe;
                return seams === undefined ? "no probe" : seams;
            }""")
        journal.check("the engine's imported seams are filled",
                      # The engine drives every screen through them; a screen
                      # opening at all is that proof, and it is cheaper and
                      # less coupled than exporting a probe for it.
                      (await page.evaluate(
                          """() => { window.__screens.profile("Silo");
                                     return location.pathname; }""")
                       ).startswith("/quality/"),
                      f"probe={refused}")

        await browser.close()


def main():
    journal = Journal("R88 — the boot installs five seams, in one order")
    hold_the_source(journal)
    asyncio.run(hold_the_browser(journal))
    journal.summary()


if __name__ == "__main__":
    main()
