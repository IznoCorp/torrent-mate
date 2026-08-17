"""R77 — a PAGE has one owner at a time, and the container never holds two.

Every surface migrated before this one is an overlay SCREEN with its own path,
drawn inside the React root. A PAGE is a value of `state.page`, drawn into the
legacy `#view` — so for as long as the conversion lasts, that one container is
written by two worlds: the fragment's `render()` for a page it still owns, a
React portal for a page that has migrated.

Two worlds writing one container is where a conversion goes wrong quietly. The
failure is not an exception: it is BOTH pages drawn at once, or a page drawn by
nobody. This rule holds the law that prevents it — the shell empties `#view`
when it takes ownership, the fragment stops writing there for a page it no
longer owns, and handing back needs nothing because the fragment's own write
removes what React left.
"""
import asyncio
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

# The pages the shell owns today. A page absent here is one the fragment still
# draws, and the rule holds that too — it is the other half of the law.
SHELL_OWNED = ["sys", "maint", "cfg", "arr"]
LEGACY_OWNED = ["lib", "acq"]

READ = """()=>{
  const view = document.querySelector('#view');
  if (!view) return {absent: true};
  return {
    children: view.children.length,
    roots: [...view.children].map((element) => element.className),
    elements: view.querySelectorAll('*').length,
    text: view.textContent.replace(/\\s+/g,' ').trim().length,
  };}"""


