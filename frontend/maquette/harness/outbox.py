#!/usr/bin/env python3
"""A mutation issued offline departs on reconnection, exactly once.

R107 — P8. The four things that have to be true, and each is a way this can be
       wrong rather than a restatement that it is right:

  a mutation the NETWORK would not take is HELD, not failed. It does not roll
      back, because it has not failed — the operator's action is still going to
      happen, and erasing it from the interface would be the defect this whole
      lot exists to prevent;
  what is held SURVIVES THE PROCESS. The operator's arbitration of 2026-08-30:
      an action watched succeed that then vanishes because the application was
      closed is NE-DOIT-PAS-1's shape;
  it DEPARTS when the network comes back, and the queue empties;
  and the data changes ONCE even when the request arrives twice.

WHAT A REFUSAL IS NOT. A layer that ANSWERS — 404, 409, 500 — has made a
decision, and that decision must reach the operator: it rolls back and says why.
Only a network that does not answer AT ALL is held. Confusing the two would
queue a mutation the server has already rejected and re-send it forever, which
is worse than losing it.

EXACTLY ONCE IS TWO PROPERTIES IN TWO PLACES, and they are held separately
because they can fail separately. The CLIENT forgets an envelope only after its
request has answered — at LEAST once, which is all a client can promise, since a
request whose answer is lost is indistinguishable from one that never arrived.
The LAYER records the keys it has applied and replays the first answer for a
second arrival. Holding only the pair, end to end, would pass over a client that
had stopped sending the key at all.
"""
import asyncio
import sys

from common import Journal, PROTOTYPE, open_page
from playwright.async_api import async_playwright

# The mutation driven throughout: it is idempotent in the domain sense (a title
# is followed or it is not), so a defect in the deduplicator shows up as a
# COUNT and not as a crash.
TITLE = "Une série que personne ne suit"  # french-ok: a fixture title the layer stores


async def follows(page):
    """Reads how many follows the layer holds for the driven title.

    Args:
        page: The page.

    Returns:
        The count, -1 when the layer refused the read, and -2 when the network
        is down — which is a reading this rule must never take as a count of
        zero, since « nothing is followed » and « nobody could ask » are the two
        answers it exists to tell apart.
    """
    return await page.evaluate(
        """async(title)=>{let r;
             try { r = await fetch("/api/acquisition/followed"); }
             catch(offline){ return -2; }
             if(!r.ok) return -1;
             const body = await r.json();
             const rows = Array.isArray(body) ? body : (body.items ?? body.follows ?? []);
             return rows.filter((row)=>(row.title ?? row.t) === title).length;}""",
        TITLE)


