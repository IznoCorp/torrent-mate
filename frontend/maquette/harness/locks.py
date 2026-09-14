"""R184 — B-297: what holds the pipeline is DRAWN, and its repair is a path.

THE CLAUSE. §13 asks that one question have one derivation, and §8 that a
« rien » carry its reason. The locks block answers four questions a person acts
on — is the pipeline held, is everything paused, is the automatic trigger
paused, and did a crash leave temporary entries behind — and each is useless
without what makes it decidable: an AGE. « Pris » alone says nothing one can
decide on; « Pris — il y a 4 jours » does.

WHAT IS READ, and the four holds are not the same question:

  1. THE FOUR FACTS ARE DRAWN, each with its own `data-part`, each carrying a
     value. Read on the DOM. A block that draws three of four is the failure
     this hold exists for — the missing one reads as « nothing to report »
     rather than as « not asked ».
  2. THE PENDING SWEEP SKELETONS ITS OWN BLOCK ONLY. Driven through the named
     state where the sweep has not finished: the other three rows still carry
     their values. A skeleton over the whole section would hide three facts
     that have already answered, which is the defect, not thoroughness.
  3. ZERO ORPHANS IS SAID. « Aucune. » — never an empty block. An empty block
     reads as « nothing happened » and §14 asks for « inconnue » over silence.
  4. THE REPAIR IS A PATH, NOT A BUTTON. B-297's own words: the repair stays a
     Maintenance command. So this block offers a cross-reference and no verb of
     its own — no mutating control anywhere inside it.

AND ITS SECOND HALF, THE AGREEMENT. Once the levers exist, the same rule reads
them against these facts: pause is offered only while the pause sentinel is
ABSENT, resume only while it is PRESENT. §13 — one question, one derivation. Two
fields that can disagree is the defect, not something the reader should
reconcile by looking twice.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# THE FIVE STATES THIS BLOCK CAN BE IN, by the id `window.__go` takes. Each is
# a fact of the machine rather than a phase of the read: a held lock, a stale
# one, a sweep still running, entries left behind, and everything free.
FREE = "locks-free"
HELD = "locks-held"
STALE = "locks-stale"
SWEEP_PENDING = "locks-sweep-pending"
ORPHANS = "locks-orphans"

# THE FOUR ROWS, by the `data-part` each carries. Named here so a failure says
# which fact was missing rather than « the block is wrong ».
ROWS = ("locks/pipeline", "locks/pause-sentinel", "locks/watcher-sentinel", "locks/sweep")

# WHAT A ROW SAYS, as the two things a fact row IS: a name and a value, read
# from the emitter's own parts rather than from the row's concatenated text.
# READING THE TEXT WHOLE WAS THE WEAKER HOLD, and it fell on its own arbitrary
# threshold: « Pause » beside « Inactive » reads as `PauseInactive`, which is a
# correct row and a short string. What this rule is about is that each fact
# carries a VALUE — so the value is what it reads.
ROW_FACT = """(part)=>{
  const row = document.querySelector(`[data-part="${part}"]`);
  if (!row) return null;
  const said = (selector) => {
    const node = row.querySelector(selector);
    return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  };
  return {
    name: said('[data-part="flux/name"]'),
    value: said('[data-part="flux/value"]'),
    detail: said('[data-part="flux/detail"]'),
  };
}"""

# THE SWEEP'S BLOCK, read whole: it is a block and not a fact row — it holds a
# row, and under it the entries the sweep found.
SWEEP_TEXT = """()=>{
  const block = document.querySelector('[data-part="locks/sweep"]');
  return block ? (block.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# THE BLOCK'S OWN CONTENT, for the holds that read it whole.
BLOCK_TEXT = """()=>{
  const block = document.querySelector('[data-part="locks"]');
  return block ? (block.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# WHETHER A ROW IS A SKELETON rather than an answer. The skeleton is drawn by
# the shared primitive, so it is read by ITS marker and not by « the row has no
# text »: a row can be empty for reasons that are not a skeleton, and reading
# emptiness would call both the same thing.
IS_SKELETON = """(part)=>{
  const row = document.querySelector(`[data-part="${part}"]`);
  if (!row) return null;
  return Boolean(row.querySelector('[data-skeleton]') || row.matches('[data-skeleton]'));
}"""

# EVERY CONTROL INSIDE THE BLOCK, with what it would ask for. A cross-reference
# is a path — it carries `data-go` or `data-page` and asks the server for
# nothing — and anything else inside this block would be the repair button
# B-297 refuses.
CONTROLS = """()=>[...document.querySelectorAll(
  '[data-part="locks"] button, [data-part="locks"] a')]
  .map((node) => ({
    parts: node.dataset.part || '',
    go: node.dataset.go || node.dataset.page || '',
    text: (node.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60),
  }))"""

# WHAT THE LAYER WAS ASKED FOR, so « the block drew four facts » cannot be true
# of a build that drew them from nothing. Read through the mocks' own record,
# because the layer replaces `fetch` and a request event would never fire.
ASKED = """()=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === 'readLocks')
  .map((call) => call.status + ' ' + call.operationId)"""

# WHETHER A CONTROL IS ON SCREEN, for the agreement half.
PRESENT = """(part)=>Boolean(document.querySelector(`[data-part="${part}"]`))"""

# THE SENTENCE A ZERO WEARS. The interface's own word for « the sweep found
# nothing », which is a real answer and not an absence.
NONE_SAID = "Aucune"


async def drive(journal, page, state):
    """Drives one named state and holds that it is reachable at all.

    AN UNKNOWN ID IS A FALL, NEVER A CRASH. `window.__go` throws on a state the
    table does not declare, and a script that let the exception out would end in
    a traceback with no FAIL line — which reads as the instrument breaking
    rather than as the interface missing the state. So the throw is caught and
    recorded as the hold it is.

    Args:
        journal: The run's journal.
        page: The prototype's page.
        state: The named state's id.

    Returns:
        Whether the state could be driven.
    """
    try:
        await page.evaluate("(id)=>window.__go(id)", state)
        reached = True
        detail = ""
    except Exception as error:  # noqa: BLE001 — the message IS the measurement
        reached = False
        detail = str(error).splitlines()[0]
    journal.check(f"{state} is a state the table declares", reached, detail)
    await page.wait_for_timeout(SETTLED)
    return reached


async def main():
    """Reads the locks block in each of its five states."""
    journal = Journal("R184 — B-297: what holds the pipeline is drawn, "
                      "and its repair is a path")
    async with async_playwright() as playwright:
        # THE INSTALLED CHROME, as every rule here launches: the repository's
        # own browser, never a download this script would have to manage.
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # 1 — THE FOUR FACTS, each with a value, in the ordinary state.
        await drive(journal, page, FREE)
        asked = await page.evaluate(ASKED)
        journal.check("the locks read is asked for", bool(asked), f"{asked}")
        for part in ROWS:
            fact = await page.evaluate(ROW_FACT, part)
            journal.check(f"{part} is drawn and carries a value",
                          bool(fact) and bool(fact["name"]) and bool(fact["value"]),
                          f"{fact!r}")

        # AND THE AGE IS SAID where the fact has one. A held lock without its
        # age is the defect this rule was written for: « Pris » is not a fact
        # anyone can act on.
        await drive(journal, page, HELD)
        held = await page.evaluate(ROW_FACT, "locks/pipeline")
        journal.check("a held lock says so AND says since when",
                      bool(held) and "Pris" in held["value"]
                      and len(held["value"].split("Pris")[-1].strip(" —")) > 2,
                      f"{held!r}")

        await drive(journal, page, STALE)
        stale = await page.evaluate(ROW_FACT, "locks/pipeline")
        journal.check("a stale lock is named as stale, not as held",
                      bool(stale) and "obsolète" in stale["value"], f"{stale!r}")

        # 2 — THE PENDING SWEEP SKELETONS ITS OWN BLOCK, and the other three
        # rows still answer.
        await drive(journal, page, SWEEP_PENDING)
        sweeping = await page.evaluate(IS_SKELETON, "locks/sweep")
        journal.check("the unfinished sweep draws a skeleton", sweeping is True,
                      f"{sweeping}")
        for part in ROWS[:-1]:
            other = await page.evaluate(IS_SKELETON, part)
            fact = await page.evaluate(ROW_FACT, part)
            journal.check(f"{part} still answers while the sweep is pending",
                          other is False and bool(fact) and bool(fact["value"]),
                          f"{fact!r}")

        # 3 — ZERO ORPHANS IS SAID, in the state where the sweep has finished
        # and found nothing.
        await drive(journal, page, FREE)
        sweep = await page.evaluate(SWEEP_TEXT)
        journal.check("a sweep that found nothing says so",
                      bool(sweep) and NONE_SAID in sweep, f"{sweep!r}")

        # AND AN ENTRY IS DRAWN WITH ITS AGE when the sweep found one.
        await drive(journal, page, ORPHANS)
        orphan = await page.evaluate(ROW_FACT, "locks/orphan")
        journal.check("an entry left behind is drawn, with its age",
                      bool(orphan) and bool(orphan["name"])
                      and any(word in orphan["value"]
                              for word in ("jour", "heure", "minute", "instant")),
                      f"{orphan!r}")

        # 4 — THE REPAIR IS A PATH. Every control inside the block leads
        # somewhere; none of them acts.
        controls = await page.evaluate(CONTROLS)
        journal.check("the block offers a way to the repair",
                      any(one["go"] for one in controls), f"{controls}")
        # AND THE HOLD IS NOT VACUOUS: « every control leads somewhere » is also
        # true of a block with no control at all, which is the shape of a green
        # line that measures nothing. The corpus is asserted in the same breath.
        journal.check("and no control inside it acts",
                      bool(controls) and all(one["go"] for one in controls), f"{controls}")

        # 5 — THE AGREEMENT. The levers and these facts answer one question
        # between them, so they cannot say different things about it.
        for state, sentinel_on, offered, hidden in (
            ("levers-running", False, "levers/pause", "levers/resume"),
            ("levers-paused", True, "levers/resume", "levers/pause"),
        ):
            if not await drive(journal, page, state):
                continue
            fact = await page.evaluate(ROW_FACT, "locks/pause-sentinel")
            said_on = bool(fact) and "Activée" in fact["value"]
            journal.check(f"{state}: the pause sentinel reads as the state says",
                          said_on is sentinel_on, f"{fact!r}")
            journal.check(f"{state}: the lever offered agrees with that sentinel",
                          await page.evaluate(PRESENT, offered)
                          and not await page.evaluate(PRESENT, hidden),
                          f"{offered} present={await page.evaluate(PRESENT, offered)}, "
                          f"{hidden} present={await page.evaluate(PRESENT, hidden)}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
