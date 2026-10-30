"""R401 — a settled decision is read on its medium's journey sheet (L24 S1, OPEN 1 = C).

The operator's ruling: « Les décisions ne peuvent t'elle pas vivre sur la carte
d'un média d'acquisions ? », then « C ». No list of decisions, no screen: the
journey sheet of a medium whose identification is behind it says what was
chosen, among how many candidates, by whom — the operator or the engine — and
when. A decision left as it was says its own sentence in the choice's place.

WHAT IS READ, every expected word from the ONE settled read the layer answered
(`/api/v1/decisions/` in the query cache) and from `fr.json`, never retyped:

  1. `sheet-journey-decision-operator` — the choice (title · PROVIDER id), the
     candidates' count, « vous — <how it was reached> », the date;
  2. `sheet-journey-decision-engine` — the same rows, the author the engine's;
  3. `sheet-journey-decision-dismissed` — the state word in the choice's place,
     and the state's sentence;
  4. `sheet-journey` — identification still running (« identifié » now): no
     block;
  5. on those sheets, the rung « identifié » is drawn done, and never with the
     running rung's words (« en cours depuis … ») — a done rung borrowed the
     template's time while the mock laid it done — nor with « — », which says
     nothing lived: a done rung with no time recorded says « fait »
     (orchestrator, 2026-10-01);
  5b. each sheet names the release of ITS OWN acquisition — its decision's
     folder — never another medium's (the reader, 2026-10-01: President
     Curtis's journey read « release Furious.S01E01… »);
  6. a medium whose decision is PENDING (« Lucky », an « À traiter » card), its
     ladder laid past identification: no block — its card opens the arbitration;
  7. that decision settled now (`resolveDecision`, « Choisir »): the block's
     date is the settling's, never the pending decision's creation — RE-AIMED
     (reader, 2026-10-01): it read « 15 juillet », older than the card's
     « arrivé », for a choice just made.
"""
import asyncio
import json
import pathlib

from common import Journal, open_page, read_at, browser_channel, chrome_launch_args, PANEL_IN, SETTLED
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
BLOCK = WORDS["surfaces"]["decision"]
RESOLUTION = WORDS["screens"]["resolution"]

STATES = (
    ("sheet-journey-decision-operator", "President Curtis"),
    ("sheet-journey-decision-engine", "Furious"),
    ("sheet-journey-decision-dismissed", "The Alabama Solution"),
)

IDENTIFIED = WORDS["surfaces"]["ladder"]["rungs"]["identified"]
NO_TIME = "—"
RUNNING = [stage["when"] for stage in json.loads((SOURCE / "mocks/seeds/journey-stages.json").read_text(encoding="utf-8"))
           if stage["state"] == "now"]

READ = """(subject) => {
  const IDENTIFIED = %s;
  const sheet = document.querySelector('#sheet[data-open]');
  const block = sheet?.querySelector('[data-part="decision"]');
  const rows = {};
  block?.querySelectorAll('[data-decision-part]').forEach((row) => {
    const spans = row.querySelectorAll(':scope > span');
    rows[row.dataset.decisionPart] = spans.length ? spans[spans.length - 1].textContent.trim() : row.textContent.trim();
  });
  const identified = [...(sheet?.querySelectorAll('[data-part="key-value"]') ?? [])]
    .find((row) => row.querySelector('span')?.textContent.trim() === IDENTIFIED);
  const answer = window.__queries.getQueryData(['/api/v1/decisions/']);
  return {open: !!sheet, block: !!block, rows,
          meta: sheet?.querySelector('[data-part="sheet/meta"]')?.textContent.trim() ?? '',
          identified: identified ? {tone: identified.querySelector('[data-part="status-dot"]')?.dataset.tone,
                                    value: identified.querySelectorAll(':scope > span')[1]?.textContent.trim()} : null,
          settled: answer?.settled.find((one) => one.title === subject || one.choice?.title === subject) ?? null};
}""" % json.dumps(IDENTIFIED)


def count_words(count):
    """The block's words for a candidates' count, from the resources.

    Args:
        count: The decision's candidates' count.

    Returns:
        The phrase the block must draw.
    """
    key = "candidates_one" if count == 1 else "candidates_other"
    return BLOCK[key].replace("{{count}}", str(count))


