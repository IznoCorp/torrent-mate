"""R237 — « Chercher maintenant » on a follow queues its search, and says it is « en file ».

THE SEARCH IS QUEUED, LIKE THE GRAB (operator ruling O-6 B, 2026-11-27: « la page
reçoit « en file » tout de suite, le résultat arrive sur la fiche et dans le
sélecteur une fois la recherche finie »). The follow sheet's primary act on a
follow with nothing to take sends `searchForFollow` for THAT follow:

1. the tap sends the follow's own search — one POST to its address;
2. it is answered 202 `{queued, runUid}`, with no result in the answer;
3. it says the search is « en file » for that title, and announces no result;
4. the result is read afterwards: the follows are read again, the follow counts
   one more search, and `readReleases` answers what it holds for the medium.

The expected sentence is read from the interface's resources, and what the follow
and its releases hold from the layer itself, never written here. The follow with
nothing to read is a follow CREATED on a suggestion the seeds hold no release
for — every seeded follow has at least one.
"""
import asyncio
import json
import pathlib
from urllib.parse import unquote

from common import ACTED, KEY_OF_JS, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
SAID = WORDS["verbs"]["acquisition"]
TOAST = "()=>(document.querySelector('#toast')||{}).textContent || ''"
# A FOLLOW IS ADDRESSED BY ITS MEDIUM'S KEY (K3-G1, K3-G5), TVDB first for a show and TMDB first for a film.
KEY_OF = KEY_OF_JS
RELEASES = """async (key) => (await (await fetch(
  '/api/v1/acquisition/releases?followedId=' + encodeURIComponent(key))).json()).length"""
FOLLOWS = "async () => {" + KEY_OF + """
  return (await (await fetch('/api/v1/acquisition/followed')).json())
    .map((follow) => ({ title: follow.title, status: follow.status, searches: follow.searches,
      key: keyOf(follow) })); }"""
# THE ANSWER'S BODY, which the layer's record of calls does not hold: kept as the interface receives it.
KEEP_ANSWERS = """() => {
  window.__searchAnswers = [];
  const answer = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const response = await answer(input, init);
    const asked = new Request(input, init);
    if (asked.method === 'POST' && new URL(asked.url).pathname.endsWith('/search'))
      window.__searchAnswers.push(await response.clone().json());
    return response;
  };
}"""
# A suggestion the seeds hold no release for, followed through the layer.
UNFOUND = "async () => {" + KEY_OF + """
  const deck = await (await fetch('/api/v1/acquisition/suggestions')).json();
  for (const one of deck.suggestions) {
    if (one.ids?.tmdb === undefined) continue;
    const kind = one.kind === 'Film' ? 'movie' : 'show';
    const answer = await fetch('/api/v1/acquisition/followed', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: one.title, kind, provider: 'tmdb', providerId: Number(one.ids.tmdb) }) });
    if (!answer.ok) continue;
    const created = await answer.json();
    // NO RELEASE FOR IT, read once the follow exists: a release list is the medium's, by its key.
    const key = keyOf(created);
    const releases = await (await fetch('/api/v1/acquisition/releases?followedId='
      + encodeURIComponent(key))).json();
    if (releases.length > 0) {
      await fetch('/api/v1/acquisition/followed/' + encodeURIComponent(key), { method: 'DELETE' });
      continue;
    }
    await window.__queries.invalidateQueries({ queryKey: ['/api/v1/acquisition/followed'] });
    return created.title ?? one.title;
  }
  return null;
}"""


def base_title(title):
    """The title as a sentence says it — without a year in parentheses."""
    words = title.split(" ")
    return " ".join(word for word in words
                    if not (word.startswith("(") and word.endswith(")") and word[1:-1].isdigit())).strip()


def queued(title):
    """What the tap says, from the resources."""
    return SAID["searchQueued"].replace("{{title}}", base_title(title))


async def searches_of(page, title):
    """How many searches the layer counts on the follow, and its key."""
    follow = next(follow for follow in await page.evaluate(FOLLOWS) if follow["title"] == title)
    return follow["searches"], follow["key"]


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
    journal = Journal("R237 — « Chercher maintenant » queues the search, and says it is « en file »")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate("()=>window.__go('acq-follows-list')")
        await page.wait_for_timeout(SETTLED)

        await page.evaluate(KEEP_ANSWERS)
        follows = await page.evaluate(FOLLOWS)
        pending = next((follow for follow in follows if follow["status"] == "pending"), None)
        searched = pending["title"] if pending else None
        journal.check("a follow waiting for a release is seeded", searched is not None, str(follows))
        if searched is not None:
            calls, said = await search(page, searched)
            address = f"/api/v1/acquisition/followed/{pending['key']}/search"  # the recorded path is read decoded
            sent = [(unquote(call.get("path", "")), call.get("status")) for call in calls
                    if call.get("operationId") == "searchForFollow" and call.get("method") == "POST"]
            journal.check(f"the tap on « {searched} » sends its own search, once, answered 202",
                          sent == [(address, 202)], json.dumps(calls, ensure_ascii=False))
            answers = await page.evaluate("()=>window.__searchAnswers")
            journal.check("the answer says queued, names its run, and carries no result",
                          len(answers) == 1 and sorted(answers[0]) == ["queued", "runUid"]
                          and answers[0]["queued"] is True and bool(answers[0]["runUid"]), str(answers))
            journal.check("it says the search is « en file » for that title",
                          said == queued(searched), f"said {said!r}")
            operations = [call.get("operationId") for call in calls]
            after = operations[operations.index("searchForFollow") + 1:] if "searchForFollow" in operations else []
            journal.check("the follows are read again, after the search was queued",
                          "readFollows" in after, str(operations))
            count, key = await searches_of(page, searched)
            journal.check("the follow, read afterwards, counts one more search",
                          count == pending["searches"] + 1, f"{pending['searches']} -> {count}")
            held = await page.evaluate(RELEASES, key)
            journal.check("its releases are read afterwards from `readReleases`", held > 0, f"{held} release(s)")

        unfound = await page.evaluate(UNFOUND)
        journal.check("a follow the seeds hold no release for can be created", unfound is not None, str(unfound))
        if unfound is not None:
            await page.wait_for_timeout(SETTLED)
            before, key = await searches_of(page, unfound)
            calls, said = await search(page, unfound)
            journal.check("its search is « en file » too, and announces no result",
                          said == queued(unfound), f"said {said!r}")
            count, _ = await searches_of(page, unfound)
            held = await page.evaluate(RELEASES, key)
            journal.check("afterwards the follow counts the search and `readReleases` answers none",
                          count == before + 1 and held == 0, f"{before} -> {count}, {held} release(s)")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
