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
wrapped to answer the title alone for the sheet under
test, and the read is held back through the mock layer's own knob.

HOW THE TWO SEAMS ARE REACHED BEFORE THE SCREEN FIRST RENDERS. A cold load
mounts the screen and issues the read at boot, so a wrapper installed after
`load` is installed after the placeholder was computed. Both seams are
published by assignment onto `window`, so an init script defines a SETTER for
each: the reference is wrapped the instant it is published, and the latency is
set the instant the layer is installed. The boot's own reads are slowed by the
same latency; the screen does not wait for them.

WHAT IT DRIVES. TEN cold loads, and each one is a walk of its own — the count is
the number of `cold_load` calls below, and it has been wrong in three documents
at once by being written down from memory:

  1. a placeholder thinned to the TITLE alone (`KEPT`), the leanest a tap knows;
  2. the prototype's own COMPLETE placeholder, as a control;
  3. a read that FAILS over that complete placeholder;
  4. the same failure over a THINNED one, on a title nobody owns;
  5. the same again on the rule's own title — the one sheet with NO trailer,
     which is the only walk where the sentence about what a provider furnishes
     can be printed at all;
  6. the same on a series the reader owns INCOMPLETELY, the only walk where a
     season's closed BODY has anything to assert;
  7. a walk where the SEASONS read fails alone and the sheet lands;
  8. the same failure on a FILM, which has no seasons to fail;
  9. a PARTIAL placeholder carrying the year and not the kind, where « field by
     field » is decidable at all;
 10. one where the seasons land before the sheet.

WHAT THE FIRST VERSION OF THIS RULE DID NOT READ, because it is the reason the
holds below have the shape they have. It counted `[data-skeleton]` against a
FLOOR of six where eleven stood then and fifteen stand now, and it read assertions as
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
# A SERIES THE LIBRARY DOES NOT OWN, for the walk that lands the two reads
# apart. An owned season draws its episode matrix from the owned numbers, which
# the reference answers synchronously — so the branch that says « les épisodes
# ne sont pas détaillés » is unreachable there, whatever the sheet is doing. On
# a suggestion there are no owned numbers, the matrix has nothing to draw, and
# the sentence about the sheet's episode lists is what the row would print.
NOT_OWNED_TITLE = "The Venture Bros"
# AND A TITLE THE READER OWNS, INCOMPLETELY. The walk above measures nothing
# about a season's BODY: the fixture records no owned numbers for a series
# nobody owns, so `ownedFor` answers nothing and the body is empty however the
# code is written. This one has holes, which is what makes « Manquants : … » and
# a matrix of cells reachable at all.
OWNED_INCOMPLETE_TITLE = "Monk"
# AND A FILM, which has no seasons at all — the kind that must never be told a
# seasons read failed.
FILM_TITLE = "Marjorie Prime"
# WHAT THE TAP KNOWS, and it is the TITLE alone. A list row is `{t, f}` — a
# title and a folder — and the year and the kind a card displays come from the
# same projection this thinning stands in for, folded into one string. Keeping
# `k` and `y` here made the hero's own fields impossible to measure: the metadata
# line was gated on the whole sheet being null, and with those two present it
# never took the branch that printed « année inconnue · Série » about a medium
# whose kind was in flight.
KEPT = ["t"]
# AND A PARTIAL ONE, which is where « field by field » is the whole question.
# With NOTHING known the hero draws one skeleton for its whole metadata line and
# the per-field branches are never reached — so a walk on the leanest projection
# alone cannot tell a line gated on the WHOLE sheet from a line gated per field.
# With the year known and the kind not, the two answers are separable, and a
# screen that prints « Série » for a kind it has not got says so out loud. That
# defect was live until a reader found it by reading; the mutation
# for it passes over the lean walk and falls here.
KEPT_PARTIAL = ["y"]
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
# The parts, on the `{t}` thinning, as the rule PRINTS them: the year and the
# kind of the hero's metadata line — separately, which is what « field by field »
# means — the genres, the rating, the trailer, the cast section's HEADING and its
# row LABEL (both are the kind, said in other words), the synopsis, the
# director's value, the cast strip, the VALUES of the two rows the library block
# draws while ownership is unknown — the rows name what they are waiting for, so
# only their answers wait — the two lines of the identifiers row, and the
# actions. Fifteen, and the rule prints them.
#
# The address in the bar is NOT among them any more: it is the address the reader
# navigated with, known at frame one, and a skeleton stood over it. The count has
# moved four times, each time because a part stopped asserting or stopped
# pretending to wait — which is what an exact count is for. The season list contributes none:
# with the seasons read still out there are no rows to draw them under, which is
# the honest drawing and not an omission.
#
# This number was written as 21 before it was measured, and the rule fell on its
# author's arithmetic — which is the reason it is an exact count and not a
# floor: a wrong number here is loud, where a floor is silent. It has moved
# twice since, both times because a part that had been asserting started
# waiting, and both times the rule said so.
SKELETONS_EXPECTED = 15

