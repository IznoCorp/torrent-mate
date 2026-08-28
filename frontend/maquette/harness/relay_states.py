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

  - IT CANNOT SEE `new Date()` SUBSTITUTED FOR `new Date(currentSince)`, and
    this limit is stated rather than discovered. The notice prints an hour and a
    minute; a rule runs in a second, so the connection's instant and « now »
    format identically and the substitution is invisible to any assertion on the
    rendered string. What IS held is the published `data-since`, compared for
    EQUALITY against the instant the relay holds — so the age the notice derives
    from cannot drift from the connection's, which is the defect that was really
    there (the instant was written at the handshake and announced the session's
    start). A rule that claimed to catch the substitution would be claiming more
    than it can do, and this file already has two entries in `BUGS.md` for
    exactly that.
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

# Where the sign-in lives, read from the address model rather than retyped.
# <sub>`grep -n "SIGN_IN_PATH =" frontend/maquette/design/src/lib/addresses.ts`</sub>
SIGN_IN_PATH = "/login"

# WHAT EACH NOTICE SAYS IT IS ABOUT, and this list exists because the rule was
# GREEN WITHOUT IT. Its first version held that the notice named a real reason
# by looking for the SINCE lead and the absence of « 4401 » — so a mutation that
# made `lost` draw the reconnecting copy changed the reason, kept the
# timestamp, and passed (B-157). A hold that reads when a thing happened is not
# a hold that reads what happened.
#
# Read off `i18n/fr.json`, never retyped:
# <sub>`python3 -c "import json;print(json.load(open('frontend/maquette/design/src/i18n/fr.json'))['connection']['lost']['body'])"`</sub>
REASONS = {                                  # french-ok: the app's rendered output
    "lost": "Cet écran ne se met plus à jour : la connexion au serveur est perdue.",
    "refused": "Votre session n'est plus valide, cet écran ne se met plus à jour.",
}

# And what each control SAYS, beside what it does. Both are held: a control that
# did the right thing under the wrong words is a control a reader will not press.
LABELS = {                                   # french-ok: the app's rendered output
    "lost": "Réessayer maintenant",
    "refused": "Se reconnecter",
}

