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
> **B-024** is diagnosed **latent and unreachable**: the census of `[data-go]` producers shows
> every one of them renders into `#view`, which sits under every layer, so none can be tapped
> while a layer is open — real, with no path to it. **B-030** is a defect of the maquette's
> embedded DATA (87 of 345 sheets carry no genre and no cast), not of the drawing, and the
> operator has excluded it from the batch closure. Neither was ever `to confirm`.

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
| B-024 | `data-go` settles ONE history entry, layers pile      | by review   | `open`       |
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
| B-036 | Two state ids are still French: `panne`, `groupe`      | by review   | `open`       |
| B-037 | `arrivals.py` reads a French global nothing defines      | by review   | `open`       |
| B-038 | `arrivals.py` reads `empty` and asserts nothing on it    | by mutation | `open`       |
| B-039 | `actions.py` prints `.freshtag` presence, asserts nothing | by mutation | `open`       |
| B-040 | Names in files no arm reads: `sweep.py`, a region id, `oracle.py` | by review   | `open`       |
| B-041 | `check-frontend-boundaries.py` has no committed test                | by audit    | `open`       |
| B-042 | An orphan `http.server` holds port 8900 on the operator's machine   | by review   | `open`       |
| B-043 | A deep media address lands the 404 page underneath it               | by review   | `fixed #484` |
| B-044 | A 404's address recomposes to `/` after a cold load                 | by review   | `fixed #484` |
| B-045 | `?panel=follows` without its colon is accepted, and fabricates media | by review   | `fixed #484` |
| B-046 | The fallback port moved onto `switchover.py`'s, whose bind error is swallowed | by review | `fixed #484` |
| B-047 | The navigation-failure flag is raised by no guard and read by no rule | by review   | `fixed #484` |
| B-048 | The ninth boundary arm stays green with `addresses.ts` deleted      | by review   | `fixed #484` |
| B-049 | A rule reads the operator's live `acquire.db` and turns red on every cron | by review | `open` |
| B-050 | `check-frontend-boundaries.py` is at 921 lines, 79 from the hard ceiling | by review | `fixed #500` |
| B-051 | `toFollows()` carries the page in its query, invisible to the boundaries arm | by review | `open` |
| B-052 | A synthesised follow panel labels a film « Série »                  | by review   | `open`       |
| B-053 | A panel's layer entry is taken by a tab tap on the same layer (revisit) | by review | `open`     |
| B-054 | `data-go="acq"` no longer forces the « now » tab (revisit)           | by review   | `open`       |
| B-055 | The a11y floor measures only the dark theme — light carries 154 findings | by review | `open` |
| B-056 | A `@keyframes` name is French (`splashremplit`), invisible to no-french  | by review | `open` |
| B-057 | `audit2.py`'s R12 silently measures four of five contexts, not five | by review   | `open`       |
| B-058 | commit-msg's AI-attribution match is unanchored, flags quoting prose | by mutation | `open`       |
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
| B-100 | Invariant 10 is written and unarmed: no arm counts the frame's domain words | by audit | `open` |
| B-101 | The steward's brief predicted an oracle movement that could not happen | by audit | `open` |
| B-102 | Seven register rows are duplicated, once `fixed` and once `open` | by audit | `open` |
| B-103 | Two invariants are numbered 10, and a brief pointed at « invariant 10 » | by audit | `open` |
| B-104 | The generated contract types live under `mocks/`, and they are not a mock | by gate | `open` |
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
| B-138 | The profile panel's avatar is unconstrained, inside a region whose probe reads only the container | by operator | `open` |
| B-139 | Three typed variants were written and never wired; one leaves a bare button unreadable | by operator | `open` |
| B-140 | Back returns to the top of a page: the scroll memory only knows overlay screens | by operator | `fixed #512` |
| B-141 | Ten elements carry no class at all, in a prototype that imports no preflight | by audit | `open` |
| B-142 | Nothing measures the interface against the constitution: five DOIT clauses have no surface | by audit | `open` |
| B-143 | §17 (accounts, rights, Plex SSO) has no surface, no contract operation and no lot | by audit | `open` |
| B-144 | §18 (ratio per tracker) needs three operations the backend already answers and nothing calls | by audit | `open` |
| B-145 | §19 (cross-seed) has no route in either contract, and its events reach no stream | by audit | `open` |
| B-146 | D11 is decided and nothing styles a scrollbar yet; the change may move the oracle | by audit | `open` |
| B-147 | Nine steward findings were stacked on five unmerged branches and collided with a wave | by audit | `fixed #511` |
| B-148 | Lot status lives in two files, and § 0 reads the one a wave forgets | by audit | `fixed #511` |
| B-149 | A declared departure from the lot's « Done when » lives only in a session report | by audit | `fixed #511` |
| B-150 | A size promise expired unnoticed because the guard read the status B-148 froze | by audit | `fixed #511` |
| B-151 | `coverage-merge` reports « Artifact not found » whenever an earlier job fails | by audit | `open` |
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
| B-220 | The drawer and the bottom tab bar are converted by no lot of the plan | by audit | `open` |
| B-221 | A wave merged leaving its own status as the literal placeholder `fixed #NNN` | by guard | `open` |

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

