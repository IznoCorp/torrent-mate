"""R59 — the back gesture follows the path actually walked.

Only the LAYERS used to push history. A back closed a sheet, and then, with
nothing left to close, left the application — losing every page the operator
had walked through. A tab is a place one navigates to; it belongs in the
history exactly as a screen does.

RENEGOTIATED, and this paragraph is the record rather than a rewrite of
history. « It belongs in the history exactly as a screen does » was read as
« every tap is a step », and this rule held four backs undoing four taps in
reverse. The constitution's § 16 says which taps are steps: opening a surface
is an arrival and stacks, adjusting one — an inner tab, a lens, a sort — is a
setting and replaces, and switching a top-level page stacks nothing at all
because a destination is not a step of a journey. A tab is still IN the
history: it is on the entry, which is what lets a back put it back. What it is
no longer is an entry of its own.

At the bottom of the stack a guard entry sits, so a back at the root has
something to pop and the application is never left by surprise. Popping it says
so and puts it back; a second back within five seconds does not, and lets the
stack run out — which is what closes an installed app on Android. A page cannot
close itself; exhausting its history is the only honest thing it can do, and
this script checks that it does exactly that and nothing more.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


# Reading the interface AFTER a back that left the document raises instead of
# naming the defect. A crash is a failure nobody can read.
#
# The test is the ORIGIN, never the file name. Every address the router owns —
# `/`, `/add`, a page's own path — is served by the same document and carries no
# « wrapped.html » anywhere in it, so a name test would report « the document was
# left » about a journey that never left it. `ident.py` met this first and wrote
# the answer down; this is the same answer.
async def where(pg):
    """Where the interface is, or None when the document is gone."""
    if pg.is_closed() or not pg.url.startswith("http://127.0.0.1:8899"):
        return None
    try:
        return await pg.evaluate(WHERE)
    except Exception:  # noqa: BLE001 — the document left, which is the finding
        return None


WHERE = """() => ({
  page: state.page,
  tab: state.acqTab,
  lens: state.libLens,
  sheet: document.querySelector('#sheet').hasAttribute('data-open'),
  screen: document.querySelector('#screen').hasAttribute('data-open'),
  drawer: document.querySelector('#drawer').hasAttribute('data-open'),
  dialog: document.querySelector('#dlg').hasAttribute('data-open'),
  entries: history.length,
  message: (document.querySelector('#toast')||{}).textContent || '',
  toastVisible: (document.querySelector('#toast')||{hasAttribute:()=>false})
                  .hasAttribute('data-shown'),
})"""


async def main():
    global _journal
    _journal = Journal("R59 — the back gesture follows the path")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>document.querySelector('#toastx').click()")
        await pg.wait_for_timeout(300)

        # ── the path, walked forward by tapping ────────────────────────────
        path = [
            ('[data-acqtab="follows"]', "acq", "follows"),
            ('[data-page="lib"]', "lib", None),
            ('[data-lens="inc"]', "lib", None),
            ('[data-page="arr"]', "arr", None),
        ]
        for selector, _, _ in path:
            await pg.click(selector)
            await pg.wait_for_timeout(250)
        arrival = await where(pg)
        check("the path can be walked", arrival is not None and arrival["page"] == "arr",
              str(arrival and arrival["page"]))

        # ── and walked back: the ARRIVALS, which is not every tap ──────────
        # § 16 renegotiates what the walk above leaves behind, and the four
        # taps are one of each kind. An inner tab and a lens are SETTINGS — the
        # same surface looked at another way — and they replace the entry they
        # are on; a top-level page is a destination rather than a step of a
        # journey, so the stack under the walk is the entry page plus one. ONE
        # back therefore leaves all three pages behind at once, which is the
        # whole of rule 2: no platform makes a reader rewind the tabs they
        # visited, and a Retour that undoes a lens is a Retour that refuses to
        # let go of the screen.
        await pg.go_back()
        await pg.wait_for_timeout(320)
        step = await where(pg)
        check("one back leaves every page visited behind and lands on the entry page",
              step is not None and step["page"] == "acq", str(step and step["page"]))
        check("carrying the inner tab the walk had set — a setting travels ON the entry",
              step is not None and step["tab"] == "follows", str(step and step["tab"]))
        check("and the lens THAT entry carries, not the one set on the page since left",
              step is not None and step["lens"] == "cat", str(step and step["lens"]))

        # ── a layer is what a back closes first ────────────────────────────
        await pg.evaluate("()=>openFollowSheet('Silo')")
        await pg.wait_for_timeout(350)
        opened = await where(pg)
        check("a sheet opens", bool(opened and opened["sheet"]))
        await pg.go_back()
        await pg.wait_for_timeout(300)
        after = await where(pg)
        check("the back closes it without changing page",
              after is not None and not after["sheet"] and after["page"] == "acq",
              str(after and after["page"]))

        # ── at the root: the application is not left by surprise ───────────
        before = await where(pg)
        await pg.go_back()
        await pg.wait_for_timeout(300)
        bottom = await where(pg)
        check("at the bottom of the path, the route does not change",
              bottom is not None and before is not None and bottom["page"] == before["page"],
              f"{before and before['page']} → {bottom and bottom['page']}"
              if bottom else "the document was left")
        check("and the app warns that a second back leaves it",
              bottom is not None and "quitter" in bottom["message"].lower() and bottom["toastVisible"],
              (bottom["message"][:60] if bottom else "the document was left"))
        check("the page is still there", not pg.is_closed())

        # ── the offer expires: after the window, it warns again ────────────
        await pg.wait_for_timeout(5200)
        if await where(pg):
            await pg.evaluate("()=>document.querySelector('#toastx').click()")
        await pg.go_back()
        await pg.wait_for_timeout(300)
        late = await where(pg)
        check("past five seconds, the warning starts over",
              late is not None and "quitter" in late["message"].lower(),
              (late["message"][:60] if late else "the document was left"))

        # ── a second back inside the window exhausts the stack ─────────────
        # Nothing is put back, so the document is left. That is what closes an
        # installed app; here it lands on the blank page the context started on.
        await pg.go_back()
        await pg.wait_for_timeout(600)
        check("a second back inside the window exhausts the history",
              not pg.url.startswith("http://127.0.0.1:8899"), pg.url[:60])

        # ── B-229: THE DIALOG IS A RUNG, AND BACK WALKS IT ────────────────
        # D1's third tier reads « Transient: no URL, but Back still closes it »
        # and names a confirmation as its example. It was not implemented:
        # `openDlg` pushed no entry and the back handler had no branch, so a
        # hardware Back popped the entry UNDER the dialog — a page, or the exit
        # guard — with the dialog still up. The dialog was never CLOSERLESS:
        # Escape reached it and so did a scrim tap. Only Back did not.
        #
        # THE ADDRESS ALONE WOULD NOT SAY THIS, which is R69's own lesson: a
        # hold that reads only where the interface IS passes over an entry
        # spent twice. All three are read together — the dialog closed, the page
        # underneath unchanged, and the history back to the length it had.
        second = await b.new_context(viewport={"width": 390, "height": 844},
                                     is_mobile=True, has_touch=True)
        dialog_page = await second.new_page()
        await dialog_page.goto("http://127.0.0.1:8899/", wait_until="load")
        await dialog_page.evaluate("()=>window.__loadingDone?.()")
        await dialog_page.evaluate("()=>window.__go('lib-delete')")
        await dialog_page.wait_for_timeout(400)
        raised = await dialog_page.evaluate(WHERE)
        check("a confirmation really opens, so this hold has a subject",
              raised["dialog"], str({k: raised[k] for k in ("dialog", "page")}))
        # BACK TO A STATE WITH NO DIALOG, so the entry underneath is a PAGE's
        # and not another confirmation's. Driving to `lib-delete` above proved
        # the subject exists; measuring on top of it would measure two dialogs
        # stacked, which is a real case and not this one.
        await dialog_page.evaluate("()=>window.__go('lib-list')")
        await dialog_page.wait_for_timeout(350)
        raised = await dialog_page.evaluate(WHERE)

        # THE ENTRY UNDERNEATH IS CAPTURED FIRST, verbatim. `history.length`
        # cannot say this: it counts entries and a back MOVES the cursor
        # without removing one, so it reads the same either way — a number that
        # cannot come out the other way, which is the shape this wave has
        # already met twice. What DOES separate « spent its own entry » from
        # « spent one too many » is the entry the interface ends up standing on.
        beneath = await dialog_page.evaluate("()=>JSON.stringify(history.state)")
        floor = await dialog_page.evaluate("()=>history.length")
        await dialog_page.evaluate(
            "()=>window.__dialog.open({heading: 'probe', body: [], actions: []})")
        await dialog_page.wait_for_timeout(250)
        pushed = await dialog_page.evaluate(
            "()=>({length: history.length, layer: history.state && history.state.layer})")
        check("opening a confirmation stacks an entry of its own (B-229)",
              pushed["length"] == floor + 1 and pushed["layer"] == "dialog",
              f"{floor} → {pushed['length']}, layer={pushed['layer']!r}")
        await dialog_page.go_back()
        await dialog_page.wait_for_timeout(450)
        after = await dialog_page.evaluate(WHERE)
        check("a back closes the confirmation (B-229)",
              not after["dialog"], str(after["dialog"]))
        check("and leaves the page underneath exactly where it was",
              after["page"] == raised["page"] and after["lens"] == raised["lens"],
              f"{raised['page']}/{raised['lens']} → {after['page']}/{after['lens']}")
        landed = await dialog_page.evaluate("()=>JSON.stringify(history.state)")
        check("and lands on the entry the dialog was opened over, not the one under it",
              landed == beneath, f"{beneath} → {landed}")
        await second.close()

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
