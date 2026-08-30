# Phases 8 and 9 — P27 and P30

Both were pulled into L11 by the operator on 2026-08-30, against `MODEL.md` § 3's assignment; the
lot's own « Done when » named neither.

## R109 — P27, and why it is a controlled PAIR

The first version held only that the proposal is absent under standalone. **It passed with the
check deleted from the application**: in a plain desktop context the banner never appears anyway,
because Android needs a `beforeinstallprompt` that no headless run fires. « Not offered » was
« never offered ».

The pair is an iPhone user agent — the one platform that offers the banner with no event at all.
Without standalone it must be **on screen**; with it, gone. Only the second reading is the
property; the first is what makes the second mean anything.

**Two limits, stated rather than worked around.** `Emulation.setEmulatedMedia` does not carry
`display-mode` in the Chrome this harness runs (measured, all three payload shapes), so the query
is answered in the page. That proves the *application's* branch, not that Chrome reports standalone
correctly when really installed — which only a home screen settles. And `install.py` already holds
the `navigator.standalone` branch; what R109 adds is the `display-mode` one, which an Android or
desktop install takes and which nothing read.

## R110 — P30, a ratchet by necessity

Chrome refuses to keep a page in the back-forward cache whenever a DevTools client is attached, and
Playwright is always one: `pageshow.persisted` came back `undefined` on a real walk out and back,
with and without `--enable-features=BackForwardCache`. A rule that cannot distinguish « the page was
rebuilt » from « this browser never keeps pages » is a rule about the harness.

So the runtime half is **device-only**, exercised and dated — `MODEL.md` § 3.1's precedent for the
interaction budget. What runs in CI is the ratchet, and it is the half that catches the regression:
the two handlers that evict are `beforeunload` and `unload`, the tree registers neither, and this
goes red the day someone adds the line — which looks harmless in every review.

## One trap paid for here, and it was mine

After mutation M16 the source was restored and **the bundle was not rebuilt**, so three subsequent
readings measured the mutated build. The rule was right and I was reading a stale `dist/`. Every
mutation in this wave rebuilds and re-copies inside the mutation helper for that reason.

## Done when

ACC-17 (P27), ACC-18 (P30's ratchet). R109/R110 — 7 holds, no violation.
