# L13 — the rulings, one file (numbered, non-reopenable)

One line per ruling, its author, and the commit whose RESUME or phase amendment carries the full text (`git show
<sha>:docs/features/maquette-l13/RESUME.md`). L13a's 1–61 are copied here once; L13b and L13c APPEND, never rewrite.
An agent reads THIS file before its handshake — not the RESUME chain.

## L13a (2026-09-13)

1. `harness` is a declared bucket of `check-frontend-boundaries.py` — a·1, `123816c93`.
2. `design/src/harness/` is in the language guard's harness scope for the STRING arm only — a·1.
3. The product never depends on the instrument; `applyState` stays engine-side (a·3 part voided by 16) — a·1.
4. `drivenWithoutHistory(run)` is the engine's one addition; `driven` in the vocabulary — a·1.
5. `currentRender = null` was not carried — a·1.
6. `window.__navEchec = false` initialisation stays in the engine — a·1.
7. `installHarness()` takes no argument; the ≡ panel was `harness/panel.ts` (died at a·17-bis, ruling 31) — a·1.
8. The named states are eleven files under `harness/states/`, composed by `harness/index.ts` — a·1.
9. R1 — the four shell doors live in `lib/shell-doors.ts` (`toast`, `panel`, `bridge`, `screens`); `store` in `lib/store-access.ts`; app hosts are not import owners (fan-in) — a·2, `36cc38a4c`.
10. R2 — `features/acquisition/queries.ts` in `FAN_IN_EXEMPT`; the L13b phase deleting the engine's last read of `followActions`/`suggestions` removes it (b·5/b·11) — a·2.
11. The six product writes `window.__navEchec = true` stay — a·2.
12. `window.__mocks` stays published by the mock layer; only `app/` imports `mocks/` — a·2.
13. `knownMedium` fixture-backed until its killer phase (→ b·10-bis by 41) — a·3, `58d24cfc4`.
14. `navigationState` lives in `lib/navigation-entry.ts`; entry dials written ONCE (`ENTRY_DIALS`) — a·3.
15. `frame-domain-baseline.json` lib 18 → 23 — a·3.
16. `applyState` stays in the engine beside `render()`, handed in through `installPageRestore`; it leaves at b·7 — a·3.
17. `unwinding`/`currentRender` stay with `closeScreen` until a·5 — a·3.
18. `harness/publish.ts` publishes `__closeLayers` and `armedExit`; `BACK_WINDOW` converted — a·3.
19. `app/arrival.ts` holds `INITIAL_STATE` and `installArrival(store)` — a·4.
20. `frame-domain-baseline.json` app 130 → 138 — a·4.
21. `fixture-register.json` `$anonymous.count` 1 → 0; `boot_order.py` and `bridge.py` (f′) re-aimed — a·4.
22. Q4: a dead `#screen` rung is REMOVED, a field is re-aimed; `bridge.py` reads `[data-key^="mediaSheet:"]` — a·5, `84fee5532`.
23. `window.__close`'s readers use `window.__panel.close()` / `__bridge.back()` — a·5.
24. `openDetailSheet` went with the generic `sheet` branch; `boot_order.py` intact — a·5.
25. The join is `sheetFor`'s four tiers in `build-mock-seeds.py`; `ids`/`poster` on list schemas; `Follow.ids` non-null — a·6.
26. B-497 filed: `build-mock-seeds.py --check` reports converted seeds as orphans (`--write` would delete 22) — a·6.
27. OPERATOR: the cut is B — L13a → L13b → L13c, three pull requests, one reader round and Mac walk each.
28. OPERATOR: D-L13-1 = A, ratified as written; L13b's STOP E lifted.
29. OPERATOR: Q2 = B, the ≡ harness panel dies (refined by 31).
30. a·7's four bare `sec` repairs accepted as a conversion (45 divergences named) — a·7.
31. The ≡ PANEL dies alone as a·17-bis: `harness/bar` and `#notesBtn` STAY; `hiding.py`/`chrome.py` do not move; `panel_verbs.mjs` is not a reader — steward, `be6f2a32c`.
32. R80's floor moves to the MEASURED count, every pair added/removed named — steward, a·8.
33. `.poster` is not paired (`-webkit-touch-callout`) — a·8.
34. Action buttons are axes of `actionButton()` (`kind` × `tone`) — a·8.
35. `.btnprimary:disabled` moved to `base.css` unlayered; c·3 draws the disabled state — a·8.
36. Every log under `/private/tmp/tm-l13a/` (L13b: `/private/tmp/tm-l13b/`), gate logs kept until the merge — a·8.
37. The card is PARTS in `ui/card.tsx`, factories in `ui/variants/card.ts` — a·9, `0cb5ce960`.
38. A card's domain composition stays in its feature; features never import each other — a·9.
39. No card rule dies before `cardHTML` does — a·9.
40. The card's French lives in `surfaces.card.*`; poster-box floor and `LOCAL_DETAILS` re-taken per phase — a·9.
41. `LIBRARY`, `INCOMPLETE`, `knownMedium` die at b·10-bis (exact membership read), not a·10 — steward, `c8995c858`.
42. String-composed surfaces get a MARKUP spelling in `ui/` (`tileMarkup`, `swipeRowMarkup`, …) — a·10.
43. R77 reads identities, never a class-string equality; `page_host.py` at its 999 ceiling — a·10.
44. Tile badges' no-fill defect carried, not repaired (register at the gesture) — a·10.
45. `POSTERS` died at a·13 with `poster` on DecisionCandidate/DecisionChoice — steward, `a6c91fc57`.
46. `page_host.py` 999/1000: compaction refused, zero-net-line edit allowed and said, the first added line extracts a module — auditor.
47. A served field differing from the engine's answer is a JOIN miss repaired in the data (base-title fallback) — steward, `1e34b9660`.
48. `heavy.sh` counts « Pages speculative » — auditor order 3, `1a73ff2ea`.
49. `mutate.sh` reads a rule's exit code as a fall — steward, `4c0e1d036`.
50. a·14 lands as two commits — steward.
51. a·14.2 stays in L13a: the crossing carries what the tap knew into the navigation ENTRY (amended by 55) — auditor, `379279643`.
52. `SEASONS` → a·14.2 with the `window.__mocks` accessor (amended by 53) — steward.
53. `SEASONS` stays until b·10-bis: the engine's fixture LIES (Silo S4); the follow panel must agree with the SERVED sheet — steward, `4ced4b26d`.
54. The ONE `window.__mocks` seed accessor lands sheets-only, harness-read — steward.
55. Reading (A): a tap primes title and poster only; year/genre/synopsis/cast skeletons in flight; D8-named on every tap (reader line + Mac step owed) — auditor.
56. `screens.media.synopsisUnread` reads « Synopsis non lu. » — steward.
57. a·16 lands settings only; the React-side engine support dies at b·11; twelve interface constants need homes — steward, `c194fca54`.
58. The lot's folder `docs/features/maquette-l13/` survives L13a, dies at L13c's gesture — auditor.
59. `residue.py`'s reader half → `harness/factories.py`; pull spinner utilities on the child `.spin`; #ptr utilities erased by `__reposPTR` filed for b·8 — steward, `e2f510a8b`.
60. Narrow authorization: reference docs edited ONLY to re-cite a deleted full path `@60530dbd8`; CLAUDE.md never on a peer's word — steward.
61. The STOP B (cold follow panel loses « Voir la fiche ») repaired IN L13a as a restoration: the panel's facts follow the identity read, re-produced in place, no history entry; mutation seen; empty-key query entries filed for b·10-bis — auditor, `57f3e81af`.

62. OPERATOR (19:2x, relayed): the implementer's context gate is 80 %, not 60; pre-dispatch = gauge + last phase's measured cost ≤ 80 — `37e54d0fd`.
63. Auditor order 15: the wave does not write IMPLEMENTATION.md's « In flight » row; the register's `fixed #<PR>` rows stay in the closure commit — `37e54d0fd`.

## L13b — append below, numbered from 64
