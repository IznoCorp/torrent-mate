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
from common import Journal, open_page

from playwright.async_api import async_playwright

# THE KINDS THIS LOT HAS MOVED, in the order they moved. It grows by one entry
# per conversion phase, and it is an EQUALITY rather than a subset: a kind that
# appears without being written here is a registration nobody declared, and a
# kind written here that is missing is a producer that stopped answering.
MOVED = ("account", "action", "secret", "setting")

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
            await page.wait_for_timeout(150)
            expected = await page.evaluate(f"()=>{expected_from}")
            await page.evaluate(
                "([kind, subject])=>window.__panel.produce(kind, subject)",
                [kind, subject])
            await page.wait_for_timeout(250)
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

        # AFTER THE BOOT, and said so rather than left to be assumed: the
        # listener is attached once `open_page` has navigated, so this reads the
        # errors the SEAM raises and not the ones the boot might. Boot errors are
        # `states.py`'s, on all 54 named states.
        # 4. THE CHIP'S TONE, on the panel a named state opens.
        for state, tone, why in TONES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(400)
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

        # 5. THE HOLDER, both ways.
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
