"""R159 — a message said while a layer is open is SEEN, and it takes a finger (B-381).

WHAT NOBODY COULD SEE. A verb pressed inside the bottom sheet speaks through the
message layer, and the frame ranked the message at z-49 under the sheet at z-52
(`ui/variants/frame.ts`). The sentence was in the document, visible, at full
opacity — and painted under the sheet's own content: « Série suivie et saison 3
demandée — 6 épisodes à récupérer. » held by the toast seam for three seconds
while the operator saw nothing.

AND A SECOND HALF UNDER THE FIRST. While any layer is open, `app/focus.ts` marks
every child of the shell except that layer `inert` — and the message was one of
them. `inert` changes nothing about painting and removes an element from
hit-testing, so a message raised above the sheet would have been SEEN with a
close and an « Annuler » that no finger could reach.

Every instrument was green over both. R125 and R158 read `window.__toast.read()`,
which answers what the layer HOLDS, not what is painted. R101's hold (d) shows
the message with no layer open. The oracle measures no paint order.

TWO QUESTIONS, READ SEPARATELY, because each half can be broken alone:

  PAINT — `elementFromPoint` at the centre of the element carrying the message's
  text, with `inert` LIFTED from the message host for the reading and put back
  at once. The lift is what lets a hit test answer « what is painted here »
  rather than « what takes a finger here »; R101 lifts `inert` from the tab bar
  for the same reason.
    1. Over an open bottom sheet (`sheet-user`), a message is painted on top.
    2. On the follow panel, after the panel's own verb — « Récupérer la saison »
       on the one follow with a hole — the sentence the verb chose is on top.
    3. On the media screen (`mediasheet-series`), a message is painted on top.
       THIS LEG WAS NEVER RED FOR PAINT. The first version of this rule read the
       screen as covering the message; it was reading `inert`. It stays as the
       witness that the screen, ranked 45, never covered it.

  TOUCH — nothing lifted, a real finger.
    4. Over an open bottom sheet, a finger on the message's close takes the
       message off screen.

  PLACEMENT — at the top of the screen while a layer is open, at the bottom
  otherwise. Ranked above the layer and taking a finger, a message along the
  bottom band still covered the very controls a layer anchors there: the boot
  hint lay over « Pas intéressé », « Re-scraper ce passage » and « Retirer de la
  liste » at the moment a finger went for them, and a verb's answer lies over
  the next verb of the same layer for five seconds. Read on BOXES, nothing
  lifted:
    5. A message up BEFORE a layer opens — the boot hint's shape — moves off
       the layer: its box meets none of the sheet's controls, and each action
       is what a finger at its centre lands on.
    6. The verb's own answer, on leg 2's follow panel: its box meets none of the
       panel's controls, and a finger on its close takes it off screen.
    7. Over a confirmation whose button sits in the bottom band, its box meets
       none of the confirmation's buttons.
    8. With no layer open, the message is at the bottom, as it always was:
       above the tab bar, in the lower half of the screen.
    9. AT REST, a message hidden while a layer is open goes back to the bottom
       box. The oracle measures the hidden host on every state, so a box left at
       the top would be a divergence on states that draw no message at all.
   10. On EVERY KIND OF SCREEN — media, releases, quality, add, resolution — a
       message up sits below the screen's own bar, and « Retour » takes a finger
       and leaves the screen. A screen keeps its way out in that bar: a message
       at the top of the frame lay over it, and the tap did nothing for the
       message's five seconds, after every verb answered on a screen and after
       the boot hint on any address that opens one.
   11. A MESSAGE THE READER HAS SEEN NEVER JUMPS between the two edges. When a
       screen closes, or a sheet opens, under a message already drawn, it fades
       out where it is and appears at the other edge — read frame by frame, and
       no two consecutive frames at full opacity show it in two places. Moved at
       once, it crossed the frame in one frame while it was being read.
       RE-AIMED BEFORE IT WAS WRITTEN, and said here: the wording first given
       was « no frame shows the message at full opacity outside both its old and
       its new edge ». That wording cannot fall — each frame of the jump sits at
       one of the two edges — so it would hold over the defect. What is read
       instead: no two CONSECUTIVE frames at full opacity in two places; a frame
       at the first place partly faded; and the message whole at the other edge.
       RE-AIMED A SECOND TIME, and said here: those three stayed green over a
       message moved 50 ms into its fade — at the first place at 0.4 opacity,
       the next frame at the other edge rising from 0.4, a 660 px teleport never
       at full opacity in two consecutive frames. The leg now also holds that
       between the last frame at the first place and the first frame at the
       other edge, each above 0.05 opacity, a frame shows the message wholly
       gone.
       WITHIN ONE EDGE it is not read: a message on a screen when a sheet opens
       over it follows the layer's bar by a slide, measured 46 px, at full
       opacity — not an edge change, and not what this leg holds.
   12. A CROSSING TAKES NOTHING FROM THE MESSAGE'S LIFE. A screen closes inside
       the last 600 ms of a life — five seconds, and six with « Annuler » — and
       the message is read frame by frame. Owed 560 ms when it starts to leave,
       it comes back at the other edge and is whole there for at least those
       560 ms, with and without « Annuler ». Owed 150 ms, less than its own
       400 ms exit, it ends by leaving and is never drawn at the other edge.
       With the clock running through the crossing, a message that changed edge
       at 4 419 ms came back with 181 ms left — whole for about twenty
       milliseconds, a flash of a sentence the reader had just watched go.

WHAT IT DOES NOT READ: whether the message covers something it should not on a
bare screen — R101 holds the message against the tab bar.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

SHEET_STATE = "sheet-user"
FOLLOWS_STATE = "acq-follows-list"
SCREEN_STATE = "mediasheet-series"
PROBE = "probe message for R159"

# THE MESSAGE ON SCREEN IS TAKEN OFF FIRST. The design note's greeting occupies
# the host after boot, and a probe shown over it was never carried: an earlier
# version of this rule read the greeting's text and failed for a reason that
# was not the stacking.
HIDE = "()=>window.__toast.hide()"
SHOW = "(text)=>window.__toast.show({message: text})"
SHOWN = "()=>window.__toast.read().shown"

# WHAT IS PAINTED AT THE MESSAGE'S OWN TEXT — the deepest element under the
# message host whose text holds the words, hit-tested with `inert` lifted from
# the host and its ancestors for the reading only.
PAINTED_ON_TOP = """(words)=>{
  const host = document.querySelector('#toast');
  if (!host) return {host: false};
  const holders = [...host.querySelectorAll('*')].filter((one) =>
    (one.textContent || '').includes(words)
    && ![...one.children].some((child) => (child.textContent || '').includes(words)));
  const carrier = holders[0] || ((host.textContent || '').includes(words) ? host : null);
  if (!carrier) return {host: true, carried: false, text: (host.textContent || '').trim()};
  const lifted = [];
  for (let node = host; node; node = node.parentElement)
    if (node.hasAttribute('inert')) { lifted.push(node); node.removeAttribute('inert'); }
  const box = carrier.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  lifted.forEach((node) => node.setAttribute('inert', ''));
  return {host: true, carried: true, at: [Math.round(x), Math.round(y)], lifted: lifted.length,
          onTop: !!hit && host.contains(hit),
          hit: hit ? hit.tagName + '.' + String(hit.className || '').split(' ')[0]
                     + (hit.dataset && hit.dataset.part ? '[' + hit.dataset.part + ']' : '') : null};}"""

# WHERE A FINGER ON THE MESSAGE'S CLOSE WOULD LAND — nothing lifted.
AIM_AT_THE_CLOSE = """()=>{
  const close = document.querySelector('#toastx');
  if (!close) return {found: false};
  const box = close.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === close || close.contains(hit)),
          hit: hit ? hit.tagName + '.' + String(hit.className || '').split(' ')[0] : null,
          inert: !!close.closest('[inert]')};}"""

# The one follow with a hole, drawn on the follows list.
THE_FOLLOW_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map((one) => one.dataset.panel);
  for (const follow of (window.__followActions?.all() || [])) {
    if (!drawn.some((seen) => seen === follow.t || seen.endsWith(':' + follow.t))) continue;
    if ((window.SEASONS[follow.t] || []).some(([n, aired, owned]) => (owned || 0) < (aired || 0)))
      return follow.t;
  }
  return null;}"""

