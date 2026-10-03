"""R422 — Acquisition is the account's own: its lists, its counts, its acts (§ 17).

DESIGN maquette-l18 § 3.4, § 5 (R-L18-g, R-L18-h, R-L18-k), F33, F65, round 9 Q16.

1. R-L18-g — THE LISTS ARE THE ACCOUNT'S: a household member reads only the acquisitions it
   is among the requesters of; a role that sees everyone's reads them all, and « À traiter »'s
   count and the bar's badge count ITS OWN cards only — never another's read-only card.
2. F65 — THE « ＋ » ASKS FOR A MEDIUM: offered to a household member, absent for a role that
   only sees.
3. R-L18-k — OWN TUNNEL, BOTH SIDES: a card another account asked for opens a journey panel
   without the tunnel's verbs, and forcing « Remettre en file » on it answers 403; on the
   account's own card the verb is offered and the call is not refused. A household member's
   « À traiter » card carries no foot of the pipeline's decisions (`pipeline.control`).
4. Round 9 Q16 — A CARD SEVERAL ACCOUNTS ASKED FOR NAMES THEM ALL on its line.
5. R-L18-x — A COLD BOOT LANDS ON THE REMEMBERED TAB: before the account is read nothing is
   known to be closed, so the owner's first Acquisition is « Suivis », not a fallback.
6. R-L18-h — THE SECTION ABSENT: a Default-only account has no Acquisition in the bar and none
   in the drawer.

WHAT IT DOES NOT READ: reassigning (R283), quality and pause (R284).
"""
import asyncio

from common import SETTLED, PANEL_IN, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

OWN_CARD = "Star Trek: Strange New Worlds (2022)"
FOREIGN_CARD = "Lucky"

CARDS = """() => [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-panel]')]
  .filter((one) => !one.hasAttribute('aria-label'))
  .map((one) => one.dataset.panel.slice(one.dataset.panel.indexOf(':') + 1))"""
ANSWER = """async (who) => {
  const queue = await (await fetch('/api/v1/acquisition/to-handle')).json();
  const follows = await (await fetch('/api/v1/acquisition/followed')).json();
  const rows = [...Object.values(queue).flat(), ...follows];
  return { all: rows.length, others: rows.filter((row) => !(row.requesters || []).some((one) => one.id === who))
    .map((row) => row.title) };
}"""
COUNTS = """() => ({
  tab: Number(document.querySelector('[data-acqtab="todo"] [data-part="segment/count"]')?.textContent || 0),
  badge: Number(document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]')?.textContent || 0),
  fab: !document.querySelector('#fab')?.hidden })"""
# A MESSAGE HIDES THE « ＋ » while it is shown (R86), so the button is read once
# no message stands and none is still owed. F65 read red in CI with the right
# held ({'tab': 0, 'badge': 0, 'fab': False}, run 36831342708): the welcome hint
# is armed at the module's evaluation with 900 ms, this read starts about 750 ms
# after `load`, and a hint landing just after the loop looked hid the button at
# the read — reproduced by moving the hint's delay to 950 ms. The session's
# first touch is what stops it for good (`harness/panel.ts`), so the loop
# starts with one. Two neighbours of the same race are closed with it:
# - the button comes back AFTER_A_MESSAGE_MS (200 ms) after the message has
#   left, counted from React's commit, not from the click — 250 ms after the
#   click left a slow runner 50 ms of margin. The read waits past the hold;
# - the account the state signed in is read again (`as()`), and until it is the
#   rights are none.
QUIET = """async (who) => {
  const pause = (ms) => new Promise((settle) => setTimeout(settle, ms));
  document.dispatchEvent(new PointerEvent('pointerdown'));
  for (let i = 0; i < 40 && document.querySelector('#toast[data-shown]'); i += 1) {
    document.querySelector('#toastx')?.click(); await pause(250); }
  for (let i = 0; i < 40 && window.__queries.getQueryData(['/api/v1/auth/me'])?.id !== who; i += 1) await pause(100);
  await pause(300);
  await new Promise((settle) => requestAnimationFrame(() => requestAnimationFrame(settle))); }"""
PANEL_VERBS = """() => [...document.querySelectorAll('#sheet [data-journey-requeue], #sheet [data-journey-rescrape]')]
  .map((one) => one.getAttribute('data-journey-requeue') ? 'requeue' : 'rescrape')"""
FORCE_REQUEUE = """async ([who, title]) => { window.__mocks.setIdentity(who);
  return (await fetch('/api/v1/acquisition/journeys/' + encodeURIComponent(title) + '/requeue', { method: 'POST' })).status; }"""


