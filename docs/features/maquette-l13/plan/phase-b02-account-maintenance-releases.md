# Phase b·2 — Account, maintenance, releases

A BEHAVIOUR move: `signout`, `sheet=utilisateur`, `maintact`, `releases` and `profile` are
registered by their features, and their engine branches are deleted. `releases` and `profile` are
two of the five surface-opening verbs (DESIGN § 6, row b·2; § 2.3).

## The proof FIRST

- **Re-take the rows before moving anything**: branches, emitters and rule taps (DESIGN § 6 method).
- **Rules green before and after, counts unchanged**: `page_host.py`'s `maintact` and `profile`
  holds, `panel.py`'s `maintact` holds, and the account panel's reader (the phase names which).
- **Names no rule holds get their hold FIRST**: `signout` and `releases` (DESIGN § 6).
  - **`signout`**: tap « Se déconnecter » from the account page. The entry screen is shown, and the
    session is gone (the pattern `logout.py` already reads). Red with the engine branch deleted on
    purpose.
  - **`releases`**: from a follow's panel, the releases verb opens the releases screen for that
    title, and the address says so. Red with the branch deleted on purpose.
- **Timers are kept as they are.** `releases` and `profile` still close the panel and open the
  screen 260 ms later (DESIGN § 6: « A move keeps its timer »). Each hold reads the OUTCOME after
  the timer, never the timer itself, so b·9 can change the shape without rewriting these holds.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes each `registerVerb`. The
  holding rule falls, naming the screen or the page that did not appear.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  every new hold named.

## The move

- **Registered with `registerVerb`**:
  - `signout` and `sheet=utilisateur` in `features/account/`;
  - `maintact` in `features/maintenance/`;
  - `releases` and `profile` in `features/releases/`.

  Each module is imported from `app/feature-verbs.ts`.
- **`sheet=utilisateur` is split** (DESIGN § 6, « One name, one owner »). The static avatar in
  `frontend/maquette/design/index.html` emits the account's own English name, renamed with
  `scripts/rename-identifiers.py` across markup, reader and rules; the rules tapping
  `data-sheet="utilisateur"` are re-aimed, counts unchanged, and the diff is re-read after the tool.
  `sheet=plus` is split the same way in b·5.
- **`signout`** calls the entry module directly, not `window.__entry`.
- **Deleted from `legacy.js`**: the branches. `scripts/frontend_size_ledger.py` is re-recorded
  DOWNWARD in the same commit.
- **The contract's count moves.** `grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)"`
  over `legacy.js` loses the `releases` and `profile` lines, and the reading goes in the report.

## Gate

Per INDEX « Gates ». In addition, the oracle shows zero divergence (STOP B otherwise). The two
first-holds' red readings and the mutations go in the report.

## Commit

`feat(maquette-l13): account, maintenance and releases answer their own delegation names`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** `app/entry.ts` reaches 4 fan-in keys exactly — the next importer is refused; every NEW `data-*` name's words enter `code-vocabulary.txt` in the same commit; frame-domain cost measured before and after.
