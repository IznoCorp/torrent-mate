"""R227 — « Supprimer » deletes a set-aside folder for real, and only once he confirms.

A folder he set aside is still on the machine and still has to be dealt with
(ruling 16). One of the four things the folded « Mis de côté » lets him do is
delete it: a REAL deletion of the staging folder — not the quarantine
« Abandonner » makes — behind a confirmation of the same care as the
Médiathèque's, which names the folder (it has no provider identity) and says
whether this copy is the only one.

Walked by finger on « Lucky », a real pending decision set aside:

1. its card in « Mis de côté » offers « Supprimer »;
2. the tap opens a confirmation naming the folder and saying its case, and
   NOTHING is sent before it is confirmed;
3. « Annuler » sends nothing and leaves the card where it was;
4. confirmed, the deletion is ANSWERED on the network, and the card leaves
   « Mis de côté »;
5. both reads asked again, it does not come back — the mock's state, not the
   screen's;
6. the confirmation says the case its read answered, on three folders: the
   torrent keeps its files (« Lucky », the case POSED on it — RULINGS 22: a
   derivation the backend replaces by qBittorrent's answer at the gesture), the
   only copy (« Top Chef Le Concours Parallèle », dropped by hand, no torrent),
   and unknown, treated as the only copy (« Lucky » with nothing posed).

Red before the move: the card offers no « Supprimer ».
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))
FOOT = WORDS["screens"]["acquisition"].get("deleteFoot")
CASE = WORDS["verbs"]["acquisition"].get("deleteStaged", {}).get("caseUnknown")
# Each case's named state, its folder and the words its confirmation must say.
CASES = {
    "acq-delete-keeps-files": ("Lucky", "caseKeepsFiles"),
    "acq-delete-only-copy": ("Top Chef Le Concours Parallèle (2026)", "caseOnlyCopy"),
    "acq-delete-unknown": ("Lucky", "caseUnknown"),
}
FOLDER = "Lucky"
SECTION = '[data-part="section/set-aside"]'
OPERATION = "deleteStagedMedia"

ASIDE = f"""() => {{
  const section = document.querySelector('#view {SECTION}');
  return section ? [...section.querySelectorAll('[data-part="card/title"]')].map(one => one.textContent) : [];
}}"""
FOOT_OF = f"""(title) => {{
  const section = document.querySelector('#view {SECTION}');
  if (!section) return null;
  const foot = [...section.querySelectorAll('[data-part="card/foot"]')]
    .find(one => one.getAttribute('data-staging-delete') === title);
  return foot ? foot.textContent.trim() : null;
}}"""
TAP_FOOT = f"""(title) => {{
  const foot = [...document.querySelectorAll('#view {SECTION} [data-part="card/foot"]')]
    .find(one => one.getAttribute('data-staging-delete') === title);
  if (!foot) return false; foot.click(); return true;
}}"""
DIALOG = """() => {
  const open = document.querySelector('[data-part="dialog"][data-open]');
  return open ? open.textContent : null;
}"""
TITLES = """() => [...document.querySelectorAll('#view [data-part="card/title"]')].map(one => one.textContent)"""
ANSWERED = """(operation) => (window.__mocks?.answered() || [])
  .filter(call => call.operationId === operation && call.status === 200)
  .map(call => decodeURIComponent(call.path))"""
PRESS = """(danger) => {
  const buttons = [...document.querySelectorAll('[data-part="dialog"][data-open] [data-part="dialog/button"]')];
  const button = buttons.find(one => (one.dataset.tone === 'danger') === danger);
  if (!button) return false; button.click(); return true;
}"""


async def main():
    journal = Journal("R227 — « Supprimer » deletes a set-aside folder, once confirmed")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-card-set-aside');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-card-set-aside exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        journal.check(f"« {FOLDER} » is in « Mis de côté »", FOLDER in await page.evaluate(ASIDE), "")

        foot = await page.evaluate(FOOT_OF, FOLDER)
        journal.check("its card offers « Supprimer »", FOOT is not None and foot == FOOT, f"{foot!r}")

        # ── the confirmation, then « Annuler » ───────────────────────────────
        await page.evaluate(TAP_FOOT, FOLDER)
        await page.wait_for_timeout(ACTED)
        text = await page.evaluate(DIALOG)
        journal.check("the tap opens a confirmation naming the folder and its case",
                      text is not None and FOLDER in text and CASE is not None and CASE in text, f"{text!r}")
        journal.check("nothing is sent before it is confirmed",
                      not await page.evaluate(ANSWERED, OPERATION), "")
        cancelled = await page.evaluate(PRESS, False)
        await page.wait_for_timeout(ACTED)
        journal.check("« Annuler » sends nothing and the card stays in « Mis de côté »",
                      cancelled and not await page.evaluate(ANSWERED, OPERATION)
                      and FOLDER in await page.evaluate(ASIDE) and await page.evaluate(DIALOG) is None,
                      f"cancelled {cancelled}")

        # ── confirmed ────────────────────────────────────────────────────────
        await page.evaluate(TAP_FOOT, FOLDER)
        await page.wait_for_timeout(ACTED)
        confirmed = await page.evaluate(PRESS, True)
        await page.wait_for_timeout(SETTLED)
        answered = await page.evaluate(ANSWERED, OPERATION)
        journal.check("confirmed, the deletion is answered on the network",
                      confirmed and any(path.endswith("/" + FOLDER) for path in answered),
                      f"confirmed {confirmed}, answered {answered}")
        journal.check("and the card has left « Mis de côté »", FOLDER not in await page.evaluate(ASIDE), "")

        # ── the layer holds it: both reads asked again ───────────────────────
        await page.evaluate("""()=>{
            window.__queries?.removeQueries({ queryKey: ["/api/v1/acquisition/to-handle"] });
            window.__queries?.removeQueries({ queryKey: ["/api/v1/staging/media"] }); }""")
        await page.evaluate("()=>document.querySelector('[data-acqtab=\"now\"]')?.click()")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("()=>document.querySelector('[data-acqtab=\"todo\"]')?.click()")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(f"()=>document.querySelector('#view {SECTION} summary')?.click()")
        await page.wait_for_timeout(ACTED)
        titles = await page.evaluate(TITLES)
        journal.check("both reads asked again, it does not come back", FOLDER not in titles, str(titles))

        # ── each case, as its named state opens the confirmation ─────────────
        for state, (folder, key) in CASES.items():
            words = WORDS["verbs"]["acquisition"].get("deleteStaged", {}).get(key)
            answer = await page.evaluate(
                "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            await page.wait_for_timeout(SETTLED)
            text = await page.evaluate(DIALOG)
            journal.check(f"{state}: the confirmation names « {folder} » and says its case",
                          text is not None and folder in text and words is not None and words in text,
                          f"{text!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
