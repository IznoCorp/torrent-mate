"""R119 — priming draws what the tap knew, and a skeleton for the rest.

THE DEFECT (B-283). While a media sheet's read is in flight, the screen printed
its unknown parts as ANSWERS — « aucun synopsis », « aucune distribution »,
« pas de bande-annonce », seasons « inconnu » — assertions about data that has
not arrived, which the constitution refuses (§13). The decision that governs
the arrival — « A généralisée + amorçage » — says the screen opens with what
the tap already knew, in real content, and draws a SKELETON for the parts still
to come. Never an answer.

WHY NOTHING SAW IT, and why this rule cannot read the page as it is served.
The prototype's placeholder is the engine's COMPLETE sheet, so during priming
here no field is ever missing and no assertion is ever printed: a rule that
reads the full placeholder is green over the defect it is written for — the
species the register counts most. The real backend's projection carries
`{t, f}`, and THAT is the case driven here: the reference's `sheetFor` is
wrapped to answer the title, the kind and the year alone for the sheet under
test, and the read is held back through the mock layer's own knob.

HOW THE TWO SEAMS ARE REACHED BEFORE THE SCREEN FIRST RENDERS. A cold load
mounts the screen and issues the read at boot, so a wrapper installed after
`load` is installed after the placeholder was computed. Both seams are
published by assignment onto `window`, so an init script defines a SETTER for
each: the reference is wrapped the instant it is published, and the latency is
set the instant the layer is installed. The boot's own reads are slowed by the
same latency; the screen does not wait for them.

WHAT THE FIRST VERSION OF THIS RULE DID NOT READ, because it is the reason the
holds below have the shape they have. It counted `[data-skeleton]` against a
FLOOR of six where eleven stand, and it read assertions as
`[data-part="no-info"]`, a part name worn by two of the nine sites that can
print one. Between them that left a slack of five: the synopsis, the director
and the three season lines could all revert to printing their answer about data
in flight and every hold stayed green — three of the four examples the register
entry names, in the rule written for that entry. So the count is held EXACTLY,
against a thinning whose unknown parts are known, and the assertions are read as
TEXT: the screen's own words, taken from `fr.json` rather than retyped here, and
refused while the read is out.

WHAT IT DOES NOT READ, said first:
  - The RENDERING of a skeleton line. No named state shows the priming at
    rest — the placeholder is complete — so the oracle never measures it; the
    line's drawing is its variant's, and what this rule holds is that a line
    STANDS where an assertion would, and stands down when the read lands.
  - Any sheet but Broadchurch's. It is the one title whose served sheet lacks
    exactly one part (the trailer) while the cast and the seasons are full, so
    the landed reading has ONE no-info to find and every other part to land.
  - The seasons' own placeholder: there is none, and their flight is read
    through the same skeleton count — three of the lines counted below stand
    in the library facts while the seasons are out.
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal, open_page

TITLE = "Broadchurch"
# WHAT THE TAP KNOWS, and it is the TITLE alone. A list row is `{t, f}` — a
# title and a folder — and the year and the kind a card displays come from the
# same projection this thinning stands in for, folded into one string. Keeping
# `k` and `y` here made the hero's own fields impossible to measure: the metadata
# line was gated on the whole sheet being null, and with those two present it
# never took the branch that printed « année inconnue · Série » about a medium
# whose kind was in flight.
KEPT = ["t"]
# Long enough that every reading below is taken with the read still out under
# the suite's parallel load, and short enough that the rule stays cheap.
LATENCY_MILLISECONDS = 2000
# How long the screen is given to mount on a cold load before the in-flight
# reading is taken. Well under the latency, so the reading is in flight or the
# hold that says so falls.
MOUNT_DEADLINE_MILLISECONDS = 1500
# EXACTLY, not at least. A placeholder thinned to a known set has a KNOWN number
# of unknown parts, so the count is a fact and a floor under it is slack a defect
# fits into — measured: with a floor of six against eleven, three of the four
# assertions this rule exists to refuse could come back untouched. The number is
# read from the run and written here with the enumeration that produces it; a
# part gained or lost moves it, deliberately, and the rule says which.
#
# The parts, on the `{t}` thinning, as the rule PRINTS them: the address in the
# bar, the year and the kind of the hero's metadata line, the genres, the
# trailer, the synopsis, the director, the cast strip, the four library figures
# (seasons, aired episodes, owned, completeness), the two lines of the
# identifiers row, and the actions. Fourteen. The season list contributes none:
# with the seasons read still out there are no rows to draw them under, which is
# the honest drawing and not an omission.
#
# This number was written as 21 before it was measured, and the rule fell on its
# author's arithmetic — which is the reason it is an exact count and not a
# floor: a wrong number here is loud, where a floor is silent.
SKELETONS_EXPECTED = 14

INTERCEPT = """({ title, kept, latency, thin, fail }) => {
  let reference;
  Object.defineProperty(window, '__referentiel', {
    configurable: true,
    get() { return reference; },
    set(value) {
      reference = value;
      if (!thin || !value || typeof value.sheetFor !== 'function') return;
      const full = value.sheetFor.bind(value);
      window.__fullSheetFor = full;
      value.sheetFor = (asked) => {
        const sheet = full(asked);
        if (!sheet || asked !== title) return sheet;
        const thinned = {};
        for (const key of kept) if (key in sheet) thinned[key] = sheet[key];
        return thinned;
      };
    },
  });
  let mocks;
  Object.defineProperty(window, '__mocks', {
    configurable: true,
    get() { return mocks; },
    set(value) {
      mocks = value;
      if (!value || typeof value.setDefaultLatency !== 'function') return;
      value.setDefaultLatency(latency);
      // THE SHEET'S OWN READ FAILS, and only it: the seasons and the library
      // answer normally, so what is measured is a screen whose sheet failed
      // rather than a page with no server at all.
      if (fail) value.setOperationOutcome('readMediaSheet', { status: 502, latencyMilliseconds: 0 });
    },
  });
}"""

def assertions_from_resources():
    """The screen's own « unknown » words, read from the resource it prints from.

    NOT RETYPED. A rule holding a sentence it typed itself is a rule that goes
    green the day the interface's words change, which is the same defect one
    layer up from the one it measures.

    Returns:
        Every value under `screens.media` whose key names an unknown or an
        absence, plus the two the sheet draws from elsewhere.
    """
    resource = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
    media = resource["screens"]["media"]
    wanted = [key for key in media
              if key.endswith("Unknown") or key.endswith("UnknownFeminine")
              or key in ("unknown", "unknownFeminine", "unidentified", "noTrailer",
                         "episodesNotDetailed", "seasonAnnounced")]
    return sorted({media[key] for key in wanted if isinstance(media[key], str)})


def kind_words_from_resources():
    """« Film » and « Série » — an assertion about a KIND, not an absence.

    THE OTHER SHAPE OF THE SAME DEFECT, and the one an « unknown » word cannot
    catch: a screen that does not know whether it holds a film prints « Série »
    because that is the branch a false boolean takes. It says something
    confident about data in flight, which is what §13 refuses — the answer being
    positive rather than negative changes nothing. Measured: a mutation putting
    the kind back moved the skeleton count and left a text hold reading only the
    « unknown » words untouched.

    Returns:
        The two words, as the interface prints them.
    """
    resource = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
    return sorted({resource["common"]["film"], resource["common"]["series"]})


READ = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open]');
  return {
    open: !!screen,
    title: ((screen && screen.querySelector('[data-part="hero/title"]')) || {}).textContent || '',
    skeletons: screen ? screen.querySelectorAll('[data-skeleton]').length : -1,
    noInfos: screen ? [...screen.querySelectorAll('[data-part="no-info"]')].map((p) => p.textContent) : [],
    bodyChildren: ((screen && screen.querySelector('[data-region="screen-media/body"]')) || { children: [] }).children.length,
    cast: !!(screen && screen.querySelector('[data-part="cast"]')),
    synopsis: (((screen && screen.querySelector('[data-part="heading"]')) || {}).nextElementSibling || {}).textContent || '',
    inFlight: window.__mocks ? window.__mocks.inFlight() : -1,
    // WHAT EACH SKELETON STANDS IN FOR, so the count below is an enumeration a
    // reader can check rather than a number someone wrote down. A part that
    // stops waiting leaves this list, and the diff names it.
    parts: screen ? [...screen.querySelectorAll('[data-skeleton]')].map((line) => {
      const row = line.closest('[data-part="key-value"], [data-part="hero"], p, [data-part="screen/bar"], [data-part="sheet/actions"]');
      return ((row && row.textContent) || (line.parentElement || {}).className || '?')
        .trim().replace(/\s+/g, ' ').slice(0, 28);
    }) : [],
    text: screen ? (screen.textContent || '') : '',
    failed: !!(screen && screen.querySelector('[data-part="surface-error"]')),
    busy: !!(screen && screen.querySelector('[aria-busy="true"]')),
    actions: screen
      ? (screen.querySelector('[data-part="sheet/actions"]') || { children: [] }).children.length
      : -1,
  };
}"""


