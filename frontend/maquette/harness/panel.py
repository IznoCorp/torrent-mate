"""R56 — ONE bottom panel, and its shape follows the facts it is given.

The card and the tile were each reduced to a single builder taking a descriptor
of facts. The panel had not been: `openSheet` took ready-made markup, so every
surface assembled its own — three head shapes had grown that way, two of them
out of inline styles, which belong to no stylesheet and are therefore exported
nowhere. A second builder had also appeared for « whatever the first does not
recognise », and it offered six buttons of which three led nowhere at all. That
is what a fallback builder becomes: never the one being looked at, so never the
one being fixed.

An envelope guarantees nothing about what it carries. This script checks the
guarantees a builder CAN make:

  · no caller hands markup to the panel;
  · nothing inside a panel is positioned by an inline style;
  · every panel has exactly one heading;
  · every action in a panel has a destination, or says why it has none;
  · a block type nobody declared is refused rather than drawn empty.

The builder and the verb have MOVED: the constructor is the component
`design/src/ui/panel/index.tsx`, and a producer opens a panel by calling
the shell's `window.__panel.open(descripteur)` rather than the engine's own
`openSheet(panneauHTML({…}))`. The two source checks below follow them there.
What they hold is unchanged — one constructor, no second one, and every caller
handing FACTS rather than markup — and the behavioural checks that follow are
untouched: they read the panel as drawn, and a panel is a panel wherever it is
built.

THE BLOCK KINDS ARE NO LONGER A CLOSED SWITCH, and that adds one failure mode
this rule now holds. The two kinds that know a domain — the season matrix and
the setting field — live with those domains and REGISTER themselves with the
panel's contract, so the panel imports no feature. A registration has three
ends: the kind declared in `PanelBlockMap`, the `registerBlock` call that says
what draws it, and — for a kind outside `ui/panel` — the boot import that makes
that file evaluate at all. Nothing imports a block module otherwise: a panel is
opened by a legacy producer through `window.__panel`, never by a component
holding a reference to the block. Two of the three ends present is a panel that
throws on a kind it declares, and it throws where the PRODUCER wrote it, far
from the file that forgot.
"""
import asyncio
import pathlib
import re

from common import PHONE, PROTOTYPE, Journal, design_source, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The file that boots the application, relative to `design/src`. This rule
# reads it to answer « does anything make this block's module evaluate? », and
# that can only be answered in the file that starts everything. It is named
# once, here: read inline, a move of the shell crashes this rule instead of
# adjusting it — which is exactly what happened the day the shell moved into
# `app/`, and the contract tier does not run this rule, so only the full
# suite before the merge said so.
BOOT_FILE = "app/shell.tsx"

# What the boot logs when an addressed panel was accepted and then failed to
# open. A value the address model REFUSES never reaches the opener, so this
# text appearing at all is a subject that got through without being held.
REOPEN_CRASH = "reopening the addressed panel failed"

# The medium whose SCREEN a panel is opened over. The screen's own address is
# derived from the running application rather than written here — it is keyed
# on a provider id — but the title is the one the fixture holds.
SHEET_TITLE = "Silo (2023)"
# The same medium as the follow catalogue names it: a screen and a follow are
# two surfaces onto one thing, and they do not spell it the same way.
FOLLOW_TITLE = "Silo"

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


# Every panel this interface can open, and how to reach it without knowing
# which screen draws which.
PANELS = [
    ("complete follow", "followsheet-complete", None),
    ("follow with holes", "followsheet-gaps", None),
    ("journey", "sheet-journey", None),
    ("watch", "sheet-more", None),
    ("user menu", "sheet-user", None),
    ("suggestion", "acq-discover", '#view [data-panel^="sug:"]'),
    # The add screen left `#screen` for a real route (`/add`, rendered
    # inside `#coquille`) — its results live under `[data-part="screen"][data-open]` now.
    ("search result", "acq-add-results", '[data-part="screen"][data-open] [data-panel^="add:"]'),
    ("library sort", "lib-grid", "[data-sort]"),
]

# Whether a screen route is mounted and open. Hosted in a triple-quoted string
# rather than escaped inside a double-quoted one: a naming attribute written
# with a backslash is invisible to the markup-contract arm, which reads the
# harness as raw text — the selection would then be held by nothing.
SCREEN_UP = """() => !!document.querySelector('[data-part="screen"][data-open]')"""

