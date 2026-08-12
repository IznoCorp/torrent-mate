import asyncio
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    await pg.click('[data-acqtab="suivis"]'); await pg.wait_for_timeout(350)

    print("modes offered    :", await pg.evaluate("()=>[...document.querySelectorAll('.vsw button')].map(b=>b.getAttribute('aria-label'))"))
    print("pastilles        :", await pg.evaluate("()=>[...document.querySelectorAll('.pill')].map(b=>b.textContent.trim())"))
    print("ordre liste      :", await pg.evaluate("()=>[...document.querySelectorAll('.ctitle')].map(e=>e.textContent).slice(0,6)"))
    print("point across chip   :", await pg.evaluate("()=>{const c=document.querySelector('.chip');const s=getComputedStyle(c,'::before');return {w:s.width,h:s.height,radius:s.borderRadius};}"))
    print("titre seul       :", await pg.evaluate("""()=>[...document.querySelectorAll('.card')].slice(0,4).every(c=>{
        const t=c.querySelector('.ctitle').getBoundingClientRect(), m=c.querySelector('.cmeta').getBoundingClientRect();
        return t.bottom<=m.top+0.5;})"""))
    await pg.screenshot(path="s_liste.png")

    await pg.click('[data-fmode="group"]'); await pg.wait_for_timeout(350)
    print("groupes rendus   :", await pg.evaluate("()=>[...document.querySelectorAll('.sechead .t')].map(e=>e.textContent)"))
    print("chip hidden in a homogeneous group:", await pg.evaluate("""()=>{
       const secs=[...document.querySelectorAll('.sec')];
       const aJour=secs.find(s=>(s.querySelector('.sechead .t')||{}).textContent==='À jour');
       return aJour? aJour.querySelectorAll('.chip').length===0 : 'groupe absent';}"""))
    print("chip kept in a heterogeneous group:", await pg.evaluate("""()=>{
       const secs=[...document.querySelectorAll('.sec')];
       const d=secs.find(s=>(s.querySelector('.sechead .t')||{}).textContent==='Demandent quelque chose');
       return d? d.querySelectorAll('.chip').length>0 : 'groupe absent';}"""))
    await pg.screenshot(path="s_groupe.png")

    await pg.click('[data-fmode="grid"]'); await pg.wait_for_timeout(350)
    print("tuiles           :", await pg.evaluate("()=>document.querySelectorAll('.tile').length"),
          "| badges :", await pg.evaluate("()=>[...document.querySelectorAll('.tilebadge')].map(e=>e.textContent)"))
    await pg.screenshot(path="s_grille.png")

    await pg.click('[data-fmode="list"]'); await pg.click('[data-pill="films"]'); await pg.wait_for_timeout(300)
    print("filtre Films     :", await pg.evaluate("()=>[...document.querySelectorAll('.ctitle')].map(e=>e.textContent)"))
    print("film label       :", await pg.evaluate("()=>document.querySelector('.chip').textContent"))
    print("film actions     :", await pg.evaluate("()=>[...document.querySelectorAll('.swipe .act')].slice(0,2).map(e=>e.textContent.trim())"))
    print("\nJS errors:", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if errs: raise SystemExit(1)
asyncio.run(main())
