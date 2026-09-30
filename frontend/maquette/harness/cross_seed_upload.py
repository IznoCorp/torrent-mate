"""R450–R454 — « Créer et publier un torrent »: offered where nothing cross-seeds, confirmed, answered, read.

§ 19 point 5: « l'application peut créer un torrent et le publier sur un tracker
pour ouvrir un cross-seed »; « un échec de publication ou de création est un
échec du cross-seed, compté comme tel » (round 8 Q8, « le cas A »). Round 11:
OPEN 1 = A, only a torrent active in the client, complete and seeding, from its
own row; OPEN 2 = B, a tracker's « accepte les uploads » switch, distinct from
its cross-seed one; OPEN 3 = A, the interface pre-validates nothing, the
tracker's refusal is read on the row with its reason; OPEN 4 = A, only the row
remains, counted in the badge while in error. DOIT-4 / NE-DOIT-PAS-3: one ask, a
visible « en file », never « occupé »; NE-DOIT-PAS-4: never a bare code;
NE-DOIT-PAS-6, in the creating direction: a confirmation that names what is
published and where. L23 DESIGN § 2.3, § 4 (labels R-L23-a … e).

R451 (R-L23-b) — offered only where nothing already cross-seeds:
1. the act is offered ONLY on a pair with no match, in error or not yet searched,
   not excluded, its origin seeding whole — never on « actif », « stoppé »,
   « tracker sans cross-seed », an excluded pair or title, nor while the
   original still downloads;
2. the pair's tracker no longer accepting uploads: the act is gone, its line
   says why, the search is still offered; its cross-seed switch off: the act is
   gone too, the switch's own reason said once;
3. the layer's own handler refuses an upload asked where the act is not drawn;
3b. the pair's tracker ITSELF switched off, by a failure (lacale, « Injoignable »)
   or by the operator, its two cross-seed switches left on: neither the upload
   nor the search is offered, the row's line says the tracker is off and why,
   and the layer's handlers refuse both (§ 17 point 1).

R453 (R-L23-d) — the confirmation names what is published, before any call:
4. `torrents-cross-seed-upload-confirm`: the tracker and the release whose files
   are sent are named; nothing is called until confirmed, nothing on « Annuler ».

R452 (R-L23-c) — the call is answered, visible, and resolved in the same visit:
5. confirmed: ONE `uploadCrossSeed`, even under a double tap; the pair reads
   « en file », never « occupé »;
6. its outcome arrives by `CrossSeedInjected`, no finger on the page: the pair
   reads « actif », « publié par vous le … », and the Torrents tab carries a new
   card marked « Publié par vous » on that tracker;
7. `torrents-cross-seed-upload-queued` reads « en file » and offers nothing more.

R450 (R-L23-a) — the two codes are sentenced, never bare:
8. `torrents-cross-seed-upload-refused-creation` / `-publish`: « erreur de
   cross-seed », the code's sentence and its kind of trouble, no code in the
   text; the publication's refusal says the tracker's own reason, the
   creation's none.

R454 (R-L23-e, re-aims R-L17-g/h) — the badge's slot filled, the stream the same:
9. an upload refused by the tracker arrives by `CrossSeedRejected` and moves the
   open row and the badge by one, the badge still the SAME five terms' sum.

Red before the move: no pair offers « Créer et publier un torrent », no state is named.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["crossSeed"]
SEED = json.loads((ROOT / "mocks/seeds/cross-seed.json").read_text(encoding="utf-8"))
CROSS_SEEDING = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
REFUSED = "8d51568b1a4f46e1fb7e7b535b52a5203312fc28"
UNSEARCHED = "c44e8cd75bec37a8337175c6580e85d4e2079da3"
EXCLUDED = "e1af6819d9e3159e0aa191b534b6a66af4344788"
UPLOADABLE = "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb"
LANTERNS = "0ff265e478d97d9eae4d1cabd13748e23b9e6cba"
UPLOADABLE_STATES = {"noMatch", "error", "notSearched"}
ACT = '#sheet[data-open] [data-cross-seed-upload$=":v3x.club"]'
DIALOG = '[data-part="dialog"][data-open]'
BUTTONS = f'{DIALOG} [data-part="dialog/button"]'
# Long enough for the engine's queued upload to end (the layer's SEARCH_MILLISECONDS, 4 s).
UPLOAD_ENDS = 6000
# A code as the engine writes it: a word, an underscore, a word.
BARE = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")

OFFERS = """() => {
  const origin = document.querySelector('#sheet[data-open] [data-part="torrents/cross-seed"]');
  const entry = (window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [])
    .find(one => one.infoHash === origin?.dataset.entry);
  return [...document.querySelectorAll('#sheet[data-open] [data-part="torrents/cross-seed-row"]')].map(row => ({
    tracker: row.dataset.tracker, state: row.dataset.state, excluded: row.dataset.excluded === 'true',
    trackerOff: row.querySelector('[data-part="torrents/cross-seed-tracker-off"]')?.textContent.trim() ?? null,
    titleExcluded: origin?.dataset.titleExcluded === 'true',
    seeding: !!entry && entry.progress >= 1 && entry.state === 'seeding',
    trackerOn: (() => { const one = (window.__queries?.getQueryData(['/api/trackers']) || [])
      .find(t => t.name === row.dataset.tracker); return !one || (one.enabled && !one.disabled); })(),
    offered: !!row.querySelector('[data-part="torrents/cross-seed-upload"]'),
    searched: !!row.querySelector('[data-part="torrents/cross-seed-search"]'),
    queued: row.querySelector('[data-part="torrents/cross-seed-upload-queued"]')?.textContent.trim() ?? null,
    off: row.querySelector('[data-part="torrents/cross-seed-upload-off"]')?.textContent.trim() ?? null,
    date: row.querySelector('[data-part="torrents/cross-seed-date"]')?.textContent.trim() ?? null,
    reason: row.querySelector('[data-part="torrents/cross-seed-reason"]')?.dataset.reason ?? null,
    reasonText: row.querySelector('[data-part="torrents/cross-seed-reason"]')?.textContent.trim() ?? null,
    trackerReason: row.querySelector('[data-part="torrents/cross-seed-tracker-reason"]')?.textContent.trim() ?? null,
    text: row.textContent,
  }));
}"""
UPLOADS = """() => (window.__mocks?.answered() || []).filter(call => call.operationId === 'uploadCrossSeed')"""
BADGE = """() => document.querySelector('[data-part="shell/tab-bar"] [data-page="trackers"] [data-part="shell/tab-badge"]')
  ?.textContent.trim() ?? ''"""
SUM = """() => {
  const get = (address) => window.__queries?.getQueryData([address]);
  const trackers = get("/api/trackers") ?? [];
  const downloads = get("/api/acquisition/downloads")?.downloads ?? [];
  const obligations = get("/api/acquisition/obligations")?.items ?? [];
  const active = new Set(downloads.map((entry) => `${entry.infoHash}:${entry.tracker}`));
  const under = trackers.filter((one) => one.alertThreshold !== null && one.ratio !== null
    && one.ratio < one.alertThreshold).length;
  const failed = trackers.filter((one) => one.disabled?.by === "failure").length;
  const breached = obligations.filter((one) => one.breachedAt !== null && one.satisfiedAt === null
    && one.releasedAt === null && active.has(`${one.infoHash}:${one.sourceTracker}`)).length;
  const unseen = trackers.reduce((total, one) => total + one.brokenObligations.filter((row) => !row.seen).length, 0);
  const crossSeed = trackers.reduce((total, one) => total + one.crossSeed.failed, 0);
  return under + failed + breached + unseen + crossSeed;
}"""
PUBLISHED_CARD = """(tracker) => [...document.querySelectorAll('#view [data-part="torrents/row"]')]
  .filter(row => row.querySelector('[data-part="torrents/origin"]')?.dataset.origin === 'published')
  .map(row => ({ tracker: row.querySelector('[data-part="torrents/tracker"]')?.textContent.trim(),
                 word: row.querySelector('[data-part="torrents/origin"]')?.getAttribute('aria-label') }))
  .filter(card => card.tracker === tracker)"""
# Asks the layer for an upload the way the interface would, bypassing the act.
FORCE = """async ([hash, tracker]) => (await fetch(
  `/api/torrents/${hash}/cross-seed/${encodeURIComponent(tracker)}/upload`, { method: 'POST' })).status"""
# Asks the layer for a search on one pair the way the interface would, bypassing the act.
FORCE_SEARCH = """async ([hash, tracker]) => (await fetch(`/api/torrents/${hash}/cross-seed/search`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tracker }) })).status"""
# Writes tracker settings the way Réglages does — the operator's own gesture — and
# forgets the page's stale trackers read.
WRITE = """async (values) => {
  const status = (await fetch('/api/config/files/tracker', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) })).status;
  window.__queries?.removeQueries({ queryKey: ['/api/trackers'] });
  return status;
}"""
# Poses a scenario on the layer and forgets the page's stale trackers read.
POSE = """([dial, args]) => {
  window.__mocks?.[dial](...args);
  window.__queries?.removeQueries({ queryKey: ['/api/trackers'] });
}"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def panel(page, entry):
    """Opens one entry's panel over the Torrents tab."""
    await page.evaluate("(entry) => window.__panel.produce('torrent', entry)", entry)
    await page.wait_for_timeout(ACTED)


