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

from common import Journal, design_source, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

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
    boot = (source_root / "shell.tsx").read_text(encoding="utf-8")
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
            if f'"./{stem}"' not in boot:
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

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
