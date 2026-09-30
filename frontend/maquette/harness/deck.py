"""Both deck gestures, under real TouchEvents on the real surface.

Synthetic PointerEvents would never be cancelled by the browser, so they prove
nothing about a gesture that has to claim an axis.

RE-AIMED when the suggestions, the search and the releases took the contract's
names: a suggestion's title is read as `title`, where they were the engine's
short keys. The holds and what they compare are unchanged.

R-L16bis-l — Découvrir's swipe: left passes, right rejects, in the LIST as on the
deck (the operator's Q7, and « passer » is the back of the one order, his
OPEN 10 = A). By real touches (`Input.dispatchTouchEvent`), in the list:
- held mid-travel, the word uncovered is « Passer » to the left, « Pas
  intéressé » to the right;
- a left throw removes the row from its place, leaves the rejected set unchanged,
  shows no notification, and the suggestion is still in the order, at its back;
- a right throw removes it, the rejected set grows by one, the notification
  carries « Annuler », and « Annuler » puts the row back at its place;
- the list's row is the design system's commit row.
On the deck, beside its holds: held mid-travel, each side shows its own hint.

Red before the move: the list rejected both ways, with the same word on both sides.
"""
import json
import pathlib
import asyncio
from common import PROTOTYPE, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SEL = '[data-part="deck/card"][data-depth="0"]'
ROW = '#view [data-part="suggestion/wrap"]'
WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1] / "design/src/i18n/fr.json")
                   .read_text(encoding="utf-8"))["discover"]

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
    ctx = await b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2,
                              is_mobile=True, has_touch=True)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(PROTOTYPE, wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")

    async def deck():
        # RE-AIMED OUT LOUD: « Découvrir » is a page of the bar.
        await pg.evaluate('()=>{window.__reset(); applyState({page:"discover",phase:"ready"}); window.__store.write({sugMode: "deck"}); window.__store.touch();}')
        await pg.wait_for_timeout(600)

    async def title():
        return await pg.evaluate(
            f"""()=>document.querySelector('{SEL} [data-part="deck/title"]').textContent""")

    async def swipe(dx):
        await pg.evaluate("""(dx)=>{
          const c=document.querySelector('[data-part="deck/card"][data-depth="0"]');
          const r=c.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
          // Real PointerEvents of type « touch »: the handlers now serve finger,
          // mouse and pen through one path, and the axis claim still lives in
          // `touch-action`, which a synthetic event cannot exercise — that claim
          // is asserted separately, below.
          const P=(t,cx,extra)=>new PointerEvent(t,{bubbles:true,cancelable:true,isPrimary:true,
            pointerId:1,pointerType:'touch',clientX:cx,clientY:y,...(extra||{})});
          c.dispatchEvent(P('pointerdown',x));
          for (let i=1;i<=6;i++) c.dispatchEvent(P('pointermove',x+dx*i/6));
          window.dispatchEvent(P('pointerup',x+dx));
        }""", dx)
        await pg.wait_for_timeout(700)

    await deck()
    t0 = await title(); n0 = await pg.evaluate("()=>state.sugGone.size")
    await swipe(-170)
    t1 = await title(); n1 = await pg.evaluate("()=>state.sugGone.size")
    comes_back = await pg.evaluate("(t)=>window.__discover.order().map(i=>(window.__suggestions?.()||[])[i].title).includes(t)", t0)
    print(f"LEFT   « {t0[:26]} » → « {t1[:26]} »")
    print(f"       dismissed {n0} → {n1} · comes round again: {comes_back}")

    await deck()
    t2 = await title()
    await swipe(170)
    t3 = await title(); n3 = await pg.evaluate("()=>state.sugGone.size")
    undo = await pg.evaluate("()=>!!document.querySelector('#toastundo')")
    print(f"RIGHT  « {t2[:26]} » → « {t3[:26]} »")
    print(f"       dismissed {n3} · undo offered: {undo}")

    # ── R-L16bis-l: the LIST, by real touches ─────────────────────────────
    cdp = await ctx.new_cdp_session(pg)

    async def touch(selector, dx, release=True):
        box = await pg.evaluate(f"""()=>{{const b=document.querySelector('{selector}').getBoundingClientRect();
          return {{x:b.left+b.width/2, y:b.top+b.height/2}};}}""")
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
        for i in range(1, 13):
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchMove", "touchPoints": [{"x": box["x"] + dx * i / 12, "y": box["y"], "id": 1}]})
            await pg.wait_for_timeout(16)
        if release:
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await pg.wait_for_timeout(700)

    async def listed():
        await pg.evaluate('()=>{window.__reset(); applyState({page:"discover",phase:"ready"}); window.__store.write({sugMode: "list"}); window.__store.touch();}')
        await pg.wait_for_timeout(600)

    UNCOVERED = """(side)=>{const row=document.querySelector('%s');
      const card=row.querySelector('[data-part="card"]').getBoundingClientRect(), r=row.getBoundingClientRect();
      const open = side === 'right' ? card.right < r.right - 30 : card.left > r.left + 30;
      return open ? row.querySelector(`[data-part="commit/back"] [data-side="${side}"]`)?.textContent.trim() ?? null : null;}""" % ROW
    ROWS = "()=>[...document.querySelectorAll('%s')].map(row=>Number(row.dataset.dismissable))" % ROW
    # EVERY notification SHOWN FROM NOW ON, kept as it is shown: one left standing
    # from an earlier gesture is not this gesture's.
    WATCH = """()=>{window.__seen=[]; const toast=document.getElementById('toast');
      if (toast) new MutationObserver(()=>window.__seen.push(toast.textContent.trim()))
        .observe(toast, {childList:true, subtree:true, characterData:true});}"""
    TOAST = "()=>(window.__seen||[]).join(' | ')"

    await listed()
    await touch(ROW, -70, release=False)
    left_word = await pg.evaluate(UNCOVERED, "right")
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await listed()
    await touch(ROW, 70, release=False)
    right_word = await pg.evaluate(UNCOVERED, "left")
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    words_ok = left_word == WORDS["skip"] and right_word == WORDS["notInterested"]
    print(f"LIST   held left uncovers « {left_word} », held right « {right_word} »")

    await listed()
    before = await pg.evaluate(ROWS); gone0 = await pg.evaluate("()=>state.sugGone.size")
    await pg.evaluate(WATCH)
    await touch(ROW, -170)
    after = await pg.evaluate(ROWS); gone1 = await pg.evaluate("()=>state.sugGone.size")
    passed_toast = await pg.evaluate(TOAST)
    back = await pg.evaluate("(p)=>{const order=window.__discover.order(); return order[order.length-1]===p;}", before[0])
    pass_ok = (after[:1] != before[:1] and gone1 == gone0 and before[0] in after and after[-1] == before[0]
               and not passed_toast and back)
    print(f"LIST   left: first {before[0]} → {after[0]}, drawn again last {after[-1] == before[0]}, "
          f"rejected {gone0} → {gone1}, notification {passed_toast!r}, at the order's back {back}")

    await listed()
    before = await pg.evaluate(ROWS)
    await touch(ROW, 170)
    after = await pg.evaluate(ROWS); gone2 = await pg.evaluate("()=>state.sugGone.size")
    offered = await pg.evaluate("()=>!!document.querySelector('#toastundo')")
    await pg.evaluate("()=>document.querySelector('#toastundo')?.click()")
    await pg.wait_for_timeout(500)
    undone = await pg.evaluate(ROWS)
    reject_ok = before[0] not in after and gone2 == 1 and offered and undone[:1] == before[:1]
    print(f"LIST   right: rejected {gone2}, « Annuler » offered {offered}, back at its place {undone[:1] == before[:1]}")
    commit_ok = await pg.evaluate("""()=>{const row=document.querySelector('%s');
      return !!row && row.classList.contains('commitrow') && !!row.querySelector('[data-part="commit/back"]');}""" % ROW)
    print(f"LIST   the row is the design system's commit row: {commit_ok}")

    # ── the deck's hint, per side ───────────────────────────────────────────
    await deck()
    HINT = """(side)=>{const h=document.querySelector('%s .dhint.' + side);
      return h && Number(getComputedStyle(h).opacity) > 0.5 ? h.textContent.trim() : null;}""" % SEL
    await touch(SEL, -110, release=False)
    deck_left = await pg.evaluate(HINT, "l")
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await pg.wait_for_timeout(500)
    await deck()
    await touch(SEL, 110, release=False)
    deck_right = await pg.evaluate(HINT, "r")
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    hints_ok = deck_left == WORDS["skip"] and deck_right == WORDS["notInterested"]
    print(f"DECK   held left shows « {deck_left} », held right « {deck_right} »")
    list_ok = words_ok and pass_ok and reject_ok and commit_ok and hints_ok

    # The axis claim is what makes a REAL touch gesture reach us instead of
    # being taken by the browser. A synthetic event never exercises it, so it is
    # asserted on the declaration itself.
    axis = await pg.evaluate("""()=>getComputedStyle(document.querySelector('[data-part="deck"]')).touchAction""")
    print(f"       axis claim on the deck: {axis}")
    ok = (t1 != t0 and n1 == n0 and comes_back) and (t3 != t2 and n3 == 1 and undo) and axis == "pan-y" and list_ok
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "left skips and comes back, right dismisses with an undo — in the list as on the deck"
          if ok and not errs else "needs review")
    await b.close()

    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if not ok or errs: raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
