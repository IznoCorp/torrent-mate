"""What every rule script needs, in one place.

Twelve scripts carried a byte-identical `check()`, fourteen their own `BAR`,
and thirty-two the same four lines to open the prototype. That is not a style
question: when the startup screen started covering the frame for as long as the
load it stands for, twenty-eight scripts had to be edited by hand to close that
wait, and a script that had been forgotten would have failed for a reason that
has nothing to do with the rule it carries.

A script still owns its own rules, its own state driving and its own probes.
What it borrows here is the plumbing: how a verdict is printed, how a run ends,
and how the document is opened.

The address model and the boot's history seam joined that plumbing later, for
the same reason and from the same place: one script had read the model and
wrapped the boot's writers, and both are answers to « where is the interface? »
rather than holds about it. A model read in one script is a model the next one
transcribes, and a transcription drifts.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTOTYPE = "http://127.0.0.1:8899/"
BAR = "─" * 62

# Beside THIS FILE, never in the current directory — the same reason `audit.py`
# anchors `violations.json`, learned a second time and more expensively.
# Twenty-two captures were written as `screenshot(path="name.png")`, a path
# relative to wherever the caller happened to stand, and every proof in this
# repository is run from the root: 127 `.png` files had piled up there,
# invisible because a blanket `*.png` rule ignores them all. An artifact with a
# floating path is an artifact nobody owns and nobody counts.
SCREENSHOTS = pathlib.Path(__file__).resolve().parent / "__screenshots__"

# THE DESIGN'S SOURCES, and it is a LIST because the design stopped being one
# file. A rule that greps « the design » must grep all of them.
#
# This exists because of what happened the day the engine left the fragment:
# three rules kept reading `refonte.html` alone and stayed green over evidence
# that had simply moved — 930 image references, five colour references, and the
# whole body of code a fourth rule counts history primitives in. None of them
# failed. A hold that greps a file which no longer holds its subject reports
# « no violation » about nothing at all, and it does so silently, for as long
# as nobody thinks to check.
#
# `index.html` joined the list when the application shell's markup moved there,
# and it contributes nothing to any of those four counts TODAY. That is not a
# reason to leave it out: the list names where the design is WRITTEN, so the
# next `var(--…)` or `assets/…` added to the shell is covered on the day it is
# typed rather than on the day someone notices.
#
# Reading a missing path raises here rather than yielding "": a renamed source
# must break the rule that depends on it, loudly, on the next run.
DESIGN_SOURCES = (
    ROOT / "design" / "refonte.html",
    ROOT / "design" / "index.html",
    ROOT / "design" / "src" / "engine" / "legacy.js",
)


def design_source():
    """Returns every source the design is written in, concatenated.

    Returns:
        The text of each entry in `DESIGN_SOURCES`, joined by a newline so a
        pattern cannot match across the seam between two files.

    Raises:
        FileNotFoundError: If a declared source no longer exists — the failure
            this helper is built to make loud.
    """
    return "\n".join(path.read_text(encoding="utf-8")
                      for path in DESIGN_SOURCES)

# The phone the design targets. Every measurement is taken here, because a
# geometry read at another width answers a question nobody asked.
# The appearance is PINNED: the document's « systeme » mode follows the
# browser's colour-scheme preference, and a headless browser's preference is
# an accident of its defaults. The rules measure the reference appearance —
# dark — deterministically; a rule that wants to measure the light theme
# passes color_scheme="light" itself.
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2,
         "is_mobile": True, "has_touch": True, "color_scheme": "dark"}


class Journal:
    """Collects the verdicts of one script and decides its exit code.

    A rule that only prints cannot fail, and a script that cannot fail is a
    report nobody is obliged to read — so the count and the failures live
    together, and `summary()` is what ends the process.
    """

    def __init__(self, title):
        self.title = title
        self.executed = 0
        self.failures = []
        print(f"{BAR}\n{title}\n{BAR}")

    def check(self, name, condition, detail=""):
        """Records one executed check and its verdict.

        Args:
            name: What is being held to, phrased as the interface's promise.
            condition: The measurement's verdict.
            detail: What was measured, printed either way — a green line that
                shows its number is what makes a rule readable a year later.
        """
        self.executed += 1
        print(("  PASS" if condition else "  FAIL") + f" {name}"
              + (f" — {detail}" if detail else ""))
        if not condition:
            self.failures.append(name)
        return bool(condition)

    def summary(self, errors=()):
        """Prints the run's summary and exits non-zero on any failure.

        Args:
            errors: JS errors collected from the page, which are failures even
                when every rule passed.
        """
        print()
        print(f"{BAR}\n{self.executed} rules EXECUTED — "
              + ("no violation" if not self.failures
                 else f"{len(self.failures)} violation(s): {', '.join(self.failures)}"))
        if errors:
            print("JS errors:", list(errors))
        if self.failures or errors:
            raise SystemExit(1)


async def open_page(browser, **kwargs):
    """Opens the prototype in a fresh context, past the startup screen.

    The startup screen covers the frame for as long as the load it stands for
    lasts. Nothing is fetched here, so the wait is closed through the same seam
    the app uses rather than slept out — a sleep would be slower and would still
    be a race.

    Args:
        browser: A launched Playwright browser.
        **kwargs: Context overrides — a user agent, an init script, anything a
            script needs that the phone defaults do not carry.

    Returns:
        The (context, page) pair, on a page that has dismissed the design note.
    """
    ctx = await browser.new_context(**{**PHONE, **kwargs})
    pg = await ctx.new_page()
    await pg.goto(PROTOTYPE, wait_until="load")
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(250)
    return ctx, pg


async def shot(pg, name):
    """Captures the page into the harness's one screenshot directory.

    A capture is a READING AID and never an oracle: two captures of the same
    unmodified file disagree on a third of the states, because skeleton
    shimmer, sheet entrances and image decoding do not settle on a schedule
    that can be waited out. What holds a rendering is `oracle.py`.

    Args:
        pg: The Playwright page to capture.
        name: The capture's name, without an extension, as `<rule>-<what>` so
            that listing the directory says which rule wrote which frame. The
            directory is created here rather than at import time: a rule that
            takes no capture leaves none behind.
    """
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(SCREENSHOTS / f"{name}.png"))


# ── the address model ─────────────────────────────────────────────────────
# The page a path names. Kept in step with `design/src/lib/addresses.ts`,
# which is the model the address rules measure — a contract has three ends,
# and this is one of them.
HOME = "/acquisition"
HOME_PAGE = "acq"
LIBRARY = "/media"
ARRIVALS = "/arrivals"

# And the model itself, READ rather than transcribed. The dial list and the
# page table were both written out once, and the dial list had already
# drifted — five names against the model's six — in the very wave that wrote
# the comment forbidding a second list. A copy nothing renders drifts in
# silence, so the names come from the declaration, exactly as
# `scripts/check-frontend-boundaries.py` reads them. They live here rather
# than in one rule so that the next rule to need an address reads the model
# too instead of writing a third list.
MODEL = ROOT / "design" / "src" / "lib" / "addresses.ts"
DECLARATION = MODEL.read_text(encoding="utf-8")
DIAL_PARAMETERS = tuple(
    re.findall(r'parameter:\s*"([^"]+)"', DECLARATION)
    + re.findall(r'PANEL_PARAMETER = "([^"]+)"', DECLARATION)
)
PAGE_PATHS = dict(re.findall(r'^\s{2}(\w+):\s*"(/[^"]*)"', DECLARATION, re.M))
# And the SCREEN routes WITH THE PAGE EACH BELONGS TO, from the same
# declaration and with the same regex `scripts/check-frontend-boundaries.py`
# uses. A `$segment` stands for any one non-empty segment; what fills it is a
# rule's business, the TABLE is the model's. Written out by hand it was a
# copy, and a copy of a table drifts the day a screen is added — silently,
# because a screen no rule opens is a screen no rule contradicts. The PARENT
# is read for the same reason it is declared: what sits under a screen is the
# page it belongs to, and a rule that expected the home page under every one
# of them would agree with the defect § 16 rule 3 names.
SCREEN_PARENTS = dict(re.findall(r'^\s{2}"(/[^"]*)":\s*"(\w+)"', DECLARATION, re.M))
SCREEN_PATHS = tuple(SCREEN_PARENTS)

# ── the boot's history seam ───────────────────────────────────────────────
# The boot's own writers run before anything in the document can reach the
# bridge, so a cold load cannot break them the way an in-app gesture does.
# What is left is the history primitives themselves, wrapped before the first
# script of the page runs. And the boot writes THREE times, not once: the
# settlement and the guard both travel through `replaceState`, the arrival
# entry through `pushState`. A seam over `pushState` alone therefore refuses
# one write and says nothing whatever about the other two — measured: either
# `replace` catch reverted to a bare call left every hold over it green.
BOOT_DIAL = "lens=inc"
BOOT_ADDRESS = f"media?{BOOT_DIAL}"
BOOT_PATH = "/" + BOOT_ADDRESS
# The markers the boot's entries carry, read back off the refused write so a
# hold can say the refusal was the boot's own. They are the ENGINE's data,
# matched here and never authored here.
NAV_MARKER = "nav"
GUARD_MARKER = "garde"  # french-ok: the engine's own history marker, matched not authored


def refuse_one_boot_write(primitive, condition):
    """Composes an init script refusing exactly ONE of the boot's history writes.

    Args:
        primitive: The `History.prototype` method to wrap — `pushState` for
            the arrival entry, `replaceState` for the two before it.
        condition: A JavaScript expression over `url` (the address the call
            carries) and `given` (its state argument), true for the one call
            to refuse.

    Returns:
        The script, installed before the page's first script runs. It refuses
        the FIRST call the condition matches, records the address and the state
        it refused on `window.__refused`, and lets every later call through.
    """
    return """
