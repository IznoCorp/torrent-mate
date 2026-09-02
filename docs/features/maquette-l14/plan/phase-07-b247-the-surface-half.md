# Phase 7 — B-247's surface half · behaviour

**Owns**: B-247 (surface half), B-295, D-L14-3, D-L14-4, D-L14-6. **Constitution**: §12 (a tap
lost to a re-render is a phone defect), §16 (nothing about the ladder moves). **Depends on
phases 5 and 6.**

## What changes

1. `ui/markup.tsx` — `useMarkup(html: string): { __html: string }`, a `useMemo` on the string,
   **and a `<Markup>` component that calls it.** *(Deviation from the design, which named
   `ui/markup.ts` and `useMarkup` at every site: a hook cannot be called inside a `.map`, and
   several sites are inside one. The component is where the hook is called — once, unconditionally
   — so every site is an element and the rule of hooks is kept by construction rather than by care.
   The file is `.tsx` because it renders.)*
   Its header says WHY (React 19 assigns `innerHTML` on the prop's identity, string unchanged or
   not — the comparison React 18 made) and names the one place the trick lives. Zero domain words.
2. Every `dangerouslySetInnerHTML={{ __html: … }}` under `design/src` becomes a `<Markup>`
   element — the component of item 1, never a `useMarkup(…)` call at the site: several sites are
   inside a `.map` or a helper closure, where a hook may not be called. `discover-tab.tsx`'s
   engine-filled containers are not among them (the engine owns their content).
3. `library-list.tsx`: `drawKey` becomes `` `${state.libMode}:${state.selMode}:${firstPageDraw}` ``
   where `firstPageDraw` is a counter kept in a ref that increments when
   `listing.data?.pages[0]` changes identity — D-L14-6. The comment that argued for keying on the
   version is replaced by the comment that says why not, keeping the sentence about the engine's
   inline transforms as the reason the reset EXISTS.
4. **R100 (f)** in `harness/persistence.py`: for each of `acq-now-loaded`, `acq-follows-list`,
   `acq-follows-grid`, `lib-list`, `lib-grid`, `mediasheet-series`, `arr-resolution`: drive the
   state, `quiet()`, capture the page's nodes (the design § 4.1's selector), `__store.touch()`,
   250 ms, hold « every captured node is the same node » with the captured count printed and a
   floor of 10 per state. The docstring's « what it does not read » gains the Découvrir containers
   (L19) and the legitimate redraws (selection mode, sort, delete). R100 stays on the contracts
   tier; its cost is measured and written in the commit.
5. `BUGS.md`: B-295 → `fixed #NNN`; B-247's body gains « surface half: fixed by L14 (#NNN), held by
   R100 (f); the producer half is L19's » — the row stays `open`.

## Definition of done

- `scripts/mutate.sh frontend/maquette/design/src/features/library/library-list.tsx
't.replace(<the drawKey expression>, "version")' frontend/maquette/harness/persistence.py` →
  (f) falls on `lib-list` and `lib-grid`; restored.
- `scripts/mutate.sh frontend/maquette/design/src/ui/markup.tsx 't.replace("useMemo(", "((f) => f())(")'`
  (or the exact form that returns a fresh object) → (f) falls on the three acquisition states;
  restored.
- **R117 green** (identity across a scroll is untouched), **R94** green, `selection.py`,
  `library_load.py`, `library_sort.py`, `filters.py` green — a delete still removes its row
  (`__deleteLibraryItems` rewrites the pages, which moves the first page's identity).
- The oracle: zero divergence (nodes at rest are the same markup).
- `python3 scripts/check-frame-domain.py | tail -1` → `ui/ 0` unchanged.
- Two commits: the repair (`fix(maquette-l14): a page's nodes keep identity across a store write —
B-247's surface half, B-295`), then the rule (`test(maquette-l14): R100 (f) …`).

## Deviations, recorded here rather than discovered later

- **A module the plan never planned: `ui/window-geometry.ts`.** The repairs this phase owns, and the
  place-restoration the review rounds added on top of them, took `ui/virtual-rows.tsx` to 403
  non-blank lines — over the very ceiling this lot exists to enforce. It splits on a SUBJECT rather
  than on a line count: what the grid draws (its lanes, its line height, where the container starts
  inside its scroller) is one question, measured rather than believed; the window's own maintenance
  is another. The behaviour did not change with the split — the hook holds the code that stood in
  `virtual-rows.tsx`, verbatim, and a reader diffed it to confirm — and it changed afterwards, when
  the ordering defect the split made visible was repaired inside it.
- **THE ENGINE'S TWO FILES WERE OPENED, and the plan said they would not be.** Under review, at
  rounds 5 and 6, for defects in the surface this lot owns and nowhere else. `engine/legacy.js`:
  the library's selection was a set of positions IN THE LISTING ON SCREEN read as indexes into the
  source, so a bulk delete taken under any order but the source's named and destroyed media the
  reader had not ticked — it is keyed by title now, dropped where the question is written, and the
  delete dialog counts the media each title names, because ONE title in this library names two media
  — « Doctor Who », 2005 and 2023, the only duplicate in 345 rows
  and the manifest said one file while two left. `engine/states.js`: the named selection state
  seeded three POSITIONS, which had to become the three titles with the set. Both are a wrong key
  replaced by the right one; neither adds a drawing, and the oracle reads no divergence. The
  operator may overrule it — a wrong deletion was judged not to be a thing to file for later, and
  D-L14-8's « only subtracted from » is the sentence it bends.
- **The reader's PLACE across a pitch change is this phase's, and it was not in the plan at all.**
  The window is re-measured when the row pitch moves; a reader's place has to survive that, and
  three review rounds were spent finding what « a place » is: the first VISIBLE line, not the first
  drawn one; an ITEM index, not a line, because the lanes change too; restored after the container
  is reset, not before the draw.
