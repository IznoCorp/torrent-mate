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
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"
BAR = "─" * 62

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
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(250)
    return ctx, pg
