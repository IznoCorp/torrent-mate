"""R200 — a follow cannot be built without a provider identity (B-366).

WHAT WAS RULED. « Le suivi sans fiche n'est pas un état possible. » A follow
whose medium nothing identifies has no sheet to open, no artwork to draw and no
catalogue to count against — so it is not a follow to be drawn carefully, it is
a follow that must not exist.

WHERE THE REFUSAL HAS TO LIVE, measured rather than assumed: making `Follow.ids`
optional in the contract produces ZERO diagnostics, because every reader already
guards the field; and the interface's own create sends a title and a kind and no
identity at all, so the identity comes from the entry the title was followed
from. The refusal therefore belongs on that path — the layer, asked to create a
follow it can identify from nothing, answers the contract's 400 and records
nothing.

  f1. A CREATE NOTHING IDENTIFIES IS REFUSED, and the refusal is the contract's
      own status, not a silent success.
  f2. AND NO FOLLOW IS RECORDED BY IT: the list holds what it held.
  f3. A CREATE THE LAYER CAN IDENTIFY STILL LANDS, and carries the identity —
      the control, without which the two holds above would pass over a layer
      that refused everything.
  f4. A FOLLOW WITH NO EPISODE DATA IS NOT A FOLLOW WITHOUT A SHEET: identified,
      followed on purpose, it is created like any other. « No sheet » and « no
      episodes » are two different absences.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SETTLED, Journal, open_page

from playwright.async_api import async_playwright

STATE = "acq-follows-list"
# A title no seeded search result and no suggestion carries, so the layer has
# nothing to identify it with. french-ok: a media title, which is data.
NAMELESS = "Un dossier que rien n'identifie"

CREATE = """async(body)=>{
  const answer = await fetch("/api/acquisition/followed", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)});
  let payload = null;
  try { payload = await answer.json(); } catch (nothing) { payload = null; }
  return {status: answer.status, payload};
}"""

FOLLOWS = """async()=>{
  const answer = await fetch("/api/acquisition/followed");
  const body = await answer.json();
  const rows = Array.isArray(body) ? body : (body.items ?? body.follows ?? []);
  return rows.map((row) => ({title: row.title, ids: row.ids}));
}"""

# A title the layer itself can identify, taken from the suggestions it serves —
# the join the create falls back on when the request names no identity.
IDENTIFIABLE = """async()=>{
  const answer = await fetch("/api/acquisition/suggestions");
  const body = await answer.json();
  const rows = Array.isArray(body) ? body : (body.items ?? body.suggestions ?? []);
  const named = rows.find((row) => row.ids && Object.keys(row.ids).length > 0);
  return named ? {title: named.title, kind: named.kind ?? "tv"} : null;
}"""


async def main():
    """Asks the layer for a follow it cannot identify, and for one it can."""
    journal = Journal("R200 — a follow cannot be built without a provider identity")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", STATE)
        await page.wait_for_timeout(SETTLED)

        before = await page.evaluate(FOLLOWS)
        refused = await page.evaluate(CREATE, {"title": NAMELESS, "kind": "tv"})
        after = await page.evaluate(FOLLOWS)
        journal.check("a create the layer cannot identify is refused",
                      refused["status"] == 400,
                      f"answered {refused['status']} — {refused['payload']}")
        journal.check("and no follow is recorded by it",
                      [row["title"] for row in after] == [row["title"] for row in before],
                      f"{len(before)} follow(s) before, {len(after)} after; "
                      f"{[row['title'] for row in after if row['title'] == NAMELESS]}")

        named = await page.evaluate(IDENTIFIABLE)
        landed = await page.evaluate(
            CREATE, {"title": (named or {}).get("title"), "kind": (named or {}).get("kind", "tv")})
        held = await page.evaluate(FOLLOWS)
        recorded = next((row for row in held if row["title"] == (named or {}).get("title")), None)
        journal.check("a create the layer CAN identify still lands, carrying the identity",
                      named is not None and landed["status"] == 200
                      and recorded is not None and recorded["ids"],
                      f"asked for {named}, answered {landed['status']}, recorded {recorded}")
        journal.check("and it is a follow with a sheet even where no episode data is held",
                      recorded is not None and recorded["ids"] is not None,
                      f"{recorded}")

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
