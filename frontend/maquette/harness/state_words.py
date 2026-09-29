"""R-conformity-f — a state is a code in the data and ONE word in the interface.

THE DEFECT THIS ENDS. Système's seeds carried their state words themselves —
« en ligne », « connecté », « disponibles », « joignable » for one state — where
no guard over the interface's resources could see them. The operator ruled: the
data carry a state CODE, the word is the interface's, one per state.

WHAT IT READS:
  - the five seeds Système draws its facts from: no row carries a state WORD — a
    row is a `state` code, or a quantity (`value` with the `info` tone);
  - on `system`, every row whose seed carries a code says `states.<code>` from
    `fr.json`, and every row of one code says the SAME word.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "design" / "src"
STATES = json.loads((SOURCE / "i18n" / "fr.json").read_text(encoding="utf-8"))["states"]
SEEDS = ("services", "schedulers", "disks", "index-health", "dependencies")
QUANTITY_TONE = "info"

VALUES = """()=>Object.fromEntries([...document.querySelectorAll('#view [data-part="flux/row"], #view li')]
  .map((row) => [row.querySelector('[data-part="flux/name"]')?.textContent.trim(),
                 row.querySelector('[data-part="flux/value"]')?.textContent.replace(/\\s+/g, ' ').trim()])
  .filter(([name]) => name))"""


async def main():
    """Reads the seeds, then the page they are drawn on."""
    journal = Journal("R-conformity-f — a state is a code in the data and one word in the interface")
    rows = []
    for name in SEEDS:
        for row in json.loads((SOURCE / "mocks" / "seeds" / f"{name}.json").read_text(encoding="utf-8")):
            rows.append(row)
            if "state" not in row:
                journal.check(f"{name} · {row['label']}: a row with no code is a quantity",
                              row.get("tone") == QUANTITY_TONE, f"{row}")
    coded = [row for row in rows if "state" in row]
    journal.check("the seeds carry codes at all", len(coded) >= 20, f"{len(coded)} coded row(s)")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        await page.evaluate("(id)=>window.__go(id)", "system")
        await page.wait_for_timeout(SETTLED)
        drawn = await page.evaluate(VALUES)
        words: dict[str, set[str]] = {}
        for row in coded:
            said = drawn.get(row["label"])
            words.setdefault(row["state"], set()).add(said or "")
            journal.check(f"« {row['label']} » says its state in the interface's word",
                          said == STATES.get(row["state"]), f"said {said!r}, code {row['state']!r}")
        for code, said in sorted(words.items()):
            journal.check(f"every row in state {code} says ONE word", len(said) == 1, f"{sorted(said)}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
