"""R116 — B-252: the two child nodes the oracle cannot see, by contract.

D8 is explicit and the operator arbitrated keeping it that way: the recorded
oracle resolves a region to the nodes its selector names, and reads the nineteen
properties ON THOSE NODES — never on a child. So a defect carried by a child is
invisible to it, CORRECTLY, by its own contract. The remedy is not to widen the
oracle. It is that *a child node which carries a function is covered by a named
rule*, exactly as a pseudo-element is.

THESE TWO WERE FOUND BY EYE in #528's adversarial review, and the steward
replayed both with the oracle GREEN over them — 167 divergences before, 167
after, all on `shell/sheet-content`, in both cases. That measurement is what
makes this rule necessary rather than tidy: it is the lived proof that eyes
caught what 2 958 measurements could not.

  1. THE DIALOG'S PARAGRAPH CARRIES ITS COLOUR. `dialogParagraph` was stripped
     of `text-muted-foreground`, so a confirmation's explanatory sentence read at
     full foreground weight — the same weight as its own heading, which destroys
     the hierarchy that tells a reader which line is the question. Read under
     BOTH themes: a colour that resolves correctly in the dark palette and
     collapses in the light one is a defect present half the time, and half the
     time is not a state anybody designs.

  2. THE DANGER ACTION HAS CONTRAST UNDER THE LIGHT THEME. `selectionAction`
     carried `bg-transparent` in its BASE, so the danger tone's own background
     lost to it: white text on a white ground under `data-theme="light"`,
     contrast 1.00 — an action that deletes, rendered invisible.

WHAT MAKES THIS RULE DIFFERENT FROM THE ORACLE, and it is the entire point: every
read below resolves the CHILD and reads there. A rule that resolved the region's
root and read on it would reproduce the oracle's blindness exactly and be green
over both defects — which is the B-085 question asked in advance rather than
answered afterwards.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

# A state that opens a confirmation, and one that raises the selection bar.
DIALOG_STATE = "lib-delete"
SELECTION_STATE = "lib-selection"

# WCAG AA for body text. The danger action's defect measured 1.00 — white on
# white — so the floor only has to be above « invisible » to bite; it is set at
# the real requirement rather than at a number chosen to pass.
CONTRAST_FLOOR = 4.5


async def open_with_theme(browser, theme):
    """Opens the prototype under one theme.

    Args:
        browser: A launched Playwright browser.
        theme: `"dark"` or `"light"`.

    Returns:
        The (context, page) pair.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.evaluate("(t)=>document.documentElement.setAttribute('data-theme', t)", theme)
    await page.wait_for_timeout(250)
    return context, page


async def hold_the_dialog_paragraph(journal, browser, theme):
    """The confirmation's paragraph carries a colour of its own."""
    context, page = await open_with_theme(browser, theme)
    await page.evaluate("(s)=>window.__go(s)", DIALOG_STATE)
    await page.wait_for_timeout(420)

    # RESOLVED ON THE CHILD. `#dlg p` is a descendant of the region the oracle
    # measures, which is why the oracle is silent here and this rule is not.
    reading = await page.evaluate("""()=>{
      const dialog = document.querySelector('#dlg');
      if (!dialog) return null;
      const paragraph = dialog.querySelector('p');
      if (!paragraph) return null;
      const heading = dialog.querySelector('h1, h2, h3, [data-part$="/title"]');
      return {
        paragraph: getComputedStyle(paragraph).color,
        heading: heading ? getComputedStyle(heading).color : null,
      };
    }""")
    journal.check(f"the confirmation is drawn ({theme})",
                  reading is not None,
                  "no `#dlg p` — the hold below would decide nothing")
    if not reading:
        await context.close()
        return

    # THE ASSERTION IS A DIFFERENCE, NOT A LITERAL. Pinning the exact colour
    # would make this rule fall every time the palette is legitimately retuned,
    # and the defect was never « the wrong colour » — it was the paragraph
    # reading at the SAME weight as its heading, which is the hierarchy gone.
    journal.check(
        f"under `{theme}`, the dialog's paragraph is muted against its heading",
        reading["heading"] is not None
        and reading["paragraph"] != reading["heading"],
        f"paragraph {reading['paragraph']} against heading {reading['heading']} "
        "— the explanatory sentence reads at the weight of the question itself")
    await context.close()


# RESOLVING A COLOUR TO RGB IS THE PAGE'S JOB, NOT THIS SCRIPT'S.
#
# `getComputedStyle` answers in the syntax the stylesheet used, and this palette
# is written in `oklch()` — so a parser expecting `rgb(r, g, b)` reads
# « 0.58 0.215 25 » and raises. It did, on the first run of this rule.
#
# Painting the colour onto a 1×1 canvas and reading the pixel back makes the
# BROWSER do the conversion, which is both correct for every colour syntax that
# exists and future-proof against the next one. It is the same instrument R102
# uses to compare `theme-color` against the painted ground, and for the same
# reason.
CONTRAST_IN_THE_PAGE = """(colours) => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const context = canvas.getContext('2d', {willReadFrequently: true});
  const resolve = (colour) => {
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = colour;
    context.fillRect(0, 0, 1, 1);
    const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
    return [r, g, b];
  };
  const luminance = ([r, g, b]) => {
    const channel = (value) => {
      const proportion = value / 255;
      return proportion <= 0.03928
        ? proportion / 12.92
        : Math.pow((proportion + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  };
  const first = luminance(resolve(colours[0]));
  const second = luminance(resolve(colours[1]));
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
}"""


async def hold_the_danger_action(journal, browser):
    """The danger action is visible under the LIGHT theme."""
    context, page = await open_with_theme(browser, "light")
    await page.evaluate("(s)=>window.__go(s)", SELECTION_STATE)
    await page.wait_for_timeout(420)

    reading = await page.evaluate("""()=>{
      const action = document.querySelector('.selbar .danger, [data-part$="selection/bar"] .danger')
        || [...document.querySelectorAll('button')].find(b => b.className.includes('danger'));
      if (!action) return null;
      const style = getComputedStyle(action);
      // The painted ground, walked up until something is not transparent — a
      // button with `bg-transparent` shows whatever is BEHIND it, and that is
      // the colour its text has to contrast against.
      let node = action, ground = style.backgroundColor;
      while (node && (ground === 'rgba(0, 0, 0, 0)' || ground === 'transparent')) {
        node = node.parentElement;
        if (node) ground = getComputedStyle(node).backgroundColor;
      }
      return {text: style.color, ground};
    }""")
    journal.check("the selection bar's danger action is drawn",
                  reading is not None,
                  "no danger action — the hold below would decide nothing")
    if not reading:
        await context.close()
        return

    ratio = await page.evaluate(CONTRAST_IN_THE_PAGE,
                                [reading["text"], reading["ground"]])
    journal.check(
        "under `data-theme=\"light\"`, the danger action has contrast",
        ratio >= CONTRAST_FLOOR,
        f"{reading['text']} on {reading['ground']} is {ratio:.2f}:1 against a "
        f"floor of {CONTRAST_FLOOR} — an action that DELETES, rendered "
        "invisible")
    await context.close()


async def hold(journal):
    """Drives both child-node reads."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_dialog_paragraph(journal, browser, "dark")
        await hold_the_dialog_paragraph(journal, browser, "light")
        await hold_the_danger_action(journal, browser)
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R116 — B-252's two child nodes, which the oracle cannot see")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
