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
SHELL_OWNED = ["sys", "maint", "cfg", "arr", "lib", "acq", "profile", "404"]

# What each page really emits, less a small margin. Measured, not guessed: one
# floor for eight pages is either too high for the smallest or too low to notice
# a page that lost half of itself.
FLOORS = {"sys": 180, "maint": 50, "cfg": 40, "arr": 140, "lib": 150,
          "acq": 55, "profile": 30, "404": 5}
# EMPTY, and that is the point of this wave: no page is drawn by the fragment
# any more. The hold below says so out loud rather than passing over an empty
# list — a scope that silently empties is a rule that stopped measuring.
LEGACY_OWNED: list[str] = []

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
            await page.evaluate(f"()=>window.__store.write({{page: {identifier!r}}})")
            await page.evaluate("()=>window.__referentiel.render()")
            await page.wait_for_timeout(300)
            seen = await page.evaluate(READ)
            # « ONCE » is the residue hold's business, and it measures it
            # across predecessors. What this one holds is that the page is
            # DRAWN — and it may not assume a root count: the Médiathèque emits
            # four siblings where the other four emit one, which is why the
            # host stopped supplying a root element of its own.
            # A FLOOR PER PAGE, and that is the point. One floor for all of
            # them has to clear the smallest — the unknown-address page is
            # SEVEN elements and one sentence, by design — and a floor low
            # enough for that one calls a Médiathèque reduced to its tab bar
            # « drawn ». Each number is a little under what the page really
            # emits, so a page that loses a section says so.
            floor = FLOORS[identifier]
            journal.check(
                f"the shell-owned page « {identifier} » is drawn, whole",
                seen.get("children", 0) >= 1
                and seen.get("elements", 0) >= floor,
                f"{seen.get('elements')} elements, floor {floor}")

        # (b) A page the fragment still owns is drawn exactly as before — and
        # when there are none left, that is itself the thing to say.
        # READ FROM THE APP, never from the list above: a check whose
        # condition is a constant declared in the same file cannot fail,
        # and would have counted toward this rule's total while measuring
        # nothing.
        drawn_by_legacy = await page.evaluate(
            "()=>window.__referentiel.PAGES_OF()"
            ".filter((x) => !x.shellOwned).map((x) => x.id)")
        journal.check(
            "every page in the table has an owner, and the fragment draws none",
            not drawn_by_legacy,
            f"the fragment still draws: {drawn_by_legacy}" if drawn_by_legacy
            else f"{len(SHELL_OWNED)} shell-owned, none left to the fragment")
        for identifier in LEGACY_OWNED:
            await page.evaluate(f"()=>window.__store.write({{page: {identifier!r}}})")
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
                "cfg", "sys", "cfg", "lib", "arr", "acq", "arr", "profile",
                "acq", "profile", "404", "lib", "404"]
        signatures: dict[str, set[str]] = {}
        residue = []
        absent = []
        for identifier in walk:
            await page.evaluate(f"()=>window.__store.write({{page: {identifier!r}}})")
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
        await page.evaluate("()=>window.__store.write({page: 'maint', maintTopic: null})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        refused = await tap("#view .topic[data-maintopic='scan']")
        opened = await page.evaluate("""()=>({
          topic: window.__store.read().state.maintTopic,
          back: !!document.querySelector('#view .crossref[data-maintopic=""]'),
          rows: document.querySelectorAll('#view .flux .fx').length,
        })""")
        journal.check(
            "a real tap on a rubric row opens that rubric",
            not refused and opened["topic"] == "scan" and opened["back"]
            and opened["rows"] > 0,
            str(opened) if not refused else f"data-maintopic='scan' {refused}")

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
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(300)

        # (c-ter) THE SAME DEBT, on the page that carries the most of it. The
        # settings page emits seven attributes the document-level delegation
        # acts on, and R60 reaches every one of its states through
        # `window.__go(...)` — never through a tap. So the whole delegation
        # path was unmeasured: a component that stopped writing
        # `data-topic` would leave a page of rows nothing opens, with R60
        # entirely green. Each control is LOOKED UP before it is tapped: a
        # click on a selector that matches nothing times out and crashes the
        # script, which reads as a broken rule instead of a named defect.
        await page.evaluate(
            "()=>{SETTINGS_STATE.topic = null; SETTINGS_STATE.q = '';"
            " SETTINGS_STATE.modifs.clear(); SETTINGS_STATE.redemarrage = false;}")
        await page.evaluate("()=>window.__store.write({page: 'cfg'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)

        topic = await page.evaluate(
            "()=>{const b = document.querySelector('#view .topic[data-topic]');"
            " return b ? b.dataset.topic : null;}")
        refused = await tap("#view .topic[data-topic]") if topic else "absent"
        opened = await page.evaluate("""()=>({
          topic: SETTINGS_STATE.topic,
          rows: document.querySelectorAll('#view .settingrow[data-setting]').length,
        })""")
        journal.check(
            "a real tap on a settings topic opens THAT topic",
            not refused and opened["topic"] == topic and opened["rows"] > 0,
            f"{topic} → {opened}" if not refused else f"data-topic {refused}")

        # The row's own identity, compared against the field the panel opens on:
        # « a panel opened » would be satisfied by every row opening the same
        # one. The panel's META carries the identity for EVERY type, while
        # `data-field` exists only for the types that offer a field — a
        # structure or a list would fail this hold for the wrong reason.
        identity = await page.evaluate(
            "()=>{const b = document.querySelector('#view .settingrow[data-setting]');"
            " return b ? b.dataset.setting : null;}")
        refused = (await tap("#view .settingrow[data-setting]")
                   if identity else "absent")
        edited = await page.evaluate("""()=>{
          const field = document.querySelector('#sheetin [data-field]');
          const meta = document.querySelector('#sheet .sheetmeta');
          return {open: !!document.querySelector('#sheet.open'),
                  field: field ? field.dataset.field : null,
                  meta: meta ? meta.textContent.trim() : null};}""")
        named = identity and edited["meta"] and all(
            part in edited["meta"] for part in identity.split(":"))
        journal.check(
            "and a real tap on a setting opens THAT setting",
            not refused and edited["open"] and bool(named)
            and (edited["field"] is None or edited["field"] == identity),
            f"{identity} → {edited}" if not refused else f"data-setting {refused}")
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(300)

        # The save bar is the page's second host, and its button is the only
        # control in the prototype that WRITES. The change is staged through
        # the legacy's own verb rather than typed, because what is held here is
        # the tap, not the field.
        staged = await page.evaluate("""()=>{
          const setting = window.__referentiel.allSettings()
            .find((x) => x.type === 'boolean');
          if (!setting) return null;
          const id = window.__referentiel.settingId(setting);
          window.__referentiel.changeSetting(id, !setting.brut);
          window.__referentiel.render();
          return id;}""")
        await page.wait_for_timeout(300)
        refused = (await tap("#savebar [data-save]") if staged else "absent")
        saved = await page.evaluate(
            "()=>({pending: SETTINGS_STATE.modifs.size, restart: SETTINGS_STATE.redemarrage,"
            " bar: !!document.querySelector('#savebar')})")
        journal.check(
            "a real tap on the save bar files the change and asks for a restart",
            not refused and saved["pending"] == 0 and saved["restart"]
            and not saved["bar"],
            str(saved) if not refused else f"data-save {refused}")

        await page.evaluate("()=>{SETTINGS_STATE.topic = null;}")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        refused = await tap("#view [data-restart]")
        # The restart offer only exists because the save above raised it, so a
        # lost `data-save` reaches this hold as « absent ». The detail
        # says what was MEASURED either way — a line that reads « restart
        # cleared » under a FAIL tells a reader the opposite of what happened.
        restart_left = await page.evaluate("()=>SETTINGS_STATE.redemarrage")
        journal.check(
            "and a real tap on the restart offer takes it",
            not refused and not restart_left,
            f"redemarrage={restart_left}" if not refused
            else f"data-restart {refused} (the save above raises it)")

        refused = await tap("#view .topic[data-topic='secrets']")
        listed = await page.evaluate(
            "()=>({topic: SETTINGS_STATE.topic,"
            " rows: document.querySelectorAll('#view [data-secret]').length})")
        journal.check(
            "a real tap on the secrets topic lists the secrets",
            not refused and listed["topic"] == "secrets" and listed["rows"] > 0,
            str(listed) if not refused else f"data-topic='secrets' {refused}")

        # THAT secret's panel: the key it carries has to appear in the panel it
        # opened, or every secret row opening one panel would pass.
        key = await page.evaluate(
            "()=>{const b = document.querySelector('#view [data-secret]');"
            " return b ? b.dataset.secret : null;}")
        await page.evaluate("()=>window.__panel.close()")
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
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(300)

        # The search's clear button exists only while something is searched
        # for, so the query is staged first — the tap is what is held.
        await page.evaluate(
            # french-ok: a French search WORD, typed into the app's own search
            # — the data a French interface is searched with, not a name.
            "()=>{SETTINGS_STATE.topic = null; SETTINGS_STATE.q = 'espace';}")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        refused = await tap("#view [data-qsettings]")
        cleared = await page.evaluate(
            "()=>({q: SETTINGS_STATE.q,"
            " clear: !!document.querySelector('#view [data-qsettings]')})")
        journal.check(
            "a real tap on the search's cross clears the search",
            not refused and cleared["q"] == "" and not cleared["clear"],
            str(cleared) if not refused else f"data-qsettings {refused}")

        # And the one row that leaves the page entirely: the quality profile is
        # a ROUTE, so what proves the tap landed is the address — the address
        # the ROW NAMED, and only if it was not already there before the tap.
        profile = await page.evaluate(
            "()=>{const b = document.querySelector('#view .topic[data-profile]');"
            " return b ? b.dataset.profile : null;}")
        before_address = await page.evaluate("()=>location.pathname")
        refused = await tap("#view .topic[data-profile]") if profile else "absent"
        await page.wait_for_timeout(400)
        address = await page.evaluate("()=>location.pathname")
        journal.check(
            "a real tap on the quality-profile row goes to ITS address",
            not refused and profile is not None
            and address == f"/profile/{profile}" and before_address != address,
            f"{before_address} → {address} for data-profile={profile!r}"
            if not refused else f"data-profile {refused}")
        await page.evaluate("()=>window.__bridge.back()")
        await page.wait_for_timeout(420)

        # (c-sexies) THE MÉDIATHÈQUE'S OWN DELEGATION. This page carries more
        # of it than any other — the lens, the category, the view mode, the
        # selection, the deletion and the search's cross — and R63 drives it
        # through the store, never through a tap.
        await page.evaluate("()=>window.__reset()")
        await page.evaluate("()=>window.__store.write({page: 'lib', phase: 'ready',"
                            " libLens: 'cat', libMode: 'list', libCat: 'all', q: ''})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)

        refused = await tap("#view .seg [data-lens='rec']")
        lens = await page.evaluate("""()=>({
          lens: window.__store.read().state.libLens,
          drawn: (document.querySelector('#view .countline')||{}).textContent || '',
        })""")
        journal.check(
            "a real tap on a lens opens THAT lens",
            not refused and lens["lens"] == "rec" and "index" in lens["drawn"],
            str(lens)[:120] if not refused else f"data-lens {refused}")

        await page.evaluate("()=>window.__store.write({libLens: 'cat'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)
        wanted = await page.evaluate(
            "()=>{const b = [...document.querySelectorAll('#view .pill[data-cat]')]"
            ".find((x) => x.dataset.cat !== 'all'); return b ? b.dataset.cat : null;}")
        refused = (await tap(f"#view .pill[data-cat='{wanted}']") if wanted else "absent")
        chosen = await page.evaluate(
            "()=>({cat: window.__store.read().state.libCat,"
            " pressed: (document.querySelector('#view .pill[aria-pressed=true]')||{})"
            ".dataset?.cat || null})")
        journal.check(
            "a real tap on a category pill filters by THAT category",
            not refused and chosen["cat"] == wanted and chosen["pressed"] == wanted,
            f"{wanted} → {chosen}" if not refused else f"data-cat {refused}")

        refused = await tap("#view [data-lmode='grid']")
        mode = await page.evaluate("""()=>({
          mode: window.__store.read().state.libMode,
          drawn: (document.querySelector('#libitems')||{}).className || null,
        })""")
        journal.check(
            "a real tap on the view switch really switches the view",
            not refused and mode["mode"] == "grid" and mode["drawn"] == "grid",
            str(mode) if not refused else f"data-lmode {refused}")
        await page.evaluate("()=>window.__store.write({libMode: 'list', libCat: 'all'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)

        # The selection bar is the FRAGMENT's node in `#device`: tapping the
        # entry proves the seam still works across the two worlds.
        refused = await tap("#view [data-selmode='1']")
        selecting = await page.evaluate("""()=>({
          mode: !!window.__store.read().state.selMode,
          bar: !!document.querySelector('#device .selbar'),
          rows: document.querySelectorAll('#libitems .selrow[data-tile]').length,
        })""")
        journal.check(
            "a real tap on « sélectionner » opens selection, bar included",
            not refused and selecting["mode"] and selecting["bar"]
            and selecting["rows"] > 0,
            str(selecting) if not refused else f"data-selmode {refused}")
        await page.evaluate("()=>window.__store.write({selMode: false})")
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
            "()=>{window.__store.write({q: 'stargate'});}")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)
        refused = await tap("#view [data-clearq]")
        cleared = await page.evaluate("""()=>({
          q: window.__store.read().state.q,
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
        await page.evaluate("()=>{SETTINGS_STATE.topic = null; SETTINGS_STATE.q = '';"
                            " SETTINGS_STATE.modifs.clear(); SETTINGS_STATE.redemarrage = false;}")
        await page.evaluate("()=>window.__store.write({page: 'cfg'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        await page.evaluate("""()=>{
          const setting = window.__referentiel.allSettings()
            .find((x) => x.type === 'boolean');
          window.__referentiel.changeSetting(
            window.__referentiel.settingId(setting), !setting.brut);
          window.__referentiel.render();}""")
        await page.wait_for_timeout(300)
        raised = await page.evaluate("()=>!!document.querySelector('#savebar')")
        await page.evaluate("()=>{window.__store.write({page: 'lib'});"
                            " window.__referentiel.render();}")
        await page.wait_for_timeout(500)
        await page.evaluate("()=>{window.__store.write({page: 'cfg'});"
                            " window.__referentiel.render();}")
        await page.wait_for_timeout(500)
        returned = await page.evaluate("""()=>({
          roots: [...document.querySelector('#view').children].map((x) => x.className),
          rows: document.querySelectorAll('#view .topic[data-topic]').length,
        })""")
        journal.check(
            "leaving a migrated page with an unsaved change, and coming back, "
            "leaves the shell alive",
            raised and returned["roots"] == ["body"] and returned["rows"] > 0
            and not console_errors,
            f"bar raised: {raised}; back: {returned}; console errors: "
            + (str(console_errors[:1])[:160] if console_errors else "none"))

        # (c-septies) ACQUISITION'S OWN DELEGATION, on the page that carries
        # the most controls of all: three tabs, four pills, three display modes,
        # three suggestion modes, and the sheet that holds watch and
        # obligations. R63 and the audit reach this page through `__go`; none of
        # them taps.
        await page.evaluate("()=>window.__reset()")
        await page.evaluate("()=>window.__store.write({page: 'acq',"
                            " acqTab: 'now', phase: 'ready'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(400)

        refused = await tap("#view .seg [data-acqtab='follows']")
        opened = await page.evaluate("""()=>({
          tab: window.__store.read().state.acqTab,
          field: !!document.querySelector('#view #follq'),
          rows: document.querySelectorAll('#view .card').length,
        })""")
        journal.check(
            "a real tap on a tab opens THAT tab",
            not refused and opened["tab"] == "follows" and opened["field"]
            and opened["rows"] > 0,
            str(opened) if not refused else f"data-acqtab {refused}")

        wanted = await page.evaluate(
            "()=>{const b = [...document.querySelectorAll('#view .pill[data-pill]')]"
            ".find((x) => x.dataset.pill !== 'tout'); return b ? b.dataset.pill : null;}")
        refused = (await tap(f"#view .pill[data-pill='{wanted}']") if wanted else "absent")
        filtered = await page.evaluate(
            "()=>({pill: window.__store.read().state.pill,"
            " pressed: (document.querySelector('#view .pill[aria-pressed=true]')||{})"
            ".dataset?.pill || null})")
        journal.check(
            "a real tap on a pill filters by THAT pill",
            not refused and filtered["pill"] == wanted
            and filtered["pressed"] == wanted,
            f"{wanted} → {filtered}" if not refused else f"data-pill {refused}")

        refused = await tap("#view [data-fmode='grid']")
        mode = await page.evaluate(
            "()=>({mode: window.__store.read().state.followMode,"
            " tiles: document.querySelectorAll('#view .grid .tile').length})")
        journal.check(
            "a real tap on a display mode really changes the display",
            not refused and mode["mode"] == "grid" and mode["tiles"] > 0,
            str(mode) if not refused else f"data-fmode {refused}")

        await page.evaluate("()=>window.__store.write({acqTab: 'discover',"
                            " followMode: 'list', sugMode: 'list'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(500)
        refused = await tap("#view [data-sugmode='poster']")
        suggestions = await page.evaluate(
            "()=>({mode: window.__store.read().state.sugMode,"
            " grid: (document.querySelector('#sugitems')||{}).className,"
            " tiles: document.querySelectorAll('#sugitems .tile').length})")
        journal.check(
            "a real tap on a suggestion mode redraws the suggestions",
            not refused and suggestions["mode"] == "poster"
            and suggestions["grid"] == "grid" and suggestions["tiles"] > 0,
            str(suggestions) if not refused else f"data-sugmode {refused}")

        # THE CONTAINERS ARE THE FRAGMENT'S TO FILL, and that seam is what this
        # wave chose deliberately — so it is held: React draws them, the
        # fragment fills them, and a re-render does not empty them.
        await page.evaluate("()=>window.__store.write({page: 'lib'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(300)
        await page.evaluate("()=>window.__store.write({page: 'acq'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(600)
        # WHO FILLED IT, not merely whether it is full: « some children »
        # is satisfied by React rendering one, which is exactly the
        # arrangement this hold exists to forbid. What only the FRAGMENT
        # does is set the container's own `className` — React was never
        # given that prop — and emit rows carrying `data-dismissable`,
        # which no component writes.
        refilled = await page.evaluate(
            "()=>{const box = document.querySelector('#sugitems');"
            " return {items: box ? box.children.length : 0,"
            " written: box ? box.className : null,"
            " fragmentRows: box ?"
            " box.querySelectorAll('[data-dismissable]').length : 0,"
            " foot: !!document.querySelector('#sugload')};}")
        journal.check(
            "the suggestion containers survive a round trip, still filled "
            "BY THE FRAGMENT",
            refilled["items"] > 0 and refilled["foot"]
            and refilled["fragmentRows"] == refilled["items"],
            str(refilled))

        # AND THE PAGE FOLLOWS THE WORLD. Every action this page offers
        # mutates the world IN PLACE and signals with `touch()`, which
        # leaves the state's identity unchanged — a component subscribed to
        # the state alone bails out, and the page keeps drawing what it
        # drew. Measured before it was held: « Récupérer now » moved
        # a medium from one list to the other and left every counter on
        # screen unchanged.
        await page.evaluate("()=>window.__go('acq-encours-loaded')")
        await page.wait_for_timeout(600)
        counters = await page.evaluate(
            "()=>[...document.querySelectorAll('#view .sechead .k')]"
            ".map((x) => x.textContent)")
        moved = await page.evaluate(
            "()=>{const first = window.__referentiel.derivedTakeable()[0];"
            " if (!first) return null;"
            " window.__referentiel.actionTake(first.t);"
            " return first.t;}")
        await page.wait_for_timeout(700)
        after_action = await page.evaluate(
            "()=>[...document.querySelectorAll('#view .sechead .k')]"
            ".map((x) => x.textContent)")
        journal.check(
            "an action that moves a medium redraws the page it moved it on",
            moved is not None and counters != after_action,
            f"{counters} → {after_action} after « {moved} » was taken")

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
        await page.evaluate("()=>window.__store.write({page: 'arr',"
                            " phase: 'ready', pipe: 'repos', scen: 'loaded'})")
        await page.evaluate("()=>window.__referentiel.render()")
        await page.wait_for_timeout(320)
        refused = await tap("#view .pipeline [data-pipe='lancer']")
        started = await page.evaluate(
            "()=>({pipe: window.__store.read().state.pipe,"
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
            "()=>({pipe: window.__store.read().state.pipe,"
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
          pipe: window.__store.read().state.pipe,
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
        landed = await page.evaluate("()=>window.__store.read().state.page")
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
        # the store (`window.__store.write`), or `applyState` / `__go`, which
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
        # (`Object.assign(state, stateFromUrl())`), which is why this is measured
        # rather than assumed. Measured, it holds for a sturdier reason than the
        # ordering alone: the address write that follows re-renders the shell,
        # which re-reads the mutated object — starting the engine AFTER React's
        # first paint does not fell this hold. What fells it is the parser
        # ceasing to read `page`, which is the promise itself.
        cold = await context.new_page()
        await cold.goto(f"{PROTOTYPE}?page=arr", wait_until="load")
        await cold.evaluate("()=>window.__loadingDone?.()")
        await cold.evaluate("()=>document.querySelector('#toastx')?.click()")
        await cold.wait_for_timeout(500)
        landed = await cold.evaluate("""()=>({
          page: window.__store.read().state.page,
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
        # container React holds. THE LAW IS HELD TWICE, and the two halves ask
        # different questions.
        #
        # The first is STRUCTURAL, and it is read from the engine's source —
        # because the branch it guards is currently DEAD. Every page is
        # shell-owned today, so the `else` never runs, and no runtime probe can
        # reach it. It still has to be right for the day a page is handed back.
        # This used to read the served document instead, and the reason was
        # sound while the engine WAS the served document: a source read cannot
        # see a served copy a rule corrupted. That reason expired when the
        # engine became a module — what the browser now runs is minified, where
        # `if (found.shellOwned)` reads `if(e.shellOwned)`, and a structural
        # assertion written against mangled names measures the minifier rather
        # than the law. This rule already reads `design/src` from disk two holds
        # above, for an invariant of exactly the same kind.
        #
        # The second is BEHAVIOURAL and covers the live branch — see below.
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

        engine = (pathlib.Path(__file__).resolve().parent.parent / "design"
                  / "src" / "engine" / "legacy.js").read_text(encoding="utf-8")
        writes = re.findall(r"[^\n]*view\.innerHTML\s*=[^\n]*", engine)
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
            engine)
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

        # (d-sexies) AND THE LIVE BRANCH, measured rather than read. The half
        # above proves the shape of code that does not run; this one proves the
        # code that does. `#view`'s own `innerHTML` setter is wrapped for the
        # duration of one real redraw of a shell-owned page: the fragment must
        # write it ZERO times. A guard hoisted out of its `else` — the exact
        # defect the structural half describes — destroys React's portal
        # children on every draw, and would count here.
        # AND IT CARRIES ITS OWN POSITIVE CONTROL, because a hold that asserts
        # a count of ZERO passes just as happily when its detector is dead. The
        # control cannot come first: it writes `#view` on purpose, which tears
        # out the children React holds there and leaves the shell unable to
        # commit. So the order is measure, then prove the measurement — and
        # this is the last thing the rule does before the browser closes, which
        # is why the damage costs nothing.
        #
        # Learned the expensive way: the obvious mutation for this hold — a
        # write on the shell-owned branch, spelled so the structural pattern
        # above cannot see it — breaks the page so thoroughly that thirty
        # earlier holds fail and the script never reaches this line. « The
        # suite went red » is not the same as « this hold works ».
        spied = await page.evaluate("""()=>{
          const view = document.querySelector('#view');
          const setter = Object.getOwnPropertyDescriptor(
            Element.prototype, 'innerHTML').set;
          let writes = 0;
          Object.defineProperty(view, 'innerHTML', {
            configurable: true,
            set(value) { writes++; setter.call(this, value); },
            get() { return view.textContent; },
          });
          window.__referentiel.render();
          const drawn = {writes, children: view.children.length};
          // The control: one deliberate write, which the spy must count.
          view.innerHTML = '<i data-control></i>';
          const counted = writes - drawn.writes;
          delete view.innerHTML;
          return {...drawn, counted,
                  page: window.__store.read().state.page};}""")
        journal.check(
            "redrawing a shell-owned page writes #view zero times, and the "
            "spy that says so is alive",
            spied["writes"] == 0 and spied["children"] > 0
            and spied["counted"] == 1,
            f"{spied['writes']} write(s) on « {spied['page']} », "
            f"{spied['children']} child(ren) left standing, "
            f"control counted {spied['counted']}/1")

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