AIM = """([selector, predicate])=>{
  const target = [...document.querySelectorAll(selector)].find((one) =>
    predicate === null || one.dataset.panel === predicate || (one.dataset.panel || '').endsWith(':' + predicate));
  if (!target) return {found: false};
  target.scrollIntoView({block: 'center'});
  const box = target.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === target || target.contains(hit))};}"""

SAID = """()=>{const held = window.__toast?.read?.();
  return held && held.message ? held.message.message || '' : '';}"""

# WHERE THE MESSAGE'S BOX IS, AND WHICH OF A LAYER'S CONTROLS IT MEETS. A box
# with no size is not a control a finger can reach, so it meets nothing.
MEETS = """(controls)=>{
  const box = document.querySelector('#toast').getBoundingClientRect();
  const every = controls ? [...document.querySelectorAll(controls)] : [];
  const met = every.filter((one) => {
    const other = one.getBoundingClientRect();
    return other.width > 0 && other.height > 0 && other.left < box.right
      && other.right > box.left && other.top < box.bottom && other.bottom > box.top;})
    .map((one) => (one.textContent || one.getAttribute('aria-label') || '').trim().slice(0, 30)
      + '@' + Math.round(one.getBoundingClientRect().top));
  const bar = document.querySelector('#nav')?.getBoundingClientRect();
  return {shown: window.__toast.read().shown, box: [Math.round(box.top), Math.round(box.bottom)],
          controls: every.length, met, barTop: bar ? Math.round(bar.top) : null,
          height: window.innerHeight};}"""

