"""R100 — the chrome persists: one document, the same nodes, and focus survives.

THREE PROPERTIES OF `MODEL.md` § 3, AND ONE DEFECT UNDER ALL THREE.

  P1  ONE DOCUMENT. No full navigation between any two named states. It was
      true by construction and measured by nothing, which is a different thing
      from true: a single `<a href>` without a router, or one `location.assign`
      in a producer, turns a mobile application back into a website and no
      existing rule would say so.
  P2  A PERSISTENT CHROME. The tab bar's button nodes keep their identity
      across a page switch and a store bump. This was FALSE — B-231: the engine
      called `renderNav()` unconditionally from `render()`, so the bar's
      buttons were new nodes on every navigation and every simulated mutation.
  P28 FOCUS SURVIVES A REDRAW. `document.activeElement` is the same node across
      the same two events. It was false for the same reason and by the same
      mechanism: a focused button replaced by an equal one leaves focus on the
      document body, so a keyboard reader loses their place whenever a counter
      moves.

WHY P2 AND P28 ARE ONE RULE AND NOT TWO. They have one cause and one repair,
and holding them apart would let a repair satisfy one while the other stayed
broken in a way nobody was measuring. The interesting case is precisely the one
where the node LOOKS the same: an `innerHTML` rewrite produces buttons that are
identical in every respect a screenshot, a rectangle or a text assertion can
read. `isSameNode` is the only question that separates them.

WHAT IT DOES NOT READ, said before what it does:

  - It does not hold the bar's CONTENTS. Which pages sit in it, in what order,
    with which badge, is the navigation table's, and `page_host.py` holds the
    table against the address model. This rule would pass over a bar that kept
    four wrong buttons perfectly.
  - P1's walk drives the named states through `window.__go`, which is a seam
    and not a finger. A full navigation caused by a real tap on a control this
    walk never touches is outside it. What the walk DOES cover is every state
    the interface declares it can be in, which is the corpus every other rule
    here is measured over.
  - The store bump is `window.__store.touch()` — the same call every engine
    action ends in. A bump made another way is not a different case; that is
    the one door.
  - Hold (f) reads a PAGE's own nodes — cards, tiles, rows, buttons, pills,
    images, key-value rows — on seven named states, and NOT the containers
    the dying engine fills on Découvrir (`#sugitems`, the deck): those are
    the producers' half of the same defect and belong to the lot that moves
    the producers. Nor a write that legitimately redraws — entering selection
    mode, a sort, a delete: the bump driven is `touch()`, which changes no
    row. And not `features/maintenance/page.tsx`, where the defect was first
    seen: it is held by nobody yet and this hold says so rather than reading
    a surface the repair did not reach.
"""
import asyncio
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PROTOTYPE, Journal, open_page

from playwright.async_api import async_playwright

# The identity of every button in the bar, as a list of node handles held on
# the page. `isSameNode` is asked on the page rather than in Python, because a
# Playwright element handle survives a re-render and would compare equal to a
# replacement by its selector.
CAPTURE = """() => {
  window.__persistenceProbe = [...document.querySelectorAll('#nav button')];
  return window.__persistenceProbe.length;
}"""

# (f) THE PAGE'S OWN NODES — B-247's surface half. A store write between
# `pointerdown` and `click` replaced a page's DOM nodes and the tap was lost:
# no event, no error. The chrome was held (b, c); a page's rows had the same
# property and nothing read it. Two mechanisms, both repaired in the surfaces:
# React 19 assigns `innerHTML` on the prop OBJECT's identity, so every inline
# `{ __html }` recreated its children on every render (B-295, `ui/markup.tsx`);
# and the library's window was keyed on the store's version, so every bump
# emptied it. The states below cover the two acquisition tabs React draws,
# the library in both modes, and the two screens this lot cut; a floor on the
# nodes captured keeps a state that draws nothing from passing as kept.
PAGE_STATES = (
    ("acq-now-loaded", 10), ("acq-follows-list", 10), ("acq-follows-grid", 10),
    ("lib-list", 10), ("lib-grid", 10), ("mediasheet-series", 10), ("arr-resolution", 10),
)
PAGE_SELECTOR = (
    '#view [data-part="card"], #view [data-part="tile"], #view button, '
    '#view [data-part="pill"], #view img, '
    '[data-part="screen"][data-open] button, '
    '[data-part="screen"][data-open] [data-part="episode/row"], '
    '[data-part="screen"][data-open] [data-part="card"], '
    '[data-part="screen"][data-open] [data-part="key-value"], '
    '[data-part="screen"][data-open] img'
)
PAGE_CAPTURE = """(selector) => {
  window.__pageProbe = [...document.querySelectorAll(selector)];
  return window.__pageProbe.length;
}"""
PAGE_SAME = """(selector) => {
  const before = window.__pageProbe || [];
  const now = [...document.querySelectorAll(selector)];
  const same = before.filter((node, at) => node.isSameNode(now[at])).length;
  return { before: before.length, now: now.length, same,
           lost: before.filter((node) => !node.isConnected).slice(0, 3).map(
             (node) => (node.dataset && node.dataset.part) || node.tagName) };
}"""