async def main():
    journal = Journal("R77 — one owner per page, and no residue")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # (a) A migrated page is drawn, and drawn ONCE.
        for identifier in SHELL_OWNED:
            await page.evaluate(f"()=>window.__magasin.ecrire({{page: {identifier!r}}})")
            await page.evaluate("()=>window.__referentiel.render()")
            await page.wait_for_timeout(300)
            seen = await page.evaluate(READ)
            journal.check(
                f"the shell-owned page « {identifier} » is drawn, once",
                seen.get("children") == 1 and seen.get("elements", 0) > 20
                and seen.get("text", 0) > 200,
                str(seen)[:140])

        # (b) A page the fragment still owns is drawn exactly as before.
        for identifier in LEGACY_OWNED:
            await page.evaluate(f"()=>window.__magasin.ecrire({{page: {identifier!r}}})")
            await page.evaluate("()=>window.__referentiel.render()")
            await page.wait_for_timeout(300)
            seen = await page.evaluate(READ)
            journal.check(
                f"the legacy-owned page « {identifier} » still draws",
                seen.get("children", 0) >= 1 and seen.get("elements", 0) > 5,
                str(seen)[:140])

        # (c) THE RESIDUE HOLD, and what it must NOT assume: pages emit
        # different numbers of root elements (« lib » emits four, « acq » two,
        # « sys » one), so « exactly one root » is not the law. The law is that
        # a page looks the SAME whichever page preceded it — residue is markup
        # that survives a handover, and it shows up as a page carrying more
        # than it emits. Each page below is reached from two different
        # predecessors, once across each world's boundary.
        walk = ["lib", "sys", "lib", "arr", "sys", "arr", "acq", "sys", "acq",
                "maint", "lib", "maint", "cfg", "maint", "sys", "cfg", "arr",
                "cfg", "sys", "cfg", "lib", "arr", "acq", "arr"]
        signatures: dict[str, set[str]] = {}
        residue = []
        absent = []
        for identifier in walk:
            await page.evaluate(f"()=>window.__magasin.ecrire({{page: {identifier!r}}})")
            await page.evaluate("()=>window.__referentiel.render()")
            await page.wait_for_timeout(300)
            seen = await page.evaluate(READ)
            if seen.get("absent"):
                absent.append(identifier)
            signature = f"{seen.get('children')} roots {seen.get('roots')}"
            signatures.setdefault(identifier, set()).add(signature)
            if len(signatures[identifier]) > 1:
                residue.append(f"{identifier}: {sorted(signatures[identifier])}")
        # THE DENOMINATOR, because this hold asserts a constancy: a walk that
        # visited each page once has nothing to compare, and a `#view` that
        # disappeared would make every signature the same word and pass. Both
        # are held before the constancy means anything.
        compared = {name: len(hits) for name, hits in signatures.items()}
        walked_twice = [name for name in signatures
                        if walk.count(name) < 2]
        journal.check(
            "every page in the walk was reached from two different predecessors",
            not walked_twice and not absent,
            f"never re-entered: {walked_twice}" if walked_twice
            else f"#view was absent on: {absent}" if absent
            else ", ".join(f"{name}×{walk.count(name)}" for name in signatures))
        journal.check(
            "a page draws the same whichever world it was reached from",
            not residue,
            str(residue) or "; ".join(
                f"{name}={next(iter(signatures[name]))}" for name in compared))

        # EVERY tap goes through this, and it answers three different questions
        # with three different words. A control that is ABSENT is the defect the
        # holds below are written for; a control that is present but INERT —
        # disabled, or covered by a toast — would otherwise hold Playwright's
        # actionability wait open for thirty seconds and kill the script, which
        # reads as a broken rule rather than a named defect. Both come back as a
        # verdict, never as an exception.
        async def tap(selector):
            """Taps the first match; returns why not when it does not tap."""
            control = page.locator(selector).first
            if not await control.count():
                return "absent"
            try:
                await control.click(timeout=4000)
            except PlaywrightTimeoutError:
                return "present but not tappable"
            await page.wait_for_timeout(360)
            return None

        # (c-bis) THE DELEGATION STILL READS WHAT REACT EMITS. A migrated page
        # keeps emitting the `data-*` attributes the document-level click
        # handler acts on — and nothing else in the suite drives them: R67
        # reaches Maintenance through `applyState`, never through a tap. So the
        # wave that moves the emitter owes these two holds, or a component that
        # stopped writing one of those attributes would break the page while
        # every existing rule stayed green.
        await page.evaluate("()=>window.__magasin.ecrire({page: 'maint', maintRub: null})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        refused = await tap("#view .topic[data-maintrub='scan']")
        opened = await page.evaluate("""()=>({
          rubrique: window.__magasin.lire().etat.maintRub,
          back: !!document.querySelector('#view .crossref[data-maintrub=""]'),
          rows: document.querySelectorAll('#view .flux .fx').length,
        })""")
        journal.check(
            "a real tap on a rubric row opens that rubric",
            not refused and opened["rubrique"] == "scan" and opened["back"]
            and opened["rows"] > 0,
            str(opened) if not refused else f"data-maintrub='scan' {refused}")

        # Looked up rather than clicked blind, and identified: the panel must be
        # THAT command's. « a panel opened » is satisfied by
        # every row opening the same one, which is the defect a page whose rows
        # all carry one id would have.
        wanted = await page.evaluate("""()=>{
          const row = document.querySelector('#view .flux .fx .fw[data-maintact]');
          if (!row) return null;
          const id = row.dataset.maintact;
          const action = window.__referentiel.MAINT_ACTIONS.find((x) => x.id === id);
          return {id, title: action ? action.l : null};}""")
        refused = (await tap("#view .flux .fx .fw[data-maintact]")
                   if wanted else "absent")
        panel = await page.evaluate("""()=>({
          open: !!document.querySelector('#sheet.open'),
          title: (document.querySelector('#sheet .sheettitle')||{}).textContent || null,
        })""")
        journal.check(
            "and a real tap on a command row opens THAT command's panel",
            not refused and panel["open"] and wanted
            and panel["title"] == wanted["title"],
            f"{wanted} → {panel}" if not refused
            else f"data-maintact {refused}")
        await page.evaluate("()=>window.__panneau.fermer()")
        await page.wait_for_timeout(300)

        # (c-ter) THE SAME DEBT, on the page that carries the most of it. The
        # settings page emits seven attributes the document-level delegation
        # acts on, and R60 reaches every one of its states through
        # `window.__go(...)` — never through a tap. So the whole delegation
        # path was unmeasured: a component that stopped writing
        # `data-rubrique` would leave a page of rows nothing opens, with R60
        # entirely green. Each control is LOOKED UP before it is tapped: a
        # click on a selector that matches nothing times out and crashes the
        # script, which reads as a broken rule instead of a named defect.
        await page.evaluate(
            "()=>{REG_ETAT.rubrique = null; REG_ETAT.q = '';"
            " REG_ETAT.modifs.clear(); REG_ETAT.redemarrage = false;}")
        await page.evaluate("()=>window.__magasin.ecrire({page: 'cfg'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)

        topic = await page.evaluate(
            "()=>{const b = document.querySelector('#view .topic[data-rubrique]');"
            " return b ? b.dataset.rubrique : null;}")
        refused = await tap("#view .topic[data-rubrique]") if topic else "absent"
        opened = await page.evaluate("""()=>({
          rubrique: REG_ETAT.rubrique,
          rows: document.querySelectorAll('#view .settingrow[data-reglage]').length,
        })""")
        journal.check(
            "a real tap on a settings topic opens THAT topic",
            not refused and opened["rubrique"] == topic and opened["rows"] > 0,
            f"{topic} → {opened}" if not refused else f"data-rubrique {refused}")

        # The row's own identity, compared against the field the panel opens on:
        # « a panel opened » would be satisfied by every row opening the same
        # one. The panel's META carries the identity for EVERY type, while
        # `data-champ` exists only for the types that offer a field — a
        # structure or a list would fail this hold for the wrong reason.
        identity = await page.evaluate(
            "()=>{const b = document.querySelector('#view .settingrow[data-reglage]');"
            " return b ? b.dataset.reglage : null;}")
        refused = (await tap("#view .settingrow[data-reglage]")
                   if identity else "absent")
        edited = await page.evaluate("""()=>{
          const field = document.querySelector('#sheetin [data-champ]');
          const meta = document.querySelector('#sheet .sheetmeta');
          return {open: !!document.querySelector('#sheet.open'),
                  field: field ? field.dataset.champ : null,
                  meta: meta ? meta.textContent.trim() : null};}""")
        named = identity and edited["meta"] and all(
            part in edited["meta"] for part in identity.split(":"))
        journal.check(
            "and a real tap on a setting opens THAT setting",
            not refused and edited["open"] and bool(named)
            and (edited["field"] is None or edited["field"] == identity),
            f"{identity} → {edited}" if not refused else f"data-reglage {refused}")
        await page.evaluate("()=>window.__panneau.fermer()")
        await page.wait_for_timeout(300)

        # The save bar is the page's second host, and its button is the only
        # control in the prototype that WRITES. The change is staged through
        # the legacy's own verb rather than typed, because what is held here is
        # the tap, not the field.
        staged = await page.evaluate("""()=>{
          const setting = window.__referentiel.tousLesReglages()
            .find((x) => x.type === 'booleen');
          if (!setting) return null;
          const id = window.__referentiel.reglageId(setting);
          window.__referentiel.modifierReglage(id, !setting.brut);
          window.__referentiel.render();
          return id;}""")
        await page.wait_for_timeout(300)
        refused = (await tap("#savebar [data-enregistrer]") if staged else "absent")
        saved = await page.evaluate(
            "()=>({pending: REG_ETAT.modifs.size, restart: REG_ETAT.redemarrage,"
            " bar: !!document.querySelector('#savebar')})")
        journal.check(
            "a real tap on the save bar files the change and asks for a restart",
            not refused and saved["pending"] == 0 and saved["restart"]
            and not saved["bar"],
            str(saved) if not refused else f"data-enregistrer {refused}")

        await page.evaluate("()=>{REG_ETAT.rubrique = null;}")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        refused = await tap("#view [data-redemarrer]")
        # The restart offer only exists because the save above raised it, so a
        # lost `data-enregistrer` reaches this hold as « absent ». The detail
        # says what was MEASURED either way — a line that reads « restart
        # cleared » under a FAIL tells a reader the opposite of what happened.
        restart_left = await page.evaluate("()=>REG_ETAT.redemarrage")
        journal.check(
            "and a real tap on the restart offer takes it",
            not refused and not restart_left,
            f"redemarrage={restart_left}" if not refused
            else f"data-redemarrer {refused} (the save above raises it)")

        refused = await tap("#view .topic[data-rubrique='secrets']")
        listed = await page.evaluate(
            "()=>({rubrique: REG_ETAT.rubrique,"
            " rows: document.querySelectorAll('#view [data-secret]').length})")
        journal.check(
            "a real tap on the secrets topic lists the secrets",
            not refused and listed["rubrique"] == "secrets" and listed["rows"] > 0,
            str(listed) if not refused else f"data-rubrique='secrets' {refused}")

        # THAT secret's panel: the key it carries has to appear in the panel it
        # opened, or every secret row opening one panel would pass.
        key = await page.evaluate(
            "()=>{const b = document.querySelector('#view [data-secret]');"
            " return b ? b.dataset.secret : null;}")
        await page.evaluate("()=>window.__panneau.fermer()")
        await page.wait_for_timeout(250)
        refused = await tap("#view [data-secret]") if key else "absent"
        sheet = await page.evaluate("""()=>({
          open: !!document.querySelector('#sheet.open'),
          text: (document.querySelector('#sheet')||{}).textContent || '',
        })""")
        journal.check(
            "and a real tap on a secret opens THAT secret's panel",
            not refused and sheet["open"] and bool(key) and key in sheet["text"],
            f"{key} → open={sheet['open']}, named={bool(key) and key in sheet['text']}"
            if not refused else f"data-secret {refused}")
        await page.evaluate("()=>window.__panneau.fermer()")
        await page.wait_for_timeout(300)

        # The search's clear button exists only while something is searched
        # for, so the query is staged first — the tap is what is held.
        await page.evaluate(
            # french-ok: a French search WORD, typed into the app's own search
            # — the data a French interface is searched with, not a name.
            "()=>{REG_ETAT.rubrique = null; REG_ETAT.q = 'espace';}")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        refused = await tap("#view [data-qreg]")
        cleared = await page.evaluate(
            "()=>({q: REG_ETAT.q,"
            " clear: !!document.querySelector('#view [data-qreg]')})")
        journal.check(
            "a real tap on the search's cross clears the search",
            not refused and cleared["q"] == "" and not cleared["clear"],
            str(cleared) if not refused else f"data-qreg {refused}")

        # And the one row that leaves the page entirely: the quality profile is
        # a ROUTE, so what proves the tap landed is the address — the address
        # the ROW NAMED, and only if it was not already there before the tap.
        profile = await page.evaluate(
            "()=>{const b = document.querySelector('#view .topic[data-profil]');"
            " return b ? b.dataset.profil : null;}")
        before_address = await page.evaluate("()=>location.pathname")
        refused = await tap("#view .topic[data-profil]") if profile else "absent"
        await page.wait_for_timeout(400)
        address = await page.evaluate("()=>location.pathname")
        journal.check(
            "a real tap on the quality-profile row goes to ITS address",
            not refused and profile is not None
            and address == f"/profil/{profile}" and before_address != address,
            f"{before_address} → {address} for data-profil={profile!r}"
            if not refused else f"data-profil {refused}")
        await page.evaluate("()=>window.__pont.retour()")
        await page.wait_for_timeout(420)

        # (c-quater) LEAVING A MIGRATED PAGE MUST NOT KILL THE SHELL. This is
        # the half of the ownership law no hold covered, and it cost a real
        # defect: the settings page's save bar is a React portal into `#device`,
        # and the legacy still removed that node by hand on the way out — so
        # React, unmounting the portal a microtask later, removed a node that
        # was no longer its container's child. The exception is not a page
        # error: React reports it on the CONSOLE, the root tears down, and
        # every migrated page and screen is dead until a reload. Nothing here
        # is hypothetical — the walk below is exactly the one that did it.
        console_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text)
                if message.type == "error" else None)
        await page.evaluate("()=>{REG_ETAT.rubrique = null; REG_ETAT.q = '';"
                            " REG_ETAT.modifs.clear(); REG_ETAT.redemarrage = false;}")
        await page.evaluate("()=>window.__magasin.ecrire({page: 'cfg'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        await page.evaluate("""()=>{
          const setting = window.__referentiel.tousLesReglages()
            .find((x) => x.type === 'booleen');
          window.__referentiel.modifierReglage(
            window.__referentiel.reglageId(setting), !setting.brut);
          window.__referentiel.render();}""")
        await page.wait_for_timeout(300)
        raised = await page.evaluate("()=>!!document.querySelector('#savebar')")
        await page.evaluate("()=>{window.__magasin.ecrire({page: 'lib'});"
                            " window.__referentiel.render();}")
        await page.wait_for_timeout(500)
        await page.evaluate("()=>{window.__magasin.ecrire({page: 'cfg'});"
                            " window.__referentiel.render();}")
        await page.wait_for_timeout(500)
        returned = await page.evaluate("""()=>({
          roots: [...document.querySelector('#view').children].map((x) => x.className),
          rows: document.querySelectorAll('#view .topic[data-rubrique]').length,
        })""")
        journal.check(
            "leaving a migrated page with an unsaved change, and coming back, "
            "leaves the shell alive",
            raised and returned["roots"] == ["body"] and returned["rows"] > 0
            and not console_errors,
            f"bar raised: {raised}; back: {returned}; console errors: "
            + (str(console_errors[:1])[:160] if console_errors else "none"))

        # (c-quinquies) ARRIVÉES' OWN DELEGATION. This page carries the first
        # migrated control that MUTATES: the pilot's bar writes nothing itself,
        # it emits `data-pipe` and the document-level handler does the writing.
        # R66 drives the page through the store and never through a tap, so the
        # bar's three states were emitted by a component nothing had ever
        # clicked.
        await page.evaluate("()=>window.__magasin.ecrire({page: 'arr',"
                            " phase: 'prete', pipe: 'repos'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(320)
        refused = await tap("#view .pipeline [data-pipe='lancer']")
        started = await page.evaluate(
            "()=>({pipe: window.__magasin.lire().etat.pipe,"
            " controls: [...document.querySelectorAll('#view [data-pipe]')]"
            ".map((x) => x.dataset.pipe)})")
        journal.check(
            "a real tap on « lancer » starts the pipeline",
            not refused and started["pipe"] == "encours"
            and "arreter" in started["controls"],
            str(started) if not refused else f"data-pipe='lancer' {refused}")

        # DOIT-4, the one the bar exists for: asked DURING a run, another pass
        # is QUEUED — visibly — never refused with « busy, try again ».
        refused = await tap("#view .pipeline [data-pipe='lancer']")
        queued = await page.evaluate(
            "()=>({pipe: window.__magasin.lire().etat.pipe,"
            " live: !!document.querySelector('#view .pipeline .live')})")
        journal.check(
            "and asked again DURING a run, the next pass is queued, not refused",
            not refused and queued["pipe"] == "file" and queued["live"],
            str(queued) if not refused else f"data-pipe='lancer' {refused}")

        refused = await tap("#view .pipeline [data-pipe='arreter']")
        stopped = await page.evaluate(
            "()=>window.__magasin.lire().etat.pipe")
        journal.check(
            "and a real tap on « arrêter » stops it",
            not refused and stopped == "repos",
            f"pipe={stopped}" if not refused else f"data-pipe='arreter' {refused}")

        # The crossref leaves the page entirely, and it is the page's own
        # `data-go` — the attribute B-024's containment argument counts.
        await page.evaluate("()=>window.__magasin.ecrire({page: 'arr',"
                            " phase: 'prete', pipe: 'repos', scen: 'charge'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(320)
        refused = await tap("#view .crossref[data-go='acq']")
        landed = await page.evaluate("()=>window.__magasin.lire().etat.page")
        journal.check(
            "a real tap on the crossref lands on Acquisition",
            not refused and landed == "acq",
            f"page={landed}" if not refused else f"data-go='acq' {refused}")

        # (d-bis) NO RULE DRIVES A PAGE BY MUTATING THE ENGINE'S ALIAS.
        # `state` is a module-global alias onto the store's CURRENT object, so
        # `state.page = "arr"` mutates that object IN PLACE: its identity never
        # changes, nothing React subscribes to moves, and the page keeps drawing
        # whatever was there before. Measured on the wave that migrated
        # Arrivées — the store said « arr », `#view` held the acquisition page's
        # roots, and the rule that hit it reported a MISSING BUTTON rather than
        # a stale page, which is what makes this worth a source-level hold. The
        # door is the store (`window.__magasin.ecrire`), or `applyState` /
        # `__go`, which go through it.
        scripts = sorted(pathlib.Path(__file__).resolve().parent.glob("*.py"))
        writers = []
        for script in scripts:
            for number, line in enumerate(
                    script.read_text(encoding="utf-8").split("\n"), 1):
                # A COMMENT is not a drive — this hold's own explanation
                # above says the forbidden thing in order to name it.
                if line.lstrip().startswith("#"):
                    continue
                if re.search(r"(?<![.\w])state\.\w+\s*=(?!=)", line):
                    writers.append(f"{script.name}:{number}")
        journal.check(
            "no rule drives a page by mutating the engine's state alias",
            not writers,
            str(writers) if writers else f"{len(scripts)} scripts read, none does")

        # (d) The handover is the SHELL's: the fragment must not write into a
        # container React holds. Read from the DOCUMENT THE BROWSER RAN, never
        # from the source on disk — every other hold here measures the served
        # copy, and this rule's own mutations disable things in that copy alone,
        # so a source read could stay green over a page that lost the guard.
        # Read as a pattern rather than as a byte-exact line, because reflowing
        # the line changes nothing about the law; and counted, because the guard
        # says nothing about a SECOND, unguarded write elsewhere.
        served = await page.content()
        writes = re.findall(r"[^\n]*view\.innerHTML\s*=[^\n]*", served)
        guarded = [w for w in writes if re.search(r"!\s*found\.shellOwned", w)]
        journal.check(
            "the fragment writes #view only for a page it still owns",
            len(writes) == 1 and len(guarded) == 1,
            f"{len(writes)} write(s) to #view's innerHTML, {len(guarded)} guarded"
            + ("" if len(writes) == 1 else f" — {[w.strip()[:80] for w in writes]}"))

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