const native = History.prototype.PRIMITIVE;
let refused = false;
History.prototype.PRIMITIVE = function (...args) {
  const url = String(args[2] ?? "");
  const given = args[0] || {};
  if (!refused && (CONDITION)) {
    refused = true;
    window.__refused = { url: url, state: given };
    throw new Error("refused");
  }
  return native.apply(this, args);
};
""".replace("PRIMITIVE", primitive).replace("CONDITION", condition)


# One seam per boot write, in the order the boot issues them, each with the
# marker its entry carries. The settlement is recognised by the ADDRESS it
# writes, the guard by the marker in its state — it writes no address of its
# own — and the arrival entry is the first push of the load, whatever it
# carries. What each seam refused is read back against these: a boot that
# stopped writing through the primitive while some later writer still did would
# otherwise read as a swallowed refusal instead of a rotted seam.
# Each seam also carries the ADDRESS its write should have been carrying: the
# boot pushes the FLOOR before the arrival now, so a seam matching « the first
# push » would refuse the floor and a hold naming the arrival would report the
# wrong write as caught.
BOOT_WRITES = (
    ("the arrival address", "replaceState", f'url.includes("{BOOT_ADDRESS}")',
     NAV_MARKER, BOOT_PATH),
    ("the exit guard", "replaceState", f'given.tm === "{GUARD_MARKER}"',
     GUARD_MARKER, BOOT_PATH),
    ("the floor beneath the arrival", "pushState", f'url.endsWith("{HOME}")',
     NAV_MARKER, HOME),
    ("the arrival entry", "pushState", f'url.includes("{BOOT_ADDRESS}")',
     NAV_MARKER, BOOT_PATH),
)
