"""R66 — Arrivées carries the PIPELINE's health, and says what really happened.

The cut this page obeys is by the nature of the trouble: a medium in trouble is
Arrivées, a machine in trouble is Système. That is what puts the run controls
here — DOIT-3, act where one observes — beside the stalled step they answer,
rather than one page away from it.

What this holds to:

1. The pilot's bar offers ONE control, and it is the right one for the state.
   Asked while a run is going, a run is QUEUED and says so (DOIT-4): « occupé,
   réessaie » is the answer this interface does not give.
2. All NINE steps the engine runs are drawn, in the engine's order, each named
   for what it does with the engine's own name beside it in the mono face
   (DOIT-1) — so a log can be read without a translation table.
3. A step that did nothing says so with an em dash, never « 0 ». And a step
   that did have something to look at never wears the em dash, or the row
   contradicts its own sub-line.
4. The step that BLOCKS points at what is stuck, on this page, rather than at a
   log.
5. **The run told here really happened.** Its counts are compared against
   `pipeline_run` in `library.db`, by run_uid — not against the last run, which
   would make this rule rot every time the pipeline fires (R63 rots exactly
   that way, and it is a seam rather than a defect). A past run does not
   change; inventing one is what this catches.
6. Nothing overflows a 390px frame in any of the three states.
"""
import asyncio
import json
import os
import pathlib
import sqlite3

from common import Journal, open_page
from playwright.async_api import async_playwright

LIBRARY = pathlib.Path(os.path.expanduser("~/dev/PersonalScraper/.data/library.db"))

# The engine's steps, in `DEFAULT_STEPS` execution order (docs/reference/
# commands.md § Pipeline). Written here rather than read from the prototype:
# a rule that takes its expectation from what it measures agrees with anything.
ENGINE_STEPS = ["ingest", "sort", "clean", "scrape", "cleanup",
                "enforce", "verify", "trailers", "dispatch"]

READ = """() => {
  const port = document.querySelector('#port');
  return {
    overflow: port.scrollWidth - port.clientWidth,
    status: (document.querySelector('.pipeline .pt') || {}).textContent || '',
    buttons: [...document.querySelectorAll('.pipeline [data-pipe]')]
               .map((b) => b.dataset.pipe),
    queued: !!document.querySelector('.pipeline .live'),
    uid: (window.PIPELINE_UID_POUR_LA_SONDE || null),
    steps: [...document.querySelectorAll('.flux [data-part="flux/row"]')].map((x) => ({
      name: x.querySelector('[data-part="flux/name"]').textContent.trim(),
      result: x.querySelector('[data-part="flux/value"]').textContent.trim(),
      sub: x.querySelector('[data-part="flux/detail"]').textContent.trim(),
      key: (x.querySelector('[data-part="flux/key"]') || {}).textContent || '',
      empty: x.hasAttribute('data-empty'),
      blocked: x.hasAttribute('data-blocked'),
    })),
    sections: [...document.querySelectorAll('[data-part="section/head"] .t')].map((x) => x.textContent.trim()),
  };
}"""


def real_run(uid):
    """The run `library.db` really recorded under this uid, or None.

    Args:
        uid: The run_uid prefix the prototype prints.

    Returns:
        A dict step name → its recorded counts, or None when the database is
        absent or holds no such run.
    """
    if not LIBRARY.is_file():
        return None
    db = sqlite3.connect(f"file:{LIBRARY}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    row = db.execute(
        "SELECT run_uid, trigger, steps_json FROM pipeline_run "
        "WHERE run_uid LIKE ? AND kind = 'pipeline'", (uid + "%",)).fetchone()
    db.close()
    if row is None:
        return None
    steps = {s["name"]: s for s in json.loads(row["steps_json"] or "[]")}
    return {"trigger": row["trigger"], "steps": steps}


async def on_arrivals(pg, pipe="idle"):
    """Drives to Arrivées in one of the pipeline's three states."""
    # THROUGH THE STORE, never by mutating the engine's alias in place: this
    # page is drawn by the shell now, and a component reads the store. An
    # in-place write leaves the object's identity unchanged, so React never
    # re-renders and the measurement lands on whatever page was drawn before —
    # measured, not assumed: it read the acquisition page's roots.
    await pg.evaluate(
        f"()=>{{window.__store.write({{page: 'arr', pipe: '{pipe}'}}); render();}}")
    await pg.wait_for_timeout(320)
    return await pg.evaluate(READ)