READ = """() => {
  const p = document.querySelector('#sheetin');
  const inline = [...p.querySelectorAll('[style]')]
    .map(e => e.tagName + '.' + e.className);
  const actions = [...p.querySelectorAll('[data-part="sheet/action"]')].map(b => ({
    text: (b.textContent || '').trim().slice(0, 34),
    data: Object.keys(b.dataset).length,
    disabled: b.disabled}));
  return {empty: (p.textContent || '').trim().length < 8,
          titles: p.querySelectorAll('[data-part="sheet/title"]').length,
          inline, actions,
          unknown: [...p.querySelectorAll('*')].filter(e =>
            e.tagName === 'DIV' && e.className === '').length};
}"""



def block_kind_ends():
    """Reads the three ends of every panel block kind, from the sources.

    A kind is DECLARED in `PanelBlockMap` — in the contract itself for the
    kinds that know no domain, in a `declare module` augmentation for a
    feature's own. It is REGISTERED by a `registerBlock("kind", …)` call. And
    when it is registered outside `ui/panel`, the file holding that call must
    be IMPORTED at boot, because nothing else imports it.

    Returns:
        `(declared, registered, unimported)` — the set of kinds declared, the
        set registered, and the registering files outside `ui/panel` that the
        shell does not import.
    """
    source_root = ROOT / "design" / "src"
    declared, registered, unimported = set(), set(), []
    boot = (source_root / BOOT_FILE).read_text(encoding="utf-8")
    for file in sorted(source_root.rglob("*.ts")) + sorted(source_root.rglob("*.tsx")):
        text = file.read_text(encoding="utf-8")
        # A `PanelBlockMap` body, wherever it is declared or augmented. Its
        # entries are `kind: {…}` at one level of nesting.
        for body in re.findall(r"interface PanelBlockMap\s*\{(.*?)\n\}", text, re.S):
            declared |= set(re.findall(r"^\s{2,4}([A-Za-z_][A-Za-z0-9_]*)\s*:", body, re.M))
        calls = re.findall(r'registerBlock\(\s*"([^"]+)"', text)
        registered |= set(calls)
        if calls and "ui/panel" not in file.as_posix():
            stem = file.relative_to(source_root).as_posix().rsplit(".", 1)[0]
            # The boot writes its import RELATIVE TO ITSELF, so the needle is
            # built the same way rather than assumed to start at the root.
            up = "../" * (len(pathlib.PurePosixPath(BOOT_FILE).parts) - 1) or "./"
            if f'"{up}{stem}"' not in boot:
                unimported.append(stem)
    return declared, registered, unimported


