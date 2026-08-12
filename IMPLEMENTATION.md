# Current feature: shell-mobile

**Branch:** `feat/shell-mobile` — every phase targets it. `main`, and therefore production, is
touched **once, at the end**, after everything has been validated together. Non-negotiable.

**Spec:** `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md`
**Design reference:** `frontend/maquette/refonte.html` — §15 of `docs/reference/product-intent.md`
**Plans:** one per phase, in `docs/superpowers/plans/2026-08-12-shell-mobile-phase-*.md`

---

## Where to start

Read, in this order:

1. `frontend/maquette/README.md` — the prototype's contract, the 47 named states, the rule set,
   and the traps already paid for. It is short and it saves days.
2. `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md` — §7 is the parity
   methodology and is the part that matters most.
3. `docs/superpowers/plans/2026-08-12-shell-mobile-phase-0-parity-tooling.md` — the first phase.

Then execute phase 0 task by task. Nothing else can start before it: every later phase leans on
the guards it builds.

**Serve the prototype locally** (never on 8710 or 8711, which the reverse proxy routes to
production and staging):

```bash
cd frontend/maquette && python3 -m http.server 8899
```

The prototype needs a wrapper supplying a viewport meta; the harness scripts build one. Without
it Chrome falls back to the legacy 980px layout viewport and every measurement is wrong.

**Run the harness** with the Python that carries Playwright:

```bash
cd frontend/maquette/harness
for s in audit audit2 states sweep scen dest scroll filtres actions deck souris \
         inter sel bugs ident pop suivis surfaces export; do
  python3 $s.py > /dev/null || echo "FAILED: $s"
done
```

Every script fails through its exit code, not through its output. A script that only prints
cannot fail, and a script that cannot fail is a report nobody is obliged to read.

---

## Phases

| Phase | Delivers                                                                    | Status      |
| ----- | --------------------------------------------------------------------------- | ----------- |
| 0     | Parity tooling: CSS extractor, drift guard, class-coverage guard, probe, CI | not started |
| 1     | Scope rename, four shared primitives, `PageHeader` off mobile               | not started |
| 2     | Arrivées + reception into Système; old routes demoted to redirects          | not started |
| 3     | Médiathèque, read-only, three lenses                                        | not started |
| 4     | Media sheet: visual header, single back control, YouTube trailer, seasons   | not started |
| 5     | Delete, dry-run enforced, three paths                                       | not started |
| 6     | Découvrir: three formats, TMDB account, background pool                     | not started |

**Next action:** execute phase 0.

---

## What the prototype already settles

These were argued, measured and recorded. Re-opening one costs a day; the reasons are in
`frontend/maquette/regions.json` → `$adversarialReview` (37 rules) and `$methodLessons` (15).

- **The prototype is the reference.** A divergence between the app and it is a defect in the app,
  unless the prototype was amended first with the reason written down.
- **CSS is extracted, never retyped.** A hand edit to the generated stylesheet is reverted by the
  drift guard.
- **Every gesture answers a pointer**, not only a finger — the interface is used from a desktop
  browser too, at a phone width.
- **Episode presence is read, never inferred.** A `number <= owned count` threshold assumes the
  hole is at the end of a season; it is false for 35 series in this library.
- **A trailer always opens YouTube**, never in-app playback, wherever one arrives from.
- **One back control**, in the flow, on every screen that has one.
- **One season rendering**, within a sheet and across sheets.
- **Identify is not follow.** Resolving a stuck folder associates a medium so the pipeline
  finishes; it never creates a follow.

## Three method lessons that cost the most

- **A screenshot fingerprint is not an oracle.** Two captures of the same unmodified file diverge
  on 8 to 15 of the 47 states. Use bounding rects plus a computed-style subset.
- **A rule that never bit proves nothing.** Every rule added is mutation-tested: break the
  behaviour on purpose, confirm the rule falls, restore.
- **An audit must announce how many rules it EXECUTED.** « 0 violations across 0 rules » reads
  the same when all is well and when nothing runs.

---

## Carried, not hidden

1. **Plex deletion.** `api/plex.py` only refreshes. Which route removes an entry on this server is
   a verification step of phase 5, not a claim.
2. **A real deletion cannot be validated before production.** Staging writes to the real disks and
   the real databases, and fabricating a medium for the proof is forbidden. Protocol: dry-run only
   on staging; the first real deletion happens after the production merge, on a medium the
   operator names, after a genuine `sqlite3 .backup` — a file copy of a WAL database is not a
   backup.
3. **The multi-user account system** is a later mission. The user menu draws its place — profile
   and preferences, disabled, saying why — so the shape is settled before the feature lands.
4. **`?tab=maintenant`.** The label became « En cours »; whether the URL param migrates with a
   legacy redirect or stays is an implementation detail of phase 6's sibling work. The deep link
   must keep working either way.