# EACH ACTION OF THE OPEN SHEET IS WHAT A FINGER AT ITS CENTRE LANDS ON — the
# property the four rules that met the message read, asked of every action.
ACTIONS_REACHABLE = """()=>{
  const actions = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')];
  const missed = actions.filter((one) => {
    const box = one.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return !hit || !(hit === one || one.contains(hit));})
    .map((one) => (one.textContent || '').trim().slice(0, 30));
  return {actions: actions.length, missed};}"""

SHEET_CONTROLS = "#sheetin button"
# THE CONFIRMATION'S BUTTONS, on a confirmation whose button REALLY sits in the
# bottom band. This leg has been aimed three times, and the first two are the
# reason for the third. It read the buttons of a forty-line confirmation, which
# is taller than the screen: its button lay below the fold and the hold was
# green over the defect. It then read the whole confirmation, which no edge can
# keep clear of: a confirmation is CENTRED, so one tall enough to reach the
# bottom band reaches the top band too. What a message must not cover is a
# verb — so the buttons, and the hold first shows the button is in the band.
CONFIRMATION_BUTTONS = '#dlg [data-part="dialog/button"]'
BARE_STATE = "lib-list"
SELECTION_STATE = "lib-selection"

# The exit is a fade and a visibility step after it; a box read before both have
# run is still the leaving message, not the host at rest.
EXITED = 700

# Twenty-six lines put the button at the foot of a 390 x 844 screen, the
# confirmation still whole on it.
# ONE STATE PER KIND OF SCREEN, each drawing its bar and its « Retour ».
SCREEN_STATES = {
    "media": "mediasheet-series",
    "releases": "screen-releases",
    "quality": "screen-profile",
    "add": "acq-add-empty",
    "resolution": "arr-resolution",
}

