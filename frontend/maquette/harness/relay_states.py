"""R92 — the connection says what is wrong, and says it where a reader is.

§8 OF THE CONSTITUTION IS THIS RULE. « Un "rien ne se passe" sans raison visible
est un mensonge par omission. » The worst defect L10 can ship is not a lost
event: it is a screen that looks current and is not.

AND THE HEADER USED TO BE EXACTLY THAT (B-155). It carried « Connecté » as a
literal, beside a green dot, with `title="Temps réel connecté"` written into the
markup — in a prototype with no connection anywhere. A permanent claim of
liveness over a dead stream is §8 inverted: the interface looked current
whatever the truth, and nothing could have told a reader otherwise.

WHY IT DOES NOT DEPEND ON A RECTANGLE, and this is R90's lesson taken second
hand. The oracle recorded four loading and error states BLANK (B-108) because
its own `neutralise` tore React's nodes out before measuring. An instrument
blind to a surface is blind to it whatever the surface is FOR, and a surface
whose whole job is to be noticed is the worst place to find that out. So this
rule reads the TEXT and the CONTROL, directly.

WHAT IT HOLDS:

  the word      each condition draws its own word in the header, and no two
                conditions draw the same one — a dot that said « Connecté » in
                three of four conditions would pass a « text is present » hold.
  the notice    `lost` and `refused` draw a bar saying what is wrong AND since
                when, with a control that does something. `connected` and
                `connecting` draw NO bar: a bar that was always there would be
                chrome, and chrome is what a reader learns to stop seeing.
  the reason    the notice names a real reason, never a code (NE-DOIT-PAS-5).
                `4401` must not appear on screen.
  the action    `lost` offers a retry that reconnects; `refused` offers the way
                back to the sign-in. Held by what the control DOES, not by its
                label.
  reduced motion  the reconnecting dot's motion is DECLARED and disappears
                under `prefers-reduced-motion: reduce`, leaving the same dot in
                the same colour — a drawn state, not an absence (invariant 14).
  both ways     `refused` is reached BY A REAL 4401 as well as by the harness's
                driver, and draws the same thing. Three of the four conditions
                take a backoff and a handshake to reach, and `__go` is
                synchronous, so the named states force the condition — which
                would leave the DRAWING proved against a lever and never against
                the transport. This hold is the join: R93 proves socket ->
                condition, this proves condition -> drawing, and this hold
                proves the two meet.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read whether the copy is RIGHT. The strings live in
    `i18n/fr.json` and are quoted here because they are the app's rendered
    output; a hold asserting a KEY would pass over a resource serving nothing.
  - It does not read the transport. A drop, a backoff, a replay and a refusal
    walked for real are R93's.
  - It does not read WHAT an event refreshes. That is R91's.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# The word each condition draws in the header. Read off `i18n/fr.json`, never
# guessed: a first version of R90's own list invented two state ids that did not
# exist and crashed on the third rather than quietly measuring three of five.
# <sub>`python3 -c "import json;print(json.load(open('frontend/maquette/design/src/i18n/fr.json'))['connection'])"`</sub>
WORDS = {                                    # french-ok: the app's rendered output
    "connected": "Connecté",
    "reconnecting": "Reconnexion…",
    "lost": "Hors ligne",
    "refused": "Session expirée",
}

# The conditions that owe a reader more than a word, and the control each ends
# with. The VERB is what is held, never the label.
NOTICES = {
    "lost": "retry",
    "refused": "signin",
}

# What every notice says about the age of what is on screen. Quoted because it
# is the app's rendered output; the time itself is the moment of the run.
SINCE_LEAD = "Les informations affichées datent de"   # french-ok: the app's rendered output

# The dot and the notice, by their `data-*` anchors (D4).
#
# READ BY THEIR PART NAME, NEVER BY `[data-connection]` ON ITS OWN. A presence
# selector on a state attribute matches in ALL FOUR conditions, so a hold built
# on it is green whatever the interface is drawing — which is exactly what
# `check-markup-contracts`'s state arm refuses, and it refused this rule's first
# version. The VALUE is compared below instead, which is a stronger hold: the
# selector itself then asserts the condition.
MARK = '[data-part="shell/connection-mark"]'
NOTICE = '[data-part="shell/connection-notice"]'

# The same anchor, selecting the CONDITION rather than the element. Held per
# condition, so a dot that stopped changing its attribute falls here.
MARK_AT = '[data-part="shell/connection-mark"][data-connection="{condition}"]'


async def read_condition(page, state):
    """Drives one named state and reads what the connection draws."""
    return await page.evaluate(
        """async ({ state, mark, notice }) => {
             window.__go(state);
             await new Promise((r) => setTimeout(r, 120));
             const dot = document.querySelector(mark);
             const bar = document.querySelector(notice);
             const control = bar ? bar.querySelector("button") : null;
             return {
               condition: dot ? dot.getAttribute("data-connection") : null,
               word: dot ? dot.textContent.trim() : null,
               title: dot ? dot.getAttribute("title") : null,
               body: bar ? bar.textContent.trim() : null,
               action: control ? control.getAttribute("data-connection-action") : null,
               role: bar ? bar.getAttribute("role") : null,
             };
           }""",
        {"state": state, "mark": MARK, "notice": NOTICE})


async def hold(journal):
    """Drives every drawn condition and reads what a reader would see."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser, **PHONE)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # A GOOD CONNECTION FIRST, and it is the hold B-155 would have failed.
        good = await read_condition(page, "acq-now-idle")
        journal.check(
            "an ordinary state draws the connection it really has",
            good["condition"] == "connected" and good["word"] == WORDS["connected"],
            f"the header says {good['word']!r} at condition {good['condition']!r}")
        journal.check(
            "and it draws no notice at all while the connection is good",
            good["body"] is None,
            f"a bar was drawn saying {good['body']!r} — a bar that is always "
            "there is chrome, and chrome is what a reader stops seeing")

        # THE VALUE IS SELECTED, condition by condition. `[data-connection]`
        # on its own matches whatever the interface draws; this asks whether the
        # attribute really carries the condition, and it is the hold that makes
        # the presence-anchored version of this rule impossible to write back.
        selected = await page.evaluate(
            """(pattern) => Object.fromEntries(
                 ["connected", "reconnecting", "lost", "refused"].map((condition) => [
                   condition,
                   document.querySelectorAll(
                     pattern.replace("{condition}", condition)).length,
                 ]))""",
            MARK_AT)
        journal.check(
            "the header carries the condition it draws, and only that one",
            selected == {"connected": 1, "reconnecting": 0, "lost": 0, "refused": 0},
            f"selecting each condition by value found {selected}")

        seen = {"connected": good["word"]}
        for condition, expected in NOTICES.items():
            drawn = await read_condition(page, f"relay-{condition}")
            seen[condition] = drawn["word"]
            journal.check(
                f"`{condition}` draws its own word in the header",
                drawn["condition"] == condition and drawn["word"] == WORDS[condition],
                f"the header says {drawn['word']!r} at condition {drawn['condition']!r}")
            journal.check(
                f"`{condition}` says what is wrong, and since when",
                drawn["body"] is not None and SINCE_LEAD in drawn["body"],
                f"the notice reads {drawn['body']!r}")
            journal.check(
                f"`{condition}` names a reason and never a code",
                drawn["body"] is not None and "4401" not in drawn["body"],
                f"the notice reads {drawn['body']!r} — NE-DOIT-PAS-5 asks for the "
                "real reason, never a bare code")
            journal.check(
                f"`{condition}` offers the control its situation calls for",
                drawn["action"] == expected,
                f"the control is {drawn['action']!r}, expected {expected!r}")
            journal.check(
                f"`{condition}` announces itself to a screen reader",
                drawn["role"] == "status",
                f"role={drawn['role']!r}")

        reconnecting = await read_condition(page, "relay-reconnecting")
        seen["reconnecting"] = reconnecting["word"]
        journal.check(
            "`reconnecting` draws its own word, and no notice",
            reconnecting["word"] == WORDS["reconnecting"]
            and reconnecting["body"] is None,
            f"the header says {reconnecting['word']!r}, the notice "
            f"{reconnecting['body']!r} — a reconnection under way is a wait, not "
            "a screen the reader has to act on")

        # NO TWO CONDITIONS SAY THE SAME THING. Every hold above would pass over
        # an indicator that said « Connecté » in all four.
        journal.check(
            "the four conditions draw four different words",
            len(set(seen.values())) == 4,
            f"the header drew {sorted(seen.values())}")

        # THE CONTROL DOES SOMETHING, held by what happens and not by its label.
        acted = await page.evaluate(
            """async ({ notice }) => {
                 window.__go("relay-lost");
                 await new Promise((r) => setTimeout(r, 60));
                 document.querySelector(notice).querySelector("button").click();
                 await new Promise((r) => setTimeout(r, 200));
                 return window.__relay.condition().condition;
               }""",
            {"notice": NOTICE})
        journal.check(
            "the retry really reconnects",
            acted == "connected",
            f"after the retry the condition is {acted!r}")

        # REDUCED MOTION IS A DRAWN STATE. The dot keeps its colour and loses
        # its movement — never the other way round, and never nothing at all.
        motion = await page.evaluate(
            """async ({ mark }) => {
                 window.__go("relay-reconnecting");
                 await new Promise((r) => setTimeout(r, 60));
                 const dot = document.querySelector(mark).firstElementChild;
                 const read = () => {
                   const style = getComputedStyle(dot);
                   return { animation: style.animationName, colour: style.backgroundColor };
                 };
                 return read();
               }""",
            {"mark": MARK})
        journal.check(
            "the reconnecting dot moves, and its motion is declared",
            motion["animation"] == "pulse",
            f"animation-name is {motion['animation']!r} — a scripted movement "
            "would read `none` here (D9: motion is declared, not scripted)")

        await context.close()

        still_context, still_page = await open_page(
            browser, reduced_motion="reduce", **PHONE)
        still = await still_page.evaluate(
            """async ({ mark }) => {
                 window.__go("relay-reconnecting");
                 await new Promise((r) => setTimeout(r, 60));
                 const dot = document.querySelector(mark).firstElementChild;
                 const style = getComputedStyle(dot);
                 return { animation: style.animationName, colour: style.backgroundColor,
                          word: document.querySelector(mark).textContent.trim() };
               }""",
            {"mark": MARK})
        journal.check(
            "under reduced motion the dot stops moving",
            still["animation"] == "none",
            f"animation-name is {still['animation']!r}")
        journal.check(
            "and it is still the same dot, in the same colour, saying the same thing",
            still["colour"] == motion["colour"] and still["word"] == WORDS["reconnecting"],
            f"colour {still['colour']} against {motion['colour']}, "
            f"word {still['word']!r} — invariant 14 asks for a designed state, "
            "not an absence")
        await still_context.close()

        # BOTH WAYS. The named states force the condition, because `__go` is
        # synchronous and three of four conditions take a handshake to reach.
        # This is the join between that lever and the transport.
        real_context, real_page = await open_page(browser, **PHONE)
        real = await real_page.evaluate(
            """async ({ mark, notice }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__go("acq-now-idle");
                 await wait(80);
                 window.__mocks.stream.refuse(true);
                 window.__mocks.stream.drop(1006);
                 await wait(1200);
                 const dot = document.querySelector(mark);
                 const bar = document.querySelector(notice);
                 return {
                   condition: dot.getAttribute("data-connection"),
                   word: dot.textContent.trim(),
                   body: bar ? bar.textContent.trim() : null,
                   action: bar ? bar.querySelector("button")
                     .getAttribute("data-connection-action") : null,
                 };
               }""",
            {"mark": MARK, "notice": NOTICE})
        journal.check(
            "a REAL 4401 draws exactly what the named state draws",
            real["condition"] == "refused"
            and real["word"] == WORDS["refused"]
            and real["action"] == NOTICES["refused"]
            and real["body"] is not None and SINCE_LEAD in real["body"],
            f"a real refusal drew {real['word']!r} with control {real['action']!r} "
            f"and the notice {real['body']!r}")
        await real_context.close()

        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R92 — the connection says what is wrong, where a reader is")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