async def main():
    global _journal
    _journal = Journal("R56 — one single panel")

    # The callers, and the constructor this rule forbids coming back, are
    # both in the engine now — reading the fragment alone would count no
    # callers at all and still call it « no violation ».
    source = design_source()
    component = (ROOT / "design" / "src" / "ui" / "panel" / "index.tsx").read_text()

    # 1. No caller hands markup to the panel. Read on the SOURCE, because that
    #    is where a panel is asked for; the DOM only shows what came out. A
    #    descriptor is an OBJECT — a call opening on anything else (a string, a
    #    template literal, a variable holding ready-made markup) is an envelope.
    # BOTH SPELLINGS, because there are two and they are the same object. The
    # engine imports `panel` from `src/seams.ts` and says `panel.open(`;
    # anything reaching it as a global still says `window.__panel.open(`,
    # and the shell fills the one from the other. Counting only the global form
    # found ZERO callers the day the engine converted its 40 call sites — which
    # is what the « there really are callers » check below exists to notice,
    # and did.
    calls = re.findall(
        r"(?:window\.__)?panel\.open\(\s*(.{0,24})", source, re.S)
    not_facts = [a.strip()[:24] for a in calls if not a.lstrip().startswith("{")]
    check("no caller hands markup", not not_facts,
          " · ".join(not_facts))
    check("there really are callers", len(calls) >= 6, f"{len(calls)} calls")

    # 2. One builder, not two. A fallback builder is the one that rots. The
    #    engine's own builder must not come back either: two constructors are
    #    two head shapes, whichever file they live in.
    check("one panel constructor and no other",
          component.count("export function PanelContent(") == 1
          and "function panneauHTML(" not in source
          and "openDetailSheetLegacy" not in source,
          "openDetailSheetLegacy still present"
          if "openDetailSheetLegacy" in source else
          "panneauHTML is back in the design's sources"
          if "function panneauHTML(" in source else
          f"{component.count('export function PanelContent(')} PanelContent")

    # 3. EVERY DECLARED KIND HAS A RENDERER, AND EVERY RENDERER IS REACHED.
    #    The switch is a registry now, so a kind can be declared with nothing
    #    drawing it, or drawn by a file nothing imports — two spellings of the
    #    same defect, and both throw at the PRODUCER rather than here.
    declared, registered, unimported = block_kind_ends()
    check("every declared block kind has a registered renderer",
          declared == registered,
          f"declared not registered: {sorted(declared - registered)} · "
          f"registered not declared: {sorted(registered - declared)}")
    check("every block module outside ui/panel is imported at boot",
          not unimported, ", ".join(unimported))
    check("there really are block kinds", len(declared) >= 5, f"{len(declared)} kinds")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        empty, styles, titles, without_destination = [], [], [], []
        for name, state_, click in PANELS:
            await pg.evaluate("(s)=>window.__go(s)", state_)
            await pg.wait_for_timeout(320)
            if click:
                await pg.evaluate("(s)=>document.querySelector(s).click()", click)
                await pg.wait_for_timeout(320)
            r = await pg.evaluate(READ)
            if r["empty"]:
                empty.append(name)
            if r["inline"]:
                styles.append(f"{name}: {', '.join(r['inline'][:3])}")
            if r["titles"] != 1:
                titles.append(f"{name} ({r['titles']})")
            for action in r["actions"]:
                if action["data"] == 0 and not action["disabled"]:
                    without_destination.append(f"{name} : « {action['text']} »")

        check(f"the {len(PANELS)} panels open and carry content",
              not empty, ", ".join(empty))
        check("no inline style inside a panel", not styles, " · ".join(styles))
        check("one heading per panel", not titles, ", ".join(titles))
        # The exact defect the fallback builder shipped: a button that looks
        # like an action and answers nothing. A disabled one is allowed — it
        # says of itself that it does nothing yet.
        check("no action without a destination", not without_destination,
              " · ".join(without_destination))

        # 3. A block the builder does not know is REFUSED. Silence here would
        #    draw an empty panel and blame the data.
        refusal = await pg.evaluate("""()=>{try{
            window.__unknownPanel();
            return "no refusal";
          }catch(e){return String(e.message||e);}}""")
        # The message reads ENGLISH because it is a DEVELOPER message: it
        # reaches this harness and a console, never the interface, so the
        # no-French-in-code rule applies to it and the assertion follows it.
        check("an undeclared block is refused",
              "unknown panel block" in refusal, refusal)

        # 4. D1's THREE TIERS, applied. A panel whose subject is stable and
        #    nameable travels in the query and reopens on a reload; a layer
        #    with no subject writes no address at all and Back still closes
        #    it. An index into a list the engine regenerates is deliberately
        #    NOT addressable: after that list moves, such an address would
        #    reopen about something the operator never asked for.
        ctx2 = await b.new_context(**PHONE)
        pg2 = await ctx2.new_page()
        await pg2.goto(PROTOTYPE, wait_until="load")
        await pg2.evaluate("()=>window.__loadingDone?.()")
        await pg2.wait_for_timeout(300)

        await pg2.evaluate("()=>window.openFollowSheet('Silo')")
        await pg2.wait_for_timeout(400)
        addressed = pg2.url
        check("an addressed panel writes its address",
              "panel=follow" in addressed, addressed)

        await pg2.go_back()
        await pg2.wait_for_timeout(400)
        check("and Back takes the address off with the panel",
              "panel=" not in pg2.url and not await pg2.evaluate("()=>window.__panel.isOpen()"),
              pg2.url)
        await ctx2.close()

        # The cold journey: the address alone must reopen it, or it is
        # decoration — written and never read.
        ctx3 = await b.new_context(**PHONE)
        pg3 = await ctx3.new_page()
        cold_errors = []
        pg3.on("pageerror", lambda e: cold_errors.append(str(e)))
        await pg3.goto(addressed, wait_until="load")
        await pg3.evaluate("()=>window.__loadingDone?.()")
        await pg3.wait_for_timeout(600)
        check("a reload at that address reopens the panel",
              await pg3.evaluate("()=>window.__panel.isOpen()"), pg3.url)
        check("no JS error reopening it cold", not cold_errors, str(cold_errors))
        await ctx3.close()

        # AN ADDRESS IS TYPED, PASTED AND KEPT FOR MONTHS, so the panel
        # parameter is the one part of an address the interface must be able to
        # DECLINE. Three shapes of refusal, and the same answer to all three:
        # the page underneath, with the parameter taken off — never a panel
        # built out of the value itself. The engine's producers answer for
        # anything they are handed (a medium nobody holds still gets a panel,
        # which is the right answer for the door inside the application), so
        # what is read here is that the URL door asks a question first.
        async def cold(query):
            """Opens the acquisition page cold at one panel query.

            Returns:
                `(url, open, title, errors)` — the address settled on, whether
                a panel is up, the title the panel descriptor names, and any
                JS error the load raised. A refused value is refused BEFORE the
                opener runs, so the boot's own « reopening the addressed panel
                failed » counts as one of those errors: a subject the opener
                chokes on is a subject that was never held.
            """
            context = await b.new_context(**PHONE)
            page = await context.new_page()
            raised = []
            page.on("pageerror", lambda e: raised.append(str(e)))

            def note_reopen_crash(message):
                """Keeps the boot's reopen crash beside the page errors."""
                if REOPEN_CRASH in message.text:
                    raised.append(message.text)

            page.on("console", note_reopen_crash)
            await page.goto(PROTOTYPE + "acquisition" + query, wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            await page.wait_for_timeout(600)
            seen = (
                page.url,
                await page.evaluate("()=>window.__panel.isOpen()"),
                await page.evaluate(
                    "()=>(window.__store.read().state.panelDescriptor||{}).title||''"),
                raised,
            )
            await context.close()
            return seen

        url, is_open, title, raised = await cold("?panel=follows")
        check("a panel value that is not kind:subject opens nothing",
              not is_open and "panel=" not in url and not raised,
              f"{url} · title={title!r} · {raised}")

        url, is_open, title, raised = await cold("?panel=nobody:Silo")
        check("a panel kind the table does not carry opens nothing",
              not is_open and "panel=" not in url and not raised,
              f"{url} · title={title!r} · {raised}")

        # The one that fabricated a medium: the producer's synthesised fallback
        # was reachable FROM AN ADDRESS, so any title at all opened a panel
        # describing a series this library has never heard of.
        unknown = "Ceci N'Existe Pas"  # french-ok: a title no source holds
        url, is_open, title, raised = await cold(
            "?panel=follow:" + unknown.replace(" ", "%20").replace("'", "%27"))
        check("a subject no source holds opens nothing, and names nothing",
              not is_open and "panel=" not in url and title != unknown and not raised,
              f"{url} · title={title!r} · {raised}")

        # AND « HELD » IS EXACT MEMBERSHIP, which the value above cannot show:
        # it misses both of the ways a title used to be accepted without being
        # in any of the sources the opener matches. The media-sheet lookup was
        # once consulted here, and it is deliberately forgiving — it answers on
        # a prefix of more than six characters, and, reading a plain object by
        # bracket, it answers for every name `Object.prototype` carries. Each
        # of the four below is refused by exact membership and by nothing else.
        for subject, wanted in (
            ("American", "a subject resolved only by a sheet's prefix opens nothing"),
            ("constructor",
             "a subject resolved only through Object.prototype opens nothing"),
            ("Silo (2023)",
             "a sheet key whose medium is followed under another title opens nothing"),
            ("silo", "a subject that differs from a followed title by case opens nothing"),
        ):
            url, is_open, title, raised = await cold(
                "?panel=follow:" + subject.replace(" ", "%20"))
            check(wanted,
                  not is_open and "panel=" not in url and title != subject and not raised,
                  f"{url} · title={title!r} · {raised}")

        # THE GUARD IS NOT THE PANEL'S TO SPEND. Reopened cold, the panel used
        # to push its layer entry BEFORE the boot wrote the exit guard, so the
        # guard's marker landed on the panel's own entry: closing the panel
        # spent it, `panel=` never left the address, and the « one more back to
        # leave » warning could not arm at all. One Back closes the panel and
        # nothing else; the SECOND reaches the guard.
        ctx5 = await b.new_context(**PHONE)
        pg5 = await ctx5.new_page()
        walk_errors = []
        pg5.on("pageerror", lambda e: walk_errors.append(str(e)))
        await pg5.goto(PROTOTYPE + f"acquisition?panel=follow:{FOLLOW_TITLE}",
                       wait_until="load")
        await pg5.evaluate("()=>window.__loadingDone?.()")
        await pg5.wait_for_timeout(600)
        check("a valid subject reopens the panel it names",
              await pg5.evaluate("()=>window.__panel.isOpen()")
              and await pg5.evaluate(
                  "()=>(window.__store.read().state.panelDescriptor||{}).title") == "Silo",
              pg5.url)
        await pg5.go_back()
        await pg5.wait_for_timeout(450)
        check("the first Back closes it and spends no guard",
              not await pg5.evaluate("()=>window.__panel.isOpen()")
              and "panel=" not in pg5.url
              and pg5.url.endswith("/acquisition")
              and not await pg5.evaluate("()=>window.armedExit"),
              f"{pg5.url} · armedExit={await pg5.evaluate('()=>window.armedExit')}")

        # AND HISTORY GOES BOTH WAYS. The Back leaves the panel's entry AHEAD,
        # and stepping forward onto it used to land on an address naming a
        # panel with nothing open — invariant 1 broken in the one direction
        # nothing walked, and a reload at that address brought back what the
        # gesture had not. The entry names the panel, so the panel comes back.
        await pg5.go_forward()
        await pg5.wait_for_timeout(500)
        check("a Forward onto the panel's own entry opens it again",
              await pg5.evaluate("()=>window.__panel.isOpen()")
              and await pg5.evaluate(
                  "()=>(window.__store.read().state.panelDescriptor||{}).title")
              == FOLLOW_TITLE
              and "panel=" in pg5.url,
              f"{pg5.url} · panel={await pg5.evaluate('()=>window.__panel.isOpen()')}")
        await pg5.go_back()
        await pg5.wait_for_timeout(500)
        check("and the Back after it closes the panel and takes its address off",
              not await pg5.evaluate("()=>window.__panel.isOpen()")
              and "panel=" not in pg5.url
              and pg5.url.endswith("/acquisition"),
              f"{pg5.url} · panel={await pg5.evaluate('()=>window.__panel.isOpen()')}")
        check("no JS error walking the panel's entry forward and back",
              not walk_errors, str(walk_errors))

        await pg5.go_back()
        await pg5.wait_for_timeout(450)
        check("and the second Back is the one that reaches the guard",
              bool(await pg5.evaluate("()=>window.armedExit")),
              f"{pg5.url} · armedExit={await pg5.evaluate('()=>window.armedExit')}")
        await ctx5.close()

        # A PANEL OVER A SCREEN HANGS OFF THE SCREEN'S OWN PATH. The panel's
        # address used to be composed from the page UNDERNEATH, which under a
        # screen is the home page — so opening a panel over the media sheet
        # pushed the home page's path, the route stopped matching, and the
        # screen the operator had linked to unmounted behind the panel. Both
        # doors are read: the address, and the in-app open.
        # DERIVED from the running application, never written down: the media
        # sheet's address is keyed on a provider id, and a constant nothing
        # verifies against its source rots the day the fixture moves.
        ctx_ids = await b.new_context(**PHONE)
        pg_ids = await ctx_ids.new_page()
        await pg_ids.goto(PROTOTYPE, wait_until="load")
        await pg_ids.evaluate("()=>window.__loadingDone?.()")
        await pg_ids.wait_for_timeout(300)
        ids = await pg_ids.evaluate(f"()=>window.addressIdsFor({SHEET_TITLE!r})")
        await ctx_ids.close()
        check("the media sheet's own address ids are resolvable",
              bool(ids and ids.get("provider") and ids.get("id")), str(ids))
        screen_path = f"/media/{(ids or {}).get('provider')}/{(ids or {}).get('id')}"

        ctx6 = await b.new_context(**PHONE)
        pg6 = await ctx6.new_page()
        screen_errors = []
        pg6.on("pageerror", lambda e: screen_errors.append(str(e)))
        await pg6.goto(PROTOTYPE.rstrip("/") + screen_path + f"?panel=follow:{FOLLOW_TITLE}",
                       wait_until="load")
        await pg6.evaluate("()=>window.__loadingDone?.()")
        await pg6.wait_for_timeout(650)
        check("a cold panel over a screen leaves the screen standing",
              await pg6.evaluate("()=>window.__panel.isOpen()")
              and await pg6.evaluate(
                  SCREEN_UP),
              f"{pg6.url} · panel={await pg6.evaluate('()=>window.__panel.isOpen()')}")
        check("and its address is the screen's path, with the panel in the query",
              screen_path in pg6.url and "panel=" in pg6.url, pg6.url)
        await pg6.go_back()
        await pg6.wait_for_timeout(500)
        check("one Back closes the panel and the screen is still there",
              not await pg6.evaluate("()=>window.__panel.isOpen()")
              and await pg6.evaluate(
                  SCREEN_UP)
              and pg6.url.endswith(screen_path),
              f"{pg6.url} · panel={await pg6.evaluate('()=>window.__panel.isOpen()')}")
        check("no JS error opening a panel over a screen cold",
              not screen_errors, str(screen_errors))
        await ctx6.close()

        # The same mechanism, through the door inside the application: the
        # sheet is opened by a verb, not by an address, and the panel opened
        # over it must leave it exactly as it found it.
        ctx7 = await b.new_context(**PHONE)
        pg7 = await ctx7.new_page()
        await pg7.goto(PROTOTYPE, wait_until="load")
        await pg7.evaluate("()=>window.__loadingDone?.()")
        await pg7.wait_for_timeout(300)
        await pg7.evaluate(f"()=>window.__screens.mediaSheet({SHEET_TITLE!r})")
        await pg7.wait_for_timeout(500)
        await pg7.evaluate(f"()=>window.openFollowSheet({FOLLOW_TITLE!r})")
        await pg7.wait_for_timeout(500)
        check("a panel opened in-app over a screen leaves the screen standing",
              await pg7.evaluate("()=>window.__panel.isOpen()")
              and await pg7.evaluate(
                  SCREEN_UP)
              and screen_path in pg7.url and "panel=" in pg7.url,
              f"{pg7.url} · panel={await pg7.evaluate('()=>window.__panel.isOpen()')}")
        await ctx7.close()

        # AND NEVER OVER AN ADDRESS NOBODY SERVES. The not-found page is not a
        # state anyone links to, so a panel asked for over it is asked for over
        # nothing: it is declined like any other value the interface cannot
        # honour, and the parameter comes off the address.
        ctx8 = await b.new_context(**PHONE)
        pg8 = await ctx8.new_page()
        await pg8.goto(PROTOTYPE + f"nimportequoi?panel=follow:{FOLLOW_TITLE}",
                       wait_until="load")
        await pg8.evaluate("()=>window.__loadingDone?.()")
        await pg8.wait_for_timeout(650)
        check("a panel over an address nobody serves opens nothing",
              not await pg8.evaluate("()=>window.__panel.isOpen()")
              and "panel=" not in pg8.url
              and pg8.url.endswith("/nimportequoi"),
              f"{pg8.url} · panel={await pg8.evaluate('()=>window.__panel.isOpen()')}")
        await ctx8.close()

        # A menu has no subject, so it is tier 3: no address, Back still shuts
        # it. Reading the OTHER side of the same rule is what stops « every
        # layer writes an address » passing as « the tiers are applied ».
        ctx4 = await b.new_context(**PHONE)
        pg4 = await ctx4.new_page()
        await pg4.goto(PROTOTYPE, wait_until="load")
        await pg4.evaluate("()=>window.__loadingDone?.()")
        await pg4.wait_for_timeout(300)
        before = pg4.url
        await pg4.evaluate("()=>window.openUserSheet()")
        await pg4.wait_for_timeout(400)
        check("a transient layer writes NO address",
              pg4.url == before and await pg4.evaluate("()=>window.__panel.isOpen()"),
              f"{before} -> {pg4.url}")
        await pg4.go_back()
        await pg4.wait_for_timeout(400)
        check("and Back still closes it",
              not await pg4.evaluate("()=>window.__panel.isOpen()"), pg4.url)
        await ctx4.close()

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