async def main():
    """Runs R107.

    Returns:
        0 when P8 holds, 1 otherwise.
    """
    journal = Journal("R107 — a mutation issued offline departs exactly once (P8)")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("async()=>{ await window.__outbox.forget(); }")
        journal.check("the outbox starts empty",
                      await page.evaluate("()=>window.__outbox.depth()") == 0)

        before = await follows(page)

        # --- the network goes, and the mutation is held ----------------------
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        held = await page.evaluate(
            """async(title)=>{
                 try { return await window.__outbox.issue(
                         "POST", "/api/acquisition/followed",
                         {title, kind: "tv"}); }
                 catch(refusal){ return "threw: " + (refusal?.title ?? refusal); }}""",
            TITLE)
        # IT RESOLVES, AND IT SAYS WHY IT RESOLVED. A rejection is what triggers
        # L09's rollback and the mutation has not failed — but answering the way
        # a 204 does would be as bad: a caller that cannot tell « held » from
        # « no body » refreshes its query over the top of its own optimistic
        # write, and the operator's action snaps back minutes before it applies.
        journal.check(
            "a mutation the network will not take is HELD rather than failing",
            held == "held",
            f"{held!r} — neither a rejection nor a silent empty success")

        depth = await page.evaluate("()=>window.__outbox.depth()")
        journal.check("and it is waiting in the outbox", depth == 1, f"depth {depth}")

        on_disk = await page.evaluate(
            "async()=>(await window.__outbox.waiting()).length")
        journal.check("and it is on DISK, not only in a counter", on_disk == 1,
                      f"{on_disk} envelope(s) in the store")

        # THE LAYER IS ASKED WITH THE NETWORK BRIEFLY BACK, because a READ is
        # offline too and would throw exactly as the mutation did. Toggling the
        # dial does not dispatch the browser's `online` event, so nothing
        # departs in between — the queue is asked to stay put, not trusted to.
        await page.evaluate("()=>window.__mocks.setOffline(false)")
        during = await follows(page)
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        journal.check("and the layer has not been told anything yet",
                      during == before, f"{before} → {during}")
        still = await page.evaluate("()=>window.__outbox.depth()")
        journal.check("and nothing departed behind the rule's back",
                      still == 1, f"depth {still}")

        # --- and the interface SAYS what is waiting ---------------------------
        # §8: a mutation that resolved and one that departed are not the same
        # thing, and the operator has no other way of telling them apart. The
        # count is read off the surface, not off the module — a module that
        # counts correctly while nothing draws it is the omission this holds
        # against.
        said = await page.evaluate(
            """()=>{const mark=document.querySelector('[data-part="shell/connection-mark"]');
                 const notice=document.querySelector('[data-part="shell/connection-notice"]');
                 return {mark: mark?.getAttribute("data-pending") ?? null,
                         notice: notice?.getAttribute("data-pending") ?? null,
                         words: (notice?.innerText ?? "").trim()};}""")
        journal.check("the header's mark carries what is waiting",
                      said["mark"] == "1", f"data-pending={said['mark']}")
        journal.check("and the notice says so in words",
                      said["notice"] == "1" and len(said["words"]) > 10,
                      f"{said['words'][:70]!r}")

        # --- a departure that fails leaves the envelope where it was ---------
        # THE CLIENT'S HALF OF « AT LEAST ONCE », and it is held here because
        # nothing else in this rule can see it: with the network up, an envelope
        # forgotten BEFORE its request answered and one forgotten after are
        # indistinguishable. Found by mutation — moving the `forget` above the
        # departure produced no failure at all, which made this rule silent
        # about the one moment the property is about.
        departed = await page.evaluate(
            """async()=>{ await window.__outbox.depart(); }""")
        del departed
        left = await page.evaluate(
            "async()=>(await window.__outbox.waiting()).length")
        journal.check(
            "a departure the network refuses leaves the envelope on disk",
            left == 1,
            f"{left} envelope(s) — forgotten first, it would be lost for good")

        # --- it survives the process -----------------------------------------
        # A RELOAD IS THE PROCESS ENDING, as far as this queue is concerned: the
        # module is evaluated again, every variable it held is gone, and the
        # only thing that can bring the envelope back is the store.
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        # The boot sends what survived, and the network is up again in this new
        # document — `setOffline` lives in the page and did not survive either.
        # So this reload measures BOTH halves at once, which is why the count is
        # read from the store before anything is allowed to depart.
        survived = await page.evaluate(
            "async()=>(await window.__outbox.waiting()).length")
        after_boot = await follows(page)
        journal.check(
            "what was waiting survived the process and departed on the next boot",
            survived == 0 and after_boot == before + 1,
            f"{survived} left in the store, {before} → {after_boot} follows")

        depth = await page.evaluate("()=>window.__outbox.depth()")
        journal.check("and the queue is empty again", depth == 0, f"depth {depth}")

        # --- exactly once, on the layer's side --------------------------------
        # The key arrives TWICE. This is the case a client cannot prevent: a
        # request that departed and whose answer was lost is replayed at the
        # next boot, and only the layer can tell it is the same one.
        twice = await page.evaluate(
            """async(title)=>{
                 const key = "r107-repeated-key";
                 const call = () => fetch("/api/acquisition/followed", {
                   method: "POST",
                   headers: {"idempotency-key": key,
                             "content-type": "application/json"},
                   body: JSON.stringify({title: title + " (bis)", kind: "tv"})});
                 await call(); await call();
                 return window.__mocks.arrivalsByKey()[key] ?? 0;}""",
            TITLE)
        journal.check("a repeated key really arrived twice", twice == 2,
                      f"{twice} arrival(s) — a rule that saw one would prove nothing")

        applied_twice = await page.evaluate(
            """async(title)=>{const r = await fetch("/api/acquisition/followed");
                 const body = await r.json();
                 const rows = Array.isArray(body) ? body : (body.items ?? body.follows ?? []);
                 return rows.filter((row)=>(row.title ?? row.t) === title + " (bis)").length;}""",
            TITLE)
        journal.check("and the data changed exactly once", applied_twice == 1,
                      f"{applied_twice} row(s) for two arrivals")

        # --- and a REFUSAL is not a queue -------------------------------------
        await page.evaluate(
            """()=>window.__mocks.setOperationOutcome(
                 "createFollow", {status: 409})""")
        refused = await page.evaluate(
            """async(title)=>{
                 try { await window.__outbox.issue(
                         "POST", "/api/acquisition/followed",
                         {title: title + " (refusé)", kind: "tv"});
                       return "resolved"; }
                 catch(refusal){ return "threw"; }}""",
            TITLE)
        depth = await page.evaluate("()=>window.__outbox.depth()")
        journal.check(
            "a layer that ANSWERS is a decision the operator must see, never a queue",
            refused == "threw" and depth == 0,
            f"{refused}, depth {depth}")

        # --- a REFUSED replay leaves the queue instead of jamming it ---------
        # THE DEFECT THIS HOLDS AGAINST, found by adversarial review: the run
        # stopped on ANY failed departure, outage or refusal alike. A refusal
        # will not change on the tenth attempt, so the envelope stayed forever,
        # every envelope behind it stayed with it, and the interface went on
        # showing the operator's action as applied over something the server had
        # rejected — NE-DOIT-PAS-1, the defect this queue exists to prevent,
        # arriving from the other side.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        await page.evaluate(
            """async(title)=>{ await window.__outbox.issue(
                 "POST", "/api/acquisition/followed",
                 {title: title + " (jam)", kind: "tv"}); }""", TITLE)
        depth = await page.evaluate("()=>window.__outbox.depth()")
        journal.check("an envelope is waiting before the refusal is armed",
                      depth == 1, f"depth {depth}")
        await page.evaluate("()=>window.__mocks.setOffline(false)")
        await page.evaluate(
            """()=>window.__mocks.setOperationOutcome("createFollow", {status: 409})""")
        await page.evaluate("async()=>{ await window.__outbox.depart(); }")
        depth = await page.evaluate("()=>window.__outbox.depth()")
        left = await page.evaluate(
            "async()=>(await window.__outbox.waiting()).length")
        journal.check(
            "a replay the layer REFUSES leaves the queue rather than jamming it",
            depth == 0 and left == 0,
            f"depth {depth}, {left} on disk — kept, it would block every "
            "envelope behind it forever")

        # --- and the drop is SAID, not silent -------------------------------
        # THE FIRST REPAIR MOVED THE DEFECT RATHER THAN FIXING IT. A jammed
        # queue is visible; an envelope silently destroyed is not, and the
        # notice disappeared exactly as it does on success — under the finger of
        # an operator who had just pressed « Envoyer maintenant ».
        said = await page.evaluate(
            """()=>{const n=document.querySelector('[data-part="shell/connection-notice"]');
                 return {refused: n?.getAttribute("data-refused") ?? null,
                         words: (n?.innerText ?? "").trim()};}""")
        journal.check("a refused departure is SAID, not silently dropped",
                      said["refused"] == "1" and len(said["words"]) > 10,
                      f"data-refused={said['refused']}, {said['words'][:60]!r}")

        # --- a refusal that WILL change keeps its envelope -------------------
        # « DID THE LAYER ANSWER? » WAS TOO WIDE. A 503 from a restarting
        # backend is an answer, and dropping the envelope on it destroys the
        # operator's action in the one case the queue exists for. So is a 429,
        # and so is a 401 after a session expires.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        await page.evaluate(
            """async(title)=>{ await window.__outbox.issue(
                 "POST", "/api/acquisition/followed",
                 {title: title + " (503)", kind: "tv"}); }""", TITLE)
        await page.evaluate("()=>window.__mocks.setOffline(false)")
        await page.evaluate(
            """()=>window.__mocks.setOperationOutcome("createFollow", {status: 503})""")
        await page.evaluate("async()=>{ await window.__outbox.depart(); }")
        still = await page.evaluate(
            "async()=>(await window.__outbox.waiting()).length")
        journal.check(
            "a 503 is an answer that will CHANGE, so its envelope stays",
            still == 1,
            f"{still} on disk — dropped, the operator's action is destroyed by "
            "the very outage this queue exists for")

        # --- the button's ACT matches its NAME (B-266) ----------------------
        # THE OTHER REGRESSION HOLD THE REPAIR SHIPPED WITHOUT. Three rules read
        # `data-connection-action`, all in states where nothing is queued and
        # nothing was refused, and all of them read the NAME. Nothing anywhere
        # asserted that pressing it does what it says — which is the entire
        # content of the defect: on a lost connection with a refusal recorded
        # and an empty queue, the button read « Réessayer maintenant » and
        # CLEARED the refusal instead of reconnecting.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("()=>window.__outbox.forget()")
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        await page.evaluate(
            """async(title)=>{ await window.__outbox.issue(
                 "POST", "/api/acquisition/followed",
                 {title: title + " (bouton)", kind: "tv"}); }""", TITLE)
        await page.evaluate("()=>window.__mocks.setOffline(false)")
        await page.evaluate(
            """()=>window.__mocks.setOperationOutcome("createFollow", {status: 409})""")
        await page.evaluate("async()=>{ await window.__outbox.depart(); }")
        # A refusal recorded, nothing waiting, and the socket driven to `lost` —
        # the exact cell the two ladders disagreed on.
        await page.evaluate("""()=>window.__relay.force("lost")""")
        await page.wait_for_timeout(200)
        named = await page.evaluate(
            """()=>document.querySelector("[data-connection-action]")
                 ?.getAttribute("data-connection-action")""")
        journal.check(
            "on a lost connection with a refusal, the button offers to RETRY",
            named == "retry", f"data-connection-action={named!r}")
        before_click = await page.evaluate(
            """()=>({refused: document.querySelector('[data-part="shell/connection-notice"]')
                       ?.getAttribute("data-refused"),
                     condition: window.__relay.condition().condition})""")
        await page.evaluate(
            """()=>document.querySelector("[data-connection-action]").click()""")
        await page.wait_for_timeout(400)
        after_click = await page.evaluate(
            """()=>({refused: document.querySelector('[data-part="shell/connection-notice"]')
                       ?.getAttribute("data-refused"),
                     condition: window.__relay.condition().condition})""")
        # RETRY MUST RECONNECT AND MUST NOT DISCARD THE RECORD. Reading the name
        # alone would pass over a button that cleared the refusal instead.
        journal.check(
            "and pressing it reconnects rather than discarding the refusal",
            after_click["condition"] != "lost"
            and after_click["refused"] == before_click["refused"],
            f"{before_click} → {after_click}")

        # --- and a 401 is not final either (B-265) --------------------------
        # THE REGRESSION HOLD THE REPAIR SHIPPED WITHOUT. The 503 hold above was
        # green under the deny-list too — `status >= 500` was already excluded —
        # so it did not move across the repair and proves nothing about it. 401
        # is the status that DID fall through: an installed application with the
        # radio off queues N mutations, the session expires, the radio returns,
        # and every one of them is destroyed in turn when a re-login would have
        # saved them all.
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("()=>window.__outbox.forget()")
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        await page.evaluate(
            """async(title)=>{ await window.__outbox.issue(
                 "POST", "/api/acquisition/followed",
                 {title: title + " (401)", kind: "tv"}); }""", TITLE)
        await page.evaluate("()=>window.__mocks.setOffline(false)")
        await page.evaluate(
            """()=>window.__mocks.setOperationOutcome("createFollow", {status: 401})""")
        await page.evaluate("async()=>{ await window.__outbox.depart(); }")
        survived = await page.evaluate(
            "async()=>(await window.__outbox.waiting()).length")
        journal.check(
            "an expired session does not destroy what a re-login would save",
            survived == 1,
            f"{survived} on disk — dropped, every queued mutation goes with the "
            "session one after another")

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