async def main():
    journal = Journal("R66 — Arrivées carries the pipeline's health")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # The uid and the counts the prototype claims, read from its own data
        # rather than scraped off the screen — the screen is what is being
        # judged against them.
        claimed = await pg.evaluate("()=>({uid: PIPELINE.last.uid,"
                                    " decl: PIPELINE.last.declencheur,"
                                    " facts: PIPELINE.last.facts})")

        view = await on_arrivals(pg, "idle")

        # ── 1. the pilot's bar ─────────────────────────────────────────────
        journal.check("at rest, a single command, and it is « lancer »",
                      view["buttons"] == ["start"], str(view["buttons"]))
        journal.check("at rest, the state is named", view["status"] == "Au repos",
                      view["status"])

        # The journey, not a named state. Both of the following are reached by
        # TAPPING, because a queue nobody can reach by a gesture is a branch no
        # gesture can enter — and driving `state.pipe` straight to it would
        # certify exactly that. The first version of this rule did.
        await pg.tap('.pipeline [data-pipe="start"]')
        await pg.wait_for_timeout(350)
        running = await pg.evaluate(READ)
        journal.check("pressing « lancer » sets the pipeline running",
                      running["status"] == "En cours", running["status"])
        journal.check("while running, another pass can still be ASKED for",
                      "start" in running["buttons"] and "stop" in running["buttons"],
                      str(running["buttons"]))
        journal.check("while running, nothing claims a pass is already queued",
                      not running["queued"])

        await pg.tap('.pipeline [data-pipe="start"]')
        await pg.wait_for_timeout(350)
        queued = await pg.evaluate(READ)
        journal.check("a pass asked for DURING another is queued, and says so",
                      queued["queued"], f"queued={queued['queued']} buttons={queued['buttons']}")
        journal.check("and it is not refused: the running pass carries on",
                      queued["status"] == "En cours" and "stop" in queued["buttons"],
                      f"{queued['status']} · {queued['buttons']}")

        await pg.tap('.pipeline [data-pipe="stop"]')
        await pg.wait_for_timeout(350)
        stopped = await pg.evaluate(READ)
        journal.check("« arrêter » brings it back to rest", stopped["status"] == "Au repos",
                      stopped["status"])

        # ── 2. the nine steps, in the engine's order ───────────────────────
        view = await on_arrivals(pg, "idle")
        keys = [e["key"] for e in view["steps"]]
        journal.check("the engine's nine steps are drawn, in its order",
                      keys == ENGINE_STEPS, str(keys))
        journal.check("every step carries a French name besides the engine's",
                      all(e["name"] and e["name"] != e["key"] for e in view["steps"]),
                      str([e["name"] for e in view["steps"]]))

        # ── 3. nothing to do says so, and never with a zero ────────────────
        zeros = [e["name"] for e in view["steps"] if e["result"] == "0"]
        journal.check("no step answers « 0 »", not zeros, str(zeros))
        silent = [e["name"] for e in view["steps"] if e["result"] == "—"]
        journal.check("a step with nothing to do carries a dash", silent,
                      f"{len(silent)}: {', '.join(silent)}")
        # An em dash beside a sub-line that describes work is a row arguing
        # with itself. The engine name always sits in the sub-line, so what is
        # looked for is anything BEYOND it.
        contradictions = [
            e["name"] for e in view["steps"]
            if e["result"] == "—" and e["sub"].replace(e["key"], "").strip(" ·")
            not in ("", "rien à faire")]
        journal.check("no step says « nothing » beside what it did",
                      not contradictions, str(contradictions))

        # ── 4. what blocks points at what is stuck ─────────────────────────
        blocking = [e for e in view["steps"] if e["blocked"]]
        journal.check("the step that blocks is flagged", len(blocking) == 1,
                      str([e["name"] for e in blocking]))
        if blocking:
            journal.check("and it points back to what is stuck, on this page",
                          "coince" in blocking[0]["sub"], blocking[0]["sub"])
        journal.check("« Ça coince » is indeed on the page",
                      "Ça coince" in view["sections"], str(view["sections"]))
        journal.check("and « Arrivé dans les 24 h » too",
                      "Arrivé dans les 24 h" in view["sections"], str(view["sections"]))

        # ── 5. the run told here really happened ───────────────────────────
        real = real_run(claimed["uid"])
        if real is None:
            journal.check("the run told about exists in library.db", False,
                          f"no run {claimed['uid']}… "
                          + ("(database absent)" if not LIBRARY.is_file() else ""))
        else:
            journal.check("the run told about exists in library.db", True,
                          f"{claimed['uid']}… · {real['trigger']}")
            journal.check("the trigger is the one the database recorded",
                          claimed["decl"] == real["trigger"],
                          f"{claimed['decl']} vs {real['trigger']}")
            # Every count the prototype prints is checked against the step the
            # engine recorded. Only the numbers are compared: the sentence is
            # the interface's business, the figure is the engine's.
            gaps = []
            for fact in claimed["facts"]:
                step = real["steps"].get(fact["n"])
                if step is None:
                    gaps.append(f"{fact['n']} absent from the database")
                    continue
                for text in (fact.get("r") or "", fact.get("s") or ""):
                    for word in text.split():
                        if word.isdigit():
                            n = int(word)
                            if n not in (step.get("success_count"),
                                         step.get("skip_count"),
                                         step.get("error_count")):
                                gaps.append(f"{fact['n']}: {n} is none of "
                                            f"{step.get('success_count')}/"
                                            f"{step.get('skip_count')}/"
                                            f"{step.get('error_count')}")
            journal.check("every figure shown is a figure of the real run",
                          not gaps, "; ".join(gaps) or "all agree")

        # ── 6. nothing overflows, in any state ─────────────────────────────
        for name, measure in (("at rest", view), ("running", running), ("queued", queued)):
            journal.check(f"nothing spills past the frame {name}", measure["overflow"] <= 0,
                          f"{measure['overflow']}px")

        journal.check("no JS error", not errors, str(errors))
        await ctx.close()
        await b.close()

    journal.summary()


asyncio.run(main())