async def address_of(browser):
    """Resolves the sheet's address through the reference, on a throwaway page."""
    context, page = await open_page(browser)
    ids = await page.evaluate("(title)=>window.addressIdsFor(title)", TITLE)
    await context.close()
    return f"{PROTOTYPE}media/{ids['provider']}/{ids['id']}"


async def cold_load(browser, address, thin, fail=False):
    """Opens the sheet cold with the two seams intercepted from the first byte.

    Args:
        browser: A launched browser.
        address: The sheet's address.
        thin: Whether to thin the placeholder to what a list row carries.
        fail: Whether the sheet's own read answers with a failure.
    """
    context = await browser.new_context(**PHONE)
    await context.add_init_script(
        f"({INTERCEPT})({{ title: {TITLE!r}, kept: {KEPT!r}, "
        f"latency: {LATENCY_MILLISECONDS}, thin: {'true' if thin else 'false'}, "
        f"fail: {'true' if fail else 'false'} }})")
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    waited = 0
    while waited < MOUNT_DEADLINE_MILLISECONDS:
        if await page.evaluate("""()=>!!document.querySelector('[data-part="screen"][data-open]')"""):
            break
        await page.wait_for_timeout(50)
        waited += 50
    return context, page, errors


ASSERTIONS = assertions_from_resources()
# Refused only while the sheet's own read is out: once it lands, or once it
# fails and the screen falls back on what the tap knew, the kind is a fact.
KIND_WORDS = kind_words_from_resources()