# THE OPEN SCREEN'S WAY OUT, AND WHAT A FINGER ON IT LANDS ON — nothing lifted.
BACK_UNDER = """()=>{
  const screens = [...document.querySelectorAll('[data-part="screen"][data-open]')];
  const screen = screens[screens.length - 1];
  if (!screen) return {screen: null};
  const back = screen.querySelector('[data-part="screen/back"]');
  const bar = screen.querySelector('[data-part="screen/bar"]');
  if (!back || !bar) return {screen: screen.dataset.key || '', back: !!back, bar: !!bar};
  const message = document.querySelector('#toast').getBoundingClientRect();
  const box = back.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {screen: screen.dataset.key || '', x, y, shown: window.__toast.read().shown,
          message: [Math.round(message.top), Math.round(message.bottom)],
          barBottom: Math.round(bar.getBoundingClientRect().bottom),
          reachable: !!hit && (hit === back || back.contains(hit)),
          hit: hit ? hit.tagName + (hit.closest('#toast') ? ' in the message' : '') : null};}"""

OPEN_SCREEN = """()=>{
  const screens = [...document.querySelectorAll('[data-part="screen"][data-open]')];
  return screens.length ? screens[screens.length - 1].dataset.key || '' : null;}"""

A_TALL_CONFIRMATION = """()=>window.__dialog.open({
  heading: 'probe',
  body: [{type: 'manifest', entries: Array.from({length: 26},
    (_, n) => ({text: 'line ' + n, value: String(n)}))}],
  actions: [{text: 'Annuler', dismiss: true}]})"""


# EVERY FRAME OF THE MESSAGE ACROSS ONE LAYER CHANGE — where its box is, its
# opacity and whether it is visible, sampled on each animation frame. The first
# sample is taken BEFORE the change, so the place the message left is in the
# record; the change is spliced in where the placeholder stands.
ACROSS_THE_CHANGE = """(span)=>new Promise((resolve)=>{
  const host = document.querySelector('#toast');
  const samples = [];
  const started = performance.now();
  const take = () => {
    const box = host.getBoundingClientRect();
    const style = getComputedStyle(host);
    samples.push({at: Math.round(performance.now() - started), top: Math.round(box.top),
                  opacity: Number(style.opacity), visible: style.visibility === 'visible'});
  };
  take();
  /*CHANGE*/
  const next = () => {
    take();
    if (performance.now() - started < span) requestAnimationFrame(next);
    else resolve(samples);
  };
  requestAnimationFrame(next);})"""

# How long the frames are sampled: the leave, the move and the return all fit.
SAMPLED_FOR = 1200

# AT FULL OPACITY — what a reader reads as the message itself, not its fade.
FULL = 0.99

# WHOLLY GONE FROM PAINT — at or under it, nothing of the message is read.
GONE = 0.05

# HOW FAR A BOX MUST TRAVEL BETWEEN TWO FRAMES TO BE A JUMP rather than the
# fourteen pixels of its own entrance.
JUMP = 20

# HOW FAR APART THE TWO EDGES ARE, at the least, for « it changed edge ».
ACROSS = 100