def expected(decision):
    """What the block must say for one settled decision, from its data alone.

    Args:
        decision: The settled decision, as the layer answered it.

    Returns:
        The rows keyed by their part.
    """
    rows = {"count": count_words(len(decision["candidates"])), "when": decision["when"]}
    if decision["state"] == "resolved" and decision.get("choice"):
        choice = decision["choice"]
        rows["choice"] = f"{choice['title']} · {choice['provider'].upper()} {choice['id']}"
    else:
        rows["state"] = RESOLUTION["decisionState"][decision["state"]]
        rows["sentence"] = RESOLUTION["decisionStateDetail"][decision["state"]]
    choice = decision.get("choice")
    rows["author"] = (BLOCK["byEngine"] if decision["settledBy"] == "engine"
                      else BLOCK["byOperator"].replace("{{via}}", RESOLUTION["via"][choice["via"]]) if choice
                      else BLOCK["byOperatorAlone"])
    return rows


async def main():
    journal = Journal("R401 — a settled decision is read on its medium's journey sheet")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        authors = set()
        for state, subject in STATES:
            seen = await read_at(page, state, READ, subject, wait=PANEL_IN + SETTLED)
            journal.check(f"{state}: the journey sheet draws the decision block",
                          seen["open"] and seen["block"], str({k: seen[k] for k in ("open", "block")}))
            if seen["settled"] is None:
                journal.check(f"{state}: the layer holds a settled decision for « {subject} »", False)
                continue
            authors.add(seen["settled"]["settledBy"])
            wanted = expected(seen["settled"])
            for part, words in wanted.items():
                journal.check(f"{state}: « {part} » reads « {words} »", seen["rows"].get(part) == words,
                              repr(seen["rows"].get(part)))
            journal.check(f"{state}: nothing drawn beyond what the decision says",
                          set(seen["rows"]) == set(wanted), str(sorted(seen["rows"])))
            rung = seen["identified"] or {}
            journal.check(f"{state}: « {IDENTIFIED} » drawn done, not with the running rung's words",
                          rung.get("tone") == "success" and rung.get("value") not in RUNNING, str(rung))
            journal.check(f"{state}: « {IDENTIFIED} » done says so in words, never « {NO_TIME} »",
                          rung.get("value") not in (NO_TIME, None, ""), str(rung))
            journal.check(f"{state}: the sheet names the release of its own acquisition",
                          seen["meta"].endswith(seen["settled"]["folder"]),
                          f"meta {seen['meta']!r}, its decision's folder {seen['settled']['folder']!r}")
        journal.check("the three states cover both authors", authors == {"operator", "engine"}, str(authors))

        running = await read_at(page, "sheet-journey", READ, "Furious", wait=PANEL_IN + SETTLED)
        journal.check("sheet-journey: identification still running, no block",
                      running["open"] and not running["block"], str(running["block"]))

        await page.evaluate("""() => { window.__mocks.reset(); window.__mocks.placeAtPlexCheck('Lucky');
                                      window.__panel.produce('journey', 'Lucky'); }""")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        pending = await page.evaluate(READ, "Lucky")
        journal.check("a medium whose decision is pending draws no block",
                      pending["open"] and not pending["block"], str(pending["block"]))

        waited = await page.evaluate("""async () => {
          const pending = window.__queries.getQueryData(['/api/v1/decisions/']).pending.find((one) => one.folder === 'Lucky');
          const kept = pending.candidates[0];
          await fetch('/api/v1/decisions/Lucky/resolve', {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({provider: kept.provider, providerId: kept.id})});
          await window.__queries.refetchQueries({queryKey: ['/api/v1/decisions/']});
          window.__panel.close(); window.__panel.produce('journey', 'Lucky');
          return {when: pending.when};
        }""")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        chosen = await page.evaluate(READ, "Lucky")
        seeded = {decision["when"] for decision in json.loads(
            (SOURCE / "mocks/seeds/settled-decisions.json").read_text(encoding="utf-8"))}
        journal.check("a decision settled now reads now, never the pending decision's creation",
                      chosen["block"] and chosen["rows"].get("when") not in {waited["when"], "", None} | seeded,
                      f"block {chosen['rows'].get('when')!r}, pending since {waited['when']!r}")

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
