"""R-conformity-e — one mechanism, one row, and the app's one on/off pair.

THE DEFECT THIS ENDS. Système said the automatic processing twice — a bare word
« actif » / « coupé » beside its lever, and a chip « Actif » / « Désactivé »
among the locks — and the app had seven pairs of words for « on » and « off ».
The operator ruled one row, beside its control, the chip at its end, and ONE
pair: « actif » / « inactif ».

WHAT IT READS, on `levers-idle` (on) and `levers-trigger-off` (off), then the
settings' boolean field, which says the same pair:
  - the processing's row is a fact row whose value is a CHIP, read from the
    chip, saying the pair's word for the state, in the pair's tone;
  - the page names the mechanism ONCE — its label appears in exactly one row;
  - no word of the old pairs is drawn anywhere on the page.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, PANEL_IN, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

FRENCH = json.loads((pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n" / "fr.json")
                    .read_text(encoding="utf-8"))
STATES = FRENCH["states"]
LABEL = FRENCH["screens"]["system"]["automaticTrigger"]
# The words the one pair replaced — none may be drawn again.
OLD_WORDS = ("coupé", "Désactivé", "Activée")  # french-ok: the retired words this rule refuses

READ = """(label)=>{
  const row = document.querySelector('[data-part="levers/watcher-state"]');
  const chip = row && row.querySelector('[data-part="flux/value"] [data-part="chip"]');
  const view = document.querySelector('#view');
  const text = (view && view.textContent) || '';
  return {
    chip: chip ? chip.textContent.replace(/\\s+/g, ' ').trim() : null,
    tone: chip ? chip.dataset.tone || null : null,
    named: [...document.querySelectorAll('#view [data-part="flux/name"], #view [data-part="topic/title"]')]
      .filter((node) => node.textContent.trim() === label).length,
    text,
  };
}"""


async def main():
    """Reads the processing's row in both states."""
    journal = Journal("R-conformity-e — one mechanism, one row, one on/off pair")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state, word, tone in (("levers-idle", STATES["active"], "success"),
                                  ("levers-trigger-off", STATES["inactive"], "danger")):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ, LABEL)
            journal.check(f"{state}: the processing's row wears the chip « {word} »",
                          read["chip"] == word, f"chip {read['chip']!r}")
            journal.check(f"{state}: in the pair's tone, {tone}", read["tone"] == tone, f"tone {read['tone']!r}")
            journal.check(f"{state}: the page names the mechanism once", read["named"] == 1,
                          f"{read['named']} row(s) named « {LABEL} »")
            old = [one for one in OLD_WORDS if one in read["text"]]
            journal.check(f"{state}: no word of the retired pairs is drawn", not old, f"{old}")
        # THE SETTINGS FIELD SAYS THE SAME PAIR beside its switch.
        await page.evaluate("(id)=>window.__go(id)", "settings-field-boolean")
        await page.wait_for_timeout(PANEL_IN)
        said = await page.evaluate("""()=>{
          const field = document.querySelector('#sheetin [data-part="field"]');
          return field ? field.textContent.replace(/\\s+/g, ' ').trim() : null;}""")
        journal.check("settings-field-boolean: the field says the pair's word",
                      said in (STATES["active"], STATES["inactive"]), f"{said!r}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
