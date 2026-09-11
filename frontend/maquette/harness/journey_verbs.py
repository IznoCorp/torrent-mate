"""R126 — the tunnel is resumed from where the operator looks at it (B-302).

§20 says a blocked tunnel « reprend là où il s'est arrêté, par l'opérateur ».
The journey sheet IS the tunnel as the operator sees it, and it offered exactly
one action — « Voir la fiche » — while
`POST /api/acquisition/journeys/{infoHash}/requeue` and `/rescrape` went
uncalled. The producer's own header said the verbs « belong to the lot that
wires the tunnel's verbs ».

WHAT IT READS, and each fails differently:

  1. THE JOURNEY PANEL OFFERS BOTH VERBS, told apart by LABEL. Two buttons that
     both call something are not two verbs.
  2. EACH OPERATION IS CALLED, and the right one. Read on what the LAYER
     answered, never on the network and never on the screen: this layer replaces
     `globalThis.fetch`, so a mocked call raises no request event at all, and a
     hold reading the screen passes a build that drew a message and sent
     nothing.
  3. THE JOURNEY'S STAGES MOVE — a stage that was still to come is now the one
     running. Read on the LAYER's answer, because the producer takes its stages
     from the query cache: a rule asserting a hard-coded list would be green
     over a build that called the operation and threw the answer away.
  4. NO ERROR IS RAISED.
  5. UNDER A BUSY PIPELINE both asks are still accepted, say they are QUEUED,
     and are never answered 409 nor dressed as « occupé » (DOIT-4,
     NE-DOIT-PAS-3). The backend answers 409 for exactly this case; the
     interface is forbidden to show it.

⚠ « RE-SCRAPER » HERE IS NOT THE MEDIA SHEET'S METADATA RE-SCRAPE. The
resources already hold « Re-scraper les métadonnées » twice, and that is another
subject entirely: this verb re-runs the tunnel's scrape for one tracked staging
item. The rule reads the JOURNEY panel's own action, never a match on the word
somewhere in the tree.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE A JOURNEY IS REACHED. The acquisitions page lists what is in flight, and
# a journey is one acquisition's own history — so a medium drawn there is a
# medium whose tunnel can be looked at.
JOURNEY_STATE = "acq-now-loaded"

# The operations, as the CONTRACT names them. Read by operationId rather than by
# URL, so a path parameter spelled differently cannot turn a real call into a
# silent miss.
REQUEUE = "requeueJourney"
RESCRAPE = "rescrapeJourney"

# THE WORDS A REFUSAL WEARS. « occupé » is the constitution's own; the others are
# what the same refusal reads like when it is dressed differently.
REFUSALS = ("occupé", "occupee", "occupée", "déjà en cours", "réessayez plus tard")

# WHAT THE LAYER ANSWERED. Not the network: this layer replaces `globalThis.fetch`,
# so a mocked call reaches no wire and the browser's own request events never
# fire for one. A hold listening there is green whatever the interface does.
ANSWERED = "()=>(window.__mocks?.answered?.() || [])"

# WHAT THE INTERFACE SAID, through the door the message host publishes FOR a
# rule. It is NOT `#toast`: that element is the dying engine's and the message
# layer is React.
SAID = """()=>{
  const held = window.__toast?.read?.();
  return {said: held && held.message ? held.message.message || '' : '',
          shown: !!(held && held.shown)};}"""

# THE STAGES THE LAYER HOLDS for one journey, which is where the move has to be
# real. The producer reads them from the query cache, so this is the same answer
# the panel was drawn from rather than a second opinion.
STAGES_HELD = """(title)=>{
  const held = window.__queries.getQueryData(["/api/acquisition/journeys", title]);
  return Array.isArray(held) ? held.map((one) => ({label: one.label, state: one.state}))
                             : null;}"""

# THE ACTIONS THE PANEL OFFERS, by LABEL. Counted by label because that is how a
# doubled action shows itself, and read off the panel rather than off the
# producer's source.
ACTIONS = """()=>[...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
  .map((one) => (one.textContent || '').trim())"""


async def tap_action(page, label):
    """Taps the panel action whose label contains a word, by a real finger.

    Args:
        page: The page.
        label: A word the action's label carries.

    Returns:
        What the aim read, with `tapped` saying whether a finger went down.
    """
    aim = await page.evaluate("""(word)=>{
        const act = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
          .find((one) => (one.textContent || '').toLowerCase().includes(word));
        if (!act) return {found: false};
        const box = act.getBoundingClientRect();
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        const hit = document.elementFromPoint(x, y);
        return {found: true, x, y, label: (act.textContent || '').trim(),
                reachable: !!hit && (hit === act || act.contains(hit)),
                covering: hit === null ? "nothing" : hit.tagName};}""", label.lower())
    if aim["found"] and aim["reachable"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim


async def main():
    journal = Journal("R126 — the tunnel's verbs resume it where it stopped")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def calls_since(mark, operation):
            """Every call to one operation the layer answered after a mark."""
            every = await page.evaluate(ANSWERED)
            return [call for call in every[mark:]
                    if call["operationId"] == operation]

        async def mark():
            """How many calls the layer has answered."""
            return len(await page.evaluate(ANSWERED))

        await page.evaluate("(id)=>window.__go(id)", JOURNEY_STATE)
        await page.wait_for_timeout(SETTLED)
        # THE SUBJECT IS THE MEDIUM THE QUEUE IS ACTUALLY CARRYING, read from
        # the queue rather than named here: a title written into a rule is a
        # title that goes stale the day the fixture moves.
        subject = await page.evaluate(
            """()=>{const now = window.__queue?.() || {};
                    const one = (now.inFlight || [])[0] || (now.blocked || [])[0]
                             || (now.takeable || [])[0];
                    return one ? one.t : "";}""")
        journal.check(
            "the queue really carries a medium whose tunnel can be looked at",
            bool(subject), subject or "the queue is empty")

        await page.evaluate("(t)=>window.__panel.produce('journey', t)", subject)
        await page.wait_for_timeout(PANEL_IN)
        offered = await page.evaluate(ACTIONS)
        journal.check(
            "the journey panel offers « Remettre en file » (B-302, §20)",
            any("file" in one.lower() for one in offered), str(offered))
        journal.check(
            "and « Re-scraper » — the TUNNEL's scrape, not the sheet's metadata",
            any("scrap" in one.lower() for one in offered), str(offered))

        held_before = await page.evaluate(STAGES_HELD, subject)
        journal.check(
            "the layer really holds this journey's stages, so a move can be read "
            "on the answer and not on a literal",
            bool(held_before), str(held_before))

        # ── REMETTRE EN FILE ───────────────────────────────────────────────
        errors.clear()
        requeue_mark = await mark()
        aim = await tap_action(page, "file")
        journal.check(
            "« Remettre en file » is on a button a finger reaches",
            aim["tapped"], str(aim))
        await page.wait_for_timeout(ACTED)
        requeued = await calls_since(requeue_mark, REQUEUE)
        journal.check(
            "and it calls the REQUEUE operation — read on what the layer "
            "answered, never on the screen (B-302)",
            len(requeued) == 1, f"{len(requeued)} call(s): {requeued[:2]}")
        held_after = await page.evaluate(STAGES_HELD, subject)
        journal.check(
            "the journey's stages MOVE — a stage still to come is now the one "
            "running (§20: it resumes where it stopped)",
            held_after is not None and held_after != held_before,
            f"{held_before} → {held_after}")
        journal.check(
            "and asking raises no error",
            not errors, str(errors))

        # ── RE-SCRAPER ─────────────────────────────────────────────────────
        await page.evaluate("(t)=>window.__panel.produce('journey', t)", subject)
        await page.wait_for_timeout(PANEL_IN)
        errors.clear()
        rescrape_mark = await mark()
        rescrape_aim = await tap_action(page, "scrap")
        journal.check(
            "« Re-scraper » is on a button a finger reaches",
            rescrape_aim["tapped"], str(rescrape_aim))
        await page.wait_for_timeout(ACTED)
        rescraped = await calls_since(rescrape_mark, RESCRAPE)
        journal.check(
            "and it calls the RESCRAPE operation, not the requeue beside it",
            len(rescraped) == 1, f"{len(rescraped)} call(s): {rescraped[:2]}")
        journal.check(
            "and asking raises no error either",
            not errors, str(errors))

        # ── AND UNDER A BUSY PIPELINE, where the clause bites ──────────────
        #
        # THE MACHINE IS PUT TO WORK AFTER THE STATE IS DRIVEN, never before:
        # `window.__go` RE-SEEDS the layer, so a pipeline started earlier is
        # idle again by the time the act lands and the walk would measure a
        # clause it had switched off.
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("(id)=>window.__go(id)", JOURNEY_STATE)
        await page.wait_for_timeout(SETTLED)
        started = await page.evaluate("""async()=>{
            const answer = await window.fetch("/api/pipeline/run", {method: "POST"});
            const body = await answer.json().catch(() => ({}));
            return body.state || "";}""")
        await page.evaluate("""()=>window.__store.write({pipe: "running"})""")
        await page.wait_for_timeout(SETTLED)
        journal.check(
            "the LAYER really has the pipeline busy at the moment of the act",
            started in ("running", "queued"), str(started))

        await page.evaluate("(t)=>window.__panel.produce('journey', t)", subject)
        await page.wait_for_timeout(PANEL_IN)
        busy_mark = await mark()
        busy_aim = await tap_action(page, "file")
        await page.wait_for_timeout(ACTED)
        busy_calls = await calls_since(busy_mark, REQUEUE)
        journal.check(
            "the tunnel can still be put back in the queue while the pipeline "
            "runs — the ask is ACCEPTED (NE-DOIT-PAS-3)",
            busy_aim["tapped"] and len(busy_calls) == 1,
            f"tapped={busy_aim['tapped']} {len(busy_calls)} call(s)")
        spoken = await page.evaluate(SAID)
        said = spoken["said"].lower()
        journal.check(
            "and the interface says it is IN FILE — DOIT-4's own words, "
            "« En file — pipeline en cours »",
            spoken["shown"] and "en file" in said,
            f"shown={spoken['shown']} said={spoken['said']!r}")
        journal.check(
            "never « occupé », nor any other dress of the same refusal",
            not any(word in said for word in REFUSALS),
            next((word for word in REFUSALS if word in said), ""))

        # READ ON WHAT THE LAYER ANSWERED, for the reason given at the top: a
        # `page.on("response")` listener cannot see a status this layer never
        # put on a wire, so a 409 hold written that way is green by construction.
        every = await page.evaluate(ANSWERED)
        refused = [call for call in every if call["status"] == 409]
        journal.check(
            "and no ask anywhere was answered 409 (NE-DOIT-PAS-3)",
            not refused, str(refused[:3]))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