INTERCEPT = """({ title, kept, latency, thin, fail, failSeasons, ownershipUnknown, seasonsFirst }) => {
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
      // THE TWO READS LAND APART, which is the only arrangement where the
      // season list's own question can be asked: its rows come from the seasons
      // and its episode lists from the sheet. With one latency for both they
      // arrive together and the interval does not exist to be measured.
      if (seasonsFirst) value.setOperationOutcome('readMediaSeasons', { latencyMilliseconds: 0 });
      // AND THE SEASONS READ FAILS ON ITS OWN. It is a SECOND query, and every
      // number in the library block is derived from it: with the sheet landed
      // and this one errored the screen printed « Possédés 0 » — a count of
      // what the reader holds, taken from a read that never arrived — with no
      // surface and nothing to press.
      if (failSeasons) value.setOperationOutcome('readMediaSeasons', { status: 502, latencyMilliseconds: 0 });
      // AND THE OWNERSHIP THE CONTRACT CALLS UNKNOWN. `ownership` is nullable
      // and null means the library database is unavailable — a state a backend
      // reaches on its own, and the one the screen has to draw as « inconnue »
      // rather than as « non ».
      if (ownershipUnknown && typeof value.setLibraryDatabaseAvailable === 'function') {
        value.setLibraryDatabaseAvailable(false);
      }
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


def provider_sentences_from_resources():
    """The sentences that answer FOR the provider, as the interface prints them.

    A SENTENCE THAT SPEAKS FOR SOMEONE ELSE cannot be printed over a read that
    never reached them. « Synopsis inconnu — le provider n'en fournit pas » and
    « Aucune bande-annonce fournie par le provider » are answers about what a
    provider holds; after a 502 nobody asked it. They are not « unknown » words
    — each one asserts something — so the list this rule already reads cannot
    catch them.

    Returns:
        The two sentences, from the resource the screen prints from.
    """
    resource = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
    media = resource["screens"]["media"]
    return [media["synopsisUnknown"], media["noTrailer"]]


def unidentified_from_resources():
    """The bar's sentence for a medium no read identified.

    Returns:
        The sentence, from the resource the screen prints from.
    """
    resource = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
    return resource["screens"]["media"]["unidentified"]


def kind_words_from_resources():
    """Every text the KIND decides — an assertion about it, not an absence.

    THE OTHER SHAPE OF THE SAME DEFECT, and the one an « unknown » word cannot
    catch: a screen that does not know whether it holds a film prints « Série »
    because that is the branch a false boolean takes. It says something
    confident about data in flight, which is what §13 refuses — the answer being
    positive rather than negative changes nothing. Measured: a mutation putting
    the kind back moved the skeleton count and left a text hold reading only the
    « unknown » words untouched.

    THE WORD IS NOT THE ONLY WAY TO SAY IT, and reading « Film »/« Série »
    alone left three sites out: the section HEADING (« Création et distribution »
    against « Réalisation et distribution »), the row LABEL (« Créateur »
    against « Réalisateur ») and, through the same boolean, the SHAPE of the
    library block. Every one of them says what the screen thinks it holds.

    Returns:
        Every such text, as the interface prints them.
    """
    resource = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
    media = resource["screens"]["media"]
    return sorted({resource["common"]["film"], resource["common"]["series"],
                   media["castHeadingFilm"], media["castHeadingSeries"],
                   media["director"], media["creator"]})


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
    // IS THE SHEET'S OWN READ OUT? `inFlight()` counts every request the layer
    // holds — the library's, the stream's — so « something is in flight » is
    // true on a page where the sheet landed long ago, and a hold resting on it
    // would call any reading « in flight ». The cache answers about THIS query.
    sheetOut: (() => {
      const cache = window.__queries && window.__queries.getQueryCache();
      if (!cache) return null;
      const sheet = cache.getAll().find(
        (query) => query.queryKey[0] === '/api/media' && query.queryKey.length === 3);
      // `data === undefined` was the first reading and it says two things at
      // once: a read still out, and a read that FAILED with nothing to show.
      // The screen is not in flight in the second, so a walk holding « in
      // flight » on it would measure the error case under another name.
      return sheet
        ? (sheet.state.status === 'pending' || sheet.state.fetchStatus === 'fetching')
        : null;
    })(),
    // WHAT EACH SKELETON STANDS IN FOR, so the count below is an enumeration a
    // reader can check rather than a number someone wrote down. A part that
    // stops waiting leaves this list, and the diff names it.
    parts: screen ? [...screen.querySelectorAll('[data-skeleton]')].map((line) => {
      const row = line.closest('[data-part="key-value"], [data-part="hero"], p, [data-part="screen/bar"], [data-part="sheet/actions"]');
      return ((row && row.textContent) || (line.parentElement || {}).className || '?')
        .trim().replace(/[ ]+/g, ' ').slice(0, 28);
    }) : [],
    text: screen ? (screen.textContent || '') : '',
    // WHAT ARITHMETIC ASSERTS, which no list of words can catch. « Possédés 0 »
    // and « 13 manquants » are answers about what the reader HOLDS, and they are
    // numbers: a text hold reading the interface's « unknown » words is blind to
    // them by construction, and the exact skeleton count only says that
    // something is waiting, not that nothing is claiming.
    ownedZero: screen ? /Poss[ée]d[ée]s[ ]*0/.test(screen.textContent || '') : false,
    missing: screen ? screen.querySelectorAll('[data-part="season/missing"]').length : -1,
    // AND WHAT IS ONE TAP DOWN. The three lines of a season's SUMMARY waited on
    // ownership and its BODY did not: under « Saison 8 inconnu » stood
    // « Manquants : 1–16 » and sixteen cells coloured « à récupérer », an
    // assertion about what the reader holds, drawn from `ownedFor` read one
    // line below the gate. The rows are closed at rest, so a hold that reads
    // only what is visible sees none of it — these count the markup.
    openRows: screen ? screen.querySelectorAll('[data-part="season"][open]').length : -1,
    episodeCells: screen ? screen.querySelectorAll('[data-part="episode"]').length : -1,
    missingParagraphs: screen
      ? screen.querySelectorAll('[data-part="season/missing-list"]').length : -1,
    // A FRACTION IS THE OWNERSHIP ASSERTION IN ITS SHORTEST FORM. « 0/13 » in a
    // season's summary says the reader holds none of it; it is neither a word
    // this rule lists nor a chip it counts.
    fractions: screen
      ? [...screen.querySelectorAll('[data-part="season"] summary')]
          .filter((row) => /[0-9]+[ ]*\\/[ ]*[0-9]+/.test(row.textContent || '')).length
      : -1,
    // THE BAR'S OWN SENTENCE. « média non identifié » is an answer about the
    // medium, and after a failure nobody answered.
    bar: screen
      ? ((screen.querySelector('[data-part="screen/bar"]') || {}).textContent || '')
      : '',
    completeness: screen
      ? /Compl[ée]tude[ ]*0[ ]*%/.test(screen.textContent || '') : false,
    failed: !!(screen && screen.querySelector('[data-part="surface-error"]')),
    // WHAT THE FAILURE SAYS, and not merely that it is drawn. The shared body
    // is a sentence about a TIMEOUT; a read that came back 502 with its reason
    // in hand is not a timeout, and « the surface is present » cannot tell the
    // two apart.
    errorText: screen
      ? ((screen.querySelector('[data-part="surface-error"]') || {}).textContent || '')
      : '',
    errorDetail: screen
      ? ((screen.querySelector('[data-part="surface-error/detail"]') || {}).textContent || '')
      : '',
    // THE SCREEN ITSELF COUNTS. `querySelector` reads DESCENDANTS only, so an
    // `aria-busy` moved one level up — onto the screen — would leave this
    // reading false while the screen says it is busy.
    busy: !!(screen && (screen.matches('[aria-busy="true"]')
                        || screen.querySelector('[aria-busy="true"]'))),
    // BUTTONS, not children: in flight the one child is a skeleton, so « at
    // most one child » is satisfied by one real button just as well — and one
    // real button over a medium nobody has identified is the whole defect.
    actions: screen
      ? (screen.querySelector('[data-part="sheet/actions"]')
          || { querySelectorAll: () => [] }).querySelectorAll('button').length
      : -1,
  };
}"""