# THE TITLE EACH CONDITION CARRIES. It was READ into the rule's snapshot and
# asserted nowhere — the signature of a hold someone intended and did not write,
# and the attribute is B-155's own: the header used to carry
# `title="Temps réel connecté"` as a literal. At the width this rule measures it
# is also the only WORDS a reader gets, because the label is `display: none`.
TITLES = {                                  # french-ok: the app's rendered output
    "connected": "Temps réel connecté",
    "reconnecting": "Temps réel : la connexion a été perdue, reconnexion en cours",
    "lost": "Temps réel interrompu — cet écran ne se met plus à jour",
    "refused": "Session expirée — reconnectez-vous pour revoir les mises à jour",
}

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
               // READ THE WAY A READER GETS IT. `textContent` returns text CSS
               // has taken off the page — measured on the header's own label,
               // where it says « Hors ligne » while `innerText` says nothing.
               // A notice this rule could not see is the §8 defect wearing the
               // fix's clothes.
               shown: bar ? {
                 text: bar.innerText.trim(),
                 display: getComputedStyle(bar).display,
                 visibility: getComputedStyle(bar).visibility,
                 height: Math.round(bar.getBoundingClientRect().height),
                 top: Math.round(bar.getBoundingClientRect().top),
               } : null,
               // FORMATTED FROM THE RELAY'S OWN INSTANT, with the surface's own
               // options — so the hold compares what the notice SAYS against
               // what the connection KNOWS, rather than against a constant.
               since: bar ? bar.getAttribute("data-since") : null,
               held: window.__relay.condition().currentSince,
               stamp: (() => {
                 const since = window.__relay.condition().currentSince;
                 return since === null ? null : new Date(since)
                   .toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
               })(),
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

        journal.check(
            "an ordinary state carries the title of the condition it has",
            good["title"] == TITLES["connected"],
            f"the header's title is {good['title']!r}")

        seen = {"connected": good["word"]}
        titles = {"connected": good["title"]}
        for condition, expected in NOTICES.items():
            drawn = await read_condition(page, f"relay-{condition}")
            seen[condition] = drawn["word"]
            titles[condition] = drawn["title"]
            journal.check(
                f"`{condition}` carries its own title",
                drawn["title"] == TITLES[condition],
                f"the title is {drawn['title']!r}, expected "
                f"{TITLES[condition]!r} — a literal here is B-155 rewritten")
            journal.check(
                f"`{condition}` draws its own word in the header",
                drawn["condition"] == condition and drawn["word"] == WORDS[condition],
                f"the header says {drawn['word']!r} at condition {drawn['condition']!r}")
            journal.check(
                f"`{condition}` says what is wrong, in its own words",
                drawn["body"] is not None and REASONS[condition] in drawn["body"],
                f"the notice reads {drawn['body']!r}, and must carry "
                f"{REASONS[condition]!r}")
            journal.check(
                f"`{condition}` says since when, and says the RIGHT when",
                drawn["body"] is not None and SINCE_LEAD in drawn["body"]
                and drawn["stamp"] is not None and drawn["stamp"] in drawn["body"]
                and drawn["since"] is not None
                and int(drawn["since"]) == drawn["held"],
                f"the notice reads {drawn['body']!r}, derived from "
                f"{drawn['since']!r} against the connection's own "
                f"{drawn['held']!r}, rendering as {drawn['stamp']!r} — the "
                "lead phrase says a "
                "time is coming; it does not say the time is the right one, and "
                "the age of the data is the one fact this notice has that a "
                "reader can act on")
            journal.check(
                f"`{condition}` labels its control for what it does",
                drawn["body"] is not None and LABELS[condition] in drawn["body"],
                f"the notice reads {drawn['body']!r}, and must offer "
                f"{LABELS[condition]!r}")
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
                f"`{condition}` is actually ON SCREEN",
                drawn["shown"] is not None
                and drawn["shown"]["text"] != ""
                and drawn["shown"]["display"] != "none"
                and drawn["shown"]["visibility"] != "hidden"
                and drawn["shown"]["height"] > 0
                and 0 <= drawn["shown"]["top"] < 844,
                f"the notice reads {drawn['shown']} — every other hold in this "
                "file reads `textContent`, which CSS can empty without any of "
                "them noticing")
            journal.check(
                f"`{condition}` carries a live-region role",
                drawn["role"] == "status",
                f"role={drawn['role']!r}. NAMED FOR WHAT IT MEASURES: this hold "
                "used to be called « announces itself to a screen reader », "
                "which it cannot know — the region is CREATED rather than "
                "filled, and whether that is announced varies by assistive "
                "technology. Mounting it permanently and swapping its content "
                "is the shape that would let a rule say the stronger sentence")

        reconnecting = await read_condition(page, "relay-reconnecting")
        seen["reconnecting"] = reconnecting["word"]
        titles["reconnecting"] = reconnecting["title"]
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
        journal.check(
            "and four different titles",
            len(set(titles.values())) == 4,
            f"the header carried {sorted(titles.values())}")

        # AND NO TWO NOTICES SAY THE SAME THING. Every hold above is per
        # condition, so a notice drawing ANOTHER condition's copy would need a
        # reason list wrong in two places to pass — this makes one enough.
        journal.check(
            "the two notices say different things",
            len(set(REASONS.values())) == 2 and len(set(LABELS.values())) == 2,
            f"the reasons are {sorted(REASONS.values())}")

        # THE COLOUR IS THE MESSAGE, and until this hold existed nothing read
        # it. At 390 px `hidden sm:inline` removes the word, and `harness.css`
        # re-hides it ABOVE 640 px inside the phone frame — so in the frame the
        # oracle and this rule measure, the label is `display: none` at EVERY
        # width and the dot is all a reader has. Five holds above read a
        # `textContent` CSS had taken off the page, and the one colour assertion
        # compared `reconnecting` with itself. `lost: "bg-success"` — a green dot
        # over a dead stream, B-155 exactly — passed all 25.
        painted = await page.evaluate(
            """async ({ mark, states }) => {
                 const probe = document.createElement("span");
                 document.body.appendChild(probe);
                 const resolve = (token) => {
                   probe.style.backgroundColor = `var(${token})`;
                   return getComputedStyle(probe).backgroundColor;
                 };
                 const out = {};
                 for (const [condition, state] of Object.entries(states)) {
                   window.__go(state);
                   await new Promise((r) => setTimeout(r, 120));
                   const dot = document.querySelector(mark).firstElementChild;
                   const label = document.querySelector(mark).lastElementChild;
                   out[condition] = {
                     colour: getComputedStyle(dot).backgroundColor,
                     // AGAINST THE TOKEN, not against the other conditions. A
                     // set of inequalities is satisfied by a SWAP: exchange
                     // `connected` and `lost` in the variant table and all four
                     // still hold, while a dead stream draws the success token
                     // and a healthy one draws danger — B-155 exactly.
                     // RESOLVED THROUGH THE ENGINE, not read as a string. A
                     // token's DECLARED text is `oklch(72% .165 152)` and its
                     // computed form is `oklch(0.72 0.165 152)`: the same
                     // colour, and a string comparison of the two fails while
                     // saying nothing about the paint.
                     success: resolve("--color-success"),
                     danger: resolve("--color-danger"),
                     labelShown: getComputedStyle(label).display !== "none",
                   };
                 }
                 probe.remove();
                 return out;
               }""",
            {"mark": MARK, "states": {
                "connected": "acq-now-idle",
                "reconnecting": "relay-reconnecting",
                "lost": "relay-lost",
                "refused": "relay-refused"}})
        journal.check(
            "the word is not visible at the width this rule measures",
            not any(one["labelShown"] for one in painted.values()),
            "the label is shown — if that is true the word holds above measure "
            "something a reader sees, and this hold can go; while it is false "
            "they measure a `textContent` CSS has removed from the page")
        colours = {name: one["colour"] for name, one in painted.items()}
        journal.check(
            "a healthy connection is painted with the SUCCESS token",
            painted["connected"]["colour"] == painted["connected"]["success"],
            f"connected draws {painted['connected']['colour']} where "
            f"--color-success is {painted['connected']['success']}")
        journal.check(
            "and a lost one with the DANGER token",
            painted["lost"]["colour"] == painted["lost"]["danger"]
            and painted["refused"]["colour"] == painted["refused"]["danger"],
            f"lost draws {painted['lost']['colour']}, refused "
            f"{painted['refused']['colour']}, where --color-danger is "
            f"{painted['lost']['danger']} — a set of inequalities is satisfied "
            "by a SWAP, and a swap is the defect this hold opens by naming")
        journal.check(
            "a healthy connection is not painted like a broken one",
            colours["connected"] != colours["lost"]
            and colours["connected"] != colours["refused"]
            and colours["connected"] != colours["reconnecting"],
            f"the four conditions painted {colours} — the colour is the whole of "
            "what a reader sees here, and a dot that stayed green over a dead "
            "stream is the defect this rule opens by naming")
        journal.check(
            "and a wait is not painted like a settled failure",
            colours["reconnecting"] != colours["lost"],
            f"reconnecting {colours['reconnecting']}, lost {colours['lost']}")

        # THE CONTROL DOES SOMETHING, held by what happens and not by its label.
        acted = await page.evaluate(
            """async ({ notice }) => {
                 window.__go("relay-lost");
                 await new Promise((r) => setTimeout(r, 60));
                 document.querySelector(notice).querySelector("button").click();
                 await new Promise((r) => setTimeout(r, 400));
                 // THE DRAWING, not only the store. A component that stopped
                 // re-rendering on the condition would leave « cet écran ne se
                 // met plus à jour » on screen over a healthy connection, and
                 // this hold read the store and passed.
                 const mark = document.querySelector('[data-part="shell/connection-mark"]');
                 return {
                   condition: window.__relay.condition().condition,
                   drawn: mark ? mark.getAttribute("data-connection") : null,
                   noticeGone: document.querySelector(notice) === null,
                 };
               }""",
            {"notice": NOTICE})
        journal.check(
            "the retry really reconnects, and the warning really goes",
            acted["condition"] == "connected" and acted["drawn"] == "connected"
            and acted["noticeGone"],
            f"the condition is {acted['condition']!r}, the header draws "
            f"{acted['drawn']!r}, the notice is gone: {acted['noticeGone']} — a "
            "retry that fixes the store and leaves the warning on screen is "
            "still a screen saying something false")

        # AND `refused` OFFERS THE WAY BACK, held by where it LANDS. The
        # docstring said the action was "held by what the control DOES, not by
        # its label", and only the `lost` retry was: `refused`'s was held by a
        # `data-*` attribute and a label authored beside each other in the same
        # expression. Deleting the navigation left 25 holds green over the one
        # control a reader with an expired session can press.
        went = await page.evaluate(
            """async ({ notice }) => {
                 window.__go("relay-refused");
                 await new Promise((r) => setTimeout(r, 80));
                 document.querySelector(notice).querySelector("button").click();
                 await new Promise((r) => setTimeout(r, 300));
                 return location.pathname;
               }""",
            {"notice": NOTICE})
        journal.check(
            "`refused` really leads back to the sign-in",
            went == SIGN_IN_PATH,
            f"the control landed on {went!r}, expected {SIGN_IN_PATH!r} — a "
            "dead control in the state that offers it is B-156, and this is its "
            "other branch")

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
                          // `getComputedStyle` IS BLIND to the Web Animations
                          // API and to `requestAnimationFrame`: both read
                          // `animationName: "none"`. A hold whose stated
                          // subject is « the motion is DECLARED » must ask the
                          // element what is animating it, not what CSS says.
                          scripted: dot.getAnimations().length,
                          word: document.querySelector(mark).textContent.trim() };
               }""",
            {"mark": MARK})
        journal.check(
            "under reduced motion the dot stops moving, by every mechanism",
            still["animation"] == "none" and still["scripted"] == 0,
            f"animation-name is {still['animation']!r} and "
            f"{still['scripted']} animation(s) are running on the element — a "
            "scripted movement reads `none` here, so the CSS answer alone "
            "leaves invariant 14 held only against the mechanism nobody used")
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

        # `lost` REACHED FOR REAL, and it is the condition that most needed it:
        # the join to the transport was ONE hold, on `refused`, which is a
        # single close rather than a schedule. `lost` requires the ladder to
        # climb past three failed attempts — exactly the mechanism a forced
        # condition steps over — so a relay that could never REACH it would draw
        # the state perfectly in the named state and never in production.
        real_lost_context, real_lost_page = await open_page(browser, **PHONE)
        real_lost = await real_lost_page.evaluate(
            """async ({ mark, notice }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__go("acq-now-idle");
                 await wait(80);
                 // THE OPENING DEADLINE IS HELD LONG. Shortened, it climbs a
                 // ladder of its own on the same schedule and the hold can no
                 // longer name which timer it measured — the trap R95's own
                 // `PATIENT_OPENING_MS` comment records.
                 window.__relay.limits({ silence: 60_000, opening: 30_000 });
                 window.__mocks.stream.setUnreachable(true);
                 window.__mocks.stream.drop(1006);
                 // Past the fourth failure: 250 + 500 + 1000 + 2000.
                 await wait(4200);
                 const dot = document.querySelector(mark);
                 const bar = document.querySelector(notice);
                 window.__mocks.stream.setUnreachable(false);
                 return {
                   attempts: window.__relay.condition().attempts,
                   condition: dot ? dot.getAttribute("data-connection") : null,
                   word: dot ? dot.textContent.trim() : null,
                   action: bar ? bar.querySelector("button")
                     .getAttribute("data-connection-action") : null,
                 };
               }""",
            {"mark": MARK, "notice": NOTICE})
        journal.check(
            "a REAL climb past the backoff draws what the named state draws",
            real_lost["condition"] == "lost"
            and real_lost["word"] == WORDS["lost"]
            and real_lost["action"] == NOTICES["lost"]
            and real_lost["attempts"] > 3,
            f"after {real_lost['attempts']} failed attempt(s) the header drew "
            f"{real_lost['word']!r} at {real_lost['condition']!r} with control "
            f"{real_lost['action']!r} — the named states force the condition, so "
            "without this `lost` was proved against a lever and never against "
            "the ladder that has to climb to it")
        await real_lost_context.close()

        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R92 — the connection says what is wrong, where a reader is")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
