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
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# The pages the shell owns today. A page absent here is one the fragment still
# draws, and the rule holds that too — it is the other half of the law.
SHELL_OWNED = ["sys"]
LEGACY_OWNED = ["lib", "arr", "acq"]

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
        walk = ["lib", "sys", "lib", "arr", "sys", "arr", "acq", "sys", "acq"]
        signatures: dict[str, set[str]] = {}
        residue = []
        for identifier in walk:
            await page.evaluate(f"()=>window.__magasin.ecrire({{page: {identifier!r}}})")
            await page.evaluate("()=>window.__referentiel.render()")
            await page.wait_for_timeout(300)
            seen = await page.evaluate(READ)
            signature = f"{seen.get('children')} roots {seen.get('roots')}"
            signatures.setdefault(identifier, set()).add(signature)
            if len(signatures[identifier]) > 1:
                residue.append(f"{identifier}: {sorted(signatures[identifier])}")
        journal.check(
            "a page draws the same whichever world it was reached from",
            not residue,
            str(residue) or "; ".join(
                f"{name}={next(iter(seen))}" for name, seen in signatures.items()))

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
        await page.click("#view .topic[data-maintrub='scan']")
        await page.wait_for_timeout(360)
        opened = await page.evaluate("""()=>({
          rubrique: window.__magasin.lire().etat.maintRub,
          back: !!document.querySelector('#view .crossref[data-maintrub=""]'),
          rows: document.querySelectorAll('#view .flux .fx').length,
        })""")
        journal.check(
            "a real tap on a rubric row opens that rubric",
            opened["rubrique"] == "scan" and opened["back"] and opened["rows"] > 0,
            str(opened))

        # Looked up rather than clicked blind: a component that stopped emitting
        # `data-maintact` would otherwise time the click out and CRASH the
        # script, which reads as a broken rule instead of a named defect.
        target = page.locator("#view .flux .fx .fw[data-maintact]").first
        emitted = await target.count()
        if emitted:
            await target.click()
            await page.wait_for_timeout(420)
        panel = await page.evaluate("""()=>({
          open: !!document.querySelector('#sheet.open'),
          title: (document.querySelector('#sheet .sheettitle')||{}).textContent || null,
        })""")
        journal.check(
            "and a real tap on a command row opens its panel",
            bool(emitted) and panel["open"] and bool(panel["title"]),
            str(panel)[:120] if emitted else "no row carries data-maintact")
        await page.evaluate("()=>window.__panneau.fermer()")
        await page.wait_for_timeout(300)

        # (d) The handover is the SHELL's: the fragment must not write into a
        # container React holds. Proven from the source rather than by drawing:
        # a write there would be invisible until the day it removes a node
        # React still believes it owns.
        fragment = (pathlib.Path(__file__).resolve().parent.parent
                    / "design" / "refonte.html").read_text(encoding="utf-8")
        guarded = "if (!found.shellOwned) view.innerHTML = found.render();"
        journal.check(
            "the fragment writes #view only for a page it still owns",
            guarded in fragment,
            "guard present" if guarded in fragment else "the guard is gone")

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