async def main():
    journal = Journal("R422 — Acquisition is the account's own")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def go(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)

        tab = await page.evaluate("()=>window.__store.read().state.acqTab")
        journal.check("R-L18-x: a cold boot lands the owner on the remembered tab, « Suivis »", tab == "follows",
                      str(tab))

        await go("acq-household")
        await page.evaluate(QUIET, "household-member")
        member = await page.evaluate(ANSWER, "household-member")
        journal.check("R-L18-g: a household member reads only the acquisitions it asked for",
                      member["all"] > 0 and not member["others"], str(member))
        counts = await page.evaluate(COUNTS)
        journal.check("F65: the « ＋ » is offered to a household member", counts["fab"], str(counts))

        await go("acq-household-sees-all")
        seer = await page.evaluate(ANSWER, "household-member-sees-all")
        journal.check("R-L18-g: a role that sees everyone's reads others' acquisitions too",
                      len(seer["others"]) > 0, f"{len(seer['others'])} of {seer['all']} not its own")
        await page.evaluate("()=>window.__store.write({ acqTab: 'todo' })")
        await page.wait_for_timeout(SETTLED)
        drawn = await page.evaluate(CARDS)
        own = [title for title in drawn if title not in seer["others"]]
        counts = await page.evaluate(COUNTS)
        journal.check("R-L18-g: « À traiter » draws another's card and does not count it",
                      any(title in seer["others"] for title in drawn) and counts["tab"] == len(own),
                      f"drawn {drawn}, own {own}, tab {counts['tab']}")
        journal.check("R-L18-g: the bar's badge counts what the tab counts", counts["badge"] == counts["tab"],
                      str(counts))

        await go("acq-see-only")
        await page.evaluate(QUIET, "see-only")
        counts = await page.evaluate(COUNTS)
        journal.check("F65: a role that only sees has no « ＋ »", not counts["fab"], str(counts))

        await go("acq-card-read-only", PANEL_IN + SETTLED)
        foreign = await page.evaluate(PANEL_VERBS)
        journal.check("R-L18-k: another account's card opens its journey without the tunnel's verbs",
                      await page.evaluate("()=>!!document.querySelector('#sheet')?.textContent") and not foreign,
                      str(foreign))
        refused = await page.evaluate(FORCE_REQUEUE, ["household-member-sees-all", FOREIGN_CARD])
        journal.check("R-L18-k: forcing « Remettre en file » on another's card answers 403", refused == 403,
                      str(refused))
        await go("acq-household")
        await page.evaluate("(title)=>window.__panel.produce('journey', title)", OWN_CARD)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        mine = await page.evaluate(PANEL_VERBS)
        journal.check("R-L18-k: the account's own card offers the tunnel's verbs", "requeue" in mine, str(mine))
        allowed = await page.evaluate(FORCE_REQUEUE, ["household-member", OWN_CARD])
        journal.check("R-L18-k: « Remettre en file » on its own card is not refused", allowed != 403, str(allowed))

        await go("acq-household")
        await page.evaluate("()=>window.__store.write({ acqTab: 'todo' })")
        await page.wait_for_timeout(SETTLED)
        feet = await page.evaluate("""() => [...document.querySelectorAll('#view [data-part="card/foot"]')]
          .flatMap((one) => [...one.attributes].map((attribute) => attribute.name))
          .filter((name) => ['data-resolution', 'data-plex-confirm', 'data-staging-delete', 'data-journey-abandon']
          .includes(name))""")
        journal.check("R-L18-k: a household member's « À traiter » card carries none of the pipeline's decisions", not feet,
                      str(feet))

        await go("acq-card-plural-requesters")
        text = await page.evaluate("()=>document.querySelector('#view')?.textContent || ''")
        await page.evaluate("()=>window.__store.write({ acqTab: 'todo' })")
        await page.wait_for_timeout(SETTLED)
        text += await page.evaluate("()=>document.querySelector('#view')?.textContent || ''")
        journal.check("round 9 Q16: a card several accounts asked for names them all",
                      "demandé par izno et Noé" in text, "found" if "demandé par izno et Noé" in text else text[:200])

        await go("bar-rightless")
        places = await page.evaluate("""() => ({
          bar: [...document.querySelectorAll('#nav button[data-page]')].map((one) => one.dataset.page),
          drawer: [...document.querySelectorAll('[data-navgo]')].map((one) => one.dataset.navgo) })""")
        journal.check("R-L18-h: a Default-only account has no Acquisition — no bar row, no drawer entry",
                      "acq" not in places["bar"] and "acq" not in places["drawer"], str(places))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