async def main():
    journal = Journal("R119 — priming draws what the tap knew, and a skeleton for the rest")
    journal.check(
        "the screen's own « unknown » answers are readable from the resource — "
        "the text hold has something to refuse",
        len(ASSERTIONS) >= 8,
        f"{len(ASSERTIONS)} answer(s): {ASSERTIONS[:3]}…")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        address = await address_of(browser)

        # ─── The thinned walk: the case the real backend produces ─────────
        context, page, errors = await cold_load(browser, address, thin=True)
        thinned = await page.evaluate("""(title)=>{
          const full = window.__fullSheetFor ? window.__fullSheetFor(title) : null;
          const thin = window.__referentiel.sheetFor(title);
          return { fullKeys: full ? Object.keys(full).length : 0,
                   thinKeys: thin ? Object.keys(thin) : null };
        }""", TITLE)
        journal.check(
            "(a) the reference is wrapped and the placeholder is THINNED — the "
            "flight has a subject",
            thinned["fullKeys"] > 6 and thinned["thinKeys"] is not None
            and set(thinned["thinKeys"]) <= set(KEPT)
            and len(thinned["thinKeys"]) < thinned["fullKeys"],
            f"full sheet {thinned['fullKeys']} key(s), placeholder {thinned['thinKeys']} "
            f"— the title is the fixture's KEY, not a field, so a sheet thinned to "
            f"it carries no field at all, which is the leanest projection a tap can "
            f"know and the hardest case for the screen")
        early = await page.evaluate(READ)
        # THE SUBJECT FIRST, AND ON ITS OWN LINE. A hold that conflates « the
        # screen is open and its read is out » with « and here is what it draws »
        # falls for either reason and the tool that reads a FAIL cannot tell
        # which — so a mutation that merely broke the mount would read as proof
        # of the drawing.
        journal.check(
            "(b) the screen is open with its read still out — the holds below "
            "have a subject",
            early["open"] and early["inFlight"] > 0 and TITLE in early["title"],
            f"open={early['open']} in flight={early['inFlight']} title={early['title']!r}")
        journal.check(
            "(b-i) every unknown part stands as a skeleton — the EXACT count a "
            "known thinning produces, never a floor",
            early["open"] and early["skeletons"] == SKELETONS_EXPECTED,
            f"{early['skeletons']} skeleton(s), expected {SKELETONS_EXPECTED}, "
            f"standing in for: {early['parts']}")
        printed = [answer for answer in ASSERTIONS + KIND_WORDS
                   if answer and answer in early["text"]]
        journal.check(
            "(b-ii) and the screen says NONE of its « unknown » answers while "
            "the read is out — read as TEXT, from the resource it prints from",
            early["open"] and not printed and len(early["noInfos"]) == 0,
            f"{len(ASSERTIONS)} unknown answer(s) and {len(KIND_WORDS)} kind "
            f"word(s) read from fr.json; printed in flight: "
            f"{printed}; no-info part(s): {early['noInfos']}")
        journal.check(
            "(b-iii) the body says it is busy, so the silence a reader hears is "
            "temporary rather than empty",
            early["open"] and early["busy"],
            f"aria-busy present: {early['busy']}")
        journal.check(
            "(b-iv) and no action is offered over a medium the read has not "
            "identified — a destructive button is an assertion too",
            early["open"] and early["actions"] <= 1,
            f"{early['actions']} action(s) drawn while the sheet is out")
        early_children = early["bodyChildren"]
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        late = await page.evaluate(READ)
        journal.check(
            "(c) once the read lands the skeletons stand down and the one part "
            "the served sheet lacks is said — the trailer",
            late["inFlight"] == 0 and late["skeletons"] == 0
            and len(late["noInfos"]) == 1 and "bande-annonce" in late["noInfos"][0]
            and not late["busy"],
            f"read {late}")
        journal.check(
            "the body keeps the same blocks at both instants — a line stands "
            "in, a block never appears late",
            early_children > 0 and early_children == late["bodyChildren"],
            f"{early_children} block(s) in flight, {late['bodyChildren']} landed")
        journal.check("no JS error on the thinned walk", not errors, str(errors))
        await context.close()

        # ─── The control: the prototype's own COMPLETE placeholder ────────
        # NOT « zero skeletons ». The seasons have no placeholder and this
        # sheet's served creator is absent, so a few lines stand here too —
        # measured at 4 against 11. What separates the two walks is that the
        # parts the placeholder CARRIES are real content while the read is out:
        # the cast strip is drawn and the synopsis is a sentence, not a line.
        # A control that asked for zero was green over nothing and red over the
        # design working exactly as written.
        context, page, errors = await cold_load(browser, address, thin=False)
        control = await page.evaluate(READ)
        journal.check(
            "(d) the control — the complete placeholder, same latency — draws "
            "FEWER skeletons, and the parts it carries are content while the "
            "read is out",
            control["open"] and control["inFlight"] > 0
            and control["skeletons"] < early["skeletons"]
            and control["cast"] and len(control["synopsis"]) > 40,
            f"read {control} against {early['skeletons']} skeleton(s) thinned")
        journal.check("no JS error on the control walk", not errors, str(errors))
        await context.close()

        # ─── (e) THE READ FAILS, and the screen must not lie about it ──────
        # The query library drops its placeholder the moment a read errors, so
        # the screen went from showing what the tap knew to printing « le
        # provider n'en fournit pas » about a provider that had answered 502 —
        # a sentence that cannot change when the reality does, which is the
        # first thing the constitution's §13 forbids. Neither a skeleton
        # forever nor an answer: what the tap knew, and the failure said.
        context, page, errors = await cold_load(browser, address, thin=False, fail=True)
        # READ AT REST. Only the sheet's own read fails; the seasons answer
        # normally and are still out at the mount, so a reading taken there
        # measures a screen that is half in flight and says nothing about the
        # failure. What is held is the state a reader is LEFT in.
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        broken = await page.evaluate(READ)
        journal.check(
            "(e) a FAILED read draws the error surface, keeps what the tap knew, "
            "and asserts nothing about what it never got",
            broken["open"] and broken["failed"] and broken["skeletons"] == 0
            and TITLE in broken["title"] and broken["cast"]
            and not [answer for answer in ASSERTIONS
                     if answer in broken["text"] and "bande-annonce" not in answer],
            f"read {broken}")
        journal.check("no JS error on the failed walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