async def address_of(browser, title=None):
    """Resolves a sheet's address through the reference, on a throwaway page.

    Args:
        browser: A launched browser.
        title: Which title. The measured one by default.

    Returns:
        The address, as the router reads it.
    """
    context, page = await open_page(browser)
    ids = await page.evaluate("(t)=>window.addressIdsFor(t)", title or TITLE)
    await context.close()
    return f"{PROTOTYPE}media/{ids['provider']}/{ids['id']}"


async def cold_load(browser, address, thin, fail=False, kept=None, seasons_first=False,
                    title=None, fail_seasons=False, ownership_unknown=False):
    """Opens the sheet cold with the two seams intercepted from the first byte.

    Args:
        browser: A launched browser.
        address: The sheet's address.
        thin: Whether to thin the placeholder to what a list row carries.
        fail: Whether the sheet's own read answers with a failure.
        kept: Which fields the thinned placeholder keeps. `KEPT` by default.
        seasons_first: Whether the seasons answer at once while the sheet waits.
        fail_seasons: Whether the SEASONS read answers with a failure — the
            sheet lands, and every number derived from the seasons does not.
        ownership_unknown: Whether the layer answers a NULL ownership, which the
            contract defines as « the library database is unavailable ».
        title: Whose placeholder is thinned. The measured title by default — and
            it must be the title the ADDRESS opens, or the thinning applies to a
            sheet nobody is looking at and the walk measures a complete one.
    """
    context = await browser.new_context(**PHONE)
    await context.add_init_script(
        f"({INTERCEPT})({{ title: {(title or TITLE)!r}, kept: {(kept or KEPT)!r}, "
        f"latency: {LATENCY_MILLISECONDS}, thin: {'true' if thin else 'false'}, "
        f"fail: {'true' if fail else 'false'}, "
        f"failSeasons: {'true' if fail_seasons else 'false'}, "
        f"ownershipUnknown: {'true' if ownership_unknown else 'false'}, "
        f"seasonsFirst: {'true' if seasons_first else 'false'} }})")
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


