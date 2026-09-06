"""R125 — « Récupérer cette saison » really takes the season (B-301).

THE SEASON MATRIX PRINTS A HOLE AND OFFERS NOTHING. `panel-seasons.tsx` draws
one cell per episode and marks a season whose owned count is short of what
aired — « Saison 3 · 6/7 · 1 manquant ». The interface SHOWS what is wanted and
gives no way to ask for it, while
`POST /api/acquisition/follows/{followedId}/seasons/{season}/grab` goes uncalled.
DOIT-3 is « agir là où l'on observe », and this is the clearest place in the
application where one cannot.

⚠ THE HOLE IS NOT A `to_grab` CELL, whatever the lot's brief says. Measured on
2026-09-06: the fixture contains **no `to_grab` episode cell anywhere**, because
`epState` colours a missing episode by the FOLLOW's status and the one follow
with a hole is `pending`. The subject this rule walks is the only one that
exists — « Silo », season 3, six of seven aired episodes held — and it is chosen
from `window.SEASONS` (owned < aired) BEFORE a finger moves, so a failure is
about the interface and never about the walk.

THIS RULE IS WRITTEN BEFORE THE VERB EXISTS and is RED against `main` with no
mutation needed — the strongest form of « seen red first » this repository asks
for, and the form L19 proved the value of on `data-take`: a repair held by
nothing came back with its sign turned round.

WHAT IT READS, and each fails differently:

  1. A SEASON WITH A HOLE OFFERS THE VERB, reached by a FINGER. Not by the
     seam: `window.__panel.produce` opens the panel without walking the path
     that raises it, so a row that had lost its `data-panel` would be invisible
     here while every hold below stayed green. That is the vacuity R124 was
     repaired for, and it is not reproduced.
  2. THE OPERATION IS CALLED, read on the NETWORK. A hold reading the screen
     alone passes a build that toasted and sent nothing — which is exactly what
     « Récupérer maintenant » did for a whole wave under a green gate (B-309).
     The request's own path is read back, so a call to the WRONG season is a
     failure and not a pass.
  3. THE STATE MOVES. The follow leaves the status it had. A message is a
     message and can be right about nothing (NE-DOIT-PAS-1).
  4. NO ERROR IS RAISED — B-309's signature, and the reason a hold reading only
     the counts could pass a build that threw on the way.
  5. UNDER A BUSY PIPELINE the ask is still accepted, says it is QUEUED, and is
     never answered 409 nor dressed as « occupé » (DOIT-4, NE-DOIT-PAS-3, §20).

WHY THE HIT TEST IS COPIED HERE rather than shared: `busy.py` carries the same
helper, and the natural home for a second copy is `common.py` — which cannot be
opened without taking B-325 (no rule can be pointed at a build; `PROTOTYPE` is
hard-coded with no override). A third copy is where that move stops being
optional; this is the second, and it is said out loud so the next reader decides
rather than discovers.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, PANEL_OUT, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE A FOLLOW IS DRAWN WITH A ROW A FINGER CAN REACH. The acquisitions page
# lists what is in FLIGHT, so a followed medium not currently being acquired has
# no row there at all — the correction R124 paid for, taken here from the start.
FOLLOWS_STATE = "acq-follows-list"

# The operation, as the contract names it. The path is matched on these two
# segments rather than on a whole URL, so a parameter spelled differently does
# not turn a real call into a silent miss.
GRAB_PATH = "/seasons/"
GRAB_SUFFIX = "/grab"

# THE WORDS A REFUSAL WEARS. « occupé » is the constitution's own; the others
# are what the same refusal reads like when it is dressed differently.
REFUSALS = ("occupé", "occupee", "occupée", "déjà en cours", "réessayez plus tard")

FOLLOWS = """()=>(window.__followActions?.all() || []).map(
  (one) => ({t: one.t, st: one.st}))"""

# WHICH MEDIUM HAS A SEASON WITH A HOLE, decided from the DATA before a finger
# moves. `window.SEASONS` is `[number, aired, owned]` per season; a hole is
# `owned < aired` — an episode that HAS aired and is not held, which is exactly
# what a season grab is for. An unaired episode is not a hole: it is not out yet.
# The follow must also be drawn on this page, or no finger could reach it.
THE_MEDIUM_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map(
    (one) => one.dataset.panel);
  const reachable = (title) => drawn.some(
    (seen) => seen === title || seen.endsWith(":" + title));
  for (const follow of (window.__followActions?.all() || [])) {
    if (!reachable(follow.t)) continue;
    for (const [number, aired, owned] of (window.SEASONS[follow.t] || [])) {
      if ((owned || 0) < (aired || 0))
        return {title: follow.t, season: number, aired, owned};
    }
  }
  return null;}"""

