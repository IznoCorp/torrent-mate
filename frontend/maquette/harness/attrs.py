"""How React renders a boolean into an attribute, measured in the live document.

The markup-contracts guard refuses a boolean state attribute written without
`|| undefined` — `data-open={isOpen}`, never `data-open={isOpen || undefined}`.
That refusal rests on one belief about the renderer the maquette bundles, and
the belief has two halves. React turns the boolean `false` into the STRING
`"false"`: the attribute is still PRESENT, so a presence selector such as
`[data-open]` matches it unconditionally — and a hold built on that selector
is green while measuring nothing, because the attribute is never absent. The
other half is the escape: an attribute rendered from `undefined` is omitted
from the markup entirely, which is exactly what the imposed idiom produces.

Nothing in this repository has measured either half. A guard arm that rests
on a belief nobody demonstrated is the exact failure this suite exists to
make loud, so the two halves are demonstrated here, in the live document, on
the attributes the bundled React really renders today: the add screen's
segment buttons (`aria-pressed`, screens/add.tsx), the quality-profile
screen's options and switches (`aria-checked`, screens/profile.tsx), and the
resolution cards' poster `title` (screens/resolution.tsx). Those are `aria-*`
and a standard attribute, not the `data-*` the guard concerns — React routes
all three through the same passthrough, but « the same passthrough » is itself
a belief, so the same four holds are owed a second time, against the real
`data-open`, on the day that attribute first exists. The gap is closed by
re-measuring, not by analogy — and it is closed here: the last four holds read
`data-open` on the sheet layer directly, closed and open, instead of arguing
from the `aria-*` attributes above.

The segments are reached through `[aria-pressed]` — the attribute the hold
measures — never through a class name, because a class anchor added by this
migration would be a fresh entry on the very burn-down list the migration
exists to empty.

Each hold is built to FAIL on an absent subject rather than pass over it: a
probe that returns no element has measured nothing, and a green line printed
over nothing is the defect this rule is the demonstration of.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


# The add screen's segments. Six buttons in two groups, every `aria-pressed`
# rendered from a boolean (screens/add.tsx): `addKind === value` for the three
# kind segments, `idProv === element` for the three provider-id segments.
# Exactly one button per group matches, the others render the boolean `false`.
# The screen answers to its own identity — two screens can carry `open` at
# once, and this rule must measure THIS one. An absent screen reads as zero
# buttons, and every check falls on its own numbers — readable — instead of on
# a TypeError, which is not.
ADD_SCREEN = """() => {
  const s = document.querySelector('[data-part="screen"][data-open][data-key^="add:"]')
    ?? document.createElement('div');
  const segs = [...s.querySelectorAll('[aria-pressed]')];
  const unselected = segs.find(b => b.getAttribute('aria-pressed') === 'false');
  return {
    count: segs.length,
    values: segs.map(b => b.getAttribute('aria-pressed')),
    unselected: unselected ? {
      value: unselected.getAttribute('aria-pressed'),
      present: unselected.hasAttribute('aria-pressed'),
      matches: unselected.matches('[aria-pressed]'),
    } : null,
  };
}"""

# The quality-profile screen's options: five boolean expressions render
# `aria-checked` across radios, checkboxes and switches (screens/profile.tsx).
# Several are false under the default profile — the same trap, second source.
PROFILE_SCREEN = """() => {
  const s = document.querySelector('[data-part="screen"][data-open][data-key^="profile:"]')
    ?? document.createElement('div');
  const opts = [...s.querySelectorAll('[aria-checked]')];
  const unselected = opts.find(b => b.getAttribute('aria-checked') === 'false');
  return {
    count: opts.length,
    values: opts.map(b => b.getAttribute('aria-checked')),
    unselected: unselected ? {
      value: unselected.getAttribute('aria-checked'),
      present: unselected.hasAttribute('aria-checked'),
      matches: unselected.matches('[aria-checked]'),
    } : null,
  };
}"""

# The resolution screen's candidate posters. `title` is rendered from
# `opts.noPoster ? text : undefined` (screens/resolution.tsx): candidates the
# provider has no picture for carry the title, the others carry NOTHING. Only
# the candidate cards are read — a decision card's poster has no `title` prop
# at all, which is a different fact from « rendered from undefined ».
# « Lucky » is the real case that exercises both branches at once: one of its
# five candidates has no provider picture, the other four do.
RESOLUTION_SCREEN = """() => {
  const s = document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"]')
    ?? document.createElement('div');
  const posters = [...s.querySelectorAll('[data-part="card"][data-nonmedia="candidat"] [data-part="card/poster"]')];
  const titled = posters.filter(el => el.hasAttribute('title'));
  const untitled = posters.filter(el => !el.hasAttribute('title'));
  return {
    count: posters.length,
    titled: titled.map(el => el.getAttribute('title')),
    untitled: untitled.map(el => ({
      attr: el.getAttribute('title'),
      matches: el.matches('[title]'),
    })),
  };
}"""


# The sheet layer, whose `data-open` is a `data-*` boolean written through the
# imposed idiom — the very attribute the guard arm concerns, rather than the
# `aria-*` stand-ins the holds above measure. Both `#sheet` and `#scrim` are
# mounted with the shell and rendered always (components/sheet.tsx), so a
# missing element here is a defect, never a closed sheet — every hold below
# asserts the element was FOUND before it asserts anything about its
# attribute. `#scrim` is read too, but only reported: it has TWO writers,
# React for the sheet's own state and the engine for the drawer's and the
# dialog's, so an assertion on it would measure the engine rather than the
# idiom this rule is about.
SHEET_LAYER = """() => {
  const read = (el) => el === null ? null : {
    attr: el.getAttribute('data-open'),
    present: el.hasAttribute('data-open'),
    matches: el.matches('[data-open]'),
  };
  return {
    sheet: read(document.getElementById('sheet')),
    scrim: read(document.getElementById('scrim')),
    selected: document.querySelectorAll('[data-part="sheet"][data-open]').length,
    parts: document.querySelectorAll('[data-part="sheet"]').length,
  };
}"""


async def main():
    global _journal
    _journal = Journal("R80 — how React renders a boolean into an attribute")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        # The two false-boolean subjects, driven by name. Each state renders
        # its screen inside the shell, and the wait is the suite's own idiom
        # for letting that mount settle before reading it.
        await pg.evaluate("()=>window.__go('acq-add-empty')")
        await pg.wait_for_timeout(420)
        add = await pg.evaluate(ADD_SCREEN)

        await pg.evaluate("()=>window.__go('screen-profile')")
        await pg.wait_for_timeout(420)
        prof = await pg.evaluate(PROFILE_SCREEN)

        add_false = add["unselected"]
        prof_false = prof["unselected"]

        # 1. A boolean rendered false still emits the attribute. It is PRESENT
        #    in the markup, not omitted — on both subjects the spec names.
        check("a boolean rendered false still emits the attribute — present, not omitted",
              add["count"] > 0 and add_false is not None and add_false["present"]
              and prof_false is not None and prof_false["present"],
              f"add segments: {add['values']} · "
              f"profile options: {prof['values']}")

        # 2. And its value is the STRING "false" — exact equality, never a
        #    truthiness read, because the string is what a selector sees.
        check("its value is the string \"false\" — exact, never a truthiness read",
              add_false is not None and add_false["value"] == "false"
              and prof_false is not None and prof_false["value"] == "false",
              f"aria-pressed: {add_false['value'] if add_false else None!r} · "
              f"aria-checked: {prof_false['value'] if prof_false else None!r}")

        # 3. The presence selector MATCHES the false-valued attribute. This is
        #    the defect itself: [data-open] would match an attribute whose
        #    value is false, always — a hold built on it measures nothing.
        check("the presence selector matches the false-valued attribute — the trap the guard rests on",
              add_false is not None and add_false["matches"] is True
              and prof_false is not None and prof_false["matches"] is True,
              f"[aria-pressed] matched: "
              f"{add_false['matches'] if add_false else None} · "
              f"[aria-checked] matched: "
              f"{prof_false['matches'] if prof_false else None}")

        # 4. The escape half: an attribute rendered from `undefined` is
        #    ABSENT, and the presence selector does NOT match. The one titled
        #    card in the same document proves the conditional is live — that
        #    its true branch still renders — so the absence measured on the
        #    others is the undefined branch, not a title nobody draws.
        await pg.evaluate("()=>window.__go('arr-decision')")
        await pg.wait_for_timeout(420)
        res = await pg.evaluate(RESOLUTION_SCREEN)
        untitled = res["untitled"]
        check("an attribute rendered from undefined is omitted — [title] does not match it",
              res["count"] >= 1
              and len(res["titled"]) >= 1
              and len(untitled) >= 1
              and all(u["attr"] is None and u["matches"] is False
                      for u in untitled),
              f"{res['count']} candidate posters · {len(res['titled'])} titled "
              f"{res['titled']} · {len(untitled)} untitled: "
              f"attr={[u['attr'] for u in untitled]}, "
              f"matched={[u['matches'] for u in untitled]}")

        # The same four halves, re-measured on the real `data-open` rather
        # than inferred from the `aria-*` ones above. Two named states drive
        # it: one where no layer is up, one that opens the sheet.
        await pg.evaluate("()=>window.__go('acq-now-idle')")
        await pg.wait_for_timeout(420)
        closed = await pg.evaluate(SHEET_LAYER)

        await pg.evaluate("()=>window.__go('sheet-more')")
        await pg.wait_for_timeout(420)
        shown = await pg.evaluate(SHEET_LAYER)

        closed_sheet = closed["sheet"]
        shown_sheet = shown["sheet"]

        # 5. Closed, the attribute is ABSENT — this is `|| undefined` doing
        #    its job on a `data-*`, the half the guard's arm rests on.
        check("data-open rendered from undefined is omitted — absent on the closed sheet",
              closed_sheet is not None and closed_sheet["present"] is False
              and closed_sheet["attr"] is None,
              f"#sheet found: {closed_sheet is not None} · "
              f"attr={closed_sheet['attr'] if closed_sheet else 'NOT FOUND'!r} · "
              f"#scrim attr="
              f"{closed['scrim']['attr'] if closed['scrim'] else 'NOT FOUND'!r}")

        # 6. And the presence selector does not reach it. `parts` proves the
        #    part anchor itself is there — an absent element would score zero
        #    on both counts and pass this hold while measuring nothing.
        check("the presence selector does not match the closed sheet — 0 selected, the anchor still emitted",
              closed_sheet is not None and closed_sheet["matches"] is False
              and closed["selected"] == 0 and closed["parts"] >= 1,
              f"[data-open] matched: "
              f"{closed_sheet['matches'] if closed_sheet else 'NOT FOUND'} · "
              '[data-part="sheet"][data-open] selected '
              f"{closed['selected']} of {closed['parts']} anchored")

        # 7. Open, the attribute is PRESENT. Its value is whatever React
        #    stringifies the true branch into — reported, not asserted: the
        #    contract is presence, and every selector above reads presence.
        check("data-open is present on the open sheet — the true branch emits it",
              shown_sheet is not None and shown_sheet["present"] is True
              and shown_sheet["attr"] is not None,
              f"#sheet found: {shown_sheet is not None} · "
              f"attr={shown_sheet['attr'] if shown_sheet else 'NOT FOUND'!r} · "
              f"#scrim attr="
              f"{shown['scrim']['attr'] if shown['scrim'] else 'NOT FOUND'!r}")

        # 8. And the anchored selector reaches exactly it — the shape a rule
        #    that wants the shown sheet is written with.
        check('[data-part="sheet"][data-open] selects the open sheet'
              ' — the shape a rule selects it with',
              shown_sheet is not None and shown_sheet["matches"] is True
              and shown["selected"] == 1 and shown["parts"] >= 1,
              f"[data-open] matched: "
              f"{shown_sheet['matches'] if shown_sheet else 'NOT FOUND'} · "
              '[data-part="sheet"][data-open] selected '
              f"{shown['selected']} of {shown['parts']} anchored")

        await b.close()

    _journal.summary(errors)


asyncio.run(main())
