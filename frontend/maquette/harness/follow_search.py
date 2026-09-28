"""R237 — « Chercher maintenant » on a follow searches, and says what it found.

What was not found reads on the follow, and a live search CONFIRMS it (« une
recherche en direct le confirme par « aucun torrent trouvé » »). The follow
sheet's primary act on a follow with nothing to take used to close the sheet
and announce a search that nothing sent, pointing at a card that no longer
exists. Now the tap sends `searchForFollow` for THAT follow and reads its
answer:

1. the tap sends the follow's own search — one POST to its address;
2. a search that found releases says how many;
3. a search that found none says « aucun torrent trouvé » for that title.

Every expected sentence is read from the interface's resources, and every count
from the layer's own releases for the title (`readReleases`), never written
here. The zero case is a follow CREATED on a suggestion the seeds hold no
release for — every seeded follow has at least one.
"""
import asyncio
import json
import pathlib
from urllib.parse import unquote

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
SAID = WORDS["verbs"]["acquisition"]
TOAST = "()=>(document.querySelector('#toast')||{}).textContent || ''"
RELEASES = """async (title) => (await (await fetch(
  '/api/acquisition/releases?title=' + encodeURIComponent(title))).json()).length"""
FOLLOWS = """async () => (await (await fetch('/api/acquisition/followed')).json())
  .map((follow) => ({ title: follow.title, status: follow.status }))"""
# A suggestion the seeds hold no release for, followed through the layer.
UNFOUND = """async () => {
  const deck = await (await fetch('/api/acquisition/suggestions')).json();
  for (const one of deck) {
    const releases = await (await fetch('/api/acquisition/releases?title='
      + encodeURIComponent(one.title))).json();
    if (releases.length > 0 || one.ids?.tmdb === undefined) continue;
    const kind = one.kind === 'Film' ? 'movie' : 'show';
    const answer = await fetch('/api/acquisition/followed', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: one.title, kind, provider: 'tmdb', providerId: Number(one.ids.tmdb) }) });
    if (!answer.ok) continue;
    const created = await answer.json();
    await window.__queries.invalidateQueries({ queryKey: ['/api/acquisition/followed'] });
    return created.title ?? one.title;
  }
  return null;
}"""


def base_title(title):
    """The title as a sentence says it — without a year in parentheses."""
    words = title.split(" ")
    return " ".join(word for word in words
                    if not (word.startswith("(") and word.endswith(")") and word[1:-1].isdigit())).strip()


def sentence(count, title):
    """What the search says, from the resources."""
    if count == 0:
        template = SAID["searchFoundNone"]
    else:
        template = SAID["searchFound_one" if count == 1 else "searchFound_other"]
    return template.replace("{{count}}", str(count)).replace("{{title}}", base_title(title))


async def search(page, title):
    """Taps the follow sheet's primary act; returns the calls it made and what it said."""
    before = len(await page.evaluate("()=>window.__mocks.answered()"))
    await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
    await page.wait_for_timeout(ACTED)
    await page.click("#sheet [data-sheetprim]")
    await page.wait_for_timeout(ACTED)
    await page.evaluate("()=>window.__mocks.quiet()")
    await page.wait_for_timeout(ACTED)
    calls = (await page.evaluate("()=>window.__mocks.answered()"))[before:]
    return calls, (await page.evaluate(TOAST)).strip()


async def main():
    journal = Journal("R237 — « Chercher maintenant » searches, and says what it found")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate("()=>window.__go('acq-follows-list')")
        await page.wait_for_timeout(SETTLED)

        follows = await page.evaluate(FOLLOWS)
        searched = next((follow["title"] for follow in follows if follow["status"] == "pending"), None)
        journal.check("a follow waiting for a release is seeded", searched is not None, str(follows))
        if searched is not None:
            found = await page.evaluate(RELEASES, searched)
            calls, said = await search(page, searched)
            address = f"/api/acquisition/followed/{searched}/search"
            sent = [unquote(call.get("path", "")) for call in calls
                    if call.get("operationId") == "searchForFollow" and call.get("method") == "POST"]
            journal.check(f"the tap on « {searched} » sends its own search, once",
                          sent == [address], json.dumps(calls, ensure_ascii=False))
            journal.check(f"it says how many releases the search found ({found})",
                          found > 0 and said == sentence(found, searched), f"said {said!r}")

        unfound = await page.evaluate(UNFOUND)
        journal.check("a follow the seeds hold no release for can be created", unfound is not None, str(unfound))
        if unfound is not None:
            await page.wait_for_timeout(SETTLED)
            calls, said = await search(page, unfound)
            journal.check("a search that found nothing says « aucun torrent trouvé » for that title",
                          said == sentence(0, unfound), f"said {said!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
