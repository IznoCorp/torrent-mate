# L10-ter — the questions that belong to the operator

**All nine answered by the operator on 2026-08-30**, one by one, and the plan, the constitution
(§17 completed, §20 new) and the clause map amended in the same pull request. The questions are
kept with their context so the answers can be read against what they answered.

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
**Answered 2026-08-30: drawer alone — and NOT frozen.** The operator stays open to a rail if real use asks for it; until then one navigation for every width. B-235 is not a defect.

**Q2 — The order of the product lots against the frame lots.**
Context: the plan now reads L15 (the frame) → L11 (offline) → L12 (native interaction) → L19 (the
producers) → L20 (the control station) → L16 (§18 ratio) → L17 (§19 cross-seed) → L18 (§17
accounts) → L13 → L14. The three constitution sections and the two undrawn pages are therefore
four lots away from the next wave.
Recommendation: **as written** — a surface drawn after L12 and L19 inherits the transition
vocabulary, the offline queue and the producer template rather than being retrofitted with them.
The reverse order would draw §18's screens with engine-style producers and convert them twice.
**Answered 2026-08-30: as written.**

**Q3 — Pull L14 forward?**
Context: L14 (the four files over 400 lines) has both dependencies landed and the plan already
says the operator may pull it forward between any two lots. L15 writes into `features/acquisition/`
and `features/library/`, whose pages are two of the four; it may not extend them (grandfathered
files are never extended), so it must create new files beside them either way.
Recommendation: **not now** — L15 is unaffected, and L14's whole subject is comfort. Pull it
forward before L19, which is the lot that will otherwise work inside the two largest files.
**Answered 2026-08-30: before L19.** L14 moves to Phase 5, ahead of the producers.

**Q4 — Which platform entry points does the application owe?**
Context: L11's objective names « receiving a shared link, and being the handler its links
deserve ». The manifest can declare a `share_target` (another app shares a URL or a title into
TorrentMate — the natural entry is `/add?q=`), `launch_handler` (an installed app reopens its
existing window rather than a second one), and `handle_links` (the OS opens `tm.` links in the app).
None is drawn or declared today.
Recommendation: **all three**, with `share_target` landing on `/add` pre-filled — it is the one
that changes what the operator can do from another app.
**Answered 2026-08-30: all three — « la meilleure intégration possible ».** Written into L11 as a principle: every entry point the platform offers an installed application is declared, unless a written reason says why not.

**Q5 — noted, not asked: a Back with a dialog open closes the dialog.**
D1's third tier already decides it (« Transient — no URL, but Back still closes it », a
confirmation being its own example), and §16 backs it. B-229 is an unimplemented decision, not an
open one; L15 implements it. Written here so the finger-visible change is announced rather than
discovered, and so nobody reads its absence from this list as a question skipped.

**Q6 — Does the pipeline's running state belong in the chrome?**
Context: production shows a running/paused dot on the `/pipeline` tab. The maquette's chrome has
no such indicator; the connection mark says the STREAM is live, not that a run is. When `/pipeline`
is drawn (L20), a badge on its tab is one row in the navigation table.
Recommendation: **yes, as a tab badge on `/pipeline`** when that page exists — §1 says the
running pipelines are seen « au même endroit ».
**Answered 2026-08-30: no badge, and no Pipeline tab.** The operator dictated §20 in the same breath — the pipeline becomes a tunnel per media, so there is no global run to signal; what the chrome must show « au même endroit » is what awaits the operator, and the Acquisition and Arrivées badges already do. L20 is re-cut to the global levers and the history.

**Q7 — Ratify or amend the clause map.**
Context: `docs/reference/product-intent-map.md` says « the operator amends this file; an agent
proposes ». Its 23 verdicts created four lots (L16, L17, L18, L20) and assigned nine instruments to
L19. An adversarial review already moved seven verdicts from `served` to `partly`; the rows are
what they are because a reader checked each proof, and the operator is the reader whose reading
counts.
Recommendation: **read the two tables once and mark any row whose verdict you would change**; a
row left unmarked is ratified.
**Answered 2026-08-30: ratified as written**, updated in the same pull request for §20 and the re-cut L20.

**Q9 — Do `/control` and `/pipeline` (L20) wait behind eight lots?**
Context: the mission of 2026-08-19 re-opened these two pages by name; the plan kept them « outside
this file, blocked by nothing ». This phase gave them a lot — because four DOIT clauses (1, 3, 5,
6) each have a half only those pages serve — and placed it after L15, L11, L12, L19, L16, L17 and
L18. That is a scope arbitration of the first order and neither branch of Q2 surfaces it: the
« product lots first » order still leaves L20 last of the four.
Recommendation: **after L19** — a page drawn before the producer template exists is drawn twice —
but **before the three constitution lots**, because it is the operator's own re-opening and the
clauses it serves are the oldest. The plan is written on the recommendation.
**Answered 2026-08-30: after L19, before L16, as written** — and re-cut by §20 to the global levers (the parallelism bound, pause and resume of everything, the watcher) and the history.

**Q8 — §17's four open points.** **Answered 2026-08-30, and written into §17 itself** (« Ce que
cela tranche »): three roles and two per-account options, the requester, the quality-profile
override, SSO added not substituted with e-mail linking, a rights-less Plex user admitted read-only
on the library, and what a default account sees. L18's blocking note is lifted. The backend's share
is in `docs/reference/backend-demands-architecture.md` § 2–3.
