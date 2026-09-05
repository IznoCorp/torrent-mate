"""R120 — a panel's content is PRODUCED by the feature that owns it.

WHAT A PRODUCER IS. `ui/panel` renders a descriptor the same whichever side
produced it, which is exactly why moving a producer out of the dying engine is
provable at zero divergence over the oracle — and exactly why the oracle cannot
say a producer moved at all. The rendering is the same by construction. This
rule reads the thing the oracle cannot: WHO answered.

THREE PROPERTIES, and each one fails differently.

  1. THE KINDS THAT HAVE MOVED ARE REGISTERED. A registration lost in a
     refactor leaves a panel that stops opening on one path and keeps opening
     on every other, which is a defect no state walk finds. It is read as a
     LIST compared with an expected list, never as « at least one » — a floor
     of one is met by any single surviving producer.
  2. A KIND NOBODY REGISTERED RAISES. It must not open an empty panel: a
     forgotten `registerProducer` and a subject the cache does not hold look
     identical from outside, and only one of them is a defect. `refuseProducer`
     is the named thrower, and `window.__unknownProducer` calls it as a plain
     function — no tap, so a failure here has one candidate rather than two.
  3. THE PANEL A PRODUCER OPENS IS ABOUT THE SUBJECT IT WAS ASKED FOR. A
     producer reading the wrong key, or ignoring its subject, answers a
     perfectly well-formed descriptor about something else. The title is read
     against the subject's own data — never against a literal written here,
     which would be this file agreeing with itself.

WHAT IT DOES NOT READ, said before what it does: whether a producer's
descriptor is CORRECT in its details. That is the oracle's, surface by surface,
at zero divergence. This rule reads the seam.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, PANEL_OUT, SETTLED, open_page

from playwright.async_api import async_playwright

# THE KINDS THIS LOT HAS MOVED, in the order they moved. It grows by one entry
# per conversion phase, and it is an EQUALITY rather than a subset: a kind that
# appears without being written here is a registration nobody declared, and a
# kind written here that is missing is a producer that stopped answering.
MOVED = ("account", "action", "journey", "more", "secret", "setting", "sort",
         "suggestion", "add", "follow")

# What each kind is driven with, and what the panel must then say about it. The
# expected title is read from the PROTOTYPE's own data at run time — the third
# element names where — so this file states a relation and never a value.
DRIVEN = (
    # kind, subject, how the expected title is read from the page
    ("account", "", "window.__queries.getQueryData(['/api/auth/me']).name"),
    ("action", "library-clean",
     "window.__queries.getQueryData(['/api/maintenance/actions'])"
     ".find(a=>a.id==='library-clean').l"),
    ("setting", "thresholds:thresholds.min_free_space_staging_gb",
     "window.__settingLabels.label("
     "window.__queries.getQueryData(['/api/config/schema']).flatMap(r=>r.r)"
     ".find(s=>`${s.f}:${s.c}`==='thresholds:thresholds.min_free_space_staging_gb'))"),
    ("secret", "TMDB_API_KEY",
     "window.__queries.getQueryData(['/api/config/secrets'])"
     ".find(s=>s.k==='TMDB_API_KEY').l"),
    ("sort", "", "window.__i18n.t('panels.sort.title')"),
    ("more", "", "window.__i18n.t('panels.standby.title')"),
    ("journey", "Furious", "'Furious'"),
    ("suggestion", "0", "window.__suggestions()[0].t"),
    ("follow", "Silo", "'Silo'"),
    # `add` WAS THE ONE REGISTERED KIND NOTHING DROVE — ten moved, nine walked,
    # and the tenth's order and subject were held by nothing at all. It needs a
    # search to have happened, because its subject is a POSITION in what the
    # operator just typed, so the walk asks for one first (`__addSearch`) rather
    # than opening the panel over an empty answer.
    ("add", "0", "window.__searchResults()[0].t"),
)

# WHAT A PANEL SAYS ABOUT RISK, read on the DRAWN chip. It is here because the
# mutation that turned `destructive` from `danger` to `success` fell NO rule:
# `machine.py` walks the maintenance panel and reads its actions, the oracle
# measures a region ROOT and a chip is a child of one, and nothing anywhere
# asked what colour a command that deletes is announced in. A destructive
# command wearing the success tone is a reassuring lie about the one thing this
# panel exists to say.
#
# THE TONE IS READ, NOT THE WORD. The word is `fr.json`'s and moves with the
# copy; the tone is a token name and is code, and they are two halves the engine
# kept in one object because it had no i18n layer.
TONES = (
    # named state, the tone its chip must carry, and why it must
    ("maintenance-delete", "danger", "a command that deletes says so"),
)

# THE OTHER QUESTION A KIND MAY ANSWER — « does this interface HOLD this
# subject » — and the addressed-panel table asks it before opening anything from
# an address a reader can type. It is not `produce` answering: a producer
# answers for anything, which is right inside the application and wrong for a
# typed address. A kind that declares it is read BOTH WAYS here, because a
# holder that says yes to everything is the defect the table exists to prevent
# and it passes a one-sided reading.
HOLDS = (
    # kind, a subject it holds, a subject it does not
    ("action", "library-clean", "no-such-command"),
    ("setting", "thresholds:thresholds.min_free_space_staging_gb", "nowhere:no.such.key"),
    ("secret", "TMDB_API_KEY", "NO_SUCH_SECRET"),
)


async def main():
    journal = Journal("R120 — a panel's content is produced by its feature")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # 1. THE REGISTRY, read as a set rather than a count.
        registered = await page.evaluate("()=>window.__panel.producers()")
        journal.check(
            "every kind this lot has moved has a producer registered",
            set(MOVED) <= set(registered),
            f"missing {sorted(set(MOVED) - set(registered))} · registered {registered}")
        journal.check(
            "and no kind is registered that this rule does not name",
            set(registered) <= set(MOVED),
            f"unnamed {sorted(set(registered) - set(MOVED))}")

        # 2. THE REFUSAL. A kind nobody registered must throw, and the message
        #    must name the kind — a bare throw would leave the next reader
        #    guessing which of thirty producers was missing.
        refusal = await page.evaluate("""()=>{
          try { window.__unknownProducer(); return null; }
          catch (error) { return String(error && error.message); }
        }""")
        # READ AS THE NAMED THROWER'S MESSAGE, never as « something threw ».
        # Written the second way first, and its own mutation showed why: making
        # `refuseProducer` return instead of throwing left `produce` null and
        # the next line called it, so a TypeError arrived and « is refused »
        # passed over a refusal that had stopped existing. A rule that accepts
        # any throw certifies the crash it was written to prevent.
        journal.check(
            "a panel kind nobody produces is refused BY THE NAMED THROWER",
            bool(refusal) and refusal.startswith("unknown panel producer:"),
            str(refusal))
        journal.check(
            "and the refusal names the kind",
            bool(refusal) and "ceci-n-existe-pas" in refusal, str(refusal))
        journal.check(
            "and it opens no panel",
            not await page.evaluate("()=>window.__panel.isOpen()"))

        # 3. EACH MOVED KIND OPENS A PANEL ABOUT ITS OWN SUBJECT.
        for kind, subject, expected_from in DRIVEN:
            await page.evaluate("()=>window.__panel.close()")
            await page.wait_for_timeout(PANEL_OUT)
            # `add` reads what the operator has just typed, so a search has to
            # have happened before its panel means anything.
            if kind == "add":
                await page.evaluate("()=>window.__go('acq-add-results')")
                await page.wait_for_timeout(SETTLED)
                await page.evaluate("()=>window.__panel.close()")
                await page.wait_for_timeout(PANEL_OUT)
            expected = await page.evaluate(f"()=>{expected_from}")
            await page.evaluate(
                "([kind, subject])=>window.__panel.produce(kind, subject)",
                [kind, subject])
            await page.wait_for_timeout(PANEL_IN)
            drawn = await page.evaluate(
                """()=>{const head = document.querySelector('#sheet [data-part="sheet/title"]');
                        return head ? head.textContent.trim() : null;}""")
            journal.check(
                f"« {kind} » opens a panel",
                await page.evaluate("()=>window.__panel.isOpen()"), str(drawn))
            journal.check(
                f"and it is about the subject it was asked for ({kind})",
                drawn is not None and drawn == expected,
                f"drawn {drawn!r} · expected {expected!r}")
            # AND ITS FIRST ACTION IS NOT THE DESTRUCTIVE ONE, because that is
            # where focus lands. `app/focus.ts` moves focus into a layer that
            # opens and takes the layer's own named entry, then the first
            # control a reader would reach — and a panel names none, so the
            # first action IS the entry. The dialog layer solved this by naming
            # its way out; a panel is a menu rather than an interposition and
            # has no way out to name, so what keeps it safe is the ORDER, and
            # the order is what this reads. A panel that puts a destructive act
            # first hands a keyboard's or a switch control's next Enter the act
            # it should have had to travel to.
            # THE COUNT IS READ BESIDE THE TONE, and it has to be: the first
            # version compared `None` with « danger » and passed whenever the
            # selector matched NOTHING — so a panel that drew no action at all,
            # or one whose action markup moved, satisfied « its first action is
            # not destructive » by having no first action. That is the vacuous
            # pass this whole rule exists to refuse, in a hold added to refuse
            # it elsewhere.
            # SCOPED TO THE PANEL THAT IS OPEN, and this is not tidiness. The
            # sheet's tree PERSISTS: a `produce` that opens nothing leaves the
            # previous panel's actions in the document, so an unscoped read
            # answers about the panel BEFORE this one — shown with
            # `produce("add", "")`, which drew nothing and left the read
            # reporting its predecessor's tone. The open panel is the one
            # carrying `data-open` — `#sheet`, with `#sheetin` inside it — and a
            # read that finds none answers zero rather than borrowing.
            offered = await page.evaluate(
                """()=>{const panel = document.querySelector(
                     '#sheet[data-open]');
                   if (!panel) return {count: 0, first: null, scoped: false};
                   const all = [...panel.querySelectorAll('[data-part="sheet/action"]')];
                   return {count: all.length, scoped: true,
                           first: all.length ? (all[0].dataset.tone || "neutral") : null};}""")
            journal.check(
                f"and its FIRST action is not the destructive one ({kind}) — "
                f"a panel names no way out, so focus lands there",
                offered["scoped"] and offered["count"] >= 1
                and offered["first"] != "danger",
                f"scoped={offered['scoped']}, {offered['count']} action(s), "
                f"first one's tone: {offered['first']}")

        # AFTER THE BOOT, and said so rather than left to be assumed: the
        # listener is attached once `open_page` has navigated, so this reads the
        # errors the SEAM raises and not the ones the boot might. Boot errors are
        # `states.py`'s, on all 54 named states.
        # 4. THE CHIP'S TONE, on the panel a named state opens.
        for state, tone, why in TONES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            chip = await page.evaluate(
                """()=>{const c = document.querySelector('#sheet [data-part="chip"]');
                        return c ? {tone: c.dataset.tone, text: c.textContent.trim()} : null;}""")
            journal.check(
                f"on {state}, {why}",
                chip is not None and chip["tone"] == tone,
                f"{chip} · expected tone {tone!r}")
            # AND THE WORD ARRIVED. A producer's copy moved out of the engine
            # into `fr.json` in this lot; a key that does not resolve renders as
            # the key itself, which reads like a label until someone looks. This
            # is the cheapest reading that separates the two.
            journal.check(
                f"on {state}, the chip's word is a word and not its key",
                chip is not None and bool(chip["text"])
                and not chip["text"].startswith("panels."),
                str(chip))

        # 5. §5 SEEN IN THE PANEL: a film is ADDED and a series is FOLLOWED.
        #
        # « Une fois acquis, ce film quittera automatiquement votre liste » is
        # the constitution's §5 in the interface's own words — a film has an
        # end, a series does not — and NOTHING read it: a mutation forcing every
        # suggestion to be treated as a series fell no hold here and none in
        # `deck.py`. A suggestion panel offering « Suivre » on a film is the
        # interface promising a watch that will never end.
        #
        # THE TWO ARE READ TOGETHER: the verb AND the note. Either alone passes
        # over a panel that says the right word and draws the wrong promise.
        kinds = await page.evaluate("""()=>{
          const all = window.__suggestions();
          const film = all.findIndex((s) => s.k === 'Film');
          const series = all.findIndex((s) => s.k !== 'Film');
          return {film, series};}""")
        journal.check(
            "the reserve carries both a film and a series, so « the verb "
            "follows the kind » is a question",
            kinds["film"] >= 0 and kinds["series"] >= 0, str(kinds))
        said = {}
        for kind, position in (("film", kinds["film"]), ("series", kinds["series"])):
            await page.evaluate("()=>window.__panel.close()")
            await page.wait_for_timeout(PANEL_OUT)
            await page.evaluate(
                "(at)=>window.__panel.produce('suggestion', String(at))", position)
            await page.wait_for_timeout(PANEL_IN)
            said[kind] = await page.evaluate("""()=>({
              primary: (document.querySelector(
                '#sheetin [data-part="sheet/action"]') || {}).textContent,
              body: document.querySelector('#sheetin').textContent});""")
        journal.check(
            "a film is ADDED and a series is FOLLOWED, never the same word (§5)",
            said["film"]["primary"] and said["series"]["primary"]
            and said["film"]["primary"] != said["series"]["primary"],
            f"film {said['film']['primary']!r} · series {said['series']['primary']!r}")
        journal.check(
            "and only the film is told it will leave the list once acquired (§5)",
            "quittera" in (said["film"]["body"] or "")
            and "quittera" not in (said["series"]["body"] or ""),
            f"film says it: {'quittera' in (said['film']['body'] or '')} · "
            f"series says it: {'quittera' in (said['series']['body'] or '')}")

        # 6. THE HOLDER, both ways.
        for kind, real, invented in HOLDS:
            journal.check(
                f"« {kind} » holds a subject it really has",
                await page.evaluate("([k,s])=>window.__panel.holds(k,s)", [kind, real]),
                real)
            journal.check(
                f"and refuses one it does not ({kind})",
                not await page.evaluate(
                    "([k,s])=>window.__panel.holds(k,s)", [kind, invented]),
                invented)

        journal.check("no JS error while the seam is driven", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
