# Bug register

Every defect the operator reports lands here **the moment it is reported**, before any work
starts. A bug leaves this file only through the `Fixed` column, and only with a rule that fails
when the defect comes back.

## Rules of this file

1. **Reported = written down.** No triage, no judgement first. An unwritten bug is a bug that
   comes back a third time.
2. **One bug is closed at a time**, and the operator confirms the fix before the next one starts.
3. **A fix is not a fix without a rule that bites, and the rule is RUN.** Mutation-tested: break
   the behaviour on purpose, confirm the rule falls and names the right defect, restore. A closing
   entry names the script, the mutation, and the run that passed — a command whose output nobody
   has seen is a claim.

   **When no instrument reaches the defect, building one is part of the work — never a reason to
   leave the entry open.** Dictated by the operator on 2026-08-28, and the count is why. Forty-one
   entries stood open that day and eight of them were closed in substance, held open by one
   sentence wearing the same shape: « not fixed here, it needs its own X ». That sentence satisfies
   the first half of this rule *perfectly* — a rule nobody wrote cannot fail its mutation — which is
   how the rule written to force proof became the rule that licensed deferral. It is written into
   B-036, B-041, B-055, B-057, B-058, B-061, B-100 and B-104, each time in good faith.

   **So every entry a wave takes is closed by an instrument that RAN**: the oracle, a harness hold,
   the accessibility tier, a guard arm, a test. The entry carries the command and its result.
   Where the instrument did not exist, the wave built it, and the instrument is the deliverable as
   much as the fix — B-139's own text says its defect « is measurable in twenty lines and nothing
   measures it », which is the whole of this rule in one line.

   **The one honest exception, and it is narrow.** Where no instrument can reach the defect, the
   entry names WHICH instrument cannot, WHY, and what was done instead. Two shapes have been met so
   far: prose in a document no guard greps (B-024 — a dead phase name cited as live), and a
   continuous-integration condition provable only by making the pipeline red on purpose (B-151).
   **An exception that is not named is indistinguishable from an instrument nobody built**, which
   is B-085's sentence with the reader replaced by a wave.

4. **The rule must cover the path the operator actually walks.** Several bugs below survived a
   green harness because the rule drove a named state instead of the real journey — a cold load,
   a real finger, a real browser menu.
5. **Repeats are counted.** `Reported` records every time the operator has had to say it again.
   A count above one is a failure of this register, not of memory.

## Status vocabulary

| Status       | Means                                                          |
| ------------ | -------------------------------------------------------------- |
| `open`       | Reproduced and diagnosed, not yet fixed.                       |
| `fixing`     | Being worked on right now. Exactly one bug may hold this.      |
| `to confirm` | Fixed, rule green, mutation proven — waiting for the operator. |
| `fixed #509` | Fixed on a branch, in the pull request named — not on `main` yet. |
| `closed`     | Operator confirmed on a real device.                           |

---

> **What is open is in the table below, and only there.** This banner used to carry a count of
> its own; it read « two » while three entries already said `open`, because a summary that is
> written once and never recounted stops being true on the next line added. The `Status` column
> is the answer. What belongs here is only what the column cannot say — WHY an entry is still
> open when its diagnosis looks finished:
>
> **B-030** is a defect of the maquette's embedded DATA (87 of 345 sheets carry no genre and no
> cast), not of the drawing, and the operator has excluded it from the batch closure. It was
> never `to confirm`.
>
> **B-024 no longer belongs here**, and this banner said it did for the length of the wave that
> closed it: its status column reads `fixed #516` while the paragraph above still explained why
> it stayed open. A banner is exactly the summary the first paragraph warns about — written once,
> never recounted — and it went stale about the one entry the wave named as an exception.

## Open

| ID    | Defect                                                | Reported    | Status       |
| ----- | ----------------------------------------------------- | ----------- | ------------ |
| B-019 | Many media sheets have lost their visual              | 1×          | `closed`     |
| B-020 | Actor portraits on media sheets are broken            | 1×          | `closed`     |
| B-021 | Signing out leaves the bottom panel on top            | 1×          | `closed`     |
| B-022 | « Voir mes suivis » in the add search is inert        | 1×          | `closed`     |
| B-023 | Médiathèque « Incomplets »: every visual broken       | 1×          | `closed`     |
| B-013 | The drawer's entries lead nowhere                     | 2×          | `closed`     |
| B-014 | The drawer's current entry is unreadable              | 1×          | `closed`     |
| B-015 | Back reopens the drawer that was just closed          | 1×          | `closed`     |
| B-016 | Swiping a row right, then left, makes it jump         | 1×          | `closed`     |
| B-017 | Closing a panel sends the list back to its top        | by mutation | `closed`     |
| B-018 | On a desktop, dragging a row opens the panel          | 1×          | `closed`     |
| B-024 | `data-go` settles ONE history entry, layers pile      | by review   | `fixed #516`       |
| B-025 | The screen half of the `data-go` fix has no Back rule | by review   | `closed`     |
| B-026 | A silent `catch {}` can let URL and UI disagree       | by review   | `closed`     |
| B-027 | `resync.py` trusts `t:` first-match + naive braces    | by review   | `closed`     |
| B-028 | `resync.py` says « 0 correction » for unknown titles  | by review   | `closed`     |
| B-029 | Counter rule misses suffix drift (« 1 » in « 11 »)    | by review   | `closed`     |
| B-030 | 87 library sheets carry no genre and no cast          | by rule     | `open`       |
| B-031 | « Réessayer » on every error surface is inert          | by review   | `to confirm` |
| B-032 | The harness's data-scenario dial selects the wrong one | by review   | `to confirm` |
| B-033 | `test_locks_tmp_orphans` is flaky under xdist          | by rule     | `open`       |
| B-034 | `TestQuickMode` reads a foreign `os.scandir` caller    | by gate     | `open`       |
| B-035 | `test_continues_on_per_file_error` writes no backup    | by gate     | `open`       |
| B-036 | Two state ids are still French: `panne`, `groupe`      | by review   | `fixed #516`       |
| B-037 | `arrivals.py` reads a French global nothing defines      | by review   | `open`       |
| B-038 | `arrivals.py` reads `empty` and asserts nothing on it    | by mutation | `open`       |
| B-039 | `actions.py` prints `.freshtag` presence, asserts nothing | by mutation | `open`       |
| B-040 | Names in files no arm reads: `sweep.py`, a region id, `oracle.py` | by review   | `fixed #516`       |
| B-041 | `check-frontend-boundaries.py` has no committed test                | by audit    | `fixed #516`       |
| B-042 | An orphan `http.server` holds port 8900 on the operator's machine   | by review   | `fixed #516`       |
| B-043 | A deep media address lands the 404 page underneath it               | by review   | `fixed #484` |
| B-044 | A 404's address recomposes to `/` after a cold load                 | by review   | `fixed #484` |
| B-045 | `?panel=follows` without its colon is accepted, and fabricates media | by review   | `fixed #484` |
| B-046 | The fallback port moved onto `switchover.py`'s, whose bind error is swallowed | by review | `fixed #484` |
| B-047 | The navigation-failure flag is raised by no guard and read by no rule | by review   | `fixed #484` |
| B-048 | The ninth boundary arm stays green with `addresses.ts` deleted      | by review   | `fixed #484` |
| B-049 | A rule reads the operator's live `acquire.db` and turns red on every cron | by review | `fixed #516` |
| B-050 | `check-frontend-boundaries.py` is at 921 lines, 79 from the hard ceiling | by review | `fixed #500` |
| B-051 | `toFollows()` carries the page in its query, invisible to the boundaries arm | by review | `fixed #516` |
| B-052 | A synthesised follow panel labels a film « Série »                  | by review   | `open`       |
| B-053 | A panel's layer entry is taken by a tab tap on the same layer (revisit) | by review | `open`     |
| B-054 | `data-go="acq"` no longer forces the « now » tab (revisit)           | by review   | `open`       |
| B-055 | The a11y floor measures only the dark theme — light carries 154 findings | by review | `fixed #516` |
| B-056 | A `@keyframes` name is French (`splashremplit`), invisible to no-french  | by review | `open` |
| B-057 | `audit2.py`'s R12 silently measures four of five contexts, not five | by review   | `fixed #516`       |
| B-058 | commit-msg's AI-attribution match is unanchored, flags quoting prose | by mutation | `fixed #516`       |
| B-059 | `check-css-tokens.py` crossed the 1 000-line hard ceiling during L07        | by audit    | `fixed #494` |
| B-060 | The rename tool could not rename a CSS custom property, and reported it as success | by mutation | `fixed #494` |
| B-061 | The oracle cannot see a pseudo-element, so a class that generates nothing reads green | by rule | `open` |
| B-062 | Three markup readers were blind to `cva()` factories, which emit a class name with no `class=` | by gate | `fixed #494` |
| B-063 | The wave's per-phase gate tier runs none of the repository's own guards | by gate | `fixed #500` |
| B-064 | R72's mutation recipe names an environment variable no code reads | by review | `fixed #500` |
| B-065 | A duplicated `design/frontend/maquette/design/src/` tree is tracked, dead and drifting | by review | `fixed #500` |
| B-066 | Two off-scale values sit under a named exemption rather than on the scale | by gate | `fixed #500` |
| B-067 | A typed variant shadowed by the unlayered residue is inert, and nothing says so | by review | `fixed #500` |
| B-068 | The wave's documentation drifted in forty small places, and one figure family is wrong | by review | `open` |
| B-069 | `legacy.css`'s licence to exist names a decision only an about-to-be-archived doc defines | by review | `fixed #500` |
| B-070 | `rename-identifiers.py` passed the 800-line soft ceiling | by gate | `fixed #500` |
| B-071 | The design-notes toggle survives the overlay it toggles | by review | `open` |
| B-072 | `build-surface-manifest.py` crashes: its own command no longer runs | by review | `fixed #500` |
| B-073 | The size arm checks WHICH files are grandfathered, never the lot each names | by audit | `fixed #500` |
| B-074 | The abbreviation rule's figures were measured against a list the document did not contain | by audit | `fixed #500` |
| B-075 | Five guards were written green over the very defect they were written for | by mutation | `fixed #500` |
| B-076 | The hero's entrance animates for a reader who asked for no motion | by rule | `fixed #500` |
| B-077 | A test of the browser-free half of a rule could not be collected without a browser | by CI | `fixed #500` |
| B-078 | The state row outlived its subject, ajourned on a rule that does not exist | by audit | `fixed #501` |
| B-079 | The design host cannot say which commit it serves, and production's host can | by audit | `fixed #505` |
| B-080 | The drawer shows a hard-coded version and build, and calls itself up to date | by operator | `fixed #505` |
| B-081 | Design notes can no longer be hidden, and the oracle measures without them | by operator | `fixed #505` |
| B-082 | `hidden` hides nothing on five elements, so an invisible button is still tappable | by operator | `fixed #505` |
| B-083 | L08's design and plan were never archived, and every lot before it was | by audit | `fixed #505` |
| B-084 | A wave that found twenty defects wrote none of them in this register | by audit | `fixed #505` |
| B-085 | Guards green over what they do not read: 17 in three consecutive waves, counted by nobody | by audit | `fixed #505` |
| B-086 | A season tuple was declared in the wrong order, and a seed claimed 175 episodes of 117 | by review | `fixed #503` |
| B-087 | A media sheet substituted one family's synopsis for another's, on 213 of 259 titles | by review | `fixed #503` |
| B-088 | Twenty provider identities name two sheet keys, and the first returned nine empty season lists | by review | `fixed #503` |
| B-089 | `serie` is a broadcast status, and a rename read it as a series name | by review | `fixed #503` |
| B-090 | `Setting.value` carries the engine's rendered French, and one of them is lossy | by review | `fixed #509` |
| B-091 | `grabForFollow` answered a hash field with a release name | by review | `fixed #503` |
| B-092 | Four mutating routes changed nothing the next read could see | by review | `fixed #503` |
| B-093 | `isPureLiteral` walked an initializer's children and never the initializer | by review | `fixed #503` |
| B-094 | The register held its families' NAMES and not their classes | by review | `fixed #503` |
| B-095 | Two families shipped unprojected while the builder reported success and lossless | by review | `fixed #503` |
| B-096 | The contract was wrong about the data in five places, and the seeds proved it | by review | `fixed #503` |
| B-097 | Twenty seed renames never reached the index, and only a case-sensitive runner saw it | by CI | `fixed #503` |
| B-098 | The build plugin raced its own output and failed three jobs on a fresh checkout | by CI | `fixed #503` |
| B-099 | A test pass writes 13 GB of real zeroes into `/tmp` and pytest keeps three of them | by operator | `fixed #505` |
| B-100 | Invariant 10 is written and unarmed: no arm counts the frame's domain words | by audit | `fixed #516` |
| B-101 | The steward's brief predicted an oracle movement that could not happen | by audit | `open` |
| B-102 | Seven register rows are duplicated, once `fixed` and once `open` | by audit | `fixed #516` |
| B-103 | Two invariants are numbered 10, and a brief pointed at « invariant 10 » | by audit | `fixed #516` |
| B-104 | The generated contract types live under `mocks/`, and they are not a mock | by gate | `fixed #516` |
| B-105 | R89's waterfall hold was green over the exact defect it names | by mutation | `fixed #509` |
| B-106 | The server-state arm read only the component tree, so its ceiling was pre-satisfied | by mutation | `fixed #509` |
| B-107 | `git checkout --` on an untracked file is a no-op, and a mutation stayed in the tree | by review | `fixed #509` |
| B-108 | The oracle tore React's own nodes out before measuring, and recorded four states as blank | by oracle | `fixed #509` |
| B-109 | A retry that re-asks nothing was written, and the invariant-4 arm refused it | by gate | `fixed #509` |
| B-110 | The fixture register had no word for a family L09 deliberately deletes | by gate | `fixed #509` |
| B-111 | An edit replaced a span it had not read, and took six published members with it | by rule | `fixed #509` |
| B-112 | The library's sentinel watched the wrong port, masked by a 620 ms delay | by oracle | `fixed #509` |
| B-113 | A named state was reachable from a known store and an unknown cache | by oracle | `fixed #509` |
| B-114 | The listing conflated what the library claims with what the source holds | by rule | `fixed #509` |
| B-115 | A redraw bridge deduplicated on a clock the oracle is allowed to stop | by oracle | `fixed #509` |
| B-116 | The inverse projection turned a string into an object of its characters | by rule | `fixed #509` |
| B-117 | The queue read served the dense world under the real scenario | by review | `fixed #509` |
| B-118 | The seed builder deleted twenty-one seeds the mock layer serves | by review | `fixed #509` |
| B-119 | A copy of the design root no longer builds, and the rule read a broken host | by rule | `fixed #509` |
| B-120 | A journey rule read the verb of a panel the previous half had left open | by rule | `fixed #509` |
| B-121 | A gate compared a committed seed to a counter the daemon increments | by gate | `fixed #509` |
| B-122 | A guard named a path by cutting it on the operator's own clone directory | by CI | `fixed #509` |
| B-123 | The settings drew a cron expression raw — the kind of the field lived nowhere | by adversarial review | `fixed #509` |
| B-124 | The invariant-4 arm read one spelling of a store write out of three | by adversarial review | `fixed #509` |
| B-125 | The invariant-5 arm did not know `fetchNextPage`, nor count a layout effect | by adversarial review | `fixed #509` |
| B-126 | The unit-test floors sat a third under the corpus they guard | by adversarial review | `fixed #509` |
| B-127 | A search matching nothing said « 0 résultat affiché sur 257 trouvés » | by adversarial review | `fixed #509` |
| B-128 | The release picker was title-blind, and its cache key with it | by adversarial review | `fixed #509` |
| B-129 | The library count line printed a literal beside the number it was served | by adversarial review | `fixed #509` |
| B-130 | Discarding a staged medium walked one list out of three | by adversarial review | `fixed #509` |
| B-131 | A listing parameter, a served resource and a hook, none of them read | by adversarial review | `fixed #509` |
| B-132 | The inverse projection threw, or converted, on shapes nobody declared | by adversarial review | `fixed #509` |
| B-133 | Three new rules held on something other than what they read | by adversarial review | `fixed #509` |
| B-134 | No arm read what a HANDLER answers — only what a seed holds | by adversarial review | `fixed #509` |
| B-135 | Three named states measured the panel left open by the state before them | by adversarial review | `fixed #509` |
| B-136 | B-090's headline figure counted quotes, and it had reached the contract | by adversarial review | `fixed #509` |
| B-137 | Four ACCEPTANCE criteria could not run, or expected the wrong answer | by adversarial review | `fixed #509` |
| B-138 | The profile panel's avatar is unconstrained, inside a region whose probe reads only the container | by operator | `fixed #516` |
| B-139 | Three typed variants were written and never wired; one leaves a bare button unreadable | by operator | `fixed #516` |
| B-140 | Back returns to the top of a page: the scroll memory only knows overlay screens | by operator | `fixed #512` |
| B-141 | Ten elements carry no class at all, in a prototype that imports no preflight | by audit | `fixed #516` |
| B-142 | Nothing measures the interface against the constitution: three DOIT clauses have no surface | by audit | `fixed #528` |
| B-143 | §17 (accounts, rights, Plex SSO) has no surface, no contract operation and no lot | by audit | `open` |
| B-144 | §18 (ratio per tracker) needs three operations the backend already answers and nothing calls | by audit | `open` |
| B-145 | §19 (cross-seed) has no route in either contract, and its events reach no stream | by audit | `open` |
| B-146 | D11 is decided and nothing styles a scrollbar yet; the change may move the oracle | by audit | `fixed #516` |
| B-147 | Nine steward findings were stacked on five unmerged branches and collided with a wave | by audit | `fixed #511` |
| B-148 | Lot status lives in two files, and § 0 reads the one a wave forgets | by audit | `fixed #511` |
| B-149 | A declared departure from the lot's « Done when » lives only in a session report | by audit | `fixed #511` |
| B-150 | A size promise expired unnoticed because the guard read the status B-148 froze | by audit | `fixed #511` |
| B-151 | `coverage-merge` reports « Artifact not found » whenever an earlier job fails | by audit | `fixed #516` |
| B-152 | `IMPLEMENTATION.md` still named L09 as the next lot two commits after L09 merged | by design | `fixed #512` |
| B-153 | The demand register is computed from OpenAPI paths, and a WebSocket has none | by design | `open` |
| B-154 | `staleTime: Infinity` with no focus or reconnect refetch: a missed invalidation never heals | by design | `open` |
| B-155 | The header claimed « Temps réel connecté » as a literal, with no connection anywhere | by design | `fixed #512` |
| B-156 | The harness's condition lever left the retry control dead in the state that offers it | by rule | `fixed #512` |
| B-157 | R92 held that a notice named its reason by reading the TIMESTAMP beside it | by mutation | `fixed #512` |
| B-158 | R94 walked a journey that cannot lose a scroll position, and passed over B-140 | by mutation | `fixed #512` |
| B-159 | Two instruments split a file on a WORD whose first use is the type import | by gate | `fixed #512` |
| B-160 | The relay said « connected » over a dead link, by three independent routes | by adversarial review | `fixed #512` |
| B-161 | `currentSince` was the age of the CONNECTION, and the notice called it the age of the data | by adversarial review | `fixed #512` |
| B-162 | A refusal was inescapable: signing back in left the relay dead and the notice pointing at it | by adversarial review | `fixed #512` |
| B-163 | The message listener had no identity guard, so a stale socket could report health | by adversarial review | `fixed #512` |
| B-164 | The cursor took every id it was handed and could walk backwards | by adversarial review | `fixed #512` |
| B-165 | `DownloadStarted`/`Progressed` were refused as per-tick; they fire once and thrice | by adversarial review | `fixed #512` |
| B-166 | `FilmAcquired` deletes a follow and closes a wanted row, and refreshed neither list | by adversarial review | `fixed #512` |
| B-167 | Three transition events existed for a demand that asked the backend to build them | by adversarial review | `fixed #512` |
| B-168 | The guard's event corpus was six files written by hand, and nine events lived outside | by adversarial review | `fixed #512` |
| B-169 | `StepItemStatus` is a StrEnum, and a rule named it as an event that can never arrive | by adversarial review | `fixed #512` |
| B-170 | R91 computed one direction while its docstring claimed two | by adversarial review | `fixed #512` |
| B-171 | R92 read a word the CSS had removed, and never read the colour that replaced it | by adversarial review | `fixed #512` |
| B-172 | R93 was blind to cache REMOVAL, the purest form of the reload it refuses | by adversarial review | `fixed #512` |
| B-173 | R89's four stream holds passed with no socket open at all | by adversarial review | `fixed #512` |
| B-174 | R94's central hold passed while a different page was on screen | by adversarial review | `fixed #512` |
| B-175 | `invalidateQueries({queryKey: []})` was counted as a HEALTHY named invalidation | by adversarial review | `fixed #512` |
| B-176 | `unmatched` grew without bound, fed by the highest-frequency events by design | by adversarial review | `fixed #512` |
| B-177 | A mutation's `git checkout` reverted an uncommitted repair, and a commit described it anyway | by adversarial review | `fixed #512` |
| B-178 | B-140 was closed with the second defect its own entry names still in the code | by adversarial review | `fixed #512` |
| B-179 | Two correct repairs, together wrong: closing a drawer put an older offset back | by gate | `fixed #512` |
| B-180 | The repair for the false « connected » reintroduced it: a teardown flag nothing consumed | by adversarial review | `fixed #512` |
| B-181 | `reset()` could drive the settle counters NEGATIVE, and then `quiet()` never resolved again | by adversarial review | `fixed #512` |
| B-182 | There was no `open` listener, so the opening deadline was a time-to-first-frame deadline | by adversarial review | `fixed #512` |
| B-183 | The cursor « moves only if delivered » was jumped over by the next event that succeeded | by adversarial review | `fixed #512` |
| B-184 | The way out of a refusal could be spent before the refusal arrived | by adversarial review | `fixed #512` |
| B-185 | `ProviderCallCompleted` is a throttled health sample, exempted as per-item progress | by adversarial review | `fixed #512` |
| B-186 | `ItemProgressed` had no predicate and fired ~540 times a run at two lists | by adversarial review | `fixed #512` |
| B-187 | `CACHE_WIDE` was matched line by line, so a wrapped whole-cache invalidation passed | by adversarial review | `fixed #512` |
| B-188 | `SELF_RESCHEDULING` could not cross a semicolon, so it missed every realistic poll | by adversarial review | `fixed #512` |
| B-189 | The exemptions reader kept the adjacency defect the rules reader was repaired for | by adversarial review | `fixed #512` |
| B-190 | A comment claimed `fanout.py` had been repaired for that defect; it had not | by adversarial review | `fixed #512` |
| B-191 | R95's recovery hold was a tautology, and its own printed proof contradicted it | by adversarial review | `fixed #512` |
| B-192 | R95's « superseded socket » hold could not produce a superseded socket | by adversarial review | `fixed #512` |
| B-193 | R92's colour hold was a difference test, and a SWAP of two tokens passed it | by adversarial review | `fixed #512` |
| B-194 | R94's layer hold never verified that a layer opened | by adversarial review | `fixed #512` |
| B-195 | R91's sibling was seeded under the key, where it could never be an over-refresh | by adversarial review | `fixed #512` |
| B-196 | R95 certified the shipped limits from a literal, not from the running program | by adversarial review | `fixed #512` |
| B-197 | The hold-count baseline was stale for three rules, so the gate reported false regressions | by adversarial review | `fixed #512` |
| B-198 | `resetQueries`/`removeQueries`/`refetchQueries` were refused even when given a key | by adversarial review | `fixed #512` |
| B-199 | The event corpus was a regex re-implementation of a registry the bus already keeps | by adversarial review | `fixed #512` |
| B-200 | The two headline relay repairs were never in the tree, under a commit describing them | by adversarial review | `fixed #513` |
| B-201 | The unresolved-key count was made and thrown away two lines later | by adversarial review | `fixed #513` |
| B-202 | The cursor freeze was permanent: no reconnect could ever thaw it | by adversarial review | `fixed #513` |
| B-203 | R91 merged every rule's sample, so its verdict depended on source order | by adversarial review | `fixed #513` |
| B-204 | R92 resolved the token through the cascade that paints it, so a value swap passed | by adversarial review | `fixed #513` |
| B-205 | Nothing read whether the connection dot is on screen | by adversarial review | `fixed #513` |
| B-206 | `type:` narrowing was refused beside a key, telling its author to delete it | by adversarial review | `fixed #513` |
| B-207 | `.clear()` was anchored on nothing: vacuous now, a false diagnosis later | by adversarial review | `fixed #513` |
| B-208 | The registry-versus-regex disagreement was printed and could fail nothing | by adversarial review | `fixed #513` |
| B-209 | `violations` was used before assignment a second time, behind an empty loop | by adversarial review | `fixed #513` |
| B-210 | The counter floor traded a loud deadlock for a silent under-count | by adversarial review | `fixed #513` |
| B-211 | A nested object before an empty key hid a whole-cache invalidation | by adversarial review | `fixed #513` |
| B-212 | An event every predicate refused was counted as neither claimed nor unclaimed | by adversarial review | `fixed #513` |
| B-213 | The poll reader adopted the wrong block for 545 bindings out of 925 | by adversarial review | `fixed #513` |
| B-214 | The guard's import loaded 41 environment variables to count 48 class names | by adversarial review | `fixed #513` |
| B-215 | `installRelayRecovery` declared its position as a constraint and no arm read it | by adversarial review | `fixed #513` |
| B-216 | The mutation tool announced « no hold fell » under the falls it had just printed | by adversarial review | `fixed #513` |
| B-217 | The cursor thaw was measured by nothing, and the tool's first use found it | by adversarial review | `fixed #513` |
| B-218 | The « Before it » row stopped at L07 and still named a merged PR as « this pull request » | by design | `fixed #514` |
| B-219 | A wave's brief existed only in a session scratch directory, and its agent could not read it | by agent | `fixed #515` |
| B-220 | The drawer and the bottom tab bar — L15's since 2026-08-29 | by audit | `open` |
| B-221 | A wave merged leaving its own status as the literal placeholder `fixed #NNN` | by guard | `fixed #516` |
| B-222 | The add screen is the only one of five measured by no oracle region at all | by audit | `fixed #516` |
| B-223 | Three more typed variants were orphaned, and the arm for B-139 found them | by guard | `fixed #516` |
| B-224 | The header's avatar rendered 20x30 in a 32x32 button, every class on it correct | by audit | `fixed #516` |
| B-225 | A guard froze its own corpus size in a comment, and the figure drifted three times | by audit | `fixed #516` |
| B-226 | The cross-check B-208 built never ran in CI: the import branch printed and passed | by audit | `fixed #516` |
| B-227 | The post-merge gesture was missed at the close of L09, L10 and L10-bis, and § 5’s guard for it stayed a sentence | by audit | `fixed #518` |
| B-228 | The brief's inventory command reads twelve of thirteen writes | by survey | `open` |
| B-229 | The confirmation dialog is not on the back ladder | by survey | `fixed #528` |
| B-230 | The engine re-adds a viewport refusal to any host without a viewport meta | by survey | `fixed #528` |
| B-231 | The tab bar is rebuilt from scratch on every render | by survey | `fixed #528` |
| B-232 | Two dead layers: the page-render branch and `#screen` | by survey | `open` |
| B-233 | `theme-color` is a constant while the document paints light | by survey | `fixed #528` |
| B-234 | The viewport meta declares no `interactive-widget` | by survey | `fixed #540` |
| B-235 | No desktop navigation exists beyond the drawer | by survey | `open` |
| B-236 | Every bottom-panel producer is the engine's — L19's since 2026-08-29 | by survey | `open` |
| B-237 | The confirmation dialog paints under the tab bar | by review | `fixed #528` |
| B-238 | A version-less « In flight » row is held by nothing | by review | `fixed #527` |
| B-239 | `CLAUDE.md` announced 24 frame properties where the model it points at holds 30 | by audit | `fixed #524` |
| B-240 | `CLAUDE.md` announced 25 engine French words where the file it points at holds 24 | by audit | `fixed #524` |
| B-241 | `IMPLEMENTATION.md`'s « Next » row said « once L10-ter merges » and « L14 stays last » after both had changed | by audit | `fixed #527` |
| B-242 | `MODEL.md` P14 says 78 named states where 87 are driven | by audit | `fixed #527` |
| B-243 | Three small drifts in the directives: nineteen guards for twenty, an archived path cited live, « twenty times » for twenty-four | by audit | `fixed #527` |
| B-244 | A contracts-tier guard whose subject only the `docs` filter names runs in no job | by L15 | `fixed #528` |
| B-245 | The pre-paint appearance script compares against the French spellings the engine stopped writing | by L15 | `fixed #528` |
| B-246 | The « In flight » row's version arm is defeated by markdown emphasis, in silence | by L15 | `fixed #528` |
| B-247 | A store bump replaces a feature page's nodes, so a write between press and click destroys the click | by L15 | `open` |
| B-248 | The bottom sheet rises behind the tab bar; the operator wants it to cover the bar | 1× | `fixed #528` |
| B-249 | The screen flashes when a sheet action closes the sheet AND opens a page | 1× | `open` |
| B-250 | `check-live-relay`'s stale-figure arm cannot tell a register citation from a frozen count | by L15 | `fixed #528` |
| B-251 | A file under `docs/` that no commit force-added is invisible to `git add -A`, to `git status` and to every gate | 1× | `fixed #532` |
| B-252 | The oracle reads a region's node and never its children; two L15 surfaces are held by no rule | by audit | `fixed #540` |
| B-253 | B-247 was reassigned to L14 and L19 by the wave that left it, and the plan named it in neither | by audit | `fixed #532` |
| B-254 | Two figures written by hand: the Makefile's « 83 states x 33 regions » and CLAUDE.md's guard count | by audit | `fixed #532` |
| B-255 | `check-frontend-boundaries.py` is back at 952 lines, 48 from the hard ceiling it was cut away from | by audit | `open` |
| B-256 | The harness's served copy has no lock and no build stamp; a fresh copy arriving mid-run is a false reading either way | by audit | `fixed #534` |
| B-257 | Push notifications are declined for L11 and their consumer is §18's ratio alert, which is L16 | by L11 | `fixed #534` |
| B-258 | `Makefile`'s contract tier announced « 9 rules » where `run.sh` held 12 | by L11 | `fixed #534` |
| B-259 | The design host answers **401 for `/` itself**, so a worker installing from the gate can require nothing | by L11 | `fixed #534` |
| B-260 | A harness rule named after a STANDARD LIBRARY module shadows it for everything downstream | by L11 | `fixed #534` |
| B-261 | The cached shell outlived the session that filled it — the prototype readable offline after sign-out | by review | `fixed #534` |
| B-262 | The update discipline reloaded without ever swapping the worker, and then never swapped again | by review | `fixed #534` |
| B-263 | A refused replay jammed the queue forever, over an optimistic write the server had rejected | by review | `fixed #534` |
| B-264 | `caches.open` CREATES, so a controlling worker re-made the cache a sign-out had just deleted | by L11 | `fixed #534` |
| B-265 | The queue's drop-decision treated **401 as final**, destroying every queued mutation an expired session met | by review | `fixed #534` |
| B-266 | A notice button's name, words and action were three ladders in different orders, so it said one thing and did another | by review | `fixed #534` |
| B-267 | The real backend answers `{detail}`, which the queue's failure shape does not match — every refusal would be QUEUED at switchover | by review | `open` |
| B-268 | R104 lives in the file it measures, and has been defeated twice by exactly that | by audit | `open` |
| B-269 | Five corpus floors in `served_copy.py` are calibrated by hand, one figure per corpus | by audit | `open` |
| B-270 | Two harness journals are labelled « R80 » — `attrs.py`'s has no number of its own | by audit | `open` |
| B-271 | `MODEL.md` cited `index.html:241` for `#ptr`; that line is the skip link's comment and the node is at `:255` | by L12 | `fixed #540` |
| B-272 | The compositor guard's floors carried slack while its own note claimed they had none — 3 `touch-action` sites were deletable under a green guard | by L12 | `fixed #540` |
| B-273 | `scripts/mutate.sh` cannot judge a GUARD, and says « no hold fell » either way — and it exits SILENTLY when a mutation breaks the build | by L12 | `open` |
| B-274 | `page_host.py`'s state-alias arm read DOCSTRINGS as code — English prose ending « … state. » before an assignment matched it | by L12 | `fixed #540` |
| B-275 | Back from a media screen opened via « Voir la fiche » does NOT reopen the panel — §16's mirror cannot play | by L12 bench | `open` |
| B-276 | A delay set by hand in an INSTRUMENT outlives the drawn duration it was set against — twice in one rule | by L12 | `open` |
| B-277 | `exits.py`'s frame-count CONTROL flakes under the suite's parallel load — 2 falls in 3 runs, green alone | by L12 | `open` |
| B-278 | The drawer's dismiss acknowledges itself TWICE — two marks, same millisecond, both with no previous value; unexplained | by L12 review | `open` |
| B-279 | Twelve contracts-tier guards run in NO CI job when a pull request edits only the guard — the filter names their subjects, never their own file | by L12 review | `fixed #540` |
| B-280 | Transition A-extended had no subject: the engine closed the panel 260 ms before the capture, so `old(leaving-panel)` never existed | by L12 review | `fixed #540` |
| B-281 | The media body's arrival had TWO owners — `@starting-style` applies to the whole screen, which is inserted inside the transition's callback | by L12 review | `fixed #540` |
| B-282 | The fanart's entry faded the element that CARRIES the placeholder, so the muted block and the melt blinked with it | by L12 review | `fixed #540` |
| B-283 | During priming, the media screen prints its UNKNOWN parts as answers — « aucun synopsis », « aucune distribution » — about data in flight (§13) | by L12 review | `open` |
| B-284 | A pull cancelled by a mouse or a stylus was FORGOTTEN rather than released — the indicator hung open, armed | by L12 review | `fixed #540` |
| B-285 | `go()` discarded the router's promise, so the NEW snapshot is captured before the route has committed | by L12 review | `fixed #540` |
| B-286 | A hero whose picture changes UNDER it — media to media — was never followed again, and the new fanart snapped in | by L12 review | `fixed #540` |
| B-287 | 266 maquette/harness comments name a date, a lot or a phase — the rule against it has no arm, so nothing counts them | by L12 review | `open` |
| B-288 | The media screen's priming matches a title by PREFIX, so a medium whose title prefixes another opens with the other one's poster and year | by L12 review | `open` |
| B-289 | `check-frame-domain`'s comment scanner opens a phantom string on a REGEX LITERAL holding a quote, and counts every comment after it as code | by L12 | `fixed #540` |
| B-290 | A layer closed inside a navigation's commit KEEPS its history entry, so Back crosses two entries where its siblings cross one | by L12 review | `open` |

**B-278 — the drawer's dismiss acknowledges itself twice, and I could not explain it.**
One leftward swipe on the drawer produces TWO `data-feedback` marks on `#drawer`, at the same
millisecond, **both reporting no previous value**. The sheet's dismiss, driven the same way in the
same run, produces exactly one.

**What is ruled out, each by measurement rather than by reasoning:**

- **A stale observer in the probe.** The probe installed its `MutationObserver` twice without
  disconnecting the first; both pushed into one array, which would double every record. Disconnecting
  it changed nothing.
- **`React.StrictMode` double-invoking the install.** `installDrawerDismissGesture` returned `void`
  and its `useLayoutEffect` had no cleanup, so two independent gesture closures were plausible. A
  disposer was added — the effect now aborts its listeners — and the double mark **survived it**.
- **Two elements.** There is exactly one `#drawer` node.
- **One element marked twice in a task.** That would give the second record `oldValue: "commit"`.
  Both read `null`.

**What it is NOT: a visible defect.** The drawer closes once, correctly, and two marks of the same
kind inside 200 ms restart one timer — the acknowledgement simply lasts marginally longer. Nothing
the operator validated is affected.

**Why it is filed anyway.** « One `feedback()` call site every gesture passes through » is D9's whole
reason for the seam, and a gesture that appears to pass through it twice is either a second call
nobody can name or a mark nobody can account for. Both matter the day haptics make the seam fire
something. **The remaining candidate I did not test is a node REPLACED between the two marks** — a
re-render giving a fresh `#drawer` that is also marked — which would explain both `null` oldValues
and the single node count.

**B-289 — the frame-domain guard's comment scanner opens a phantom string on a regex literal.**
It scans rather than substitutes, deliberately — a `//` inside a string is not a comment — and the
quote branch runs BEFORE the comment branch. So a regex literal holding a quote opens a string the
scanner never closes: `app/artwork-arrival.ts`'s own `/url\(["']?(.+?)["']?\)/` opened one and the
scanner stayed inside it for thirty lines, emitting every comment it passed as code. Two `media` in
a sentence about the media screen were counted as domain words in the frame, and the guard went RED
over prose — the invariant it holds is about identifiers.

**A false red, and this register counts it**: the criterion above admits both signs, because a
reader who trusts a printed verdict is misled either way. This one cost an hour and nearly a
ceiling raise, which is the expensive half — the ceiling would then have blessed two words that
were never there.

**The fix is the language's own rule** rather than a regex-literal parser: a `'` or `"` string
cannot contain a raw newline, so reaching one means the quote was never an opener. Only a backtick
spans lines.

<sub>`python3 scripts/check-frame-domain.py` → `app/ 129` (131 before, over 9 060 identifier words
against 9 192 — the difference is the prose it was reading)</sub>

**B-290 — a layer closed inside a navigation's commit keeps its history entry.**
« Voir la fiche » closes the panel inside `go()`'s commit with `close(true)`, which does not unwind,
and pushes the media screen on top. Back from that screen lands on the LIST with the panel shut —
measured — because the ladder's handler steps over the standing layer entry. So the reader crosses
TWO entries for one gesture, where every sibling action (`data-releases`, `data-profile`,
`data-take`) reaches the same place by popping the layer's entry first and pushing 260 ms later.

**The outcome matches; the mechanism does not**, and a ladder with two shapes for one gesture is a
ladder nobody can reason about. The arbitration is not this lot's: whether a layer closed inside a
commit should keep its entry decides §16's « one entry per arrival » for every future surface, and
the handler that would implement either answer is **L13's**.

**Done when** the arbitration is written, the two shapes are one, and a rule COUNTS the entries
crossed on the way back — the five ladder rules count entries going forward and none counts pops.

<sub>drive « Voir la fiche » from an open panel, then `page.go_back()`, and read
`history.state.__TSR_index` before and after: 3 → 1</sub>

**B-287 — the rule that maquette comments carry no date, lot or phase has no arm.**
`CLAUDE.md` § Language: « Maquette/harness comments carry no reference to a session, a phase or a
dated decision — they must still read years from now, out of context. » Measured 2026-09-01 over
`frontend/maquette`'s `.py`, `.ts`, `.tsx` and `.css` comments alone (the engine's fixture DATES are
data, not prose, and are excluded): **266 occurrences across 85 files**, the largest being
`styles/legacy.css` at 64 and `contract/types.d.ts` at 26. This wave added roughly thirty-five of
them and repaired the ones an adversarial reader named.

**Why it is filed rather than fixed.** The debt is eight waves deep and the corpus is not this lot's;
a partial pass leaves the corpus inconsistent without achieving the rule. The shape of the arm is
already in this repository, twice: a per-file baseline that refuses the count going UP, exactly like
`scripts/french-exemption-baseline.json` and `scripts/code-abbreviations-baseline.json`. That freezes
the debt on the day it is armed and lets it drain wave by wave.

**Owner: the instruments' debts block of `frontend-architecture.md` § 5** — it is a repository guard,
belonging to no lot, and the rule there decides it.

<sub>comment-only scan over `frontend/maquette/**/*.{py,ts,tsx,css}` for `20\d\d-\d\d-\d\d`,
`\bL\d\d\b`, `\bphase \d` → 266 in 85 files</sub>

**B-288 — the media screen's priming matches a title by prefix.**
`useMediaSheet` primes from `reference.sheetFor(title)`; the engine's lookup falls back to a
normalised key and then to a PREFIX match (`startsWith(key + " ") && length > 6`). So a medium whose
title is a prefix of another's opens with **the other medium's poster and year** for as long as the
read is in flight, then corrects itself when the answer lands. On this fixture the family « Lucky »,
« Lucky (2026) », « Lucky Chances » is exactly that shape.

**Not a defect of the priming**, which is why it is filed against the lookup rather than the screen:
an absent title answers `null` and the screen shows its skeleton, which is correct. What is wrong is
a resolver that answers « close enough » to a question about identity. The placeholder is never
written into the cache — verified — so nothing durable is corrupted; what the reader sees for a few
hundred milliseconds is another film.

<sub>`grep -n "startsWith" frontend/maquette/design/src/engine/legacy.js` around `normalisedKey`;
prime `/media` for a title that prefixes another and read the hero before the answer lands</sub>

**B-279 — twelve contracts-tier guards run in no CI job when a pull request edits only the guard.**
`harness-contracts` is the only job that runs them, and it gates every step on the `maquette`
filter, which names their SUBJECTS and not their own files. `scripts/**` belongs to `python`, whose
jobs do not run them: CI never runs `make check` as such — it splits into `lint`, `test` and
`guards`. So the shape every repair to a guard takes ran the guard nowhere. B-244's third
recurrence, and the reason the two existing holds stayed green is that both read a guard's subject:
the third question — is the guard ITSELF named? — had never been asked. Fixed by naming the CLASS
(`scripts/check-*.py`) rather than the instances, because the instance list went stale three times,
and by a hold that computes, per guard, whether any job running it is ungated or gated on a filter
naming it.

<sub>`python3 -m pytest tests/scripts/test_ci_filter_covers_the_guards.py -q` → 66 passed; remove
the glob and 11 fall</sub>

**B-280 — transition A-extended had no subject.**
« Voir la fiche » is reached from an open panel. The engine closed the panel and waited 260 ms
before opening the screen, so by the time the transition captured the old state
`#sheet[data-open]` matched nothing and `::view-transition-old(leaving-panel)` never existed. The
whole drawing painted nothing for a day, and every hold in R115 passed because every one of them
reads the ROOT transition, which happens either way. A view transition captures the old state at
the next rendering update rather than at the call, so no ordering of two statements in one task
fixes it: the dismissal belongs inside the commit, which is what `go()`'s `during` is for. The
reverse animation was removed rather than left waiting — Back lands on the list with the panel
shut, measured — and reopening a panel on a backward step is **L13's**, with B-275.

<sub>panel open on `lib-grid`, click `[data-mediasheet]`, sample
`getAnimations().map(a => a.effect.pseudoElement)` → `::view-transition-old(leaving-panel)`
present</sub>

**B-281 — the media body's arrival had two owners.**
The blocks carry an element-side entry from an `@starting-style`, on the argument that an element
already present when the screen mounted never has a starting style. The whole screen is inserted
INSIDE the view transition's callback, so every block has one on the arrival itself: measured at
16 ms intervals, `opacity` and `translate` ran from 0 and 16 px in the very frames `body-rise` was
lifting the same snapshot 24 px. Forty pixels and a double fade, in the drawing whose own heading
is « one entry, one owner ». The transition is silenced while the page's own is running rather than
the rule being scoped away — scoping leaves `translate: none` for the arrival and `0 0` afterwards,
a second owner one frame later, which the new hold caught on its first run.

<sub>sample the first child of `[data-region="screen-media/body"]` at 16 ms across an arrival →
one owner, `body-rise`</sub>

**B-282 — the fanart's entry faded the element that carries the placeholder.**
`[data-arrival="faded"]` animated the hero background element from opacity zero. That element IS
the placeholder: `bg-muted` is its background colour and the melt is its `::after`. At the moment
the picture decoded, the muted block and the melt vanished for a frame and came back with the
image — appear, flash, reappear, in miniature, inside the rule written to remove that shape from
the hero. The faded branch held `min < 1.0`, which a flash satisfies as well as a fade. A
`::before` the placeholder's colour covers the picture and fades out now; the element never changes
opacity. It also answers the case nobody had measured — a file decoding DURING the 450 ms
transition, which the fixture produces on a LAN.

<sub>sample the element's opacity and its `::before`'s across a faded arrival → element 1
throughout, cover 1 → 0</sub>

**B-283 — during priming, the media screen prints its unknown parts as answers.**
Decision (6) of this wave says « skeletons reduced to the unknown parts ». The screen has no
skeleton at all: while the sheet's read is in flight, a missing field prints
`screens.media.synopsisUnknown`, `castUnknown`, `noTrailer` and « unknown » seasons — assertions
about data still in flight, which §13 refuses. **The maquette cannot exhibit it**, and that is why
nothing saw it: the placeholder is the engine's COMPLETE `sheetFor(title)`, so no field is ever
missing during priming — measured, the body holds 8 children at 120 ms and 8 at 2 400 ms. The real
backend's projection carries `{t, f}`.

**Owner: L14.** The repair is a line in `features/media/media-screen.tsx`, one of the four files
L14 owns and this lot may not extend — which is also why it is filed rather than fixed.

<sub>`grep -c "Unknown\|noTrailer" frontend/maquette/design/src/features/media/media-screen.tsx`;
drive with a partial placeholder and read `[data-part="no-info"]` while `status === "pending"`</sub>

**B-284 — a pull cancelled by a mouse or a stylus was forgotten rather than released.**
`pointercancel` is ignored for a FINGER on purpose: the browser claims the pan one move in while
the touch stream carrying the gesture keeps running. For a mouse or a stylus there is no such
stream and a cancel is the platform taking the pointer away for good. The module cleared its three
variables and told the surface nothing, so the indicator hung at the height the cancelled pull left
it, armed, transition suppressed, until some later gesture moved it. The engine called its release
there — which is why « carried over verbatim » was not true — and nothing drove a mouse cancel, so
nothing saw it.

<sub>`frontend/maquette/harness/press.py` → « a cancelled mouse pull puts the indicator BACK »;
its mutation reads `{'height': 72, 'armed': True}`</sub>

**B-285 — `go()` discarded the router's promise.**
A view transition captures the NEW state when the callback's returned promise settles. Discarded,
the capture happens at the next rendering opportunity whether or not the route has committed — so
the day a route has a loader or a lazy component, the arrival animates the departing page, and
every hold in R115 stays green because they all read the OLD side. Correct today only by the
absence of loaders, which is not a property anybody is holding.

<sub>wrap `document.startViewTransition` and read whether the callback returned a thenable → true;
`void navigated` makes both preferences fall</sub>

**B-286 — a hero whose picture changes under it was never followed again.**
The media screen leads to other media — a suggestion, a related title — the route's params change
and the SAME element stays mounted with a new `background-image`. `artwork-arrival` returned early
on `data-arrival` being set at all, and its observer watched added nodes only. So the stale mark
stayed, no entry played, and the new fanart snapped in — on the navigation most likely to happen
twice in a row. It follows by SOURCE now, clears the mark before re-marking (an attribute re-set to
its own value restarts no animation), and a decode landing after the picture moved on marks
nothing.

<sub>media → media on the last `[data-mediasheet]`: same node, background changed,
`data-arrival` written again</sub>

**The disposer is kept** and is not offered as the fix: an effect that installs listeners and returns
nothing leaks a set on every remount, which is true independently.

<sub>drive the drawer's dismiss with a real touch stream and watch `data-feedback` with `attributeOldValue: true`</sub>

---

**B-277 — `exits.py`'s frame-count control flakes under the suite's parallel load.**
« The scrim's exit really animates, so the hold below has something to measure » fell in two full-suite
runs out of three and passed **alone, twice, reliably** — reading `0 frame(s)` where it wants more
than three. The suite runs eight rules at a time; `requestAnimationFrame` is what the sampler counts
by, and under that contention 24 frames span a window the exit no longer sits inside.

**It is worth an entry precisely because it is a CONTROL.** Its whole job is to refuse a vacuous
reading of the hold beneath it — « something to measure ». A control that itself flakes trains a
reader to re-run until green, which is how a real fall gets dismissed as noise; and the harness's own
« re-run it alone » rule, applied to a control, means the first thing the re-run removes is the
condition the failure needed.

**Not attributed to L12's changes**, and that was checked rather than assumed: the suite ran green
several times AFTER the scrim's duration was redrawn, and the two falls came later with only a CSS
deletion and prose between. The likely shape is a sampler counted in FRAMES against an animation
measured in MILLISECONDS — B-276's neighbour rather than its instance.

**ITS BOUND — WHEN IT MAY BE READ AS TRUE, AND WHEN AS FALSE.** A control that flakes can lie in
both directions, so its reading is only worth what its conditions are. Written out because the next
reader will meet it as a red line in a suite and has to know which way it can be wrong.

- **A FALL is not evidence of a defect** *by itself*, and specifically not when the suite ran it
  alongside seven others: 24 frames of `requestAnimationFrame` under that contention span a window
  the exit no longer sits inside, and `0 frame(s)` is what that reads as. **Re-run it ALONE. A fall
  that survives running alone is real** — that is the only reading of a fall that stands.
- **A PASS is worth its full weight**, in the suite or alone. Nothing about frame starvation invents
  frames: if more than three frames were seen mid-exit, the exit animated. This control cannot pass
  falsely; it can only fail falsely, which is why the remedy is a re-run and not a tolerance.
- **AND THE RE-RUN IS ITSELF A HAZARD**, which is the reason this entry exists at all. « Run it
  alone » applied to a control REMOVES the load the failure needed, so the habit it teaches is to
  re-run until green — and that habit is how a real fall elsewhere gets dismissed as this one. Anyone
  re-running it alone should say so in the same breath as the verdict, as this wave's close does.

**Left open**: the fix is to sample against the clock, or to make the frame budget follow the
duration it watches, and that is the harness's tooling rather than this lot's.

<sub>`frontend/maquette/harness/run.sh` (2 falls in 3) against `python3 frontend/maquette/harness/exits.py` (green, twice)</sub>

---

**B-276 — a hand-set delay in an INSTRUMENT outlives the duration it was set against.**
Named as a species because it happened twice in one rule, in one wave, and neither instance was
wrong when it was written.

`harness/touch.py` waited **420 ms** between press surfaces and **340 ms** after closing the sheet.
Both were calibrated against a layer that took 200–300 ms. L12 drew the panel's rise on
`--duration-4`, so the close became 450 ms and the scrim's `visibility` carries that as a DELAY —
and the rule then pressed a poster the scrim was still covering, and pressed the next surface while
the previous sheet was still closing. Two of five surfaces failed; both passed in isolation, which
is what makes this expensive to diagnose.

**This is B-269's shape moved from a guard into an instrument.** B-269 is five corpus floors
« calibrated by hand, one figure per corpus »; these are two delays calibrated by hand against a
duration somebody else later redraws. The failure mode is identical — right on the day it was typed,
wrong the day the thing it describes legitimately changes, and indistinguishable in a log from a
real defect.

**Not fixed as a species here**, and the distinction matters: both instances are repaired, with the
reason written beside each, but nothing stops the third. The shape a fix would take is a delay
DERIVED from the value it waits on rather than typed beside it — the harness would have to read the
drawn durations, which is a piece of tooling and not this lot's.

<sub>`frontend/maquette/harness/touch.py` — `wait_for_timeout(700)` twice, each with the duration it now follows</sub>

---

**B-275 — Back from a media screen opened from the panel does not reopen the panel.**
§16's first rule: Back returns to the previous ARRIVAL. Opening a media screen from the panel makes
the panel the previous arrival, so Back should reopen it over the list. Measured, it does not:
`/media?panel=follow:…` → « Voir la fiche » → `/media/tmdb/1284465` → Back lands on **`/`** with
`#sheet[data-open]` absent.

**It is PRE-EXISTING and not L12's**, and that was established rather than assumed: the identical
flow on `origin/main` (5322c2fa), built and driven the same way, gives the identical result — `/`,
no panel, the same 1.3s. The first attempt to check this was worthless and said so, which is why the
second was run: `git checkout origin/main` was REFUSED because a source file was still modified, and
the « comparison » therefore ran on the branch under test. A checkout that aborts is not a checkout.

The cause is the ladder rather than the transition: opening a screen from a layer settles history
through `switchPageFromLayer`, which REPLACES the layer's entry instead of pushing over it — the
engine's own comment explains why (letting the close unwind and the arrival push would race). Undoing
that is the ladder's handler, which **L12 is forbidden to touch by name** (it is L13's).

**Consequence for this lot, stated plainly**: the operator's decision 3 asks the return to play the
mirror of the departure, and the rule that would draw it has **no subject**, because the panel is
never the thing being returned to.

**The rule was REMOVED rather than kept (2026-09-01).** The entry above said « it costs nothing and
is kept », and that is the sentence this repository has paid for twice: machinery nobody can justify
becomes machinery nobody dares delete. `::view-transition-new(leaving-panel)` is written the day the
return exists, which is also the day its shape can be verified. **L13 owns both**, and the plan says
so at that lot rather than only here.

**What DID land is the departure**, which had no subject either and now has one (B-280): the panel is
captured leaving, `::view-transition-old(leaving-panel)` runs `panel-down`, and R115 falls if it
does not.

<sub>`frontend/maquette/harness/transition.py` — `hold_the_panel_departs` drives the whole flow (long press, « Voir la fiche ») and reads the pseudo-elements; add `page.go_back()` after it and read `location.pathname` and `#sheet[data-open]`. The original proof was a script in `/tmp`, which cannot be replayed from the tree — the same lesson as the report that was never committed.</sub>

---

**B-274 — `page_host.py`'s state-alias arm read docstrings as code, and accused a rule that mutates nothing.**
The arm refuses a harness rule that drives a page by writing the engine's `state` alias. It flattens
each script first — comments dropped, **quote characters removed**, whitespace collapsed — and the
quote removal is deliberate and right: a driver is a string here, split at the author's convenience,
so a real `state.page = 1` hides inside one.

But it turns English prose into something that reads like code. A docstring ending « … and the
pressed state. » immediately before `errors = []` flattens to `state. errors =` and matches the first
shape exactly. **Measured on `harness/feedback.py`, a rule that mutates nothing at all**, which the
tier then reported as a contract failure.

This is B-085's species with its sign reversed — a guard green over what it does not read is the
usual direction; this one goes RED over what it should not read — and it is the same root cause the
compositor guard paid for, where five of thirteen `touch-action` sites turned out to be prose, two of
them the sentence naming that guard.

**Fixed in the same move, and narrowly**: docstrings are blanked before the flattening, and ONLY
docstrings — driver strings are left intact, because a rule that really drove `state.page = 1` would
do it inside one. `ast` is what tells the two apart: a docstring is the first statement of a module,
class or function and nothing else is. Verified both ways — the false positive is gone, and a
genuine `state.page = 1` planted inside a driver string still falls.

<sub>`python3 frontend/maquette/harness/page_host.py` after adding a docstring ending in « state. » above an assignment</sub>

---

**B-273 — `scripts/mutate.sh` cannot judge a guard, and is silent when a mutation breaks the build.**

**The second half, found 2026-09-01 and it is the sharper one.** The script reports « no hold
fell » for a GUARD under mutation *whatever the guard says*: it decides by reading journal `FAIL`
lines, and a guard in `scripts/` prints violations and exits 1 without ever printing one. Three
mutations aimed at `check-markup-contracts.py` were reported as caught by nothing while the guard
was in fact naming the defect and exiting 1 — and the first two of those were believed, and led to
the arm being rewritten twice on a false reading. **A verdict that is the same whatever happened is
not a verdict**, which is this register's own subject applied to the tool the register's proofs are
made with. Until it reads exit codes as well as journals, a guard's mutation is run by hand.
It mutates, runs `npm run build`, then `served_copy.py --publish`. When the mutation
breaks the build — renaming an exported symbol its importers still name, which is an
ORDINARY mutation to want — the publish fails, `set -e` exits the script, and the trap
restores the file. **No rule runs, and nothing is printed about why.** The output is the
mutation line and the restore line, with neither a rule's verdict nor the « NO RULE FELL »
the script prints when a rule genuinely does not catch something.

It is not actively misleading — the absent verdict is not a false one — but it is one
glance away from being read as « the tool ran and found nothing », and this repository has
a register entry for exactly that reading (« a failed command is not a no-op »). Met while
mutating the feedback seam: the branch had to be exercised by hand instead, running the
guard directly, which needs no build because it reads source.

**Not fixed here**: the fix is `mutate.sh`'s, one visit for whoever next touches it, and it
is small — report the build's failure and say that the mutation was invalid rather than
that nothing happened.

<sub>`scripts/mutate.sh frontend/maquette/design/src/lib/feedback.ts 't.replace("export function feedback(", "export function acknowledge(")' scripts/check-feedback-seam.py`</sub>

---

**B-272 — the compositor guard's floors carried slack, and its own note claimed they did not.**
`compositor-css.json`'s `taken_at` said « the figures below are the real sites, so a deletion has no
slack to hide in ». Measured on 2026-08-31 by raising each floor until it bit: `touch-action` stood
at **8 against 11** real sites, `user-drag` at **3 against 4**, `user-select` at **4 against 5**.
**Three `touch-action` declarations could have been deleted with the guard green** — which is
precisely the incident the file exists to prevent (`user-drag` vanishing with a converted selector,
three gesture holds failing for a reason that looked nothing like a CSS deletion), sitting inside the
instrument written to prevent it. B-085's species: a guard green because of what it does not read.

The floors were RIGHT when they were taken at L07's close and drifted as L08 to L11 added surfaces —
nobody re-took them because nothing asked, and a floor is silent about the distance between itself
and the truth. Found while raising `tap-highlight-color` off its deliberate zero for P25 and noticing
that the mutation of a two-declaration block produced one violation instead of two.

Fixed in the same move: the floors are the measured counts, and the measurement is now written as a
COMMAND rather than a reading — raise a floor until the guard falls; the last value that passed is
the true count. **What stays open is the general shape**: nothing re-takes these floors on a
schedule, so they will drift again the next time a wave adds surfaces.

<sub>`python3 scripts/check-compositor-css.py` after editing one floor upward in `frontend/maquette/compositor-css.json`</sub>

---

**B-271 — `MODEL.md` cited `index.html:241` for `#ptr`, and that line holds the skip link.**
Part 8 assigns pull-to-refresh to L12 and located it at `index.html:241`. That line is inside the
comment explaining the skip link's `tabindex="-1"`; the `#ptr` element opens at `:253` and carries its
id at `:255`, and the engine drives it from `legacy.js:32313`. The citation was not wrong when it was
written — it drifted — which is exactly L15's paid shape (« cited line numbers past the end of the
file ») in a document no guard reads for line numbers. Found by re-deriving the L12 plan's citations
against the tree rather than copying them from the model. Corrected in the same move (§ 7.1: what
loses its subject is fixed, not kept). **The general defect is not fixed**: nothing checks a
`file:line` citation in `docs/`, and `check-docs-cited-paths.py` reads paths, not lines.

<sub>`grep -n 'id="ptr"' frontend/maquette/design/index.html` · `grep -n 'select("#ptr")' frontend/maquette/design/src/engine/legacy.js`</sub>

---

**B-270 — two harness journals are labelled « R80 », and `attrs.py`'s has no number of its own.**
`harness/residue.py` is R80 (a typed variant and the residue rule shadowing it agree; the README's rule
table says so). `harness/attrs.py` — how React renders a boolean into an attribute — opens no rule
number and labels its journal `Journal("R80 — how React renders a boolean into an attribute")`. Any
reader that keys on the label merges two rules; the hold-count baseline keys on the FILE, which is
why no count is wrong today, and why nothing said so. Found while re-deriving the L12 brief's rule
citations. One line to fix, with the next free number — the harness's, in the same visit as B-268 and
B-269.

<sub>`grep -n "R80" frontend/maquette/harness/attrs.py frontend/maquette/harness/residue.py`</sub>

---

**B-269 — five corpus floors in `served_copy.py` are calibrated by hand, one figure per corpus.**
`served_copy.py:619` floors five filtered corpora, each floor « set near its own corpus » — which is
five hand-written figures, B-254's species inside an instrument: right on the day they were typed,
wrong the day a refactor legitimately shrinks a corpus, and indistinguishable in a log from a floor
that still bites. The wave's own author said they would not defend them hard. Two honest exits: DERIVE
each floor (a fraction of the corpus measured at record time, stored beside the hold counts so the
squash re-record refreshes it), or keep the calibration and write next to each figure the command
that re-measures it. Owner: the next wave that touches the harness — with B-268, they are one visit.

<sub>`grep -n "for name, corpus, floor in" frontend/maquette/harness/served_copy.py`</sub>

---

**B-268 — R104 lives in the file it measures, and has been defeated twice by exactly that.**
R104 holds `served_copy.py`'s publish-then-stamp ordering and is DEFINED in `served_copy.py`. It has
been beaten twice by self-reference: three substrings satisfied on the rule's own assignment lines,
then both search anchors found in the rule's own source (`1419 < 9068`, where 9068 was the searching
line). The current answer, `_function_body`, is one file-reorder from the same class: if `publish()`
ever moves below the rules, `find()` meets the rule's literals first. **The shape is the defect**: a
rule inside the file it measures inherits every future edit of that file as a potential self-match,
and the repository's own doctrine — an instrument written by whoever it measures inherits their
blind spots — applies here at the level of the FILE. Recommendation: the ordering holds move to a
reader OUTSIDE the file (a `tests/scripts/` test reading `served_copy.py` as text through its AST,
where the searching source and the searched source cannot be the same object). Owner: the next wave
that touches the harness; the operator may place it sooner.

<sub>`grep -n "_function_body" frontend/maquette/harness/served_copy.py` · `grep -c "def publish(" frontend/maquette/harness/served_copy.py`</sub>

---

**B-267 — the real backend's failure shape does not match the one the queue reads, and at switchover every refusal becomes a queued mutation.**
Found by the fourth adversarial round, and it is LATENT rather than live: the mock layer emits the
right shape, so nothing in the maquette is wrong today. `isRequestFailure` requires
`{status, title, detail}`. `personalscraper/web/deps.py` raises `HTTPException(403, detail="…")`
and FastAPI serialises `{"detail": "…"}` — no `status`, no `title`, and there is no
`exception_handler` reshaping it. On the day `send()` points at that server, **every** refusal —
403 read-only, 401, a 400 for a missing `X-Requested-With`, a 409 — fails the shape test, takes the
OUTAGE branch, and is queued: the optimistic write stands over an action the server refused, and
the replay meets the same answer forever. NE-DOIT-PAS-1 from both ends at once.

**It belongs to the lot that binds the maquette to the backend**, and it is written here so that
lot finds it rather than discovering it in production. The fix is one of two: a FastAPI exception
handler that emits the problem shape the interface already reads, or a reader on this side that
accepts `{detail}` — and the first is the one §15 asks for, since the interface declares what it
requires and the backend follows.

<sub>`grep -rn "HTTPException(" personalscraper/web/deps.py | head -3` · `grep -n "isRequestFailure" frontend/maquette/design/src/lib/query-client.ts`</sub>

---

**B-266 — a notice button's name, words and action were three ladders in different orders.**
Found by the third adversarial round. The label and `data-connection-action` tested « does the
condition owe an explanation? » first; the click tested « is a refusal recorded and nothing
waiting? » first. On a lost connection with a refusal and an empty queue they disagreed: the button
said « Réessayer maintenant » and CLEARED the refusal instead of reconnecting — so pressing the
reconnect button did not reconnect, and silently discarded the record the round-two repair exists
to show. It is the same « lie by suggestion » that repair was written for, reintroduced by writing
the decision three times. One function decides all three now.

<sub>`grep -n "whatToOffer" frontend/maquette/design/src/app/connection-notice.tsx`</sub>

---

**B-265 — the queue's drop-decision treated 401 as final, destroying every queued mutation an expired session met.**
Found by the third adversarial round, inside the second round's repair for exactly this. That repair
replaced « did the layer answer? » with « will re-sending ever produce a different answer? » and
implemented it as a DENY-list: 408, 429 and the 5xx were kept, everything else at or above 400 was
final. **401 fell through it.** An installed application with the radio off queues N mutations; the
session expires; the radio returns; the first replay answers 401, the envelope is destroyed, the
loop continues, and all N are destroyed the same way — when a re-login would have made every one of
them succeed. The commit that introduced it names that case as fixed.

**A deny-list is wrong here by construction**, and that is the repair: the safe direction is to KEEP
the operator's action, so anything unlisted must be kept. `FINAL_STATUSES` names the seven that say
something about the REQUEST — 400, 404, 405, 409, 410, 415, 422 — and nothing about the caller's
identity is among them, because 401 and 403 change when a session or a right changes and 423
unlocks.

<sub>`grep -n "FINAL_STATUSES" frontend/maquette/design/src/lib/query-client.ts`</sub>

---

**B-264 — `caches.open` creates, so a controlling worker re-made the cache a sign-out had just deleted.**
Found by R111 on 2026-08-31, one minute after that rule was written to prove B-261's repair — and it
is the reason a repair needs a rule rather than a reading. `signOut` deleted every `tm-shell-*`
cache and the cache was still there afterwards. The worker still CONTROLS the page until it
unloads, its fetch handler opened the cache by name on the next request, and `caches.open` creates
one when it is absent. The teardown had run perfectly and left no trace.
`caches.match(request, {cacheName})` reads without creating, and it gives the same guarantee the
scoped `open().match()` gave: this build's cache and no other.

<sub>`grep -n "caches.match" frontend/maquette/design/sw.js`</sub>

---

**B-263 — a refused replay jammed the queue forever, over an optimistic write the server had rejected.**
Found by adversarial review of L11's own change. `departAll` stopped on ANY failed departure, and
a refusal is not an outage: 401 on an expired session, 404 on an item already gone, 409 from a
second operator. The envelope was never forgotten, every envelope behind it was blocked with it,
the pending count never fell, and the interface went on showing the operator's action as applied
over something the server had refused. That is NE-DOIT-PAS-1 — the defect the queue exists to
prevent — arriving from the other side, with no path out of it but clearing storage by hand.
The queue asks whether the layer ANSWERED, through a predicate injected with the departure so it
still knows no domain; a refused envelope leaves the queue and is remembered.

<sub>`python3 frontend/maquette/harness/outbox.py` → « a replay the layer REFUSES leaves the queue rather than jamming it »</sub>

---

**B-262 — the update discipline reloaded without ever swapping the worker, and then never swapped again.**
Found by adversarial review. `registration.update()` resolves when a worker begins INSTALLING, not
when it is waiting — so `registration.waiting` was null, the optional chain swallowed the
`skip-waiting` message, and the page reloaded anyway. After that reload the served build EQUALS the
running build, so the comparison returns early and the message is never sent again for the session:
the page runs the new build while the OLD worker controls it, and the new one is parked until every
tab closes. The file's own comment said « what changes here is the signal, and only the signal » —
what had changed was the reload's ORDER against the swap. Driven from `updatefound` →
`statechange` → `installed` now, with the reload following `controllerchange`.

<sub>`grep -n "updatefound\|controllerchange" frontend/maquette/design/src/app/worker-registration.ts`</sub>

---

**B-261 — the cached shell outlived the session that filled it.**
Found by adversarial review, and it is a security regression L11 introduced. Before this wave the
worker cached one page — the offline notice. It now caches the document and every bundle, taken
from an AUTHENTICATED context, and **nothing cleared them on sign-out**: a cache outlives a cookie.
Sign in on a phone, sign out, hand it over, turn the radio off, and the whole password-protected
prototype renders from disk with no session. Online it still answers 401, so the bypass cost exactly
one toggle of airplane mode. `signOut` deletes every `tm-shell-*` cache and unregisters the worker,
each step independent and best-effort — refusing to sign out because a cache would not clear is the
worse of the two failures. **R111 holds it, with a control**: « nothing is cached after signing
out » is also true of a browser that never cached anything.

<sub>`python3 frontend/maquette/harness/pwa.py` → R111's three holds</sub>

---

**B-260 — a harness rule named after a standard library module shadows it for everything downstream.**
Found by `make check` on 2026-08-31, and the symptom names nothing that would lead you to it: four
subprocess smoke tests failed with `AttributeError: module 'platform' has no attribute
'python_implementation'`, raised inside `attr/_compat.py`, which none of them mentions. The new
rule was called `platform.py`. A rule is run as `python3 <harness>/<rule>.py`, which puts the
harness directory at `sys.path[0]`, and `tests/scripts/` puts that directory on the path too — so
every `import platform` downstream got the rule.

**What makes it worth an entry rather than a rename.** It was invisible to every gate that had run:
`ruff`, the harness suite, the boundaries guard and the abbreviation guard all passed, and the rule
itself was green. Only the full test suite saw it, and only through four tests in a different
subsystem. The general form is the part to keep: **a directory that lands on `sys.path` may not
hold a file named after anything in the standard library**, and the harness is 80 such files.
Renamed to `installed.py`, with the reason written in its own header.

<sub>`python3 -c "import platform, pathlib; print(pathlib.Path(platform.__file__).parent)"` from `frontend/maquette/harness`</sub>

---

**B-259 — the design host answers 401 for `/` itself, so a worker installing from the gate can require nothing.**
Found by L11 on 2026-08-30, by a symptom that names nothing: « the service worker never became
ready », a 401 in the console, and no registration left behind. A browser reads the manifest of the
page in front of it and never one waiting behind a cookie, so the only document a phone can install
from here is the SIGN-IN GATE — and there `/vite/*` answers 401 because the bundles are the
prototype, which is what the password protects, and `/` answers 401 too because the login page is
served WITH that status. `cache.addAll` and `Promise.all` both fail the install as a whole. The
install attempts everything and requires nothing; the running application completes the shell,
which is the first moment anything is reachable; and what guarantees the shell is whole is R105
reading the cache after boot rather than a promise made at install.

<sub>`python3 -c "import urllib.request as u" -c "import urllib.error as e"` — or, as one line that PRINTS: `python3 -c "exec('import urllib.error as e, urllib.request as u\\ntry: u.urlopen(\\'https://tm-design.iznogoudatall.xyz/\\', timeout=15)\\nexcept e.HTTPError as x: print(x.code)')"` → `401`. Written CAUGHT because `urlopen` RAISES on a 4xx and never reaches `.status` — and written as one runnable line because the first repair of this line was prose about a command, which is the same defect one step further along.</sub>

---

**B-258 — the Makefile's contract tier announced « 9 rules » where `run.sh` held 12.**
B-254's species in a line B-254's own repair did not reach: a hand-written figure beside a script
that prints the real one. Fixed by REMOVING the figure rather than correcting it, so the class of
defect goes with it — `run.sh` prints the count and always has.

<sub>`grep -n "contract subset" Makefile`</sub>

---

**B-257 — push notifications are declined, and the reason is written here so it is a decision.**
The operator's principle (Q4, 2026-08-30) is that every entry point the platform offers an
installed application is declared *unless a written reason says why not*. This is that reason: a
permission prompt with nothing to send trains the operator to refuse it, and a browser remembers a
refusal far longer than a wave. **The consumer exists and is named** — a ratio alert arriving by
FCM, which is §18, which is **L16**. R108 holds the manifest to declaring no push, so reversing
this is a deliberate act rather than an accident.

**It closes, and its third column reads `by L11`.** Both were wrong on the register's own rules: `1×` counts the times the OPERATOR has had to say a thing again, and nobody reported this — it is the wave's decision record. And `open` means « diagnosed, not yet fixed » while the instrument that holds the decision exists and bites, which is rule 3's closing condition. Left open on the sentence « the consumer is L16 », it would be the deferral shape rule 3 was dictated to end.

<sub>`python3 -c "import urllib.request as u,json; print('push' in u.urlopen('https://tm-design.iznogoudatall.xyz/manifest.webmanifest').read().decode().lower())"` → False</sub>

---

**B-256 — the harness's served copy has no lock and no build stamp; a fresh copy arriving mid-run is a false reading either way.**
Found by collision on 2026-08-30: the steward's `make maquette-oracle` rebuilt and re-copied
`/tmp/tm-refonte/wrapped.html` while the executing agent's suite was mid-run, and two of the agent's
rules fell over a build they were not started against; both passed alone. The dangerous case is the
other direction — a rule can PASS over the wrong prototype just as silently. `run.sh` re-copies
unconditionally at every invocation; the harness README warns only that a STALE copy measures the
previous build. **No instrument reaches this without a build stamp the rules read** (write the built
commit into the copy, have every rule assert it at start), and no lot owns the harness's serving
mechanism — the convention (two sessions coordinate by message first) is in `frontend-steward.md`.
**Placed by the operator on 2026-08-30: the stamp rides the next wave — L11, in flight — and its
agent is told.**

**Placed on L11 by the operator on 2026-08-30, and closed there.** A lock PREVENTS and a stamp
DETECTS, and neither is enough alone: the lock covers the builders that take it and cannot cover a
reader started before it existed or a rule launched by hand from an editor. `harness/served_copy.py`
holds both. The stamp is read in three places and the coverage of each is given WITH ITS COMMAND,
because the first version of this paragraph published four figures that were stale on the day they
were written — the wave had added four rules, and « 75 of 75 » was 79.

<sub>`ls frontend/maquette/harness/*.py | grep -v common.py | wc -l` (every rule, covered by
`run.sh`'s per-rule wrapper — the only reading that reaches `audit2.py`, which uses no
`common.Journal` and is the rule that started the incident) · `grep -l "open_page" frontend/maquette/harness/*.py | grep -vc common.py` · `grep -l "Journal("
frontend/maquette/harness/*.py | grep -vc common.py` (the two ends `common.py` asserts at — and
`common.py` is EXCLUDED from both, because it is the file doing the asserting and not a rule being
protected; counting it was this paragraph's second wrong figure in two rounds)</sub>

**AND IT WAS STILL OPEN AFTER THE FIRST REPAIR.** `scripts/mutate.sh` and
`scripts/harness-hold-counts.py` each rebuilt and re-copied the served copy with neither the lock
nor the stamp — the tool that recorded this wave's own baseline, and the mutation tool the method
mandates. The assembly is `served_copy.publish()` now and all three call it, which also ends the
other half: `sw.js` and `build.json` had joined the copy in `run.sh` alone, so a copy either tool
made served a worker from a previous build.

R104 holds the WIRING, because the unit tests prove the lock and the stamp behave and cannot prove
`run.sh` still calls them — a mechanism nothing calls is a mechanism that is not there, which is how
B-256 existed at all. It reads the COMPARISON and not three substrings that survive without it, and
`_code_of` strips docstrings as well as `#`: leaving them, the arm was satisfiable by moving an
assertion's sentence into a docstring and deleting the assertion.

<sub>`grep -n "cp .*wrapped.html\|tm-refonte" frontend/maquette/harness/run.sh` · `python3 frontend/maquette/harness/served_copy.py`</sub>

---

**B-255 — `check-frontend-boundaries.py` is back at 952 lines, 48 from the hard ceiling it was cut away from.**
B-050 (#500) found it at 921 and L07-bis split three guards on a subject rather than a line count.
`python3 scripts/check-module-size.py --root scripts` on `main` at `99a82a35` warns at **952** — it grew
through L08 to L15 by an arm at a time, the shape B-050 named. The next arm added to it crosses 1 000
and `make check` refuses the pull request that adds it, for a reason foreign to that pull request.
Open, and the split is a wave's: the next lot that touches the file cuts it on a subject first —
the ADDRESSING arm is a whole one on its own (the executing agent's own reading, 2026-08-30, owning
its share: L15 added twice to a file already at the soft warning, and « the change is small » is how
a file reaches a ceiling nobody decided to approach). On a subject, not on a line count, or it is
back at 900 in two waves with the arms interleaved differently.

<sub>`python3 scripts/check-module-size.py --root scripts`</sub>

---

**B-254 — two figures written by hand, both wrong on the day they were read.**
`Makefile`'s `maquette-oracle` target announced « 83 states x 33 regions » while the run beneath it
printed 87 × 34; `CLAUDE.md` § 4 said the contracts tier runs « twenty » cheap guards after the
steward had corrected « nineteen » the same day, and `run.sh` lists 23 with this entry's own guard.
A number written in prose is right once. Both now say what the instrument prints and no number.

<sub>`grep -c "states x" Makefile` → 0 · `frontend/maquette/harness/run.sh --contracts | grep "cheap guards"`</sub>

---

**B-253 — B-247 was reassigned to L14 and L19 by the wave that left it, and the plan named it in neither.**
L15's report said B-247 (a store bump replaces a feature page's nodes, so a write between
`pointerdown` and `click` destroys the tap) « is L14's and L19's ». `grep -n "B-247"
docs/reference/frontend-architecture.md` returned nothing: a debt with no named owner, which the plan's
own L14 entry calls « a debt nobody pays, and it reappears in the last lot ». Both entries name their
half now, and L19 names B-249's producer half (the 260 ms wait R103 prints) in the same move.

<sub>`grep -c "B-247" docs/reference/frontend-architecture.md` → 2 · `grep -c "B-249" docs/reference/frontend-architecture.md` → 2</sub>

---

**B-252 — the oracle reads a region's node and never its children; two L15 surfaces are held by no rule.**

**CLOSED BY L12 phase 11 — `harness/child_nodes.py` (R116).** Both nodes are read where the
oracle cannot: the dialog's paragraph under BOTH themes, and the danger action's contrast under
`data-theme="light"`. The mutations reproduce the original defects exactly — the paragraph reading
`oklch(0.96 0.003 286)` against a heading of the same value, and the danger action at **1.00:1**,
white on white, which is the figure the steward recorded — **and the oracle stayed green over both,
2 958 measurements, no divergence**, which is D8's prediction confirmed rather than a surprise.

Two things the rule had to be taught, and both are worth keeping: the assertion on the paragraph is a
DIFFERENCE against its heading rather than a literal colour, so a legitimate retune of the palette
does not fell it; and the contrast is computed IN THE PAGE through a 1×1 canvas, because
`getComputedStyle` answers in the syntax the stylesheet used — this palette is `oklch()`, and a
parser expecting `rgb(r, g, b)` reads « 0.58 0.215 25 » and raises, which it did on the rule's first
run.
Measured by the steward on `main` at `212faf0a`: with `dialogParagraph` stripped of
`text-muted-foreground`, and separately with `bg-transparent` restored to `selectionAction`'s base
(the white-on-white destructive button of the light theme, contrast 1.00), `make maquette-oracle`
reported **167 divergences before and 167 after**, every one on `shell/sheet-content` — the two
defects the adversarial review of #528 found by eye are invisible to the instrument by its own
contract, which D8 already stated for pseudo-elements and now states for descendants. **The two
surfaces are repaired and held by nothing**: the light-theme ratchet stayed at 166 across the defect
and its repair. D8's contract is that a child carrying a function is covered by a NAMED rule: one
that reads `color` of `.dlg p` under both themes, one that reads the danger action's contrast under
`data-theme="light"`. **Placed by the operator on 2026-08-30: L12's**, written into its entry in the plan.

<sub>`sed -i '' 's/ text-muted-foreground"/"/' frontend/maquette/design/src/ui/variants/frame.ts && make maquette-oracle; git checkout -- frontend/maquette/design/src/ui/variants/frame.ts` → 167 both ways</sub>

---

**B-251 — a document under `docs/` can be written, cited and never committed, with nothing red.**
The operator's global `~/.gitignore` carries a `docs/` rule, so a NEW file under `docs/` is
ignored: `git add -A` skips it, `git status` does not list it, and no gate in this repository —
`check-bug-register`, `audit_design_coverage`, `check-implementation-state`, CI's `docs` filter —
reads a path that is not in the index. A folder whose other files were force-added once looks
entirely normal, because the tracked siblings are tracked. **Found on 2026-08-30 by the steward,
measuring `origin/main` after L15 merged**: `docs/archive/features/maquette-l15/REPORT.md` was cited in the
pull request body, in the wave's own account of its gates and in two cross-session reports, and it
existed on one disk. `BRIEF.md`, `DESIGN.md` and `plan/` were there because the commit that created
them used `git add -f`; every commit after that skipped the report in silence.

**This is B-219's shape with a worse mechanism.** B-219 is a document that says something untrue;
this is a document that is not there at all, and the difference is that a reader who greps for it
locally FINDS it. The check is cheap and does not exist: after any commit that was meant to add a
file under `docs/`, `git ls-files <path>` answers whether it landed — `git status` does not.
Filed open rather than repaired, because the guard belongs with whoever owns the archive gesture
(§ 5's fourth step) and this pull request is that gesture, not its instrument.

<sub>`git check-ignore -v docs/features/<any-new>.md` → `/Users/izno/.gitignore:10:docs/` · `git ls-files docs/features/maquette-l15` listed 22 files and not the report</sub>

**B-142 — the constitution has an instrument, and B-244 is worse than it was filed as.**
Closed by L15's phase 18. `scripts/check-intent-map.py` holds every DOIT and NE-DOIT-PAS clause
against the surface `product-intent-map.md` says serves it, and refuses: a clause with no row; a
verdict outside the five words the map declares; a NAMED surface the tree does not have (a route
path no route file serves, a feature directory that is not there); an owed half naming no lot, or a
lot § 4 does not declare; a « served » naming no rule, harness script or guard; and a row for a
clause that does not exist. It prints ONE LINE PER CLAUSE and never a count alone.

**What it cannot do is the first thing its own header says.** It cannot tell whether a named proof
READS the clause — two rows of the first map named a print statement and a rule about PM2 processes,
and only a reader found them. So it prints the verdict beside every clause, and its summary line
ends by saying whose job that is.

**Its own first version refused all twenty-three rows**, because the map writes a verdict as code —
`` `partly` `` — and the vocabulary is the five bare words. And its second refused every row whose
Surface cell says « every surface »: several clauses bind all of them, which is right and is nothing
a guard could check. What it refuses is a surface NAMED and absent.

**B-244 is closed with it, and the number is seven, not one.** The hold in
`tests/scripts/test_ci_filter_covers_the_guards.py` asked « is this path named by ANY filter? »; the
job that runs the contracts tier gates every step on `maquette`. Asked the second question — « by
the filter that gates the job that runs the guard? » — the hold goes red over **seven** guards:
`check-implementation-state` (`IMPLEMENTATION.md`), `check-intent-map` (the constitution, the map
and the plan), `check-bug-register` (`frontend-architecture.md`), `check-code-abbreviations` (its
three lists), `check-frame-domain` (its baseline), `check-live-relay` (`personalscraper/`) and
`compare-contracts` (`openapi.json` and the demands register). Every one of them was running in no
job for a pull request touching only its own subject. The `maquette` filter names all of them now,
and the hold asks both questions.

<sub>`python3 scripts/check-intent-map.py` — 23 clauses against 23 rows, 0 violations. Three mutations: a clause's row deleted; a lot the plan does not declare; a `served` row pointed at a route that does not exist.</sub>

---

**B-230 — the viewport fallback is deleted, and a guard refuses its pair anywhere.**
Closed by L15, alone. `legacy.js:41–50` added a viewport meta — carrying a maximum scale and a
user-scalable refusal — to any host that had none. **Deleted rather than corrected**: « a page that
does not own its `<head>` » is not a case this prototype has (`index.html` IS the document and
`serve.py` serves it), so a fallback for a host nobody serves is machinery nobody can justify, which
is D5's own shape.

**Why the accessibility tier could not see it, and why the answer is a file guard.** axe reports
`meta-viewport` when the directive is PRESENT on the document it audits, and this one never was:
the branch fired only on a host that had no meta, and the maquette's has one. Dead here, live on
every other host the file could be served from — a landmine is not a defect, it is a defect waiting
for a different reader. `scripts/check-viewport-directives.py` reads every source under `design/` —
markup, script AND stylesheet, because the defect was a STRING built in JavaScript — comments
included, because a directive commented out is one edit away from being live. The only file allowed
to spell either of them is the guard itself, which is why `index.html`'s own comment now names them
without spelling them.

**Its first version had the split-literal blind spot**, found by the mutation that restored the
directive as `"maximum" + "-scale=1"`: a reader of raw text saw neither half. Adjacent string
literals are folded before the search now. What it still cannot see is stated in its own docstring
rather than left to be discovered: a value composed at RUNTIME. No reader of source text can, and a
guard claiming otherwise would claim more than it does.

**The inventory this closes.** `SURVEY.md` § 1.1's command listed nineteen sites when this wave
opened, one of which « draws nothing at all » — this one. It lists **nine** now: seven of the
Découvrir feed (L19's) and two of the harness panel, which ships nowhere.

<sub>`python3 scripts/check-viewport-directives.py` — 165 source file(s), floor 50, 0 violation(s). In the contracts tier as the twenty-first cheap guard.</sub>

---

**B-245 and B-233 — the appearance survives a reload, and the status bar follows it.**
Both closed by L15, in one commit because they are one surface and one rule (R102,
`harness/appearance.py`) — and both are BEHAVIOUR, so they land outside every conversion.

**B-245 is worse than a flash, and the mutation is what said so.** The entry says the pre-paint
script's mismatch cost « a flash on every reload ». Measured, by restoring the mismatch and
reloading: the attribute is not set AT ALL, before or after load. That script is the ONLY reader of
the stored choice at boot — nothing else applies it — so a saved « light » was not applied until the
operator touched the control again. The two ends say the same words now.

**B-233's value is READ, never retyped.** `app/appearance.ts` writes the meta from
`getComputedStyle(document.body).backgroundColor` whenever it writes the attribute — the ground the
document really paints, in whatever colour space the token declares. A second copy of a colour is a
colour that drifts, and this repository has the measurement: the brand colour was renamed and a
retyped copy went on rendering correctly while the reference was broken. The document keeps its own
static `theme-color`, the DARK value, for the frames before any module runs.

**Why nothing saw either.** The oracle runs under the default theme, so a light-theme defect is
outside it by construction; a `<meta>` has no rectangle and no computed style, so it is outside it
twice. The accessibility tier reads the rendered markup and not the head. And the flash is a
property of the FIRST FRAMES of a reload — a state nothing here drove, because every rule opens a
page and then measures it. R102 reloads, drives the interface's own control, and reads the attribute
from an INIT SCRIPT: read after load, the module has long since corrected whatever the pre-paint
script did.

<sub>`python3 frontend/maquette/harness/appearance.py` — 6 holds, no violation. Mutations: the French spellings restored (« first frame None, after load None, stored 'light' »); the meta write removed (« light 11,11,13 against dark 11,11,13 »).</sub>

---

**B-250 — the stale-figure arm cannot tell a register citation from a frozen count.**
Found on 2026-08-30 during L15's entry conversion, by the arm going red over a sentence that could
never be wrong. `check-live-relay.py`'s `stale-figure` arm refuses any literal in its own source
equal to a count it measures — a guard may PRINT a figure and may not write one down (A-2). Its
boundary is `(?<![\w])N(?![\w])`, and a hyphen is not a word character, so **`B-154` is a match
the day the TypeScript corpus reaches that size.** It did, when L15 added the frame's modules, and
the arm reported this module as freezing its own corpus count over a sentence about a defect.

**Fixed in #528**: register citations — `B-NNN`, `E-NNN`, `A-N`, `R-NN` — are struck out of the
source before the search. They are struck rather than exempted one by one, because a list of
numbers to ignore is the shape this arm exists to refuse.

**And it caught the first draft of its own repair**: the comment explaining the fix said « the
corpus reached 154 files », which is exactly the frozen figure the arm forbids. The comment names
no size now, and says why.

<sub>`python3 scripts/check-live-relay.py` — `stale-figure: 2 measured count(s) checked`</sub>

---

**B-237 — the confirmation is ranked above the chrome, and the ranked list exists.**
Closed by L15's phase 10, alone, with R101 (`harness/stacking.py`). The dialog's rank moves
48 → 56 — above the drawer it can be opened from, above the selection bar it usually is opened
from, below the sign-in gate — and `ui/variants/frame.ts` opens with THE RANKED LIST, every rank
the frame paints named once, each variant carrying its number with a pointer back to it. Part 6
says the chrome owns the z-order and that today it is « not a decision but an accumulation »; this
is the decision.

**Half of this entry's own text was wrong, and the rule says so rather than repeating it.** It
read « the bar's four buttons stay tappable over a modal that says `aria-modal="true"` ». They are
not: `app/focus.ts` marks the whole background `inert` while a layer is open, `#nav` among the
thirteen elements it names, and `inert` takes an element out of HIT-TESTING as well as out of the
focus order. What was really wrong is the PAINT — the chrome drawn across a modal wherever the two
met, which a reader sees and a finger cannot report.

**And the rule had to be written three times before it measured anything**, which is this wave's
sixth and seventh instance of B-085's shape. The named delete states raise dialogs of 184–660 and
142–702 against a bar at 787–844: **they do not touch**, so a hold that opened one and hit-tested
its own rectangle passed at 48 exactly as at 56. The overlap is PRODUCED now — a manifest long
enough to reach past the bar, opened through the layer's own verb. And with the background `inert`,
`elementFromPoint` answered the dialog either way; the bar's `inert` is lifted for the length of one
reading and put back.

<sub>`python3 frontend/maquette/harness/stacking.py` — 7 holds, no violation. Mutation: the rank restored to 48; the hold falls with « at: 'nav', dialogRank: '48', barRank: '50' ».</sub>

---

**B-229 — the confirmation dialog is on the ladder, and Back walks it.**
Closed by L15's phase 9, in a commit of its own with its own rule — a BEHAVIOUR
change, never inside a conversion. `app/dialog-host.ts`'s `open` pushes
`pushLayer("dialog")` and its `close` unwinds that entry unless the close IS the
pop; the engine's `onEngineBack` gains a `dialog` branch ABOVE the drawer, asked
of the registration (`app/layer-registry.ts`) rather than of a class.

**Held by R59** (`harness/back.py`), in four holds that read together because no
one of them is the property: a confirmation really opens, so the hold has a
subject; opening it stacks an entry of its own AND that entry carries
`layer: "dialog"`; a back closes it; the page underneath is unchanged; and the
entry the interface lands on is the one the dialog was opened OVER, compared
verbatim. **`history.length` cannot say the last of those** and the first version
of the hold used it: a back MOVES the cursor without removing an entry, so the
number reads the same whether one entry was spent or two — a reading that cannot
come out the other way, which is this wave's fourth instance of that shape.

<sub>`python3 frontend/maquette/harness/back.py` — 17 holds, no violation. Mutation: the `pushLayer` removed; the hold falls naming the page that changed.</sub>

---

**B-247 — a store bump replaces a feature page's nodes, and a write between press and click destroys the click.**
Found on 2026-08-30 during L15's phase 3, by a rule that fell for a reason that had nothing to do
with what it was written for: `page_host.py`'s « a real tap on a command row opens THAT command's
panel » went red while a programmatic `.click()` on the same node opened it perfectly.

**What is really happening.** A store write re-renders every page, and `features/maintenance/page.tsx`
does not keep its DOM nodes across one — measured directly:

    const before = document.querySelector(row);
    window.__store.write({ … });          // any write at all
    // 60 ms later
    before.isSameNode(document.querySelector(row))   // false
    before.isConnected                                // false

A real finger's tap is `pointerdown`, then `pointerup`, then `click`, and the browser dispatches
`click` on a node that is still in the tree. **So any store write in that gap loses the tap
entirely** — no error, no event, the interface simply does nothing. The engine dismisses its boot
hint from a **capture-phase `pointerdown`** handler, which is exactly that gap, so the FIRST tap of
a session on a React page was already being lost while the hint was up. L15 found it because phase
3 briefly routed the message's presence through the store and made the window wider.

**This is B-231's shape one layer down.** L15's P2 holds the CHROME's node identity — the tab bar's
buttons across a page switch and a store bump — and it is scoped to the chrome by name. A PAGE's
rows have the same property and nothing reads it. `harness/persistence.py` is where the equivalent
hold goes, and it is not L15's to write: the repair is in the surfaces, and the surfaces are L14's
(their reduction) and L19's (their producers).

**What L15 did about it, and what it did NOT do.** It stopped depending on it: the message's
presence is `app/message-presence.ts`, its own subscription with its own subscribers — today
exactly one, the action button — so a message no longer re-renders every page. **The defect itself
is untouched and open**: any other store write in that gap still loses a tap.

<sub>`page_host.py` (c-bis) · the identity measurement above, run against `features/maintenance/page.tsx`</sub>

---

**B-246 — the « In flight » row's version arm is defeated by markdown emphasis, in silence.**
Found on 2026-08-30 by writing the row this guard exists to hold, and reading what the guard said
about it. `VERSION_IN_ROW` was `\bversion\s+(\d+\.\d+\.\d+)`. Every row of that table writes
its pull request in bold — « PR **#528** » — so a wave writing the version the same way
(« version **0.98.55** ») produced a cell the pull-request arm read and the version arm did not.

**And the guard exited 0 saying so about neither.** The `named is None` branch returned zero with
no output at all, because a row carrying a pull request and no version is legitimate for a
`no-version-bump` wave. In a log, « this wave declares no version » and « I could not parse the
version » are the same line: none. So the row was held by ONE of two arms and every gate was
green — B-085's species inside the instrument written against B-238, which is itself B-085's
species. **The ninety-ninth and the hundredth of that count belong to this wave** (B-244 is the
other).

**Fixed in #528**: the emphasis markers are skipped rather than matched, so `version 0.98.55`,
`version **0.98.55**` and `version *0.98.55*` are one spelling; and the no-version branch prints
what it read and names the one case in which it is legitimate. Three mutations, each seen and
restored: a bold version is read; a version-less row says so instead of passing mutely; a row
naming a version below `main`'s is still refused.

<sub>`python3 scripts/check-implementation-state.py` — two `[in-flight]` lines where there was one</sub>

---

**B-244 — a contracts-tier guard whose subject only the `docs` filter names runs in no job.**
Found on 2026-08-30 while placing B-142's arm, by reading the workflow the arm was to be placed in.
`frontend/maquette/harness/run.sh`'s contracts tier runs `scripts/check-implementation-state.py`,
which reads `IMPLEMENTATION.md`. That path is named by the **`docs`** filter of
`.github/workflows/ci.yml`. The job that runs the tier — `harness-contracts` — gates every one of
its steps on the **`maquette`** filter, which does not name it. So a pull request touching
`IMPLEMENTATION.md` alone runs that guard **in no job at all** — and a pull request touching that
file alone is exactly what the post-merge gesture IS, which is the gesture the guard was written
to hold.

**And the hold that exists for this shape cannot see it.**
`tests/scripts/test_ci_filter_covers_the_guards.py` asks « is every path this guard declares
matched by at least one filter pattern? ». `docs/**` matches, so it passes. The question it never
asks is « by the filter that gates the job that runs the guard? ». It was written after
`check-mock-seeds.py` and `check-bug-register.py` shipped with the first shape, and both of those
were fixed by adding the path to the **`maquette`** filter — so the hold has only ever been
exercised on cases where the two questions had the same answer. B-085's species: a guard green
because of what it does not read, and it is the ninety-ninth counted.

<sub>`grep -n "IMPLEMENTATION.md" .github/workflows/ci.yml` (under `docs:`) · `sed -n '231,250p' .github/workflows/ci.yml` (every step `if: needs.changes.outputs.maquette == 'true'`)</sub>

---

**B-245 — the pre-paint appearance script compares against the French spellings the engine stopped writing.**
Found on 2026-08-30 while planning L15's Part 9 conversion, by reading both ends of the contract
rather than either alone. `index.html`'s inline script — the one that exists so a chosen appearance
survives a reload **without a flash** — reads:

    var mode = localStorage.getItem("tm-apparence") || "systeme";
    var light = mode === "clair" || (mode === "systeme" && matchMedia(...).matches);

The engine writes `"system"`, `"light"` or `"dark"` to that key (`legacy.js:10596`, from
`data-apparence`, whose values are `APPARENCES = ["system", "light", "dark"]`). **No value the
engine can write matches either literal the script tests.** So a stored « light » paints dark until
the module runs and `applyAppearance` corrects it, and a stored « system » on a light-preference
device does the same — the flash the script exists to prevent, on every reload, for every reader
who has ever touched the control.

**Why nothing caught it.** The two ends are in different files and different languages; a `data-*`
contract's three ends move in one step or the interface half-works in a way no single file reveals
(D4), and this is that, with `localStorage` as the third end. The French literals survived the
English rename because they are compared VALUES, and « it is a value » was accepted as an answer —
the reading `CLAUDE.md` § Language now refuses by name: an appearance mode is a name someone chose.
`check-no-french.py`'s vocabulary arm does not read `index.html`'s inline scripts.

**L15's**, with Part 9's conversion: the two spellings become one, in the engine's, and a rule
reads the attribute in an init script — before the first paint — after a reload.

<sub>`grep -n "tm-apparence" frontend/maquette/design/index.html frontend/maquette/design/src/engine/legacy.js`</sub>

---

**B-152 — the one file § 0 was pointed at was itself stale.**
Found on 2026-08-28 while opening L10. `frontend-architecture.md` lost its per-lot status that same
day (B-148) precisely so that state would exist once, in `IMPLEMENTATION.md`. The « Landed, in
order » row and the « Next » row were both correct. The **« Next action »** paragraph 20 lines
below them was not: it still read « **L09 — The data layer, surface by surface** is the next lot,
and nothing is open on it », two commits after L09 merged.

**This is B-148's shape, one file to the left.** Removing a duplicate state from the plan does not
help if the file that keeps the state carries the same fact twice — a row and a paragraph — and a
wave updates one. The repair is the same repair: the paragraph now says what is IN HAND rather than
re-deriving what is next, so it cannot disagree with the row above it about a lot's status.
Repaired on `feat/maquette-l10`.

**B-218 — B-152's shape a THIRD time, in the row that records the lots.**
Found on 2026-08-29 while closing L10, in the same file and the same table as B-152 and its
second instance. The **« Before it »** row named L07 as the most recent lot before the current
one — three lots after that stopped being true — and it closed on « L05 … archived by **this
pull request** », a phrase whose subject merged weeks earlier and which had been read as current
ever since.

**The mechanism is not staleness, it is a sentence built to accrete.** The archive fact was
written as a growing list — « all three archived; L04 and L05 are archived beside them; L06 and
L07 are archived beside them » — so recording a new lot meant appending a clause, and the wave
that forgot to append left a row that reads as complete and is not. A fact that is true of
EVERY item does not belong in a per-item list: it is now one sentence that no future wave has to
touch.

**And « this pull request » is the deeper defect.** A row that names the PR it was written in
is correct exactly once, in the diff. Afterwards it is a pointer with no referent, and nothing
can detect it, because the phrase stays grammatical. The row now names every lot by its number
and its version and never by a deictic.

**Why no arm guards it, stated rather than left implicit.** The three instances share a cause —
one fact, two places, one wave updating one of them — and the answer L10 already took is
structural: state exists ONCE, in « Landed, in order », which § 0 reads. « Before it » survives
beside it only to carry what that row deliberately omits (the pull request and the version), and
it now carries nothing else. An arm that compared the two rows would be comparing a row to its
own subset. Repaired on `chore/close-l10`.

**B-153 — the demands register cannot describe the thing L10 is about.**
`scripts/compare-contracts.py` COMPUTES `docs/reference/frontend-backend-demands.md` by diffing
paths and operations between `frontend/maquette/contract/openapi.json` (50 paths) and
`frontend/openapi.json` (61). **Neither declares the event stream**, and neither can: OpenAPI does
not describe a WebSocket.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.
>
> **SUPERSEDED the same day**: placed as L16 / L17 / L18 (`frontend-architecture.md` § 4, Phase 5);
> the mapping is written and the arm is **L15's**. This block sits in B-153's entry by the accident
> of where the arbitration was pasted; the placement notes live under B-143, B-144 and B-145.

<sub>`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(len(d['paths']),[k for k in d['paths'] if 'ws' in k or 'event' in k])"` → `50 []`</sub>

So every demand L10 raises about the stream must be filed BY HAND, and the computed register will
go on reporting nothing about it — which reads as « no demands » rather than « out of scope ».
D7 says the contract is the maquette's own artefact; the stream is part of that contract and has
no artefact. Left open: what shape a stream contract should take is an arbitration, not a fix, and
L10 does not take it — it files its demands by hand and says so.

**B-154 — the cache has no way to heal itself, and nothing says so where it matters.**
`lib/query-client.ts` sets `staleTime: Infinity`, `refetchOnWindowFocus: false`,
`refetchOnReconnect: false`, `retry: false`. Each is argued in the file, each is right, and their
SUM is a property no one of the four comments states: **a query that misses an invalidation is
stale for the life of the process.** There is no clock, no focus event and no reconnect refetch
underneath.

Production's `useWsInvalidation` is a per-surface hook and is safe there because 21 `refetchInterval`
sites poll underneath it — a missed event costs 60 seconds. Here it would cost forever. The same
shape, transposed, would be a defect that only ever shows as « the screen was out of date and I do
not know since when ».

L10 designs around it (the relay subscribes once, at boot, never with a surface — D-L10-1). The
entry stays open because the PROPERTY is still undocumented at the one place a future reader meets
it: nothing in `query-client.ts` says the four options together forbid self-healing.

**B-155 — the interface claimed to be live, in the markup, forever.**
`index.html` carried, in the header and as literals:

```html
<span class="ps-dot ps-dot--done …" title="Temps réel connecté">
  <span class="ps-dot__d … bg-success"></span><span class="ps-dot__label …">Connecté</span>
</span>
```

A green dot, the word « Connecté », and a tooltip saying real-time was connected — in a prototype
where nothing connected to anything. **This is §8 of the constitution inverted.** §8 refuses a
« rien ne se passe » with no visible reason; a permanent claim of liveness is worse than silence,
because a reader who checks the indicator is told the screen is current whatever the truth. Nothing
could have contradicted it: the value was not read from anywhere.

It was not a lie anyone told on purpose — it was a drawing of what the state should look like,
which is what a maquette is for. It became a defect the moment a real connection existed to
contradict it. Repaired by L10 phase 4: the same element, in the same place, drawing what the
relay really reports. The connected rendering is byte-identical to what the oracle recorded — the
React portal sits in a `display: contents` wrapper, which generates no box — and the measurement
says so: 2 871 measurements over 87 states, the three new ones added, **zero existing measurement
changed**.

**B-156 — the lever that draws a condition made the control in it dead.**
Found by R92, in the phase that wrote it. A named state reaches `relay-lost` through
`window.__relay.force("lost")`, because `__go` is synchronous and the condition takes a backoff
and a handshake to reach for real. `reconnectNow()` then set the REAL condition back to
`connecting` and connected — and the snapshot went on reporting `lost`, because the override was
still in place. So « Réessayer maintenant », in the very state whose whole purpose is to offer it,
did nothing a reader could see.

**It is the §8 defect sitting inside the §8 feature**, and it is exactly the shape this repository
keeps paying for: an instrument's lever left in the product's path. The repair is also the correct
semantics — an explicit ask clears the override, because a reader who taps « réessayer » has asked
for the real condition, not for the drawn one.

**What is worth keeping is why it was caught**: the hold does not read the control's LABEL, it
clicks it and reads what the connection then is. A hold asserting that a button exists and says
« Réessayer maintenant » would have been green over a dead control.

**B-157 — the hold read when it happened, not what happened.**
R92's first version held « `lost` says what is wrong, and since when » by looking for two things
in the notice: the lead « Les informations affichées datent de », and the ABSENCE of the string
« 4401 ». Both survive a notice that says something entirely different.

**The mutation is what found it, and it found nothing the first time.** Making `lost` draw the
RECONNECTING copy — a real defect, the exact « wrong state » failure the rule names in its own
docstring — left the timestamp and the retry label in place, so the rule reported 20 holds and no
violation. The rule was green over the defect it was written for, which is B-085's shape and
this repository's dominant one: **the seventeenth, eighteenth and every instance since have all
been an instrument reading a neighbour of its subject rather than its subject.**

Repaired by holding the REASON itself, per condition, read off `i18n/fr.json` rather than retyped —
plus the control's label, plus a hold that the two notices differ from each other, so one wrong
entry in the list cannot pass. Re-mutated: both `lost` and `refused` fall, each naming the copy it
should have carried. A second mutation — the notice never rendering at all — falls twelve holds.

**What is worth carrying forward**: « and since when » in the hold's own NAME was the tell. A hold
whose sentence contains « and » is answering two questions, and it will pass whenever the easier
one is true.

**B-158 — the rule walked a journey that cannot lose anything.**
R94 was written to hold B-140's repair, and its mutation — restore
`.screen.open .port` — did not fall. The rule scrolled the library, opened a media sheet and
came back, which is the operator's sentence read literally.

**That journey cannot lose a position.** A screen is `position: absolute` over the page: `#port`
is never unmounted and its height does not change, so the offset survives with or without any
memory at all. Measured with the defect restored: 300 px before, 300 during, 300 after.

What loses it is a TOP-LEVEL PAGE SWITCH — the content is replaced, `#port` becomes a different
length, and the browser clamps the offset to zero. Measured on one build, one selector apart:
back at **0** with `.screen.open .port`, back at **300** with the repair.

**And the journey needs the item's push BEFORE the tab**, which is not a detail: a top-level tab
REPLACES the current entry (D1b), so leaving the page directly consumes the very entry the return
needs — `history.back()` stays put and the rule fails for a reason that is not the defect. It is
also the operator's own journey read properly: **the position is not lost coming back FROM the
item, it is lost coming back from somewhere else.**

The rule now carries the hold that would have caught its own first version: « leaving a page
really loses the offset, so the return means something ». A rule that measures a return without
first establishing that anything was at stake passes with no memory at all.

**B-159 — two instruments split a file on a word whose first use is the import.**
`check-live-relay.py` and `harness/fanout.py` both read each feature's `live.ts` and both needed
to separate the RULES from the EXEMPTIONS. Both split on the string `"Exemptions"`. Its first
occurrence in every one of those files is the TYPE IMPORT on line 1.

**The two failed differently, and that is the whole entry.** The guard's `rules` variable held an
import statement, so it reported **3 refreshed addresses out of 24** — a confident number, printed,
that only a reader comparing it against the tree would ever have questioned. The harness rule read
three exemptions as rules with empty type lists and raised `IndexError` on the first one.

A crash is a better failure than a wrong number, and neither was found by design: the guard's was
found because 3 looked implausible, the rule's because it stopped. Both split on the exemptions
OBJECT now (`^export const \w+LiveExemptions`), and R91 additionally holds that every declared
rule names at least one event — so a rule that ends up empty falls with a sentence rather than a
traceback.

**B-160 to B-178 — what an adversarial review found under a green gate.**
Seven reviewers, one lens each, against 66 rules / 17 guards / an oracle at 2 871 measurements /
`make check` at 10 849 passed. They returned roughly fifty findings; the ones recorded here are
those verified line by line before being acted on. **Five were production defects, and three of them
made the lot's own headline promise false.**

**The shape that produced most of them is one sentence**: the fake transport pushes nothing on its
own (D-L10-4), so **silence is its normal state** — and no rule could tell « quiet because nothing
happened » from « quiet because the link is dead ». `MockSocket` had exactly two ways to end a
connection, both explicit and both delivered. A hang was unrepresentable, so the watchdog defect was
unreachable by construction. **The instrument's design made the defect invisible.**

**B-160** — a half-open socket (sleep, backgrounding, an idle proxy) never closes itself and the
relay listened only for `close`; a hung 101 upgrade fires neither event, and the backoff ladder only
steps on a `close`; and an unsolicited clean 1000 — **which is how this connection ends on every
merge**, because `torrentmate-autodeploy` restarts the web process — was treated as a teardown this
side had asked for. Three routes to a green dot over a frozen screen, in the lot whose §8 promise is
that the interface says when it stops updating. Production had answered for all of it since before
the maquette existed: `useEventStream.ts` carries `WATCHDOG_MS = 45_000` re-armed on every frame and
`CONNECT_TIMEOUT_MS = 10_000`.

**B-165 is the one to keep.** The wave's headline refusal — `DownloadProgressed` « fires per torrent
per tick » — is contradicted by the event's own docstring: only the highest threshold crossed per
pass fires, the mark never regresses, and the thresholds are 25/50/75. **Three emissions for a whole
download.** `DownloadStarted` fires once per info-hash. Meanwhile `ItemProgressed`, which the map
DOES point at a list, fires once per item per step across nine steps. **The volume argument was
applied to the bounded events and not to the unbounded one**, and the card drew « Téléchargement
68 % » frozen for the life of the tab. It was written into the file, the demands register, the
commit message and the pull-request body — five places, one unchecked claim.

**B-167 and B-166 are the same error read from the other end**: two demands asked the backend for
work it had already done. `CircuitBreakerOpened/Closed/HalfOpened` fire on transition and never per
probe, which is exactly what demand §4 asked to be built; `FilmAcquired` and
`SeasonAbsorbedEpisodes` carry `media_ref`, which is exactly what §1 asked for. **Asking for work
already done is worse than asking for nothing**: it reads as a considered gap.

**B-177 is a discipline failure, not a defect**, and it is recorded because it happened twice.
B-107 records the mirror — `git checkout` on an UNTRACKED file is a no-op and a mutation stayed in
the tree. Here `git checkout` on a TRACKED file reverted an uncommitted repair, and the commit that
followed described an attribute the tree did not contain. The rule covering both is one sentence and
was already written down: commit before mutating, always. It was followed for thirteen mutations and
skipped for the fourteenth.

**B-179 — two repairs that were each right and together wrong.**
B-140 taught `activePort()` about `#port`; B-178 stopped `if (remembered)` skipping a stored zero.
Neither is questionable alone. Together they made the scroll memory act across a LAYER boundary,
which it must never do: a drawer, a panel or a sheet opens OVER the page — `#port` keeps its
element, its height and its offset throughout — so opening one stored the page's offset and closing
one wrote that older value back over whatever the operator had scrolled to since.

Measured by `drawer.py`, which is not R94: `18 → 0`, on two layers.

**Neither repair could have been dropped, and neither test could have found it.** R94 walks pages;
`drawer.py` walks layers and had held this property since before L10 existed. The defect lives
exactly on the seam between them, and it was found by the WAVE GATE — the full suite, run before the
merge — which is the one thing in this project's method that reads both.

R94 gains the hold anyway. Two readers of one property is not duplication here: `drawer.py` asks
whether closing a layer disturbs the page, and R94 asks whether the scroll memory knows what a layer
is. The second question is the one that will still make sense when the first rule's subject moves.

**B-180 to B-199 — the second review, and what it says about the first.**
Three reviewers read the twelve commits that repaired round one. Thirty-three findings, six
severe — **and six of the severe ones were in the REPAIRS, not in the code they repaired.** That is
the whole case for a second round, and it was not predicted: the first round's own findings all sat
in code written without a reader, and these sit in code written BY one, in response to one.

**B-180 is the sharpest thing in this register.** The repair for « the relay says connected over a
dead link » introduced `teardownAsked`, a module-level flag set when this side asks for a teardown
and consumed by the close it expects. It is consumed by nothing when `socket` is already `null` —
which is every `reconnectNow()` from `refused` or `lost` — because `close()` on null is a no-op. And
in a REAL browser it is consumed by nothing at all, because `close()` is asynchronous and the close
arrives after the replacement is in place, where the identity guard eats it first. Either way the
flag stays true, and the next unsolicited `1000` — one per deploy — is swallowed. **The condition
stays « connected », with no socket and nothing scheduled: B-160 exactly, through the door of its own
fix.** The repair deletes the flag rather than mending it: nulling the socket before closing makes
the identity guard do the work, per-socket, with nothing to leak.

**B-181 is the same shape on the instrument side.** `reset()` was taught to zero `inFlight` and
`delivering` so a desynchronised page had a way back — and a request already in flight then
decremented past zero. At `-1` both `releaseWaiters` and `quiet()` are false for ever. **A repair for
an accidental desynchronisation created a deterministic and unrecoverable one, on the signal all
2 871 oracle measurements rest on.**

**B-190 is worth its own line.** A comment stated that `fanout.py` had been repaired for the rule
reader's adjacency defect. It had not been. A false claim about a repair is worse than the defect,
because the next reader stops looking — and this register exists because that keeps happening.

**And B-185 closes the loop on the wave's own headline.** Round one found `DownloadProgressed`
refused on a reason its docstring contradicts. Round two found `ProviderCallCompleted` ACCEPTED into
an exemption on a reason its docstring contradicts — it is throttled to one sample per ten seconds
and exists so the web process can track per-provider latency, which is the derivation
`/api/system/dependencies` is built on. The same error, at the other end, in the same wave, after
the first was found. A `because` line is a claim, and a claim nobody checks is a coin toss.

**B-200 to B-217 — the third review, and the finding that ends the recursion.**
One reviewer, on the twelve commits that repaired round two. Nineteen findings, **two critical** —
and neither is a wrong mechanism.

**B-200 is the worst entry in this register.** Commit `435751d3` describes deleting the
`teardownAsked` flag and adding an `open` listener across five paragraphs, and **does not touch
`lib/relay.ts`**. `letGo` existed nowhere. The flag was live. B-160 and B-182 were both recorded
`fixed #512` with neither repair in the tree.

What happened is the whole lesson: the edits were made, the identity-guard mutation ran, and
`git checkout -- lib/relay.ts` reverted the file **to HEAD** — where the repairs were not yet
committed. Everything else in the batch was committed around the hole, under a message describing
work that had just been destroyed. **That is B-177 for the third time in one wave**, each time on
the file the round's own headline finding was about.

And the register said it first: **B-190**, filed two commits earlier, reads « a false claim about a
repair is worse than the defect, because the next reader stops looking ». It sits three paragraphs
below B-180 in the same file, in the same commit that broke it.

**The answer is a tool, not a resolution.** `scripts/mutate.sh` refuses a dirty tree, restores from
the INDEX rather than HEAD, restores on any exit including an interrupt, and refuses an expression
that changes nothing. The rule was already written down and writing it down was not enough; the
failure mode is gone rather than watched. **B-216 and B-217 are its first two uses**: it had a
`pipefail` defect of its own, and it immediately found that the cursor's thaw was measured by
nothing.

**B-201 and B-209 are one shape twice.** A `violations` counter used before its assignment, and a
count made and discarded two lines later. Both survived because the loop that fed them was empty,
and only `make lint` — which reads the code rather than running it — could see either.

**B-210 is the third attempt at one property**, and worth recording as a sequence: leaving the
settle counters alone stranded a desynchronised page for ever; zeroing them let a request still in
flight decrement past zero, where `quiet()` never resolves again — **worse than the defect**;
flooring left the count short, so a later stale landing released the waiters over a request that was
really running — quieter, and still wrong. A generation token settles it. Three repairs, two of them
regressions, on the signal all 2 871 oracle measurements rest on.

**And the second structural gap, which is why B-180 survived two reviews.** `MockSocket.close()`
dispatched its close SYNCHRONOUSLY. A browser never does — the socket enters CLOSING and the event
arrives afterwards, by which time a client that replaced it has installed the replacement. That
asynchrony IS the close-then-replace race, so dispatching synchronously made it unrepresentable: a
client distinguishing a close it asked for from one it did not could be wrong in production and
green in every rule. The fake waits a task now, and the flag's reintroduction falls three holds
where it fell none.

**B-041 — the newest guard is the only one of its family with nothing to re-run.**
`scripts/check-frontend-boundaries.py` is 515 lines and eight arms, and it landed with L04
(#478). Its pull request reports **twelve mutations, each seen red and restored** — the work was
done. What is missing is that it can be done again: there is no file under `tests/scripts/`, so
the proof exists as a sentence in a merged pull request body and nowhere a gate can reach.

Invariant 11 of `docs/reference/frontend-architecture.md` asks that every change land with a rule
that bites, mutation-tested. A mutation performed once in a session satisfies the letter on the
day and nothing afterwards: the arm that stops biting next month falls silent, and silence is
what this register exists to refuse. **The four closest members of the same family all have
theirs** — `test_check_no_french.py`, `test_check_css_tokens.py`, `test_check_markup_contracts.py`,
`test_check_module_size.py`.

Found by the steward's audit of L04, not by a gate — a guard with no test is invisible to every
guard. **Not fixed here**: the office that found it does not carry code (`docs/reference/frontend-steward.md`),
and the test belongs with whoever wrote the eight arms and knows which mutation each one deserves.


**CLOSED by L10-bis, and the entry was half stale and half exactly right.** The test file exists
since #484 and carries 42 tests — so « nothing to re-run » had stopped being true. What was still
true is what the entry actually faulted: those 42 tests are ALL about the addressing arm, its own
docstring says so, and the guard carries **eleven**. **Eight were named by no test at all**,
measured on 2026-08-29. So the row does NOT close as `fixed #484`; the gap was real and it is
named.

**The instrument — `tests/scripts/test_check_frontend_boundaries_arms.py`.** A meta-assertion that
every `arm_*` reachable from the entry point is exercised, against a CEILING on how many are not.
A ceiling, not a floor: adding an arm without a test raises the count and is refused, which is the
opposite shape from a floor set at the current value. It also NAMES the three it still allows, so a
fresh uncovered arm cannot take a retired one's place in silence.

**Five arms were given their mutation in the same commit** — cycles, layering, typing,
duplicate-import, mocks — and the ceiling fell from 8 to 3. The three left are named with the
reason each is more than a one-line fixture.

**A defect in the TEST HARNESS came out of writing it**: copying the sources to `tmp/src` breaks
three imports that climb above the tree (`../../../fixture-projections.json`), `arm_cycles` reports
three unresolved imports, and **the GREEN case fails** — so every mutation would have been measured
against a red baseline and proved nothing. The depth is mirrored now, and the green case is asserted
first, before any mutation.

<sub>mutation — add a new `arm_freshly_added` with no test: the assertion falls NAMING it, not
merely counting. Neuter `arm_typing` to `return 0`: its own mutation falls. Restored →
`10 passed`</sub>
**B-042 — a stray process holds a port nothing in the repository claims.**
A `python3 -m http.server` listens on **8900** on the operator's machine, working directory
`/private/tmp/tm-a11y-probe`, and **no file in this repository mentions that port**. It is the
residue of an accessibility probe launched by hand during L03. Harmless in itself — 9.6 MB — and
reported by the L04 wave, which correctly declined to repair something that was not its own.

It is written here because that report lived only in a merged pull request body, which is the
same defect as B-041 read from the other end: a finding recorded where nothing re-reads it has
not been recorded. The port the harness actually uses is **8899**; `run.sh` starts it and reuses
it deliberately, and that one is not this.

**CLOSED by L10-bis, and it was closed with no closure written — which is the most direct
violation of the very rule this wave hardened.** The status line read `fixed #516` while the body
below it was byte-identical to `main`: nothing said what had been established, or how, or by whom.
An adversarial reviewer found it. The rule amended in this wave's first commit says a fix requires
an instrument that RAN; a status that says « fixed » over an unchanged body is the shape that rule
exists to refuse, and it appeared inside the wave that wrote it.

What actually establishes it, run on the operator's machine on 2026-08-29 — this wave runs there,
which is why the entry was takeable at all:

```
$ lsof -nP -iTCP:8900 -sTCP:LISTEN        # nothing listens
$ ls -la /private/tmp/tm-a11y-probe       # No such file or directory
```

Both are gone. The wave did not kill the process — it had already gone, to a reboot or to the
orphan killer — so the honest closure is « no longer true », not « repaired ». **The port that IS
listening is 8899**, `frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte`, reparented
to init and three days old: that is the server `run.sh` starts and reuses deliberately, named in
the paragraph above as not being this one. It stays.

What outlives the process is the entry itself, and that half was never about the port: a finding
recorded only in a merged pull request body has not been recorded. That is why B-042 was written
down, and writing it down is what made it checkable three waves later.

**B-043 to B-048 — what L05 left on `main`, and why they are here rather than only in a phase file.**
All six were found by an adversarial review that did not write the code, and reproduced by the L05
wave itself before it stopped. Each is written up in full — with the command that establishes it and
what its repair must hold — in `docs/archive/features/maquette-l05/plan/phase-08-pr-fixes-cycle-1.md`, which
is on `main`. **That file is the source of truth and these entries are the index into it**; a phase
plan is archived with its wave, and a defect that outlives the wave has to be findable after that.
The four blocking ones (B-043 to B-046) were known before the merge and merged anyway, so they are
on `main` now.

- **B-043** — a deep address to a media sheet opens the screen but leaves `state.page = 404`
  underneath, so Back reads « Adresse introuvable ». It is a **regression** against the tree before
  the wave, on the wave's own headline feature, and R75 stays green because the screen covers the
  frame.
- **B-044** — a 404's address recomposes to `/`, so a mistyped link becomes a real page on the Back
  after a cold load. R69's fourth hold measures only the cold load and cannot see it.
- **B-045** — `?panel=follows`, with no colon, is accepted as a genre because the separator search
  returns −1, and an unknown subject fabricates a media that does not exist, labelled « à jour » and
  now reachable from a URL.
- **B-046** — the fallback port moved onto the one `switchover.py` uses. That script swallows its
  bind error, so a port collision would surface as R73 reporting a broken sign-in — a rule giving a
  confident wrong reason, which is worse than a rule that fails.
- **B-047** — the navigation-failure flag those sign-in guards are meant to raise is not raised by
  them, and **no rule reads it** — not after the wave and not before it. That is why they passed: a
  flag nothing reads cannot fail. Same family as B-038 and B-039.
- **B-048** — the ninth arm of `check-frontend-boundaries.py` reports clean over a tree with
  `addresses.ts` deleted (`0 dial(s), 0 page(s)`). A guard that stays green on a tree it cannot read
  is the shape its own neighbour's docstring names. Same family as B-041.

All six are repaired on `fix/maquette-l05` and land with **#484**, each with the hold that falls
when it comes back.

**B-049 — a rule class reads live operator data, and a cron makes it red on schedule.**
The follow fixture mirrors the operator's `acquire.db`; the watcher cron that resolves searches
moves that database independently of any wave (twice inside 24 h during the L05 repair). The
rule reads the mismatch as a defect and regenerating the fixture only holds until the next cron
run. Not a code defect — a class question: whether a rule that reads live data belongs in a gate
at all, and if so, on what cadence it re-syncs. Raised by the L05 repair wave (PR #484's open
points), not decided there. **Recurred during L06** (`content.py` reddened by the
operator's search cron; fixture regenerated from `acquire.db` again, same class, same
non-fix) — the second occurrence inside two waves, and the question is still not decided.


**CLOSED by L10-bis. The question of class is settled and, for the first time, ARMED.**

**The rule**: a hold that reads the operator's live databases may run in the WAVE gate, on the
machine where those databases exist, and may never be in the per-pull-request `--contracts` tier.
That was already the practice — `arrivals.py` is out of `CONTRACTS` with the reason written beside
it — and it was held by nothing at all. It was corrected by hand once; a second rule joining the
tier with a `sqlite3.connect` in it would have gone unnoticed exactly as the first did.

**The arm** is `check-maquette-unit-tests.py`'s second subject, and the two belong together because
both ask « does the runner run what it says it runs? ». It reads `CONTRACTS=(…)` out of `run.sh`
and refuses any member whose source names a `.db` path or opens a connection — a text question with
a text answer, which is the whole of the disqualifying property. **It runs even where the
maquette's dependencies are absent**: it reads two files and needs neither node nor a browser, so
skipping it beside the suite would have made it the kind of check that is only ever green.

**The cadence half.** The three rules that read live data — `arrivals.py`, `content.py`,
`library_load.py` — were run twice, separated by the full rule suite, and both passes were green:
**24, 27 and 8 holds, no violation**, at 14:29 and again after the suite. What makes them stable is
not luck: they assert SHAPE and AGREEMENT — that two tabs say the same thing, that a card carries
what the row carries — and never a count a cron can move. A rule that pinned a number would drift
whatever tier it sat in, and that is the real answer to « at what cadence does it re-sync »: it
does not need to, because it does not read a number.

<sub>mutation — put `arrivals.py` back at the head of `CONTRACTS`, which is B-049's own history:
the arm falls naming the file and the reason, « 12 rule(s) in the per-pull-request tier, 1 of them
disqualified ». Rename the declaration so it cannot be parsed: it refuses rather than reading the
tier as empty. Restored → `11 rule(s) in the per-pull-request tier, none reading a live
database`</sub>
**B-050 — the guard that watches module size has itself grown past comfortable.**
`scripts/check-frontend-boundaries.py` reached 883 lines during the L05 repair (nine arms). The
module-size ratchet (invariant 6) does not exempt guard scripts. Split before the next arm lands,
not as an emergency — the file is not yet over the hard ceiling, only past the point where one
more addition should pause and ask.

**The 883 was the figure on the day it was written, and it was read as the state for two waves.**
Re-measured on `main` at `2a3f2576`: **921** non-blank lines, 79 from the hard ceiling, not 117.
The entry above is kept as it was written — this paragraph is the correction, because a figure
silently overwritten teaches nothing about the figure that will go stale next. Whoever closes
this bug re-runs the command rather than trusting either number.

<sub>`python3 scripts/check-module-size.py --root scripts`</sub>

**B-059 — the token guard is 58 lines from the ceiling, with 14 of L07's 16 phases to run.**
`scripts/check-css-tokens.py` was **815** non-blank lines on `main` and is **942** on
`feat/maquette-l07` at `dfb6ee42` — +13 in phase 1, +114 in phase 2 and its follow-up fix. The
hard ceiling is 1 000, it is enforced over `scripts/` (`check-module-size.py --root scripts`, in
`make check` and in CI's `guards` job), and exceeding it exits 1. Fourteen phases remain, and
**phase 4 plans another arm inside this very file** — `--arm motion-classes`, which the phase
document argues is not optional because nothing else in the repository would catch a
`duration-<n>` off the scale.

**The plan does not name this anywhere**: no phase document, neither `DESIGN.md` nor
`plan/INDEX.md`, mentions module size — the file is cited only as a command to run green. So the
wave is on course to redden a gate through a channel its own plan never forecast, and the phase
that trips it will look like the phase at fault rather than the accumulation. Not this steward's
to repair: reported so the split is planned rather than discovered at a red CI. The measurement
belongs to the wave; what belongs here is that it was never measured.

**IT HAPPENED, AND EXACTLY WHERE THIS ENTRY SAID IT WOULD** — at phase 4, the phase that adds
`--arm motion-classes` to this same file. The wave carried **1 016** non-blank lines at
`3e1f1ce5` and **1 022** at `2634de86`, two commits over a ceiling that exits 1, and the guard
that caught it was the repository's own — `check-module-size.py --root scripts`, in `make check`
and in the `guards` job — not anything the wave had planned. `777ec798` repaired it: the sign-in
gate's arm left for `scripts/csstokens_login.py` on a SUBJECT split, the four shared patterns
kept in one module so the first copy to drift cannot do so in silence, and the file is **851**
lines on the wave's tip.

Closed as `fixed #494` rather than `closed`: it is repaired on the branch, not on `main`. Rule 3
is met by the gate that already exists and already bit — the mutation was not staged, it was
lived.

**#494 merged on 2026-08-25 (squash `5fdbfc9a`), so « not on `main` » stopped being true the
moment it did.** The status column keeps `fixed #494` — that is what the entries of #484 do once
their pull request lands, and `closed` means the operator confirmed. What this paragraph corrects
is the SENTENCE, because a sentence that outlives its subject is read as current by the next
session. Two further things moved with the merge, and one of them is a warning rather than a footnote.
The command below names `origin/feat/maquette-l07`, a branch deleted at the merge — measure the
file instead. **And the file is 905 lines on `main`, not the 851 the split left it at**: the
adversarial review before the merge widened the scale arm, corrected two messages and added a
served-page hold to the login arm, so **95 lines of the 149 the split bought back are already
spent**. This entry's mechanism is therefore live, not historical: the next arm to land in this
file crosses again. **What this entry did NOT get right** is its own forecast of the deadline: it read « phase
3 » from a two-phase slope, and the crossing came at phase 4. The mechanism was right, the
extrapolation was decoration — a rate measured over two points is a rate that has not been
measured.

<sub>`for c in $(git log --format=%h --reverse origin/main..origin/feat/maquette-l07); do printf '%s %s\n' "$c" "$(git show $c:scripts/check-css-tokens.py | grep -c '[^[:space:]]')"; done`</sub>

**B-051 — a feature-owned reader escapes the boundaries arm.**
`toFollows()` carries its page identity in a query parameter, inside a feature file the ninth
arm's inline-`validateSearch` reader does not reach (it reads route files, not every function
that shapes a query). D1's rule — path carries identity, query carries state — is not enforced
here by any guard; only readable by a human diff.


**CLOSED by L10-bis, and the defect was worse than the entry said.** `toFollows()` navigated to
**`/`** — not to `/acquisition` — with `search: { page: "acq", tab: "now" }`. So the identity was in
the query AND the path named the root, which the boot SETTLES onto `/acquisition` with a replace:
the destination was right only by way of a redirect. `/acquisition` declares
`SearchParams = { tab?: string }` and carries no `page` at all, which is what the address model has
said all along. It now reads `to: "/acquisition", search: { tab: "now" }`.

**The instrument — the ninth arm reaches NAVIGATIONS, not only declarations.** Everything it read
before was `routes/`, where an address is DECLARED; D1 is broken just as easily where one is
CONSTRUCTED. It reads the `search:` object of every `go(…)`/`navigate(…)` outside `routes/` and the
dying engine — **22 of them** — and the count is printed, because a reader that finds none reports
the same word as one that read the tree.

**The arm was written and it matched NOTHING, and the run is what said so.** Its pattern held a
literal **backspace character** where `\b` was meant: a heredoc turned the escape into `\x08`, so
`\x08(?:go|navigate)` matched no text in any file. Every gate stayed green, the arm reported « 0
violations » over 116 files, and the mutation passed. It was found by instrumenting the loop and
reading the line back **as bytes** — `repr()` on the source, not a look at the diff, because a
backspace is invisible in a diff. That is CLAUDE.md's « the tool is not the proof » with the tool
being a heredoc.

**A second instrument holds the other end**: R96 gained a hold on where the action LANDS, because
the destination moved and a static arm cannot see a redirect.

<sub>mutation — put `to: "/"` and `page: "acq"` back: the ARM falls naming
`features/acquisition/add-screen.tsx:140`, and R96 falls with « it landed on
'/?page=acq&tab=now' ». Both ends, from either side. Restored → `22 navigation(s) outside routes/,
0 violation(s)` · `11 rules EXECUTED — no violation`</sub>
**B-052 — a synthesised follow panel can label a film « Série ».**
Found during the same review that produced B-045: an entry fabricated by `knownMedium`'s now-
narrowed match can still carry the show-shaped label on a film-shaped title, when the synthesis
path is reached at all. Cosmetic on the surface, but it is the same fabrication class as B-045 —
recorded so it is not rediscovered as a new defect.

**B-053 and B-054 — two behaviours changed inside the L05 repair wave, not separately arbitrated.**
Recorded so they are revisitable rather than silently permanent: (B-053) a panel's layer entry
is now taken by a tab tap that lands on the same layer, where before the tap and the panel were
independent; (B-054) `data-go="acq"` no longer forces the acquisition page onto its « now » tab
on arrival, which some journeys relied on implicitly. Neither broke a hold — both are readings
the repair wave settled on to close its own defects, not product decisions taken with the
operator. Either may be the right call; neither has been asked.

**B-055 — the a11y floor certifies one of two themes.** `a11y.py` drives the 83 named
states in the default (dark) theme only; no `data-theme` handling exists anywhere in the
harness. Found during L06 phase 5 by a sub-agent who drove `data-theme="light"` by hand and
re-ran axe — not by the gate, which has no arm that would. After phase 5's own repairs (the
light `--primary-foreground` at 2.14:1 across 19 consumers, `--primary` as a label at 2.16:1
on three sites), a full light-theme sweep still reads **154 occurrences over 115 rows in 34
states** — dominated by `--primary` used as a label colour on a light surface (~40 sites),
the `warning`/`success`/`info` tones repeating the same fill-versus-label confusion, and one
`.tsx` inline re-skin (`add-screen.tsx:185-191`). A remediation campaign, not a call-site fix;
needs its own design and plan (`docs/archive/features/maquette-l06/drafts/a11y-floor-measures-one-theme.md`
carries the full inventory). Not decided here: whether the audit runs both themes (doubling
its runtime) or a lighter arm audits palette pairs alone in light.


**CLOSED by L10-bis. The measurement is ARMED; the 154 are not remediated, and that split is the
entry's own.**

**THE OPEN QUESTION IS DECIDED: the tier drives BOTH themes, and the lighter palette-pair arm was
refused for this file's own reason.** `a11y.py`'s header argues that a house rule proves the list of
criteria someone wrote into it and nothing else — it is why axe-core is here at all, and why
`check-no-french.py` was turned around rather than lengthened. A palette-pair arm would have been
exactly that rule, on exactly the theme nobody was measuring. Driving axe twice costs a second pass
of ~25 s and buys the same body of criteria on both themes.

**The light theme is MEASURED AND RECORDED, not enforced**, which is this file's own earlier
handling of contrast (D-L03-4: measured, written to a file of its own, kept out of the floor,
because « not measured » would have read as « no problem »). The dark floor stays a HARD ZERO.
`a11y-light-debt.json` is a RATCHET — read by `--check`, unlike `a11y-debt.json`, and it says so:
a debt file a gate reads is a tolerance, and a tolerance that only tightens is a ratchet.

**MEASURED TODAY: 166, and all 166 are `color-contrast`.** L06's hand count was 154; the tree has
moved since, and 166 is what it reads now rather than what a document says. Remediating them is a
campaign with its own design and plan; what is held meanwhile is that nothing is ADDED.

**Two things the arming needed that are not obvious.** The theme is re-applied AFTER every
`window.__go`, because several scenarios re-render the shell and put the appearance back — a theme
set once before the loop is a theme the audit believes it is measuring. And the attribute is
read back at the end: an audit that silently measured the dark theme twice would report the dark
theme's zero and call it two themes clean, which is this very defect arriving by a new road.

<sub>mutation — `--color-foreground` broken in the LIGHT palette only: light goes 166 → **1162** and
the tier FAILS, while dark stays at **0 violation(s)**. That is the entry's own test, and before
this wave the same mutation was invisible to every instrument. Restored → `a11y: 87 states, 0
violation(s)` · `a11y[light]: 166 violation(s) … against a ceiling of 166`</sub>
**B-056 — a French name sits where no arm reads it.** `refonte.html` names a keyframe
`splashremplit` (used by `.splashbar i`). A keyframe name is a name someone chose — code,
under the English-names rule — and none of `check-no-french.py`'s fourteen arms reads
`@keyframes` names, so the gate is green over it. Found during L06 sub-phase 1.3, not fixed:
outside the lot's letter, which folds values onto a scale and refuses any naming change
beyond D-L06-4's publisher move. Fixing it needs both ends moved in one step (the
`@keyframes` declaration and every `animation`/`animation-name` reading it) through the
rename discipline, plus a fifteenth arm so the next one does not sit the same way.

**B-057 — a hold that measures nothing reads as a hold that passed.** `audit2.py:65`'s
`measure()` returns silently when its selector finds nothing. `.resbtn` is one of five
contexts R12 names, and it is absent from the state the rule visits (`acq-add-results`), so
only four primaries are ever measured while the rule believes it holds five. The exact family
of hole `type_scale.py` was written to refuse — a gate proves what it READS. Found while
repairing R12's pinned size during L06; not fixed there, a rule-shape change outside the
lot's letter. Fix: either the rule visits a state that paints `.resbtn`, or `measure()`
refuses an empty selection the way `type_scale.py` does; mutation-tested either way (hide the
element, watch the rule fall).


**CLOSED by L10-bis, and it was BOTH of the two fixes the entry offered, because one alone would
have been a lie.** `measure()` now records a MISS instead of returning silently, and R12 prints
« N of 5 context(s) measured ». **And the fifth context had MOVED**: `.resbtn` returns zero elements
in `acq-add-results` — a search result's primary action is not on the card any more, it is in the
PANEL the card opens. So refusing the empty selection alone would have left R12 permanently red
about a selector that is simply obsolete; re-pointing it alone would have left the silence for the
next context to move.

**The new selector is a `data-part`, never a style class** — `[data-act^="add:"]` inside the panel,
reached the way a reader reaches it, by opening the first result.

<sub>mutation — point the fifth context back at `.resbtn`: R12 prints « 4 of 5 context(s)
measured » and raises « R12 context measured by nothing », one violation, where the same state
before the repair reported nothing at all. Restored → `Primary button geometry — 5 of 5 context(s)
measured` · `TOTAL, second pass: 0 violations · 13/13 rules executed`</sub>
**B-058 — the AI-attribution check can fire on prose that quotes what it looks for.**
`hooks/commit-msg`'s second alternative, `generated with .*claude`, carries no `^` anchor —
unlike the other two real-trailer alternatives — so it matches the phrase ANYWHERE in the
message, including inside a sentence documenting the rule itself. Found writing the commit
that fixed B-058's sibling: a French sentence quoting « generated with claude » in guillemets,
to explain what the hook forbids, tripped the hook it was describing. Not fixed here — the two
real alternatives are anchored to a line start on purpose (a trailer, not prose), and giving
this one the same anchor needs its own mutation test to confirm it still catches a genuine
footer while releasing a quoting sentence; a same-commit reflex fix on a compliance-relevant
guard is exactly the haste this register exists to slow down.


**CLOSED by L10-bis, and NOT as a reflex — the entry's own warning was the instruction.** Measured
first: a real footer fell, a real `Co-Authored-By:` trailer fell, prose QUOTING that trailer passed,
and prose describing the ban was REFUSED. The two alternatives that were already anchored never had
the problem, which is what proves the anchor is the answer rather than a weaker pattern.

**BOTH unanchored alternatives were anchored, not one.** `generated with .*claude` was the one the
entry named; a bare `🤖` had exactly the same shape three characters later, and repairing one and
leaving the other is the defect this repository paid for twice in the same week (B-208's `try`,
A-1's import branch). Fixing only the named half would have left the emoji refusing the same
paragraph.

**What is no longer caught, stated rather than discovered**: an attribution buried mid-line inside a
sentence. That is not a trailer, no tool emits it, and refusing it is what made this hook refuse
English.

**The instrument is a TEST, not the run that proved it.** `tests/scripts/test_commit_msg_hook.py`
executes the hook as a process — the file git runs, not a Python transcription — over five refusals
and three acceptances. The five refusals are the half a future loosening breaks first, and this
pattern has been loosened once already.

<sub>mutation, both ways and both seen red — restore the unanchored pattern: « prose describing the
footer » fails, which is B-058 reproduced. Delete the `claude-session:` alternative: « a
Claude-Session trailer » fails, which is the compliance half. Restored → `8 passed`</sub>
**B-060 — the tool `CLAUDE.md` mandates for renames could not perform one, and said so as success.**
`scripts/rename-identifiers.py` is the only sanctioned way to rename an identifier in this
repository. Asked to move the CSS custom property `--card` to `--color-card` it touched **zero
files** and printed « 0 file(s) touched » — its normal success line. The cause is one character
class: every mode anchored its pattern on `\b`, and a word boundary cannot precede `--`, so the
name was unmatchable by construction. A tool that cannot fail loudly is a tool whose report means
nothing; this one was believed twice before the diff was read, which is why `CLAUDE.md` already
says the tool is not the proof. **Repaired in #494** (L07 phase 3): a custom-property mode anchored
on the FORM (`--name`) rather than on the word, with five tests under
`tests/scripts/test_rename_identifiers.py`.
<sub>`python3 scripts/rename-identifiers.py --help` names the mode · the five tests are `pytest tests/scripts/test_rename_identifiers.py -k propert`</sub>

**B-061 — the oracle measures an element, so a pseudo-element that stopped existing is invisible to it.**
The recorded oracle reads a bounding rectangle plus 19 computed properties **of the element
itself**. A `::after` that stops being painted changes neither, so the oracle stays green — and
correctly, by its own contract. L07 phase 15 produced the measured example: the media sheet's
legibility gradient was written across four concatenated string literals, Tailwind reads
candidates out of RAW TEXT, no single literal carried the whole class name, and the utility was
never generated — leaving the hero's text resting on the bare image, the one thing that rule
exists to forbid. **R26 caught it**, because R26 reads `getComputedStyle(bg, "::after")`.

**What #494 repaired is the concatenation, not the blindness.** The hold that refuses a split
class name is the sixth of `scripts/check-tailwind-confinement.py` — **not** of R26, which is the
rule that CAUGHT the defect and is unchanged. A literal ending in a space is a clean break between
class names; a literal ending in anything else continues a name into the next. Mutation-tested by
cutting `bg-muted` in half. ⚠ That hold then read six files and was blind to the three holding the
shared vocabulary, which is its own entry in this wave's story and is repaired in the same pull
request. The oracle's own blind spot
stands: **no pseudo-element is among its 2 739 measurements**, and the next one to disappear will
disappear silently unless a rule happens to read it. Not fixed, and not fixable by a call-site
change — it is a question about the oracle's contract (whether a named region may declare a
pseudo-element to measure), and it belongs with whoever owns that contract.


**Arbitrated 2026-08-25: the oracle is NOT widened.** It keeps its contract — it measures
elements — and the limit is written into D8 of `frontend-architecture.md`, where it is read
before anyone relies on the instrument. A pseudo-element carrying a function is covered by a
named rule instead, the way R26 covers this one. A surface that leans on a functional
pseudo-element with no such rule is the defect; the oracle is not.

**B-062 — a class name emitted by a `cva()` base string wears no `class=`, and three readers looked for `class=`.**
The markup-contract readers learn what a class NAME is from the sites that emit one, and they
knew three such sites: `class="…"` in a document, `className="…"` in a component, and the engine's
string writes. A fourth arrived with L07: `cva("fback flex items-center …")` emits `fback` as
surely as `className="fback"` ever did, and carries no attribute for the readers to find. So the
vocabulary the guards police silently stopped covering every surface this wave converted.
**Repaired in #494** (`777ec798`): both readers take the first token of a `cva` base string — the
identity class, by this wave's convention — and both match `*variants.ts` as a FAMILY rather than
one exact name, because the vocabulary split into a directory the same day and a reader pinned to
one filename would have gone quiet again.

**B-063 — the maquette's gate tiers do not include the repository's own guards, and three invariant breaches lived across phases.**
`frontend/maquette/harness/run.sh` has a cheap tier and a full tier, and the wave's cadence runs
the cheap one per phase and the full one once before the merge. **Neither tier runs `make check`**,
which is where `scripts/check-frontend-boundaries.py`, the module-size ceiling and the French guard
live. So invariant 7 of `docs/reference/frontend-architecture.md` (« `ui/` never imports a feature.
Two features never import each other ») was broken **three times** across L07 and stayed broken
until the pre-merge `make check`: Maintenance and Système reached into Configuration for the topic
row, and the release screen reached into Acquisition for the result count. Two files passed a hard
line ceiling in the same interval.

**The three breaches are repaired in #494** (`777ec798` — both shared pieces are in `ui/` now).
**The cadence is not**, and it is the durable half: a wave can convert eleven surfaces without any
repository guard reading the tree once. The question is a cadence one, like B-049's — whether the
per-phase tier gains a `make check`, or the boundaries guard joins the contracts tier — and it is
not this wave's to settle alone.


**Arbitrated 2026-08-25: the repository's CHEAP guards join the per-phase tier.** Not `make
check` entire — 10 763 tests cost fourteen minutes and the operator's cadence ruling of
2026-08-24 stands for the expensive half. What joins are the guards that run in seconds and read
what a phase touches: `check-frontend-boundaries.py`, `check-module-size.py` over its four roots,
and `check-no-french.py`. An invariant breach is then attributable to the phase that commits it,
instead of to a fifteen-phase interval.

**B-064 — R72's mutation recipe names an environment variable that nothing reads, so following it proves nothing.**
`frontend/maquette/regions.json`'s R72 text says « `R72_SANS_BUILD=1` skips the build gate ALONE ».
`frontend/maquette/harness/shell.py` reads **`R72_SKIP_BUILD`**. The rename landed with #446 and
the rule's prose was not moved with it. The consequence is not cosmetic: `shell.py` rebuilds
before it reads, so an operator following the recorded recipe — apply a mutation to
`dist/index.html`, re-run with the documented variable — has the mutation **erased by the rebuild**
and reads a green run as « the mutation was survived ». A recipe that cannot fail certifies the
rule it was written to test. Pre-existing on `main` since #446; found while reading R72 to decide
whether it could be renegotiated. Fix: move the name, and re-run the recorded mutation with the
real variable so the recipe is seen to bite once.
<sub>`grep -rn 'R72_SANS_BUILD\|R72_SKIP_BUILD' --include='*.py' --include='*.json' frontend | grep -v node_modules`</sub>

**B-065 — a duplicated source tree is tracked, read by nothing, and has begun to drift.**
`frontend/maquette/design/frontend/maquette/design/src/` holds **11 tracked files** — nine
`features/*/reference.ts`, `lib/engine-drawing.ts`, `lib/engine-queue.ts` — a copy of the real
tree nested under its own path. It landed with **#478** (L04, « les frontières et l'arbre »), the
wave that moved every file, and has been on `main` since. Nothing reads it: `tsconfig.json`'s
`include` is `["src"]`, and every harness and script reader roots at `design/src`. So it does not
lie to a gate — it is dead weight.

**It has started to diverge, which is what makes it worth an entry rather than a `git rm`.** Three
of the eleven now differ from their live counterparts: `features/media/reference.ts` is missing
the six lines §11's address contract added (`titleForProviderId`, `addressIdsFor`), and
`features/maintenance/reference.ts` and `features/system/reference.ts` carry an import shape their
originals no longer have. A stale copy of a contract file, sitting at a plausible path, is
something a future search will find and read. Fix is a deletion — outside L07's letter, and it
should carry the one thing that would refuse the next one: a guard that no path under
`design/` repeats `design/` .
<sub>`git ls-files 'frontend/maquette/design/frontend' | wc -l` → 11 · `git log --oneline --diff-filter=A -- 'frontend/maquette/design/frontend/**'` → the commit that added them</sub>

**B-066 — the scale arm can now see two declarations, and neither is its to fix.**
Widening the arm to the shipped stylesheets (#494) exposed what it had never read: `.skip-link`
declares `padding: 10px 16px` and `border-radius: 0 0 10px 10px`, and `.visually-hidden` declares
`margin: -1px`. All three came out of the prototype's HARNESS block — never under the scale rule —
and entered the shipped base layer when that block was cut, so they are debt this wave inherited
rather than debt it wrote. Two of the four found were repaired in the same commit because the fix
was free: `body`'s `font-size: 14px` IS `--text-5`, and `--spacing-0` was a step declared one line
outside the markers.

**These two are not free.** The spacing ramp reads 14 then 18 — there is no 16 — and the radius
ramp reads 8 then 12, so honouring the scale means CHANGING what a keyboard user sees when the
skip link takes focus. That is a design call. `margin: -1px` is not a design constant at all: it
is the one-pixel clip idiom, and no step of any ramp would do. Both are named exemptions in
`scripts/check-css-tokens.py`'s `EXEMPTIONS`, each with its reason, which is what lets the arm go
green over what it CAN answer for — and this entry exists so the exemption does not become the
answer.
<sub>`python3 scripts/check-css-tokens.py --arm scale` → 0, with the two selectors skipped by name</sub>

**B-067 — a variant that can be edited and changes nothing.**
`src/styles/legacy.css` is deliberately UNLAYERED so it wins over `@layer utilities` — the right
call for markup the engine draws, and the wave says so in the file. It also lands on markup
COMPONENTS draw: seven shared identity anchors carry both a residue rule and a typed variant —
`.empty`/`emptyNote`, `.surferr`/`surfaceError`, `.panel`/`factsPanel`, `.pip`/`statusDot`,
`.sec`/`section`, `.sechead`/`sectionHead`, and the sheet's `open` branches. Unlayered normal
declarations beat every cascade layer whatever the specificity, so on those elements the utility
loses.

**Nothing renders wrong today**, and the wave recorded that plainly rather than counting the
surfaces as converted: the declarations are identical term for term, and the oracle says so. The
defect is the one nobody is holding — **the day a variant DRIFTS from the rule it shadows,
editing it changes nothing on screen and no gate speaks.** TypeScript passes, the build passes,
`make check` passes, the rendering does not move. The shape of the fix is a guard cross-checking
each variant's identity anchor against the residue's selectors and refusing a divergence; the
alternative is scoping the residue to the engine's instances, which is L13's work.


**Arbitrated 2026-08-25: the guard is built now, and it dies with D10.** It reads the seven shared
identity anchors, compares each typed variant against the residue rule that shadows it, and
refuses a divergence. Scoping the residue to the engine's instances stays L13's work — waiting for
it would leave the trap open across L08 through L12. The guard is recorded in D10, so it is
removed in the same move as the decision that makes it necessary.

**B-068 — the wave's prose drifted in forty small places, and the inventory is kept.**
An adversarial doc-accuracy review over #494 re-measured every figure the wave asserts. **Most
are right** — 2 739 measurements, 530 rules, 4 136 lines, 30 colours, 8 shadows, 55 rules, 936
bytes leaked, and D-L07-1's six line ranges are exact. What is not right is written up, item by
item, in `docs/archive/features/maquette-l07/drafts/documentation-drift-inventory.md`, which travels with
the wave into `docs/archive/features/`. **That file is the source and this entry is the index**,
the same arrangement B-043 to B-048 use.

Three families, and they fail differently. **Counts** that no longer measure what they say (nine,
plus two pre-existing). **Comments detached from their subject** — an orphaned table comment, a
docblock about a factory sitting atop a barrel, five orphaned comments in the residue, and
`harness.css` citing two tools deleted in 2026-08-20 and **re-committed into a living source file
by this wave**. And **§ Language**: `CLAUDE.md` says maquette and harness comments carry no
reference to a session, a phase or a dated decision, and this wave added eighteen « CONVERTED
(L07 phase N) » banners plus a dozen more. The durable half of each is already written; the phase
number is what has to go, and a rename campaign over comments is its own wave's work, not a
tail-of-session sweep. **What #494 repaired instead** is every sentence that was actually FALSE
rather than merely dated — those are in its own commit, because a wrong sentence is read as
current and a phase number is only noise.

**B-069 — the residue's licence to exist points at a document about to be archived.**
`src/styles/legacy.css` justifies itself with « D-L07-5, arbitrated by the operator on
2026-08-24 », and D-L07-5 is defined in `docs/archive/features/maquette-l07/DESIGN.md` and nowhere else.
That directory was archived when #494 landed, so **the only definition of the decision keeping a
2 470-line stylesheet alive is now in frozen history** — and `docs/archive/` is never revised. Its sibling deferral (the
prototype fragment, ACC-14/ACC-19) already has a durable home in
`docs/reference/frontend-architecture.md` § L13. This one needs the same: the decision moves
there, and the stylesheet's header cites the durable address.


**Arbitrated 2026-08-25: D-L07-5 becomes D10** of `docs/reference/frontend-architecture.md`, a
full § 2 decision rather than a note inside a lot's description — a decision keeping 2 357
non-blank lines alive carries the same standing as those that structure the plan. (« 2 470 » is
the figure L07 recorded; re-measured at 2 511 lines, 2 357 non-blank, and corrected in `legacy.css`
and in D10 where a reader acts on it.) `legacy.css`'s header cites
that address, and the archived DESIGN stays what it is: the record of where the decision was
taken.

**B-070 — the rename tool passed the soft ceiling, and it is the same family as B-050.**
`scripts/rename-identifiers.py` reads **829 non-blank lines** against a soft warning at 800 and a
hard ceiling at 1 000. It stood at 716 before L07, 786 after the custom-property mode landed, and
crossed on the no-op refusal (#494). `check-module-size.py` warns and exits 0, so nothing is
blocked — which is exactly what B-050 says about its own file: split before the next addition,
not as an emergency, and the moment to pause is the crossing rather than the ceiling. The subject
line is visible: the mapping validation, the span readers and the three apply modes are three
subjects behind one entry point.
<sub>`python3 scripts/check-module-size.py --root scripts`</sub>

**B-071 — a toggle for an overlay that was deleted.**

> **Widened by B-081 (operator, 2026-08-25), and this entry understated it.** « Reporting success
> for a class nothing reads » reads as though the notes were simply gone. They are not: the DEFAULT
> flipped, so they are shown on every screen and cannot be hidden. And the oracle masks them while
> measuring, so the instrument never sees what the operator is judging. B-081 carries the
> mechanism and the fix for the visible half; this entry keeps the third end, inside the dying
> engine, for L13.
D-L07-1 deleted the design-notes overlay with BLOCK 1, correctly: `:root.notes .note` was harness
CSS and it must not ship. `src/engine/legacy.js:11414-11419` still toggles the `notes` class,
still flips `aria-pressed`, and still toasts « Notes de conception affichées. » — reporting
success for a class nothing reads. A contract with three ends and two of them gone, which is the
shape `CLAUDE.md` names about `data-*` names: the markup that emits it, the code that reads it,
and the rules that tap it move in ONE step. Left here rather than fixed because the third end is
inside the dying engine, where an edit is L13's to make; it is written down so L13 does not
rediscover it as a live feature.

**B-072 — the command that proves the surface partition no longer runs.**
`docs/archive/features/maquette-l07/DESIGN.md:281` names `build-surface-manifest.py` as the builder that
asserts the partition of BLOCK 2's 530 rules into 38 surfaces is TOTAL. Run today it raises
`IndexError` at line 79: it reads `refonte.html`, which is 120 lines and holds no rule. The
committed `plan/surface-manifest.json` is correct — it was built when the fragment still carried
the stylesheet — so nothing downstream is wrong. What is gone is the ability to re-derive it: a
proof that ran once and cannot run again is a sentence in a merged pull request, which is
precisely what B-041 says from the other end.

**B-036 — the English campaign missed two state ids, and no arm reads them.**
`window.__states()` returns **`system-panne`** and **`acq-follows-groupe`**. Both are NAMED STATE
IDS, which `CLAUDE.md` §Language settles explicitly: « a NAMED STATE id is a name someone chose
(`window.__go("acq-now-idle")`), and 51 of the maquette's 82 were French until 2026-08-20 because
« it is a value » was accepted as an answer ». These two are survivors of that campaign
(#455/#456).

Found while driving the 82 states for L01, not by a guard — which is the point worth recording:
`scripts/check-no-french.py` has fourteen arms and none of them reads the state table, so the
count went from 51 to 2 and then stopped moving with nothing to notice. A rule with no arm is a
sentence in a file.

**Not fixed here, deliberately.** A state id has more than three ends — `states.js`, every
harness script that drives it, `regions.json`'s records, and this repository's dated documents —
and L01 is the lot that must not move anything: its whole value is a reference recorded against
an unchanged prototype. Renaming them would land in the same wave as the instrument that would
have to prove the rename. **Its fix belongs to the wave after this one, and it should carry the
missing arm rather than only the two renames.**


**CLOSED by L10-bis, and the arm is the deliverable — the entry said so.** Both ids renamed
through `scripts/rename-identifiers.py --values`: `acq-follows-groupe` → `acq-follows-group`,
`system-panne` → `system-outage`.

**THE TOOL REPORTED « 5 file(s) touched » AND LEFT A LIVE END BEHIND.** `harness/audit2.py` still
read `'acq-follows-groupe'` inside a JavaScript array written within a Python string — `--values`
moves a WHOLE quoted value, and that one is embedded in a larger literal. Found by re-reading the
diff rather than the count, which is the rule CLAUDE.md writes after two corruptions found the same
way. Six ends per id: the engine's table, `oracle-reference.json`, `a11y-contrast.json`,
`a11y-debt.json`, and two harness rules.

**The arm — `scripts/nofrench_states.py`, arm 15 of `check-no-french.py`.** It asks the
vocabulary's question of every named-state id, and eleven English words the table already used —
`android`, `arr`, `boolean`, `degraded`, `exhausted`, `followsheet`, `outage`, `pwa`,
`reconnecting`, `signin`, `structure` — entered `code-vocabulary.txt` one line each, which is that
file's own stated point.

**ITS CORPUS IS CROSS-CHECKED, AND THE DISAGREEMENT IS BLOCKING**, because a scan for a quoted
literal at the head of a bracket reads **77 of the 87**. Ten are written in shapes it never sees:
one single-line entry (`["signin", …]`) and a family of nine built from a template
(`` `settings-field-${genre}` ``). The second reader is `oracle-reference.json` — the states the
recorded oracle actually drove — and **an id it measured that the parser cannot reach is refused**,
never printed. That is B-208's shape used deliberately, and it is the direction that means
blindness; the other direction is a state added and not yet re-recorded, which the oracle reports
itself.

**The first expansion over-generated and would have failed on names nobody wrote.** Sweeping the
file for `["word", "` invented `settings-field-signin` out of a single-line entry three hundred
lines away. The members are matched by walking the receiver array's bracket BACKWARDS now, and the
two readers agree at 87 and 87.

<sub>mutation — restore `system-panne`: the arm falls naming it. Rename the single-line entry to
`connexion`: it falls naming `connexion`. Rename the generated family to `reglages-champ-${genre}`:
it falls nine times. **Remove the single-line reader from the arm itself**: the CROSS-CHECK falls —
« the recorded oracle measured 1 state(s) this arm could not parse — signin » — which is the arm
proving it cannot go quiet. Restored → `15 arms … no violation`, `87 state identifiers / engine` ·
oracle unchanged at 3 deliberate divergences, no measurement moved</sub>
**B-034 and B-035 were found running `make check` on Linux, and they are NOT one defect.**
Both fail identically on `origin/main` with no local change — a worktree at `9632491c` reproduces
them — so neither belongs to the work that found them. They are written as two because they have
two causes, and merging them would let one hide behind the other's fix (the same reason B-013 to
B-015 are three).

They surfaced with eleven others that had a single mundane cause: **`rsync` was absent from the
container**. Installing it took the same files from `14 failed` to `173 passed, 3 failed`. That
is worth recording on its own — eleven red tests said nothing about the code, and the honest
first reading of them was wrong.

**B-034 — the two `TestQuickMode` holds.** Both die on
`[c for c in scandir_calls if c.startswith(mount)]` with `AttributeError: 'int' object has no
attribute 'startswith'`, so the recorder caught a call made with a file DESCRIPTOR rather than a
path. `_walker` cannot be the source: `_list_dir_entries` is the only `scandir` site in the whole
`scanner/` package (ACC-08) and it passes `dir_abs`. The diagnosis — **stated as a diagnosis, not
as a confirmed cause** — is that patching `personalscraper.indexer.scanner._walker.os.scandir`
patches the SHARED `os` module rather than a name private to that module, so any other caller
active inside the `with` block is recorded too. Which foreign callers run there differs by
platform and by installed dependencies, which is why the operator's machine and CI do not see it.
If that holds, the defect is in the test's reach, not in the walker.

**B-035 — `TestRestoreMergeBackup::test_continues_on_per_file_error`.** `backup.exists()` is
False: the run left no `.merge_backup` beside the destination. Not root-caused, and not guessed
at — per rule 1 of this file, it is written down before any work starts.

**Neither is dismissed as « environment ».** That reasoning was put and rejected here on
2026-08-20: *if it were true on main, CI would not have passed* — and a gate that is green by
accident of the environment is not a gate. What makes these different from that precedent is
narrower and it is measured: **CI never runs this suite on `main`** (the workflow triggers on
`pull_request` only), so « CI passed on main » is not evidence that exists. The suite's last real
execution is the run of #465.

**B-033 was seen ONCE, and is written down rather than guessed at.** `make test` reported
`tests/web/test_maintenance_panels.py::TestLocksRoute::test_locks_tmp_orphans` failed on worker
`gw7`; the same test passes alone and the very next full run was 10 742 green. Its assertion is
`len(orphans) == 3` — an EXACT count over what a background sweep reports — and the `test_config`
fixture is function-scoped with its own `tmp_path`, so a sibling test cannot be leaking into its
staging directory. The cause is therefore not the obvious one, and the obvious fix (count only
this test's own paths) would weaken a hold whose failure nobody has explained. Reported before
any work starts, per rule 1 of this file.

**B-031 and B-032 are ONE defect class, and it is the eighth and ninth instance of it.**
A `data-*` value, the handler that forwards it verbatim into a store field, and the readers that
compare that field are a THREE-ENDED contract, and nothing tied them together. `data-phase="prete"`
wrote a phase no reader knows, so the retry button on every « Impossible de charger… » surface
wrote a value nothing renders and the error screen never cleared. `data-hscen="reel"`/`"charge"`
wrote scenario names whose readers compare `real`/`loaded`, so « État réel du 10 août » landed on
the loaded branch and both dial buttons showed unpressed.

Both PRE-DATE the English rename that exposed them, both were found by an adversarial review, and
neither was visible to the 50-rule suite, to a reading of the diff, or to a sweep for French
strings — they are not French-versus-English, they are markup-versus-reader. Fixed with
`scripts/check-markup-contracts.py`, which asks the only question that catches the class: **does
anything understand what this button writes?** Mutation-proven on both.

**B-018 was written down as a regression from B-016, and that was wrong.** It has two ways in, one
of which is older than this work — the correction is recorded here rather than quietly amended,
because a register that only ever gets more accurate teaches nothing about how it goes wrong.

B-013 to B-015 arrived as **one** report about the navigation drawer. They are written as three
because a fix closes only with a rule that bites, and three symptoms with three causes need three
rules — merging them would let two hide behind the one that got fixed.

B-017 was reported by nobody. The mutation proving R65 bites found it, which is the whole reason
mutations are run against a rule rather than trusted to be green.

**B-030 was found by a RULE that could not reach it before.** R1 (« every tappable poster leads
to a filled-in sheet », `harness/audit.py`) drives named states, and every state that drew the
library drew its FIRST page — twenty-four rows, all of whose sheets are complete. The wave that
migrated the Médiathèque added a state for the load-failure surface, which drew two pages, and R1
fired immediately. Measured over the whole library: **87 of 345 titles have a sheet with no genre
(`g`) and no cast**, and none of them is in the first twenty-four — « Chouette, un jeu
d'enfants », « Andrew The Problem Prince », « Furies » and eighty-four more. It is reachable in
the app by scrolling past the first page and tapping any of their posters: the sheet opens, and
it has nothing to say. The defect is in the embedded DATA, not in the drawing, so closing it is a
scraping question rather than a rendering one — which is why it is written down rather than
fixed in a conversion wave. The state that found it was narrowed back to one page, so the suite
measures the surface it was added for; R1 remains the rule that bites the day the data is filled
in or the state widened.

**B-024 to B-029 arrived from an adversarial code review of commit `3e66fa66` (#434), not from
the operator** — same standing as B-017: found by tooling, written down before anyone walks into
them. None is reproduced on a device yet; each entry below records the walk that would.

- **B-024** — `data-go` (refonte.html ~17901) closes up to three layers but settles exactly ONE
  history entry (`__pont.remplacer` overwrites only the top). With two layer entries buried
  (screen over screen — the case the block's own comment claims to handle — or sheet over
  screen), one Back after the navigation lands on a stale `{layer}` entry and answers a
  legitimate Back with the « Encore un retour pour quitter » toast; a second Back exits the app.
  **Latent, non atteignable** — re-measured post-SP4a, walked control by control: the DOM carries
  exactly five `[data-go]` producers, no more. Four render only into
  page-body `#view` content (`viewAcquisition`, `viewArrivals`, `viewIntrouvable`, `viewSystem`)
  — and that census now spans TWO files, because Système moved to the shell: three producers
  remain in the fragment (`refonte.html` 12020, 12532, 12631) and the fourth is
  `design/src/pages/system.tsx`'s own `data-go="arr"` button, which renders into the SAME `#view`
  through the page host and is covered by a layer exactly as it was;
  `#view` sits under every layer (`.screen` z-45, `.sheet` z-47 over `.topbar` z-40), so each is
  covered — and therefore untappable — the instant any layer is open, meaning zero layers, let
  alone two, ever precede their tap. The fifth is the user sheet's « Profil et préférences »
  (`cible:{go:"profil"}`, the only dynamic producer in the whole file — confirmed by grep) — its
  only trigger is the header avatar (`data-sheet="utilisateur"`), itself in `.topbar` and so
  covered the same way whenever a screen is already open (measured: `elementFromPoint` at the
  avatar's coordinates resolves to `.screenbar` inside `#screen`, not the avatar, and a click there
  opens nothing). One layer (the sheet itself) is therefore the most that can ever precede this
  control's tap; a fresh-boot walk confirms `history.length` is unchanged before and after tapping
  it, matching the single-entry case the fix already covers. No live call path stacks a second
  screen either: `openScreen`'s `dejaOuvert` branch (pushed layer on top of an already-open screen)
  exists in code, and `data-fiche` (18336-18349) is its one UNGUARDED trigger — when no sheet is
  open (`couche` false) it calls `openFiche(fiche)` directly, with no `closeScreen()` first, so a
  `[data-fiche]` element tapped from inside an already-open screen WOULD stack a second one. But
  no `[data-fiche]` element is ever rendered inside a screen today: its three producers —
  `cardHTML`'s poster (11578), `tileHTML`'s tile (15395), the Découvrir deck's poster (15855) —
  are called only from page-list/grid/deck builders (11555-15987), never from `openFiche`,
  `openResolve`, or `openReleases` (39527-40337, the only functions that build screen content);
  `openResolve`'s own cards (`releaseCardHTML`, 11613-11637) are marked `data-nonmedia` and carry
  `data-resolve`, not `data-fiche`, by design ("no medium here yet"). The sheet-to-screen half of
  `data-fiche` is guarded (`couche` true closes the sheet first, 18342-18344), and `data-refiche`
  reopens the SAME key (`memeEcran`, no new layer). The comment still overclaims — it is true of
  the DOM, not of history — but no reachable walk buries two entries under a `[data-go]` tap
  today. Fix shape unchanged: one loop, one entry per closed layer.
  **Final status (SP4b, task 6): latent, held by the Task-1 measurement.** No close-block fix
  applied — the entry-count law would be exercised on a control that cannot reach it. The
  handler's own comment no longer claims to handle a buried second entry (corrected to name the
  single-entry assumption, `refonte.html` ~17861); the intro comment's second example (the add
  screen's « Voir mes suivis ») is removed too — it left `data-go` in the interim (see B-025).
  Settles with the ownership law when `data-go` itself migrates to the shell (SP4d): if a sixth
  producer, or a new path to the existing five, can ever reach a layer, the entry-count law
  (`__pont.regler(n)`, sketched but unapplied here) is owed then, not before.

  **CLOSED by L10-bis, and the phase name above is dead.** SP4d ran — its two waves are recorded
  in `IMPLEMENTATION.md` as #447 and #448 — and `data-go` did NOT migrate to the shell in it. The
  phase that owns that migration today is **L13**, where the dying engine is subtracted. A
  forward-looking sentence pointing at a phase that has already passed reads as pending to every
  session after it, and this one has read that way since 2026-08-20.

  **THIS IS ONE OF THE TWO CLOSURES WITH NO INSTRUMENT, and rule 3's amendment obliges naming
  which one cannot and why.** No guard here greps prose. `check-no-french.py` reads names, not
  citations; `check-bug-register.py` reads the index, not the bodies; the harness reads a browser.
  A phase name inside a paragraph of English is text nothing in this repository parses. What was
  done instead is this correction, written beside the original rather than over it (§ 7.1).

  **The lead the entry offered was checked and is already spent.** « Five such sentences were found
  in the plan » — `docs/reference/frontend-architecture.md` carries none today; a later wave
  repaired them. The two survivors are in `product-intent.md` and are HISTORICAL (« ce qui a été
  livré de SP5 avant cette règle — SP5a »), which is a record and not a forecast, and that document
  is the operator's. An arm refusing a dead phase name would therefore have to tell a record from a
  forecast, which is a judgement about a sentence's tense and not a thing to grep. Recorded as
  measured rather than built, so the next wave inherits the measurement and not the suggestion.

  ⚠ The citation `refonte.html ~17861` in the paragraph above is stale by the same species: that
  file is **7 057 bytes** today and holds no such line. Left as written, because § 7.1 corrects
  beside and never over — and named here so a reader does not go looking.
- **B-025** — harness `bugs.py` check 10b stops at the landing (`10b. « Voir mes suivis » lands`)
  and never presses Back; only the sheet half (9b) is guarded. The `remplacer`-on-screen half of
  the fix — exactly what B-024 concerns — can regress without a single check falling.
  **Fixed (SP4b, task 6).** The footer itself left `data-go` between the review and this walk
  (Task 5 migrated « Voir mes suivis » to `AddScreen`'s own `toFollows`, a router-owned
  `remplacer:true` — same "the layer's entry becomes the arrival" semantics `data-go`'s own
  comment describes), so the regression this entry names now lives there, not in the shared
  handler; the guard follows it. `bugs.py` 10b gained a Back press, `10c`: after the footer
  lands, one real Back must leave `/ajout` in a single hop (no buried `layer` entry, `page`
  still `acq`) — mutation-verified by mutating `toFollows`'s `remplacer:true` to `false` at
  source (`10c` fell, naming the still-buried `/ajout`), rebuilt, then restored (`git diff`
  empty), rebuilt, re-run green.
- **B-026** — the `data-go` handler's outer `try { … } catch (error) {}` (house pattern from
  `data-navgo`) silences a `remplacer` failure: the page renders the destination while URL and
  history still describe the layer — a silent violation of the DOIT-10 claim that « the URL and
  the interface never disagree », with nothing logged.
  **Fixed (SP4b, task 6).** Three swallows now `console.error` and raise
  `window.__navEchec = true`, a probe published next to the other probe flags
  (the precedent set by the unnamed-subject set, which the shell publishes as `window.__settingLabels.unnamedSubjects`) for the harness to read: the `data-go` handler's own tail,
  `noterLeChemin`'s (`refonte.html` ~16561, the write door every OTHER navigation goes
  through), and `data-navgo`'s own tail (`refonte.html` ~18188-18194) — the pattern's
  ORIGIN, byte-identical in shape and risk, and left silent in the first pass (a review
  finding on the same commit). Mutation-verified for both call sites: with the intact
  catch, stubbing `__pont.remplacer` to throw (page context) and driving « Profil et
  préférences » from the user sheet (`data-go`, the one control that can fire `remplacer`
  from a layer) or the drawer's own first entry (`data-navgo`, opened through its handle)
  raised the probe (`true`) in both cases; a plain tap left it `false` either way (no false
  positive). Reverting either catch to silent and repeating the SAME forced throw on that
  path left the probe `false` — the hold falls without the fix, confirming it bites — then
  each catch was restored in turn.
  **Known residual, not fixed, deliberate.** The three silent catches in
  `window.__demarrerMoteur` (`refonte.html` ~40699-40721: the opening `remplacer`, the
  guard `remplacer`, the boot `noter`) stay silent. Boot-time, pre-render — a failure there
  leaves the splash/boot state visible rather than a rendered interface disagreeing with
  its URL, which is the lower-risk failure mode DOIT-10 is not written against. Settles
  when the legacy engine itself dies (SP4-end), not before.
  **The residual is closed on `fix/maquette-l05` (#484), and its justification had stopped being
  true.** « Boot-time, pre-render » no longer describes those three writes: `render()` runs above
  the first of them and `__loadingDone()` between the first and the second, so a refusal leaves a
  fully drawn interface standing on an address nothing wrote — the failure mode DOIT-10 IS written
  against, not the lower-risk one. The third is also the entry an addressed panel's layer is
  stacked on, so losing it makes the first Back spend the exit guard instead. All three now log in
  English and raise `window.__navEchec`, and R69 reads the flag on a cold load whose boot write is
  refused from outside the page.
  **A fourth swallow, found by the SP4b final review and fixed, not left residual.**
  `shell.tsx`'s `openPanel` wrapped `window.__pont.coucher("sheet")` in the same
  silent `try { … } catch {}`, inherited from the legacy `openSheet`'s own guard around this
  call. Unlike the boot-time residual above, `window.__pont` is assigned synchronously at
  this module's top level, before any producer can call `ouvrir` — there is no window where
  the bridge is genuinely absent, so the swallow's own justification ("a bridge that is not
  there yet") no longer held. A throw here means the write itself failed, and the store had
  already flushed the panel open: exactly the URL/UI disagreement DOIT-10 forbids, silently.
  Wired to `console.error` + `window.__navEchec = true`, the same pattern as the other three.
- **B-027** — `resync.py` extracts a follow's title with the FIRST `t: "…"` match anywhere in
  the object and counts braces with no string-awareness. An object whose first `X: "…"` key is
  not the title, or a title containing `{`/`}`, silently skips or — worse — rewrites the WRONG
  follow's counter. Holds today only by convention (all 12 objects start with `t:`), asserted
  nowhere.
  **Fixed.** The title is now read anchored on the object's own opening brace
  (`re.match(r'\s*\{\s*t:\s*"((?:[^"\\]|\\.)*)"', obj)`): the title must be the FIRST key or the
  script RAISES, naming the object's head. **Mutation** (proof executed, `task-7-report.md`, re-run
  after the script's messages moved to English): a scratch FOLLOWS fragment whose sole object opens
  on `x:` instead of `t:` → `resync.py` raises
  `ValueError: FOLLOWS object whose first key is not "t": …` quoting the object, rather than
  silently skipping it.
- **B-028** — `resync.py` cannot say a title went unmatched: a FOLLOWS title absent from the
  DB reads exactly like « already in sync », prints `0 correction(s)` and exits 0. Especially
  live once vo-title (#435) changes which spelling a follow carries — the operator running the
  documented remedy gets silence instead of « 4 of 12 titles never looked up ».
  **Fixed.** Every FOLLOWS title with no matching row in `acquire.db` is now collected during the
  same pass and, if any exist, `resync.py` prints
  `nothing written — N title(s) never looked up: …` naming each and exits 1 — `0 correction(s)` is
  only ever printed once every title matched. **Mutation** (proof executed, re-run after the
  script's messages moved to English): a copy of `refonte.html` with one real FOLLOWS title
  (« Kyma, l'onde mystérieuse ») misspelled → exit 1,
  `nothing written — 1 title(s) never looked up: Kyma, l'onde MISSPELLED`. **The mutation must be
  applied INSIDE the `const FOLLOWS = [` block**: that same title string also appears in the
  embedded référentiel earlier in the file, so a first-match replace edits the référentiel, leaves
  FOLLOWS intact, and the run prints `0 correction(s)` — which reads exactly like a guard that no
  longer bites.
- **B-029** — `content.py`'s counter rule tests `f"{n} recherche" in s["facts"]`: « 1 recherche » is
  a substring of « 11 recherches », so whenever the real count is a suffix of the embedded one the
  drift the rule exists to name is never named.
  **Fixed.** The hold now compares numbers with a word boundary
  (`re.search(rf"\b{r['searches']}\s+recherche", s["facts"])`), so a digit that merely ENDS the
  embedded count no longer satisfies it. **Mutation** (proof executed against the built prototype on
  8899): a copy of `refonte.html` with « Kyma, l'onde mystérieuse »'s embedded `recherches` set to
  17 while `acquire.db` still holds 7 → the rule falls:
  `FAIL the numbers come from acquire.db, not from the mock-up — ["Kyma, l'onde mystérieuse : « …
17 recherches » vs 7"]`, where the pre-fix substring check
  (`"7 recherche" in "… 17 recherches"`) would have stayed silently green. The searched word
  `recherche` is the French the prototype RENDERS — it stays French; only the hold's own label and
  the verdict word moved to English.

---

## B-021 — Signing out leaves the bottom panel on top

**Reported** 1× (2026-08-15). **Status** `to confirm` — `harness/bugs.py` checks 9/9b.

**What the operator sees.** From the user panel, reach the profile, sign out: the panel never
seems to leave the foreground.

**What actually happens**, measured on the journey: tapping « Profil et préférences » in the
user sheet changed the page to `?page=profil` UNDER the sheet and left the sheet on top
(`elementFromPoint` said `sheet`). Everything tapped from there happens under a stuck panel.
The sign-out itself, measured alone, closes the sheet and lands on the entry screen — the
stuck panel comes from the step BEFORE it.

**Why.** The `data-go` handler predates the layer rules: it navigated (`state.page`, `render`,
`noterLeChemin`) without closing the layer it may sit in, and pushed its nav entry ON TOP of
the layer's buried history entry. The drawer already had the settled pattern for exactly this
(`data-navgo`): close every layer WITHOUT touching history, and the destination TAKES the
layer's entry through `remplacer` — an unwind-then-push would race, the asynchronous pop
landing after the push.

**The fix.** The `data-go` handler now follows the drawer's pattern: `fermerTiroir(true)`,
`closeSheet(true)`, screen stack emptied then `closeScreen(true)`, render, then `remplacer`
when a layer entry was on top, `noterLeChemin` otherwise.

**Why no rule caught it.** `bugs.py` check 3 proves the BOTTOM BAR closes layers on
navigation (`data-page` calls `hideLayers()`), and every driven state reaches pages directly —
nothing walked a `data-go` control INSIDE a layer.

**Mutation.** Removing `closeSheet(true)` from the block → checks 9 and 9b fall naming the
stuck sheet. Pushing instead of replacing → check 9b alone falls (back no longer reaches the
page one stood on before the sheet). Both executed, both restored.

**Observation recorded, not fixed here**: `data-page` (bottom bar) hides layers but does not
settle their buried history entries either — masked because the DOM closes. Unreported, left
open deliberately; SP4's ownership law re-founds this bookkeeping.

---

## B-022 — « Voir mes suivis » in the add search is inert

**Reported** 1× (2026-08-15). **Status** `to confirm` — `harness/bugs.py` checks 10/10b.

**What the operator sees.** On the add-media screen, after adding a media, the « Voir mes
suivis → » footer link answers a tap with nothing.

**What actually happens.** Same defect as B-021, other layer: the footer's `data-go="acq"`
changed the page to Acquisition UNDER the still-open add screen. The page did move — behind
a screen that never left, which reads as « nothing happened ».

**The fix.** The shared `data-go` fix above. The journey test walks the real path: results →
card body → panel → « Ajouter » (confirming the replace dialog when the result is owned) →
footer appears → tap → the screen leaves and Acquisition renders.

**Mutation.** Covered by the B-021 mutations — the same handler, measured on this journey by
checks 10/10b.

---

**B-219 — the brief a wave was launched with existed in no place a second machine could reach.**
An agent was launched on 2026-08-29 to execute L10-bis. It started, looked for the two documents its
own brief announced — `amendement-regle-3.md` and `l10-bis-fermetures.md` — and found them **in
neither the repository, nor the home directory, nor any scratchpad**. They existed only in a remote
session's `/tmp`, delivered to the operator as conversation attachments.

**Six waves had been briefed the same way and none had failed**, because the operator carried each
file by hand: L07, L07-bis, L08, L08-bis, L09 and L10. The seventh was handed to an agent directly,
and the arrangement met the only condition it could not satisfy.

**The cost is not the lost minutes.** An agent that discovers mid-task that its own specification
does not exist has learned that the office directing it does not guarantee what it hands over — and
that office's whole authority is that its statements can be checked rather than believed.

**It is also the shape this register counts most, turned on its author.** « A fact that exists once
cannot go stale » was the ruling that removed the duplicated lot status from the plan (B-148); here a
fact existed once, in the one place that does not survive a container being reclaimed. And the reason
each wave's reasoning has to be reconstructed from its squashed pull-request body — a body this
office measured, three days later, to be wrong by a factor of five — is that the brief explaining it
was never written anywhere else.

**Repaired by the rule rather than by the act**: `docs/reference/frontend-steward.md` now states that
a brief a wave will execute is committed and pushed under `docs/features/<codename>/` before the
agent is called, and that the call names its path in the repository. The briefs for L10-bis and
L10-ter land with this entry.

<sub>the six that were never committed: `git log --diff-filter=A --name-only -- 'docs/features/*/BRIEF.md'` returns nothing before this change</sub>

---

## Requested evolutions (not defects — recorded here so they are not lost)

- **E-001 — Médiathèque sort inversion** (2026-08-15): every sort type must be reversible —
  A→Z and Z→A each way. An evolution, so it is maquette-first: drawn and measured in the
  prototype before any conversion work touches it. **Arbitrated by the operator
  (2026-08-15): folded into the Médiathèque wave of SP4**, where that page is drawn into
  its final component.
  **Drawn, and held by a rule of its own (R78, `harness/library_sort.py`).** The panel offers
  the six directions explicitly, each carrying its own NAME — « Ajout récent » / « Ajout
  ancien », « A → Z » / « Z → A », « Les plus incomplets » / « Les plus complets » — rather
  than an arrow bolted onto a shared one; exactly one is marked; the control on the count line
  reads the direction in force; and the reversal is measured on the ROWS DRAWN, over a library
  narrowed until the whole set fits on one page (the list draws 24 of 260, so reversing the
  order and taking the first page again gives the last rows of the other end — right, and not
  the reverse of what was drawn). MUTATION: the direction stops being applied, in the served
  copy alone — the three reversal holds fall, each naming its sort, while every hold about the
  NAMES stays green. **The ruling against the alternative — tapping the already-chosen sort to
  flip it — is recorded in `regions.json` under R78 and is open to contest**: it halves the
  rows but is invisible, and a row that reads « A → Z » and answers Z → A is the opposite of
  showing what the machine will do.

- **E-002 — the menu closes on a leftward swipe from its right edge** (2026-08-28, dictated by
  the operator as a hand-drawn mark on a screenshot). **The band**: ~67 px measured, **72 px**
  written as an arbitrary value — a grip zone is not a spacing step and the scale stops at 24 px.
  It ends exactly on the drawer's right edge, and is measured FROM that edge rather than from the
  viewport, because the drawer is `max-w-[86%]` and on a narrow frame its edge is not at 288.

  **Zero lines were added to the dying engine, which is D5's whole point.**
  `design/index.html` declares `<aside id="drawer">` EMPTY and the engine fills, opens and closes
  it; writing the gesture there would be an ADDITION where only subtraction is allowed. So
  `app/drawer-gesture.ts` installs against the node as it stands — the posture
  `installFocusManager()` takes one line above it in `app/shell.tsx`. Closing goes through
  `window.__closeLayers?.()`, the seam the sheet's scrim already calls: a second closing path
  would be a second navigation history.

  **AND THE FIRST IMPLEMENTATION WAS WRONG IN THE EXACT WAY THE PLAN PREDICTS.** Written with
  pointer events alone, it **passed under a real mouse and did nothing at all under a real touch
  stream**: `pointerdown`, ONE `pointermove`, then `pointercancel`, while the `touchmove` events
  kept arriving for the same finger. Neither `touch-action: pan-y` nor `touch-none` on the drawer
  changed it — measured both ways. `setPointerCapture` did not save it either.

  **The engine had already paid for this and written it down**, in `legacy.js` about its own
  pull-to-refresh: « a pointer-only implementation therefore works under synthetic events, which
  are never cancelled, and does nothing at all under a real thumb ». The finger is read from TOUCH
  events and everything else from pointer events, one implementation serving both. The touch
  listeners are passive, like the engine's.

  **This is the whole argument for exercise 1.** A synthetic mouse would have declared this
  gesture working. Only a real touch stream over `Input.dispatchTouchEvent` saw it.

- **E-003 — the sheet closes on a downward swipe from a widened top edge** (2026-08-28, same
  mark). Drag-to-dismiss already worked, from the 22 px `#sheetgrab` alone; the operator asked for
  four times that. **The band is 88 px and OVERLAYS the content rather than pushing it**:
  `#sheetin` is capped at `max-h-[78%]` and 88 px in flow would cost the poster and the title
  their scrolling. **What that costs was MEASURED, not assumed** — across all five sheet states
  (`sheet-journey`, `sheet-more`, `sheet-user`, `followsheet-complete`, `followsheet-gaps`)
  nothing interactive sits in the top 88 px, so no tap is swallowed.

  **The band stops at the sheet's edge.** The 12 px overhang the mark suggested was put to the
  operator before coding and arbitrated away on 2026-08-29: those pixels are the scrim, the scrim
  closes on TAP, and a tap that becomes a failed drag closes nothing.

  **One condition, not a gesture engine**: at `#sheetin.scrollTop === 0` a downward drag is a
  dismissal; anywhere else it is a scroll. A sheet that opens is always at the top, so the first
  gesture is always a dismissal and the content keeps its scrolling. The full press/drag/scroll
  arbitration remains L12's. The band's `touch-action` and `pointer-events` ride that condition as
  CLASSES, because the compositor reads them when the finger lands and not during the gesture.

**The instrument for both — `harness/gestures.py` (R98), fourteen holds.** It drives a REAL touch
stream over the DevTools Protocol AND a real mouse on the same build, because they are not two
spellings of one exercise: the drawer's first implementation passed one and failed the other.

**The third exercise was the operator's, and it is DONE.** A pass by hand, with a finger, on the
device: **confirmed by the operator on 2026-08-29**, both gestures, including the condition that
decides between them — a downward swipe in the sheet's top band dismisses at the top of the
content and SCROLLS anywhere else. No script could stand in for it: `pointercancel` is delivered
by a compositor deciding it wants the gesture, and neither driver above is that compositor.
**Both entries move from `to confirm` to confirmed.**

The device is not recorded, because the operator did not name one and this file does not hold
figures nobody measured. What the pass establishes is the compositor's behaviour on the hardware
the operator uses; a second device would be a second pass, not a correction of this one.

<sub>mutations, all seen red and restored — return both bands to their previous size (`BAND = 0`,
`h-[22px]`): three holds fall, one per gesture plus the mouse. **Remove the TOUCH path and keep the
pointer one: the touch hold falls and the MOUSE hold stays green**, which is the asymmetry the plan
names and the best proof the two exercises are not two of the same. Close on `pointercancel`
instead of restoring: the cancel hold falls alone. Restored → `14 rules EXECUTED — no violation`, re-derived by running the rule rather than
by copying the figure beside it: « eleven » was written before the three holds an adversarial
review added, and it is the same class of stale count this wave corrected in six other places</sub>

<sub>and what they cost the oracle: **nothing**, verified rather than believed — 87 states x 34
regions, the only divergences being `screen-add/body`'s three, which are B-222's</sub>

- **Ouvert opérateur — the 240 ms dead delay on `data-next`** (2026-08-16, SP4c; the attribute
  was named `data-suivante` when this was written and #455 renamed it): the
  "Passer à la suivante" action in the arbitration screen still carries a `setTimeout(240)`
  before its resolution call. It was once a cover for the legacy screen closing under it;
  the screen migrated to a router-owned route in SP4c and no longer plays a close animation
  there, so the delay is now a frozen quarter-second with nothing left for it to cover. Kept
  byte-identical rather than removed — the binding constraint on this wave was
  behaviour-preserving migration, not a UX pass — so this is flagged, not fixed. The operator
  may want it dropped.

---

## B-013 — The drawer's entries lead nowhere

**Reported** 2× — the second time this surface has been reported inert. **Status** `to confirm` — R65, `harness/drawer.py`.

**What the operator sees.** The navigation drawer opens, and its entries are not clickable: a tap
on a menu entry goes nowhere.

**What actually happens**, measured on the journey rather than read: tapping « Médiathèque » left
the bar's current tab on « Acquisition » at +60 ms and again at +560 ms. The entry was never
inert — the page changed and was put back.

**Why.** The close unwound the drawer's own history entry with `history.back()`, which is
**asynchronous**. Its pop therefore landed AFTER the arrival had rendered, and the popstate
handler read that pop as a back gesture: it applied the entry underneath, which describes where
one already was. One frame of Médiathèque, then Acquisition again.

A second cause, on one entry only: « Config » pointed at an id `PAGES_OF` does not carry, and
answered a tap with a message saying the page was out of scope. Réglages exists and is drawn; the
entry now names it.

**Why no rule caught it.** R59 covers the back gesture and was green throughout. It drives named
states; nothing walked the journey of opening the drawer and tapping an entry.

**And it is the SECOND time this surface has been reported inert.** `regions.json` →
`$reportedDefects` already carries `inert-drawer`: « the hamburger opened nothing and the drawer
links were not clickable: event delegation looked only at `<button>`, and a navigation link is an
`<a>` ». That cause was fixed and a comment left beside it. A different cause produced the same
symptom, and nothing had been left behind that would notice — the fix was recorded, the BEHAVIOUR
was not. That is precisely the difference between a note and a rule.

**The fix.** The destination TAKES the drawer's history entry (`replaceState`) instead of the
close unwinding and the arrival pushing in the same task. And our own unwind now announces itself,
so the popstate handler consumes it rather than interpreting it.

**Mutation.** Point an entry at an id no page carries → « chaque entrée nomme une page qui
existe » falls, naming `config`.

---

## B-014 — The drawer's current entry is unreadable

**Reported** 1×. **Status** `to confirm` — R65, `harness/drawer.py`.

**What the operator sees.** The entry marking where one currently is cannot be read.

**What actually happens.** Its label and its background are the **same colour** —
`oklch(0.808 0.158 79)` on `oklch(0.808 0.158 79)`. Contrast **1.00**. A label written in
invisible ink.

**Why.** `background: var(--sidebar-accent, var(--primary))`, and `--sidebar-accent` is defined
nowhere — so the background falls back to `--primary`, which is what the label is coloured with.

**Why no rule caught it.** This is the family of B-007, and R61 exists for it — but R61 forbids
only **bare** `var()`. A fallback makes a phantom token look like a considered choice, and the
rule looks away. Two other `--sidebar-*` references had the same shape with harmless fallbacks;
they are gone too, because a landmine that has not gone off is still a landmine.

**The fix.** « You are here » is the brand colour on the label — the mark the bottom bar already
uses — over a **tint** of that mark rather than the mark itself. Measured: contrast **7.66**,
above AA and above AAA.

**Mutation.** Restore the fallback → the contrast check falls at 1.0, naming the current entry.

---

## B-015 — Back reopens the drawer that was just closed

**Reported** 1×. **Status** `to confirm` — R65, `harness/drawer.py`.

**What the operator sees.** Close the drawer, then use the back gesture: the drawer comes back.
« Ce n'est pas une route. »

**What could not be reproduced.** The drawer never reopened under measurement — five ways of
closing it, on Chromium **and** WebKit, `go_back()` after each. That is recorded rather than
hidden: what follows fixes the bookkeeping the report points at, and only the operator's phone
can say whether it was the whole of it.

**What was found instead**, on every one of those paths: after using the drawer, ONE back landed
on the root-exit warning. The drawer had eaten the operator's navigation history — its entry sat
between the page and everywhere they had been.

**The fix.** The drawer leaves nothing behind: the destination replaces its entry, so a back from
there reaches where one was before opening it. Closing it without going anywhere restores the
history exactly as it was.

**Mutation.** Make the destination push instead of replace → `from « <entry> », back returns to the start` falls on
all four entries.

---

## B-016 — Swiping a row right, then left, makes it jump

**Reported** 1×. **Status** `to confirm` — R64 extended, `harness/drag.py`.

**What the operator sees.** Swipe a card right, then swipe it left: the card jumps. What it should
do is settle back to rest, so that a second, deliberate left swipe is what reveals the actions on
that side.

**Measured.** The row rests at **+84**; the finger's first 15-pixel step puts it at **−168**. A
leap of **252 pixels** — the width of both drawers — before the finger has travelled a centimetre.

**Why.** A drag beginning on an open row has to resume from where the row IS. The origin was
deduced from a side instead of read from the row — `-largeurTiroir(sw, -1)`, the right drawer's
width, whichever side the row was actually open on. A row open on the LEFT therefore started its
travel from the far side.

**Why no rule caught it.** R64 covers one swipe in one direction, and both of its ends were
correct. A jump is a **discontinuity**: a probe that reads only the resting positions certifies
it. The rule now samples during the gesture.

**The fix.** The resting offset is recorded when it is set, and the drag resumes from it. And an
open row can only be CLOSED by a drag — its travel is clamped between where it rests and zero —
so a swipe the other way settles it back instead of crossing rest and opening the opposite drawer
in one gesture. That is the operator's own prescription: « elle devrait se replacer normalement et
je reswipe à gauche si je veux voir les actions à gauche ».

A third instance of the same class was found while fixing it: the quick-action buttons cleared the
row's transform by hand without clearing what was RECORDED about it, so the next drag resumed from
a drawer that was no longer open. They close through the shared close now.

**Mutation.** Restore the deduced origin → « an open row follows the finger without leaping » falls at 252. Remove the clamp → « the reverse drag settles it back at rest, without opening the other side » falls.

---

## B-018 — On a desktop, dragging a row opens the bottom panel

**Reported** 1×. **Status** `to confirm` — R64 strengthened, `harness/mouse.py`.

**What the operator sees.** On a DESKTOP, dragging a row left or right opens the bottom panel
instead of revealing the row's actions. The drag is read as a tap.

**Measured.** On a library row dragged to the right, a click reaches the document with
`defaultPrevented: false` — **the click is not swallowed**. On the same row dragged left, and on a
follows row either way, it is.

**Why.** The guard that stops a drag from also firing the tap was armed on how far the ROW moved:
`|dx - depart| > 4`. A row is free to refuse to move — a library row has no drawer on its left, so
a right drag ends exactly where it started — and then nothing is armed, the click goes through, and
the panel opens over the row.

**Two ways in, and only one is mine.** The right drag on a row with no left drawer has behaved this
way from the beginning. The fix for B-016 added the second: since an open row can now only be
CLOSED by a drag, dragging one further in the same direction also ends where it started. Calling
the whole thing a regression, as this entry first did, was wrong.

**Why no rule caught it — and this is the part worth keeping.** Two reasons, and they compound.

1. **After a touch drag, the browser suppresses the click by itself.** Every finger measurement was
   therefore green over the hole. Only a mouse can see it, and R64 already knew that — its own text
   says a touch probe cannot tell a swallowed click from one that never happened.
2. **`mouse.py` asserted the weaker thing.** It checked that no panel appeared. A panel can fail to
   appear because the release landed a few pixels off the card, which is exactly what happened in
   the first four attempts to reproduce this: the click went through, unswallowed, and hit a `div`.
   The rule now asserts the click was **actively swallowed**, which is the property that was
   promised.

**The fix.** The guard is armed on what the FINGER travelled, never on what the row moved. The
distinction between a drag and a tap belongs to the pointer.

**Mutation.** Restore the row-displacement test → « une ligne de médiathèque, glissé droite : le
clic n'est pas avalé » falls. Disarm the guard entirely → all four fall.

---

## B-017 — Closing a panel sends the list back to its top

**Reported** by nobody. **Status** `to confirm` — R65, `harness/drawer.py`.

**What happens.** Open a bottom panel from a card halfway down a list, close it: the page
underneath is rebuilt and the list is scrolled home. Measured — a marker planted in the view was
gone, and the scroll offset went 22 → 0.

**Why.** The same root cause as B-013, seen from the other side. Closing any layer popped its own
history entry; the handler read that pop as a back gesture and re-applied the state underneath,
which re-renders the page one is standing on.

**How it was found.** By the mutation proving R65 bites. The first pass of that mutation did NOT
fell the rule, which said the guard it targeted was load-bearing for nothing — so under « what no
mutation can fell is removed », it was about to be deleted. Measuring whether it was load-bearing
for the OTHER layers is what turned a deletion into a defect.

**Mutation.** Remove the unwind guard → four checks fall, naming both the rebuilt page and the
lost scroll offset, on the panel and on the drawer.

## Closed entries — index

The bodies of these entries — what each one did, why no rule had seen it, and what proves it now —
were moved verbatim to [`BUGS-CLOSED.md`](BUGS-CLOSED.md) so the open ones stay legible. Nothing
was reworded, renumbered or dropped; the protocol and the counts stay in this file.

**Thirteen were confirmed in ONE batch on 2026-08-20**, on the operator's instruction (« Ferme
tous les bugs en attente de VOTRE confirmation, sauf B-030 »). Each had already been fixed, its
rule green and its mutation proven — `to confirm` in this register means waiting for the
operator, not waiting for work. Recorded as a batch rather than thirteen separate dates because
that is what happened: one instruction, one moment, and inventing thirteen dates would be a
record of something nobody did.

- B-013 — The drawer's entries lead nowhere (closed 2026-08-20, batch)
- B-014 — The drawer's current entry is unreadable (closed 2026-08-20, batch)
- B-015 — Back reopens the drawer that was just closed (closed 2026-08-20, batch)
- B-016 — Swiping a row right, then left, makes it jump (closed 2026-08-20, batch)
- B-017 — Closing a panel sends the list back to its top (closed 2026-08-20, batch)
- B-018 — On a desktop, dragging a row opens the panel (closed 2026-08-20, batch)
- B-021 — Signing out leaves the bottom panel on top (closed 2026-08-20, batch)
- B-022 — « Voir mes suivis » in the add search is inert (closed 2026-08-20, batch)
- B-025 — The screen half of the `data-go` fix has no Back rule (closed 2026-08-20, batch)
- B-026 — A silent `catch {}` can let URL and UI disagree (closed 2026-08-20, batch)
- B-027 — `resync.py` trusts `t:` first-match + naive braces (closed 2026-08-20, batch)
- B-028 — `resync.py` says « 0 correction » for unknown titles (closed 2026-08-20, batch)
- B-029 — Counter rule misses suffix drift (« 1 » in « 11 ») (closed 2026-08-20, batch)
- B-019 — Many media sheets have lost their visual (closed, date not recorded)
- B-020 — Actor portraits on media sheets are broken (closed, date not recorded)
- B-023 — Médiathèque « Incomplets »: every visual broken (closed, date not recorded)
- B-001 — The list poster is still too small (closed 2026-08-14)
- B-002 — The startup bar is never seen on a real load (closed 2026-08-14)
- B-003 — In Arrivées a poster does not lead where a poster leads (closed 2026-08-14)
- B-004 — Dragging the sheet handle down no longer closes the panel (closed 2026-08-14)
- B-005 — A long press on a poster raises the browser's own menu (closed 2026-08-14)
- B-006 — Two different sign-in screens: arrival and sign-out (closed 2026-08-14)
- B-007 — `--accent` referenced 11 times, defined nowhere (closed 2026-08-14)
- B-008 — The card poster should bleed to the card's edges (closed 2026-08-14)
- B-009 — Swiping a media card should reveal its quick actions (closed 2026-08-14)
- B-010 — Only one row open at a time (closed 2026-08-14)
- B-011 — The drawer renders wrong on iOS (closed 2026-08-14)
- B-012 — The startup screen plays a second time once loaded (closed 2026-08-14)

**Full bodies: [`BUGS-CLOSED.md`](BUGS-CLOSED.md)**, same order as this index.

---

## Closed

Confirmed by the operator on a real phone, on `tm-design.iznogoudatall.xyz`. What each one did,
why no rule had seen it, and what proves it now stays in `BUGS-CLOSED.md`: a closed bug whose
history has been erased is a bug that will be made again.

| ID    | Defect                                                    | Reported | Closed     |
| ----- | --------------------------------------------------------- | -------- | ---------- |
| B-001 | The list poster is still too small                        | 2×       | 2026-08-14 |
| B-002 | The startup bar is never seen on a real load              | 2×       | 2026-08-14 |
| B-003 | In Arrivées a poster does not lead where a poster leads   | 2×       | 2026-08-14 |
| B-004 | Dragging the sheet handle down no longer closes the panel | 2×       | 2026-08-14 |
| B-005 | A long press on a poster raises the browser's own menu    | 2×       | 2026-08-14 |
| B-006 | Two different sign-in screens: arrival and sign-out       | 1×       | 2026-08-14 |
| B-007 | `--accent` referenced 11 times, defined nowhere           | 1×       | 2026-08-14 |
| B-008 | The card poster should bleed to the card's edges          | 1×       | 2026-08-14 |
| B-009 | Swiping a media card should reveal its quick actions      | 1×       | 2026-08-14 |
| B-010 | Only one row open at a time                               | 1×       | 2026-08-14 |
| B-011 | The drawer renders wrong on iOS                           | 1×       | 2026-08-14 |
| B-012 | The startup screen plays a second time once loaded        | 1×       | 2026-08-14 |

**What these twelve cost, and what is worth keeping from them.** Seven had been reported
**twice** before being written down here — what was missing was this register, not memory. Four
were invisible because the rule measured a named state instead of the path actually walked: a cold
load, a real finger, a real browser menu. One — B-012 — was my own over-correction of the one
before it. And two rules had to be thrown away before one held, for the same reason both times:
asserting that a panel is open AFTER the finger lifts proves nothing, since a tap opens it too.

**B-037 — a French identifier, and a dead one, in a harness rule under a green gate.**
`frontend/maquette/harness/arrivals.py:53` reads `window.PIPELINE_UID_POUR_LA_SONDE || null`. The
name is French — a name someone chose, which CLAUDE.md §Language covers — and it sits inside a
JavaScript string, so the identifiers arm of `scripts/check-no-french.py`, which parses Python,
never sees it. And nothing under `frontend/` DEFINES that global: the expression is `null` on every
run, and R66 obtains the run uid from the text the prototype prints instead. A dead read, in French,
that fourteen arms walked past. Found by a sub-phase of L02 reading the rule it was migrating (2026-08-21),
not by a guard.

**B-038 — `arrivals.py` reads `empty` into its view and no hold consumes it.**
The rule's `READ` collects `empty` for every flux row (`classList.contains('fempty')`, now
`hasAttribute('data-empty')`), but the only holds that could use it compute the dash from the
result text and consume `blocked` alone. So the `fempty` read was dead on the class before L02 and is
dead on the attribute after it: a mutation dropping `data-empty` leaves the suite green
(`24 rules EXECUTED — no violation`), while the same mutation on `data-blocked` fells the right
hold. A hold « a row with nothing to do is marked empty » (3 of 9 rows today) closes it; it moves
R66's hold count, which is why it was not written inside the migration (2026-08-21).

**B-039 — `actions.py:81` prints whether `.freshtag` exists and asserts nothing.**
The follow flow the rule drives never produces a `fresh` descriptor, so the probe printed `False`
before L02 anchored the element as `card/fresh-tag` and prints `False` after — measured across all
83 named states: `[.freshtag, [data-part="card/fresh-tag"]] = [0, 0]`. The contract is faithful and
nothing holds it: neither end can move and fall a rule. A state that produces a fresh follow, or a
hold after a follow action, is behaviour work outside the anchoring lot (2026-08-21).

**B-040 — French names survive in files no arm of `check-no-french.py` reads.**
By design (its own docstring, arm 1), the harness's rule scripts are read for their hold LABELS
only; `states.js` and `legacy.js` are read for the declared debt alone. So five French view labels
in `sweep.py`'s `VIEWS` table (`acq/suivis`, `acq/decouvrir`, `lib/incomplets`, `lib/recents`,
`arrivees`) sat under a green gate — `arrivees` is even in `scripts/nofrench_lexicon.py:47` — until
sub-phase 6.5 of L02 turned them into screenshot file names and renamed them by hand; and
`regions.json:81` still declares the region id `arrivees/empty`, one of the oracle's 33 keys, which no
arm reads either. Same family as B-036: a name someone chose, in a file the guard does not open. The
fix is an arm over the harness's string literals and the oracle's region ids, with the lexicon it
already has; the region rename moves an oracle reference key and is not an anchoring change
(2026-08-22).

**Widened 2026-08-22 by the steward's audit of L02, because the fix above is written too narrow.**
`frontend/maquette/oracle.py` uses the French verb « entérine » three times, and line 953 is the
`--accept` HELP STRING — a message the tool prints, which `CLAUDE.md` requires to be English. An
arm over the harness's string literals and the oracle's region ids would not reach it: it is
neither.

**The mechanism is a second one, and it is the part worth fixing.** The guard reads
`frontend/maquette/` by an ENUMERATED list — `MAQUETTE / "serve.py"` and `MAQUETTE / "resync.py"`,
at three call sites — never by a glob. `oracle.py` and `fidelity.py` sit in that directory and are
in **no corpus at all**, so it is not that an arm reads them narrowly: nothing opens them. A list
hand-edited every time a sibling lands beside it goes stale, and this one did the day L01 added a
file. Widening the corpus to the directory closes both this and whatever lands there next; the
three words alone close neither.

Scope measured before reporting: three occurrences, one word, one file — `fidelity.py` is clean.
<sub>`grep -n "entérine" frontend/maquette/*.py` · `grep -n 'MAQUETTE / "' scripts/check-no-french.py`</sub>

**Precision added 2026-08-25, because the command above cannot see one of the three.** Line 637 is
inside the `$comment` this tool SERIALISES into `frontend/maquette/oracle-reference.json`, so the
word is written into a `.json` the register's own command — which globs `*.py` — will never open.
Two consequences worth the line: the scope is three occurrences in one `.py` **plus one in a
committed reference file**, and **every future `--record` rewrites the French word** into that
file, so the copy regenerates for as long as line 637 stands. Fix the source line first; the
`.json` copy then corrects itself on the next recording.
<sub>`grep -c "entérine" frontend/maquette/oracle-reference.json` → 1</sub>


**CLOSED by L10-bis: the arm already exists, and the entry had gone stale.** `oracle.py` carries no
« entérine » — `--accept`'s help string reads « ratify a REVIEWED change into the reference ». A
later wave renamed it and nothing said so.

**The scope this entry asked for is armed, and that was PROVED rather than read.**
`nofrench_lexicon.scope_of` maps `frontend/maquette/*.py` to the `servers` scope, which arms 1 and
2 both read — 927 string literals and 733 declared identifiers on the run below.

<sub>mutation, three ways, all in `oracle.py` — an ACCENTED French help string
(« entérine un changement RELU… »): arm 1 falls naming the file, the line and the literal. An
UNACCENTED French help string (« valide un changement relu dans la source »): it still falls, so
the reader is not the accent alone. A French local (`resultat_du_tri`): arm 6 falls with « built
from 'tri', which French knows and English does not ». Restored → exit 0</sub>
**B-073 — the grandfathered list guarantees its membership and never its justification.**
`scripts/check-frontend-boundaries.py`'s size arm is careful about the list's *composition*: it
refuses a file over the 400-line ceiling that no entry records (`unrecorded`), and it refuses an
entry for a file that has come back under it (`stale`). **It never reads the entry's VALUE.**
`lot = GRANDFATHERED.get(module, …)` is used for one thing only — printing
`--list-grandfathered` — so the sentence naming the lot that will convert the file is checked by
nothing, and regenerating the list preserves it verbatim.

**What that costs today.** Four of the seven entries name **L07**, which landed on 2026-08-25:
`features/acquisition/page.tsx` (« L07 — the surface converts, then L09 takes its data »),
`features/library/page.tsx`, `features/media/media-screen.tsx` and
`features/arrivals/resolution-screen.tsx` (« L07, then L09 »). All four are still over the
ceiling, and all four **grew** during the wave — 762→769, 583→589, 760→789, 412→413. The next
session reads a list promising a lot that has already been and gone.

**This is not « L07 failed its promise »**, and the distinction is the whole finding: each label
names TWO lots, the conversion (L07, done) and the data extraction (L09, owed), and nothing
distinguishes the half that is spent from the half that is not. A label carrying two lots and no
state is not a label anyone can act on.

Fix: the arm reads the value and refuses a label whose named lot is `LANDED` in
`frontend-architecture.md` while the file is still listed — either the entry is re-labelled with
the lot that actually owes the reduction, or its landing is what the ceiling should have caught.
Mutation: mark a lot `LANDED` in the plan and watch the arm fall on the entries naming it.

<sub>`python3 scripts/check-frontend-boundaries.py --arm size --list-grandfathered` · the four before-figures: `for f in features/acquisition/page.tsx features/library/page.tsx features/media/media-screen.tsx features/arrivals/resolution-screen.tsx; do git show 5fdbfc9a^:frontend/maquette/design/src/$f | grep -c '[^[:space:]]'; done` → 762, 583, 760, 412</sub>

---

## L07-bis — the tidy-up, 2026-08-25

The wave that executes the seven arbitrations the operator took on 2026-08-25. They were recorded
in **#498**, whose four documentation commits this branch carries — so the arbitration and its
execution land together, and every row below reads `fixed #500`. Every entry closes with the
mutation that was seen to bite; **three of them are new and were found BY those mutations**, which
is the reason this section exists rather than a row flipped to `fixed`.

**Three L07 findings are deliberately still `open`**: B-061 (arbitrated — the oracle is NOT
widened, so there is nothing to build), B-068 (the prose inventory) and B-071 (the design-notes
toggle, which lives in `engine/legacy.js` and belongs to L13).

**B-050, B-059 and B-070 — three angles on one mechanism, closed by splitting on a SUBJECT.**
A guard file walking towards a ceiling that exits 1, in a repository whose waves keep adding arms
to it. `check-frontend-boundaries.py` 921 → 442 (`boundaries_addressing.py`: what the SOURCE may
declare as an address), `check-css-tokens.py` 905 → 771 (`csstokens_motion.py`: is a motion value
on the motion scale, asked of a declaration and of a class name), `rename-identifiers.py`
829 → 555 (`rename_readers.py`: who decides which byte is CODE).

Proved behaviour-preserving by an ORACLE OUTSIDE THE CHANGE: `main`'s versions of both check
scripts were run in place and their output diffed against the split ones — identical, line for
line. The rename tool's 33 tests then caught what the diff could not: `subprocess` had left the
import list with the readers while `ignored()`, which stayed, still called it.
<sub>`python3 scripts/check-module-size.py --root scripts` → clean</sub>

**B-063 — the repository's cheap guards join the per-phase tier.**
`frontend/maquette/harness/run.sh --contracts` now runs **twelve invocations of nine guards**
(~31 s), and the full suite runs them too: a wave gate that reads less than the phase gate is not
a gate. NOT `make check` entire — the 2026-08-24 cadence ruling stands for its fourteen minutes of
tests. **None of the nine reads a database**, which was checked and not assumed: that is the
property that disqualified `arrivals.py` twice (B-049).

**THE FIRST SELECTION WAS WRONG, and an adversarial review is what said so.** It held the three
guards that mostly read `personalscraper/` and `tests/` — which CI already runs in its own job —
and none of the cheap ones that read what a maquette phase actually edits. `legacy.css`'s own
ceiling was absent from the tier of the very wave that edits `legacy.css`. Six more joined for
6 s: `check-css-tokens.py`, `check-legacy-css-residue.py`, `check-compositor-css.py`,
`check-markup-contracts.py`, `check-i18n-placeholders.py` and this wave's own
`check-code-abbreviations.py`. `check-tailwind-confinement.py` stays out — it needs a build of its
own and costs 102 s.
<sub>mutation: a 1 201-line file under `scripts/` — the tier prints « FAILED: python3 scripts/check-module-size.py --root scripts », names the file, and the run exits 1 after the remaining guards have had their turn</sub>

**B-064 — the recipe was wrong TWICE, and the second half was found by following the first.**
`regions.json` said `R72_SANS_BUILD`; `shell.py` reads `R72_SKIP_BUILD`. The name is corrected —
and replaying the recipe with the real variable, as the fix requires, showed the mutation it
prescribes cannot be applied at all: it renames a class inside the emitted fragment, and
`refonte.html` has carried no markup since L07. **A recipe that cannot be APPLIED certifies a rule
exactly as surely as one that cannot FAIL.** Re-recorded against today's fragment.
<sub>mutation: `@layer block2 {` → `@layer block2X {` in `dist/index.html`, `R72_SKIP_BUILD=1` — hold (a) alone falls, « fragment emitted 0 time(s) », exit 1; the rebuild restores it</sub>

**B-065 — the eleven files are gone, and the hold that refuses the next copy was itself green
over the defect first.** `arm_tree` gains it. **The first version looked for a segment repeated
INSIDE the relative path and reported the real tree clean**: read from `design/`, the copy spells
`frontend/maquette/design/src/…` — five distinct segments, nothing repeated. What repeats is the
name of the directory you are standing in, so the hold is told its ancestors and its corpus's own
name. `node_modules/` and `dist/` are skipped by name: a dependency tree repeats a hundred names
and an arm reporting those would be muted within the day.
<sub>mutation: a source file at `design/frontend/maquette/src/lib/` — « a directory under frontend/maquette/design/ is named « src/ » again », exit 1. Six of the nine new tests are red against `main`'s guard</sub>

**B-066 — settled, one each way, and the exemption is no longer the answer.**
`.skip-link` had no reason and is ON THE SCALE. Its `padding: 10px 16px` was half on it already —
10px IS `--spacing-5` — and the two values that sat between steps were the **16px of horizontal
padding** (the ramp reads 14 then 18) and the **10px radius** (the ramp reads 8 then 12). Nobody
chose either: they came from the harness block the scale rule never read. 16 → `--spacing-8`,
10 → `--radius-4`, both one increment UP, because an affordance that appears only under keyboard
focus should read generously when it does. **THE ORACLE DOES NOT MEASURE THIS
ELEMENT**, so it is not the proof here and does not pretend to be — the reading was taken in the
browser instead. `.visually-hidden` stays exempt and is no longer debt: `-1px` is the clip IDIOM,
and rounding it to a step un-hides the element.
<sub>read in the browser on the served build — `padding: 10px 18px`, `border-radius: 0px 0px 12px 12px` · mutation: `16px` back in place — « `16px` is on no step of the spacing scale », exit 1</sub>

**B-067 — R80, and its own proof is that the oracle cannot supply one.**
`frontend/maquette/harness/residue.py` pairs each residue selector with the typed variant wearing
its identity anchor and compares `getComputedStyle` IN THE DOCUMENT, on two sibling probes, for
exactly the properties the residue declares. Never as text: `flex: 0 0 auto` and `flex-none` are
one value written twice. **Sixteen pairs stand where the finding named seven.** Registered as R80
in `regions.json`, in the contracts tier, recorded in D10, and it dies with it.

Its one finding on the unmutated tree was real: `.sechead` declared the `background` SHORTHAND
where `sectionHead()` sets `bg-transparent` — same rendering, and no longer term for term. The
residue says `background-color` now, which is what it meant.
<sub>mutation: `emptyNote()`'s `rounded-3` → `rounded-2` — R80 falls, « border-radius: residue « 8px » vs variant « 6px » », exit 1, WHILE THE ORACLE RUNS GREEN over 2 739 measurements. That is B-067 demonstrated rather than asserted</sub>

**B-076 — the hero animates under `prefers-reduced-motion: reduce`, and R80 is what found it.**
`.herobg`'s residue rule sits inside `@media (prefers-reduced-motion: no-preference)`;
`heroImage()` emitted a bare `animate-hero-in`, which carries no such condition. Under
`no-preference` the two sides agree to the character, which is why the pair passed and why nothing
else ever saw it — the oracle measures one preference, and the a11y tier does not ask about
motion. Under `reduce` the residue drops out and the utility keeps animating: the hero's entrance
ran for a reader who had asked for no motion, against invariant 14, « reduced motion is a designed
state, not a fallback ». `motion-safe:animate-hero-in`.

**R80 measures BOTH preferences because of it.** The rule was written reading one, found this by
being widened, and the widening is now part of it: two contexts, every pair held in each.
<sub>mutation: the bare `animate-hero-in` back in place — « animation under reduce: residue « none » vs variant « 0.45s … heroin » », exit 1</sub>

**B-075's second instance, and it is R80's own reader.** The factory extractor split a `cva()`
call's arguments on their top-level comma and was BLIND TO COMMENTS — and this repository's
comments are full of commas. Three factories came out with an EMPTY base, dropped silently from
the anchor table, and took their pairs with them: the rule printed three comparisons fewer and
nothing red. The comma that exposed it was in a comment this very wave wrote. The reader blanks
comments now (quotes and templates tracked, so a `//` inside a class literal survives), and **a
factory whose base cannot be read is a violation, never a skip** — 108 factories became 111.
<sub>mutation: `cva('sec …')` in single quotes — « UNREADABLE: section() in layout.ts », exit 1 · before/after on the same file: 14 arguments and no anchor, against 3 and `herobg`</sub>

**B-069 — `legacy.css`'s header cites D10** of `docs/reference/frontend-architecture.md` rather
than an archived DESIGN, which is frozen history that could no longer be corrected if the
decision's terms changed. The archive keeps its record of where the decision was taken.

**B-072 — retired, not repaired, and the distinction is the finding.** ⚠ **It leaves a dangling
citation in FROZEN history, and that is said here because the archive cannot say it.**
`docs/archive/features/maquette-l07/DESIGN.md` § 248 and § 253 still name
`plan/build-surface-manifest.py`, and `docs/archive/` is never revised — so this entry is the only
place a reader can be told the file was removed on the operator's instruction and why. The
recording it produced survives at `docs/archive/features/maquette-l07/plan/surface-manifest.json`.
`build-surface-manifest.py` read a 4 136-line stylesheet inside `refonte.html`. That file is 120
lines of conversion ledger. There is nothing left to re-derive from, so the proof is CLOSED and
the recording it produced (`plan/surface-manifest.json`, correct) stays. What loses its subject is
removed, not kept « just in case » — and a tool that crashes and nobody dares delete is the shape
that rule exists to prevent.

**B-073 — the size arm reads the label now, and the grammar is written down.**
It refuses a label whose LEADING lot the plan marks `LANDED`; a label leading with no lot at all;
and a plan that cannot be read — the last being a violation rather than « no lot has landed »,
which is the reading that would make the hold pass for the one reason it must never pass for. A
label may still MENTION a spent lot (« L09 — … (L07 converted the surface) ») because that
sentence is worth keeping; what may never be spent is the lot the entry leads with. The five
entries are re-labelled with the lot that OWES the reduction.
**And the first version of that arm had B-073's own defect inside it**, found by review: it held
the label against the LANDED set alone, so « L19 — the data layer takes it » would have stayed
green for ever. The plan declares a finite set of lots (L01 to L13 when this was written — L19 has
since been declared, on 2026-08-29, and the fixture moved to `L99`); a lot it never declares is a
promise nobody can call
in. The arm reads both sets now.
<sub>mutation: mark L09 `LANDED` in the plan — the four entries naming it fall by name, exit 1. Second: the plan made unreadable — « no lot status could be read », exit 1. Third: a label leading with `L19` — « which the plan does not declare », exit 1 (re-recorded with `L99` on 2026-08-30, once L19 existed)</sub>

**B-074 — the abbreviation rule's figures were measured against a list the document did not
contain.** `docs/reference/code-naming.md` shipped on 2026-08-25 with a debt of **1 507**, a
residue of **745 in 322 files** and a blacklist described in prose but never written down. The
guard that arms it holds **56** words. Three it holds — `ref`, `dest`, `params` — were not in the
count that produced 1 507; `temp`, `func`, `prop` and `props` joined after an adversarial review
showed each was a one-character escape route from a word already refused (rename `tmp_path` to
`temp_path` and the ratchet TIGHTENS while the name gets no better); and `exc` went the other way,
544 occurrences moved to the KEPT list because `sys.exc_info` and `except … as exc` are the
standard library's own spelling. Re-measured: **1 789** in **347** files.

**The RATES hold, and they are the figures that decided the scope**: 3.7 new occurrences per day
for the residue against a forecast of ≈ 3, and 15.1 with the campaign words refused against
≈ 14.5. Both sets of numbers are in § 7 side by side rather than overwritten — a figure silently
replaced teaches nothing about the figure that goes stale next.

**AND THE SAME DEFECT RECURRED INSIDE THE FIX.** The first armed figures — 1 806 in 356 files —
were themselves taken against a reader that could not see `self._connection = …`, and against a
list missing the four escape words. **Twice now these figures have been asserted from a list that
was not the one shipping**, which is why § 7 keeps both columns and names the commit each was
measured at.
<sub>`python3 scripts/check-code-abbreviations.py --list-baseline` → `"total": 1789` over 347 files</sub>

**B-077 — the tests written to cover the browser-free half needed a browser to be collected.**
`residue.py` imported `playwright` at module level, so `tests/scripts/test_residue.py` — whose
whole subject is the four PURE functions — could not be imported in CI's `test` job, which
installs no browser. Green locally, where playwright is installed; an **ERROR** on the runner,
which is a COLLECTION crash and therefore not one test failing but the module and everything
pytest had not yet reached. The import moved into `main()`, where the browser is actually used,
and the module's own claim became true.

**Found by CI and by nothing else**, which is the entry's point: the wave ran the full harness
suite twice, `make check` twice and every guard by hand, all on a machine that has playwright.
A gate proves what it reads, and every local gate read an environment the runner does not have.
<sub>reproduced by shadowing the module: `PYTHONPATH=<dir with a raising playwright.py> python3 -m pytest tests/scripts/test_residue.py -q` → 13 passed, and the rule itself still refuses to run</sub>

**B-075 — five guards, written for a defect, were green over that exact defect.** Three were
found by mutation while the wave was being built; **two more by the adversarial review that
followed**, and those two are the more interesting half — both were holes in a guard's own stated
subject.

R80's `balanced()` counted parentheses inside string literals while `split_top_level()`, three
functions below in the SAME FILE, tracked quotes. A class list carrying `before:content-['(']` —
ordinary Tailwind, and `endMark()` already ships `before:content-['']` — ran the reader to the end
of the file and made every literal after it a branch of that factory. The anchor stayed right, so
nothing looked wrong.

And R80 held « a factory the reader cannot read is a violation » at ONE of the two entrances: an
empty base was refused, a factory the `FACTORY` pattern never matched simply was not there.
`cva<Props>(…)`, `const x: F = cva(…)`, an export on a later line, a `memo(…)` wrapper — four
ordinary spellings, and losing `statusDot()` alone would have taken six of sixteen pairs out of the
comparison while the floor of seven stayed green. **The remedy is not a bigger pattern: every
`cva(` call in the sources is counted, and the reader must account for all of them.**

**The floor was the pre-satisfied counter, one wave after the wave that named it.** Seven was
B-067's tally and it was the wrong floor the moment the rule found sixteen. It is sixteen now.

The three found during construction: The nested-copy hold read the relative path and found five distinct segments where the
real tree sat (B-065). R80 scanned `variants*.ts` and `features/*/variants.ts`, missed the three
files holding the shared vocabulary, paired ONE anchor out of eight and printed « no divergence »
(B-067). R80's FACTORY READER then split a `cva()` call on a comma inside a COMMENT, dropping
three factories out of the anchor table with their pairs — and the comma that exposed it sat in a
comment this same wave had written four hours earlier. None would have been caught by anything but
a mutation: all three had plausible output, all three exited 0, and two of them printed a count.

**What closed them is a FLOOR, and it is the general remedy.** R80 refuses fewer than **sixteen**
pairs — the measured count, not the finding's seven — and refuses a `cva(` call it cannot account
for. `check-code-abbreviations.py` refuses a corpus of zero files or zero names. `arm_size`
refuses a plan it cannot read rather than concluding nothing landed, and refuses a label naming a
lot the plan never declares. The pattern is the same in all five:
**a reader that finds nothing must say so as a violation, never as a pass.** Recorded here as its
own entry because it is not one bug: it is the failure mode this repository keeps buying, and the
remedy is cheap enough to be a habit.

**B-078 — the one file that is supposed to say where the work stands said something untrue, and the reason given for leaving it was a rule nobody wrote.**
`IMPLEMENTATION.md` read « **In flight**: L07-bis — the tidy-up » after L07-bis merged
(`ec38ff49`). That row is the section this repository declares to be **the only place that says
where the work STANDS** — « duplicating state is what produced a stale table read as current for
three days » is its own opening sentence. A wave that has landed cannot be in flight.

**The ajournment rested on a false premise, and that is the half worth recording.** The wave
carried the correction forward to L08's pull request because « the steward's rule forbids a small
follow-up pull request ». **No such rule exists.** § 5 of `frontend-architecture.md` says the
opposite in one line: « One lot, one branch, one squash merge onto `main` after green CI and a
clean final adversarial review. **This holds for a two-line documentation fix as much as for a
conversion.** » That sentence licenses the small pull request and prescribes its method; it
refuses a correction pushed straight to `main`, never a correction of two lines.

A rule remembered rather than re-read is how a directive acquires a clause nobody wrote — the same
failure mode as a figure nobody recounts, and this register carries several of those. Fixed by
this entry's own pull request, at the cost it was said to be avoiding: one branch, one review, one
squash.

<sub>`grep -n 'In flight' IMPLEMENTATION.md` · `sed -n '/^## 5. The method/,+4p' docs/reference/frontend-architecture.md`</sub>

> **Scheduled by the operator, 2026-08-25: B-079, B-080 and B-081 travel together in a correction
> wave between L08 and L09, opened once the steward's audit of L08 is done.** Not sooner, and not
> one at a time: they share a subject — what the screen asserts against what the repository holds —
> and two of them share a fix. **The cost of waiting is named rather than left implicit**: until
> that wave lands, every screen the operator judges carries design-note paragraphs the oracle does
> not measure, so the layout under judgement is not the layout under proof. The interim is a
> one-line workaround, not a repair: `document.documentElement.classList.add("measuring")` in the
> console hides the notes exactly as the oracle does — and hides the frame's own buttons with them,
> which is why it is a workaround.

**B-079 — the design host serves whatever is on disk, and nothing on screen says what that is.**
The operator judges the interface by looking at the design host. The chain from `main` to that
screen has four links, and **only one is held**:

| Link | Production | Design host |
| --- | --- | --- |
| the tree is on `main` | `deploy.sh` guard 3 refuses otherwise | nothing |
| the tree is clean | `deploy.sh` guard 2: « Uncommitted code is NEVER deployed » | nothing |
| the build matches the sources | rebuilt from source only | **held** — `serve.py` compares the newest input mtime against `dist/` and rebuilds under a lock per request |
| the served identity is visible | `BUILD_COMMIT` stamped, baked into the bundle, read by `GET /api/version`, post-check R27 proving the RUNNING process serves it | nothing (see B-080: worse than nothing) |

`serve.py` holds no notion of a commit, a branch or a dirty tree across its 784 lines. So « is what
I am looking at what is on `main`? » is unanswerable from the screen.

**Not hypothetical, and the precedent is this repository's own week.** Uncommitted edits to
`CLAUDE.md` survived four branch changes in the clone an agent was working in, and were reported as
preserved. The same clone runs `serve.py`. **And it happened to the steward mid-audit**: a local
`main` carrying the right NAME and weeks-old content, then a detached checkout two commits behind —
twice in ten minutes, on this very question, with nothing on any screen saying so.

**The fix is NOT production's fix.** `deploy.sh` REFUSES a dirty or non-main tree because
production must only serve `main`. The design host must be able to serve a branch — that is what
it is for. So it does not refuse, **it declares**: `branch @ sha` plus a visible mark when the tree
is dirty, computed per request (`serve.py` already rebuilds per request; a boot-cached identity is
the drift R27 exists to catch on the other side). The harness should read it too — `wrapped.html`
is a MANUAL copy and a stale one measures the previous build in silence.

<sub>`grep -in 'commit\|branch\|sha' frontend/maquette/serve.py` · `sed -n '50,67p' scripts/deploy.sh`</sub>

**B-080 — the drawer states a version and a build, and both are decoration.**
`src/engine/legacy.js:11829-11830` emits `<p class="vv">0.98.23</p>` and
`<p class="vc">build 58d0d4fd · à jour</p>` as **literals**. Nothing computes them, nothing checks
them, and « à jour » asserts a freshness it does not measure. Reported by the operator on
2026-08-25 from a live screenshot, while `main` stood at 0.98.40 and `893740d6`.

**This is worse than B-079's silence, and the distinction is the point.** A screen that says
nothing sends its reader to look; a screen that states a plausible answer stops them looking. The
value is credible precisely because 0.98.23 was a real version of this repository once — a
placeholder reading `0.0.0` would fool nobody. The operator asked twice in one session which commit
was being served **while this line was on screen**, which is what a reader does when an instrument
has lost their trust without being removed.

Fix: it is the same fix as B-079 — the served identity, computed. Until then the two lines should
say what they are, because a labelled mock is data and an unlabelled one is a lie.

<sub>`grep -n '58d0d4fd\|0\.98\.23' frontend/maquette/design/src/engine/legacy.js`</sub>

> **FIXED by #505, the correction wave between L08 and L09 — B-079 and B-080 together, as scheduled.**
> `frontend/maquette/host_identity.py` computes the branch, the abbreviated commit and whether the
> tree is dirty, **per request** — split out of `serve.py`, which crossed the soft module ceiling
> the moment this arrived, on the subject and not on the line count: `serve.py` answers « what
> document do I send? » and that file answers « what tree am I sending it from? ». `serve.py`
> publishes it on the document it sends, AFTER the build cache and never inside it, because a
> branch can change and a tree can go dirty without one build input's mtime moving.
>
> **Where it shows was the operator's arbitration, 2026-08-26: the drawer, and there alone.** The
> phone frame was offered and refused. `lib/served-identity.ts` words it and owns the case where
> nobody published one — the rule suite's static host, a `vite` preview — where it says the
> identity is unavailable, with the reason, and falls back to nothing at all. A fallback there is
> B-080 wearing a different number.
>
> **R87, 26 holds, mutation-tested seven ways**: the unavailable case made to state a plausible
> version (falls), the dirty mark dropped (falls), the answer cached at boot (falls), the host
> stopped publishing (falls), and a tree outside a repository given a guess (falls).
>
> **Its per-request hold was VACUOUS in its first version**, and that is recorded here rather than
> quietly repaired — it is the wave's own subject. It made the served tree dirty between two
> requests and compared the answers; on a tree that was already dirty, which is every tree a wave
> is written on, both answers read `dirty: true` and the hold passed having distinguished nothing.
> It builds a scratch repository now, with a branch name and a commit the rule chose, and reads it
> twice from one process across a change it makes itself. Counted in § Guards green over what they
> do not read.
>
> **What is NOT fixed**: production's side is untouched, and was never in question — `GET
> /api/version`, the boot-cached `BUILD_COMMIT` and post-check R27 are the other half of this
> question and belong to the shipped application.

**B-081 — the design notes cannot be hidden any more, and the instrument does not see them.**
Reported by the operator on 2026-08-25: the design-note paragraphs are visible on every screen, and
the toggle's toast announces « Notes masquées. » while nothing hides.

**The mechanism, measured.** Before L07, `refonte.html` carried both halves — `.note { display:
none }` (hidden BY DEFAULT) and `:root.notes .note { display: block }` (the toggle revealed them).
D-L07-1 deleted BLOCK 1 and both went with it. `legacy.js:11414-11419` still toggles the `notes`
class on `<html>`, still flips `aria-pressed`, still toasts — and **no rule reads that class any
more**. The default flipped from hidden to shown, which is the opposite of what B-071 records: that
entry says the toggle reports success for a class nothing reads, and reads as though the visual
state were still correct. It is not.

**The second half is the one that costs, and B-071 does not mention it.** The only surviving rule
touching `.note` is `harness.css`'s `html.measuring .note { display: none !important }`. **So the
oracle measures a document with no notes while the operator judges one full of them.** 2 739
measurements at zero divergence certify a page nobody looks at; the layout actually being judged —
density, rhythm, the space between a section head and its first card — is measured by nothing. An
instrument and an eye pointed at different documents, with nothing saying so.

Fix: restore the default in the base layer (the notes belong to the prototype, not to the product,
so `harness.css` is where the pair belongs — it ships nowhere), then mutation-test the toggle both
ways. **Do NOT close B-071 with it**: its third end lives inside the dying engine and belongs to
L13. This entry is the visible half and can be repaired now.

<sub>`grep -rn '\.note\b' frontend/maquette/design/src/styles/*.css` · `git show 5fdbfc9a^:frontend/maquette/design/refonte.html | sed -n '4008,4034p'`</sub>

> **FIXED by #505, the correction wave between L08 and L09.** The pair is restored in `harness.css`,
> with the callout's own appearance, which had gone with it: hidden by default, shown when the
> information button toggles `notes` on `<html>`.
>
> **The half that cost is answered, and it was answered by measuring rather than by asserting.**
> This entry says the oracle certifies a page nobody looks at; the reading it invites is that the
> reference would have to move once the default changed. **It does not, and that is the proof.**
> `html.measuring .note` hides the notes only while the oracle captures — so the notes were
> ALREADY absent from every measurement, and restoring the default makes the judged document match
> the measured one WITHOUT moving a number. The oracle reads no divergence over 2 739
> measurements, taken after the repair. That sentence is the repair's evidence, not a formality:
> had it diverged, the instrument and the eye would still have been pointed at two documents.
>
> **R86, mutation-tested both ways**: the default hide removed (falls, naming « hidden by default »
> and « releasing it hides them again »), and the toggle half removed (falls, naming « pressing the
> button shows them »). A rule holding only the pressed state would have passed on the broken tree,
> because the notes were visible in both positions.
>
> **AND `.note` WAS NOT ONLY THE PROTOTYPE'S ANNOTATION**, which restoring its default made
> visible: twenty-seven paragraphs on product surfaces wore it, and hiding them by default took
> with them the only sentence saying that a maintenance rubric DELETES. Found by an adversarial
> reviewer; the operator arbitrated an audit of all twenty-seven rather than a single exception.
>
> **The test applied, written where the answer lives (`ui/variants/layout.ts`)**: a paragraph is an
> annotation if it addresses the reader of the MAQUETTE — what changed, what was drawn anew, which
> section of the constitution it serves — and guidance if it addresses the operator USING the
> application. Twenty-three are annotations and keep `.note`. **Four are guidance** and wear
> `guidance()`: the maintenance rubric's subtitle, the scheduler line explaining a status the
> operator would otherwise misread, « un champ laissé vide n'efface rien » on the secrets form, and
> what « laisser tel quel » does before it is done. R86 holds the two apart in one document, and
> the mutation that gives `guidance()` the annotation's class falls.
>
> **B-071 stays open**, as this entry instructs: its third end lives inside the dying engine and
> belongs to L13.

**B-082 — the `hidden` attribute does not hide, on every element that also carries a display utility.**
Reported by the operator on 2026-08-25 from a live phone: on opening the design host, the
design-notes toast covers the floating add button; **the toast's close button (×) fires the add
button underneath**, and the reader lands on the add-to-follows search from a control that was not
on screen. Their reading — « an element removed from view should not be clickable » — is right, and
the mechanism is worse than that: **the element was never removed from view at all.**

**Measured.** `index.html`'s `#fab` carries `hidden` AND `grid` (from `grid place-items-center`).
`hidden` is styled by the user-agent stylesheet, which every author rule beats. Tailwind v4's
preflight carries the remedy — `[hidden]:where(:not([hidden="until-found"])) { display: none
!important }`, whose `!important` exists for exactly this collision — and **this prototype
deliberately does not import preflight** (`src/styles/theme.css`, L07: a second reset landing on
the one the prototype already has would break the wave's own claim; « adopting preflight belongs to
the lot that can prove what it changes »). That decision was right for L07 and it left this hole,
which nothing named.

**It is not one button. Five elements carry `hidden` beside a display utility**, so on all five the
attribute is inert: `#fab` (grid), `#nav` (flex), `#ptr` (grid), `#installbar` (flex),
`#installsteps` (flex). `#nav` is the navigation drawer.

**Why the collision lands here specifically.** The toast and the button are anchored to the SAME
edge — both `bottom-[calc(var(--tm-bottom-bar-h,0px)+16px)]`, one `right-[14px]` and the other
`right-[16px]` — so they occupy the same corner by construction, the toast at `z-[49]` painting
over the button at `z-30`. The close target is `w-[24px] h-[24px]`, which is WCAG 2.2 AA's floor
and no more, on a 52 px control hidden directly beneath it.

**What is proven and what is not.** That `hidden` is inert on those five elements is certain, read
from the markup and the import list. The exact path by which the tap reaches the button — a finger
landing outside the 24 px target, or the toast being dismissed and the same gesture falling through
to what it revealed — needs a device to separate, and the fix does not depend on knowing which.

Fix, and it is two independent halves: make `hidden` bite (a base-layer rule carrying preflight's
`!important` form, without adopting preflight entire), and stop anchoring a dismissible banner to
the same corner as a primary action. Mutation for the first: set `hidden` on `#fab` and confirm a
tap at its coordinates reaches nothing.

<sub>`grep -n 'hidden' frontend/maquette/design/index.html` · `sed -n '55,70p' frontend/maquette/design/src/styles/theme.css`</sub>

> **FIXED by #505, the correction wave between L08 and L09 — and THIS ENTRY WAS WRONG ABOUT THREE OF THE
> FIVE.** The correction is written before the fix, because it is the same failure the wave
> exists to count.
>
> « Five elements carry `hidden` beside a display utility, so on all five the attribute is inert »
> was read **from the markup and the import list**. It did not open `base.css`, which carried a
> hand-maintained group — `.fab[hidden]`, `.installbar[hidden]`, `.installsteps[hidden]` and nine
> more — **unlayered**, precisely so it would beat a utility. Measured in the document by setting
> the attribute and reading `getComputedStyle` back: `#fab`, `#installbar` and `#installsteps`
> already computed `display: none`. **Only `#nav` and `#ptr` were inert.**
>
> **AND THE CORRECTION ITSELF WAS WRONG TWICE, which is why it is written out rather than
> summarised.** This entry calls `#nav` « the navigation drawer »: it is the **bottom tab bar**
> (`class="bottombar"`, `data-part="shell/tab-bar"`); the drawer is `#drawer`. The correction
> repeated that, into four files, before an adversarial reviewer read the markup. And the
> remaining two were inert only in the STYLESHEET: neither `#nav` nor `#ptr` is ever GIVEN the
> attribute — not in `index.html`, not at run time, verified across all 83 named states — so
> nothing was ever appearing on screen because of this. What was true, and is what the fix
> answers, is that the remedy depended on somebody remembering to extend a list.
>
> Three readings of one defect, each drawn from what the reader had not opened, inside the entry
> that reports conclusions drawn from what was not read. Both are counted in § Guards green over
> what they do not read.
>
> **The fix is what this entry asks for and it also removes the list.** Preflight's remedy alone —
> `[hidden]:where(:not([hidden="until-found"])) { display: none !important }` — unlayered, in the
> base layer, without adopting preflight entire. The twelve hand-maintained cases are DELETED with
> it, because a list covers the names somebody thought of and that is exactly how `#nav` was
> missed. The oracle reads no divergence across that deletion, which is the statement that the
> twelve were doing nothing the one rule does not.
>
> **The second half was a design decision and the operator arbitrated it on 2026-08-26: the action
> button is taken away while a message is on screen.** Two alternatives were put with it — raising
> the message above the button, and shortening it on the right — and both were refused. The
> collision itself is now a measured hold rather than a claim: `elementFromPoint` at the close
> target's centre answers `#fab`.
>
> **One concern was raised before the choice and it is answered in the implementation**: a button
> that returns the instant a message closes is a target appearing under a finger still travelling.
> It returns only once the message has finished leaving, and never on a page navigation, where
> waiting would be a rendering change with no defect behind it.
>
> **The button's visibility has ONE decision point**, reading two facts — whether the page has a
> primary action, and whether a message is up. A second writer would erase the page's own answer
> and a page with no action would acquire one when a message closed; that case is a hold, and the
> mutation that introduces the second writer falls on it.
>
> **`data-shown` had SEVEN writers, and the commit that introduced the seam counted six.** The
> seventh dismisses the boot hint from a capture-phase `pointerdown`; it wrote the class alone and
> left the state saying a message was up. Found by an adversarial reviewer, who measured the
> consequence rather than deducing it: the primary « add » action absent for about four seconds on
> the first tap of every session, on the page that has one. R86 walked the close button and the
> timer, and both go through the seam — a path nobody drives is a path nobody measures. It drives
> that path now, and the mutation restoring the defect falls on it.
>
> **R86, mutation-tested five ways** beyond the two on the notes: the base-layer rule removed
> (falls on all five elements, on the probe and on the collision), the message decoupled from the
> button (falls), a second writer introduced (falls, naming the page that acquires an action), the
> button returned on the first frame of the fade (falls), and the seventh writer restored to
> writing the class alone (falls, naming the tap that leaves the state behind).

**B-083 — L08 landed and its design and plan stayed under `docs/features/`.**
Every lot from L01 to L07 sits under `docs/archive/features/`; `docs/features/` holds
`maquette-l08` and `tech-debt-2` and nothing else. The closing pull request (#504) did the other
two post-merge gestures — both references re-recorded at `ce1d7b5a`, verified ancestors of `HEAD`,
on `Darwin/arm64` — and left this one. **Third wave out of eight where archiving is the gesture
that slips**: the L06 audit had to do it retroactively, L07 did it in the move, L08 did not. A
gesture that is remembered two times out of three is a gesture that needs a check, not a reminder.

<sub>`ls docs/features/` · `ls docs/archive/features/ | tr ' ' '\n' | grep maquette`</sub>

> **FIXED by #505, the correction wave between L08 and L09** — `docs/archive/features/maquette-l08/`,
> with the three references that named the old path answered in the same step: two moved
> (`frontend-architecture.md` § L08, `IMPLEMENTATION.md` § Next action) and one REPLACED — B-084's
> own `<sub>` command, which pointed at a directory this entry had just emptied.
>
> **The operator arbitrated the remedy on 2026-08-26, and refused the guard this entry asks for.**
> Three shapes were put: a check reading § 4's `LANDED` markers and refusing a `docs/features/`
> directory for a landed lot; a wider check also covering § 7.1's deferred « a lot marked LANDED
> whose files do not exist »; and a step in the post-merge list. **The step was chosen.** It is
> now step four of five in `frontend-architecture.md` § 5, beside re-recording the references.
>
> **The objection is kept rather than tidied away, because it is this register's job to keep it**:
> that same list has been skipped three times out of four, so the remedy chosen is the one whose
> failure mode is already measured. What the step adds is that the count is now written next to
> it — whoever finds this gesture skipped a fourth time has a figure to argue with instead of a
> memory.

**B-084 — the wave that found the most wrote the least down.**
`BUGS.md` holds 78 entries on `main` after L08, the same 78 it held before. L08's own session
report enumerates roughly twenty findings: four value defects « no instrument could catch », five
the instruments did catch, six instruments that were wrong about themselves, and six faults the
agent declares as its own. **None of them is in this register**, and there is no `drafts/`
directory under the lot to hold them either.

**The precedent is one wave old and it was raised before the merge, not after.** The steward's
hand-off for L07 named this as correction 1 — « the register has not been touched, and the squash
will carry off what the wave found » — and L07 answered it with thirteen entries, several of them
`fixed #494`. The rule this register opens with does not exempt a defect because it was repaired
in the same wave: **reported is written down**, and a defect repaired in flight is precisely the
one whose recurrence nobody will recognise.

What is lost is not the repairs — those are in the code. It is the CLASSES: « a false name that
compiles » (an inverted integer pair claiming a series holds 175 episodes of 117; a field named
for a series carrying a broadcast status; a contract value holding the engine's rendered French,
lossily — « multi, vf, vostfr +1 » standing in for four items; a hash field answering with a
release name). Not one of those is findable today by anyone who was not in that session.

<sub>`grep -c '^| B-' BUGS.md` · `git log ce1d7b5a -1 --format=%B` — the squash body is the report of record</sub>

> **FIXED by #505, the correction wave between L08 and L09: thirteen entries, B-086 to B-098.** They are
> READ OUT of #503's squash body and of the four adversarial reviews it records, never invented —
> the commit message is the report of record, and it survives the squash that consumed the branch.
> The register held 85 rows before them and holds 99 after, B-099 included — and the entry's own
> opening sentence, written by the audit, says 78. That figure was already stale when it was
> written: `main` held 85 after L08. It is left as written, because § 7.1's rule is that a record
> is corrected by what is added beside it and never by editing the old text.
>
> **They are entered as CLASSES, which is what this entry says was lost.** « A false name that
> compiles » is four of them (B-086, B-089, B-090, B-091) and they are deliberately kept apart
> rather than folded into one row: a pair of integers in the wrong order, a field named for a
> series carrying a broadcast status, a contract value holding rendered French, and a hash field
> answering with a release name are four different ways for a name to be wrong while every type
> agrees, and a reader looking for the one they have just met needs to find it.
>
> **What is REPAIRED is `fixed #503` and what is not is `open`, and the distinction is not
> cosmetic.** B-090 is open: `Setting.value` still carries the engine's `displayedValue` — a
> rendered French summary, one of them lossy — and #503 recorded that, it did not fix it. Marking
> it fixed because the wave that found it merged would be the register lying about the code, which
> is worse than the register being empty.
>
> **The count itself is now a step**, not an intention: § 5's post-merge list owes the register the
> wave's findings at the same moment it owes the re-recorded references.

**B-085 — the same shape has appeared in three consecutive waves, and nothing counts it.**
« A guard is green because of what it does not read. » L07's adversarial review found it **six**
times, and named it the wave's own doctrine turned against it. L07-bis found it **five** more
(B-075), two of them inside the reader of the rule that wave was building — and recorded that the
seven-hold floor was a pre-satisfied counter *one wave after* the wave that named that trap. L08's
report lists **six** more: an extractor demanding a TypeScript install the runner lacks, a handler
guard not reading `state.ts`, a boundary arm refusing features but not the dying engine, a register
holding its names and not its classes, an oracle change with no rule at all, and an `isPureLiteral`
that never judged the node it was given.

**Seventeen in three waves.** Each was found, each was repaired, and each was recorded as an
incident of its own wave. **No figure anywhere carries the total**, so the shape reads as bad luck
three times instead of as the dominant failure mode of this repository's instruments — which is
what a count would have said after the first six.

This entry is the count. It is not a defect in one file: it asks for the figure to exist and to be
re-measured at each wave's close, the way every other figure here carries its command. A guard is
not proven by being written; it is proven by being read back — and « what does this guard NOT
read? » is the question that has paid for itself seventeen times.

<sub>L07: PR #494's review · L07-bis: B-075 · L08: PR #503's session report</sub>

> **THE FIGURE NOW EXISTS. It is § Guards green over what they do not read, below, and it is
> re-measured at every wave's close** — step five of `frontend-architecture.md`
> § 5's post-merge list, beside re-recording the oracle's references. Where it lives and who
> recounts it was the operator's arbitration, 2026-08-26; a line in § 6 of the architecture file
> was offered as an alternative and as a companion, and the register alone was chosen.
>
> **What the count is FOR, stated so a later reader does not mistake it for scoreboarding.** Each
> of the seventeen was found, repaired and recorded as an incident of its own wave, so the shape
> read as bad luck three times. A running total says the other thing: that « a guard is green
> because of what it does not read » is the dominant failure mode of this repository's
> instruments, and that the question to ask a new guard is **« what does this NOT read? »** before
> asking whether it passes.
>
> **The correction wave applied it to itself, which is the only evidence this entry can offer.**
> Three of its own instances are in the table — including one it had written that morning: R87's
> per-request hold made the served tree dirty between two requests and compared the answers, which
> on a tree that was already dirty distinguished nothing and passed. Found by asking the question,
> not by a gate.

---

**B-086 — a season tuple was declared in the wrong order, and a seed claimed 175 episodes of 117.**
Found by an adversarial reviewer of #503, and it is the worst defect that wave produced. The engine
writes `[number, aired, owned]`; L08's projection declared `[number, owned, aired]`. **No automatic
check could catch it**: no leaf moves, every type matches, and the lossless arm compares leaf VALUES
across a rename — so both readings are lossless and only one is true. Three independent
cross-checks agree on the engine's order: its own comment, the `INCOMPLETE` derivation, and the
count of episode numbers `owned` actually holds. Repaired in the wave that made it.

<sub>`git log ce1d7b5a -1 --format=%B | grep -n 'SWAPPED PAIR' -A 8`</sub>

**B-087 — a media sheet substituted one family's synopsis for another's, on 213 of 259 titles.**
Several of them in English. It is a **re-derivation**, which the projection contract forbids in
terms: a seed is a rename and a regroup of what the fixture holds, never a value computed from
another. The rule exists because a re-derived value renders plausibly and diverges silently.
Repaired in #503.

<sub>`git log ce1d7b5a -1 --format=%B | grep -n 'synopsis'`</sub>

**B-088 — twenty provider identities name TWO sheet keys each, and taking the first returned nine
empty season lists.** For the three shows a reader opens first. A one-to-many mapping read as
one-to-one: the code was right about the shape it believed in and the data had never had that
shape. Repaired in #503.

<sub>`git log ce1d7b5a -1 --format=%B | grep -n 'provider identities'`</sub>

**B-089 — `serie` is the show's RUN STATUS, and a rename read it as a series name.**
« Continuing », null for a film. The rename was mechanical and the name invited it. **Only reading
the twelve values found it** — the leaf check cannot see this class by construction, because the
leaf is the same leaf under either reading. Repaired in #503, and it is the archetype of the class
B-086, B-090 and B-091 belong to.

<sub>`git log ce1d7b5a -1 --format=%B | grep -n '`serie` is the SHOW'</sub>

**B-090 — `Setting.value` carries the engine's rendered French, and one of them is lossy.**
It is the engine's `displayedValue`: a summary RENDERED for a screen, not the value the setting
holds. **59 of the 159 fields differ from `String(raw)`, and two are lossy** — a four-element list renders
« multi, vf, vostfr +1 », so the fourth element is gone and no reader of the contract can get it
back.

**HALF OF THIS IS REPAIRED AND HALF IS NOT, and the halves are worth telling apart.** #503 renamed
the field to `displayedValue` and wrote the measurement into the contract's own description, so
the NAME no longer lies — that is the B-089 class, and it is closed. **The lossy value itself
stands**, and deliberately: L08's D-L08-5 says a pre-formatted fixture value is carried VERBATIM
and the underlying fact is asked for in `docs/reference/frontend-backend-demands.md`, because
decomposing it here would be a better contract and would forfeit the zero-divergence proof L09
rests on. Re-deriving the fourth element is the one thing forbidden outright (B-087).

**So the status is `open`**: the defect reported was a contract value holding rendered French,
lossily, and it still does. Marking it fixed because the wave that found it merged would be this
register lying about the code. It closes when the demand is served.

<sub>`grep -n 'displayedValue' frontend/maquette/design/src/mocks/contract-types.d.ts`</sub>

**B-091 — `grabForFollow` answered `infoHash` with a release name.**
A field whose name states its content, carrying something else entirely — the same class as B-089,
in a mutation's answer rather than in a read. Repaired in #503.

<sub>`git log ce1d7b5a -1 --format=%B | grep -n 'grabForFollow'`</sub>

**B-092 — four mutating routes changed nothing the next read could see.**
A maintenance run, a configuration write, a grab, and a pipeline verb that toggled instead of
transitioning. **The rule that should have caught them read ONE of sixteen mutating routes, and
the one that worked.** It reads five now, on five different subjects. Repaired in #503, and
counted in § Guards green over what they do not read.

<sub>`grep -n 'a mutation changes what the next read returns' frontend/maquette/harness/mocks.py`</sub>

**B-093 — `isPureLiteral` walked an initializer's children and never the initializer.**
So `const settle = afterUnwind` was judged a literal and then threw when read. **Seven « families »
were that shape.** It surfaced only when `--all` asked for every family at once; `--family` had
only ever been called on data already known to be good — a reader proven on the cases somebody
chose. Repaired in #503, and counted in § Guards green over what they do not read.

<sub>`grep -n 'isPureLiteral' scripts/extract-maquette-fixtures.mjs`</sub>

**B-094 — the register held its families' NAMES and not their classes.**
So a family moved from `served` to `interface` moved in one place and the tally beside it did not,
with every guard green. `$counts` is held against the classification now, and the anonymous
exclusion is a figure compared rather than printed. Repaired in #503, counted in § Guards green
over what they do not read.

<sub>`python3 scripts/check-mock-seeds.py --arm classification`</sub>

**B-095 — two families shipped UNPROJECTED while the builder reported success and lossless.**
The leaf-value check cannot see a projection that never ran: no leaf moves, so the two documents
compare equal. That limit is written beside the arm now, and the schema arm is what answers it.
Repaired in #503, counted in § Guards green over what they do not read.

<sub>`python3 scripts/check-mock-seeds.py --arm schema`</sub>

**B-096 — the contract was wrong about the data in five places, and the seeds proved it.**
`trailer` is a title and not an object, `runtime` is minutes and not a string, `tmdbTelevisionId`
is a string, recents carry no category, and `QueueCard`, `Follow` and `PendingDecision` each lacked
a field. Worth keeping as an entry rather than as a footnote: it is the direction of proof that
matters — the DATA corrected the CONTRACT, which is the whole reason the seeds are taken from the
fixtures instead of written. Repaired in #503.

**B-097 — twenty seed renames never reached the index, and only a case-sensitive runner saw it.**
macOS is case-insensitive, so git saw `ACCOUNT.json` and `account.json` as one file and reported
nothing to stage, while the runner's checkout carried the old names and none of the new ones.
`CLAUDE.md` names this trap for `git mv`; it applies just as much to a TOOL that writes the files.
Repaired in #503 with `git rm --cached` and a re-add, so the twenty appear as the renames they are.

<sub>`git config core.ignorecase`</sub>

**B-098 — the build plugin raced its own output and failed three jobs on a fresh checkout.**
`closeBundle` links the assets directory into `dist/` and assumed `dist/` existed. It does on a
machine that has built before; on a fresh checkout it exists only once the write has finished. The
race was invisible while the bundle was small and lost the moment it grew — L08 took it from
1.6 MB to 2.8 MB. The hook creates the directory it writes into now. Repaired in #503.

<sub>`grep -n 'closeBundle' frontend/maquette/design/vite.config.mjs`</sub>

---

## Guards green over what they do not read

**The count B-085 asks for.** « A guard is green because of what it does not read » — a rule that
greps a file whose subject has moved, a floor placed at today's value, a reader that never opens
the file the defect would live in, an arm that measured nothing and said so as success.

**Re-measured at every wave's close**, as step five of `frontend-architecture.md` § 5's post-merge
list. A wave that found none writes `0`, with the same authority as a wave that found six: a row
missing and a row saying zero are not the same statement, and this table is worthless if the
absence of a row can mean either.

| Wave | Found | Where it is written down |
| --- | --- | --- |
| L07 | 6 | PR #494's adversarial review |
| L07-bis | 5 | B-075 |
| L08 | 6 | PR #503's squash body — B-093 and B-094 write out two of the six; B-092 and B-095 are adjacent findings of that wave, not members of the six |
| L08-bis (#505, the correction wave) | 9 | itemised below · squash `12a134ca` |
| L09 | **14** | Recounted at the wave's close, and the count TREBLED between the gate and the merge — four adversarial reviewers ran before it, and nine of these fourteen are theirs. **B-105** and **B-106**, both found by mutation in the phases that wrote the instruments. **B-108**, the oracle itself — its `neutralise` broke the React tree and it recorded the damage as the reference, on four states of the exact kind this lot wires. **B-110**'s first attempt, which took three seeds out of the schema arm while the register claimed that arm held them. The **filters rule**, which read the FIRST listing in the cache rather than the active one. **B-121**, a gate vacuous where it blocks and moving where it does not. **B-122**, an arm that built a path by cutting it on the operator's own clone directory, so it could never match its own allowance list — two violations on CI, none locally, over an identical tree. **B-123**, a test that DERIVED a rule the application derives nowhere and then asserted the rendering that derivation produced, over a live production regression. **B-124**, one spelling of a store write out of three, defeated by a one-line wrapper already in the tree. **B-125**, an arm blind to `fetchNextPage` and to every layout effect — including in its own corpus count, which is the floor that is supposed to catch this. **B-126**, floors a third under the corpus. **B-133**, three rules of this lot's own making holding on something other than what they read. **B-134**, no arm reading what a HANDLER answers. **B-135**, three named states measuring the panel left open by the state before them, off screen, for as long as the reference has existed |
| Steward, between L09 and L10 (#511) | **1** | **B-150**, and it is the sharpest variant in this table: the size arm read the RIGHT file and asked the RIGHT question — « has the lot this label promises already landed? » — and got a stale answer, because the plan still called L09 `NOT STARTED` a wave after it merged. Four labels promised a reduction nobody owed and the guard reported clean. Found by removing the duplicated status, not by a gate: the fix for B-148 turned this one red |
| L10 | **4** | Recounted at the wave's close. **B-157**, and it is the plainest form in this table: R92 held « `lost` says what is wrong, and since when » by looking for the TIMESTAMP and the absence of « 4401 », so the mutation that made `lost` draw the RECONNECTING copy — the exact defect the rule names in its own docstring — passed. The tell was in the hold's own sentence: a hold containing « and » answers two questions and passes whenever the easier one is true. **B-158**, R94 walking a journey that cannot lose a scroll position — a screen overlays the page, `#port` is never unmounted, and the offset survives with or without any memory at all; measured with the defect restored, 300 px before, during and after. **B-159**, two instruments splitting a feature's `live.ts` on the WORD « Exemptions », whose first occurrence is the type import: the guard then read an import statement and printed « 3 refreshed addresses » out of 24, a confident number nobody could tell was short. And **R91's stated limit**, counted here rather than filed because it is the same species and it is permanent: the rule holds the IMPLEMENTATION against the DECLARATION, so a rule that declares the wrong key and invalidates that same wrong key is green — measured, by pointing `ItemProgressed` at the pipeline status and watching every per-rule hold stay green. What catches it is another arm, and the limit is written into the rule's docstring so nobody reads it as proving more than it does |
| L10, after the adversarial review | **9** | Seven reviewers against a gate green on every tier. **B-170**, R91 computing « nothing else » and never « everything it declares » — measured, `rule.keys.slice(0, 1)` silently stopped refreshing five addresses and all 57 holds stayed green — with a docstring claiming BOTH DIRECTIONS from the day it was written. **B-171**, R92 asserting five words the CSS removes at every width the frame measures, while the colour that replaces them was compared reconnecting-against-reconnecting: `lost: "bg-success"` passed all 25. **B-172**, R93 comparing only keys present in BOTH snapshots, so `queryClient.clear()` read as no movement. **B-173**, R89's four stream holds passing with zero sockets open, including the one named « resolves once the FAN-OUT has been issued ». **B-174**, R94's central hold green while a different page was on screen, in the rule rewritten because of B-158. **B-175**, a whole-cache invalidation counted as evidence the guard was working. **B-168**, an event corpus of six hand-written files with nine real events outside it. **B-169**, a `StrEnum` counted as an event, which inflated a total AND masked the dead rule naming it. And **R89's budget hold**, comparing two constants declared in its own file — a `quiet()` slower than the oracle's budget would have left every hold green while all 2 871 measurements were taken mid-flight |
| L10, after the SECOND adversarial review | **11** | Three reviewers on the repairs alone. **B-191**, R95's recovery hold a tautology whose own printed proof — a list ending in `reconnecting` — contradicted it. **B-192**, its « superseded socket » hold unable to produce one, because the fake removes a closed socket synchronously; nothing measured the identity guard until `pushStale()` existed. **B-193**, R92's colour hold a set of inequalities that a SWAP of two tokens satisfies. **B-194**, R94's layer hold never reading that a layer opened. **B-195**, R91's sibling seeded where it could never be an over-refresh. **B-196**, R95 certifying the shipped limits from a source literal rather than the running program. **B-197**, a stale hold-count baseline reporting three false regressions — which teaches whoever re-records to accept moved numbers, and that is how a count that FALLS goes through. **B-187**, `CACHE_WIDE` read line by line, so a wrapped whole-cache invalidation produced no violation AND no movement in the number printed as evidence. **B-188**, a poll regex that could not cross a semicolon and matched only the shape nobody writes. **B-189/B-190**, the exemptions reader keeping the defect the rules reader was repaired for, under a comment claiming the sibling instrument had been repaired too. And **R89's `> 1` threshold**, which could not tell one delivery plus one refetch from a delivery counted twice |
| L10, after the THIRD adversarial review | **8** | One reviewer, on round two's repairs. **B-200**, two repairs recorded `fixed` and absent from the tree — the register's own B-190 broken by the commit that filed it. **B-201** and **B-209**, a violation counter used before assignment and a count discarded two lines after being made, both invisible because the loop feeding them was empty. **B-202**, a cursor freeze no reconnect could thaw, under a docstring saying « until the connection is remade ». **B-203**, R91 merging every rule's sample so its verdict depended on source order and a predicate's deletion was invisible. **B-204**, R92 resolving the token through the same cascade that paints it — proving the dot uses the token and nothing more, so exchanging the two VALUES passed every comparison. **B-205**, nothing reading whether the dot is on screen at all. **B-208**, a disagreement between two oracles printed where it could fail nothing. And **B-213**, a poll reader adopting the wrong block for 545 bindings out of 925 |
| L10-bis | **20** | **11 counted at the wave's close, 9 more from repairing its review.** Of the first eleven, **ten are in instruments this wave was writing at the time** — which is the table's own reading of L09 arriving from the other side: the wave that builds the most finds the most blind, and it finds them in its OWN work. **The register's index** carried a status nobody could count, `fixed #NNN`, invisible both to « what is open » and to « what did that pull request close » (B-221). **The recorded oracle** was green over the add screen because no region resolved inside it: its three named states were driven, captured and compared against NOTHING, which is why B-139's white rectangle was invisible to it by construction (B-222). **Arm 5's first run returned six orphan variants where the entry named three** (B-223), and **B-138's own reference half was wrong** — the header avatar at 20x30 in a 32x32 button, every class on it correct (B-224). **The D1 arm matched no text at all**: a heredoc turned `\b` into a literal backspace, so it read 116 files and reported zero, and the mutation passed; it was found by printing the source line as BYTES, because a backspace is invisible in a diff. **The invariant-10 arm was wrong twice** — `\bword\b` cannot see `acquisitionLibraryMedia`, and lookarounds under `re.IGNORECASE` reject the very camelCase boundary they are written to accept — and its corrected reading is 124 where the first version said 53; **and with its comment stripper broken it collapsed to `0, 0, 0` and exited 0**, because every ceiling is a MAXIMUM and a reader that has stopped reading satisfies all of them at once. **B-041's green case failed**, so every mutation under it would have been measured against a red baseline. **R96 was written twice against stale DOM** — `.first` on an action reached a panel left by an earlier result, and asking whether a dialog was PRESENT found the closed one, because a closed layer is still in the document. **And a mutation missed its own instrument twice**: two attempts to fell the `generated` arm edited a `paths` key and a `paths` reference while the arm counts the `operations` interface. A mutation that misses what an instrument measures proves nothing about the instrument, and the honest move is to say so rather than to record a fall that never happened |
| L10-ter (the survey) | **5** | **1 found by the phase, 4 by its adversarial review — the L10 curve again, on a phase that wrote no instrument.** **B-228** — the brief's own inventory command, a spelling of one write out of the ways a script draws: it read twelve of thirteen and its figure had moved twice in a day; the survey's command reads every way and says what it does NOT read (descriptors, toggles) — which is how B-236 was found: ten producers no `innerHTML` grep can see. Then three readers on the finished phase: **the seams command** printed in the survey (`grep -on … \| sort -u`) could not count distinct names — it deduped line-prefixed matches and read 90 or 231 where the answer is 43, and the prose beside it said « twelve » and « 41 » in one clause; **two `served` rows of the clause map** rested on proofs that do not read their clause — `selection.py`, which PRINTS the delete dialog and asserts only that a sheet opens, and R67, a rule about PM2 processes, named for the pipeline controls that live in `arrivals.py`; and **the B-142 arm's specified regex** matched 24 clauses for 23, because §19's fourth point begins with a clause name. Seven verdicts moved from `served` to `partly` in the same pass |
| L15 (the frame) | **12** | **All twelve found by asking the question, none by a gate going red** — and eleven of them are in instruments this wave was writing, which is L09's reading arriving a fifth time. **B-246**, the version arm of the guard that holds the « In flight » row, defeated by markdown emphasis while every row of that table writes its pull request in bold — and its no-version branch exited 0 in SILENCE, so « this wave declares no version » and « I could not parse one » were the same line: none. **B-244**, the CI-filter hold asking « is this path named by ANY filter? » where the question is « by the filter that GATES THE JOB »; its two earlier cases were both fixed by adding to `maquette`, so the two questions had never yet had different answers — asked properly it goes red over **seven** guards, every one of them running in no job for a pull request touching only its own subject. **`boundaries_addressing`'s bracket search**, which found the empty pair of a TYPED declaration (`readonly NavigationRow[]`) and read an empty array — loud only because the caller has a « reads to nothing » branch at all. **R100's P1 hold, twice**: `performance.getEntriesByType("navigation").length` holds one entry PER DOCUMENT, so a full navigation makes a new document where the count is one again and the assertion cannot come out the other way; its replacement counted `framenavigated`, which fires for a `pushState` too — 63 over the 87 states with the property holding perfectly. **The tab bar's badge subscribed to NOTHING**: `acquisitionBadge()` reads the query cache synchronously and a synchronous read is not a subscription, so a badge showed the previous scenario's count until an unrelated store write redrew it — caught by `audit2.py`'s R16, an existing rule, and the reason it never bit before is that the engine's bar was rebuilt by `render()`, which the cache's redraw hook calls. **R101's B-237 hold, three times**: the named delete states raise dialogs of 184–660 and 142–702 against a bar at 787–844, so they DO NOT TOUCH and a hit-test of the dialog's own rectangle passed at 48 exactly as at 56; `inert` takes an element out of hit-testing as well as out of the focus order, so with the background inert `elementFromPoint` answered the dialog either way; and its selection-bar hold asserted over a bar that `lib-delete-multiple` does not put on screen. **R101's popover clamp** read the FIRST and LAST cell of a matrix that wraps, so both readings exercised the same edge and it reported the same placement twice. **B-250**, the stale-figure arm treating a hyphen as a separator, so `B-154` is a match the day the corpus reaches that size — and it then caught the first draft of its own repair saying « the corpus reached 154 files ». **`check-viewport-directives`'s split-literal blind spot**, found by the mutation that wrote `"maximum" + "-scale=1"`: the shape L07's split-class hold had. |
| L15, after the three adversarial reviews | **15** | Three reviewers on a wave whose every tier was green — the full suite at 75 rules, `--a11y` at 0, `make check` at 0, and the oracle at its 167 enumerated divergences. **Thirteen of the fifteen are in the wave's own instruments, and two are the ORACLE's blind spot read from the product side.** `page_host.py` held « every page in the table has an owner » by comparing `window.__pages()` against `window.__shellPages` — TWO EXPRESSIONS OVER THE SAME ARRAY, a tautology that could only fail by the seam being absent; it now drives every page and asks `#view` whether the host put anything in it. `page_host.py` again: its `#view` write detector read `view\.innerHTML\s*=` and nothing else, so `getElementById("view").innerHTML =`, `replaceChildren`, `append`, `insertAdjacentHTML` and any local alias passed — **and its own control was a literal written in the same file to match its own pattern**, a constant expression this very file warns against two hundred lines above; the control now splices two lines into a COPY of the engine and re-runs the same search. `stacking.py` PRINTED the confirmation's rank and the bar's and compared neither, holding only that they share a parent; and its message hold hit-tested inside the toast's own centre, which is true by construction — a message moved to `bottom-0 z-[60]`, squarely over the bar, would have passed it. `appearance.py` chose ONE appearance and reloaded once, leaving the pre-paint script's other two branches testing words nothing writes: the « repair applied to one branch of an `if` » shape, at the level of the walk. `exits.py` (R103) measured TWO layers of five, and the three it did not read — the message, the drawer, the confirmation — all still had B-249's defect. `boundaries_addressing.py`'s page hold said NOTHING when the navigation table's file is absent, so moving it to `app/navigation/index.ts` would have taken both directions away in silence. `persistence.py`'s focus hold read `dataset.page`, a `closest('#nav')` and « not body » — every one of which a REPLACEMENT node satisfies, in the rule written to catch replaced nodes, whose own header names `isSameNode` as the only question that separates them; and its one-document hold counted `load` events while a bfcache restore brings the sentinel back intact and fires `pageshow`. `selection.py` held its caption by digit SUBSTRING: « 0 sur 15 sélectionnés » satisfies a hold on « 1 », on the one surface whose job is to say how many things are about to be destroyed. `check-intent-map.py` gave `served, unproved` no obligation — the only verdict of five owing nothing — so rewriting fourteen `partly` rows to it empties the ledger and the guard prints « 0 violation »; and a named proof FILE was never checked to exist. `check-viewport-directives.py` read `frontend/maquette` without its `.py` files, leaving every harness rule outside the guard written to keep those two directives out of the tree. **And the two on the product side are the oracle's own limit, which is that it measures REGION ROOTS**: `.dlg p`'s `color` was one of four declarations and three were restated, so a confirmation's explanatory sentence read at full heading weight and the oracle — which does measure `color`, on `#dlg` — saw nothing; and `selectionAction` carried `bg-transparent` in its BASE with `bg-danger-fill` on the `danger` branch, two utilities of equal specificity where Tailwind emits colour alphabetically, so `transparent` always follows `danger-fill` and the destructive button rendered transparent with white text — **white on white under `data-theme="light"`, contrast 1.00** — while the light-theme audit stayed at exactly 166 before the repair and after it, which says the ratchet was not what was holding that surface |
| L11 (offline and the PWA) | **5 by the wave, 13 by four readers** | **The wave's own five were all found by MUTATING its rules, and two are the same rule going green twice over a shell that was not there.** R105 passed with the document deliberately dropped from the precache — the page had been loaded twice, so Chrome's DISK cache answered the reload after the server was gone. With the browser cache turned off it passed AGAIN: on the harness host `/offline.html` has no file behind it, the fallback folds it onto the document, and the worker's LAST-RESORT entry was a full copy of the prototype. **The consequence held while the mechanism was gone**, which is the difference between a rule and a coincidence. **R107 was silent about the client's half of « at least once »**: with the network up, an envelope forgotten BEFORE its request answered and one forgotten after are indistinguishable, so a client promising at MOST once passed eleven green holds. **R109 passed with the standalone check deleted from the application**, because in a desktop context the banner never appears anyway — « not offered » was « never offered ». And **B-258**, a Makefile announcing nine rules where `run.sh` held twelve. *(The wave first counted six here and included R105 CRASHING rather than naming its defect. A crash is RED; B-085 is « green because of what it does not read », so counting it inflated the figure in the flattering direction. It is repaired below instead.)* **THEN FOUR ADVERSARIAL READERS ON THE GREEN GATE RETURNED SOME FORTY MORE**, and the shape is L15's arriving on a wave that wrote BEHAVIOUR rather than conversions: the instruments were sound and the SUBJECT was not. A security regression — the cached shell outlived the session (B-261). An update discipline that reloaded without ever swapping the worker, and then never swapped again (B-262). A queue a refused replay jammed forever, over an optimistic write the server had rejected (B-263). **B-256 still open** through the two tools most likely to run beside a suite, one of them the tool that recorded this wave's own baseline. **R104 reading three substrings and never the comparison** — two survived on the assignment line alone. **`_code_of` stripping `#` and not docstrings**, so its own arm was satisfiable by moving an assertion's sentence into a docstring. **Five properties recorded as `false` that the wave had made true**, § 7.1's duty skipped. And **the coverage figures the register published as B-256's proof were stale the day they were written** — « 75 of 75 » was 79, in the entry that closes the finding about readings nobody can trust. **RECOUNTED BY THE STEWARD (2026-08-31): the readers' share of THIS table is 13, not « 40+ ».** The ~40, 13 and 7 of the four rounds are PRODUCT defects and belong to the rounds, not to this table, whose species is an instrument green over what it does not read. The thirteen, each named in this cell or in the archived report: B-256 left open through `mutate.sh` and `harness-hold-counts.py` · R104's three substrings · `_code_of` blind to docstrings · R104 satisfied by its own source · R111's queue hold that never queued · the corpus floors aimed at the loud corpora · `mutate.sh`'s lock leaked on the `set -e` path its comment claimed · the address pairing matching one end · R104 holding the wrong half after the repair · `_code_of` eating real code under two negative holds with no floor · the `INT` handler resuming past the released lock (B-256 re-opened) · round three's two repairs shipped with no regression hold · `mutate.sh`'s restore not idempotent under a comment asserting it. Excluded, and said so: the five stale `false` properties and the stale « 75 of 75 » — directive drift (B-243's species), not an instrument reading. **And the archived `REPORT.md` still opens its count with « Six for this wave »**: the cut to five and that sentence entered in the SAME squash (`39363e1d`) — B-239's shape, wrong the moment it was written — and the MECHANISM is on record (the wave's author, 2026-08-31): the report's correction was two `str.replace` calls whose patterns matched nothing, in an edit script where every OTHER change carried an `assert old in s` and those two did not, so they were silent no-ops reported as done — « une commande en échec est une édition qui n'a pas eu lieu », inside the very correction fixing figures nobody had compared. The archive stays frozen and this cell is the living correction. |
| **Total** | **173** | 130 by the waves through L11's own five, plus the four readers' 13 recounted above — at 2026-08-31, after L10-bis, its review, L10-ter's survey and its review, **L15 with its own review**, and **L11 with FOUR readers**. **L11's FIVE are the mutation half of the curve, and they say what mutation IS good for**: every one was found by breaking the wave's own rules on purpose, and two of them are the same rule going green twice over a shell that was not there. A rule can hold a CONSEQUENCE while the mechanism it names is gone, and only a mutation asks. **What mutation could not reach is the other forty**: four readers on that same green gate found a security regression, an update discipline that never swapped the worker, and a queue a refused replay jammed forever — none of them a defect the author had thought to break. The ratio is this table's oldest argument, arriving on a wave that wrote BEHAVIOUR rather than conversions: 5 by mutation, some 40 by reading. **And a second round on the REPAIRS found thirteen more, then a third found seven** — the two later rounds are where the sharpest findings are, not the first. Round two: the repair for a jammed queue had made a refused mutation vanish SILENTLY instead, and its classifier destroyed the operator's action on a 503, a 429 and a 401 — the very outage the queue exists for. Round three: that repair's own replacement still treated **401 as final**, so an expired session destroyed every queued mutation one after another when a re-login would have saved them all; and the notice's button said « Réessayer maintenant » while doing something else, because its name, its words and its action were written as three ladders that tested their conditions in different orders. **Each round's worst finding was in the previous round's repair**, and none of the three was found by a gate. **L12 adds 30 — 143 + 30 = 173 — and the addition is the itemisation's, not a counter's.** For two days this cell read 151 while the itemisation read 15 and `main` read 143, because the figure had been incremented ONCE PER REGISTER ENTRY FILED as B-271 to B-278 landed: 144, 145, … 151. Four of those eight entries are not units of this species at all, and the itemisation moved 6 → 14 → 15 without the total moving with it. A total that tracks a different quantity from the table under it is the drift this whole page is about, and it took an adversarial reader to do the subtraction. |
| **L12** (#540, this wave) | **30** | itemised below, one named unit per line with the proof that establishes it — the count follows the itemisation rather than the itemisation following a number. **Fifteen before the adversarial review and fifteen more from it**, which is this table's oldest reading arriving again: the sharpest findings are in the round that reads the previous round's work, and thirteen of the second fifteen are in instruments this wave had already repaired once |

### L12's fifteen, itemised

**One line per unit, each with what establishes it.** A count of prose is not a count: the steward
asked for this form before the review, and writing it moved the figure from fourteen to fifteen —
R112's tolerance hold had TWO independent causes of vacuity and had been counted once.

| # | The unit | What establishes it |
| ---: | --- | --- |
| 1 | **B-272** — the compositor manifest's floors carried slack its own `taken_at` denied; `touch-action` 8 against 11 real sites, three declarations deletable under a green guard | register entry B-272; measured by raising each floor until it fell |
| 2 | **B-274** — `page_host.py`'s state-alias arm read DOCSTRINGS as code and accused a rule that mutates nothing. B-085 with its sign REVERSED | register entry B-274; fixed with `ast`, verified both ways |
| 3 | The viewport guard's floors were counted AFTER its own summary printed, so a fired floor reported « 0 violation(s) » while exiting 1 | commit `fix(maquette-l12): the viewport guard's summary contradicted its own verdict` |
| 4 | R112's tolerance hold — its driver ramped the drift across the whole hold, so the 480 ms timer fired before the drift passed 12 px and the tolerance was never consulted | commit `test(maquette-l12): R112 measures the tolerance where it is measurable` |
| 5 | R112's tolerance hold, second and independent cause — under a real touch stream the tolerance is UNOBSERVABLE: the compositor cancels at every drift ≥ 14 px whether it exists or not, measured both ways at seven distances | same commit; only a real mouse isolates it, and the hold now asserts `pointercancel == 0` |
| 6 | R112's swallow hold could not fail — every `pointerdown` clears the mark, so a deliberate tap is never swallowed whatever the point check does | commit `test(maquette-l12): R112's swallow hold measures the case the point check decides` |
| 7 | R113's reduced-motion hold was satisfied by a stylesheet saying NOTHING — « nothing animates » is true of an absent rule | commit `test(maquette-l12): R113's reduced-motion hold reads the DESIGNED state, not an absence` |
| 8 | The page transition was DEGENERATE for six phases while R115 was green — it counted animations, and « a transition is RUNNING » and « a transition SHOWS THE PREVIOUS STATE » are different claims | commit `fix(maquette-l12): the page transition was DEGENERATE`; proved by a name existing on one side only |
| 9 | `:active-view-transition` was used to silence the hero's second entry and could not work — by the moment that animation starts the transition is over and the selector no longer matches | commit `fix(maquette-l12): one entry, one owner` |
| 10 | Removing only the Tailwind utility left `heroin` running — it was declared TWICE, as a utility and as a residue rule | same commit; re-measured rather than assumed |
| 11 | The transition option's selector carried a descendant combinator where the pseudo-elements hang off the root, so both arms of the comparison were identical | commit `feat(maquette-l12): the transitions are re-tuned above the perception threshold` |
| 12 | The priming hold was driven against a read that was never slow — `page.route` intercepts ZERO here because the mocks answer in the page | commit `feat(maquette-l12): A généralisée`; now drives `window.__mocks.setDefaultLatency` |
| 13 | The artwork's cached-versus-fetched discriminator raced `requestAnimationFrame` against `decode()` and answered `faded` on BOTH sides | same commit; reads `image.complete` synchronously now |
| 14 | **THE SHARPEST** — R115 held that the bar had a `::view-transition-group` of its own, which was TRUE, while its own stated principle « the hold is the GROUP, not a pixel » was what blinded it. The operator saw the defect and the steward filmed it one commit after the rule was written for it | **R118** (`harness/chrome_pixels.py`); its mutation reproduces the filmed defect at drift 51.9 of 255 against the steward's 52.1 |
| 15 | **B-276** — hand-set delays in an INSTRUMENT outlived the durations they were set against, twice in one rule (420 ms and 340 ms in `touch.py`) | register entry B-276; both repaired, the species left open |

### The criterion, stated once — and it admits both signs

**The species is an instrument whose READING does not decide what it claims to decide.** Not « green
over a defect » alone: a reader who trusts a printed verdict is misled in either direction, and the
cost of a false red — a defect report about code that was correct, and the re-architecture it nearly
bought — is not smaller than the cost of a false green.

**This was written the other way and the table already contradicted it.** The paragraph here said the
count admits only instruments green over a defect, and excluded the probe that truncated its own
evidence on that ground — while unit 2 (**B-274**, an arm that read DOCSTRINGS as code and accused a
rule that mutates nothing) is described in this very table as « B-085 with its sign REVERSED », and
unit 3 is a guard that printed « 0 violation(s) » while exiting 1. Two red cases in, one red case
out, one criterion. An adversarial reader applied the stated criterion and got 13 or 16, never 15.

So the criterion is the broad one, it is written here rather than inferred, and the probe is unit 16
below.


### The fifteen the adversarial review found, itemised the same way

**THIS TABLE WAS WRONG AT THIRTY BEFORE IT WAS RIGHT AT THIRTY, and the two corrections cancelled
— which is exactly the shape that hides a mistake, so it is written out.** A second adversarial
round applied the stated criterion to the table itself and found one unit in that does not belong
and one out that the register said was in:

* **OUT** — « the repair for B-281 created a second owner one frame later ». The hold written for
  B-281 went RED and named the defect: its reading DECIDED. That is an instrument working, and a
  defect in a repair — worth knowing, counted nowhere. It is recorded in that commit and in
  `REPORT.md` § 6f instead.
* **IN** — **B-289**, whose own entry says « a false red, and this register counts it » while no
  unit carried it: the table was frozen one commit before B-289 was filed and never re-opened. Two
  paragraphs of this page describe a counter that stops tracking the thing under it, in a page
  about counters that stop tracking the thing under them.

Thirty out, thirty in, and the criterion applied uniformly this time rather than by cancellation.

**Four independent readers on a wave whose every tier was green** — 86 rules, `--a11y` at 0,
`make check` at zero, the oracle at 2 958 with no divergence. **Thirteen of the fifteen are in
instruments this wave had already repaired once**, which is the reading the L11 row states and the
L15 row states before it: the round that reads the previous round's work is where the sharp findings
are.

| # | The unit | What establishes it |
| ---: | --- | --- |
| 16 | **The probe that truncated its own evidence** — eight rows read of ten running, which reported a defect that was not there and nearly bought a re-architecture | recorded in the R115 commit; admitted by the criterion above, which is the correction |
| 17 | R115's priming hold was green with `placeholderData` DELETED — it read the hero's TITLE, which `media-screen.tsx` derives from the route and draws whether or not anything primed, and `status === 'pending'`, which is true with or without priming | `49db0eb8` — « blocker I1 — the priming hold read the route's title, not the primed facts »; the hold reads the meta line while the cache is empty |
| 18 | `hold_one_entry_one_owner` only ever took the `faded` branch — every exercise opened a fresh context, so the fanart was never cached; the branch written for the operator's flash had never executed once, and the branch that did run was green over a second entry animation, because a second entry also dips | `9b61864a` — « blocker I2 — the branch written for the operator's flash had never run »; the warm branch pre-decodes the file in the same context |
| 19 | `check-feedback-seam.py` counted its own PROSE — the sentences describing the seam satisfied the floor the seam was supposed to meet | `bb26a681` — « I5/S4 — the seam guard read its own prose, and the pull never joined the seam »; comments stripped before counting |
| 20 | **B-279** — twelve contracts-tier guards run in no CI job when a pull request edits only the guard; the two existing holds both read a guard's SUBJECT, so the third question had never been asked | register entry B-279; the new hold falls over 11 of the 12 with the glob removed |
| 21 | R113's release hold read a node the panel's redraw had REPLACED — a brand-new tile is never pressed, so the hold answered « released » whatever the gesture did | commit `fix(maquette-l12): the press holds read the delay they wait on, and the node they pressed`; mutation reads `replaced: True` |
| 22 | R112's mouse hold laid 740 ms BY HAND against a press delay of 480 the design draws — B-276's species inside the file whose docstring says it removed that species | same commit; the mutation raises the delay to 900 and deletes the tolerance, and the hold still bites |
| 23 | R118 never established that a transition was CROSSING when its « in flight » sample was taken — delete `startViewTransition` and the two reads are two settled bars, drift 0.0, green over a transition that does not happen | commit `fix(maquette-l12): the two runtime probes establish the condition they measure`; reads `:active-view-transition` on both sides of the capture |
| 24 | R114 never established that a poster LANDED — an image that never arrives never pushes anything, so a broken fixture reads exactly like success | same commit; counts decoded posters across its own release |
| 25 | R114's « a poster box has its height » read the whole TILE, which carries a title and a subtitle under the picture: it held with the poster box deleted outright | `c51a1d7f` — « a cancelled pull is released, the commit hands back its navigation, three holds read the right thing »; the mutation deleting `aspect-ratio` now fells it |
| 26 | `touch.py` was the THIRD rule re-typing the press delay, in a wave that had already repaired two for it | same commit; reads `window.__gestures.press`, and a delay moved to 700 no longer fells it |
| 27 | R113 asserted a mark landed SOMEWHERE in the document — `feedback("commit", document.body)` satisfied every hold | same commit; the mark's target is held, and the mutation reads `tag: 'body'` |
| 28 | The faded branch's `min < 1.0` is satisfied by a FLASH exactly as by a fade, which is how **B-282** sat under it | register entry B-282; the hold now samples the cover and the element separately |
| 29 | « The media body's arrival is drawn » passed with `animation: body-rise …` DELETED — every view-transition pseudo-element gets the browser's own cross-fade by default, so « something animates here » is true either way | found by mutating the drawing the hold was written for; the hold reads the animation's NAME, and the mutation now reports `-ua-view-transition-fade-in` |
| 30 | **B-289** — `check-frame-domain`'s comment scanner opens a phantom string on a REGEX LITERAL holding a quote, so it read thirty lines of comments as code and reported two `media` in a sentence as domain words in the frame. A FALSE RED, and the criterion admits it | register entry B-289; `app/ 129` against `131`, and removing the newline branch brings 131 back

**The nine the correction wave found, since a wave that counts itself has to name its own.** The
figure is large because the count is honest, not because the wave was worse: four of the nine are
in instruments this wave WROTE, which is what a wave gets for asking the question of itself, and
four were found by the adversarial review — which is what the review is for.

1. **B-082's own entry** concluded that `hidden` was inert on five elements, having read the markup
   and the import list and not `base.css`, where an unlayered group already held three of them.
   **And the correction was itself wrong twice more**: it called `#nav` the navigation drawer (it
   is the tab bar), and the two remaining elements are never GIVEN the attribute at all, so
   nothing was ever appearing on screen. Three readings, each from what the reader had not opened.
2. **R87's per-request hold, in its first version**, made the served tree dirty between two
   requests and compared the answers. On a tree that was already dirty — every tree a wave is
   written on — both read `dirty: true` and the hold passed having distinguished nothing.
3. **R87's script-body hold did not exist**, and the obvious substitute would not have worked
   either: the corrupted payload PARSES as valid JSON, so a `json.loads` would have passed over a
   document whose only inline script had a syntax error and whose head carried live markup.
4. **R87 held « closing the message cannot reach the button » after holding the button was
   `display: none`** — an element at `display: none` is not hit-testable, so the second hold
   restated the first and could only fail if `elementFromPoint` returned nothing at all.
5. **R86 walked two of the three dismissal paths.** The close button and the timer both go through
   the seam; the capture-phase `pointerdown` that dismisses the boot hint does not, and that is
   the one that broke — four seconds without the primary action, on the first tap of a session.
6. **D3's « Neither may grow, both are held by a guard »** is half true. `legacy.css` is held;
   `harness.css` is held by nothing at all, and the only script naming it names it to EXCLUDE it.
7. **`check-no-french.py` named the maquette's Python one file at a time**, in five corpora across
   two files — so `host_identity.py`, split OUT of `serve.py`, inherited none of `serve.py`'s
   coverage and sat outside every arm on the day it was written. Replaced by a glob, which
   immediately found three French names in `oracle.py` that no arm had ever read.
8. **`check-mock-seeds.py`'s skip collapsed every extractor failure into « no TypeScript
   install »**, so a syntax error in the file its arms parse returned success with a confident
   wrong reason — and it skipped seven arms where three need the parser, leaving two written
   exemptions elsewhere resting on a check that read nothing.
9. **B-099's own two measurements.** `du` reported 0 bytes and proved nothing — the files had just
   been made sparse, so a run that deletes everything and a run that keeps 47 049 files both read
   as 0; the unit had to change to FILES. And the probe that first « proved » the retention policy
   ran with `rootdir` set to a scratch directory, never read `pyproject.toml`, and reported the
   default.

**The forms already met, kept as the question's checklist** — before writing a hold, ask what it
does NOT read, and whether that answer is acceptable:

- a counter placed at the current value, pre-satisfied, able only to catch a later decrease;
- an empty read that passes in silence, because « found nothing » and « looked at nothing » print
  the same;
- a corpus enumerated by hand, which goes stale the day a file moves;
- a hold armed on one of two ends, so the pair can drift while the hold stays green;
- a reader proven only on data somebody chose, never on everything at once;
- a figure printed and never compared.

---

**B-099 — a test pass writes 13 GB of real zeroes into `/tmp`, and pytest keeps three passes.**
Reported by the operator on 2026-08-26, in the hardest available form: the machine's boot volume
filled up mid-session and no command could run at all — the tool could not create its own output
file. 117 GB was cleared by hand.

**The mechanism, measured.** Thirty-eight fixture sites wrote a placeholder video with
`write_bytes(b"\x00" * 200 * 1024 * 1024)` — two hundred megabytes of REAL zeroes, allocated block
by block, one per movie or series a test builds. One `make test` pass left **13 GB across 47 049
files** under `/tmp/pytest-of-izno`. `tmp_path_retention_policy` was unset, so pytest's default
`all` kept the last three passes: ~39 GB steady state, growing every run. The comment above one of
those lines read « small but enough for tests ».

**What the tests need is the SIZE, never the content** — the library checks refuse a video under a
minimum, the disk cleaner acts above a threshold, and not one of them reads a byte. So the
placeholder is SPARSE now (`tests/_media_files.py`): `stat().st_size` answers the full figure, the
file costs one block, and a read returns the same zeroes byte for byte, so no test's meaning
changes. The small placeholders — a kilobyte, a thousand bytes — are deliberately left alone:
churn with no defect behind it.

**And the retention policy is the second half**, because the first half only holds for the
fixtures that exist today: `tmp_path_retention_policy = "failed"` keeps a temporary directory only
where it can still be read, which is a test that failed.

**Measured after, and BOTH first measurements were WRONG in the way this wave keeps counting.**
`du` reported 0 bytes and that proved nothing — the files are sparse, so a green run and a run
keeping everything both read as 0. Counted properly, by FILE: **47 049 files before, 0 after** a
full `make test`. And the retention policy had to be proven separately, because the probe that
« proved » it first ran with `rootdir` set to a scratch directory and never read `pyproject.toml`
at all — it reported `POLICY = all` when asked directly. Re-run from inside the repository: the
passing test's directory is gone, the failing test's is kept.

**What « 0 » does and does not cover, since the entry's own checklist warns against a figure nobody
compares.** The policy governs the per-test `tmp_path` fixture; SESSION-scoped directories from
`tmp_path_factory.mktemp` are outside it, and a run of two packages left twenty files and 136 kB
of them. That is a rounding error against 13 GB and it is not zero, so it is written here rather
than rounded away.

**And the sparseness stops at the source.** `rsync` re-expands a sparse file unless told not to,
and no capability's flag tuple carries `--sparse`, so the tests that really DISPATCH write dense
copies on the destination side — 315 MB for four of them. For those the saving comes entirely from
the retention policy. Both halves were needed; neither alone would have done.

**The pass is also a third faster** — 180 s to 105 s — because it is no longer writing gigabytes.

<sub>`python -m pytest tests/verify -q && find /tmp/pytest-of-izno -type f | wc -l` · `grep -n tmp_path_retention_policy pyproject.toml`</sub>
**B-100 — invariant 10 exists as a sentence, and this register knows what that is worth.**
Written 2026-08-26 with the operator: **the frame does not name the domain**, except in the three
tables whose job is to. It freezes a property that measurement shows is already true — `ui/` carries
one domain word across 1 162 lines, `lib/` only in `addresses.ts` and the dying `engine-drawing.ts`,
`app/` only in the three files that hold the list of pages.

**No arm counts any of it.** `CLAUDE.md`'s own line applies without softening: every rule has an
arm, or it is a sentence in a file — and this repository has watched exactly that happen to
`data-*` names, four of which simply stayed. The invariant is therefore recorded here as unarmed
rather than left to be discovered as such.

The shape of the arm is already in the repository, twice: `check-frontend-boundaries.py` reads the
import graph per directory, and `french-exemption-baseline.json` is the per-scope count that may
fall and never rise. This is those two, joined — a count of domain words per directory, outside
comments, refused upward.

**Two things it must NOT be**, both learned here at cost. It must not be an interdiction: a shared
component that genuinely needs a domain word should cost one reviewed line with its reason, the way
`code-vocabulary.txt` works, because a guard that blocks without a readable reason gets worked
around. And its baseline must not be seeded to the current value without being read — a floor set
where the count already sits is pre-satisfied and can never fall, which is B-075's shape, found
twice in two waves.

<sub>the measurement: domain-word count per directory of `design/src`, outside comment lines</sub>


**CLOSED by L10-bis. `scripts/check-frame-domain.py`, a ratchet per directory, refused upward.**
The vocabulary is DERIVED — it is the nine feature DIRECTORY NAMES, read from the tree, so a tenth
feature joins by existing rather than by somebody remembering this file. Comments are stripped per
line, and the entry's two requirements were kept: `frame-domain-baseline.json` carries the reason
each ceiling is not zero, and every number in it was read before it was written.

**MEASURED: `ui/` 0, `lib/` 16, `app/` 124**, over 10 047 identifier words. `app/`'s is the frame
naming its PAGES — `reference.d.ts`, `router-tree.tsx`, `page-host.tsx`, `shell.tsx` — which is the
exception the invariant blesses by name.

**THE FIRST TWO VERSIONS OF THIS ARM WERE BOTH WRONG, and the mutation found both.** Version one
matched `\bword\b` and walked straight past `acquisitionLibraryMediaCount`, which names three
domains and contains no word boundary at all — the way a domain word actually reaches the frame.
Version two used lookarounds with `re.IGNORECASE`, under which `[a-z]` matches capitals too, so the
lookahead rejected every camelCase boundary it was written to accept and the same mutation passed a
SECOND time. The arm splits identifiers into words now, which is what the rest of this repository's
name guards do. **The corrected reading is 124 in `app/` where the regex saw 53** — a ceiling
seeded from version one would have frozen an undercount and called it the invariant.

**And a third defect, found by the same route**: with the comment stripper broken the count
collapsed to `0, 0, 0` and the arm exited **0**, because every ceiling is a MAXIMUM and a reader
that has stopped reading satisfies all of them at once. A floor on the identifier words read is
what refuses it.

**What it does NOT count, said plainly**: the same thing § 3's prose counts. The invariant records
`lib/queue.ts` at **169**; this arm reads **16** there. That figure came from a broader notion of
« domain word » — the queue's whole subject vocabulary — while this counts the nine names, the only
vocabulary that can be derived rather than listed. The narrower measure is what a ratchet can hold
honestly.

<sub>mutation — add `acquisitionLibraryMediaCount` to `lib/relay.ts`: the arm falls with « 19
against a ceiling of 16 » and names the two files. Break the comment stripper to the `DOTALL` shape
that once reported 0: the corpus floor falls with « 0 identifier word(s), under the floor of 2000 ».
Remove the baseline: it refuses rather than assuming zero. Restored → `ui/ 0, lib/ 16, app/ 124 …
read from 10047 identifier word(s)`</sub>
**B-101 — a brief that told a wave what it would measure, and was wrong about it.**
The steward's hand-off for L08-bis stated, in bold: « **Cette vague VA faire bouger l'oracle** —
B-081 change ce qui est peint par défaut », and instructed the wave to expect a re-record and to
name every accepted divergence. **It could not move, and the reason was available before the brief
was written.**

The oracle captures with `html.measuring` on, and `harness.css`'s
`html.measuring .note { display: none !important }` was the ONE surviving rule touching `.note` —
a fact the steward had itself measured and written into B-081 the day before. The notes were
therefore absent from all 2 739 measurements and had always been. Restoring the hidden-by-default
pair aligns the judged document with the measured one **without changing the measured one**: the
oracle staying at zero IS the proof of the repair, not a surprise. Had it diverged, eye and
instrument would still be aimed at two documents.

**The failure is not the prediction; it is deducing where a measurement was one command away.**
The steward held both halves — the probe runs under `measuring`, and `measuring` hides `.note` —
and joined them into a forecast instead of into a check. That is the shape this register counts
under « guards green over what they do not read », applied to a person rather than a guard, and it
is the second time in two waves: B-082's five elements were read from the markup without opening
`base.css`.

**Why it belongs in the register rather than in a session's apologies.** A brief steers a wave: it
says what to expect, and an agent that expects a divergence looks for a reason to accept one. This
one did not — it measured and contradicted the brief, which is the outcome to want. The next brief
may be read by an agent that does not. **A figure in a brief carries the same duty as a figure in
the plan: the command that produces it, or it is not stated.**

Fix: no forecast of an instrument's behaviour in a hand-off without the command that establishes
it, the same rule § 0 of the architecture file already holds every figure to.

<sub>`grep -n 'measuring' frontend/maquette/design/src/styles/harness.css` · `grep -n 'measuring' frontend/maquette/oracle.py`</sub>

**B-102 — seven rows appear twice, with contradicting statuses, and the count reads them both.**
`BUGS.md` carries **108** rows and **101** distinct identifiers. B-079 to B-085 each appear once as
`fixed #505` — written by the correction wave that repaired them — and once as `open`, re-added by
#507 beside the two rows that wave was really filing.

**What it costs is the count, and the count is now a step.** B-085 made « recount at each wave's
close » the fifth post-merge gesture, and the first figure anyone reads to do it is the number of
rows. L09's own hand-off brief said « 108 entrées », which is what this register reports and not
what it holds.

**It is recorded and not repaired here, deliberately.** § 7.1's rule is that a record is corrected
by what is added beside it, never by editing the old text — and seven rows saying two things is
exactly the kind of thing an implementing wave should not silently tidy on its way past. Whoever
repairs it decides which status is true for each of the seven; six of them are plainly `fixed #505`
and B-085 is arguable, since what it asked for is a standing measurement rather than a repair.

<sub>`grep -c '^| B-' BUGS.md` → 108 · `grep -oE '^\| B-[0-9]+' BUGS.md | sort -u | wc -l` → 101 · `grep -oE '^\| B-[0-9]+' BUGS.md | sort | uniq -d`</sub>

**CLOSED by L10-bis, and the deliverable is the guard, not the deletion.** The seven `open` rows
are gone; which status was true was decided by reading the tree rather than either row, and the
entry above was right to say that decision belongs to whoever repairs it. **Two of the seven do not
say « FIXED by #505 » in their bodies** — B-079 and B-085 — so the brief that set this wave going
was wrong to say all seven did, and reading the tree is what settled them: `host_identity.py` was
split out of `serve.py` by #505 and `with_served_identity()` is called at `serve.py:735`, which is
B-079's fix landed; § *Guards green over what they do not read* exists, which is B-085's.

**The instrument — `scripts/check-bug-register.py`, four arms and one tool.** `duplicate-row`
refuses an identifier carrying more than one index row and NAMES it; `status-vocabulary` refuses a
status outside § *Status vocabulary*; `invariant-numbers` is B-103; `corpus` PRINTS the number of
rows read and refuses one below a floor of 150 — seeded well under the 214 rows standing when it
was written, never at them, because a floor set where the count already sits is pre-satisfied and
can never fall (B-075, met twice in two waves).

**It found a defect nobody had recorded, on its first run**: B-219 carried the literal status
`fixed #NNN`. That is B-221, filed rather than quietly corrected.

**What it does not read is written into the module, at the top, before what it does read.** It
reads the INDEX and never the bodies — so a row marked `open` over a body saying « FIXED by #505 »
is invisible to it, which is exactly the state these seven were in; it reads `BUGS.md` alone;
it cannot see another branch; and it does not hold rule 2's « exactly one `fixing` ».

**The recurrence this entry's neighbour really names is not a duplicate row**, and no guard can
hold it: two branches taking numbers from a register the other is writing. `--next` answers it by
removing the guessing, and it fails nothing — it is a tool, and the module says so.

<sub>mutation — duplicate a row with a different status: `duplicate-row` falls naming `B-101` and
both its lines. Write `fixed` with no number: `status-vocabulary` falls. Strip every index row:
`corpus` falls with « 0 index row(s) read, under the floor of 150 » instead of reporting clean.
Restored, then `python3 scripts/check-bug-register.py` → `207 index row(s) read … for 207
identifier(s)` · `check-bug-register: clean`</sub>

**B-103 — § 3 of the architecture file has two invariants numbered 10.**
#507 inserted « **The frame does not name the domain** » as item 10 and left « **No French in the
code and no interface text in the code** » numbered 10 below it. Both are binding, both are
called 10, and items 11 to 14 now sit one place away from every citation of them written before.

**It is not cosmetic, because the numbers are cited.** L09's hand-off brief instructed the wave on
« l'invariant 10 » meaning the new one; `docs/reference/frontend-architecture.md` cites « the
reduced-motion invariant » by name rather than by number in one place and by number in another;
and three « Where it lives (invariant 10) » lines were added to L10, L11 and L12 in the same
commit — those resolve correctly only if a reader stops at the first 10 they meet.

**Recorded, not renumbered.** § 7.1: the operator arbitrates this file and an agent proposes.
Renumbering it inside the wave that implements against it is the one moment it should not be done.

**CLOSED by L10-bis, and the repair is NOT the one this entry proposed.** Renumbering the sequence
— second 10 becomes 11, and 11 to 14 shift up — was measured before being taken, and it was the
wrong repair. It moves **ten live citations** (`harness/residue.py`, `harness/relay_states.py`
twice, `ui/variants/layout.ts` twice, `features/media/variants.ts`,
`scripts/check-maquette-unit-tests.py`, this register, and the architecture file itself) and it
**silently falsifies three archived documents**, which are frozen and must never be restyled —
`maquette-l05/plan/INDEX.md` cites invariant 11, `maquette-l07/plan/phase-09-library.md` cites 12,
`maquette-l10/DESIGN.md` cites 14.

**So the item that MOVED is the one whose number was wrong.** Every citation of « invariant 10 »
that exists — here, in the archive, in L09's DESIGN, in the three « Where it lives » lines — means
*the frame does not name the domain*. That invariant owns the number. « No French in the code » is
the one #507 left holding a number already taken, and it is now **15**, at the end of the list,
with the reason written beside it. Nothing cites it by number, so nothing moved.

**One sentence of the entry above is measurably false, and § 7.1 is why it is corrected here rather
than edited there.** « items 11 to 14 now sit one place away from every citation of them written
before » — they do not. The source numbers 11 to 14 were never shifted by the insertion, and all
ten citations resolve correctly today. The defect was real; that particular consequence was not.

**The instrument.** `scripts/check-bug-register.py --arm invariant-numbers` refuses a repeated
number AND a gap in the sequence — a citation of a number nobody wrote points at nothing, which is
the same defect seen from the other side.

<sub>mutation — renumber invariant 15 back to 10: the arm falls with « invariant 10 is written 2
times, at lines 497, 562 ». Number it 16 instead: the arm falls with « the sequence has a gap at
15 ». Restored → `check-bug-register: clean`</sub>

<sub>`grep -nE '^1?[0-9]+\. \*\*' docs/reference/frontend-architecture.md | sed -n '/^4[0-9][0-9]:/p'` · the two rows read `10.` </sub>

**B-104 — the generated contract types sit in `mocks/`, and they describe the contract.**
`design/src/mocks/contract-types.d.ts` is generated from `frontend/maquette/contract/openapi.json`
by `npm run generate-contract-types`. It is the CONTRACT's shape — what the interface may ask for
— and it is in the bucket L04 declared for « handlers and fixture seeds ».

**It surfaced as a gate failure rather than as a reading.** L09 phase 3 gave `lib/query-client.ts`
a path typed against the contract, so an address the contract does not declare is a compile error
instead of a 404 nobody sees until the surface is open. `check-frontend-boundaries.py --arm mocks`
refused the import, correctly by its own wording: only `app/` may import `mocks/`.

**What was done, and what was NOT.** The arm gained one narrow exemption — a TYPE-ONLY import of
that file — with the reason written beside it: a `.d.ts` carries no runtime value, a type-only edge
is erased by the compiler, and the defect the arm exists to refuse is a module reading a SEED so
that a fixture survives its own removal. Nothing can travel a type-only edge. A VALUE import of the
same file is still refused, proved by mutation.


**CLOSED by L10-bis. `mocks/contract-types.d.ts` is `contract/types.d.ts`, in a bucket of its own.**
It is the SHAPE of what the interface may ask for, generated from `contract/openapi.json`, and it
was filed in the bucket L04 declared for « handlers and fixture seeds ». It is neither.

**Five ends, moved in one commit**: the `package.json` generator target, `make
check-contract-types`, `check-mock-seeds.py --arm generated`, the boundaries guard's `GENERATED`
table and its `BUCKETS` list, and the five importers.

**AND THE EXEMPTION THE MISFILING FORCED IS GONE, which is the part worth more than the move.**
Because the file sat under `mocks/`, `lib/query-client.ts` imported from `mocks/` and the
boundaries arm had to be told a type-only edge to that one stem was allowed. That exemption's own
comment said « its placement is questionable » and « moving it belongs to its own change ». This is
that change. `CONTRACT_TYPES_EXEMPT` is now EMPTY rather than deleted, so the next module that needs
to reach into `mocks/` has to write its name there with a reason, in a diff somebody reads.

**The proof is the three instruments passing after the move, and they do**: `--arm generated` reads
54 operations against 54 with 0 disagreements at the new path; `make check-contract-types`
regenerates to `src/contract/types.d.ts` and `git diff --exit-code` is clean; the boundaries guard
reads **10** declared buckets with 0 files outside them and 0 forbidden edges into `mocks/`.

<sub>mutation — a module outside `app/` importing a SEED: the mocks arm falls with « 1 forbidden
edge(s) », which is what the emptied exemption had to be shown not to have weakened. Remove an
operation from the generated types: `--arm generated` falls with « 53 operation(s) in the types
against 54 in the contract » and NAMES `readAccount`. ⚠ Two earlier attempts at that second
mutation edited a `paths` key and then a `paths` reference, and the arm stayed green both times —
correctly, because it counts the `operations` interface. A mutation that misses what an instrument
measures proves nothing about the instrument, and saying so is cheaper than believing it.
Restored → all three green</sub>
**B-220 — the drawer and the bottom tab bar are converted by no lot of the plan.**
`design/index.html:451` declares an **empty** `<aside id="drawer">`; the dying engine fills it,
opens it, closes it, draws its entries (`#drawer a[data-navgo]`) and pushes its layer.
`index.html:436` declares an **empty** `<nav id="nav">`, and `renderNav()` fills it. On the React
side nothing renders either: `app/focus.ts` **watches** the drawer, `app/bar-height.ts`
**measures** the bar. The plan names the drawer once, in D1's address table, as an example of
screen state — and **L13's objective enumerates what survives subtraction** (the document-level
delegation, the boot, `/login`, the splash). Neither the drawer nor the tab bar is there.

**Why nobody saw it, and it matters more than the inventory.** Two instruments watch the engine and
**both measure its SIZE, never its surfaces**: the boundaries guard counts its lines,
`check-legacy-css-residue.py` counts its CSS rules. When L09 took `legacy.js` from 35 263 to 33 449
lines everyone read progress. A file that shrinks looks like a file that is dying, even when a
whole page never leaves it. It is **L14's class** — a surface whose conversion nobody owes — except
that here it is the application's main navigation.

**Its number changed three times before it was ever written down**: B-152, then B-160, then B-219,
each taken by a wave writing the register from another branch. B-219 went to #515 while this wave
was being briefed, which is the fourth. **Re-derived at the moment of writing** with
`python3 scripts/check-bug-register.py --next`, the tool B-102's repair ships for this exact
recurrence.

**Deferred to L10-ter, whose subject it is.** L10-bis records it and touches neither surface: a
correction wave opens no lot. **It changes nothing for E-002** — the React-side installer works
against the node as it stands, which is what makes that gesture feasible today.

<sub>`sed -n '448,454p' frontend/maquette/design/index.html` · `grep -rn '#drawer' frontend/maquette/design/src/app/` · `grep -in 'drawer' docs/reference/frontend-architecture.md`</sub>

> **PLACED, 2026-08-29 (L10-ter).** Both are the frame's chrome and both convert in **L15 — The frame**, inserted before L11 in `frontend-architecture.md` § 4. The survey widened the finding: the engine draws no page and no screen, and what it still draws is six frame surfaces, one feed and every panel producer (B-236). The two size-counting instruments are named in `MODEL.md` § 4 as what the clause map's arm must not repeat.

**B-221 — a wave merged leaving its own status as the literal placeholder `fixed #NNN`.**
Found by `check-bug-register.py --arm status-vocabulary` on its first run, against `main` at
`3316e550`. B-219's row read `` `fixed #NNN` `` — the placeholder from § *Status vocabulary*'s
example, written when the pull request had no number yet and never filled in once #515 merged.

**What it costs is every count that greps for a word.** `fixed #NNN` is neither `open` nor any
real `fixed #`, so the row is invisible to a count of what is open and invisible to a count of what
a given pull request closed. It is B-102's damage by another route: not a row saying two things,
a row saying nothing.

**It is the shape a correction wave produces most easily**, and this one is exposed to it: the
register is written DURING the wave (B-084), so its own closing rows are written before its pull
request has a number. The guard is what makes forgetting impossible rather than unlikely — the
status is filled the moment the number exists, or the gate is red.

<sub>repaired to `fixed #515` · mutation: write `` `fixed` `` with no number → the arm falls naming
the row and its line</sub>

**B-222 — the add screen is the only one of five overlay screens the oracle measures nothing of.**
Found while checking whether B-139's repair moved the recorded oracle. It did not, and the reason
is not that the repair was invisible: `regions.json` declared **33** regions and not one of them
resolved inside the add screen. Four of the five overlay screens carry a body region —
`screen-media/body`, `screen-profile/body`, `screen-releases/body`, `screen-resolution/body` — and
`features/acquisition/add-screen.tsx` carried **no `data-region` at all**.

**So its three named states were driven, captured and compared against nothing.** `acq-add-empty`,
`acq-add-results` and `acq-identify` are all three in the oracle's 87, and each contributed 33
measurements of regions that are absent from them. « Two » stood here through the wave that filed
this entry, and it is the same class of error as the entry itself: a figure written once, about
the very instrument being repaired, and never recounted against the reference. « No divergence » over that screen was an EMPTY READ, and B-139's white rectangle
was invisible to the oracle **by construction rather than by accident** — which is B-085's sentence
with « guard » replaced by « oracle », and the first time this register has caught the instrument
it trusts most in that shape.

**Repaired.** `data-region="screen-add/body"` rides the scrollport the screen already has, not a
wrapper of its own: a new block element inside a scroll container is a layout change, and this is a
measurement being added rather than a drawing being altered. The oracle now reads **34** regions,
2 958 measurements.

**This is NOT B-061 being relitigated.** That arbitration says the oracle keeps its contract — it
measures ELEMENTS, not pseudo-elements. Declaring a region on an element is inside that contract,
and it is what L10 did when it grew the oracle by three states without moving one of the 84
measurements it already held.

**What is still not held, and it is the sharp end**: nothing refuses a surface that declares no
region. The repair is one screen; the class is « an instrument's corpus is a list somebody
maintains by hand », and that list is `regions.json`.

<sub>`python3 -c "import json;print(len(json.load(open('frontend/maquette/regions.json'))['regions']))"` · `grep -c data-region frontend/maquette/design/src/features/acquisition/add-screen.tsx` → 0 before, 1 after</sub>

**B-223 — three more typed variants were orphaned, and B-139's own arm is what found them.**
`searchIcon` (`ui/variants/controls.ts`), `sectionTitle` and `sectionCount` (`ui/variants/layout.ts`)
each returned exactly one grep hit — their own declaration — on `main` at `3316e550`. B-139 named
three; the arm written for it returned **six**, which is the argument for building the instrument
rather than repairing the three.

**None of them was visible, and the difference from B-139 matters.** `.t` and `.k` are painted by
`legacy.css:382` and `:387`, and `.search svg` by `base.css:225`. So the screens are correct today
— and `.t` and `.k` are correct **only until L13**, when `legacy.css` dies and takes those two
rules with it, leaving two spans bare on every section header in the application. A latent defect
with a date on it.

**Repaired in two different ways, because they are two different things.** `sectionTitle` and
`sectionCount` are wired at their three literal call sites, which is what L13 will need anyway.
`searchIcon` is **removed**: `<Icon>` renders an `<svg>` and takes no class of its own, so nothing
could ever call it — `base.css` says exactly that in its own comment and sizes `.search svg` with a
descendant selector for that reason. A variant nothing can call is not a contract waiting for a
call site.

<sub>the arm is `scripts/check-markup-contracts.py`'s fifth, holding a HARD ZERO — 118 declared
variants across 9 files, every one named by at least one of 127 readers</sub>

**The PLACEMENT was what stayed open, and L10-bis closed it.** The move had five ends — the
`package.json` script, `make check-contract-types`, `check-mock-seeds.py --arm generated`, the
boundaries guard's `GENERATED` table, and its importers — and a rename with five ends belongs to
its own change rather than to the phase that first needed to import it. The file is
`contract/types.d.ts` now, in a bucket of its own, and nothing outside `app/` imports `mocks/`.

**The importers are FIVE, and this paragraph said four for the length of the wave that moved
them**: `mocks/state.ts`, `mocks/handlers/staging.ts`, `mocks/handlers/decisions.ts`,
`mocks/handlers/maintenance.ts` and `lib/query-client.ts`. Counting one end of a seam by hand and
writing the figure down is how the count was wrong in the first place — the same move as the
« twelve invocations » and the « two named states » corrected in this wave.

<sub>`grep -rn "mocks/contract-types" frontend/maquette/design/src scripts Makefile frontend/maquette/design/package.json`</sub>

**B-105 — the hold that names a defect, written so that the defect passes it.**
R89 (`harness/settle.py`) holds that `window.__mocks.quiet()` waits for a request the first one had
not issued yet — the waterfall, and the reason L08 made `releaseWaiters` a macrotask. **The first
version read `inFlight()` after quiet and expected 0. Both behaviours produce 0.** Released a task
later, the second request is already counted, so quiet waits for it and the count is 0 afterwards;
released inside the settlement, quiet answers before the second request exists and the count is 0
then too.

The mutation that removes the macrotask left the hold GREEN. What distinguishes the two is ORDER,
never a count: **did the second request FINISH before quiet answered?** It reads that now, and it
falls on the mutation.

**Found by mutating, not by reading** — and it is the hold that L09's whole proof rests on, written
in the phase whose stated purpose was to stop exactly this being discovered at the tenth surface.

<sub>`python3 frontend/maquette/harness/settle.py` — the hold « quiet() waits for a request the first one had not issued yet »</sub>

**B-106 — a ceiling above its own count, in the arm written to make that impossible.**
`scripts/check-state-ownership.py --arm server-state` holds invariant 4 as a count refused upward.
Its first version read the component tree alone — `app/ features/ lib/ routes/ ui/ mocks/` — and
reported **4** against a ceiling of **11**. A ceiling seven above its own count can never fall,
which is B-075's shape, in the arm whose own header names B-075.

**The eleven were measured across the whole tree, the engine included**, and the engine writes
seven of them. They are server state in the interface's bag whoever wrote them: components READ
`state.phase` and `state.pipe` regardless. The arm reads both now and holds the UNION, printing the
two shares apart.

**And a second ceiling had to exist, which the mutation is what showed.** A component writing
`pipe` — a key the engine already writes — left the union at 11 and the run green, while the
component share went 4 → 5. That is invariant 4 in its purest form, the interface copying server
state itself, and the union alone is blind to it.

<sub>`python3 scripts/check-state-ownership.py --arm server-state`</sub>

**B-107 — a restoration that silently did not happen.**
A mutation was applied to `scripts/check-state-ownership.py` and restored with
`git checkout -- scripts/check-state-ownership.py || true`. **The file was untracked**, so the
command failed, `|| true` swallowed the error, and the mutation stayed in the tree — the arm was
left reading five buckets instead of six.

Caught by re-reading the file rather than by trusting the command. « A failed command is not a
no-op — it is an edit that did not happen », read from the other end: here the edit that did not
happen was the RESTORATION, and the tree kept a change nobody intended.

**The remedy is the one the rule already implies**: a mutation is restored from a copy taken
before it, or from git only where git tracks the file — and the restoration is VERIFIED by reading
the target, never by the command's exit code.

<sub>`git checkout -- <untracked path>` exits 1 with « did not match any file(s) known to git »</sub>

**B-108 — the oracle measured its own damage, and four states were recorded as blank.**
`oracle.py`'s `neutralise` ran before each of its two passes and REMOVED every `.note` node from
the DOM. Those nodes are drawn by React components. On the next reconciliation React tried to
remove a child that was no longer its own and threw
`NotFoundError: Failed to execute 'removeChild' on 'Node'` — **22 times over the 83 states** — the
subtree died, and the surface rendered nothing.

**The reference recorded that nothing as the truth.** Four states, eight measurements, and every
one of them is a loading or an error surface:

| State | Region | Recorded | Really renders |
| --- | --- | ---: | ---: |
| `acq-now-error` | `acquisition/body` | 28 px | 162 px |
| `acq-now-loading` | `acquisition/body` | 28 px | 300 px |
| `arr-error` | `arrivals/body` | 28 px | 162 px |
| `arr-loading` | `arrivals/body` | 28 px | 230 px |

**The instrument was blind exactly where L09 needs it.** These are the states this lot exists to
wire, and the oracle would have proved them at zero divergence by comparing one blank against
another.

**The removal was also REDUNDANT.** `harness.css` carries
`html.measuring .note { display: none !important }` — restored by B-081 on 2026-08-26 — and the
oracle measures under `html.measuring`. The notes were already invisible to every capture. The DOM
removal added nothing and cost the tree; the entry's original reasoning (a note left in place
springs back to 75.6 px and pushes every region below it down) is answered by the CSS hide rather
than discarded.

**How it was found, and it is the method rather than luck.** L09 phase 4 converted six error
surfaces onto one component. Four measurements moved. The wave's own brief says a moved measurement
is named and explained before it is accepted — so it was, and the explanation was the instrument.

**The repair**: one entry gone from `probe.neutralise`, its reasoning recorded in its place, and the
reference re-recorded with the operator's arbitration. **8 measurements moved, 2 731 byte-identical**,
and on each of the eight only the HEIGHT changed — no x, no y, no width, no computed property, which
is the exact signature of a subtree that was rendering nothing and now renders. **R90**
(`harness/state_surfaces.py`, 30 holds) reads those surfaces by their own text and their own control
rather than by a rectangle, so an instrument's blind spot has a second reader instead of a wider
version of itself.

<sub>`python3 frontend/maquette/oracle.py --check` · 22 React errors measured by driving the 83 states under `html.measuring` with the removal in place, 0 without it</sub>

**B-109 — a retry that re-asks nothing, refused by the arm written three phases earlier.**
Phase 4 gave the library's error surface an `onRetry` that wrote `{ phase: "ready", libErr: false }`
and restarted the simulated load. `phase` is a SERVER-STATE key, and
`check-state-ownership.py --arm server-state` refused it: the component share went **4 → 5** against
a ceiling of 4.

**The arm was right and the change was taken back in the same phase.** No surface is wired to the
query cache yet, so there is nothing to re-ask; a retry that only writes the store is a half-fix
wearing the shape of a repair. The `onRetry` prop went with it — a prop with no caller is machinery
nobody can justify, and it belongs to the phase that gives that surface a query.

**It is written down because the count is what makes it real.** A guard refusing the wave that
wrote it is the arrangement working; a guard whose refusal is quietly worked around is the
arrangement failing, and only a register entry tells the two apart afterwards.

<sub>`python3 scripts/check-state-ownership.py --arm server-state`</sub>

**B-110 — the seed guard refuses a deletion the plan requires, and it was right to.**
L09's whole shape is D5: a surface is wired and its fixture is deleted from `legacy.js`. L08's
register holds the opposite rule, deliberately — « a family that disappears fails the guard too » —
because that is exactly right for an accidental deletion. On the first conversion the two met:
three families gone, `--arm classification` red, and the seed builder raising « the engine declares
no fixture family named 'DECISIONS_REGLEES' ».

**The gap was in the REGISTER, not in either instrument.** It could say what a family IS and not
that it had been converted. An entry now carries `converted`, naming the wave and the surface, and
three arms follow it: `classification` expects the absence and REFUSES THE REVERSE — a family
called converted that the engine still declares is a fixture that outlived its own removal;
`correspondence` prints what it can no longer compare rather than quietly comparing three fewer;
and the builder does not try to re-derive it.

**What holds a converted seed afterwards is the part worth writing down.** Its own literal is gone,
so `--arm correspondence` has nothing to compare it against — which is stated, per family, instead
of being absorbed. `--arm schema` still validates it against the contract, and the ORACLE holds the
rendering it produces at zero divergence, which reads the bytes all the way to the screen and is
the stronger of the two.

**And the first attempt at this made the claim false.** Excluding converted families from the
builder took them out of the SCHEMA arm too — 46 seeds validated became 43 — so the register said
« held by the contract's schema » while the code had stopped reading them. Caught by comparing the
printed counts before and after, which is the only reason it is not this wave's fifth instance of
guards-green-over-what-they-do-not-read.

<sub>`python3 scripts/check-mock-seeds.py` — `classification: 60 fixture(s) in the engine, 81 in the register, 21 converted, 0 out of step` · `correspondence: 25 seed(s) re-derived, 21 no longer re-derivable` · `schema: 46 seed(s) validated`. **These figures are the wave's CLOSE, not the day this entry was written** — it quoted `3 converted`, which was true for one phase and read as current for the eleven after it.</sub>

**B-111 — an edit replaced a span it had assumed rather than read.**
A stale comment in `legacy.js` named three fixtures that L09 had just deleted. The fix replaced the
text from that comment up to the next member it recognised — and six members sat in between:
`REASON_LABEL`, `REASON_TONE`, `REASON_DETAIL`, `DECISION_STATE`, `DECISION_STATE_DETAIL`,
`VIA_LABEL`. All six stopped being published on `window.__referentiel`, and the resolution screen
threw `Cannot read properties of undefined (reading 'superseded')` on every cold load.

**The contracts tier caught it in the same run** — `screen_addresses.py`'s hold (k) fell naming the
dead address, and the oracle reported `screen-resolution/body present=True -> False`. Repaired by
DIFFING against a copy of the file taken before the edit, and the audit was widened rather than
narrowed: every `const`, every `function` and every published member the whole subtraction removed
was listed, and it is exactly the three literals and their three publication lines.

**The lesson is the same one from the other end.** « Renaming needs a parser, not a regex » is
written in the plan's own trap table; an edit bounded by « from this text to the next thing I
recognise » is that trap wearing a different hat. The span was assumed; a diff would have shown it
in one command, and did.

<sub>`diff /tmp/legacy.bak frontend/maquette/design/src/engine/legacy.js | grep '^<'`</sub>

**B-112 — the library's sentinel watched a port it was not in, and a delay hid it for months.**
`LibraryList`'s infinite-scroll observer took its root from `document.querySelector("#port")` —
whichever port comes FIRST in the document. With a media sheet open over the library that is the
SHEET's port, so the footer counted as « in view » in a container it does not live in and the
sentinel asked for page after page nobody had scrolled to.

**Nothing showed it while the engine paced the loading.** Its loader waited 620 ms per page and
re-checked the store's version on landing, so a measurement taken before the first timer landed saw
a still list. Wiring the list to a cache that answers at once turned a masked defect into **46 402
px of list** where the reference holds 3 388 — the oracle's first reading of the wired surface.

**Two repairs, and the second is the one that mattered.** The root is now `foot.closest(".port")` —
the port the footer is actually in. And the observer is not set at all while the list is not on
screen: a surface showing a skeleton or an error has had nothing scrolled past it, and its footer
sits high in a short container, which is exactly where an observer fires.

<sub>`python3 frontend/maquette/oracle.py --check` — `shell/library-list` 3 208 px against 46 222 before the repair</sub>

**B-113 — a named state was reachable from a known STORE and an unknown CACHE.**
`window.__reset()` carries the sentence this whole arrangement rests on: « a measurement must never
inherit the mutations of a previous one ». It was true while every surface read a fixture. A
surface reads a query cache now, and a cache keeps what it holds — so driving one state after
another left the Médiathèque showing every page a previous state had asked for.

The cache and the mock layer's seeds go back with the world, in the same function, for the same
reason. **The alternative — each named state clearing what it happens to know about — is the
arrangement that produced this defect in the first place.**

<sub>`grep -n "window.__reset = " frontend/maquette/design/src/engine/legacy.js`</sub>

**B-114 — the listing answered one number to three different questions.**
`total` meant « what the library claims » when nothing filtered and « the size of the result set »
when something did. Three questions were being asked of it: how many rows does THIS question match
(what a page is a page of), how many does the source really hold (what the end mark says), and how
many does the library claim (what the count line says « sur »).

**Two of them broke, in opposite directions.** Paging compared the rows so far against `total`, so
on an unfiltered listing it waited for 1 861 rows from a source holding 345: `hasNextPage` stayed
true over empty pages for ever and the end mark was never drawn. And the end mark itself said the
FILTERED count, so under a search that matched nothing it announced « 0 titres réels » where the
prototype carries 345.

The answer declares `matching`, `loaded` and `total` now, each with what it is for written beside
it in the contract. R79's own hold moved with them: « the number it really has, not the library's
own total » compares `loaded` against the rows drawn and against the claim, which is what that
sentence always meant.

<sub>`python3 frontend/maquette/harness/library_load.py` — 8 holds</sub>

**B-115 — a redraw bridge that trusted a clock the instrument is allowed to stop.**
Surfaces the engine draws do not re-render when a query lands: `render()` writes markup once, from
whatever the accessors answered at that instant. `app/engine-redraw.ts` subscribes to the cache and
asks the engine to redraw — and its first version skipped events whose `dataUpdatedAt` it had
already seen.

**`dataUpdatedAt` is `Date.now()`, and the oracle measures under a FROZEN CLOCK.** Every landing
carried the same instant, so « skip what I have already seen » skipped every redraw after the
first. The discover deck measured **311.8 px** where the live page draws **4 497** — the instrument
saw an empty deck and the page was right.

**A timestamp is not an identity when something is allowed to stop time.** The dedupe is gone; the
bridge redraws on any update carrying data, which is idempotent and bounded.

<sub>`TM_ORACLE_NO_FROZEN_CLOCK` in `frontend/maquette/oracle.py` is the switch that made this
visible — the same measurement without it, and the deck drew</sub>

**B-116 — the inverse projection turned a sentence into an object of its own characters.**
A suggestion's `why` is a MIXED array: « Recoupé par », then `{emphasis: "4"}`, then « titres de
votre médiathèque ». The walker renamed the keys of every element, and `Object.entries` on a string
yields its characters — so each sentence became `{0: "R", 1: "e", …}` and the engine rendered
`undefined` in bold.

**Caught by R11**, which watches for exactly that word reaching the screen, and the oracle was green
over it: the deck's height did not change enough to move a measured rectangle. A unit test names it
now, asserting against the committed seed.

<sub>`python3 frontend/maquette/harness/audit2.py` — « R11 visible jargon or technical value »</sub>

**B-117 — the queue read served the dense world under the real scenario.**
`readAcquisitionQueue` answered `TAKEABLE`, `BLOCKED`, `IN_FLIGHT` and `DONE_TODAY` whatever was
asked for, while the engine's own `derived` answered EMPTY for the first two under the real
scenario and empty reels for the others. `readStaging` had the same shape one list over: it served
the dense `MOVING` where the engine had nothing moved yet.

**No surface read either route, so nothing said so.** L08 seeded them and L09 is the first wave to
ask. The two routes answer per scenario now, exactly as `derived` did — and « exactly » includes
the empties: a run that has just been read off the disk has moved nothing, and a layer answering
the dense lists there puts a queue on screen that no run produced.

<sub>`grep -n "scenario" frontend/maquette/design/src/mocks/handlers/staging.ts frontend/maquette/design/src/mocks/handlers/acquisition.ts`</sub>

**B-118 — the seed builder deleted twenty-one seeds the mock layer serves.**
`build-mock-seeds.py --write` deletes any seed file no family claims: « an orphan seed is a payload
nothing can re-derive », which is right. Since L09 a family is deleted from `legacy.js` the moment
its surface reads the layer instead (D5) — so it cannot be re-derived, `build()` does not build it,
and the naive reading of « not in built » became « delete the payload the mock layer actually
serves ».

**Measured: one `--write` removed twenty-one of them**, including every queue list, every decision,
the follows, the suggestions, the pipeline and the releases. Restored from git, and the builder
keeps a CONVERTED family's seed by name now — the same list the correspondence arm already reads.

**It was reached by a rebuild that had nothing to do with any of them**: adding one field to the
settings fixture. The most destructive thing a script here can do was one flag away from a routine
regeneration.

<sub>`python3 scripts/build-mock-seeds.py --write` · `git status --short frontend/maquette/design/src/mocks/seeds/`</sub>

**B-090 — the settings say the value they HOLD, and the lossy field is nobody's source.**
The panel read `displayedValue` — the engine's `v`, a French summary rendered for a screen. 110 of
the 159 fields differed from `raw` and two LOST information: a four-element list read
« multi, vf, vostfr +1 » and an eighteen-file list read « paths.json5, disks.json5,
categories.json5 +15 ».

**A pre-formatted French value cannot feed a control**, which is what made this unavoidable at the
surface with eight field kinds rather than merely untidy.

`features/settings/format.ts` says a value in the interface's own words, and its test asserts
against all 159 committed strings — extracted from `legacy.js` and held byte for byte against it,
which is the only non-vacuous oracle available for a rendering. **All 159 reproduce exactly.** The seven that
JSON cannot carry — `4` and `4.0` are one number — reproduce because the contract gains a
`precision` — added to the FIXTURE, so the seed carries it and no list of keys lives in a
handler where it would rot.

**WHAT IS NOT DONE, and it is stated rather than glossed.** `displayedValue` is still declared, now
`deprecated` and carrying its reason: no surface reads it, and it is what the formatter's test
asserts against. Removing it would leave that test with a golden written from its own output, which
is the vacuity this whole lot is built against. It dies with the fixture that produces it, at L13.

<sub>`cd frontend/maquette/design && npm test -- --run` — 57 tests · `grep -n deprecated frontend/maquette/contract/openapi.json`</sub>

**B-119 — a copy of the design root no longer builds, and the rule read a broken host.**
R73 boots the real `serve.py` on a scratch COPY of the design root, because a measurement must not
write into the operator's source. Since L09 that copy does not build: `engine/engine-shape.ts`
imports the mock layer's declaration from `frontend/maquette/`, one level ABOVE the design root —
a reach the boundaries guard names as a decision, and the only one there is until the engine dies
at L13.

**Every hold in the rule answered 503**, including the ones about sessions and portals that have
nothing to do with a build, and the rule reported a broken host where there was an incomplete copy.
A rule that copies a tree has to copy what the tree reads.

The copy is NESTED now, so a reach one level up lands where the import expects it, and what to carry
is found by READING the sources rather than by naming a file in the rule: a name typed there is a
second copy of the guard's allowance list, and it rots the day a second reach is allowed.

<sub>`python3 frontend/maquette/harness/switchover.py` — 11 rules, no violation</sub>

**B-120 — a journey rule read the verb of a panel the previous half had left open.**
`ident.py` walks two halves: identify a folder (« Associer »), then reach the same screen from the
« + » (« Suivre »). The second half opened nothing — the result row it clicks did not exist — and the
verb it printed was the FIRST half's panel, still on screen. The `?.` on the row click swallowed the
absence, so a journey that never happened reported a verb.

The panel is closed before the second half is read, and the two typing gestures are asserted rather
than assumed: `typed and typed_again and opened` reaches the verdict, so a gesture that lands on
nothing fells the rule instead of being carried by the one before it.

<sub>`python3 frontend/maquette/harness/ident.py` — VERDICT: identify != follow, and context picks the verb</sub>

**The follows fixture was one search behind the operator's own database, and had been on `main`.**
Not a defect of this lot and recorded so it is not read as one: `refresh-maquette-fixture.py --check`
answered « Star Trek: Strange New Worlds · searches: « 18 » vs 19 », and `main` held 18 too. The
guard now follows `FOLLOWS` to the seed it lives in since L09, and `--apply` wrote the measured
value. The rendering does not move — the two numbers are the same width — and the oracle confirms
it: 2 739 measurements, no divergence.

<sub>`python3 scripts/refresh-maquette-fixture.py --check` — no drift</sub>

**B-121 — a gate compared a committed seed to a counter the daemon increments.**
`make check` ran `refresh-maquette-fixture.py --check` as a blocking step. `searches` is the number
of times the acquisition daemon has looked for a followed show, so it goes up on its own: measured
19 when this wave's gate started and 21 when the gate reached that step, in one `make check`.

**And where it blocks, it verifies nothing.** CI has no `acquire.db`, so the script prints « no
database — nothing verified » and passes. Vacuous where it gates and moving where it does not is not
a check — it is the exact shape CLAUDE.md already names for `arrivals.py`: a rule that reads the
operator's live databases says nothing about the change under test.

It still runs and still prints in `make check`, prefixed `-` so its exit code does not gate, and
`--apply` stays the deliberate gesture.

**What it did NOT do, checked rather than assumed**: pointed at the deleted `FOLLOWS` array, the
tool as `main` holds it answers « refusing to report agreement about an array it could not find »
— the refusal its own tests were written to guarantee. It never reported a false agreement. What
made the drift visible again is that this lot moved the tool to the seed the family now lives in,
in the same step as the family; until then the step could only refuse.

<sub>`make check` — exit 0 · `python3 scripts/refresh-maquette-fixture.py --check`</sub>

**B-122 — a guard named a path by cutting it on the operator's own clone directory.**
`check-frontend-boundaries.py`'s `outside-imports` arm compares a module's reach against a list of
allowed reaches written repository-relative. To get that relative form it did
`target.split("PersonalScraper/", 1)[-1]` — the name this operator's clone happens to have. The CI
runner checks out into `torrent-mate/`, the split matched nothing, and every allowed reach was
compared as an ABSOLUTE path against a relative allowance: **two violations on CI, none locally,
over an identical tree**.

**A guard that answers differently by machine is measuring the machine.** It is the same class as
`arrivals.py` reading the operator's `library.db`, with the failure inverted: that one is red where
it should be silent, this one was green where it should have been red — the arm cannot have refused
a NEW outside import on this machine either, because no path it built could ever match the list.

The path is computed from the repository root now. **Proved under the other name**, which is the only
proof that means anything here: the tree was copied to `/tmp/torrent-mate-probe/` and the guard run
there — exit 0 with the repair, exit 1 with the old cut restored, naming
`/private/tmp/torrent-mate-probe/frontend/maquette/fixture-projections.json` exactly as CI did.

<sub>`python3 scripts/check-frontend-boundaries.py` — 0 violations · same script, same tree, under a
directory called `torrent-mate-probe` — 0 violations</sub>

**B-123 — the settings drew a cron expression raw, and B-090's own repair is where it came from.**
`settingInWords` has a `schedule` branch — 35 lines that say « toutes les heures, à la 15ᵉ minute »
— and nothing ever reached it. `page.tsx` passes `setting.type` verbatim, and the six cron settings
carry `type: "text"`. So the screen drew `15 * * * *`.

**The test agreed with itself.** It DERIVED a kind — « five whitespace-separated groups starting
with a digit or a star » — that the application derives nowhere, and then asserted the rendering
that derivation produced. A golden written from a rule only the test knows.

The kind of a field is a fact about the setting, so the FIXTURE carries it, like `precision` before
it: `type: "schedule"`, nine kinds in the contract's enum, a ninth named state so somebody can look
at one, and the test reads `field.type` like the page does. The control does not change — a schedule
is a text field — which is why nothing visual had ever revealed it.

<sub>`cd frontend/maquette/design && npx vitest run` — 94 tests · mutation: the kind removed from the
seed fells two holds, the precision removed fells two others</sub>

**B-124 — the invariant-4 arm read one spelling of a store write out of three.**
`WRITE_CALLS` matched `writeUiState\s*\(\s*\{`. So a write through a one-line local wrapper —
`function write(patch) { writeUiState(patch); }`, which was already in `add-screen.tsx` — was
invisible, and so was the ES6 shorthand `{ pipe }`, which is the canonical form. Proven by mutation:
a component writing two named server-state keys plus an unclassified one passed, exit 0, under a
component ceiling of ZERO.

**And the arm's central promise was already false**: `addKind` and `idProv` were on neither list, so
« a key cannot arrive unclassified » had been broken before anyone tried. The arm reads the call, not
the call-and-brace; anything whose keys it cannot read it REFUSES; and the one module that
implements the write is named, because a seam necessarily forwards a patch it did not compose.

<sub>`python3 scripts/check-state-ownership.py` — clean · three mutations (alias, shorthand,
unclassified key) each fell, naming its own defect</sub>

**B-125 — the invariant-5 arm did not know `fetchNextPage`, nor count a layout effect.**
`\bfetch\s*\(` does not match `fetchNextPage(` — the bracket the pattern wants is an `N` — so the
commonest read in a paged surface was outside the arm entirely. And `useLayoutEffect` does not
contain `useEffect`, so those bodies were neither read NOR COUNTED: the corpus floor, which is the
arm's whole defence against reading nothing, was under-reporting by a fifth on the day it landed.

**What the repair had to get right, and it is the interesting half**: a read WRITTEN in an effect's
body runs when the effect runs — that is the invariant. A read inside a callback the effect merely
REGISTERS runs on a gesture, and refusing it would forbid infinite scrolling. So the nested functions
are blanked before the body is read.

<sub>`python3 scripts/check-state-ownership.py` — `effect-fetch: 7 useEffect call site(s) read, 0
violation(s), corpus floor 5`</sub>

**B-126 — the unit-test floors sat a third under the corpus they guard.**
`TEST_FLOOR = 36`, `FILE_FLOOR = 2`, against 4 files and 58 tests. Deleting `router.test.ts` — the
whole proof of the mock routing — left 3 files and 47 tests: both floors clear, guard green, exit 0.
The docstring says « the floor is raised in the commit that adds tests »; the commit that added
twenty-two did not raise it. The floors are the corpus now, and the mutation fells them both.

<sub>`python3 scripts/check-maquette-unit-tests.py` — `5 file(s), 93 test(s) (floors: 5, 93)`</sub>

**B-127 — a search matching nothing said « 0 résultat affiché sur 257 trouvés ».**
`searchProviders` recomputed `shown`, which no surface reads, and spread `total` through untouched,
which the screen reads for its denominator. So a query the provider cannot answer drew an empty list
under a line claiming 257 — a screen saying « nothing » and « 257 » in one sentence.

It is the same defect the library listing was repaired for two files away, in the same wave:
« answering 1 861 over a search for two rows made the count describe the library rather than the
answer ». Fixed there, reproduced here, one directory apart.

<sub>`cd frontend/maquette/design && npx vitest run src/mocks/contract-conformance.test.ts`</sub>

**B-128 — the release picker was title-blind, and its cache key with it.**
The contract declares `title`, `season` and `episode` on `/api/acquisition/releases`. The handler
took none of them and the query key carried none either, so opening the picker for one medium and
then for another drew one list — and the second came from the cache without a request being made.
A release list that does not depend on what it is a list OF is not a list.

The handler reads all three, matching season and episode against the `SxxEyy` in the release NAME,
which is where a release carries them — reading them off a field the seed does not have and falling
back to « it matches » would leave both parameters accepted and ignored, which is the defect itself
wearing a repair's clothes.

<sub>`python3 frontend/maquette/harness/screen_addresses.py` — 50 rules, no violation</sub>

**B-129 — the library count line printed a literal beside the number it was served.**
`const universe = category && category.of ? category.c : 1861;` — three lines under a comment saying
the count comes « from the same query the list reads, so the two cannot disagree ». The query
answers that number. Change the seed and the screen went on saying 1861.

<sub>`grep -n "1861" frontend/maquette/design/src/features/library/page.tsx` — no match</sub>

**B-130 — discarding a staged medium walked one list out of three.**
`discardStagedMedia` filtered `stuck` alone; its sibling `continueStagedMedia` walks `stuck`,
`stuckLoaded` and `blocked`, with a comment explaining why. So a card served from the dense world was
asked to be discarded, nothing was removed, `{ok: false}` came back and the card stayed. Latent only
because the operation is orphaned — no surface calls it — which is the second half of the finding.

<sub>`rg -n "FROM_REAL, FROM_DENSE, FROM_BLOCKED" frontend/maquette/design/src/mocks/handlers/staging.ts`</sub>

**B-131 — a listing parameter, a served resource and a hook, none of them read.**
Three things declared and unread: `lens` on `/api/library/items` (sent by nobody, read by nobody),
`useLibraryRecent()` (added by this wave, called by nobody), and the register's claim that the
« récent » lens « draws the listing in the source's own order » — it draws the shared listing in
whatever order the sort control last set, which is what it drew before the wave too.

`lens` is struck from the contract, the hook is deleted, and the register entry says what is true:
the resource is served and NO SURFACE READS IT. A lens meaning « les derniers ajouts » would read it,
and that is a design decision rather than a wiring detail.

<sub>`python3 scripts/compare-contracts.py --check` · `python3 scripts/check-mock-seeds.py`</sub>

**B-132 — the inverse projection threw, or converted, on shapes nobody declared.**
B-116 was one of these: a string reaching a `*` path and coming back as an object of its characters,
drawn as `undefined` in bold. Its repair stopped at the terminal level and never reached the walk,
which still had three siblings — a `null` where a list is declared threw
« Cannot read properties of null (reading 'map') » INSIDE a `queryFn`, so the surface drew an error
naming nothing; and `Object.entries` over an array answered an object keyed "0", "1", …

The seeds are not the only input any more — handlers compose payloads and the contract has nullable
fields. Three regression tests, each seen red against the code as it stood.

<sub>`cd frontend/maquette/design && npx vitest run src/engine/engine-shape.test.ts` — 18 tests</sub>

**B-133 — three new rules held on something other than what they read.**
R89's budget hold compared `HELD_BACK_MS < ORACLE_QUIET_BUDGET_MS`, two constants declared in the
same file, beside a comment saying they were named there « so the two cannot drift silently » — the
oracle's own number was never read. R90 carried a comment about React errors, written FOR B-108,
with no `pageerror` listener anywhere in the file. R88 read a probe into a variable, printed it in a
message, and held on something else entirely.

R89 reads `NETWORK_QUIET_BUDGET_MS` out of `oracle.py` and refuses to run if it cannot find it; R90
collects the errors; R88 holds on the probe it reads.

<sub>mutation: the oracle's budget set to 100 fells R89's hold · `python3 frontend/maquette/harness/boot_order.py` — 20 rules · `state_surfaces.py` — 31 rules</sub>

**B-134 — no arm read what a HANDLER answers, only what a seed holds.**
`check-mock-seeds.py` says it in its own words: « handlers, so a handler ignoring its seed passes
here ». A composed payload touches no seed, so the two fields this lot added to the listing were held
by nothing but the surface that happened to read them. Drop `matching` and `getNextPageParam`
compares `held < undefined`, which is false — the list ends after one page under an end mark saying
the library is exhausted, with every guard green.

`mocks/contract-conformance.test.ts` holds every declared response's REQUIRED properties against what
the handler answers. Deliberately narrow: not types, not formats — a full validator would be a second
implementation of the contract, and the value is in the one question nobody was asking.

<sub>mutation: `matching` dropped from the listing → « readLibraryItems is missing matching »</sub>

**B-135 — three named states measured the panel left open by the state before them.**
`settings-read-only`, `settings-restart` and `settings-secrets` open no panel. `#sheetin` is a
persistent node that keeps its content after closing — deliberately, so a panel does not flash empty
as it slides away — and the oracle measures the region whether it is on screen or not. Those three
were therefore recording, at y=867 and invisible, the height of whichever FIELD the state before them
had opened.

**It surfaced because adding a ninth field state moved all three by 51.6 px** without touching a line
any of them draws. Isolated by measurement, not by reasoning: reverting the data changes alone left
2 739 measurements identical, and reverting the STATE alone was what moved them.

**What was NOT done, and why.** Two repairs were written and backed out — closing the layer in
`resetSettings`, and clearing the descriptor — because measurement showed neither changed anything:
the panel is already closed for those states. Adding unproven behaviour to the dying engine is the
machinery-nobody-can-justify this repository has paid for before. The reference is re-recorded, and
the weakness is named here: a region measured while its layer is closed describes the previous state.

<sub>`python3 frontend/maquette/oracle.py --check` — 84 states, 2 772 measurements, no divergence</sub>

**B-136 — B-090's headline figure counted quotes, and it had reached the contract.**
« 110 of the 159 fields differ from `raw` » was measured with `JSON.stringify`, which counts the
quotes around a string as a difference. The value is **59**, by the method the design document itself
states. The dependent figure — « the other 95 differences are reproducible » — was wrong with it.

It sat in six places, and two of them SHIP: `frontend/maquette/contract/openapi.json` and the
generated `contract-types.d.ts`. A figure quoted in a contract description is read by everyone who
reads the contract.

And « 152 reproduce exactly, the seven that do not are what JSON cannot carry » was stale in the other
direction: the seed already carried `precision`, so all 159 reproduce — the test was excluding the
seven it was written for.

<sub>`node -e "…String(f.raw) !== f.displayedValue…"` — 59 of 159</sub>

**B-137 — four ACCEPTANCE criteria could not run, or expected the wrong answer.**
ACC-05 and ACC-06 named `check-frontend-boundaries.py --arm server-state`, which exits with
`invalid choice`: both arms live in `check-state-ownership.py`, a separate file by this lot's own
decision, and the criteria were written before the split they describe. ACC-05 also expected « ending
at 0 » for a union that is 7 — the number that must be zero is the COMPONENT share. ACC-07 expected
0 `displayedValue` and the answer is 2, by a decision taken after the criterion. ACC-12 counted
`__referentiel`, which is how every engine-drawn surface gets its markup and cannot reach 0 while the
engine draws anything.

**Amended in the plan, with the amendments written out as the finding** — a criterion quietly edited
to match what happened proves nothing. And what is NOT amended is stated: the lot's `Done when` says
« the fixture literals are gone from the engine », and 60 families remain against 21 converted. That
gap is L13's subject and it is recorded as open rather than reworded away.

<sub>`python3 scripts/check-state-ownership.py --arm server-state` · `python3 scripts/check-mock-seeds.py --arm classification`</sub>

**B-138 — the same component converted twice, once whole and once half, and the half nobody measures.**
Reported by the operator on 2026-08-26 from a live phone: opening the user sheet from the header
avatar paints the image at its natural size. It covers the name, the address and the « Profil et
préférences » entry underneath.

**Before L07**, `refonte.html` carried the component in three rules:

    .avatar     { width: 32px; height: 32px; border-radius: full; background; color; … }
    .avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; display: block }
    .avatar.big { width: 42px; height: 42px; font-size: var(--text-6) }

**Today no `.avatar` rule survives in any stylesheet** — `grep -rn '\.avatar' src/styles/*.css`
returns nothing. The two call sites were converted differently:

| | Container | The `<img>` inside |
| --- | --- | --- |
| header (`index.html:193`) | all of `.avatar` — size, `rounded-full`, `bg-muted`, `grid place-items-center` | `w-full h-full object-cover rounded-[inherit] block` — all of `.avatar img` |
| panel (`ui/panel/index.tsx:221`) | `sheetAvatar()` = `big w-[42px] h-[42px] text-6` — only what `.avatar.big` ADDED | **no class at all** |

`sheetAvatar` converted the modifier and assumed the base would come from somewhere. It does not.
So the panel's container has a size and no shape, and its image has nothing — which is precisely
what the screenshot shows, a square that overflows.

**And the class `avatar` is still on both**, now an identity anchor that styles nothing. A class
that looks like it paints and does not is the shape `regions.json`'s `$vocabulary` exists to keep
honest.

**Why 2 739 measurements did not see it, and this is the finding worth more than the defect.**
The state EXISTS and is measured: `engine/states.js` declares `sheet-user` — « Menu utilisateur —
profil et déconnexion » — driven by `openUserSheet()`, and `regions.json` covers it with
`shell/sheet-content` → `#sheetin`. The oracle visits this surface at every run.

**It reads the container.** D8's probe takes a bounding rectangle and 19 computed properties **of
the region's own element**, which here is `#sheetin`. The avatar is a descendant, and a descendant
painting at the wrong size changes neither of those. This is the limit D8 records — written on
2026-08-25 for pseudo-elements (B-061) — reaching the same way through ordinary CHILDREN, which
that paragraph does not say.

So the gap is not coverage, it is depth: a region can be visited at every run, for months, while
what is wrong inside it is structurally outside what the probe returns.

Fix, in two halves: restore the base and the image rules for BOTH call sites — the header already
proves what the full set is — and decide what holds a descendant. A named rule reading the image
the way R26 reads a pseudo-element is the shape that exists; widening the probe to children is the
other, and it is D8's arbitration, not this entry's.

> **THIS ENTRY'S FIRST DIAGNOSIS WAS WRONG, and it is kept here because the way it was wrong is
> the point.** It read « no named state opens it », concluded from `regions.json` — which holds
> regions and not states — without opening `engine/states.js`, where `sheet-user` has been declared
> all along. **Third time in three waves** the same office has concluded from the one place a fact
> ought to live: B-082's five elements (`base.css` unopened), B-101's oracle forecast
> (`html.measuring` unjoined), and this. Counted in § Guards green over what they do not read,
> where it belongs: the failure is identical whether the reader is a guard or a person.

<sub>`grep -rn '\.avatar' frontend/maquette/design/src/styles/*.css` · `git show 5fdbfc9a^:frontend/maquette/design/refonte.html | sed -n '505,525p'` · `grep -o '"sheet-[a-z0-9-]*"' frontend/maquette/regions.json`</sub>

**CLOSED by L10-bis, and the entry's second half chose the route it proposed.** A named rule
reading the image — `harness/avatar.py`, R97 — the way R26 reads a pseudo-element. The probe is NOT
widened to children: that is D8's arbitration and B-061 settled the equivalent one the other way.

**MEASURED BEFORE IT WAS REPAIRED, on `sheet-user`**: the host declares 42x42 and the image
rendered at **128x128** — its natural size — with `object-fit: fill` and `display: inline`. The
repair is `avatarImage`, a variant carrying the base the header already proves, so the two ends
read one declaration instead of two spellings of it.

**AND THE HALF THAT WAS SUPPOSED TO BE CORRECT WAS NOT.** The header's image carried the complete
class set and rendered **20x30 inside a 32x32 button** — a `<button>` keeps the platform's own
padding, so `w-full` resolved against a content box the padding had already shrunk. Every class was
right and the result was a small oval. That is **B-224**, found by measuring the reference half
rather than trusting it, and it is why R97 holds BOTH: a rule holding only the panel would go green
over a fix that traded one avatar for the other.

**THE ORACLE DID NOT MOVE, and that is the entry's own claim confirmed rather than assumed.** Both
avatars changed size — 128→42 and 20x30→32x32 — and the recorded oracle reported **zero
divergence** across 87 states and 34 regions. The panel's avatar is a descendant of `#sheetin`,
whose twenty numbers are unchanged; the header is inside no region at all (B-222's class, one
surface further on). « Depth, not coverage » is exactly right, and it is now a measurement.

<sub>mutation — unwire the panel's `avatarImage`: three checks fall, the image back at 128x128,
`fill`, `inline`. Remove the shell button's `p-0`: one check falls at 20x30 against 32x32 and the
panel's three stay green, which is the trade this rule exists to refuse. Drop `object-cover` from
the variant: the crop check falls alone. Restored → `7 rules EXECUTED — no violation`</sub>

**B-224 — the header's avatar was 20x30 in a 32x32 button, and every class on it was correct.**
Found on 2026-08-29 while measuring the half of B-138 that was supposed to be the reference. The
image carried `w-full h-full object-cover rounded-[inherit] block` and computed **20x30**: a
`<button>` keeps the platform's padding (6px across, 1px down in Chrome), `w-full` is
`width: 100%`, and 100% of a content box is not 100% of a border box. 32 − 12 = 20, 32 − 2 = 30,
and the numbers say it exactly.

**Nothing was wrong with the class list, which is why reading it found nothing.** Three waves have
now concluded from the one place a fact ought to live rather than measuring it — B-138's own entry
counts two of them — and this is the same lesson from the other side: the classes were the right
place to look and they gave the wrong answer.

**Repaired** with `p-0` on the button, and held by R97 alongside the panel's. The header sits in no
region of the oracle, so nothing else could have seen it.

<sub>measured `[32,32]` host against `[20,30]` image before · `[32,32]` against `[32,32]` after ·
mutation: remove `p-0` → R97 falls naming the header alone</sub>

**B-225 — a guard froze its own corpus size in a comment, and the figure drifted three times in
three days.** Recorded by the steward's audit of L10 as A-2. `check-live-relay.py` carried
`POLLING_CORPUS_FLOOR = 60` with one comment saying « measured: 118 » and another saying « 60
against 124 files ». The tree read **120** when the pull request was written, **126** when it
merged, and **127** two days later. Two comments in one file stating one fact, disagreeing with
each other and with the tree, inside the guard whose whole subject is a count nobody recounts.

**The floor's POSTURE is right and is not the defect.** « A real floor against total collapse and
blind to targeted loss » is an honest thing for a floor to say about itself. What was wrong is the
number frozen beside it.

**The instrument, and it is exact rather than a judgement about prose.** A fifth arm,
`stale-figure`: it takes the counts the arms actually measure NOW and refuses to find them written
as literals in this module's own source. **A figure that agrees with the tree today is the
dangerous one** — it is the state every stale figure was in on the day it was typed.

**What it does not read**: any other guard. The class is general and the arm is not, and saying so
is worth more than an arm that greps every comment in `scripts/` and learns to be ignored. Nor the
floors themselves, which are the guard's own constants and are meant to be written down.

<sub>mutation — write « 60 against 127 files » back into a comment: the arm falls naming 127 and
what it measures. Write the reading-files count instead: it falls too, so it is not one number it
knows. Restored → `check-live-relay[stale-figure]: 2 measured count(s) checked against this
module's own source` · `--arm no-polling` prints 127 and the module holds no figure at all</sub>

**B-227 — four waves missed the same gesture, and the guard that catches it had been specified
and left unbuilt.**
`IMPLEMENTATION.md`'s « In flight » row goes back to *none* after a merge — the first post-merge
gesture of § 5. Measured at the close of **L09**, of **L10** (three gestures missed, repaired by
#514) and of **L10-bis**, where the row still named the wave, its branch and version `0.98.51`
while `main` carried `0.98.52`. The wave's trace row and the archive of
`docs/features/maquette-l10-bis/` were missing with it.

**§ 5 already carried the answer, written as a diagnosis with its mechanism and explicitly NOT
built**: *« a guard is code, and the steward who found this does not carry code (§ 7.2) »*. That
sentence held for four waves and produced four misses — and the fourth missed the gesture while
shipping `check-bug-register.py`'s own closure arm for the neighbouring rule. **A specification
nobody is allowed to implement is a sentence.**

**Building it corrected the specification, twice.**

- **« Has reached » is an ORDERING, not an equality.** Written as equality — the reading § 5's
  sentence invites, and the first one implemented — the arm reported **clean over the very defect
  it was written for**: the row named `0.98.51`, `main` carried `0.98.52`, because #517 re-anchored
  the oracle after the squash and bumped once more. **A wave that merges alongside any other change
  overshoots by construction.** Caught by running the new guard against the live defect rather than
  against a fixture.
- **A guard whose subject no CI filter names runs in no job.** `IMPLEMENTATION.md` was named by no
  filter, and a post-merge gesture is *precisely* a pull request touching that file alone.
  `tests/scripts/test_ci_filter_covers_the_guards.py` — L10-bis's own memory, armed as a test —
  refused it before the line existed. **The wave's instrument caught the steward's.**

**A third, smaller, found by mutation and belonging to this entry rather than to a footnote**: the
unreachable-`main` message named « neither origin/main nor main » from a literal, and survived a
mutation that pointed the lookup elsewhere entirely — reporting two refs it had never opened. The
message is derived from what is actually tried now. Same species as a guard reporting a corpus it
did not read.

**What this guard does NOT read, written into the module**: the version alone, never the pull
request number or the branch name; and it cannot see the other two gestures — the archive and the
trace row — which are a different subject it would report clean over.

**Four mutations, each seen red and restored**: a row naming a version `main` has reached → refused,
naming both versions; a row naming a version beyond `main` → clean, which is the one state it must
never refuse; the row deleted → refused; `main` out of reach → refused rather than passed.

> **The row read `fixing` until this pull request existed, and the register's own guard is why.**
> Written `fixed #NNN` first — B-221's exact defect, the placeholder saying the merge was never
> written down — and `check-bug-register.py`'s vocabulary arm refused it. The alternative was to
> guess the number, which this office has already done correctly once (B-147) and recorded as a
> fault: being right by luck is not being right by method.

<sub>`python3 scripts/check-implementation-state.py` · the specification it replaces:
`frontend-architecture.md` § 5, « Write the landed row when the pull request opens »</sub>

---

**B-228 — the brief's inventory command reads twelve of thirteen writes.**
The L10-ter brief re-derived its figure with `grep -n "\.innerHTML = " legacy.js` and read
**12**; the count had already moved from nine to twelve inside one day. `legacy.js:8943` writes
`select("#toastmsg").innerHTML =` with its value on the NEXT line, so a pattern demanding a space
after the `=` cannot see it. A count that depends on where a line breaks changes when a formatter
runs. The survey's command (`docs/features/maquette-l10-ter/SURVEY.md` § 1.1) reads every way a
script puts markup into the document and counts **19** sites — and says in the same breath what
it does NOT read: descriptors (`panel.open`, 10 producers, all the engine's) and toggles.
**B-085's species, and the phase's own figure for the « Guards green » table is 1.** Closed by
the command living in the survey with its output; there is no guard to write because the count is
a survey's, not a gate's.

<sub>`grep -n "\.innerHTML = " frontend/maquette/design/src/engine/legacy.js | wc -l` → 12 ·
`grep -cE '\.innerHTML\s*=' …` → 13</sub>

**B-229 — the confirmation dialog is not on the back ladder.**
D1's third tier: « Transient — no URL, but Back still closes it », and the example it names is a
confirmation. `openDlg` (`legacy.js:9062`) pushes no history entry, and `onEngineBack`
(`legacy.js:9461–9608`; rungs at 9477, 9478, 9481–9484) walks drawer → `#screen` → sheet and never
`#dlg`. Escape does reach the dialog (`app/focus.ts:213–235` → `__closeLayers`) and so does a scrim
tap; Back alone does not. So a hardware Back with a
delete confirmation up pops the entry UNDER it — a page, or the exit guard — with the dialog still
on screen; on `/acquisition` two Backs quit the application over an unanswered « Supprimer ».
**Derived from the code, not exercised** — the office's first limit; the rule that closes this
entry exercises it. NE-DOIT-PAS-6 is the clause it bends: a Back that does not close the dialog
neither consents nor refuses. **L15's** (the frame lot), as the dialog's rung; the operator's Q5
confirms D1's reading before it lands.

<sub>`grep -n "pushLayer" legacy.js` → one call, the drawer's · `awk 'NR>=9461 && NR<=9608' legacy.js | grep -c dlg` → 0</sub>

**B-230 — the engine re-adds `maximum-scale=1,user-scalable=no` to any host without a viewport meta.**
`legacy.js:44–50`: if the document carries no `meta[name="viewport"]`, the engine appends one
with `maximum-scale=1,user-scalable=no` — the two directives L03 removed from `index.html`
because they forbid the pinch-zoom WCAG 1.4.4 requires, 83 axe violations at the time. Dead on the
maquette's host, which declares the meta; **live on any host that does not** — a preview, a test
document, the harness's `wrapped.html` if its head were ever rebuilt. A landmine of the exact
shape § 6 records for `var()`: nothing fails, the violation simply comes back. **L15** removes the
fallback with the entry logic it belongs to; the accessibility tier over a document without the
meta is the rule.

<sub>`sed -n 44,50p frontend/maquette/design/src/engine/legacy.js`</sub>

**B-231 — the tab bar is rebuilt from scratch on every render.**
`render()` calls `renderNav()` unconditionally (`legacy.js:7868`), and `renderNav` assigns
`nav.innerHTML` (`7802`) — so every page switch, every store bump and every cache landing
(`app/engine-redraw.ts` calls `render()` on each query that has data) replaces the four tab
buttons with four new nodes. A persistent chrome is the first property of « as close to a mobile
application as possible » (`MODEL.md` § 3, P2) and it is false: focus on a tab is lost across a
redraw, `aria-current` is rewritten rather than moved, and a view transition (L12) would see four
elements disappear and four appear. Invisible to the oracle by construction — a rectangle and
nineteen properties do not carry node identity. **L15's**; the rule holds `isSameNode` across a
page switch and a bump.

**FIXED by #528, and the rule is R100** (`frontend/maquette/harness/persistence.py`). The bar is
a component (`app/tab-bar.tsx`), `renderNav` and its `nav.innerHTML` are gone from the engine, and
three holds keep it that way: « a page switch keeps the tab bar's button nodes », « a store bump
keeps them too » — both `isSameNode` over `#nav button`, asked in the page and compared position by
position — and « focus survives a page switch and a store bump, on the SAME node ». **That third
hold was itself the defect once**: it read `dataset.page`, a `closest('#nav')` and « not body »,
every one of which a REPLACEMENT node satisfies, so the rule written to catch replaced nodes could
be passed by one. An adversarial reader found it after the wave's gates were green; it asks
`isSameNode` now, which its own header had named as the only separating question from the day it
was written.

<sub>`grep -n "renderNav()" legacy.js` → 7801 (definition), 7868 (the one call, inside `render()`)</sub>
<sub>`grep -c "isSameNode" frontend/maquette/harness/persistence.py` → the three holds above, plus the message host's</sub>

**B-232 — two dead layers: the page-render branch and `#screen`.**
`PAGES_OF()` has eight entries, all `shellOwned: true`, none with a `render` — so the `else`
branch of `render()` at `legacy.js:7857–7864`, `view.innerHTML = found.render()`, is unreachable
and would throw if reached. `#screen` (`index.html:465`) is opened by nothing: `openScreen` left
with L05 and `screenStack` (`legacy.js:9101`) is never pushed, yet `onEngineBack`, `hideLayers`
and `window.__close` still test it and `app/shell.tsx:288–291` places the React mount node
relative to it. Machinery nobody can justify, kept because nobody measured it (D5's own words).
**L13's**, with the rest of the residue; the survey's inventory is what says the branch is dead.

<sub>`sed -n 7655,7745p legacy.js | grep -c "render:"` → 0 · `grep -n "screenStack" legacy.js`</sub>

**B-233 — `theme-color` is a constant while the document paints light.**
`index.html:20` declares `<meta name="theme-color" content="#0b0b0d">` once. The inline script
beneath it sets `data-theme="light"` before first paint when the operator chose « clair » or the
system prefers light — and the meta stays dark, so an installed light-theme application shows a
dark status bar over a light page. Two metas with a `media` attribute, or one the appearance
module rewrites, is the fix; **L15's**, with the appearance logic (`MODEL.md` § 2 Part 9), and the
rule reads the meta under both themes (P21).

<sub>`grep -n "theme-color" frontend/maquette/design/index.html`</sub>

**B-234 — the viewport meta declares no `interactive-widget`.**
L12's objective names « the virtual keyboard resizing content rather than the viewport ». Chrome
on Android decides that from `interactive-widget` on the viewport meta, and the platform default
is `resizes-visual` — the layout viewport keeps its height under the keyboard, and a bottom bar
positioned against it sits behind the keys. `index.html:13` declares
`width=device-width,initial-scale=1` and nothing else. **L12's**; a static read of the meta is
the rule, and the rendered behaviour is device-only, like the safe areas.

> **Closed by L12 (#540).** `index.html:20` declares
> `width=device-width,initial-scale=1,interactive-widget=resizes-content`, and the static read is
> a rule rather than a reading: `scripts/check-viewport-directives.py` REQUIRES that directive and
> refuses a viewport meta without it, across every host the maquette serves. The rendered
> behaviour stays device-only, like the safe areas — what is held here is the declaration, which
> is the only half a machine can see.
>
> The row said `open` for two days while `IMPLEMENTATION.md`, the pull request's body, the wave's
> report and its closing phase all said closed — four writings against one, and the register is
> the one that counts. Found by the adversarial review, not by a gate: `check-bug-register`
> printed « 0 closed by this branch » and nothing compares that against the prose.

<sub>`grep -c "interactive-widget" frontend/maquette/design/index.html` → 1</sub>

**B-235 — no desktop navigation exists beyond the drawer.**
`#nav` is `md:hidden` (`index.html:448`) and no rail exists anywhere under `design/src` — at
768 px and above the burger's drawer is the only navigation. Production draws a persistent
`Sidebar` there. §12 says the desktop « doit rester pleinement fonctionnel » (it is, through the
drawer) and is not the starting point of the drawing. **An unexplained difference between the
maquette and production is a decision nobody took**; this is one, filed `open` because the answer
is the operator's (`QUESTIONS.md` Q1) and not because the maquette is known to be wrong. Closed
by the answer, and by L15 if the answer is a surface.

<sub>`grep -n "md:hidden" frontend/maquette/design/index.html` · `grep -rln "sidebar\|Sidebar" frontend/maquette/design/src/{app,features,ui,lib}` → none</sub>

> **ANSWERED, 2026-08-30 (Q1): the drawer alone, at every width — and not frozen.** Not a defect: a
> decision, taken; a rail is drawn only if real use asks for it. Closes with L15's drawer.

**B-236 — every bottom-panel producer is the engine's, and no lot owed them.**
`grep -c "panel\.open(" legacy.js` → **10**; the same grep over `design/src/{features,app,lib,ui}`
→ **0**. The sheet is React (`ui/sheet.tsx`, since SP4b) and its every CONTENT — the follow sheet,
the journey, the « ⋮ », the account menu, a setting, the seasons, the acquisition status — is a
descriptor the engine produces from the fixtures. L13 said the sixty surviving fixture families
« belong to surfaces the ENGINE still draws — their literals cannot leave before their markup
does »; the markup left with the pages, and the families stayed because their readers are
producers, which D5's « surface by surface » was never applied to. **B-220's class over the
product's whole sheet layer**, and invisible to the same two size-counting instruments. Owned by
**L19** from 2026-08-29 (`frontend-architecture.md` § 4, Phase 5).

<sub>`grep -n "panel\.open(" frontend/maquette/design/src/engine/legacy.js` · `grep -rn "panel.open(" frontend/maquette/design/src/{features,app,lib,ui}`</sub>

**B-237 — the confirmation dialog paints under the tab bar.**
`.dlg` is `z-index: 48` (`legacy.css:225`); `#nav` is `z-50` (`index.html:447`); both are children
of `.device`, so a delete confirmation opens with the tab bar painted over its lower edge, and the
bar's four buttons stay tappable over a modal that says `aria-modal="true"`. Found by the
adversarial review of L10-ter's survey, which had written « the tab bar above every layer but the
drawer and the install card » from two figures and not from the stylesheet — the z-order in the
tree is an accumulation, not a list: 48 (dialog) · 50 (bar) · 51 (selection bar) · 55 (drawer,
install) · 60 (popover, harness panel, login) · 70 (splash). Invisible to the oracle (a rectangle
does not carry a stacking order) and to the accessibility tier (`inert` is on the background, and
the bar is in it — so the bar is inert AND painted on top). **L15's**, with the dialog's conversion:
one ranked list, in `MODEL.md` § 2 Part 6, and a rule that reads `elementFromPoint` over the bar
while a dialog is open.

<sub>`grep -n "z-index" frontend/maquette/design/src/styles/legacy.css` · `grep -n "z-\[\|z-[0-9]" frontend/maquette/design/index.html`</sub>

**B-249 — the screen flashes when a sheet action closes the sheet AND opens a page.**
Reported by the operator on 2026-08-30, on a phone: tapping an action of the acquisition sheet that
navigates — « Voir la fiche », « Voir le parcours », « Chercher une autre release » — produces a
visible flash of the whole interface, too fast to capture; closing the sheet alone (handle, scrim,
Back) does not. Not diagnosed here; two candidates are readable in the code and both are the
frame's. The engine's `applyState` (`legacy.js:9446`) runs `hideLayers()`, then a store write, then
`port.scrollTop = 0`, then a full `render()` — a whole-page repaint with a scroll reset sits between
the close and the open. And B-247 (L15's, filed on its branch) records that a store bump REPLACES a
feature page's nodes, which is a paint of nothing between two paints of the page. **L15's**: it is
converting the layers and their hosts now, and P1 (« one document, no full navigation ») is the
property the flash violates in spirit. The rule must walk the operator's path — a real tap on a
sheet action that navigates — and read paints or replaced nodes, not the final state.

<sub>`sed -n '9446,9456p' frontend/maquette/design/src/engine/legacy.js` · `grep -n "panel.close(" frontend/maquette/design/src/engine/legacy.js`</sub>

**DIAGNOSED AND HALF CLOSED BY L15, and neither candidate was it.** Sampled frame by frame on the
operator's own path — a long press on a library tile, then the first action of the sheet it raises:

    frame  0   the scrim is up, the sheet is in place
    frame  2   `visibility: hidden` on BOTH — while opacity and transform
               still have 200 and 300 ms to run
    frame 18   the destination screen appears, already in place

**`visibility` is not animatable the way `opacity` is.** Left out of the transition list it swaps on
the first frame, so the dimmed page snapped to full brightness in ONE frame and stayed bare for
sixteen — and the exit every producer waits for was already over before the wait began:
`data-mediasheet` closes the panel and calls `setTimeout(…, 260)` « to let the sheet finish
leaving ».

**The frame's half is repaired**: `visibility` transitions with a delay equal to the fade, on the
CLOSED state only. The bare gap goes from sixteen frames to three. **On the closed state only is
not decoration** — putting it on both broke focus ENTRY into the sheet, because `app/focus.ts`
focuses into a layer the instant `data-open` appears and an element whose `visibility` is still
resolving is not focusable. R81 caught it; it is the one hold in the suite that reads that instant.

**The other half is not L15's**: the 260 ms wait belongs to the producer, and a producer is Part
12's — **L19's**. R103 (`harness/exits.py`) measures the remaining gap and PRINTS it. A rule that
refused a number nobody in this wave may change would be a rule against the wrong subject, and a
number nobody prints is a number nobody acts on. **Left `open` for that half.**

<sub>`python3 frontend/maquette/harness/exits.py` — 5 holds, no violation, and the gap printed. Mutation: `visibility` taken back out; both exit holds fall.</sub>

---

**B-248 — the bottom sheet rises behind the tab bar; the operator wants it to cover the bar.**
Dictated by the operator on 2026-08-30 from a screenshot of the acquisition sheet. Today
`bottomSheet` (`ui/variants/layout.ts`) is `absolute … bottom-0 z-[47]`: it is anchored at the
screen's bottom edge, rises BEHIND the tab bar (z-50, `ui/variants/frame.ts`), and its body pads by
`var(--tm-bottom-bar-h)` so the last action is reachable — the variant's own comment says the bar
« sits above the layers, so a sheet must reserve its height ». **The decision reverses the RANK,
not the anchoring**: the sheet keeps rising from the screen's bottom edge and paints OVER the bar —
while a bottom layer is open the tab bar is not seen. The padding that reserved the bar's height
goes with the overlap it compensated; the dialog, at 56 since B-237, is the precedent. Interaction
does not change: `app/focus.ts` marks `#nav` `inert` while a layer is open, and B-237 measured
that its buttons were never hit-testable over one. Inherent to the template: `MODEL.md` Part 7
carries the paragraph and § 3 carries it as **P31**, with its instrument. L15's, in its own
behaviour commit: the oracle WILL move on the sheet's open states, and each divergence is accepted
under this entry's name. **The steward first wrote the opposite** — « the bar is the floor, the
sheet anchored on its top edge » — from the operator's « par-dessus », merged it in #529, and the
operator corrected it the same evening: the operator's words were read, not asked.

<sub>`grep -n "bottom-0 z-\[47\]" frontend/maquette/design/src/ui/variants/layout.ts` · `grep -n "^ *50  the tab bar" frontend/maquette/design/src/ui/variants/frame.ts`</sub>

**Closed by L15, alone, and the oracle moved exactly where this entry said it would.** The rank goes
47 → 52 — above the bar and above the slot's own bar, below the drawer and the confirmation — the
anchoring is untouched, and the padding that reserved the bar's height goes with the overlap it
compensated. **167 divergences, all on ONE region** (`shell/sheet-content`) and all of one cause:
`padding: 2px 14px 76px` → `2px 14px 18px` on 86 states, and the height that follows from it on 81.
No other region and no other property, checked by grouping the whole report; every later phase of
the wave diffed its own oracle report against that set line for line rather than against a count.

**Held by R101** (`harness/stacking.py`): the sheet is anchored on the screen's bottom edge, so the
overlap is there by construction and needs no producing — the one thing this hold has that the
confirmation's did not; and it is PAINTED over the bar, read with the bar's `inert` lifted for the
length of one reading, because a plain hit-test answers the sheet at 47 exactly as at 52. A third
hold reads that nothing reserves the bar's height any more: left behind, that padding is a blank
strip inside every sheet, which no hit-test sees.

**And R8 leaves the sheet, which is a renegotiation rather than a hole.** `audit.py`'s « every layer
reserves the height of the tab bar that passes above it » was right about a law this entry reverses;
it would now refuse the decision the operator took. Sixteen states reported it before the rule was
moved. Screens stay in its sweep — the bar does pass above them.

<sub>Mutation: the rank restored to 47; the hold falls with « at: 'nav', sheetRank: '47', barRank: '50' ».</sub>

---

**B-243 — three small drifts in the directives, found by re-running what they cite.**
`CLAUDE.md` said the contracts tier runs « nineteen » cheap guards; `run.sh` prints **20** since
`check-implementation-state.py` joined it on 2026-08-29. The plan's L01 entry cited
`docs/archive/features/maquette-l01/DESIGN.md`, archived under `docs/archive/features/` since L02. § 5 said
this file cites the survey « twenty times »; the count is **24**. None is a decision; all three are
figures nobody re-ran. Each now carries its command or its living path.

<sub>`frontend/maquette/harness/run.sh --contracts | grep "cheap guards"` · `ls docs/features/maquette-l01/DESIGN.md` (absent) · `grep -o "maquette-l10-ter\|MODEL\.md\|SURVEY\.md" docs/reference/frontend-architecture.md | wc -l`</sub>

---

**B-242 — `MODEL.md` P14 says 78 named states where 87 are driven.**
P14's instrument column reads « axe 1.4.4 on every named state (`window.__states()`, 78 today) ».
`oracle-reference.json` holds one `measurements` key per state — **87** — and the accessibility
tier prints « 87 states » in every run recorded in this register since L10. The figure was cited
from an older count and never re-derived; the property's verdict does not depend on it, its
instrument's coverage does.

<sub>`python3 -c "import json;print(len(json.load(open('frontend/maquette/oracle-reference.json'))['measurements']))"` → 87</sub>

---

**B-241 — the « Next » row said « once L10-ter merges » and « L14 stays last » after both had changed.**
One cell of `IMPLEMENTATION.md`'s state table carried, on 2026-08-30, « L15 — The frame, once
L10-ter merges » (L10-ter merged that morning, #521) and « L14 … stays last unless the operator
pulls it forward » — while the SAME cell ended « L14 pulled forward by the operator on 2026-08-30 ».
A sentence contradicted inside its own cell: B-152's shape, in the one table § 0 reads for the
state. The check-implementation-state arm reads the « In flight » row and not this one, which is
why it stayed.

<sub>`grep -c "once L10-ter merges\|stays last unless" IMPLEMENTATION.md` → 0 after this entry</sub>

---

**B-240 — the index announced twenty-five French words and the file it points at holds twenty-four.**
`CLAUDE.md` § Language says the vocabulary's seeded first version let « the twenty-five French words
that twenty-nine names in `design/src/engine/legacy.js` still needed » in with the rest.
`scripts/code-vocabulary.txt` holds **twenty-four** words below its banner, and the banner itself
says twenty-four.

**Wrong when written, then corrected in the wrong place.** At `71e50163` (#455, 2026-08-18) the
file already held twenty-four words while its own banner said twenty-five — off by one on the day
both were written. `05522b12` (2026-08-19) corrected the banner to twenty-four and left `CLAUDE.md`
saying twenty-five: the correction reached the file nobody opens for the figure and missed the
index every agent opens first. B-239's shape exactly, in the same index, found by re-running the
L15 brief's citation of the figure before the brief merged. The brief, the index and L10-ter's `DEFINITION.md` § 2.b — a third copy — all read
twenty-four now.

<sub>`awk '/LAST FRENCH/{f=1} f&&/^[a-z]/{n++} END{print n}' scripts/code-vocabulary.txt` · `git show 71e50163:scripts/code-vocabulary.txt | awk '/LAST FRENCH/{f=1} f&&/^[a-z]/{n++} END{print n}'` · `git show 05522b12 -- scripts/code-vocabulary.txt | grep -E '^[-+].*twenty'`</sub>

---

**B-239 — the index announced twenty-four properties and the document it points at holds thirty.**
`CLAUDE.md`'s reference table gained a row for `MODEL.md` on 2026-08-29 reading « the 24
mobile-application properties ». `MODEL.md` § 3 holds **P1 to P30**.

**It was not drift.** `MODEL.md` carried thirty in the same commit — `d3892d18`, #521 — that wrote
the index row saying twenty-four. The figure was wrong the moment it was written, by the wave that
wrote both files, and the session report to the operator said thirty correctly. **The error survived
only where it would be read first**: the binding index every agent opens before anything else.

**Two things it is NOT, and both were checked before this entry was written.** « Thirteen parts » in
the same row is right — `MODEL.md` § 2 runs Part 1 to Part 13, plus one heading that says it is not
a part, and counting `###` headings gives fourteen. And the suite's « 71 rules » was NOT touched:
the hold-count baseline's top-level keys are metadata, so a count taken from it is a miscount, and
the authoritative figure comes from running `run.sh` — which needs a browser this office does not
have. **A figure that cannot be re-derived is left alone and said so**, which is the other half of
the rule that produced this entry.

<sub>`grep -c '^| P[0-9]' docs/features/maquette-l10-ter/MODEL.md` · `git show d3892d18:docs/features/maquette-l10-ter/MODEL.md | grep -c '^| P[0-9]'`</sub>

> **Corrected with a second stale sentence found in the same sweep.** § 1 of the plan still read
> « invariant 10 has been binding since L09 and its subject — the frame — has never been modelled »,
> three lines above the paragraph recording that L10-ter modelled it in thirteen parts. True when
> written on 2026-08-28, false since the 29th, and contradicted within the same section. Put in the
> past tense: *that was the debt, and this phase paid it.*

---

**B-238 — a version-less « In flight » row is held by nothing.**
`scripts/check-implementation-state.py` refuses an « In flight » row naming a version `main` has
reached. A `no-version-bump` pull request — this phase's, the first since the guard shipped — names
no version, so the guard prints « the row names no version, so nothing is in flight to check » and
exits 0: after #521 merges, the row still announcing L10-ter is exactly the defect the guard exists
for, and it has no arm. The guard's own docstring lists what it does not read and this is not on
the list. Two shapes would close it: refuse a row whose named branch no longer exists on `origin`,
or refuse a row whose named pull request is merged (which needs the network the guard was built to
avoid). **The office's** under § 7.2's exception — the instrument measures the directives — or the
next wave's post-merge gesture, by hand, with this entry as the reason it is not automatic.

<sub>`python3 scripts/check-implementation-state.py` on this branch → « names no version » · `grep -n "VERSION_IN_ROW" scripts/check-implementation-state.py`</sub>

> **Closed by the steward on 2026-08-30, under § 7.2's exception, by a third shape neither of the
> two above.** A squash merge writes the pull request's number into the subject `main` carries —
> `… (#521)` — so the guard now reads the row's FIRST `#NNN` and refuses it when a subject in
> `git log origin/main` records it, offline and exactly like the version; the harness-contracts
> job checks out with `fetch-depth: 0` for the register's closure arm, so the history is whole
> there. A row in flight that names neither a version nor a pull request is refused outright. The
> guard had no committed test (B-041's shape); `tests/scripts/test_check_implementation_state.py`
> holds nine, seen red before the arm existed (1 failed, 8 errors) and green after. **Mutated on
> the real file**, three ways, restored each time: the row rewritten as L10-ter's with `PR #521`
> → exit 1, « a subject on `main` already records it as merged », 815 subjects read; `#99999` →
> exit 0; the number removed → exit 1, « names neither a version nor a pull request ». What it
> still does not read: a pull request merged without its number in a subject (this repository
> squash-merges every wave), and a row that cites an older pull request BEFORE its own.

**B-226 — the cross-check B-208 built never ran in continuous integration.** Recorded by the
steward's audit of L10 as A-1, and it is sharp. `check-live-relay.py`'s `backend_events()` compares
TWO oracles: the bus registry (`_EVENT_CLASS_REGISTRY`, what the wire actually carries) against a
regex scan of the sources. That is B-199, and it was the right repair. **B-208 then made the
DISAGREEMENT blocking** — « printed and could fail nothing » was the shape that wave had just named
two arms over — **and left the same shape three lines above**, on the import-failure path, where it
printed and returned no reason.

**And continuous integration took that branch every single time.** `harness-contracts` installs
`playwright` and `jsonschema` and never this package; `personalscraper/__init__.py` imports
`dotenv`; so on every pull request touching the maquette the arm ran on the re-implementation alone
and reported clean. The docstring's « the two are compared rather than one being trusted » was
false on the branch CI walked. The cross-check existed only in `make check`, which is a WAVE gate.

**BOTH repairs were taken, and the reason is that they answer different questions.** Making the
non-import a VIOLATION is the honest half: it costs a red the day an environment is incomplete,
which is what a red is for, and it is the same posture the tier already takes for `jsonschema` —
whose own comment says a missing package must not read as « no violation ». Installing the package
in `harness-contracts` is what makes the cross-check actually RUN per pull request rather than
merely stop lying. Installing alone would have fixed the runner and left the shape: any other
environment without the package would go back to trusting one oracle with nothing to say so.

**The cost was measured rather than assumed**: the registry import is 0.27 s and needs only
`dotenv`, `structlog` and `rich` transitively, and `pip install -e .` is marginal beside the
Chromium download this job already pays for. A hand-listed three-package install was the cheaper
option and was refused — a corpus enumerated by hand is the shape this register counts, and the
list would drift the first time `__init__.py` gained an import.

**A second defect came out of the repair**: the caller appended « is not there — » to whatever
reason it was handed, which read correctly for the absent-package case it was written for and
became a sentence-and-a-half once the unreachable-registry case started arriving there too. One
message per reason now.

<sub>mutation — shadow `dotenv` with a module that raises, which is CI's environment exactly: the
arm falls with « the event registry could not be imported … a cross-check with one side missing is
not a cross-check », where it used to print and exit 0. Restored → `48 backend event(s), 48
accounted for` · `check-live-relay: clean`</sub>

**B-139 — three variants exist, are exported, and are called by nothing.**
Reported by the operator on 2026-08-26: after adding a media to follows, the bar at the bottom of
the add screen shows « 1 média ajouté » beside **a white rectangle whose text cannot be read**, and
there is no way to dismiss it.

**The variant was written correctly and never connected.** L07 converted `.addfoot button` into
`addFooterAction` — `ml-auto [border:0] bg-transparent text-primary font-semibold text-3`, exactly
the six declarations the old rule carried. The call site does not use it:

    features/acquisition/add-screen.tsx:366
    <button onClick={toFollows}>{t("screens.add.seeFollows")}</button>

A bare `<button>`. **Preflight is deliberately not imported** (`theme.css`, L07's decision and a
right one), so a classless button keeps the user-agent's own painting — light background, dark
text, border. On this application's dark surface that is the white rectangle, and « Voir mes
suivis → » becomes unreadable. Same root as B-082 reached from the other end: there the remedy for
bare elements was a hand-kept list; here an element is bare that should not have been.

**It is not one button. Three variants in that one file are called from nowhere** — verified one by
one rather than trusting the sweep that found them: `addFooterAction`, `resultList` and
`suggestionChip` each return exactly one grep hit, their own declaration. One surface was converted
with three of its variants left unplugged.

**Nothing could have caught it.** TypeScript does not fault an unused export. The oracle cannot:
the footer paints only when `added.size > 0`, and the three named states of that screen are
`acq-add-empty`, `acq-add-results` and `acq-identify` — the second searches « star wars » and adds
nothing, the third is the identify pane — so **no measured state ever paints this bar**. Not a coverage gap this time but a STATE gap: the surface has
states, and none reaches the condition.

**The finding is that this is measurable in twenty lines and nothing measures it.** A variant
exported from a `variants.ts` and called from no other file is a mechanical check, and it would have
returned all three at once. It also asks what no existing guard asks: `check-markup-contracts.py`
reads the classes that ARE emitted; nothing reads the ones that were meant to be.

**A second defect, separate, and the operator's to arbitrate**: the bar is `sticky` above the
content and nothing reserves the space beneath it, so it covers a card. It is not a toast and has no
dismissal by design — whether it should have one is a layout decision, not a repair.

<sub>`grep -rn 'addFooterAction\|resultList\|suggestionChip' frontend/maquette/design/src/` · `grep -n 'acq-add' frontend/maquette/design/src/engine/states.js`</sub>

**CLOSED by L10-bis. All three wired, and the operator arbitrated the bar's shape before a line
was written.** Asked on 2026-08-29 whether a legible button was enough: *« Elle réserve pas sa
place elle passe par dessus c'est une notification comme une autre, elle est fermable. »* So the
bar keeps overlaying — nothing reserves its space — and it gains a dismissal. Both halves of the
report are answered: the exit is legible, and there is now an exit that is not the exit.

**The dismissal remembers a COUNT, never a boolean.** `dismissedAtCount` holds the `added.size` the
bar was dismissed at, so adding a further medium announces again. A boolean would swallow every
announcement after the first, which is a different defect wearing this fix — mutation-proven below.

**The instruments, and there are two because one could not have been enough.**

**The arm** — `check-markup-contracts.py`'s fifth: every `cva` exported from a `variants.ts` is
named by another file. It asks what no other arm asks, and the reason is structural: the four
others read what the markup EMITS, and a variant nobody calls emits nothing to be inconsistent
with. **It returned six, not three** — `searchIcon`, `sectionTitle` and `sectionCount` were
orphaned too, filed as B-223. It holds a HARD ZERO, seeded by removing the last orphan rather than
by recording it.

**The hold** — `harness/add_footer.py` (R96), ten checks walking the operator's own journey: open
the add screen, search, open a result, add it. The oracle could not do this and the reason is a
STATE gap, not a coverage one: `acq-add-empty` and `acq-add-results` are the screen's two named
states and the second adds nothing, so **no measured state has ever painted this bar**. Growing
`engine/states.js` was the other route and was refused — that file is the dying engine's scenario
table, which L13 removes, and a repair that grows what must die is a repair made twice.

**The colour is measured against a PROBE, never a literal**: a `<span>` carrying
`color: var(--color-primary)` is mounted in the same document and compared. A rule holding an
oklch literal would hold one theme and report about both.

**Two defects in the RULE were found by running it, and both are the same species.** Selecting the
add action with `.first` clicked a panel from an earlier result — a probe of five results reported
that every one took the « replace » route while three are seeded `owned: false`. And asking whether
the replace dialog is PRESENT found the closed one from the previous add, because a closed layer is
still in the document. Both routes into `added` are walked now, and each is named in its detail
line.

**What moved in the oracle: nothing, and that was an EMPTY READ.** The add screen carried no region
at all — B-222, found by asking why a painting change moved no measurement.

<sub>mutation — unwire `addFooterAction`: R96 falls three times, and it is the operator's photograph
in numbers — colour `oklch(0.96 0.003 286)` against a wanted `oklch(0.808 0.158 79)`, background
`rgb(239, 239, 239)`, border-style `outset`. Arm 5 falls naming the orphan. Remove the dismissal:
two checks fall, the touch box measuring 0x0 against 44. Dismiss on a boolean instead of the count:
the re-announcement falls alone. Restored → `10 rules EXECUTED — no violation` ·
`check-markup-contracts` clean at 118 variants over 127 readers</sub>

**B-140 — the scroll memory was built for screens and never learned about pages.**
Reported by the operator on 2026-08-26: scroll a page, open an item, come back — the page is at the
top. The application feel is to return where one left.

**The mechanism exists and is careful.** `app/shell.tsx` § « SCROLL FOLLOWS THE HISTORY ENTRY »
keys positions by the history entry, saves the outgoing position inside the history subscription —
« the only instant it is still in the DOM » — and restores over a bounded retry across five frames,
because the router commits its re-render on its own schedule. It also restores on a RETURN only,
correctly: arriving forward on an address one has seen before is a new visit.

**It reads one port out of two.** `activePort()` is
`document.querySelector(".screen.open .port")` — the port of an OVERLAY SCREEN. The main pages
scroll inside `#port`, declared in `index.html:221` with both `id="port"` and `class="port …"`, and
that element is never `.screen.open .port`. So on a main page the save either stores nothing
(no screen open, the query returns null) or stores the just-opened screen's position under the
departing page's key. Either way the return finds nothing to restore.

Nothing else covers it: `page-host.tsx:175` reaches `#port` by id, for `aria-busy` only.

**A second, latent defect in the same block**: `if (remembered)` treats a stored **0** as absent.
It is invisible today because 0 is the top, and it is the shape that hides a real regression the
day a position of zero must be honoured over a default.

<sub>`grep -n 'activePort\|scrollPositions' frontend/maquette/design/src/app/shell.tsx` · `grep -n 'id="port"' frontend/maquette/design/index.html`</sub>

**B-141 — ten elements carry no class, in a prototype whose reset does not cover bare tags.**
Measured after B-138 and B-139, because both were one element that had been left bare: a
`<button>`, `<img>`, `<input>`, `<select>`, `<textarea>` or `<a>` rendered with neither `className`
nor `class` in `design/src/**/*.tsx`.

| File | Line | Tag |
| --- | --- | --- |
| `ui/panel/index.tsx` | 222 | `<img>` — **B-138, confirmed defect** |
| `features/acquisition/add-screen.tsx` | 366 | `<button>` — **B-139, confirmed defect** |
| `features/acquisition/add-screen.tsx` | 248, 292, 314 | `<button>` ×3 |
| `features/acquisition/page.tsx` | 714 | `<button>` |
| `features/settings/panel-field.tsx` | 139 | `<input>` |
| `features/media/media-screen.tsx` | 22, 605 | `<a>`, `<img>` |
| `ui/panel/index.tsx` | 74 | `<img>` |

**This is a list of CANDIDATES, not of ten defects, and the distinction is deliberate.** A bare
element is only wrong where the user agent's own painting is wrong for it — an `<img>` whose parent
constrains it fully is fine. Two of the ten are confirmed because the operator saw them. **The
other eight are unread**, and saying so is the point: this entry exists to be checked, not believed.

**Two of them carry more risk than the rest, on grounds worth naming.** `panel-field.tsx:139` is an
`<input>`, and a classless input keeps the platform's own field — light ground, system border — on
a dark surface. And `add-screen.tsx` holds **four** of the ten, the same file as B-139's three
orphan variants: one surface converted incompletely, twice over, by two different measurements.

**Why nothing reads this.** Preflight is deliberately not imported (`theme.css`, L07), so bare tags
keep the user agent's painting by design — the decision was right and it makes bare tags a category
worth counting. `check-markup-contracts.py` reads the classes that ARE emitted; a tag with no class
emits nothing to read. Ten lines of AST would return this list, and it is the sibling of B-139's
check: one asks which variants are never called, the other which elements never call one.

**CLOSED by L10-bis. The eight were read, and the list had gone stale — which is what the entry
asked for.** `features/settings/panel-field.tsx`, the item this entry called the highest risk,
already carries `className={fieldInput({ mono })}`: a later wave dressed it and nothing said so.
The `<a>` at `media-screen.tsx:22` is gone. And the parser found one the list never had —
`ui/state-surfaces.tsx`'s retry button.

**Six remain, and NONE of them is a defect today.** Each was traced to what actually paints it,
in the stylesheet rather than in the class list — B-224's lesson, one entry earlier, is that a class
list is the right place to look and can give the wrong answer:

| Site | What paints it | Latent? |
| --- | --- | --- |
| `ui/state-surfaces.tsx` `<button>` | `.surferr button`, legacy.css:445 | **dies at L13** |
| `features/acquisition/page.tsx` `<button>` | the same rule, same surface | **dies at L13** |
| `features/acquisition/add-screen.tsx` `<button>` ×2 | `.segmini button`, legacy.css:1553 | **dies at L13** |
| `ui/panel/index.tsx` `<img>` | `.sheetposter img`, legacy.css:1929 | **dies at L13** |
| `features/media/media-screen.tsx` `<img>` | `castPortrait()`'s `[&_img]:*` utilities | no — the parent constrains it entirely |

**Five of the six become real bare elements on the day `legacy.css` dies**, which is B-223's
latency with the same date on it.

**The instrument is an ALLOW-LIST, not a count, and that is the design decision worth stating.**
`check-markup-contracts.py`'s sixth arm refuses a painting element left bare at an UNLISTED site.
A ratchet on a number was the obvious instrument and the wrong one: six is six whether the bare
element is a poster image its parent constrains or a retry button on a dark error surface, so a
count permits trading one for the other in silence. Each site carries the reason its own painting
is right, the way `code-vocabulary.txt` makes a refusal readable — and the five expiry dates are
written where they will be found at L13.

**It parses rather than greps.** An attribute list spans lines, a `className` may be a template
literal or a conditional, and an element can sit inside a template string a text reader sees as
prose. `frontend/maquette/harness/bare_elements.mjs` reads the TypeScript AST; the number of
elements it parsed is printed against a floor, and elements skipped for a `{...spread}` are counted
rather than described.

<sub>mutation — undress `addFooterAction`'s button: the arm falls on the site's ceiling (3 against
2 allowed). Add a bare `<button>` in `features/arrivals/page.tsx`, a file no entry lists: it falls
naming the file and the line. Remove the extractor: it reports that it could not run and exits 1,
never « no violation ». Restored → `85 painting element(s) parsed in 37 TSX file(s) (floor 40), 1
skipped for a spread — 6 bare, every one at a listed site with its reason`</sub>

<sub>a scan of `design/src/**/*.tsx` for the six tags rendered without `className` or `class`</sub>

**B-142 — three instruments measure the interface, and all three are bounded by what already exists.**
Raised by the operator on 2026-08-26: « what is missing is not limited to what the maquette already
offers, but also to what the app is FOR ». The three instruments this repository has answer a
narrower question than that:

| Instrument | Compares | Blind to |
| --- | --- | --- |
| `IMPLEMENTATION.md` § THE OBJECTIVE | pages, API modules, WebSocket files, service worker | anything that is not a file count |
| `frontend-backend-demands.md` | the maquette's contract against the running backend | anything the backend does not expose |
| `audit_design_coverage.py` | `tests/feature_map/` against the design docs | the product's own intent — despite the name |

**None reads `product-intent.md`**, which is the only document saying what the product must BE. So
a capability the constitution requires, that neither the maquette nor the backend has, is invisible
to every gate in this repository.

**Measured: the eleven DOIT clauses against the 53 operations the interface declares.** (Fourteen
clauses since 2026-08-26; the map re-read all fourteen.) Five have
no surface, and each one names an operation the backend already exposes and the interface does not
call — so they are not speculative:

| Clause | What it requires | The gap |
| --- | --- | --- |
| **DOIT-2** | « torrent différé (ratio, espace) … chaque « rien » a sa raison affichée » | `GET /api/acquisition/stalled-grabs` and `/obligations` are called by nothing |
| **DOIT-3** | « lancer/stopper le pipeline, **relancer le watcher** » | run/kill/pause/resume are declared; `POST /api/pipeline/watcher` is not |
| **DOIT-5** | « progression visible jusqu'au bout » | `GET /api/pipeline/stages` is called by nothing |
| **DOIT-6** | « X détectés, Y disponibles, Z récupérés » for one run | `GET /api/pipeline/history/{run_uid}` — the single run's detail — is called by nothing |
| — | configuration edited without validation | `POST /api/config/validate` is called by nothing |

**The five are not five independent gaps.** Four of them belong to `/pipeline` and `/control` — the
two surfaces § 1 of the architecture file places deliberately outside the lots, « named here only so
nobody reads their absence as an arbitration ». That framing is right and it has a consequence
nobody drew: **the clauses those pages would satisfy are unsatisfied for as long as the pages are
undrawn**, and no instrument says so.

**What is asked here is an instrument, not a page.** The 24 unused operations of
`frontend-backend-demands.md` § 4 are recomputed at every `make check` — that figure cannot go
stale. What is missing is the verdict column: for each, whether the new design retired it, whether
it is a surface still to be drawn, or whether it serves something outside the interface. Written
once, by the operator, it turns a list of « maybe » into work with a number — and any new operation
appears in it on its own.

**Two limits of this entry, stated rather than discovered.** DOIT-1, 4, 7, 8 and 10 are BEHAVIOURS,
not operations — a queued action shown as queued, a confirmation before replacement — and an
operation census cannot see them; they need reading, surface by surface, which this entry has not
done. And DOIT-10 (« Retour … refait le chemin emprunté ») is arguably already breached by B-140,
where the path is retraced and the position is not: whether the scroll is part of « le chemin » is
the operator's reading, not this steward's.

<sub>`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(1 for p in d['paths'].values() for v in p if v in ('get','post','put','patch','delete')))"` · `sed -n '492,517p' docs/reference/product-intent.md` · `docs/reference/frontend-backend-demands.md` § 4</sub>

> **THE MAPPING IS WRITTEN, 2026-08-29 (L10-ter).** `docs/reference/product-intent-map.md` — one row per DOIT and NE-DOIT-PAS clause, a verdict from a five-word vocabulary, a proof or an owning lot. Three rows read `to draw` (L16, L17, L18), eleven `partly` with an owed half (L19, L20), and the § 4 list of unused operations has a verdict for every operation a clause names — fourteen of the twenty-four. The arm is specified in `MODEL.md` § 4 and built by **L15**; this entry closes when it runs.

**B-143 — the constitution gained a section, and nothing in the plan answers it.**
The operator dictated **§17 — Comptes, droits et identité Plex** on 2026-08-26: the application
manages users, profiles and rights, and Plex users authenticate through Plex SSO. `DOIT-12` was
added with it — the actions offered are those the connected account may exercise.

**Recorded here the day it was written, because B-142 is one entry old**: three instruments measure
this interface and none reads the constitution, so a clause it gains is invisible to every gate
until someone says so. This is that someone.

**What exists today, measured**: one role (`PERSONALSCRAPER_WEB_ROLE=staging`, refusing writes
through the single `require_not_staging` dependency), one account (`WEB_PASSWORD_HASH` and a signed
session), and `GET /api/auth/me` in the maquette's contract carrying `avatar`, `email`, `name` and
nothing about rights. Plex is integrated for library refresh (`X-Plex-Token`, `plex-api.md`) and
never for identity.

**What §17 needs and nothing provides**: no operation in the 53 the interface declares concerns a
user other than the one connected, a role, or a permission; none of the thirteen lots names
accounts; and `frontend/maquette/design/src/features/account/` is a single `page.tsx` showing the
current person, not a model of several.

**The one thing §17 says that is a REQUIREMENT on existing code rather than new work**: the
read-only role must be ABSORBED by the rights model, not sit beside it. Two authorisation paths is
NE-DOIT-PAS-7, and the one that exists today is a single shared dependency — which is what makes
absorbing it cheap now and expensive after a second path exists.

Four questions §17 leaves open are written INTO the section rather than here, so that whoever
implements it reads them where the rule is: which roles and their exact rights, whether Plex SSO
replaces or joins the current sign-in, what becomes of a Plex user with no rights here, and what a
Plex account sees by default. None is the steward's to answer.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.

<sub>`grep -n 'WEB_ROLE\|require_not_staging' docs/reference/web-ui.md` · `python3 -c "import json;print([p for p in json.load(open('frontend/maquette/contract/openapi.json'))['paths'] if 'auth' in p])"`</sub>

> **PLACED, 2026-08-29 (L10-ter): L18**, last of the three, after L16 and L17, with §17's four open points written into the lot as its blocking note. It is the one lot after L15 that edits frame CODE (the gate, for Plex SSO; L16 and L20 only add navigation-table rows), and the plan says so.

**B-144 — the engine measures the ratio, and the interface shows none of it.**
The operator dictated **§18 — Le ratio est une ressource, et elle se pilote** on 2026-08-26, with
`DOIT-13`. Unlike §17, this one asks for almost no new backend: it asks the interface to read what
is already answered.

**Measured on the running backend**: the per-tracker policy exists — `min_ratio` and
`min_seed_time` on `TrackerProviderConfig`, read at the grab (`_grab_pass.py:370`) and at the
cross-seed (`cross_seed.py:871`) — and `GET /api/acquisition/obligations` is documented in the
route itself as « List seed obligations with their current ratio state ». `stalled-grabs` and
`downloads` answer beside it.

**All three are in `frontend-backend-demands.md` § 4** — the 24 operations the backend has and the
interface does not use. Which is the finding: this is not a capability to build, it is one already
built and never surfaced. The demands register named it a month before the constitution did, in a
list whose own heading says it « says what the switchover MAY retire ». **Retiring `obligations`
would have retired §18's subject**, and nothing in that list distinguishes an operation the new
design outgrew from one it has not reached yet — which is exactly the verdict column B-142 asks for,
now with a case that would have gone the wrong way.

**What §18 adds that the backend does not already answer** is the acting half: setting a tracker's
policy from the surface that shows its ratio (DOIT-3 applied here) is a write, and no operation in
either contract does it — the policy is configuration, edited today as a file.

**And one requirement that is a trap rather than a feature**: the displayed ratio must be the one
the TRACKER recognises, not a locally computed figure that drifts. An obligation shown as met and
still counted due by the tracker is NE-DOIT-PAS-1 with the account as the price.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.

<sub>`grep -rn 'min_ratio\|min_seed_time' personalscraper/acquire/*.py` · `grep -n 'obligations' personalscraper/web/routes/acquisition.py` · `docs/reference/frontend-backend-demands.md` § 4</sub>

> **PLACED, 2026-08-29 (L10-ter): L16**, first of the three, after L19 — so its per-tracker panel is written in the React producer template rather than the engine's. `features/trackers/`; the three operations wired, the policy write a demand, the ratio events claimed by its `live.ts`.

**B-145 — 797 lines of engine that inject torrents at third parties, and no way to know it happened.**
The operator dictated **§19 — Le cross-seed se voit et se décide** on 2026-08-26, with `DOIT-14`.

**Measured, and it is the most closed of the three sections dictated today.**
`personalscraper/acquire/cross_seed.py` is 797 non-blank lines. It emits `CrossSeedInjected` and
`CrossSeedRejected` on every decision. **Neither contract carries a single route for it** — zero
matches for cross-seed in `frontend/openapi.json` AND in `frontend/maquette/contract/openapi.json` —
and nothing under `personalscraper/web/` relays those events to `/ws/events`. The only trace
reaching any interface is a boolean configuration key, `"cross_seed": False` in
`web/routes/config.py:113`.

**The three sections dictated today are three different distances, and the distinction decides how
each is planned:**

| Section | What exists | What is asked |
| --- | --- | --- |
| §18 — ratio | three operations answering, none called | wire them, plus one write for the policy |
| §17 — accounts | one role, one account, no notion of several | a model, then surfaces |
| §19 — cross-seed | an engine, and **no exposure at all** | the backend follows the interface (§15) |

**§19 is where D7's rule earns itself.** « The maquette declares the contract its interface
REQUIRES … every divergence is recorded as a demand on the backend. » There is nothing to read from
here, so the demand has to start from what the experience needs — which is precisely the case D7
was written for, and the first one to arise since it was written.

**The defect this entry files, beyond the gap**: an engine that acts on third parties and reports
to nothing is `NE-DOIT-PAS-5` — silent failure — applied to a SUCCESS as much as to a failure. The
events are emitted and dropped. Whatever §19 becomes, the cheapest half is already built and
unplugged: two event types, already carrying their reason.


> **ARBITRATED, 2026-08-29.** The three sections are recorded in `frontend-architecture.md` § 1 as
> **lots that are OWED and not yet declared** — deliberately without a number, an order or a
> position, so § 0's rule cannot reach them: a lot the file has not placed is not electable.
> **L10-ter places all three**, in the order §18 → §19 → §17 unless it measures a reason to differ.
> They wait for it because §17 and §19 need new screens and L10-ter is redefining what a screen in
> this application IS — placing them before the template exists is drawing them twice.
> **B-142's instrument goes to L10-ter as well**, and the reason is not scheduling: the arm needs a
> declared mapping from each DOIT clause to the surface that serves it, and a mapping is a design
> decision rather than a grep. L10-ter is already modelling what a surface is.

<sub>`grep -rc 'cross.seed' frontend/openapi.json frontend/maquette/contract/openapi.json` · `grep -rn 'CrossSeed' personalscraper/web/` · `grep -c '[^[:space:]]' personalscraper/acquire/cross_seed.py`</sub>

> **PLACED, 2026-08-29 (L10-ter): L17**, depending on L16 because §19 is « le prolongement direct du §18 » and extends the tracker surface L16 draws. D7's first real case: routes declared by the maquette, mocks invented, the oracle recording the surfaces as new.

**B-146 — D11 is written, and no stylesheet carries a single scrollbar declaration.**
Arbitrated by the operator on 2026-08-26 after they reported that the desktop shows a native
scrollbar the phone does not: **the bar is STYLED, never replaced.** Measured before the decision —
`grep -rn 'scrollbar' src/styles/*.css` returns one hit, and it is a COMMENT inside
`.visually-hidden` explaining why `white-space: nowrap` stops a stray scrollbar appearing. Nothing
declares `scrollbar-width`, `scrollbar-color` or `::-webkit-scrollbar`.

**Recorded rather than left as a sentence**, for the reason this register keeps: a decision with no
arm and no code is a decision the next session reads as done.

**The one thing whoever implements it must NOT assume, and it is the whole entry.**
`scrollbar-width: thin` narrows the gutter, so the content beside it widens by a few pixels — and
**every measured rectangle inside that container may move.** Three outcomes are possible: no
divergence (the probe's container is inside the padding), a broad divergence across most states, or
one confined to the scrolling regions. **Which one is a run of the oracle**, on the machine that
owns the references, and this entry deliberately does not guess. Predicting an instrument's answer
from two facts held in hand is B-101, filed one week ago against this same office.

If the divergence is broad, it is not a reason to abandon D11: it is a re-record with every
signature named, the way L06's 47 folds were accepted. It IS a reason not to slip the change into a
wave whose proof rests on the oracle staying at zero.

**What it does not fix, and D11 says so**: the gutter still exists on a desktop. The comparison
that prompted this is the phone frame of `harness.css`, which ships nowhere.

<sub>`grep -rn 'scrollbar' frontend/maquette/design/src/styles/*.css` · `frontend/maquette/design/index.html:221` for the container</sub>


**CLOSED by L10-bis. D11 is implemented in `base.css`, in BOTH spellings.**
`scrollbar-width`/`scrollbar-color` is what Firefox reads; `::-webkit-scrollbar` is what Chrome
reads — and Chrome is what the oracle, the harness and the operator's phone all run, so writing one
alone would have styled the browser nobody here measures.

**THE ORACLE DID NOT MOVE, AND THE ENTRY'S PREDICTION WAS WRONG ABOUT WHY.** It expected narrowing
the gutter to move « every measured rectangle in that container »; it moved **none**. Measured:
`#port.offsetWidth - #port.clientWidth` is **0** on this machine, because macOS paints an OVERLAY
scrollbar that occupies no layout space. So there was nothing to re-record — and this entry was the
stated reason the wave had to run on the operator's machine. **The machine was still what settled
it**: only a run here could show the prediction false rather than repeat it.

**Which leaves the styling measured by NOTHING, and that is the real gap.** The oracle's twenty
numbers per region are geometry and computed properties OF THE ELEMENT; a scrollbar's colour is in
none of them, and a pseudo-element is in none of them by contract (B-061, D8). The oracle is green
over this whether it is styled or not.

**The instrument — `harness/scrollbar.py` (R99), ten holds.** Both spellings, BOTH THEMES, and the
container is asserted to actually overflow before anything is claimed about its bar. The thumb is
compared against `var(--color-border)` resolved in the same document, never against an oklch
literal.

<sub>mutation — remove the WebKit block: two holds fall, `::-webkit-scrollbar` back at `auto`.
Remove the standard block: six fall. **Replace the token with the literal it resolves to in dark:
the DARK holds stay green and the LIGHT one falls** — which is why the rule drives both themes and
compares against a token. Restored → `10 rules EXECUTED — no violation` · oracle unchanged at
B-222's three deliberate divergences</sub>
**B-147 — nine findings held on five stacked branches, and a wave took their numbers.**
B-138 to B-146 were written as **B-102 to B-110**, across five branches stacked on one another
between 2026-08-26 and 2026-08-27, none merged because the operator had scheduled them for a single
later correction wave. L09 landed in that interval and wrote **B-102 to B-137**. Every one of the
nine collided.

**The register itself had already named this shape, one wave earlier.** L09's own `B-102` reads
« Seven register rows are duplicated, once `fixed` and once `open` » — the same file, the same
mechanism, found from the other side.

**Nothing was lost, and that is not the same as nothing being wrong.** The nine are re-entered here
at B-138…B-146, and the two documents they came with — §17, §18, §19 of the constitution, `DOIT-12`
to `DOIT-14`, `D11` and the semantic-index objective — were **re-applied over `main`'s version, not
copied across it**. That distinction is the near-miss worth recording: the first attempt restored
both files wholesale from the steward branch, which would have silently erased the seventeen lines
L09 added to invariant 10 at its close — a re-measurement §7.1 obliges a wave to write, and the
most valuable paragraph either file gained that day. It was caught by asking what `main` had
touched, not by any gate.

**The cause is a steward habit, not a wave's mistake.** Holding findings on an unmerged branch to
respect « one correction wave » is right; **numbering them from a register that keeps moving is
not**. A number is only free while nobody else is writing.

Fix, and it is a rule rather than a repair: a steward branch that is not merged the same day takes
its numbers **at the moment it is opened as a pull request**, from `main` as it stands then — or
carries no number at all until it does. The entries are written; only the label waits.

**A postscript that is the entry's own lesson repeated.** This entry was written carrying
`fixed #511` before any pull request existed — the number was GUESSED, which is precisely the fault
the L08 agent declared about itself two waves earlier. The pull request opened as #511. **Being
right by luck is not being right by method**, and the guess would have been silently wrong on any
other day.

<sub>`grep -o '^| B-[0-9]*' BUGS.md | sed 's/| B-//' | sort -n | tail -1` before writing any new row</sub>

**B-148 — the plan still calls L09 `NOT STARTED`, and its selection rule reads the plan.**
L09 merged on 2026-08-28 (#509, squash `27096f31`). `IMPLEMENTATION.md` says so correctly — « Last
landed: L09 … squash 27096f31 » — and `frontend-architecture.md` line 930 still reads
**`#### L09 — The data layer, surface by surface · NOT STARTED`**. `IMPLEMENTATION.md`'s own
« Next » row also still names L09.

**This is not a cosmetic lag, because § 0 is executable prose.** « Come back here and find the
first lot whose status is not `LANDED` and whose dependencies are all `LANDED`. That is the work.
There is no other selection rule. » L09 is `NOT STARTED`; L01, L05 and L08 are `LANDED`. **The rule
elects the lot that just landed**, and an agent handed the plan and told to follow it would rebuild
L09 rather than open L10.

**The cause is structural, and naming it matters more than the fix.** The status of a lot is
written in TWO files — a per-lot label in the plan, and the state section of `IMPLEMENTATION.md` —
while § 1 assigns « where the work stands » to `IMPLEMENTATION.md` as **the only state**, and that
section opens by saying duplicating state is what produced a stale table read as current for three
days. The duplication it warns against is inside the pair of files that carry the warning.

Two repairs, and they are not the same: mark L09 `LANDED` and move « Next » to L10 — the wave's
missed gesture — and decide whether a lot's status belongs in the plan at all, or whether the plan
should name the ORDER and let the one state file carry the progress. The second is an arbitration.

Every prior wave did the first correctly; L09 is the first to miss it, which is why nothing has
caught it before and why nothing will catch the next one.

<sub>`grep -n '^#### L09' docs/reference/frontend-architecture.md` · `grep -o 'Next\*\*[^|]*| [^|]\{0,60\}' IMPLEMENTATION.md`</sub>

> **ARBITRATED AND CLOSED, 2026-08-28: the status leaves the plan.** `frontend-architecture.md`
> now carries the ORDER and the DEPENDENCIES and no status; `IMPLEMENTATION.md` carries the
> progress, which § 1 already assigned to it as *the only state*, and gains a « Landed, in order »
> row so § 0 has one place to read. The selection rule is rewritten to cross the two explicitly.
>
> **The obvious answer was refused on the evidence.** Adding « mark the lot LANDED » to the
> post-merge list is what one reaches for first — and § 5 of the plan already records that this
> list has been skipped **three times out of four**. A sixth entry on a skipped list changes
> nothing. **A fact that exists once cannot go stale**, which is the only form of this repair that
> does not depend on somebody remembering.

**B-149 — the lot's contract says the fixture literals left the engine; sixty families remain.**
L09's « Done when » includes « each surface takes its data and **its share of the fixture dies with
it** (D5) ». Measured: **21 fixture families died, 60 remain** — `legacy.js` went from 35 263 lines
to 33 449, a real subtraction and a fifth of the way.

**The wave declares the gap plainly**, in its session report and its pull request: the sixty belong
to surfaces the engine still DRAWS, so their fixtures cannot leave before their markup does, which
is L13. That reading is right, and it is the same shape L07 met when BLOCK 1 was separated instead
of deleted.

**What is missing is where it is written.** L07's equivalent departure was carried into the L13
entry of `frontend-architecture.md`, with its own « Done when » and an explicit « any earlier wave
may take it » — that is § 7.1 done properly, and it is why the deferral survives its session. This
one lives in a report and a merged pull request body. **After the squash, a reader of the plan sees
a « Done when » clause that is not true and nothing saying why.**

**B-150 — four files promised a reduction to a lot that had been and gone, and the guard that
exists to catch exactly that reported clean.**
`check-frontend-boundaries.py`'s size arm holds a grandfather list of files over the 400-line
ceiling, each labelled with the lot that OWES the reduction. B-073 armed it to refuse a label
naming a lot already landed — « a label naming a lot that is already `LANDED` promises a reduction
nobody owes any more », in the module's own words. Four entries read **« L09 — the data layer takes
it »**, and L09 landed on 2026-08-28.

**It reported clean because it read the stale word B-148 is about.** The landed set came from the
plan's own per-lot status, and the plan said L09 was `NOT STARTED`. The guard was not wrong about
its rule; it was reading a document that had stopped being true. **Forty-one now** on the B-085
counter — « a guard is green because of what it does not read » — and this one is the sharpest
variant yet: the guard read the right file, asked the right question, and got a stale answer.

**What L09 actually delivered against that promise: thirteen lines.** `features/acquisition/page.tsx`
went 769 → 756 while owing 356; `media-screen.tsx` is 796, `library/page.tsx` 613,
`resolution-screen.tsx` 430. **The premise of the label was simply wrong** — what makes those files
long is not the fetching L09 moved out, it is markup and variants. `page.tsx` holds four whole tabs
in one file, and the same `Icon` component is written out twice in two different features.

**The repair is in three parts, and only the first is the defect's own.** The arm now reads the
declaration from the plan and the advancement from `IMPLEMENTATION.md`'s « Landed, in order » row,
with each emptiness its own violation naming its own file — a single « unreadable » message would
send its reader to the document that was fine. The four labels name **L14**. And L14 exists in the
plan, because a debt with no owner is the state the ceiling is supposed to refuse.

<sub>`python3 scripts/check-frontend-boundaries.py --arm size` · `git show 5fdbfc9a:frontend/maquette/design/src/features/acquisition/page.tsx | grep -c '[^[:space:]]'`</sub>

> **CLOSED with the arbitration, 2026-08-28 (#511).** The operator's ruling: the plan declares a
> lot for it rather than hanging the debt on a lot whose subject it is not. **L14 — The surfaces
> that outgrew their file** is written into `frontend-architecture.md` after L13, depending on L07
> and L09 — both landed, so it may be pulled forward between any two lots at any time. **What that
> position costs is written into the entry rather than left to be discovered**: nothing depends on
> L14, so § 0 elects it last, and L10 through L13 are all worked inside 600-to-800-line files while
> invariant 6's reason — « an agent modifying a component opens one file » — goes unserved for them.
>
> **This entry is the argument for B-148's arbitration, found by making it.** Removing the
> duplicated status did not create this defect; it uncovered one that had been green for a wave.
> A second copy of a fact does not merely go stale — it answers for the first, and everything
> downstream reads the answer.
>
> **And the removal itself left five sentences behind, in this office's own commit.** § 4 of the
> plan still opened « Status is one word and nothing else: `NOT STARTED` · `IN PROGRESS` ·
> `LANDED` »; § 5's « which lot is next » still named the token; § 7.1's deferred-guard paragraph
> still described refusing « a lot marked `LANDED` »; `frontend-steward.md`'s first audit step and
> `IMPLEMENTATION.md`'s § SP5 both still stated the old rule. Thirteen tokens were counted out and
> the prose that described them was not — **and § 7.1's own line, one paragraph above the worst of
> them, is « when a decision changes, the implementation directives change in the same move »**.
> Corrected here. Found by grepping for the dead token after the guard was repaired, which is the
> only reason it was found at all.

---

**B-151 — a red check that names the wrong culprit, on every pull request whose lint fails.**
`coverage-merge` declares `needs: [changes, test]` with `if: always() && !cancelled()`, and gates
each of its steps on `needs.changes.outputs.python == 'true'` — on whether Python files CHANGED,
never on whether `test` actually ran. So when `lint` fails, `test` is skipped as a dependency, no
`coverage` artefact is uploaded, and `coverage-merge` runs anyway and fails with:

    Unable to download artifact(s): Artifact not found for name: coverage

**Two red checks, one cause, and the second one points nowhere.** A reader who opens
`coverage-merge` first — it is the one at the top of the list — reads an artefact problem and looks
for a coverage defect that does not exist. Observed on #511, where the real failure was a
`ruff format --check` difference of one line.

**It is a condition that reads the wrong question.** « Did Python change? » was the right gate for
whether coverage MATTERS; it is not the gate for whether the artefact EXISTS. The step needs the
second question too — `needs.test.result == 'success'` — and, failing that, the job should not
carry `always()` past a skipped dependency.

**Left open deliberately.** The fix is one line of `.github/workflows/ci.yml` and it belongs to
whoever next has a reason to open that file; recording it costs nothing and forgetting it costs a
misdirected diagnosis every time a gate goes red.

<sub>`gh run view <id> --job coverage-merge` on any run whose `lint` failed · `.github/workflows/ci.yml` § Stage 3</sub>

Fix: carry it to L13 as L07's was, or amend L09's clause to say what it actually promised — the
share of the fixture belonging to a surface the ENGINE no longer draws. Not both; the point is
that one file states it.

<sub>`grep -c '[^[:space:]]' frontend/maquette/design/src/engine/legacy.js` against `git show 27096f31^:…` · L13's entry for the shape to copy</sub>


**CLOSED by L10-bis, and it is the SECOND of the two exceptions rule 3's amendment allows by
name.** All seven steps of `coverage-merge` now carry `needs.test.result == 'success'` beside the
« did Python change? » condition they already had. When `lint` fails, `test` is skipped, no
artefact is uploaded, and the steps stand down instead of failing on a download.

**`always()` is KEPT, deliberately.** Without it a skipped `test` would skip this job too, and a
skipped required check can sit in « expected » for ever — the trap this workflow already records
above `harness-contracts`. The job runs and does nothing, which is a green check that honestly did
nothing rather than a red one blaming the wrong thing.

**NO AUTOMATIC PROOF WITHOUT MAKING THE PIPELINE RED ON PURPOSE**, which is why this entry was named
in advance as an exception. What was verified here is the shape, not the behaviour: the workflow
parses, and the seven steps carry the condition — read back from the PARSED yaml rather than from
the diff, because a condition indented into the wrong block is valid yaml that gates nothing.
**THE NEXT GENUINELY RED `lint` RUN IS THIS CONDITION'S VERIFICATION**, and it must show `lint` red,
`test` skipped, and `coverage-merge` green-and-idle. That sentence is written into `ci.yml` beside
the condition, where the next reader of a red pipeline will be.
