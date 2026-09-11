"""The page scripts R140 reads the prototype with.

They live beside the rule rather than inside it because the rule crossed its
module ceiling, and this is the seam that was already there: everything here
runs IN THE PAGE and answers a question, while `desktop_frame.py` decides what
the answers mean. Splitting anywhere else would have cut a hold from its
reading.

Each is a string evaluated by Playwright, so nothing here imports anything and
nothing here is called from Python except through `page.evaluate`.
"""

READ_FORCED = """(forced)=>{
  const out = {};
  for (const [selector, property] of forced) {
    const el = document.querySelector(selector);
    out[selector + " · " + property] =
      el ? getComputedStyle(el).getPropertyValue(property) : null;
  }
  return out;
}"""
# The control document: the frame's whole contribution is written `.device ...`,
# so an element that has stopped answering to that class is the app's cascade
# and nothing else. The class goes back on before the reading is returned.
UNFRAMED = """(forced)=>{
  const device = document.getElementById('device');
  device.classList.remove('device');
  const out = {};
  for (const [selector, property] of forced) {
    const el = document.querySelector(selector);
    out[selector + " · " + property] =
      el ? getComputedStyle(el).getPropertyValue(property) : null;
  }
  device.classList.add('device');
  return out;
}"""
# A rect and the three ways a control can still be there after being hidden: a
# box, a point a finger lands on, and the focus order. `elementFromPoint` is
# asked at the corner the control occupies when it IS drawn, so the question is
# « is anything of it under that finger », not « does it have a size ».
PRESENCE = """(selectors)=>{
  const [switchSelector, label, checkbox] = selectors;
  const node = document.querySelector(switchSelector);
  if (!node) return {missing: true};
  const box = node.getBoundingClientRect();
  const at = document.elementFromPoint(20, 20);
  const input = document.querySelector(checkbox);
  input.focus();
  const focused = document.activeElement === input;
  input.blur();
  return {missing: false,
          rects: node.getClientRects().length,
          area: box.width * box.height,
          underFinger: !!(at && at.closest(switchSelector)),
          focused: focused};
}"""
COVERS = """(argument)=>{
  const [switchSelector, chrome] = argument;
  const node = document.querySelector(switchSelector);
  const a = node.getBoundingClientRect();
  if (!a.width) return ['ABSENT'];
  const crosses = (b) => !(a.right <= b.left || b.right <= a.left
                           || a.bottom <= b.top || b.bottom <= a.top);
  return [...document.querySelectorAll(chrome)]
    .filter((el) => el.getClientRects().length > 0)
    .filter((el) => crosses(el.getBoundingClientRect()))
    .map((el) => el.getAttribute('data-part') || el.id || el.tagName);
}"""
# THE OTHER DIRECTION, and the sweep asked only one of them. « What does the
# control cover » and « what covers the control » are different questions with
# different answers: a layer the app paints AFTER the control, at the same
# stacking rank, wins on document order and takes the press while every
# crossing count reads zero. The control is the way BACK into the frame — if a
# finger cannot reach it, the operator is stranded in the state that covers it,
# and the keyboard still working is a consolation rather than an answer.
#
# Read at the centre AND the four corners, because a layer that covers half of
# a control leaves it half usable, which is not a state worth shipping either.
WHAT_COVERS_IT = """(argument)=>{
  const [switchSelector, label] = argument;
  const node = document.querySelector(switchSelector);
  if (!node) return ['ABSENT'];
  const a = node.getBoundingClientRect();
  if (!a.width || !a.height) return ['NOT DRAWN'];
  const ours = document.querySelector(label);
  const points = [[a.left + a.width / 2, a.top + a.height / 2],
                  [a.left + 1, a.top + 1], [a.right - 1, a.top + 1],
                  [a.left + 1, a.bottom - 1], [a.right - 1, a.bottom - 1]];
  const strangers = [];
  for (const [x, y] of points) {
    const top = document.elementFromPoint(x, y);
    if (!top) { strangers.push('nothing'); continue; }
    if (node.contains(top) || (ours && ours.contains(top))) continue;
    strangers.push(top.getAttribute('data-part') || top.id
                   || top.className || top.tagName);
  }
  return [...new Set(strangers)];
}"""
OUT_OF_THE_FRAME = """(argument)=>{
  const [checkbox, device] = argument;
  const box = document.querySelector(device).getBoundingClientRect();
  return {checked: document.querySelector(checkbox).checked,
          fillsTheWindow: Math.round(box.width) === window.innerWidth
                          && Math.round(box.height) === window.innerHeight,
          box: [Math.round(box.x), Math.round(box.y),
                Math.round(box.width), Math.round(box.height)]};
}"""
CROSSED = """(argument)=>{
  const [switchSelector, interactive, harness] = argument;
  const node = document.querySelector(switchSelector);
  if (!node) return ['ABSENT'];
  const a = node.getBoundingClientRect();
  if (!a.width || !a.height) return ['NOT DRAWN'];
  const crosses = (b) => !(a.right <= b.left || b.right <= a.left
                           || a.bottom <= b.top || b.bottom <= a.top);
  return [...document.querySelectorAll(interactive + ', ' + harness)]
    .filter((el) => el !== node && !node.contains(el) && !el.contains(node))
    .filter((el) => el.getClientRects().length > 0)
    .filter((el) => crosses(el.getBoundingClientRect()))
    .map((el) => el.getAttribute('data-part') || el.id
                 || (el.textContent || '').trim().slice(0, 24) || el.tagName);
}"""
LABELLED = """(argument)=>{
  const [checkbox, label] = argument;
  return document.querySelector(label).control
         === document.querySelector(checkbox);
}"""
# THE PROBE CARRIES THE FRAME'S OWN DECLARATIONS, read from the stylesheet, and
# is mounted in the device's own parent so that a percentage resolves against
# the same containing block. Whatever the browser computes for it is what the
# declaration means; the device must read the same, or the declaration has
# stopped arriving. `background: red` then differs from the token's colour and
# the hold falls, which « differs from the control document » could never see.
WHAT_THE_DECLARATIONS_MEAN = """(argument)=>{
  const [device, token] = argument;
  const el = document.querySelector(device);
  const probe = document.createElement('div');
  probe.style.background = 'var(' + token + ')';
  el.parentElement.appendChild(probe);
  const background = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return {'background-color': background};
}"""
DEVICE_BOX = """(argument)=>{
  const [device, skin, survives, dynamic] = argument;
  const el = document.querySelector(device);
  const box = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  const out = {rect: [Math.round(box.x), Math.round(box.y),
                      Math.round(box.width), Math.round(box.height)]};
  for (const property of skin) out[property] = style.getPropertyValue(property);
  for (const property of survives)
    out['survives:' + property] = style.getPropertyValue(property);
  for (const property of dynamic)
    out['dynamic:' + property] = style.getPropertyValue(property);
  return out;
}"""
# The same removal the FORCED control document uses, on the device itself: the
# frame's whole contribution is written `.device …`, so the element with that
# class off is what the app's cascade alone says about it.
UNFRAMED_DEVICE = """(argument)=>{
  const [device, skin, dynamic] = argument;
  const el = document.querySelector(device);
  el.classList.remove('device');
  const style = getComputedStyle(el);
  const out = {};
  for (const property of skin) out[property] = style.getPropertyValue(property);
  for (const property of dynamic)
    out['dynamic:' + property] = style.getPropertyValue(property);
  el.classList.add('device');
  return out;
}"""
# THE NAME AGAINST THE WORD ON SCREEN. An accessible name is computed from the
# label's RENDERED subtree, so the hold that only asked the two states to
# differ was green over a control announcing « Sortir du cadre Revenir au
# cadre » — one word against two are never equal. The question is not whether
# the name changes; it is whether the name is the word the operator can read.
VISIBLE_WORDS = """(label)=>{
  return [...document.querySelector(label).querySelectorAll('span')]
    .filter((span)=>span.getClientRects().length > 0)
    .map((span)=>span.textContent.trim());
}"""
# The label's right edge against the frame's left edge. Read at the TIGHTEST
# width rather than at 1280, where the gutter is 332px wide and any constant
# between 195 and 500 would pass — a hold placed where nothing can go wrong
# measures nothing.
# THE ABSENT CONTROL READS ZEROS, AND ZEROS PASS. `getBoundingClientRect` on a
# `display: none` element is all zeros, so `frameLeft - 0` is a comfortable
# positive gap and the hold that exists to catch an overlap was green over a
# control that was not drawn at all. 520px is the ONLY width where the
# control's PRESENCE can be read — 390 requires it absent and at 1280 the
# gutter is 332px — so the breakpoint regressing to 700px would leave all
# nineteen holds green and the operator with no way out of the frame at 640.
# The reading says which case it is instead of collapsing them.
GEOMETRY = """(argument)=>{
  const [switchSelector, device] = argument;
  const node = document.querySelector(switchSelector);
  const box = node.getBoundingClientRect();
  const frame = document.querySelector(device).getBoundingClientRect();
  const input = document.querySelector('#desktop-switch');
  input.focus();
  const focused = document.activeElement === input;
  input.blur();
  return {drawn: node.getClientRects().length > 0 && box.width > 0
                 && box.height > 0,
          rects: node.getClientRects().length,
          area: Math.round(box.width * box.height),
          focusable: focused,
          labelRight: Math.round(box.right),
          frameLeft: Math.round(frame.left),
          gap: Math.round(frame.left - box.right)};
}"""
OUTSIDE = """(argument)=>{
  const [switchSelector, device] = argument;
  return !document.querySelector(device)
            .contains(document.querySelector(switchSelector));
}"""
NOTHING_IS_MOVING = """()=>document.getAnimations()
  .every((one)=>one.playState !== 'running')"""