def hold_no_jump(journal, change, samples):
    """Holds that a message seen across a layer change leaves and comes back.

    THE DEFECT: a message up on a screen that closed crossed the frame from its
    top to its bottom between two frames at full opacity, while it was being
    read (y 16 → 724). The property is the reader's: a shown message that must
    change edge fades out where it is and appears at the other edge. So the
    hold is on CONSECUTIVE frames — no two frames at full opacity with the box
    in two places. « No frame at full opacity outside both edges » would not
    fall: each frame of that jump is at one of the two edges.

    RE-AIMED A SECOND TIME: those holds stayed green over a message moved 50 ms
    into its fade, never at full opacity in two consecutive frames. So it also
    holds a frame WHOLLY GONE between the last frame seen at the first place
    and the first frame seen at the other edge.

    Args:
        journal: Where the holds are recorded.
        change: What changed the layers, for the holds' own text.
        samples: The frames `ACROSS_THE_CHANGE` recorded.
    """
    def full(one):
        return one["visible"] and one["opacity"] >= FULL

    first, last = samples[0], samples[-1]
    journal.check(f"{change}: the message is fully drawn at its first place before the change",
                  full(first), str(first))
    journal.check(f"{change}: and it ends fully drawn at the OTHER edge",
                  full(last) and abs(last["top"] - first["top"]) >= ACROSS,
                  f"{first['top']} → {last['top']}, opacity {last['opacity']}")
    # « There » is within the fade's own travel: a leaving message slides the
    # fourteen pixels of its exit while its opacity falls.
    faded = [one for one in samples
             if abs(one["top"] - first["top"]) <= JUMP and 0.05 < one["opacity"] < 0.95]
    journal.check(f"{change}: it LEFT its first place through its fade — a frame drawn there partly faded",
                  bool(faded), f"{len(faded)} of {len(samples)} frame(s)")
    jumps = [(one, other) for one, other in zip(samples, samples[1:])
             if full(one) and full(other) and abs(one["top"] - other["top"]) > JUMP]
    journal.check(f"{change}: NEVER A JUMP — no two consecutive frames at full opacity in two places",
                  not jumps, str(jumps[:2]))
    # WHOLLY GONE BETWEEN ITS TWO PLACES. Moved 50 ms into its fade, the message
    # sat at the first place at 0.4 opacity and the next frame at the other edge
    # rose from 0.4: never two full frames apart, so the hold above was green
    # over a teleport. A frame showing nothing of it must come between.
    arrived = next((index for index, one in enumerate(samples)
                    if abs(one["top"] - first["top"]) >= ACROSS and one["opacity"] > GONE), None)
    left = None
    if arrived is not None:
        left = max((index for index, one in enumerate(samples[:arrived])
                    if abs(one["top"] - first["top"]) <= JUMP and one["opacity"] > GONE), default=None)
    gap = samples[left + 1:arrived] if left is not None else []
    journal.check(f"{change}: WHOLLY GONE between its two places — a frame at or under {GONE} opacity after "
                  "the last seen at the first place and before the first seen at the other edge",
                  arrived is not None and any(one["opacity"] <= GONE for one in gap),
                  f"frames {left} → {arrived}, opacities {[one['opacity'] for one in gap][:6]}")


# THE HOST'S OWN LENGTHS, `app/toast-host.ts`: a message's life, one offering an
# undo, and the exit — the floor below which a message owed that little ends by
# leaving.
MESSAGE_MS = 5000
MESSAGE_WITH_UNDO_MS = 6000
EXIT_MS = 400

# WHERE THE CROSSING LANDS in the life: owed a readable length, and owed less
# than the exit — both inside the last 600 ms.
LAST_OF_A_LIFE = 600
OWED_BACK = 560
OWED_LESS_THAN_THE_EXIT = 150

# What a whole return may fall short of what it was owed: the frames its
# entrance and its exit take to cross full opacity, with room for a loaded host.
TOLERANCE = 100
# The away, the entrance, the owed life and the exit all fit.
SAMPLED_TO_THE_END = 2000

# THE MESSAGE SHOWN, A SCREEN CLOSED `lead` MILLISECONDS LATER, AND EVERY FRAME
# AFTER — sampled as `ACROSS_THE_CHANGE` does. The moment of the change is read
# on the same clock as the moment of the show, so what the message was owed is
# measured, never assumed from a timer that may fire late on a loaded host.
AT_THE_END_OF_ITS_LIFE = """([text, undo, lead, span])=>new Promise((resolve)=>{
  const host = document.querySelector('#toast');
  const samples = [];
  const shownAt = performance.now();
  window.__toast.show(undo ? {message: text, undo: () => {}} : {message: text});
  const take = () => {
    const box = host.getBoundingClientRect();
    const style = getComputedStyle(host);
    samples.push({at: Math.round(performance.now() - shownAt), top: Math.round(box.top),
                  opacity: Number(style.opacity), visible: style.visibility === 'visible'});
  };
  setTimeout(() => {
    take();
    const changedAt = performance.now() - shownAt;
    history.back();
    const next = () => {
      take();
      if (performance.now() - shownAt - changedAt < span) requestAnimationFrame(next);
      else resolve({changedAt: Math.round(changedAt), samples});
    };
    requestAnimationFrame(next);
  }, lead);})"""