SAID = """()=>[...document.querySelectorAll('#toast, #view')]
  .map((node) => node.textContent || '').join(' ')"""

# PUTS THE LAYER TO WORK, through the operation the application itself calls.
# `runPipeline` moves the mock's own pipeline state to running (or to queued
# when one is already going), and that is the state the three verbs read to
# decide whether an ask waits. It answers what the state became, so a walk
# cannot believe it succeeded.
RUN_THE_PIPELINE = """async()=>{
  const answer = await window.fetch("/api/pipeline/run", {method: "POST"});
  const body = await answer.json().catch(() => ({}));
  return body.state || "";}"""

# WHAT COVERS THE ROW IS READ, NEVER ASSUMED. `elementFromPoint` at the row's
# own centre answers what a tap there would actually hit, which is a different
# question from « is the node in the tree ».
AIM_AT_THE_ROW = """(title)=>{
  const row = [...document.querySelectorAll('[data-panel]')].find(
    (one) => one.dataset.panel === title
          || one.dataset.panel.endsWith(":" + title));
  if (!row) return {found: false};
  const box = row.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y,
          reachable: !!hit && (hit === row || row.contains(hit)),
          covering: hit === null ? "nothing" :
            (hit.tagName + (hit.className ? "." + String(hit.className).split(" ")[0] : ""))};}"""

# The greeting toast sits over the surface (B-317) and a tap under it lands on
# the toast. No gesture dismisses it, so the element is emptied — said plainly,
# because this walk therefore does not prove the toast can be dismissed, only
# that what is under it is reachable once it is gone.
EMPTY_THE_TOAST = """()=>{const one = document.querySelector('#toast');
  if (!one) return false;
  one.textContent = "";
  one.className = "";
  one.removeAttribute("data-open");
  return true;}"""

# A SEASON THAT HAS A HOLE, and the verb offered on its row.
#
# THE HOLE IS `season/missing`, NOT A `to_grab` CELL, and that correction was
# paid for by a first version of this rule. It looked for an episode cell
# classed `to_grab`, on the brief's own words — « a season printed to_grab » —
# and went red saying « none offered a hole » across all twelve follows. The
# reason was not the missing verb: **the fixture contains no `to_grab` cell at
# all.** `epState` colours a missing episode by the FOLLOW's status, so a follow
# that is `pending` draws its holes `pending`, and every other follow in the
# fixture is `up_to_date` with nothing missing. A rule red for a reason
# unrelated to what it measures is a rule that would still be red after the
# repair, and would then be "fixed" into a green that never read the verb.
#
# What the panel really prints over a hole is `[data-part="season/missing"]` —
# the « N manquants » mark, drawn exactly when owned < aired. That is what a
# season grab is FOR, whatever lifecycle colour the cells happen to wear.
SEASON_WITH_A_HOLE = """()=>{
  const seasons = [...document.querySelectorAll('#sheetin [data-part="season"]')];
  for (const season of seasons) {
    const hole = season.querySelector('[data-part="season/missing"]');
    if (!hole) continue;
    const act = season.querySelector('[data-part="season/grab"]');
    const box = act ? act.getBoundingClientRect() : null;
    const hit = box ? document.elementFromPoint(
      box.left + box.width / 2, box.top + box.height / 2) : null;
    return {
      label: ((season.querySelector("summary") || {}).textContent || "").trim(),
      wanted: (hole.textContent || "").trim(),
      offered: !!act,
      value: act ? (act.dataset.grabseason || "") : "",
      x: box ? box.left + box.width / 2 : 0,
      y: box ? box.top + box.height / 2 : 0,
      reachable: !!hit && (hit === act || (act && act.contains(hit)))};
  }
  return {label: "", wanted: "", offered: false, value: "", reachable: false};}"""