async def rows(page):
    """The open panel's pairs, keyed by tracker."""
    return {row["tracker"]: row for row in await page.evaluate(OFFERS)}


async def tap(page, selector):
    """A finger on the first element a selector names; False when there is none to touch."""
    target = page.locator(selector)
    if not await target.count():
        return False
    await target.first.tap()
    await page.wait_for_timeout(ACTED)
    return True


async def main():
    journal = Journal("R450–R454 — « Créer et publier un torrent »: offered, confirmed, answered, read")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R451: offered only where nothing already cross-seeds ──────────
        answer = await enter(page, "torrents-cross-seed-upload")
        seen = []
        for entry in (CROSS_SEEDING, REFUSED, UNSEARCHED, EXCLUDED, UPLOADABLE, LANTERNS):
            await panel(page, f"{entry}:c411")
            seen += await page.evaluate(OFFERS)
        wrong = [row for row in seen if row["offered"] != (
            row["state"] in UPLOADABLE_STATES and not row["excluded"] and not row["titleExcluded"] and row["seeding"]
            and row["trackerOn"])]
        states = {row["state"] for row in seen}
        journal.check("R451 offered only on a pair with no match, in error or not yet searched, not excluded, its "
                      "origin seeding, its tracker itself on — never on actif, stoppé, tracker sans cross-seed, nor "
                      "while it downloads",
                      answer is None and any(row["offered"] for row in seen)
                      and {"active", "stopped", "trackerWithout", "notSearched"} <= states and not wrong,
                      repr(answer or wrong or [(row["tracker"], row["state"], row["offered"]) for row in seen]))

        await enter(page, "torrents-cross-seed-upload")
        await page.evaluate(POSE, ["poseUploadsOff", ["v3x.club"]])
        await panel(page, f"{UPLOADABLE}:c411")
        off = (await rows(page)).get("v3x.club", {})
        journal.check("R451 its tracker not accepting uploads: the act gone, its line says why, the search still offered",
                      off.get("offered") is False and off.get("off") and "v3x.club" in off["off"]
                      and off.get("searched") is True, repr(off))
        await enter(page, "torrents-cross-seed-upload")
        await page.evaluate(POSE, ["poseCrossSeedSwitchOff", ["v3x.club"]])
        await panel(page, f"{UPLOADABLE}:c411")
        switched = (await rows(page)).get("v3x.club", {})
        journal.check("R451 its cross-seed switch off: the act gone too, the switch's own reason said once",
                      switched.get("offered") is False and switched.get("off") is None
                      and switched.get("searched") is False, repr(switched))

        await enter(page, "torrents-cross-seed-upload")
        forced = {name: await page.evaluate(FORCE, [hash_, tracker]) for name, hash_, tracker in (
            ("active", CROSS_SEEDING, "tr4ker"), ("stopped", UPLOADABLE, "tr4ker"),
            ("downloading", UNSEARCHED, "tr4ker"), ("excluded", EXCLUDED, "v3x.club"))}
        journal.check("R451 the layer refuses an upload asked where the act is not drawn",
                      all(status == 409 for status in forced.values()), repr(forced))

        # The tracker itself off — down (lacale, by a failure) or by the operator
        # (v3x.club) — its cross-seed and « accepte les uploads » switches on.
        for tracker, by, key in (("lacale", "failure", "trackerDown"), ("v3x.club", "operator", "trackerOff")):
            await enter(page, "torrents-cross-seed-upload")
            values = {f"tracker:tracker.providers.{tracker}.cross_seed": True,
                      f"tracker:tracker.providers.{tracker}.accepts_uploads": True}
            if by == "operator":
                values[f"tracker:tracker.providers.{tracker}.enabled"] = False
            written = await page.evaluate(WRITE, values)
            state = await page.evaluate(
                "(name) => fetch('/api/trackers').then(answer => answer.json())"
                ".then(all => { const one = all.find(t => t.name === name);"
                " return { enabled: one.enabled, by: one.disabled?.by ?? null, crossSeed: one.crossSeed.enabled,"
                " uploads: one.crossSeed.acceptsUploads }; })", tracker)
            await panel(page, f"{REFUSED}:c411")
            row = (await rows(page)).get(tracker, {})
            said = WORDS["waits"].get(key)
            journal.check(f"R451 {tracker} switched off by {by}, its two switches on: neither the upload nor the "
                          "search is offered, and its line says the tracker is off and why",
                          written == 200 and state == {"enabled": False, "by": by, "crossSeed": True, "uploads": True}
                          and row.get("state") == "error" and row.get("offered") is False
                          and row.get("searched") is False and said is not None
                          and said in (row.get("trackerOff") or "") and row.get("off") is None,
                          f"{written} · {state} · {row}")
            refusals = {"upload": await page.evaluate(FORCE, [REFUSED, tracker]),
                        "search": await page.evaluate(FORCE_SEARCH, [REFUSED, tracker])}
            journal.check(f"R451 {tracker} switched off by {by}: the layer refuses the upload and the search",
                          all(status == 409 for status in refusals.values()), repr(refusals))

        # ── R453: the confirmation names what is published, before any call ──
        await enter(page, "torrents-cross-seed-upload")
        origin = await page.evaluate(
            "(hash) => window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads"
            ".find(one => one.infoHash === hash)?.name ?? null", UPLOADABLE)
        tapped = await tap(page, ACT)
        dialog = await page.evaluate(f"() => document.querySelector('{DIALOG}')?.textContent ?? null")
        called = len(await page.evaluate(UPLOADS))
        journal.check("R453 a finger opens a confirmation naming the tracker and the release whose files are sent; "
                      "nothing is called yet",
                      tapped and dialog is not None and "v3x.club" in dialog and origin and origin in dialog
                      and called == 0, f"{dialog!r} · called {called}")
        await page.locator(BUTTONS).last.tap()
        await page.wait_for_timeout(ACTED)
        journal.check("R453 « Annuler » calls nothing", len(await page.evaluate(UPLOADS)) == 0,
                      repr(await page.evaluate(UPLOADS)))

        # ── R452: one call, « en file », resolved in the same visit ────────
        await tap(page, ACT)
        confirm = page.locator(BUTTONS).first
        await confirm.tap()
        try:
            await confirm.tap(timeout=500)
        except Exception:  # noqa: BLE001 — gone is the answer this hold wants
            pass
        await page.wait_for_timeout(ACTED)
        asked = await page.evaluate(UPLOADS)
        queued = (await rows(page)).get("v3x.club", {})
        text = await page.evaluate("() => document.body.textContent")
        journal.check("R452 confirmed: ONE uploadCrossSeed; the pair reads « en file », never « occupé »",
                      len(asked) == 1 and asked[0]["status"] == 202 and queued.get("queued")
                      and not queued.get("offered") and "occupé" not in text,
                      f"{asked} · {queued}")
        await page.wait_for_timeout(UPLOAD_ENDS)
        ended = (await rows(page)).get("v3x.club", {})
        journal.check("R452 its outcome moves the pair on its own: « actif », « publié par vous le … »",
                      ended.get("state") == "active" and ended.get("queued") is None
                      and ended.get("date", "").startswith("publié par vous le"), repr(ended))
        await page.evaluate("() => window.__panel.close?.()")
        await page.wait_for_timeout(ACTED)
        cards = await page.evaluate(PUBLISHED_CARD, "v3x.club")
        journal.check("R452 the Torrents tab carries its new card on v3x.club, marked « Publié par vous »",
                      len(cards) == 1 and cards[0]["word"] == "Publié par vous", repr(cards))

        answer = await enter(page, "torrents-cross-seed-upload-queued")
        held = (await rows(page)).get("v3x.club", {})
        journal.check("R452 torrents-cross-seed-upload-queued: « en file », nothing more offered",
                      answer is None and held.get("queued") and not held.get("offered") and not held.get("searched"),
                      repr(answer or held))

        # ── R450: the two codes, sentenced ───────────────────────────────
        for state, code in (("torrents-cross-seed-upload-refused-creation", "creation_failed"),
                            ("torrents-cross-seed-upload-refused-publish", "publish_failed")):
            answer = await enter(page, state)
            row = (await rows(page)).get("v3x.club", {})
            said = row.get("reasonText") or ""
            journal.check(f"R450 {state}: « erreur de cross-seed », the code's sentence and its kind, no bare code",
                          answer is None and row.get("state") == "error" and row.get("reason") == code
                          and WORDS["reasons"][code] in said and WORDS["families"]["engine"] in said
                          and WORDS["states"]["error"] in row.get("text", "") and not BARE.search(row.get("text", "")),
                          repr(answer or row))
            wanted = SEED["publishRefusal"] if code == "publish_failed" else None
            journal.check(f"R450 {state}: the tracker's own reason said only where the tracker answered",
                          (row.get("trackerReason") is None) if wanted is None
                          else (row.get("trackerReason") or "").endswith(wanted),
                          repr(row.get("trackerReason")))
            journal.check(f"R450 {state}: a refused pair offers the act again (nothing cross-seeds there)",
                          row.get("offered") is True, repr(row))

        # ── R454: refused by the tracker, counted, by the SAME event ──────
        await enter(page, "torrents-cross-seed-upload")
        start = int(await page.evaluate(BADGE) or 0)
        await page.evaluate(POSE, ["poseUploadOutcome", [UPLOADABLE, "v3x.club", "publish_failed"]])
        await tap(page, ACT)
        await page.locator(BUTTONS).first.tap()
        await page.wait_for_timeout(UPLOAD_ENDS)
        refused = (await rows(page)).get("v3x.club", {})
        badge = await page.evaluate(BADGE)
        total = await page.evaluate(SUM)
        journal.check("R454 refused by the tracker: the open row reads « erreur de cross-seed », its reason, no finger",
                      refused.get("state") == "error" and refused.get("reason") == "publish_failed"
                      and refused.get("trackerReason"), repr(refused))
        journal.check("R454 the badge counts it — one more, still the five terms' sum, no sixth",
                      badge == str(start + 1) and badge == str(total), f"{start} → {badge!r} · sum {total}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
