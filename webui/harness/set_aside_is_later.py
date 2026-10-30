"""R226 — « Laisser tel quel » means later: the card is set aside, never removed.

Ruling 6, placed by ruling 16: leaving a folder as it is means LATER. The card
stays in acquisition — the file is still on the machine and still has to be
dealt with — marked « mis de côté par vous, le … », and it leaves the part of
« À traiter » that counts: it goes to « Mis de côté », a FOLDED section at the
END of the tab, outside the tab's count and the bar's badge. From there the
operator can still handle it: its panel offers « Résoudre ».

Walked by finger on a real blocked folder of « À traiter » (Lucky, whose tie is
a real pending decision): « Résoudre → » on its card, then « Laisser tel
quel » on the candidates screen.

1. the card is no longer among the cards « À traiter » counts, and the tab's
   count and the bar's badge both lost exactly one;
2. it is in « Mis de côté », the LAST section of the tab, folded, with the
   reason « mis de côté par vous, le <day> » — the day composed from the date
   the layer answered, never a constant (§13);
3. it is still there after both reads are asked again: the layer holds it, not
   the screen;
4. its panel offers « Résoudre » — the section's own act, also in the panel
   (one card, one behaviour);
5. the rung set aside is the one the card STANDS on (ruling 6: `aside`,
   « identifié » pending), never the first rung it has not lived — and the card
   keeps the figure and the word it had in « À traiter » (« 6 sur 8 ·
   identifié »), read on the card and on the ladder the layer holds.

Red before the move: « Laisser tel quel » took the folder out of both lists and
nothing drew it anywhere.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
LEFT = json.loads((SEEDS / "blocked.json").read_text(encoding="utf-8"))[0]["title"]
PENDING = {row["folder"] for row in json.loads((SEEDS / "pending-decisions.json").read_text(encoding="utf-8"))}
SECTION = '[data-part="section/set-aside"]'

READING = f"""(title) => {{
  const number = (element) => element ? Number(element.textContent) : null;
  const aside = document.querySelector('#view {SECTION}');
  const titles = (root) => [...root.querySelectorAll('[data-part="card/title"]')].map(one => one.textContent);
  const counted = [...document.querySelectorAll('#view [data-part="card"]')]
    .filter(card => !card.closest('{SECTION}'))
    .map(card => card.querySelector('[data-part="card/title"]').textContent);
  const card = aside ? [...aside.querySelectorAll('[data-part="card"]')]
    .find(one => one.querySelector('[data-part="card/title"]').textContent === title) : null;
  const sections = [...document.querySelectorAll('#view [data-part^="section"]')]
    .filter(one => one.matches('section'));
  const answer = window.__queries?.getQueryData(["/api/v1/acquisition/to-handle", ""]) || {{}};
  const held = [...(answer.blocked || []), ...(answer.arrivals || [])].find(one => one.title === title);
  const rung = (held?.ladder || []).find(one => one.state === 'aside');
  const drawn = [...document.querySelectorAll('#view [data-part="card"]')]
    .find(one => one.querySelector('[data-part="card/title"]').textContent === title);
  const cells = drawn ? [...drawn.querySelectorAll('[data-part="card/step"]')].map(cell => cell.dataset.state) : [];
  const figure = drawn?.querySelector('[data-part="card/meta"] > span:first-child');
  const word = drawn?.querySelector('[data-part="card/meta"] [data-part="chip"]');
  return {{
    counted,
    tab: number(document.querySelector('[data-acqtab="todo"] [data-part="segment/count"]')),
    badge: number(document.querySelector('[data-page=acq] [data-part="shell/tab-badge"]')),
    aside: aside ? titles(aside) : null,
    last: aside !== null && sections[sections.length - 1] === aside,
    folded: aside ? !aside.querySelector('details')?.open : null,
    reason: card ? (card.querySelector('[data-part="card/reason"]') || {{}}).textContent || null : null,
    when: rung ? rung.when : null,
    asideRung: rung ? rung.rung : null,
    cells,
    figure: figure ? figure.textContent : null,
    word: word ? word.textContent : null,
  }};
}}"""


async def main():
    journal = Journal("R226 — « Laisser tel quel » sets the card aside, in a folded section")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        journal.check("the folder left is a real pending decision", LEFT in PENDING, LEFT)
        answer = await page.evaluate(
            "()=>{try{window.__go('acq-todo-loaded');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-todo-loaded exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(READING, LEFT)

        # ── by finger: « Résoudre → », then « Laisser tel quel » ─────────────
        tapped = await page.evaluate("""(title)=>{
            const foot = [...document.querySelectorAll('#view [data-part="card/foot"]')]
              .find(one => one.getAttribute('data-resolution') === title);
            if (!foot) return false; foot.click(); return true; }""", LEFT)
        await page.wait_for_timeout(ACTED)
        left = await page.evaluate(
            "()=>{const exit=document.querySelector('[data-leave]'); if(!exit) return false; exit.click(); return true;}")
        await page.wait_for_timeout(ACTED)
        journal.check("« Résoudre → » then « Laisser tel quel » were both tapped",
                      tapped and left, f"foot {tapped}, leave {left}")
        after = await page.evaluate(READING, LEFT)

        journal.check("the card is no longer among the cards « À traiter » counts",
                      LEFT in before["counted"] and LEFT not in after["counted"],
                      f"{before['counted']} → {after['counted']}")
        journal.check("the tab's count and the bar's badge each lost exactly one",
                      before["tab"] is not None and after["tab"] == before["tab"] - 1
                      and after["badge"] == after["tab"] == len(after["counted"]),
                      f"tab {before['tab']} → {after['tab']}, badge {before['badge']} → {after['badge']}, "
                      f"counted {len(after['counted'])}")
        journal.check("it is in « Mis de côté »", LEFT in (after["aside"] or []), str(after["aside"]))
        journal.check("« Mis de côté » is the tab's LAST section, and folded",
                      after["last"] and after["folded"] is True,
                      f"last {after['last']}, folded {after['folded']}")
        day = str(int(after["when"][8:10])) if after["when"] else None
        journal.check("its reason says « mis de côté par vous, le <day> », the day the layer answered",
                      day is not None and after["reason"] is not None
                      and after["reason"].startswith("Mis de côté par vous, le ") and day in after["reason"],
                      f"{after['reason']!r}, answered {after['when']!r}")

        standing = before["cells"].index("blocked") if "blocked" in before["cells"] else None
        journal.check("the rung set aside is the one the card stood on, « identifié »",
                      after["asideRung"] == "identified" and standing is not None
                      and after["cells"][standing:standing + 1] == ["aside"],
                      f"layer {after['asideRung']!r}, cells {before['cells']} → {after['cells']}")
        journal.check("and the card keeps its figure and its word",
                      before["figure"] is not None and (after["figure"], after["word"]) == (before["figure"], before["word"]),
                      f"{before['figure']!r} · {before['word']!r} → {after['figure']!r} · {after['word']!r}")

        # ── the layer holds it: both reads asked again ─────────────────────
        await page.evaluate("""()=>{
            window.__queries?.removeQueries({ queryKey: ["/api/v1/acquisition/to-handle"] });
            window.__queries?.removeQueries({ queryKey: ["/api/v1/staging/media"] });
            window.__store.touch?.(); }""")
        await page.evaluate("()=>document.querySelector('[data-acqtab=\"now\"]')?.click()")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("()=>document.querySelector('[data-acqtab=\"todo\"]')?.click()")
        await page.wait_for_timeout(SETTLED)
        again = await page.evaluate(READING, LEFT)
        journal.check("and it is still set aside after both reads are asked again",
                      LEFT in (again["aside"] or []) and LEFT not in again["counted"],
                      f"aside {again['aside']}, counted {again['counted']}")

        # ── its panel offers « Résoudre » ──────────────────────────────────
        await page.evaluate(f"""(title)=>{{
            const summary = document.querySelector('#view {SECTION} summary');
            if (summary && !summary.parentElement.open) summary.click(); }}""", LEFT)
        await page.wait_for_timeout(ACTED)
        await page.evaluate(f"""(title)=>[...document.querySelectorAll('#view {SECTION} [data-part="card"]')]
            .find(one => one.querySelector('[data-part="card/title"]').textContent === title)
            ?.querySelector('[data-part="card/body"]')?.click()""", LEFT)
        await page.wait_for_timeout(ACTED)
        actions = await page.evaluate("""()=>{const sheet=document.querySelector('#sheet');
            if(!sheet||!sheet.hasAttribute('data-open')) return null;
            return [...sheet.querySelectorAll('[data-part="sheet/action"]')].map(one=>one.textContent.trim());}""")
        journal.check("its panel offers « Résoudre »",
                      actions is not None and any("Résoudre" in one for one in actions), str(actions))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