async def raise_by_finger(page, title):
    """Raises a row's panel with a hit-tested tap, and says what it hit.

    Args:
        page: The page.
        title: The subject the row's `data-panel` names.

    Returns:
        The aim's own reading, with `tapped` saying whether a finger went down.
    """
    await page.evaluate(EMPTY_THE_TOAST)
    aim = await page.evaluate(AIM_AT_THE_ROW, title)
    if aim["found"] and aim["reachable"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim


async def open_a_season_panel(page, journal, when):
    """Drives the follows list and raises the panel of the one medium with a hole.

    THE SUBJECT IS CHOSEN FROM THE DATA, AND ONE FINGER GOES TO IT. An earlier
    version tapped every row in turn looking for a hole, and measured itself
    instead of the interface: the FIRST panel it opened covered the rows behind
    it, so `elementFromPoint` at the next row's centre hit the panel, eleven
    taps never landed, and the rule reported « none printing a season with a
    hole » over twelve media it had never actually looked at. Reading
    `window.SEASONS` for a season where owned < aired names the subject before
    any gesture, so the walk is one tap and the failure — if it comes — is about
    the interface rather than about the walk.

    Args:
        page: The page.
        journal: Where the holds are recorded.
        when: What this half is measuring, for the hold's own words.

    Returns:
        The medium's title, and the season reading, or ("", None) when the
        fixture holds no season with a hole, or no finger can raise its panel.
    """
    await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
    await page.wait_for_timeout(SETTLED)
    subject = await page.evaluate(THE_MEDIUM_WITH_A_HOLE)
    journal.check(
        f"the fixture really holds a season with a hole, so this walk has a "
        f"subject — {when}",
        bool(subject), str(subject) or "no follow has owned < aired in window.SEASONS")
    if not subject:
        return "", None
    title = subject["title"]
    aim = await raise_by_finger(page, title)
    journal.check(
        f"« {title} » has a row a finger can raise its panel from",
        aim["tapped"],
        f"found={aim['found']} reachable={aim.get('reachable')} "
        f"at ({aim.get('x')}, {aim.get('y')}) hits {aim.get('covering')}")
    if not aim["tapped"]:
        return "", None
    await page.wait_for_timeout(PANEL_IN)
    season = await page.evaluate(SEASON_WITH_A_HOLE)
    if not season["label"]:
        journal.check(
            f"and the panel it raises PRINTS that hole — season "
            f"{subject['season']}, {subject['owned']} of {subject['aired']}",
            False, "the panel drew no season carrying a missing mark")
        return "", None
    return title, season


async def main():
    journal = Journal("R125 — « Récupérer cette saison » really takes the season")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        asked: list[str] = []
        refused: list[str] = []
        page.on("request", lambda call: asked.append(call.url)
                if GRAB_PATH in call.url and call.url.endswith(GRAB_SUFFIX) else None)
        page.on("response", lambda answer: refused.append(
            f"{answer.status} {answer.url}") if answer.status == 409 else None)

        # ── THE VERB, ON AN IDLE PIPELINE ──────────────────────────────────
        title, season = await open_a_season_panel(page, journal, "the pipeline idle")
        if season is not None:
            journal.check(
                f"« {title} » prints a season with a hole — {season['label']}",
                bool(season["wanted"]), season["wanted"] or "no mark drawn")
            journal.check(
                "and that season OFFERS to be taken, on a button a finger reaches "
                "(DOIT-3, B-301)",
                season["offered"] and season["reachable"],
                f"offered={season['offered']} reachable={season['reachable']} "
                f"value={season['value']!r}")
            was = await page.evaluate(
                "(t)=>(window.__followActions?.all() || []).find((one) => one.t === t)?.st",
                title)
            errors.clear()
            asked.clear()
            if season["offered"] and season["reachable"]:
                await page.touchscreen.tap(season["x"], season["y"])
                await page.wait_for_timeout(ACTED)
            # THE OPERATION IS CALLED, and the call is read on the NETWORK. A
            # hold reading the screen alone passes a build that toasted and
            # sent nothing.
            journal.check(
                "the season grab OPERATION is called — read on the network, not "
                "on the screen (B-301)",
                len(asked) == 1, f"{len(asked)} call(s): {asked[:2]}")
            # AND FOR THE SEASON THE FINGER WAS ON. A call to the wrong season
            # is a call, and a hold counting calls alone would take it.
            wanted_season = season["value"].split("|")[-1] if season["value"] else ""
            journal.check(
                "and it names the season the finger was on, not another",
                bool(wanted_season) and any(
                    call.endswith(f"/seasons/{wanted_season}/grab") for call in asked),
                f"season {wanted_season!r} against {asked[:2]}")
            journal.check(
                "tapping it raises no error",
                not errors, str(errors))
            now = await page.evaluate(
                "(t)=>(window.__followActions?.all() || []).find((one) => one.t === t)?.st",
                title)
            journal.check(
                "and the STATE moves — the act lands, it is not a message about "
                "an act (NE-DOIT-PAS-1)",
                now is not None and now != was, f"{title}: {was} → {now}")

        # ── AND UNDER A BUSY PIPELINE, where the clause bites ──────────────
        #
        # THE LAYER IS PUT TO WORK THROUGH ITS OWN OPERATION, and both truths
        # are set because there are two. The engine's `pipe` field drives the
        # DRAWING; the mock layer's `pipelineState` is what decides `queued` in
        # the answer. A walk that wrote only the store would leave the layer
        # idle and read a queued flag nobody set — the hold would be green over
        # nothing. `runPipeline` is the operation the application itself calls,
        # so this drives the layer rather than reaching past it.
        # THE FIRST HALF'S PANEL IS CLOSED FIRST, and its scrim with it. Left
        # open, the panel covers the follows list and `elementFromPoint` at the
        # row's centre answers `DIV.scrim` — the second half then failed on the
        # tap it never landed rather than on the clause it exists to read, which
        # is a rule measuring its own leftovers.
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(PANEL_OUT + SETTLED)
        started = await page.evaluate(RUN_THE_PIPELINE)
        await page.evaluate("""()=>window.__store.write({pipe: "running"})""")
        await page.wait_for_timeout(SETTLED)
        journal.check(
            "the LAYER really has the pipeline busy — the half that decides "
            "whether an ask is queued",
            started in ("running", "queued"), str(started))
        journal.check(
            "and the interface is drawing it busy too, so this half measures "
            "the clause and not the verb",
            await page.evaluate("()=>window.__store.read().state.pipe") == "running")
        busy_title, busy_season = await open_a_season_panel(
            page, journal, "the pipeline busy")
        if busy_season is not None:
            asked.clear()
            errors.clear()
            if busy_season["offered"] and busy_season["reachable"]:
                await page.touchscreen.tap(busy_season["x"], busy_season["y"])
                await page.wait_for_timeout(ACTED)
            journal.check(
                f"« {busy_title} »'s season can still be asked for while the "
                "pipeline runs — the ask is ACCEPTED (NE-DOIT-PAS-3)",
                len(asked) == 1, f"{len(asked)} call(s)")
            said = (await page.evaluate(SAID)).lower()
            journal.check(
                "and the interface says it is IN FILE — DOIT-4's own words, "
                "« En file — pipeline en cours »",
                "en file" in said,
                said[-160:] if said else "nothing said")
            journal.check(
                "never « occupé », nor any other dress of the same refusal",
                not any(word in said for word in REFUSALS),
                next((word for word in REFUSALS if word in said), ""))

        journal.check(
            "and no ask anywhere was answered 409 (NE-DOIT-PAS-3)",
            not refused, str(refused[:3]))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