SAME = """() => {
  const before = window.__persistenceProbe || [];
  const now = [...document.querySelectorAll('#nav button')];
  return {
    before: before.length,
    now: now.length,
    same: before.length > 0 && before.length === now.length
      && before.every((node, at) => node.isSameNode(now[at])),
  };
}"""


async def main():
    journal = Journal("R100 — the chrome persists, and focus with it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # (a) ONE DOCUMENT, across every state the interface declares.
        #
        # NOT BY COUNTING `performance.getEntriesByType("navigation")`, and the
        # first version of this hold did exactly that. That list holds ONE entry
        # per document — so a full navigation produces a NEW document where the
        # count is one again, and « it stayed at one » is true whether the
        # property holds or not. A reading that cannot come out the other way is
        # not a measurement.
        #
        # WHAT SEPARATES THE TWO IS THE DOCUMENT'S OWN LIFETIME. A sentinel
        # planted on `window` survives every same-document navigation and
        # nothing else, and a real document load raises `load` on the page.
        # Both are read, and BOTH ARE PROVED ALIVE at the end by a navigation
        # made on purpose — a hold asserting « none happened » is worth exactly
        # what its detector is worth.
        #
        # NOT `framenavigated`, which was tried and reads the wrong thing: it
        # fires for a `pushState` too, and the router issues one per arrival —
        # measured at 63 over the 87 states, with the sentinel intact
        # throughout. A counter that moves 63 times while the property holds
        # perfectly is a counter that would have to be given a threshold, and a
        # threshold on a signal that means two things is a number nobody can
        # defend.
        document_loads = []
        page.on("load", lambda _: document_loads.append("load"))
        # AND A RESTORE FROM THE BACK-FORWARD CACHE, which neither of the two
        # above sees: it brings back the SAME `window` — sentinel intact — and
        # fires `pageshow` rather than `load`. A walk out and back is a full
        # navigation this rule would otherwise report clean. It is counted here
        # and read with them.
        await context.add_init_script(
            "window.addEventListener('pageshow', (event) => {"
            " if (event.persisted) window.__restored = (window.__restored || 0) + 1; });")
        states = await page.evaluate("()=>window.__states()")
        journal.check(
            "the interface declares the states this walk covers",
            len(states) > 50,
            f"{len(states)} named state(s)")
        await page.evaluate("()=>{window.__oneDocument = 'planted';}")
        before = len(document_loads)
        for state in states:
            await page.evaluate("(id)=>window.__go(id)", state)
        survived = await page.evaluate("()=>window.__oneDocument ?? null")
        journal.check(
            "no full navigation between any two named states — one document",
            survived == "planted" and len(document_loads) == before
            and await page.evaluate("()=>window.__restored ?? 0") == 0,
            f"sentinel after {len(states)} state(s): {survived!r}; "
            f"{len(document_loads) - before} document load(s), "
            f"{await page.evaluate('()=>window.__restored ?? 0')} bfcache restore(s)")

        # (b) THE BAR'S BUTTONS KEEP THEIR IDENTITY across a page switch.
        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(200)
        captured = await page.evaluate(CAPTURE)
        journal.check(
            "the bar draws its buttons at all — the identity hold has a subject",
            captured == 4,
            f"{captured} button(s) in #nav")
        await page.evaluate("()=>window.__store.write({page: 'lib'})")
        await page.wait_for_timeout(200)
        switched = await page.evaluate(SAME)
        journal.check(
            "a page switch keeps the tab bar's button nodes (P2, B-231)",
            switched["same"],
            f"{switched['before']} before, {switched['now']} after, "
            f"same nodes: {switched['same']}")

        # (c) AND A STORE BUMP, which is what every engine action ends in.
        await page.evaluate("()=>window.__store.touch()")
        await page.wait_for_timeout(200)
        bumped = await page.evaluate(SAME)
        journal.check(
            "a store bump keeps them too (P2, B-231)",
            bumped["same"],
            f"same nodes after a bump: {bumped['same']}")

        # (d) FOCUS SURVIVES BOTH. Focused on the bar, not merely present: the
        # node that holds focus is the node whose replacement loses it.
        await page.evaluate("()=>document.querySelector('#nav button').focus()")
        focused = await page.evaluate(
            "()=>document.activeElement?.dataset?.page ?? null")
        journal.check(
            "focus can be placed on a tab — the hold below has a subject",
            focused is not None,
            f"focus on data-page={focused!r}")
        await page.evaluate("()=>window.__store.write({page: 'arr'})")
        await page.evaluate("()=>window.__store.touch()")
        await page.wait_for_timeout(200)
        # `isSameNode`, NOT the dataset. This hold read `dataset.page`, a
        # `closest('#nav')` and « not body » — every one of which a REPLACEMENT
        # node satisfies, so a bar that re-created its buttons and then focused
        # the equal-looking new one passed it. The rule's own header says
        # `isSameNode` is the only question that separates them; this is that
        # question, asked here too.
        kept = await page.evaluate("""()=>{
          const active = document.activeElement;
          const before = (window.__persistenceProbe || [])[0] || null;
          return {
            same: !!(before && active && before.isSameNode(active)),
            page: active && active.dataset ? active.dataset.page ?? null : null,
            inBar: !!(active && active.closest && active.closest('#nav')),
            body: active === document.body,
          };}""")
        journal.check(
            "focus survives a page switch and a store bump, on the SAME node "
            "(P28, B-231)",
            kept["same"] and kept["inBar"] and not kept["body"],
            f"active element: {kept}")

        # (d-bis) THE MESSAGE'S LIVE REGION IS THE SAME NODE THROUGHOUT, and
        # that is the mechanism rather than tidiness. `role="status"` announces
        # what appears INSIDE a region already in the document; a live region
        # inserted together with its content announces nothing at all. The
        # engine's markup was in `index.html` from the first parse for exactly
        # that reason, and only `#toastmsg` was ever written — a component that
        # mounted the region with its first message would look identical and
        # say nothing to a screen reader.
        # ON A FRESH DOCUMENT, because that is the only place the question can
        # be asked. This page has been open for the whole walk above and the
        # boot hint has come and gone — and the layer keeps a message's text
        # after it closes, deliberately, so the words do not vanish mid-exit.
        # « The region was there before any text » is a fact about the first
        # frames and about nothing else.
        first = await browser.new_context()
        first_page = await first.new_page()
        await first_page.goto(PROTOTYPE, wait_until="load")
        empty = await first_page.evaluate("""()=>{
          const host = document.querySelector('#toast');
          return {present: !!host,
                  text: (document.querySelector('#toastmsg')||{}).textContent ?? null,
                  live: host && host.getAttribute('aria-live'),
                  role: host && host.getAttribute('role')};}""")
        await first.close()
        journal.check(
            "the message's live region is in the document before any text is",
            empty["present"] and empty["live"] == "polite"
            and empty["role"] == "status" and not empty["text"],
            f"region {empty['present']}, role {empty['role']!r}, "
            f"aria-live {empty['live']!r}, text {empty['text']!r}")
        await page.evaluate(
            "()=>{window.__messageProbe = document.querySelector('#toast');}")
        await page.evaluate("()=>window.__toast.show({message: 'probe'})")
        await page.wait_for_timeout(200)
        spoken = await page.evaluate("""()=>{
          const host = document.querySelector('#toast');
          return {same: window.__messageProbe.isSameNode(host),
                  shown: host.hasAttribute('data-shown'),
                  text: (document.querySelector('#toastmsg')||{}).textContent ?? null};}""")
        journal.check(
            "a message appears inside it without the region being replaced",
            spoken["same"] and spoken["shown"] and "probe" in (spoken["text"] or ""),
            f"same node: {spoken['same']}, shown: {spoken['shown']}, "
            f"text {spoken['text']!r}")
        await page.evaluate(
            "()=>window.__toast.show({message: 'undoable', undo: () => {}})")
        await page.wait_for_timeout(200)
        undo = await page.evaluate("""()=>{
          const control = document.querySelector('#toastundo');
          return {present: !!control, tag: control && control.tagName,
                  same: window.__messageProbe.isSameNode(
                    document.querySelector('#toast'))};}""")
        journal.check(
            "the undo is a real control, in the same region",
            undo["present"] and undo["tag"] == "BUTTON" and undo["same"],
            str(undo))
        await page.evaluate("()=>window.__toast.hide()")
        await page.wait_for_timeout(200)

        # (f) THE PAGE'S OWN NODES, across the same bump, on every surface the
        # lot that repaired them cut. `isSameNode` by position, as (b) does: a
        # replacement node satisfies every other question.
        for state, floor in PAGE_STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.evaluate("()=>window.__mocks?.quiet()")
            await page.wait_for_timeout(300)
            captured = await page.evaluate(PAGE_CAPTURE, PAGE_SELECTOR)
            await page.evaluate("()=>window.__store.touch()")
            await page.wait_for_timeout(250)
            kept = await page.evaluate(PAGE_SAME, PAGE_SELECTOR)
            journal.check(
                f"on {state}, the page's own nodes are the SAME nodes after a "
                "store bump (B-247, B-295)",
                captured >= floor and kept["now"] == captured
                and kept["same"] == captured,
                f"{captured} captured (floor {floor}), {kept['now']} after, "
                f"{kept['same']} same; lost: {kept['lost']}")

        # (e) THE POSITIVE CONTROL FOR (a), and it comes LAST because it
        # destroys the document every hold above measures. One real navigation:
        # the sentinel must be gone and the counter must have moved. Without it
        # « none happened » reads the same whether the detectors are alive or
        # dead — which is the shape this repository counts.
        control_before = len(document_loads)
        await page.goto(PROTOTYPE, wait_until="load")
        await page.wait_for_timeout(150)
        gone = await page.evaluate("()=>window.__oneDocument ?? null")
        journal.check(
            "the one-document detectors are alive — a real navigation is seen "
            "by both",
            gone is None and len(document_loads) > control_before,
            f"sentinel after a real navigation: {gone!r}; "
            f"{len(document_loads) - control_before} document load(s) counted")

        await context.close()
        await browser.close()
    journal.summary(errors)


asyncio.run(main())
