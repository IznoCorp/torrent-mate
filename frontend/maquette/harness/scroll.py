"""No form interaction may move the scroll position."""
import asyncio

from playwright.async_api import async_playwright


async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]; ko=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")

    async def trial(state_, sel, idx, label, port='#screen [data-part="viewport"]'):
        await pg.evaluate("(i)=>window.__go(i)", state_); await pg.wait_for_timeout(420)
        await pg.evaluate("(s)=>{const p=document.querySelector(s); p.scrollTop=Math.min(400, p.scrollHeight-p.clientHeight);}", port)
        await pg.wait_for_timeout(180)
        before = await pg.evaluate("(s)=>document.querySelector(s).scrollTop", port)
        if before < 20: print(f"  (page too short for {label})"); return
        await pg.evaluate("([s,i])=>document.querySelectorAll(s)[i].click()", [sel, idx])
        await pg.wait_for_timeout(380)
        after = await pg.evaluate("(s)=>document.querySelector(s)?.scrollTop ?? -1", port)
        # After filtering, the page can become SHORTER than the viewport:
        # there is then nowhere to scroll, and demanding the old position
        # would demand the impossible. Compare against the reachable maximum.
        maxi = await pg.evaluate("(s)=>{const p=document.querySelector(s);return Math.max(0,p.scrollHeight-p.clientHeight);}", port)
        expected = min(before, maxi)
        ok = abs(expected-after) < 5
        if not ok: ko.append(label)
        print(("  PASS" if ok else "  FAIL"), f"{label:34} {before} → {after}" + (f"  (reachable max {maxi})" if maxi < before else ""))

    print("── quality profile ──")
    # These two screens left `#screen` for a real route, rendered inside
    # `#coquille` — their scrollport is now wherever `[data-part="screen"][data-open] [data-part="viewport"]`
    # resolves (the React section carries the same classes `#screen` did),
    # not literally inside the legacy container.
    screen_port = '[data-part="screen"][data-open] [data-part="viewport"]'
    await trial("screen-profile", '[data-part="option"][role="checkbox"]', 2, "checkbox",
                port=screen_port)
    await trial("screen-profile", '[data-part="option"][role="radio"]', 3, "radio button",
                port=screen_port)
    await trial("screen-profile", '[data-part="switch"]', 0, "switch", port=screen_port)
    print("── add screen ──")
    await trial("acq-add-results", '[data-part="segment-small"] button', 1, "type segment", port=screen_port)

    print("\n── keyboard input (value and caret) ──")
    await pg.evaluate("()=>window.__go('lib-grid')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>{const i=document.querySelector('#libq'); i.focus(); i.value='dun'; i.dispatchEvent(new Event('input',{bubbles:true}));}")
    await pg.wait_for_timeout(300)
    r = await pg.evaluate("()=>({focus:document.activeElement?.id, val:document.querySelector('#libq')?.value})")
    print("  search field:", r, "PASS" if r["focus"]=="libq" else "LOSES FOCUS")
    if r["focus"] != "libq": ko.append("field focus")

    print("\nJS errors:", errs or "none")
    print("VERDICT:", "no interaction moves the scroll position" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())