def hold_what_is_owed(journal, change, duration, reading, comes_back):
    """Holds that a crossing near the end of a message's life takes nothing from it.

    THE DEFECT: the life clock ran through the crossing's 400 ms away, so a
    message that changed edge at 4 419 ms of its 5 000 came back with 181 ms
    left — about twenty milliseconds whole, a flash at the other edge. The
    clock now stops while the message is away, and a message owed less than
    its own exit ends by leaving.

    Args:
        journal: Where the holds are recorded.
        change: What changed the layers, and when, for the holds' own text.
        duration: The life the message was shown with.
        reading: What `AT_THE_END_OF_ITS_LIFE` recorded.
        comes_back: Whether the owed life is one the message comes back for.
    """
    owed = duration - reading["changedAt"]
    samples = reading["samples"]
    first = samples[0]

    def whole(one):
        return one["visible"] and one["opacity"] >= FULL

    there = [one for one in samples[1:] if abs(one["top"] - first["top"]) >= ACROSS]
    journal.check(f"{change}: the message is whole at its first place when the screen closes",
                  whole(first), str(first))
    if comes_back:
        journal.check(f"{change}: the change lands inside the last {LAST_OF_A_LIFE} ms, owing no less than the exit",
                      EXIT_MS <= owed <= LAST_OF_A_LIFE, f"owed {owed} ms")
        drawn = [one["at"] for one in there if whole(one)]
        kept = drawn[-1] - drawn[0] if drawn else 0
        journal.check(f"{change}: it comes back at the other edge WHOLE for at least the {owed} ms it was owed",
                      kept >= owed - TOLERANCE, f"whole there for {kept} ms over {len(drawn)} frame(s)")
    else:
        journal.check(f"{change}: the change lands owing less than the {EXIT_MS} ms exit",
                      0 < owed < EXIT_MS, f"owed {owed} ms")
        seen = [one for one in there if one["opacity"] > GONE]
        journal.check(f"{change}: owed {owed} ms, it ends by leaving — never drawn at the other edge",
                      not seen, str(seen[:3]))


