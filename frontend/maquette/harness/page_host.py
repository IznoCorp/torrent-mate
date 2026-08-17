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
from common import PROTOTYPE, Journal, open_page

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

# The pages the shell owns today. A page absent here is one the fragment still
# draws, and the rule holds that too — it is the other half of the law.
SHELL_OWNED = ["sys", "maint", "cfg", "arr", "lib"]
LEGACY_OWNED = ["acq"]

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
            # « ONCE » is the residue hold's business, and it measures it
            # across predecessors. What this one holds is that the page is
            # DRAWN — and it may not assume a root count: the Médiathèque emits
            # four siblings where the other four emit one, which is why the
            # host stopped supplying a root element of its own.
            journal.check(
                f"the shell-owned page « {identifier} » is drawn",
                seen.get("children", 0) >= 1 and seen.get("elements", 0) > 20
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

        # (c-sexies) THE MÉDIATHÈQUE'S OWN DELEGATION. This page carries more
        # of it than any other — the lens, the category, the view mode, the
        # selection, the deletion and the search's cross — and R63 drives it
        # through the store, never through a tap.
        await page.evaluate("()=>window.__reset()")
        await page.evaluate("()=>window.__magasin.ecrire({page: 'lib', phase: 'prete',"
                            " libLens: 'cat', libMode: 'list', libCat: 'all', q: ''})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)

        refused = await tap("#view .seg [data-lens='rec']")
        lens = await page.evaluate("""()=>({
          lens: window.__magasin.lire().etat.libLens,
          drawn: (document.querySelector('#view .countline')||{}).textContent || '',
        })""")
        journal.check(
            "a real tap on a lens opens THAT lens",
            not refused and lens["lens"] == "rec" and "index" in lens["drawn"],
            str(lens)[:120] if not refused else f"data-lens {refused}")

        await page.evaluate("()=>window.__magasin.ecrire({libLens: 'cat'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)
        wanted = await page.evaluate(
            "()=>{const b = [...document.querySelectorAll('#view .pill[data-cat]')]"
            ".find((x) => x.dataset.cat !== 'all'); return b ? b.dataset.cat : null;}")
        refused = (await tap(f"#view .pill[data-cat='{wanted}']") if wanted else "absent")
        chosen = await page.evaluate(
            "()=>({cat: window.__magasin.lire().etat.libCat,"
            " pressed: (document.querySelector('#view .pill[aria-pressed=true]')||{})"
            ".dataset?.cat || null})")
        journal.check(
            "a real tap on a category pill filters by THAT category",
            not refused and chosen["cat"] == wanted and chosen["pressed"] == wanted,
            f"{wanted} → {chosen}" if not refused else f"data-cat {refused}")

        refused = await tap("#view [data-lmode='grid']")
        mode = await page.evaluate("""()=>({
          mode: window.__magasin.lire().etat.libMode,
          drawn: (document.querySelector('#libitems')||{}).className || null,
        })""")
        journal.check(
            "a real tap on the view switch really switches the view",
            not refused and mode["mode"] == "grid" and mode["drawn"] == "grid",
            str(mode) if not refused else f"data-lmode {refused}")
        await page.evaluate("()=>window.__magasin.ecrire({libMode: 'list', libCat: 'all'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)

        # The selection bar is the FRAGMENT's node in `#device`: tapping the
        # entry proves the seam still works across the two worlds.
        refused = await tap("#view [data-selmode='1']")
        selecting = await page.evaluate("""()=>({
          mode: !!window.__magasin.lire().etat.selMode,
          bar: !!document.querySelector('#device .selbar'),
          rows: document.querySelectorAll('#libitems .selrow[data-tile]').length,
        })""")
        journal.check(
            "a real tap on « sélectionner » opens selection, bar included",
            not refused and selecting["mode"] and selecting["bar"]
            and selecting["rows"] > 0,
            str(selecting) if not refused else f"data-selmode {refused}")
        await page.evaluate("()=>window.__magasin.ecrire({selMode: false})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)

        # `data-del` is READ rather than tapped: the control lives behind a
        # swipe, and R64 is what drives that gesture. What this holds is that
        # the attribute still names the row it belongs to — the half a moved
        # emitter can break.
        named = await page.evaluate("""()=>{
          const rows = [...document.querySelectorAll('#libitems .card')];
          const first = rows[0];
          const action = first ? first.parentElement.querySelector('[data-del]') : null;
          const title = first ? (first.querySelector('.ctitle')||{}).textContent : null;
          return {title: title ? title.trim() : null,
                  del: action ? action.dataset.del : null};}""")
        journal.check(
            "a row's delete action names THAT row",
            bool(named["title"]) and named["del"] == named["title"],
            str(named))

        await page.evaluate(
            # french-ok: a French search WORD, typed into the app's own search.
            "()=>{window.__magasin.ecrire({q: 'stargate'});}")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)
        refused = await tap("#view [data-clearq]")
        cleared = await page.evaluate("""()=>({
          q: window.__magasin.lire().etat.q,
          field: (document.querySelector('#libq')||{}).value,
          cross: !!document.querySelector('#view [data-clearq]'),
        })""")
        journal.check(
            "a real tap on the search's cross clears the field AND the search",
            not refused and cleared["q"] == "" and cleared["field"] == ""
            and not cleared["cross"],
            str(cleared) if not refused else f"data-clearq {refused}")

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
        # EVERY DIAL NAMED, and the world reset: this block runs after the
        # settings taps, which leave a scenario and a mutated world behind. The
        # crossref hold below is gated on `scen`, so the dependency is real —
        # naming half of it is what makes a hold measure a surface nobody asked
        # for.
        await page.evaluate("()=>window.__reset()")
        await page.evaluate("()=>window.__magasin.ecrire({page: 'arr',"
                            " phase: 'prete', pipe: 'repos', scen: 'charge'})")
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
        # The STORE and the DRAWING, because a component that kept drawing the
        # running bar over a stopped pipeline satisfies the store alone — which
        # is the half its two siblings above already read.
        stopped = await page.evaluate("""()=>({
          pipe: window.__magasin.lire().etat.pipe,
          idle: !!document.querySelector('#view .pipeline .pip.neutral'),
          start: !!document.querySelector('#view .pipeline .cfoot.solid'),
          controls: [...document.querySelectorAll('#view [data-pipe]')]
            .map((x) => x.dataset.pipe),
        })""")
        journal.check(
            "and a real tap on « arrêter » stops it, and the bar says so",
            not refused and stopped["pipe"] == "repos" and stopped["idle"]
            and stopped["start"] and stopped["controls"] == ["lancer"],
            str(stopped) if not refused else f"data-pipe='arreter' {refused}")

        # The crossref leaves the page entirely, and it is the page's own
        # `data-go` — the attribute B-024's containment argument counts. It is
        # drawn only outside the real-data scenario, which the block named at
        # its head.
        refused = await tap("#view .crossref[data-go='acq']")
        landed = await page.evaluate("()=>window.__magasin.lire().etat.page")
        journal.check(
            "a real tap on the crossref lands on Acquisition",
            not refused and landed == "acq",
            f"page={landed}" if not refused else f"data-go='acq' {refused}")

        # (d-quinquies) THE LEGACY'S `render()` IS NEVER CALLED FROM A REACT
        # LIFECYCLE. The handover rests on `window.__releasePage()` being
        # SYNCHRONOUS, and `flushSync` silently degrades to an async flush when
        # it is called during render or commit — at which point the fragment's
        # `view.innerHTML = …` runs with React's portal children still in place,
        # and the root tears down on the next unmount. The two call sites in the
        # shell today are both DOM event handlers, which is safe; the invariant
        # is what needs holding, because nothing about `render()` announces it.
        sources = sorted((pathlib.Path(__file__).resolve().parent.parent
                          / "design" / "src").rglob("*.tsx"))
        inside = []
        for source in sources:
            text = source.read_text(encoding="utf-8")
            for match in re.finditer(r"use(?:Layout)?Effect\(", text):
                depth, index = 0, match.end() - 1
                while index < len(text):
                    if text[index] == "(":
                        depth += 1
                    elif text[index] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    index += 1
                body = text[match.end():index]
                if re.search(r"(?<![.\w])render\(\)", body):
                    inside.append(f"{source.name}:"
                                  f"{text[:match.start()].count(chr(10)) + 1}")
        journal.check(
            "no component calls the legacy render() from an effect",
            not inside, str(inside) if inside
            else f"{len(sources)} component file(s) read")

        # (d-bis) NO RULE DRIVES A PAGE BY MUTATING THE ENGINE'S ALIAS.
        # `state` is a module-global alias onto the store's CURRENT object, so
        # `state.page = "arr"` mutates that object IN PLACE: its identity never
        # changes, nothing React subscribes to moves, and the page keeps drawing
        # whatever was there before. It was measured rather than reasoned about
        # — the store named one page, `#view` held another page's roots,
        # and the rule that hit it reported a MISSING BUTTON rather than a stale
        # page, which is what makes this worth a source-level hold. The door is
        # the store (`window.__magasin.ecrire`), or `applyState` / `__go`, which
        # go through it.
        #
        # THREE SHAPES, not one. A first version matched `state.x =` on a single
        # physical line and would have been walked past by `Object.assign(state,
        # …)` — which the engine itself uses — by `state["page"] =`, and by a
        # write split across two source lines, which is this directory's own
        # house style for long driver strings. So the text is flattened first:
        # comments dropped, quotes and backslashes removed (a driver is a STRING
        # here, split at the author's convenience), whitespace collapsed.
        scripts = sorted(pathlib.Path(__file__).resolve().parent.glob("*.py"))
        shapes = (
            r"(?<![.\w])state\s*\.\s*\w+\s*(?:\+|-|\*|\?\?|\|\|)?=(?!=)",
            r"(?<![.\w])state\s*\[[^\]]*\]\s*=(?!=)",
            r"Object\s*\.\s*assign\s*\(\s*state\b",
        )
        writers = []
        for script in scripts:
            source = "\n".join(
                line for line in script.read_text(encoding="utf-8").split("\n")
                if not line.lstrip().startswith("#"))
            flat = re.sub(r"\s+", " ", re.sub(r"[\"'\\]", "", source))
            hit = [shape for shape in shapes if re.search(shape, flat)]
            if hit:
                writers.append(f"{script.name} ({len(hit)} shape(s))")
        journal.check(
            "no rule drives a page by mutating the engine's state alias",
            not writers,
            str(writers) if writers
            else f"{len(scripts)} scripts read, three shapes each, none writes")

        # (d-ter) A COLD DEEP ADDRESS LANDS ON THE SHELL-OWNED PAGE. `/` keeps
        # its legacy query and the LEGACY parser keeps owning it, so a link to
        # `?page=arr` reaches a migrated page only if what that parser reads
        # crosses into the store the component reads. The engine reads it once
        # at boot, through the one in-place write left anywhere
        # (`Object.assign(state, etatDeLURL())`), which is why this is measured
        # rather than assumed. Measured, it holds for a sturdier reason than the
        # ordering alone: the address write that follows re-renders the shell,
        # which re-reads the mutated object — starting the engine AFTER React's
        # first paint does not fell this hold. What fells it is the parser
        # ceasing to read `page`, which is the promise itself.
        cold = await context.new_page()
        await cold.goto(f"{PROTOTYPE}?page=arr", wait_until="load")
        await cold.evaluate("()=>window.__chargementTermine?.()")
        await cold.evaluate("()=>document.querySelector('#toastx')?.click()")
        await cold.wait_for_timeout(500)
        landed = await cold.evaluate("""()=>({
          page: window.__magasin.lire().etat.page,
          roots: [...document.querySelector('#view').children].map((x) => x.className),
          bar: !!document.querySelector('#view .pipeline [data-pipe]'),
        })""")
        journal.check(
            "a cold deep address lands on the page it names, drawn by the shell",
            landed["page"] == "arr" and landed["roots"] == ["body"]
            and landed["bar"],
            str(landed))
        await cold.close()

        # (d) The handover is the SHELL's: the fragment must not write into a
        # container React holds. Read from the DOCUMENT THE BROWSER RAN, never
        # from the source on disk — every other hold here measures the served
        # copy, and this rule's own mutations disable things in that copy alone,
        # so a source read could stay green over a page that lost the guard.
        # Read as a pattern rather than as a byte-exact line, because reflowing
        # the line changes nothing about the law; and counted, because the guard
        # says nothing about a SECOND, unguarded write elsewhere.
        # (d-quater) THE TWO TABLES MUST AGREE. `PAGES` in the shell and the
        # `shellOwned` flags in the fragment's `PAGES_OF()` are independent
        # lists kept identical by hand. One direction crashes loudly — the
        # fragment calls `found.render()` where there is none. The other draws
        # the page in BOTH worlds at once, on every render, perfectly
        # consistently — which is invisible to every hold shaped like « the
        # page looks the same each time ». So they are compared.
        tables = await page.evaluate("""()=>{
          const shell = [...(window.__shellPages || [])].sort();
          const table = window.__referentiel.PAGES_OF();
          return {shell,
                  owned: table.filter((x) => x.shellOwned).map((x) => x.id).sort(),
                  ownedWithRenderer: table.filter((x) => x.shellOwned && x.render)
                    .map((x) => x.id),
                  legacyWithout: table.filter((x) => !x.shellOwned && !x.render)
                    .map((x) => x.id)};}""")
        journal.check(
            "the shell's page table and the fragment's flags name the same pages",
            tables["shell"] == tables["owned"]
            and not tables["ownedWithRenderer"] and not tables["legacyWithout"],
            f"shell {tables['shell']} vs shellOwned {tables['owned']}"
            + (f"; owned but still drawable: {tables['ownedWithRenderer']}"
               if tables["ownedWithRenderer"] else "")
            + (f"; legacy with no renderer: {tables['legacyWithout']}"
               if tables["legacyWithout"] else ""))

        served = await page.content()
        writes = re.findall(r"[^\n]*view\.innerHTML\s*=[^\n]*", served)
        # THE LAW, not one spelling of it. The guard was once a single line and
        # is now a branch, and a hold that matched the line would have failed on
        # the day the law was made STRONGER rather than weaker. What must be
        # true: `#view` is written in one place, on the branch where the shell
        # does NOT own the page, and the shell is asked to let go before that
        # write happens.
        # THE WRITE MUST BE ON THE NOT-OWNED BRANCH, which is the whole law —
        # a first version of this hold asserted only that a branch and a
        # release EXISTED somewhere in `render()`, and would have stayed green
        # over a write hoisted out of the `else`, i.e. over a migrated page
        # destroyed under React on every draw. The structure is read: the
        # ownership test, then its `else`, then the write inside it, then the
        # announcement before it.
        law = re.search(
            r"if \(found\.shellOwned\)\s*\{(?P<owned>[\s\S]*?)\}\s*else\s*\{"
            r"(?P<legacy>[\s\S]*?)\n    \}",
            served)
        owned = law.group("owned") if law else ""
        legacy = law.group("legacy") if law else ""
        journal.check(
            "the fragment writes #view only on the branch where the shell does "
            "NOT own the page, and announces the handover first",
            law is not None
            and len(writes) == 1
            and "view.innerHTML" in legacy
            and "view.innerHTML" not in owned
            and legacy.index("window.__releasePage?.()")
            < legacy.index("view.innerHTML"),
            f"{len(writes)} write(s) to #view's innerHTML; branch found: "
            f"{law is not None}; write on the not-owned branch: "
            f"{'view.innerHTML' in legacy and 'view.innerHTML' not in owned}")

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
