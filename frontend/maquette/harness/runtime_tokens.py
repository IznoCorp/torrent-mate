"""R84 — the runtime token is published, it follows the bar, and it has ONE publisher.

`--tm-bottom-bar-h` is one of the two custom properties in this interface that
are a MEASUREMENT rather than a design decision: the bottom bar's drawn height,
safe area included, known only once the bar is on screen. The other,
`--tm-screen-bar-bottom`, is how far down the frame an open screen's bar
reaches, and it has one publisher of its own, `app/layer-presence.ts`; that it
is published and follows the bar is held by R159's screen legs, where the
message placed below it is read — this rule holds only that nobody else writes
it. Everything that must clear
the bar reads it — eight `var(--tm-bottom-bar-h, 0px)` uses — and the fallback
in each of them is what makes the failure quiet. A token nobody publishes
resolves to `0px` at every use, the interface still lays out, and the only
symptom is a strip of content sliding under the bar on the states that have
content down there.

So a grep proves nothing here twice over. It cannot say whether the value was
ever WRITTEN, and it cannot say whether it still TRACKS: a publisher that
measures once and never observes again is green to every static reading and
wrong the moment a safe area, a font size or a label wraps.

THE THIRD HOLD IS ABOUT WHERE THE PUBLISHER LIVES, and it is deliberately not a
grep of one file. The publisher moved out of the legacy engine into the shell so
that the engine's removal has nothing to rescue; a rule checking « the engine
does not publish » would stay green over a SECOND publisher added anywhere
else, and two writers of one property agree until they do not. What is held
instead is the count over the whole source tree: for each `--tm-` property,
exactly one file writes it, and every such file is under `app/`. That is the shape the plan names as
the trap — a rule that greps one file while the evidence moves to another.

RE-AIMED, and said here. The count was once « exactly one file writes a `--tm-`
property ». It fell the day a SECOND measurement got a publisher of its own —
`--tm-screen-bar-bottom`, how far down the frame an open screen's bar reaches,
written by `app/layer-presence.ts` — while nothing it guards had moved: that
property has one writer, and the bar's token still has one. What two writers
break is ONE property, so what is held now is per property: every `--tm-`
property written in the source tree has exactly one writer, the bar's token
among them, and every writer is under `app/`.
"""
import asyncio
import re

from common import ROOT, Journal, open_page
from playwright.async_api import async_playwright

# The property, spelled the way the stylesheet spells it. Both ends of the
# contract carry the name, which is what makes this rule possible at all.
TOKEN = "--tm-bottom-bar-h"

# THE BAR ITSELF, anchored on its `data-part` and never on the class that
# happens to style it. The class is a style decision and the utility conversion
# takes it away; `shell/tab-bar` is the name the markup gives the element, and a
# rule that dies with a stylesheet was measuring the stylesheet.
BAR = '[data-part="shell/tab-bar"]'

# The source tree the publisher must live in, and the directory it must live
# under. `app/` is where application-level DOM concerns go — `app/focus.ts` is
# the neighbour — and the engine is where none of them may stay.
SOURCE_TREE = ROOT / "design" / "src"
PUBLISHER_HOME = SOURCE_TREE / "app"
SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")

# A WRITE of a `--tm-` property, in any of the shapes the sources use: the
# property name may sit on the call's own line or on the next one, and it may be
# quoted any of the three ways JavaScript quotes a string.
WRITE = re.compile(r"""setProperty\(\s*["'`](--tm-[A-Za-z0-9-]+)""")

# The bar is forced to this height, which no state draws it at, so a value that
# merely happened to be right stays wrong afterwards.
FORCED_PX = 140

# The published value, and the height it is supposed to be reporting, read in
# the SAME evaluation: read one call apart, a layout landing between them would
# be scored as a publisher that failed to follow.
READ = """() => {
  const bar = document.querySelector('BAR_SELECTOR');
  const published = getComputedStyle(document.documentElement)
    .getPropertyValue('--tm-bottom-bar-h').trim();
  return {
    measured: bar ? bar.getBoundingClientRect().height : null,
    published: published,
  };
}""".replace("BAR_SELECTOR", BAR)

# Forcing the bar taller, through the cascade rather than through an inline
# style on the bar itself: an inline style is what the publisher would be
# writing if it wrote the wrong thing, and a probe must not be able to be
# mistaken for the mechanism it measures.
FORCE = """(px) => {
  const style = document.createElement('style');
  style.id = 'bar-height-probe';
  style.textContent = 'BAR_SELECTOR { min-height: ' + px + 'px !important; }';
  document.head.appendChild(style);
}""".replace("BAR_SELECTOR", BAR)

RELEASE = """() => {
  const style = document.getElementById('bar-height-probe');
  if (style) style.remove();
}"""

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def publishers():
    """Returns every `--tm-` custom property written, with the files that write it.

    Returns:
        A mapping from each property to the paths that write it, relative to the
        maquette root, sorted so a refusal names the same files in the same
        order on every run.

    Raises:
        SystemExit: If the source tree holds no file of a language that could
            publish anything. A search over nothing finds one publisher never
            and zero publishers always — both verdicts about the rule's own
            reading rather than about the sources.
    """
    files = [path for path in sorted(SOURCE_TREE.rglob("*"))
             if path.suffix in SOURCE_SUFFIXES and path.is_file()]
    if not files:
        raise SystemExit(
            f"{SOURCE_TREE} holds no source file: this rule would search "
            "nothing and report on nothing.")
    written = {}
    for path in files:
        for token in sorted(set(WRITE.findall(path.read_text(encoding="utf-8")))):
            written.setdefault(token, []).append(path.relative_to(ROOT))
    return written


