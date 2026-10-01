"""R400 — a Système section whose own read failed says so (L24 S2, NE-DOIT-PAS-5).

Production's compact health card said, domain by domain, « Disques — état
indisponible ». The maquette's Système page drew each section's heading over an
EMPTY list when that section's read failed — `const { data = [] }` turns a
failure into « nothing to report », which is the « rien ne se passe » without a
reason § 8 forbids. The whole-page error state covers only the case where
everything failed.

WHAT IS READ, for each of the four machine sections — « Services », « Disques »,
« Index de la médiathèque », « Dépendances » — in the state that fails ITS read
alone (`system-<section>-unavailable`, the layer's `setOperationOutcome`):

  1. the failed section draws exactly one row, and that row wears the `alert`
     tone (the chip's `danger`);
  2. its value is the interface's word for « unavailable » (`fr.json`), never
     an empty list;
  3. every OTHER machine section still draws its own rows, none of them the
     unavailable row — one failed read does not take the page down;
  4. the menu's badge counts the section that cannot be read as ONE fault, in
     place of what that section counted when it answered — never as fine.
     RE-AIMED (reader, 2026-10-01): the badge DROPPED, 3 → 2, when `readDisks`
     or `readIndexHealth` failed.

And in the healthy state `system`, no section draws the unavailable row.
"""
import asyncio
import json
import pathlib

from common import Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
SYSTEM = WORDS["screens"]["system"]
UNAVAILABLE = SYSTEM["unavailable"]

# The four machine sections: the key of their heading in `fr.json`, and the
# named state that fails their read alone.
SECTIONS = (
    ("services", "system-services-unavailable"),
    ("disks", "system-disks-unavailable"),
    ("index", "system-index-unavailable"),
    ("dependencies", "system-dependencies-unavailable"),
)

# Every section of the page, read as its heading and the rows of the first fact
# list that follows it (before the next heading).
READ = """() => {
  const out = {};
  const headings = [...document.querySelectorAll('#view [data-part="heading"]')];
  headings.forEach((heading, index) => {
    const next = headings[index + 1];
    let list = null;
    for (let node = heading.nextElementSibling; node && node !== next; node = node.nextElementSibling) {
      if (node.matches('[data-part="flux"]')) { list = node; break; }
    }
    out[heading.textContent.trim()] = list ? [...list.querySelectorAll('[data-part="flux/row"]')].map((row) => ({
      value: row.querySelector('[data-part="flux/value"]')?.textContent.trim() ?? '',
      tone: row.querySelector('[data-part="flux/value"] [data-part="chip"]')?.dataset.tone ?? null,
    })) : [];
  });
  return out;
}"""


BADGE = """() => document.querySelector('[data-drawer] [data-part="shell/menu-badge"]')?.textContent.trim() ?? null"""

# The tone each section's rows are counted on by the badge: a machine fault is
# an alert (`danger`), a disk or the index asking for care a warning.
COUNTED = {"services": "danger", "dependencies": "danger", "disks": "warning", "index": "warning"}


async def main():
    journal = Journal("R400 — a Système section whose own read failed says so")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        healthy = await read_at(page, "system", READ)
        at_rest = int(await page.evaluate(BADGE) or 0)
        stray = [heading for heading, rows in healthy.items()
                 if any(row["value"] == UNAVAILABLE for row in rows)]
        journal.check("healthy, no section draws the unavailable row", stray == [], str(stray))

        for key, state in SECTIONS:
            heading = SYSTEM[key]
            sections = await read_at(page, state, READ)
            failed = sections.get(heading, [])
            journal.check(f"{state}: « {heading} » draws one row, not an empty list",
                          len(failed) == 1, str(failed))
            journal.check(f"{state}: that row says « {UNAVAILABLE} » in the alert tone",
                          len(failed) == 1 and failed[0]["value"] == UNAVAILABLE
                          and failed[0]["tone"] == "danger", str(failed))
            others = {SYSTEM[other]: sections.get(SYSTEM[other], []) for other, _ in SECTIONS if other != key}
            standing = all(rows and all(row["value"] != UNAVAILABLE for row in rows)
                           for rows in others.values())
            journal.check(f"{state}: every other machine section still draws its rows", standing,
                          str({name: len(rows) for name, rows in others.items()}))
            counted = sum(1 for row in healthy.get(heading, []) if row["tone"] == COUNTED[key])
            badge = int(await page.evaluate(BADGE) or 0)
            journal.check(f"{state}: the badge counts the unreadable section as one fault, never as fine",
                          badge == at_rest - counted + 1,
                          f"badge {badge}, at rest {at_rest}, the section counted {counted} when read")

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