async def show_over(page, state, wait):
    """Drives a state, clears the message on screen and shows the probe.

    Args:
        page: The page.
        state: The named state to drive.
        wait: How long the state takes to settle.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(wait)
    await page.evaluate(HIDE)
    await page.wait_for_timeout(SETTLED)
    await page.evaluate(SHOW, PROBE)
    await page.wait_for_timeout(SETTLED)


async def main():
    journal = Journal("R159 — a message said while a layer is open is seen and takes a finger")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # ── PAINT ────────────────────────────────────────────────────────────
        # 1. Over an open bottom sheet.
        await show_over(page, SHEET_STATE, SETTLED)
        over_sheet = await page.evaluate(PAINTED_ON_TOP, PROBE)
        journal.check("with a bottom sheet open, a message is painted on top at its own text",
                      over_sheet.get("onTop") is True, str(over_sheet))

        # 2. On the follow panel, after the panel's own verb.
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        title = await page.evaluate(THE_FOLLOW_WITH_A_HOLE)
        journal.check("the fixture holds a follow with a hole, drawn on the follows list",
                      bool(title), str(title))
        if title:
            await page.evaluate(HIDE)
            row = await page.evaluate(AIM, ["[data-panel]", title])
            if row.get("found") and row.get("reachable"):
                await page.touchscreen.tap(row["x"], row["y"])
                await page.wait_for_timeout(PANEL_IN)
            act = await page.evaluate(AIM, ['#sheetin [data-part="season/grab"]', None])
            journal.check(f"« {title} »'s panel offers its season verb to a finger",
                          act.get("found") and act.get("reachable"), str(act))
            if act.get("found") and act.get("reachable"):
                await page.touchscreen.tap(act["x"], act["y"])
                await page.wait_for_timeout(ACTED)
                said = await page.evaluate(SAID)
                seen = await page.evaluate(PAINTED_ON_TOP, said[:24]) if said else {"carried": False}
                journal.check("and the sentence the verb chose is painted on top, over the panel it was pressed in",
                              bool(said) and seen.get("onTop") is True, f"{said!r} {seen}")

                # 6. The verb's own answer is placed off the panel it was pressed in.
                placed = await page.evaluate(MEETS, SHEET_CONTROLS)
                journal.check("the verb's answer meets none of the panel's controls — the next verb stays free",
                              placed["shown"] and placed["controls"] > 0 and not placed["met"], str(placed))
                close = await page.evaluate(AIM_AT_THE_CLOSE)
                journal.check("and its close takes a finger where it is placed — nothing lifted",
                              close.get("found") and close.get("reachable"), str(close))
                if close.get("found") and close.get("reachable"):
                    await page.touchscreen.tap(close["x"], close["y"])
                    await page.wait_for_timeout(SETTLED)
                journal.check("and the finger takes the verb's answer off screen",
                              await page.evaluate(SHOWN) is False)

        # 3. On the media screen — the witness.
        await page.evaluate("()=>window.__panel?.close?.()")
        await show_over(page, SCREEN_STATE, SETTLED * 3)
        over_screen = await page.evaluate(PAINTED_ON_TOP, PROBE)
        journal.check("on the media screen, a message is painted on top at its own text — the "
                      "screen never covered it",
                      over_screen.get("onTop") is True, str(over_screen))

        # ── TOUCH ────────────────────────────────────────────────────────────
        # 4. Over an open bottom sheet, nothing lifted, a real finger.
        await show_over(page, SHEET_STATE, SETTLED)
        close = await page.evaluate(AIM_AT_THE_CLOSE)
        journal.check("with a bottom sheet open, the message's close takes a finger — nothing lifted",
                      close.get("found") and close.get("reachable"), str(close))
        if close.get("found") and close.get("reachable"):
            await page.touchscreen.tap(close["x"], close["y"])
            await page.wait_for_timeout(SETTLED)
        journal.check("and the finger takes the message off screen",
                      await page.evaluate(SHOWN) is False)

        # ── PLACEMENT ────────────────────────────────────────────────────────
        # 8. No layer open: at the bottom, as it always was. Read FIRST, because
        # its box at rest is what leg 9 compares with.
        await page.evaluate("()=>window.__panel?.close?.()")
        await show_over(page, BARE_STATE, SETTLED)
        bare = await page.evaluate(MEETS, None)
        journal.check("with no layer open, the message is at the bottom — above the tab bar, in the lower half",
                      bare["shown"] and bare["barTop"] is not None and bare["box"][1] <= bare["barTop"]
                      and bare["box"][0] > bare["height"] / 2, str(bare))
        await page.evaluate(HIDE)
        await page.wait_for_timeout(EXITED)
        bare_at_rest = (await page.evaluate(MEETS, None))["box"]

        # 5. A message up before the layer opens — the boot hint's shape.
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(HIDE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(SHOW, PROBE)
        await page.wait_for_timeout(SETTLED)
        first = await page.evaluate("()=>(window.__followActions?.all() || [])[0]?.t || ''")
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", first)
        await page.wait_for_timeout(PANEL_IN)
        before = await page.evaluate(MEETS, SHEET_CONTROLS)
        journal.check("a message up before a sheet opens meets none of the sheet's controls once it is open",
                      before["shown"] and before["controls"] > 0 and not before["met"], str(before))
        reach = await page.evaluate(ACTIONS_REACHABLE)
        journal.check("and each of the sheet's actions is what a finger at its centre lands on",
                      reach["actions"] > 0 and not reach["missed"], str(reach))

        # 9. At rest, hidden while the layer is still open: back to the bottom box.
        await page.evaluate(HIDE)
        await page.wait_for_timeout(EXITED)
        at_rest = await page.evaluate(MEETS, None)
        journal.check("at rest, a message hidden while a layer is open is back in the bottom box",
                      at_rest["box"] == bare_at_rest, f"{at_rest['box']} against {bare_at_rest}")

        # 7. Over a confirmation.
        await page.evaluate("()=>window.__panel?.close?.()")
        await page.evaluate("(id)=>window.__go(id)", SELECTION_STATE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(A_TALL_CONFIRMATION)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(SHOW, PROBE)
        await page.wait_for_timeout(SETTLED)
        button = await page.evaluate("""(selector)=>{
          const one = document.querySelector(selector);
          if (!one) return null;
          const box = one.getBoundingClientRect();
          return [Math.round(box.top), Math.round(box.bottom)];}""", CONFIRMATION_BUTTONS)
        # The band starts where the bottom message's box starts (leg 8) and runs
        # to the foot of the screen.
        journal.check("the confirmation's button is on screen and in the bottom band — else the next hold reads nothing",
                      button is not None and button[1] > bare["box"][0] and button[1] <= bare["height"],
                      f"button {button}, band from {bare['box'][0]} to {bare['height']}")
        over_dialog = await page.evaluate(MEETS, CONFIRMATION_BUTTONS)
        journal.check("over a confirmation, the message meets none of its buttons",
                      over_dialog["shown"] and over_dialog["controls"] > 0 and not over_dialog["met"],
                      str(over_dialog))
        await page.evaluate("()=>window.__dialog.close()")

        # 10. On every kind of screen, « Retour » takes a finger with a message up.
        for kind, state in SCREEN_STATES.items():
            await show_over(page, state, SETTLED * 3)
            under = await page.evaluate(BACK_UNDER)
            journal.check(f"on the {kind} screen, a message up sits below the screen's bar and "
                          "« Retour » takes a finger — nothing lifted",
                          under.get("shown") is True and under.get("reachable") is True
                          and under["message"][0] >= under["barBottom"], str(under))
            if under.get("reachable"):
                await page.touchscreen.tap(under["x"], under["y"])
                await page.wait_for_timeout(SETTLED * 2)
            left = await page.evaluate(OPEN_SCREEN)
            journal.check(f"and the finger on « Retour » leaves the {kind} screen",
                          under.get("screen") is not None and left != under.get("screen"),
                          f"{under.get('screen')!r} → {left!r}")

        # 11. A message the reader has seen, across a layer change: never a jump.
        await show_over(page, SCREEN_STATE, SETTLED * 3)
        closing = await page.evaluate(
            ACROSS_THE_CHANGE.replace("/*CHANGE*/", "history.back();"), SAMPLED_FOR)
        hold_no_jump(journal, "a screen closes", closing)

        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(HIDE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(SHOW, PROBE)
        await page.wait_for_timeout(SETTLED)
        first = await page.evaluate("()=>(window.__followActions?.all() || [])[0]?.t || ''")
        opening = await page.evaluate(
            ACROSS_THE_CHANGE.replace(
                "/*CHANGE*/", f"window.__panel.produce('follow', {first!r});"),
            SAMPLED_FOR)
        hold_no_jump(journal, "a sheet opens", opening)

        # 12. A crossing near the end of a life takes nothing from it.
        for undo, duration, owed, comes_back in (
                (False, MESSAGE_MS, OWED_BACK, True),
                (True, MESSAGE_WITH_UNDO_MS, OWED_BACK, True),
                (False, MESSAGE_MS, OWED_LESS_THAN_THE_EXIT, False)):
            await page.evaluate("()=>window.__panel?.close?.()")
            await page.evaluate("(id)=>window.__go(id)", SCREEN_STATE)
            await page.wait_for_timeout(SETTLED * 3)
            await page.evaluate(HIDE)
            await page.wait_for_timeout(EXITED)
            reading = await page.evaluate(
                AT_THE_END_OF_ITS_LIFE, [PROBE, undo, duration - owed, SAMPLED_TO_THE_END])
            with_undo = " with « Annuler »" if undo else ""
            hold_what_is_owed(journal, f"a screen closes {owed} ms before the end of a message{with_undo}",
                              duration, reading, comes_back)
            await page.wait_for_timeout(EXITED)

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
