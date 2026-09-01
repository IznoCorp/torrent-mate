# Phase 7 — B-247's surface half · behaviour

**Owns**: B-247 (surface half), B-295, D-L14-3, D-L14-4, D-L14-6. **Constitution**: §12 (a tap
lost to a re-render is a phone defect), §16 (nothing about the ladder moves). **Depends on
phases 5 and 6.**

## What changes

1. `ui/markup.ts` — `useMarkup(html: string): { __html: string }`, a `useMemo` on the string.
   Its header says WHY (React 19 assigns `innerHTML` on the prop's identity, string unchanged or
   not — the comparison React 18 made) and names the one place the trick lives. Zero domain words.
2. Every `dangerouslySetInnerHTML={{ __html: … }}` in `now-tab.tsx`, `follows-tab.tsx` and
   `incomplete-lens.tsx` becomes `dangerouslySetInnerHTML={useMarkup(…)}` — where a site is
   inside a `.map` or a closure (the « En cours » sections, the grouped follows), the section
   becomes a small component so the hook is called at the top level of a component, as the rules
   of hooks require. `discover-tab.tsx` has no such site (the engine fills its containers).
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
- `scripts/mutate.sh frontend/maquette/design/src/ui/markup.ts 't.replace("useMemo(", "((f) => f())(")'`
  (or the exact form that returns a fresh object) → (f) falls on the three acquisition states;
  restored.
- **R117 green** (identity across a scroll is untouched), **R94** green, `selection.py`,
  `library_load.py`, `library_sort.py`, `filters.py` green — a delete still removes its row
  (`__deleteLibraryItems` rewrites the pages, which moves the first page's identity).
- The oracle: zero divergence (nodes at rest are the same markup).
- `python3 scripts/check-frame-domain.py | tail -1` → `ui/ 0` unchanged.
- Two commits: the repair (`fix(maquette-l14): a page's nodes keep identity across a store write —
B-247's surface half, B-295`), then the rule (`test(maquette-l14): R100 (f) …`).