**B-042 — a stray process holds a port nothing in the repository claims.**
A `python3 -m http.server` listens on **8900** on the operator's machine, working directory
`/private/tmp/tm-a11y-probe`, and **no file in this repository mentions that port**. It is the
residue of an accessibility probe launched by hand during L03. Harmless in itself — 9.6 MB — and
reported by the L04 wave, which correctly declined to repair something that was not its own.

It is written here because that report lived only in a merged pull request body, which is the
same defect as B-041 read from the other end: a finding recorded where nothing re-reads it has
not been recorded. The port the harness actually uses is **8899**; `run.sh` starts it and reuses
it deliberately, and that one is not this.

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
green for ever. The plan declares L01 to L13; a lot it never declares is a promise nobody can call
in. The arm reads both sets now.
<sub>mutation: mark L09 `LANDED` in the plan — the four entries naming it fall by name, exit 1. Second: the plan made unreadable — « no lot status could be read », exit 1. Third: a label leading with `L19` — « which the plan does not declare », exit 1</sub>

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
| **Total** | **73** | at 2026-08-29. **The wave that built the most instruments found the most blind ones**, and that is the reading: nine of L09's fourteen were found by adversarial reviewers reading the gate AFTER it went green. **And a guard can be blind to a document rather than to code** — B-150's arm was correct in every line and read a file that had stopped being true. **L10 adds a fourth reading, and it is the sharpest in this table**: the wave reported **4**, found by its own mutations in the phases that wrote the instruments, and was wrong by **9**. Seven adversarial reviewers reading the same green gate found nine more — six of them in rules that had each already been mutation-tested. **Mutation proves a rule catches the defect you thought of**; every one of the nine is a defect the author did not think of, and they are all the same species: a word the CSS removes, a key that disappears rather than changes, a socket that is not there. The two methods are not substitutes, and the ratio is the argument — 4 to 9. **AND THEN THE REPAIRS WERE REVIEWED, AND HELD ELEVEN MORE.** Six of those eleven are in instruments the author had just written in response to a review, mutation-tested, and believed. The reading that survives all three rounds is not « review harder » — it is that **an instrument written by the person whose work it measures inherits that person's blind spots, whatever the discipline**, and only a second pair of eyes on the instrument finds them. 4 by mutation, 9 by review, 11 by reviewing the repairs, 8 by reviewing THOSE. **AND THE CURVE IS THE ARGUMENT FOR STOPPING**: five production defects in round one, six in round two, and in round three **none** — its two criticals were an ABSENT repair and a DISCARDED count, both procedural, and both now impossible rather than improbable (`scripts/mutate.sh`, and a fake that closes asynchronously like a real browser). A fourth round would read its own corrections. The criterion for ending is not « no findings »; it is **no undiscovered product defect, and the procedural failure mode eliminated** |

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

**What stays open is the PLACEMENT.** Moving the file has five ends — the `package.json` script,
`make check-contract-types`, `check-mock-seeds.py --arm generated`, the boundaries guard's
`GENERATED` table, and four importers — and a rename with five ends belongs to its own change, not
to the phase that first needed to import it. Until then a reader of the tree is told the contract
is a mock.

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
the footer paints only when `added.size > 0`, and the two named states of that screen are
`acq-add-empty` and `acq-add-results` — the second searches « star wars » and adds nothing — so **no
measured state ever paints this bar**. Not a coverage gap this time but a STATE gap: the surface has
states, and none reaches the condition.

**The finding is that this is measurable in twenty lines and nothing measures it.** A variant
exported from a `variants.ts` and called from no other file is a mechanical check, and it would have
returned all three at once. It also asks what no existing guard asks: `check-markup-contracts.py`
reads the classes that ARE emitted; nothing reads the ones that were meant to be.

**A second defect, separate, and the operator's to arbitrate**: the bar is `sticky` above the
content and nothing reserves the space beneath it, so it covers a card. It is not a toast and has no
dismissal by design — whether it should have one is a layout decision, not a repair.

<sub>`grep -rn 'addFooterAction\|resultList\|suggestionChip' frontend/maquette/design/src/` · `grep -n 'acq-add' frontend/maquette/design/src/engine/states.js`</sub>

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

**Measured: the eleven DOIT clauses against the 53 operations the interface declares.** Five have
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

<sub>`grep -n 'WEB_ROLE\|require_not_staging' docs/reference/web-ui.md` · `python3 -c "import json;print([p for p in json.load(open('frontend/maquette/contract/openapi.json'))['paths'] if 'auth' in p])"`</sub>

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

<sub>`grep -rn 'min_ratio\|min_seed_time' personalscraper/acquire/*.py` · `grep -n 'obligations' personalscraper/web/routes/acquisition.py` · `docs/reference/frontend-backend-demands.md` § 4</sub>

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

<sub>`grep -rc 'cross.seed' frontend/openapi.json frontend/maquette/contract/openapi.json` · `grep -rn 'CrossSeed' personalscraper/web/` · `grep -c '[^[:space:]]' personalscraper/acquire/cross_seed.py`</sub>

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