def pixels(value):
    """Returns a `NNpx` custom-property value as a float, or None.

    Args:
        value: The value read off the document, already stripped.
    """
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)px", value)
    return float(match.group(1)) if match else None


def follows(published, measured):
    """Says whether a published value is the bar's height, rounded UP.

    The publisher writes `Math.ceil` of the measured height, so the two agree
    to within one pixel and the published value is never the SMALLER of the
    two: half a pixel of bar left uncovered is half a pixel of content the
    operator cannot reach.

    Args:
        published: The value read off the document, in pixels.
        measured: The bar's own rendered height, in pixels.
    """
    if published is None or measured is None:
        return False
    return -0.01 <= published - measured < 1.01


async def main():
    global _journal
    _journal = Journal("R84 — the bottom bar's height, published once and kept current")

    # ── the source tree: one writer per property, and it is the shell's ──────
    written = publishers()
    found = sorted({path for paths in written.values() for path in paths})
    named = " · ".join(str(path) for path in found)
    bar_writers = written.get(TOKEN, [])
    check(f"exactly one source file publishes `{TOKEN}`",
          len(bar_writers) == 1,
          str(bar_writers[0]) if len(bar_writers) == 1
          else f"NO file under {SOURCE_TREE.relative_to(ROOT)} writes it — everything "
               "above the bar sits on its fallback" if not bar_writers
          else f"the runtime token has {len(bar_writers)} publishers, and two "
               f"writers of one property agree until they do not — "
               f"{' · '.join(str(path) for path in bar_writers)}")
    doubled = {token: paths for token, paths in written.items() if len(paths) > 1}
    check("no `--tm-` property has a second writer",
          bool(written) and not doubled,
          " · ".join(f"{token} by {len(paths)}" for token, paths in sorted(written.items()))
          if not doubled else
          " · ".join(f"{token} by {' and '.join(str(path) for path in paths)}"
                     for token, paths in sorted(doubled.items())))
    # Held apart from the count: one publisher in the wrong place and one
    # publisher in the right place are different defects, and a single verdict
    # over both would name whichever the reader guessed.
    home = PUBLISHER_HOME.relative_to(ROOT)
    placed = bool(found) and all(
        PUBLISHER_HOME in (ROOT / path).parents for path in found)
    # The detail says what was MEASURED when the hold stands and what the
    # refusal is when it falls. A green line printing the refusal's own sentence
    # reads as a failure to anyone scanning the log.
    check("the publisher lives with the shell's other DOM concerns",
          placed,
          f"{named}, under {home}" if placed
          else f"the publisher is not under {home}, so the engine's removal "
               f"still has something to rescue — {named or 'no publisher at all'}")

    # ── the document: the value lands, and it follows the bar ────────────────
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(browser)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        cold = await pg.evaluate(READ)
        # A bar nothing draws would put every hold below on a measurement of
        # `null`, and a rule that measured nothing must not read as one that
        # passed.
        check("the bottom bar is drawn on a cold load",
              cold["measured"] is not None and cold["measured"] > 1,
              f"`{BAR}` renders {cold['measured']}px"
              if cold["measured"] is not None else f"`{BAR}` is absent")

        published = pixels(cold["published"])
        check(f"`{TOKEN}` is published on a cold load",
              published is not None,
              f"`{TOKEN}` is never published; everything above the bar sits on "
              f"its fallback — the document reads `{cold['published']}`"
              if published is None else f"`{TOKEN}: {cold['published']}`")

        check(f"`{TOKEN}` is the bar's measured height",
              follows(published, cold["measured"]),
              f"`{TOKEN}` reads `{cold['published']}` while the bar renders "
              f"{cold['measured']}px — the value above the bar is not the bar"
              if not follows(published, cold["measured"])
              else f"{cold['measured']:g}px measured, rounded up to "
                   f"{cold['published']}")

        # ── it FOLLOWS the bar ───────────────────────────────────────────────
        await pg.evaluate(FORCE, FORCED_PX)
        await pg.wait_for_timeout(300)
        forced = await pg.evaluate(READ)
        forced_published = pixels(forced["published"])

        # The probe is held before its result is: a forcing that did not force
        # would leave the bar at its own height, the published value would
        # rightly be unchanged, and « the value follows » would pass over a
        # publisher that had stopped observing entirely.
        check("the probe really changes the bar's height",
              forced["measured"] is not None
              and cold["measured"] is not None
              and abs(forced["measured"] - cold["measured"]) > 1,
              f"{cold['measured']}px → {forced['measured']}px")

        check(f"`{TOKEN}` follows the bar when the bar changes",
              follows(forced_published, forced["measured"]),
              f"the bar moved to {forced['measured']}px and `{TOKEN}` still "
              f"reads `{forced['published']}` — the publisher measured once "
              "and stopped observing"
              if not follows(forced_published, forced["measured"])
              else f"`{cold['published']}` → `{forced['published']}`")

        await pg.evaluate(RELEASE)
        await pg.wait_for_timeout(300)
        restored = await pg.evaluate(READ)
        # The probe leaves nothing behind, and saying so is what lets the next
        # rule in the suite trust the document it opens.
        check("the bar returns to its own height once the probe is released",
              follows(pixels(restored["published"]), restored["measured"]),
              f"`{restored['published']}` at {restored['measured']}px")

        await browser.close()

    _journal.summary(errors)

asyncio.run(main())