def failure_body_from_resources():
    """The shared error surface's own sentence — the one that asserts a timeout.

    Read from the resource rather than retyped, like every other text this rule
    refuses: a hold quoting a sentence it typed itself goes green the day the
    interface's words change.

    Returns:
        The sentence, whitespace folded as the DOM renders it.
    """
    resource = json.loads(
        (pathlib.Path(__file__).resolve().parent.parent
         / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
    return " ".join(resource["surfaces"]["error"]["body"].split())


ASSERTIONS = assertions_from_resources()
TIMEOUT_SENTENCE = failure_body_from_resources()
# Refused only while the sheet's own read is out: once it lands, or once it
# fails and the screen falls back on what the tap knew, the kind is a fact.
KIND_WORDS = kind_words_from_resources()
PROVIDER_SENTENCES = provider_sentences_from_resources()
UNIDENTIFIED = unidentified_from_resources()
# The word the interface prints for a feminine unknown — « la médiathèque » —
# read from the resource rather than typed here.
UNKNOWN_FEMININE = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8")
)["screens"]["media"]["unknownFeminine"]


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
            early["open"] and early["sheetOut"] and TITLE in early["title"],
            f"open={early['open']} the sheet's own read is out={early['sheetOut']} "
            f"title={early['title']!r}")
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
            early["open"] and early["actions"] == 0,
            f"{early['actions']} action button(s) drawn while the sheet is out")
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
        # NOT « zero skeletons ». The seasons carry no placeholder of their
        # own, so the library block's rows stand here too whatever the sheet
        # holds — the rule prints the control's own count beside this hold. What
        # separates the two walks is that the parts the placeholder CARRIES are
        # real content while the read is out: the cast strip is drawn and the
        # synopsis is a sentence, not a line. A control asking for zero was
        # green over nothing and red over the design working exactly as written.
        # (The figures « 4 against 11 » stood in this comment after the thinning
        # and the count had both moved; a number written beside the number a
        # tool prints is the drift this file measures elsewhere.)
        context, page, errors = await cold_load(browser, address, thin=False)
        control = await page.evaluate(READ)
        journal.check(
            "(d) the control — the complete placeholder, same latency — draws "
            "FEWER skeletons, and the parts it carries are content while the "
            "read is out",
            control["open"] and control["sheetOut"]
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
        # THE TRAILER'S OWN LINE IS NOT AN ASSERTION ABOUT THE FAILED READ: its
        # absence is a fact the tap knew, and the sentence sits in a `no-info`
        # paragraph of its own. It used to be excluded by a French substring
        # typed here, which stopped excluding anything the day the sentence was
        # reworded — and (e) then fell over its own repair. What is excluded is
        # what the screen DRAWS as a no-info paragraph, whatever it says.
        outside = broken["text"]
        for said in broken["noInfos"]:
            outside = outside.replace(said, "")
        journal.check(
            "(e) a FAILED read draws the error surface, keeps what the tap knew, "
            "and asserts nothing about what it never got",
            broken["open"] and broken["failed"] and broken["skeletons"] == 0
            and TITLE in broken["title"] and broken["cast"]
            and not [answer for answer in ASSERTIONS if answer in outside],
            f"read {broken}; assertion(s) outside the no-info paragraphs: "
            f"{[answer for answer in ASSERTIONS if answer in outside]}")
        # AND THE RETRY RE-ASKS THE READ IT STANDS ON. « Réessayer » wrote a
        # page's UI phase through the engine's delegation and asked no query:
        # the markup carried a retry and the behaviour did not, which no hold
        # reading the surface's PRESENCE could tell apart.
        before_retry = await page.evaluate("""() => {
          const sheet = window.__queries.getQueryCache().getAll().find(
            (query) => query.queryKey[0] === '/api/media' && query.queryKey.length === 3);
          return sheet ? sheet.state.errorUpdateCount : null;
        }""")
        retry_state = await page.evaluate("""async () => {
          const button = document.querySelector('[data-part="surface-error/retry"]');
          if (!button) return { clicked: false };
          button.click();
          await new Promise((done) => setTimeout(done, 250));
          const sheet = window.__queries.getQueryCache().getAll().find(
            (query) => query.queryKey[0] === '/api/media' && query.queryKey.length === 3);
          return { clicked: true,
                   fetchStatus: sheet ? sheet.state.fetchStatus : null,
                   // `fetchFailureCount` was the first reading and it does
                   // not move: the reducer zeroes it when a read starts and
                   // adds one when it errors, so it is 1 before the click and
                   // 1 after. `errorUpdateCount` counts the ANSWERS.
                   errors: sheet ? sheet.state.errorUpdateCount : null,
                   delegated: !!button.getAttribute('data-phase') };
        }""")
        journal.check(
            "(e-i) and its « Réessayer » re-asks THIS read rather than writing "
            "a page's phase through the delegation",
            retry_state["clicked"] and not retry_state["delegated"]
            and (retry_state["errors"] or 0) > (before_retry or 0),
            f"read {retry_state}; the answer count was {before_retry} before "
            f"the click and {retry_state['errors']} after — a count that MOVED "
            f"is the query having been asked again, which a count that reads 1 "
            f"whether or not anyone clicked could never say")
        journal.check(
            "(e-ii) and the failure says what the SERVER said, not a sentence "
            "about a timeout over a server that answered",
            broken["errorDetail"].strip() != ""
            and " ".join(broken["errorText"].split()).find(TIMEOUT_SENTENCE) < 0,
            f"detail on the surface: {broken['errorDetail'][:80]!r}; the "
            f"timeout sentence present: "
            f"{TIMEOUT_SENTENCE in ' '.join(broken['errorText'].split())}")
        journal.check("no JS error on the failed walk", not errors, str(errors))
        await context.close()

        # ─── (e-iii) THE FAILURE HOLDING A THIN FALLBACK, which is the real
        # projection's error case and the one the walk above cannot reach: with
        # the complete placeholder every field is content, so there is nothing
        # left to assert about. Thinned, the screen holds a sheet that says
        # almost nothing — and « not in flight » was enough to call its
        # ownership KNOWN, which brought back « Possédés 0 », « Complétude 0 % »,
        # the missing chips and a « Supprimer » for a medium nobody identified.
        context, page, errors = await cold_load(
            browser, await address_of(browser, NOT_OWNED_TITLE),
            thin=True, fail=True, title=NOT_OWNED_TITLE)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        thin_failure = await page.evaluate(READ)
        journal.check(
            "(e-iii) a failed read holding a THIN fallback claims no ownership "
            "— no count, no completeness, no missing chip, no action, no open "
            "row, no fraction and no episode cell one tap down",
            thin_failure["open"] and thin_failure["failed"]
            and not thin_failure["ownedZero"] and not thin_failure["completeness"]
            and thin_failure["missing"] == 0 and thin_failure["actions"] == 0
            and thin_failure["openRows"] == 0 and thin_failure["fractions"] == 0
            and thin_failure["episodeCells"] == 0
            and thin_failure["missingParagraphs"] == 0,
            f"« Possédés 0 »: {thin_failure['ownedZero']}, « Complétude 0 % »: "
            f"{thin_failure['completeness']}, « manquants » chips: "
            f"{thin_failure['missing']}, action button(s): "
            f"{thin_failure['actions']}, open row(s): {thin_failure['openRows']}, "
            f"fraction(s): {thin_failure['fractions']}, episode cell(s): "
            f"{thin_failure['episodeCells']}, « Manquants : … » paragraph(s): "
            f"{thin_failure['missingParagraphs']}")
        # AND IT SAYS NOTHING FOR THE SERVER EITHER. « média non identifié » in
        # the bar and « le provider n'en fournit pas » under the synopsis are
        # both ANSWERS — one about the medium, one about what the provider
        # holds — printed over a read that came back 502 without reaching
        # either question. The words are read from the resources, never retyped:
        # a retyped sentence renders correctly while the reference has moved.
        journal.check(
            "(e-iii-a) and the failure speaks neither for the medium nor for "
            "the provider — the address the reader navigated with stands, and "
            "no sentence claims what a provider does or does not furnish",
            UNIDENTIFIED not in thin_failure["bar"]
            and PROVIDER_SENTENCES
            and not [said for said in PROVIDER_SENTENCES
                     if said in thin_failure["text"]],
            f"bar {thin_failure['bar'].strip()[:60]!r}; sentence(s) speaking "
            f"for the provider: "
            f"{[said for said in PROVIDER_SENTENCES if said in thin_failure['text']]}")
        await context.close()

        # ─── (e-iii-b) THE SAME TERM ON A TITLE THAT CAN PRINT THE SENTENCE ──
        # The walk above opens a medium the fixture gives a trailer, so its
        # trailer line is a link and the sentence about what the provider
        # furnishes is unreachable there — the term read true whatever the code
        # said. Measured: a build printing that sentence over a 502 passed every
        # hold of this rule. The rule's own title is the one sheet with NO
        # trailer, which is the case the term exists for.
        context, page, errors = await cold_load(
            browser, address, thin=True, fail=True)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        no_trailer_failure = await page.evaluate(READ)
        journal.check(
            "(e-iii-b) and on the one sheet with no trailer at all — where the "
            "sentence about what a provider furnishes is REACHABLE — a failure "
            "still does not print it",
            no_trailer_failure["open"] and no_trailer_failure["failed"]
            and not [said for said in PROVIDER_SENTENCES
                     if said in no_trailer_failure["text"]],
            f"sentence(s) speaking for the provider on {TITLE!r}: "
            f"{[said for said in PROVIDER_SENTENCES if said in no_trailer_failure['text']]}; "
            f"no-info paragraph(s): {no_trailer_failure['noInfos']}")
        journal.check("no JS error on the thin failure walk", not errors, str(errors))
        await context.close()

        # ─── (e-iv) THE SAME FAILURE ON A TITLE THE READER ACTUALLY OWNS, and
        # owns INCOMPLETELY. (e-iii) walks a title the fixture records no owned
        # numbers for, so `ownedFor` answers nothing there and the bodies are
        # empty whether or not anyone gated them: the hold could not have seen
        # the defect it was written for. On an owned, incomplete series the same
        # screen printed « Manquants : 1–16 » and sixteen cells under
        # « Saison 8 inconnu » — one tap down, on rows closed at rest.
        context, page, errors = await cold_load(
            browser, await address_of(browser, OWNED_INCOMPLETE_TITLE),
            thin=True, fail=True, title=OWNED_INCOMPLETE_TITLE)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        owned_failure = await page.evaluate(READ)
        journal.check(
            "(e-iv) and on a series the reader OWNS INCOMPLETELY, the same "
            "failure draws no missing list and no episode cell — the season "
            "bodies wait on ownership like the lines above them",
            owned_failure["open"] and owned_failure["failed"]
            and owned_failure["missingParagraphs"] == 0
            and owned_failure["episodeCells"] == 0
            and owned_failure["missing"] == 0
            and owned_failure["openRows"] == 0
            and owned_failure["fractions"] == 0,
            f"« Manquants : … » paragraph(s): "
            f"{owned_failure['missingParagraphs']}, episode cell(s): "
            f"{owned_failure['episodeCells']}, « manquants » chip(s): "
            f"{owned_failure['missing']}, open row(s): "
            f"{owned_failure['openRows']}, fraction(s): "
            f"{owned_failure['fractions']} — on {OWNED_INCOMPLETE_TITLE!r}, "
            f"which the fixture records owned numbers for")
        journal.check("no JS error on the owned-failure walk", not errors, str(errors))
        await context.close()

        # ─── (e-v) THE SECOND READ FAILS AND THE FIRST DOES NOT ─────────────
        # The library block's numbers all come from the SEASONS read. With the
        # sheet landed and that read errored, `isPending` is false and every one
        # of them printed as a fact: « Possédés 0 » — the exact string this
        # rule's own term names as the defect's signature — beside « Saisons
        # inconnu » and « Complétude inconnue », with no surface and nothing to
        # press. A read has three outcomes and this screen knew two.
        context, page, errors = await cold_load(
            browser, address, thin=False, fail_seasons=True)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(400)
        seasons_failure = await page.evaluate(READ)
        journal.check(
            "(e-v) a failed SEASONS read is said and can be asked again, and "
            "the counts derived from it are unknown rather than zero",
            seasons_failure["open"] and seasons_failure["failed"]
            and not seasons_failure["ownedZero"]
            and seasons_failure["errorDetail"].strip() != "",
            f"« Possédés 0 »: {seasons_failure['ownedZero']}, surface drawn: "
            f"{seasons_failure['failed']}, detail on it: "
            f"{seasons_failure['errorDetail'][:60]!r}")
        seasons_retry = await page.evaluate("""async () => {
          const button = document.querySelector('[data-part="surface-error/retry"]');
          if (!button) return { clicked: false };
          const count = () => {
            const seasons = window.__queries.getQueryCache().getAll().find(
              (query) => query.queryKey[0] === '/api/media' && query.queryKey.length === 4);
            return seasons ? seasons.state.errorUpdateCount : null;
          };
          const before = count();
          button.click();
          await new Promise((done) => setTimeout(done, 300));
          return { clicked: true, before, after: count() };
        }""")
        journal.check(
            "(e-v-a) and its « Réessayer » re-asks the SEASONS read — the "
            "answer count moves, which is the only reading that tells a re-ask "
            "from a screen that merely redraws",
            seasons_retry["clicked"]
            and (seasons_retry["after"] or 0) > (seasons_retry["before"] or 0),
            f"answer count {seasons_retry.get('before')} before the click, "
            f"{seasons_retry.get('after')} after")
        journal.check("no JS error on the failed-seasons walk", not errors, str(errors))
        await context.close()

        # ─── (e-vi) AND A FILM IS TOLD NOTHING ABOUT SEASONS IT HAS NONE OF ──
        # The seasons read is issued for every address — the kind arrives with
        # the sheet, after it — so a failure raised its surface under a film
        # too: « Impossible de charger les saisons de cette fiche » beside
        # « Possédé oui » and a file name, with a retry re-asking the seasons of
        # a film. A backend answering 404 there would have shown it under every
        # owned film.
        context, page, errors = await cold_load(
            browser, await address_of(browser, FILM_TITLE),
            thin=False, fail_seasons=True, title=FILM_TITLE)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(400)
        film = await page.evaluate(READ)
        journal.check(
            "(e-vi) a FILM whose seasons read failed is told nothing about "
            "seasons — the surface is drawn for what has them",
            film["open"] and not film["failed"],
            f"error surface drawn on {FILM_TITLE!r}: {film['failed']}; "
            f"it says {' '.join(film['errorText'].split())[:80]!r}")
        journal.check("no JS error on the film walk", not errors, str(errors))
        await context.close()

        # ─── (e-vii) THE OWNERSHIP THE CONTRACT CALLS UNKNOWN ─────────────
        # `MediaSheetResponse.ownership` is required and NULLABLE, and the
        # contract says what null means: the library database is unavailable.
        # That is the definition of « nobody knows », and the screen read it as
        # « the key is present », classed it KNOWN, and then printed « non » —
        # every owned number gone, the season rows switched to a catalogue of
        # air dates, and « Suivre » offered for a medium sitting in the library.
        # Nothing held it: reverting the one line left every hold of this rule
        # green, because no rule read ownership at all.
        context, page, errors = await cold_load(
            browser, address, thin=False, ownership_unknown=True)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(400)
        unknown_ownership = await page.evaluate(READ)
        journal.check(
            "(e-vii) an ownership the layer answers as NULL is drawn as unknown "
            "— not as « not owned »: no count, no completeness, no missing "
            "chip, no action, and the unknown word where the answer would be",
            unknown_ownership["open"]
            and not unknown_ownership["ownedZero"]
            and unknown_ownership["missing"] == 0
            and unknown_ownership["actions"] == 0
            and unknown_ownership["fractions"] == 0
            and unknown_ownership["openRows"] == 0,
            f"« Possédés 0 »: {unknown_ownership['ownedZero']}, "
            f"« manquants » chip(s): {unknown_ownership['missing']}, "
            f"action button(s): {unknown_ownership['actions']}, fraction(s): "
            f"{unknown_ownership['fractions']}, open row(s): "
            f"{unknown_ownership['openRows']}")
        # AND THE WORD ITSELF, because « no numbers » is also what a screen
        # showing nothing at all looks like. The library block draws its rows
        # either way; what changes is whether their VALUES are answers.
        unknown_words = await page.evaluate("""(words) => {
          const screen = document.querySelector('[data-part="screen"][data-open]');
          const text = screen ? (screen.textContent || '') : '';
          return words.filter((said) => text.includes(said));
        }""", [UNKNOWN_FEMININE])
        journal.check(
            "(e-vii-a) and it SAYS so, in the interface's own word for it",
            unknown_words == [UNKNOWN_FEMININE],
            f"the unknown word present: {unknown_words}")
        journal.check("no JS error on the unknown-ownership walk",
                      not errors, str(errors))
        await context.close()

        # ─── (e-viii) A SHEET AFTER A CONFIRMED DELETE ────────────────────────
        # The list is honest in the same task and the SHEET was not: reopened
        # after a confirmed delete it read « Possédés 24 » from its own cached
        # answer and offered « Supprimer » again — over the toast saying it was
        # done. Invalidating the media reads is half of it; the other half is
        # that the layer has to be able to ANSWER the mutation, which it could
        # not: ownership came from a seed keyed by title, so a refetch returned
        # exactly what it returned before and a repair for this was
        # unmeasurable.
        context, page, errors = await cold_load(browser, address, thin=False)
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        before_delete = await page.evaluate(READ)
        await page.evaluate("(title)=>window.__deleteLibraryItems([title])", TITLE)
        # TWO ROUND TRIPS THROUGH THE LAYER, and the layer's default latency
        # applies to both: the mutation answers, and only THEN is the read the
        # invalidation causes issued. One `quiet()` waits for the first and
        # returns before the second exists — which is a walk that reads the
        # screen mid-repair and calls it unrepaired.
        for _ in range(3):
            await page.evaluate("()=>window.__mocks.quiet()")
            await page.wait_for_timeout(300)
        after_delete = await page.evaluate(READ)
        journal.check(
            "the sheet of an owned medium offers to delete it — the hold below "
            "has a subject",
            before_delete["actions"] == 2 and before_delete["fractions"] > 0,
            f"{before_delete['actions']} action(s), "
            f"{before_delete['fractions']} fraction(s) before the delete")
        journal.check(
            "(e-viii) and once that delete is confirmed the same sheet stops "
            "saying the medium is held — no owned fraction, and no second "
            "« Supprimer » over a toast that said it was done",
            after_delete["fractions"] == 0 and after_delete["actions"] < 2,
            f"{after_delete['actions']} action(s) and "
            f"{after_delete['fractions']} owned fraction(s) after the delete, "
            f"against {before_delete['actions']} and "
            f"{before_delete['fractions']} before")
        journal.check("no JS error on the delete walk", not errors, str(errors))
        await context.close()

        # ─── (f) A PARTIAL PLACEHOLDER, where field by field is the question ─
        context, page, errors = await cold_load(
            browser, address, thin=True, kept=KEPT_PARTIAL)
        partial = await page.evaluate(READ)
        year = await page.evaluate(
            "(title)=>String((window.__fullSheetFor(title) || {}).y || '')", TITLE)
        journal.check(
            "(f) with the YEAR known and the kind not, the year is content and "
            "the kind is a skeleton — a field waits for its own answer",
            partial["open"] and partial["sheetOut"] and year
            and year in partial["text"]
            and not [word for word in KIND_WORDS if word in partial["text"]],
            f"year {year!r} in text: {year in partial['text']}; kind word(s) "
            f"printed: {[word for word in KIND_WORDS if word in partial['text']]}; "
            f"{partial['skeletons']} skeleton(s) for {partial['parts']}")
        journal.check("no JS error on the partial walk", not errors, str(errors))
        await context.close()

        # ─── (g) THE SEASONS LAND FIRST, and the sheet is still out ────────
        # The season list's rows come from the seasons read and its episode
        # lists from the sheet — two queries. Sharing one latency they arrive
        # together, so « Épisodes non détaillés pour cette saison », said about
        # a list still on its way, has no interval to be seen in. This walk
        # makes the interval, which is what a reader could only predict.
        context, page, errors = await cold_load(
            browser, await address_of(browser, NOT_OWNED_TITLE),
            thin=True, seasons_first=True, title=NOT_OWNED_TITLE)
        thinned_apart = await page.evaluate('''(title)=>{
          const full = window.__fullSheetFor ? window.__fullSheetFor(title) : null;
          const thin = window.__referentiel.sheetFor(title);
          return { fullKeys: full ? Object.keys(full).length : 0,
                   thinKeys: thin ? Object.keys(thin).length : null };
        }''', NOT_OWNED_TITLE)
        journal.check(
            "(g-i) this walk's own placeholder is thinned — the walk that "
            "exists because a previous version measured a complete one",
            thinned_apart["fullKeys"] > 6 and thinned_apart["thinKeys"] == 0,
            f"full sheet {thinned_apart['fullKeys']} key(s), placeholder "
            f"{thinned_apart['thinKeys']} key(s) — a floor on the skeleton "
            f"count is not this check: a complete placeholder leaves a skeleton "
            f"or two of residue, which passes it")
        apart = await page.evaluate(READ)
        seasons_drawn = await page.evaluate("""
            ()=>document.querySelectorAll('[data-part="season"]').length""")
        # THE SEASONS' OWN ANSWERS ARE NOT ASSERTIONS ABOUT THE SHEET. « Saison
        # annoncée : aucun épisode diffusé » is what the seasons read RETURNED,
        # drawn deliberately and before the sheet's flight — the same rule with
        # its sign turned round. It is in the list of unknown words this hold
        # refuses, so a walk that met one would have fallen on the screen being
        # right. What is refused is what stands OUTSIDE the no-info paragraphs.
        apart_outside = apart["text"]
        for said in apart["noInfos"]:
            apart_outside = apart_outside.replace(said, "")
        journal.check(
            "(g) with the seasons landed and the sheet still out, the season "
            "rows are drawn and say NOTHING about the episode lists they have "
            "not got — nor about what the reader HOLDS of them",
            apart["open"] and apart["sheetOut"] and seasons_drawn > 0
            and apart["skeletons"] > 0
            and not apart["ownedZero"] and not apart["completeness"]
            and apart["missing"] == 0
            and not [answer for answer in ASSERTIONS if answer in apart_outside],
            f"{seasons_drawn} season row(s) drawn, {apart['skeletons']} "
            f"skeleton(s); « Possédés 0 »: {apart['ownedZero']}, "
            f"« Complétude 0 % »: {apart['completeness']}, "
            f"« manquants » chips: {apart['missing']}; printed: "
            f"{[answer for answer in ASSERTIONS if answer in apart_outside]}")
        journal.check("no JS error on the split-latency walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
