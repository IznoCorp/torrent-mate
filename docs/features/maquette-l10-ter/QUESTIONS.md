# L10-ter — the questions that belong to the operator

Each is settleable on its own, without re-reading the rest. Where the phase has a recommendation
it is written as such; where it has none, it says so. Nothing below blocks the plan as amended:
the plan is written on the recommendation, and an answer that differs amends it under § 7.1.

---

**Q1 — Desktop navigation: a rail, or the drawer alone?**
Context: at widths ≥ 768 px the tab bar hides (`md:hidden`) and the maquette draws no rail; the
burger's drawer is the only navigation. Production has a persistent `Sidebar` there. §12 says the
desktop must stay fully functional — it is, through the drawer — and it is not the starting point
of the drawing. (`SURVEY.md` § 4, B-235.)
Recommendation: **the drawer alone**, drawn as the navigation surface for every width, so one
navigation exists rather than two. If a rail is wanted, it is one more surface for L15 and it is
drawn in the maquette first.
Answer: ☐ drawer alone · ☐ a rail at ≥ md · ☐ later

**Q2 — The order of the product lots against the frame lots.**
Context: the plan now reads L15 (the frame) → L11 (offline) → L12 (native interaction) → L19 (the
producers) → L16 (§18 ratio) → L17 (§19 cross-seed) → L18 (§17 accounts) → L20 (the control
station) → L13 → L14. The three constitution sections and the two undrawn pages are therefore
four lots away from the next wave.
Recommendation: **as written** — a surface drawn after L12 and L19 inherits the transition
vocabulary, the offline queue and the producer template rather than being retrofitted with them.
The reverse order would draw §18's screens with engine-style producers and convert them twice.
Answer: ☐ as written · ☐ product lots first (L16 → L17 → L18 → L20, then L11 → L12 → L19)

**Q3 — Pull L14 forward?**
Context: L14 (the four files over 400 lines) has both dependencies landed and the plan already
says the operator may pull it forward between any two lots. L15 writes into `features/acquisition/`
and `features/library/`, whose pages are two of the four; it may not extend them (grandfathered
files are never extended), so it must create new files beside them either way.
Recommendation: **not now** — L15 is unaffected, and L14's whole subject is comfort. Pull it
forward before L19, which is the lot that will otherwise work inside the two largest files.
Answer: ☐ before L15 · ☐ before L19 · ☐ last, as written

**Q4 — Which platform entry points does the application owe?**
Context: L11's objective names « receiving a shared link, and being the handler its links
deserve ». The manifest can declare a `share_target` (another app shares a URL or a title into
TorrentMate — the natural entry is `/add?q=`), `launch_handler` (an installed app reopens its
existing window rather than a second one), and `handle_links` (the OS opens `tm.` links in the app).
None is drawn or declared today.
Recommendation: **all three**, with `share_target` landing on `/add` pre-filled — it is the one
that changes what the operator can do from another app.
Answer: ☐ all three · ☐ share target only · ☐ none yet

**Q5 — Is a Back with a dialog open a close, or a pop?**
Context: D1's third tier says a transient layer has no URL « but Back still closes it », and
names a confirmation as the example. The dialog today pushes no entry and Back pops the page under
it (B-229). Android closes a dialog on Back; the plan's own decision already says so.
Recommendation: **a close**, as D1 says — L15 adds the rung. Asked only because it changes what a
finger does, and a decision that changes that is dictated, not inferred.
Answer: ☐ close (D1 as written) · ☐ pop (amend D1's table)

**Q6 — Does the pipeline's running state belong in the chrome?**
Context: production shows a running/paused dot on the `/pipeline` tab. The maquette's chrome has
no such indicator; the connection mark says the STREAM is live, not that a run is. When `/pipeline`
is drawn (L20), a badge on its tab is one row in the navigation table.
Recommendation: **yes, as a tab badge on `/pipeline`** when that page exists — §1 says the
running pipelines are seen « au même endroit ».
Answer: ☐ yes, a tab badge · ☐ no, the page alone

**Q7 — The instrument for B-142: built by L15, or by the office under § 7.2's exception?**
Context: the mapping is written (`docs/reference/product-intent-map.md`); the arm that reads it
is specified (`MODEL.md` § 4). The brief forbids this phase from writing a guard; the steward's
office may write one over directive files. The arm reads two directive files and the tree's
route and feature NAMES.
Recommendation: **L15 builds it**, as the plan now says — it is the first wave after this one,
and a wave's arm gets a wave's adversarial review, which the office's exception does not carry.
Answer: ☐ L15 · ☐ the office, now

**Q8 — §17's four open points** are written into the constitution itself (§17 « Ce que cela ne
tranche pas ») and are not restated here: which roles; whether Plex SSO replaces or joins;
what becomes of a Plex user with no rights; what a Plex account sees by default. **L18 cannot
open without them** — it is written into that lot's entry as a blocking note, which is the
mechanism § 0 already has for a lot that waits on a decision.
