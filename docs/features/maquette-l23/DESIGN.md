# L23 — the upload to a tracker (§ 19 point 5) · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L23 — §19 point 5, upload to a tracker` (its
« Where it lives » and « Done when » lines). It is not restated here; what follows is the drawing a later plan
executes, once the operator has answered § 7's five open questions.

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/design/` was touched to write it** — no code, no rule, no mock, no seed: this is prose and
numbers, drawn AHEAD of the lot's own opening, so the operator can read it and answer its questions now rather than
when L23 is next in the order. **Nothing under `frontend/maquette/design/src/features/trackers/` exists on `main`
today** (measured below, § 2.1): L16, L17 and L18 have each landed as a design-and-plan PR, not yet as code — this
document reads their DESIGNS as the tree L23 will find once they have.

**Written 2026-09-27**, on `main` at `7d40969f4` (L18's design-and-plan PR, #618, merged) — the plan's order is
`L14 · L19 · L21 · L13 · L20 · L22 · L16 · L17 · L18 · L23` (`docs/reference/frontend-architecture.md` § 1, § 4.
Phase 5). **Its spine is not mine.** `product-intent.md` § 19 point 5, dictated 2026-09-27, and the operator's own
words of round 8 question 8 (`docs/reference/operator-method.md`) give the lot its whole subject: an application
that can create a torrent and publish it on a tracker to open a cross-seed, a failure of either counted as a
cross-seed failure, and a lot of its own, after L18, drawn ahead of time so its own questions reach the operator
now. This document transcribes; it decides nothing the rulings leave open, and it invents no backend shape the
constitution's or the demands' own words do not already carry.

---

## 0. What L23 owes, said once

| # | The clause | Its source | The surface that serves it | Held for |
| --- | --- | --- | --- | --- |
| 1 | The application MAY create a torrent from a medium's own files and publish it on a tracker, to open a cross-seed where the engine's own search found none | § 19 point 5; round 8 Q8 (verbatim) | S1 — the gesture, on L17's own per-pair mark | § 1.1, § 2 |
| 2 | A failure of the CREATION or the PUBLICATION is a cross-seed failure, and counts as one | § 19 point 5; round 8 Q8 = A (« ça sera donc une erreur remontée via le cas A ») | S2 — the closed reason set's reserved slot, filled; the badge | § 1.2, § 2.2 |
| 3 | The six state words carry NO seventh — an uploaded-and-published pair reads « actif » on success, « erreur de cross-seed » on failure, exactly like a found one | § 19 point 5's own six words, unchanged; round 10 Q5 | reused verbatim, L17's own field | § 1.3 |
| 4 | It has ITS OWN LOT, after L18, drawn ahead of time in the second slot with its own questions | round 8 Q18 = B | this document, and the frontend-architecture.md entry it proposes | § 1.4 |
| 5 | L17 keeps only the reserved slot for it — L23 draws the rest | L17 DESIGN § 2.2, § 7.1 (« a reserved failure-kind slot… no code path emits it today and this lot draws nothing for it ») | S2 | § 1.2 |
| 6 | The gesture's right is a LIST item, not a choice — its default holder is configuration (Comptes), never a design decision | organisation ruling 21 (round 9 Q13, 2026-09-27, precising ruling 17) | § 0.2 — the right, drawn; L18's own model, which enforces it | § 0.2 |

**Its own blocking note.** Unlike L16/L17/L18's own first drawings, which carried a blocking note lifted by the
operator's rulings of 2026-08-30 and 2026-09-27, **this design is written WHILE its note is still on**: five
questions (§ 7) have no answer yet, and a plan cut from this document before they do would either invent a choice
this document is forbidden to make, or leave every phase provisional. **The frontend-architecture.md entry this
PR proposes (§ 6) carries the note explicitly**, and `docs/features/maquette-l23/plan/INDEX.md` is cut to the
questions' COST, not to their answer — every phase that a reading would change says so, names both readings, and
is amended in one line once the operator rules (the same discipline `docs/features/maquette-l16/DESIGN.md` § 0
used for its own three first-drawing OPEN questions, before they were ruled).

### 0.1 What L23 builds on, and does not redraw

| Lot gives (design, not yet code) | L23 reads it as |
| --- | --- |
| L16 — the Trackers page, its two tabs, the tracker's collapsed entry and its `Disclosure` | the HOME of S1's gesture: the Torrents tab's origin row, exactly where L17 already draws the per-pair mark — no new page, no new tab |
| L17 — the six-word model, the per-pair mark (S3), the closed reason set with its reserved slot, `features/trackers/live.ts`, the exclusion memory (S3-bis), `trackersBadge` | the SHAPE S1 extends: one more act on the SAME row, one more pair of codes in the SAME closed set, the SAME two events (never a third), the SAME exclusion (an excluded pair refuses the upload gesture too, § 1.1) |
| L18 — the rights model, one function from the account's role to a closed set of named RIGHTS, `trackers.control` | the HOME of § 0.2's right: L18's model is what will enforce it, from whatever role the operator, through Comptes, assigns it to |

**What L23 does NOT need from L16, L17 or L18, and must not assume**: the ratio surface, the switch's own
confirmation copy beyond its precedent, the media sheet's cross-seed block, the accounts editor. **What L23 does
not draw at all**: anything L16/L17/L18 already drew — this document adds to their surfaces, and amends none of
their files (a contradiction found while reading them is reported to the orchestrator, never fixed here).

### 0.2 The right, drawn (organisation ruling 21) — not one of § 7's open questions

**Corrected on the orchestrator's own reading of ruling 21** (round 9 question 13, 2026-09-27, precising ruling
17, `docs/reference/operator-method.md`): « les noms des rôles et la répartition des droits entre eux sont du
PARAMÉTRAGE (page Comptes), pas du dessin ; le dessin fixe seulement la LISTE des droits… [et] les rôles fournis
comme valeurs de départ ». **Who ends up holding this right is never the operator's to answer through this
document** — it is a fact of `docs/features/maquette-l18/plan/`'s own Comptes editor, changeable at any time
without touching this design. This document's OWN job, per ruling 21, is narrower: name the right in the LIST,
and PROPOSE a starting value.

- **The right's name, drawn**: `trackers.upload`, distinct from `trackers.control` (L18 DESIGN § 1.2). **Why a
  second right, not a reuse**: creating and publishing a NEW torrent at a third party is the one cross-seed act
  that can draw the tracker's OWN attention to the account — a duplicate or malformed upload risks a warning or a
  ban (NE-DOIT-PAS-8's own territory) — a heavier consequence than flipping a switch or cutting a link, so a
  manager who grants `trackers.control` to a role does not thereby grant this one; the two stay independent by
  construction, exactly as L18 already splits `trackers.view` from `trackers.control` for a comparable reason
  (F31 of that design).
- **The proposed starting value**: the SAME default `trackers.control` already reads in L18's own rights table
  (« — », held by nobody but Admin, via the ACL bypass) — because the two rights being independent (above) is a
  reason to give them SEPARATE rows, not a reason to seed them differently before any role has asked for one; a
  manager extends either right to a role from Comptes, at any time, on his own configuration.

Every place this document used to ask « who holds it by default » now reads this section instead; § 7 carries
five open questions, not six, because this was never a sixth choice for the operator to make.

---

## 1. What § 19 point 5 dictates, clause by clause, and the surface that serves it

1. **« L'application peut créer un torrent et le publier sur un tracker pour ouvrir un cross-seed. »** Served by
   **S1 — « Créer et publier un torrent »** (§ 2.3): a gesture on L17's per-pair mark, offered on exactly the three
   states nothing already cross-seeds on — the SAME three « Chercher un cross-seed » already reads (`noMatch`,
   `error`, `notSearched`, DESIGN L17 § 3.3) — because uploading is the alternative path when nothing found by
   search exists to inject, never a duplicate of what already runs. **Never offered on an EXCLUDED pair** (L17's
   S3-bis, round 9 Q11): a pair the operator has already told the engine to leave alone is not one this gesture
   should re-open by another door.
2. **« Un échec de publication ou de création est un échec du cross-seed, compté comme tel. »** Served by **S2 —
   the closed set's reserved slot, filled** (§ 2.2): two new codes, `creation_failed` and `publish_failed`, in the
   SAME counted family L17 already named « the engine could not finish » (`inject_failed`, `obligation_write_failed`)
   — round 8 Q8's own words rule this, not a choice this document makes. The Trackers badge's second term
   (L17's `crossSeed.failed`) needs NO new component: it already reads the two counted families, and these two
   codes simply populate a slot L17's own derivation already counts (`R-L17-g`, re-aimed, never re-derived, § 4).
3. **« Il a son lot, après L18. »** Served by this document's own place in `frontend-architecture.md` § 4, Phase 5
   (§ 6 below), and by the fact that nothing here amends L16, L17 or L18's own files.
4. **The six state words, unchanged.** Served by reusing L17's `state` field verbatim: a pair this gesture succeeds
   on reads « actif », with its date, EXACTLY as an injected one does (§ 3); one it fails on reads « erreur de
   cross-seed », with the new code's own sentence (never a bare code, NE-DOIT-PAS-4). **No seventh word is drawn.**
5. **L17's own reserved slot is FILLED here, not amended there.** L17's DESIGN.md is read, never edited (§ 0.1);
   this document's own § 2.2 is where the slot's two codes are proposed, and L17's file keeps saying « reserved,
   not built » until the lot that actually builds this — not this docs PR — lands.

---

## 2. The contract (D7) — and it comes FIRST

**Measured today, on `7d40969f4` (this worktree)**:

    python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"

reads **67** operations declared; `[p for p in d['paths'] if any(x in p.lower() for x in ('cross','tracker','seed'))]`
reads **`[]`** — no route names a tracker, a cross-seed or a seed on this head, because L16's and L17's own
contract demands have not been filed yet (their DESIGNs propose them; their PLANS file them when THEY open).
`ls frontend/maquette/design/src/features/trackers` answers **no such directory**. **L23's own contract phase, when
its plan opens, EXTENDS L17's `CrossSeedTrackerState` shape as L17 left it** — this document proposes the
extension's SHAPE now, against L17's OWN description (`docs/features/maquette-l17/DESIGN.md` § 2.1), and the
opening measure is RE-TAKEN, not assumed, the day L23's plan actually runs (the same discipline L17's own plan used
for L16's not-yet-landed files).

### 2.1 What is proposed as owed, once L17's shape exists to extend

| Demand | Operation | What it is for |
| --- | --- | --- |
| **Q** | `POST /api/torrents/{infoHash}/cross-seed/{tracker}/upload` — `uploadCrossSeed` (new) | one torrent, one tracker, one call: creates a `.torrent` from the medium's own files and publishes it to the named tracker; answers a visible « en file » under the SAME discipline `searchCrossSeed` already carries (DOIT-4, NE-DOIT-PAS-3) — never « occupé », bounded by the tracker's own publication rules (§ 7 Q3) and by whatever quota the backend keeps for it (a sibling of the search quota, never assumed to BE it) |
| **R** | the closed reason enum, extended | two new codes, `creation_failed` and `publish_failed`, filed into the SAME family as `inject_failed` / `obligation_write_failed` (§ 1, clause 2) — L17's twelve codes become fourteen, the reserved slot's own row in L17's table is what these two now answer |
| **S** | `CrossSeedTrackerState`, extended | a `via: "search" | "upload"` field on a pair reading `active` or `error` — so a reader can tell an injected match from a created-and-published one WITHOUT a new state word; whether this also touches the ROW-level origin colour (L16's own field, § 2.3 item 3 of its DESIGN) is § 7 Q5, open |

**Nothing here is filed against the contract today.** D7's own discipline (« a demand is filed where its surface
is drawn ») means Q, R and S are FILED by L23's own plan, when it opens — this table is the typed FORM the plan
will file, not a filing.

### 2.2 The closed set's reserved slot, filled — drawn from round 8 Q8, not invented

L17's DESIGN § 2.2 names its twelve reason codes' two counted families (« the attempt failed », « the engine could
not finish ») and states, verbatim: « reserved, not built — one slot for a future upload-to-tracker or
tracker-side torrent-creation failure… no code path emits it today and this lot draws nothing for it. » The
operator's own words at round 8 Q8 settle WHICH family it joins: « si l'upload ou la création du torrent sur le
tracker n'a pas marché ça sera donc une erreur remontée via le cas A » — case A being « the badge counts the
FAILURES only », the same family `inject_failed` and `obligation_write_failed` already occupy (an ATTEMPT that
could not finish, not an ordinary mismatch). **Two codes, not one**, because the operator's own sentence names TWO
distinct moments that can fail — building the `.torrent` (`creation_failed`) and handing it to the tracker
(`publish_failed`) — and L17's own precedent never folds two distinct engine moments into one code when they can
be told apart (fact 3 of L17's DESIGN, on the twelve it already has). Each gets ONE sentence in clear French,
never a bare code (NE-DOIT-PAS-4), worded by the phase that files it, once the backend's own error vocabulary for
this operation exists to translate — this document proposes the SLOT the sentences fill, never invents the
sentences themselves ahead of a real failure mode to describe.

### 2.3 S1 — the gesture, drawn against L17's own row

**Its place.** The SAME disclosure L17 draws on the Torrents tab's origin row, one row per other eligible tracker
(`docs/features/maquette-l17/DESIGN.md` § 3.3) — a SECOND act beside « Chercher un cross-seed », on the SAME three
eligible states (`noMatch`, `error`, `notSearched`), never a new row and never a new page. **What is on the
screen**: « Créer et publier un torrent » (proposed key `screens.torrents.uploadCrossSeed`), a confirmation before
the call fires — NE-DOIT-PAS-6 applied to CREATING a public artifact rather than destroying one, the first time
this codebase's confirmation discipline covers that direction — naming the tracker and that the medium's own files
will be packaged and sent there, then a visible « en file » (`torrents-cross-seed-upload-queued`) while the
backend works, resolving within the SAME visit exactly as `searchCrossSeed`'s own outcome does (F59's own
discipline, L17's). **On success**: the pair moves to `active`, `injectedAt` set, `via: "upload"` — read on the
SAME row S3 already draws, no new row. **On refusal**: the pair moves to `error`, the new code's own sentence
drawn exactly as any other refusal's is (§ 1, clause 2, § 2.2).

---

## 3. Named states

Every id below is PROPOSED — none exists, and none is bound to a real seed row until L23's own plan opens (the
same discipline L17's DESIGN § 4 used before its own eight OPEN questions were ruled). Three of the eight are
CONDITIONAL on an answer in § 7, named as such; five are not.

| # | id | What is on the screen | Conditional on |
| --- | --- | --- | --- |
| 1 | `torrents-cross-seed-upload` | the gesture drawn on an eligible pair's opened mark | — |
| 2 | `torrents-cross-seed-upload-confirm` | the confirmation, naming the tracker and the files to be published | — |
| 3 | `torrents-cross-seed-upload-queued` | the visible « en file », never « occupé » | — |
| 4 | `torrents-cross-seed-upload-refused-creation` | an « erreur de cross-seed » row reading `creation_failed`'s own sentence | — |
| 5 | `torrents-cross-seed-upload-refused-publish` | the same, reading `publish_failed`'s own sentence | — |
| 6 | `tracker-upload-disabled` | a tracker's own entry, a switch OFF for uploads specifically | § 7 Q2, reading B |
| 7 | `torrents-cross-seed-upload-rule-refused` | the confirmation naming a tracker-side rule the medium cannot meet, before any call fires | § 7 Q3, reading B |
| 8 | `tracker-upload-failures` | a per-tracker « N publications échouées » count, unfolding, a « vu » per row | § 7 Q4, reading B |

States 6–8 are named here so the plan that later draws them does not invent an id from nothing; they are not
proved by anything today, and a phase that finds them unneeded (because the operator ruled the OTHER reading) says
so and drops them, rather than building a state nobody's reading asks for.

---

## 4. The rules that bite

**The labels below are NOT rule numbers** (L17's own convention, DESIGN § 5): they are bound to real, consecutive
free numbers the day L23's plan's first rule-writing phase opens, against `origin/main`'s own highest at that
moment. Two are drawn in full; four are drawn PARTIALLY, because their exact hold depends on § 7's answers, and
each says which question it is waiting on.

| Rule | What it READS | The mutation that fells it | Waiting on |
| --- | --- | --- | --- |
| **R-L23-a** — the two new codes are sentenced, no bare code (NE-DOIT-PAS-4) | every `error` row reading `creation_failed` or `publish_failed` draws ITS sentence, never the code | draw the code instead of its sentence → falls | — |
| **R-L23-b** — the gesture is offered only where nothing already cross-seeds (§ 1, clause 1) | the act is present on `noMatch`/`error`/`notSearched` rows and absent on `active`/`stopped`/`trackerWithout`/excluded pairs | offer it on an `active` row → the offer hold falls | — |
| **R-L23-c** — the call is answered, visible, never « occupé » (DOIT-4, NE-DOIT-PAS-3) | a tap calls `uploadCrossSeed`; a throttled or busy answer is a visible « en file », not a duplicate refusal shape | message success without calling → the network hold falls | § 7 Q3 (what bounds the throttle) |
| **R-L23-d** — the confirmation names what will be published, before any call (NE-DOIT-PAS-6, this direction) | the confirmation's own copy names the tracker and the files, and, if § 7 Q1 reads B, the medium's own eligibility | confirm without naming the tracker → falls | § 7 Q1 |
| **R-L23-e** — the badge's slot is filled, not re-derived (round 8 Q8; re-aims L17's R-L17-g) | the Trackers badge's `crossSeed.failed` count already includes `creation_failed` and `publish_failed`, WITHOUT a new component added to the sum | add a fifth summed component instead of reusing the two counted families → the re-aim falls, naming the drift |
| **R-L23-f** — the right, on both sides (L18's own convention, « every rule proving a right names its two halves ») | the gesture ABSENT from the DOM for an account without `trackers.upload` (§ 0.2); the call refused `403` when forced | offer the act to a non-holder → falls | — (settled, § 0.2; whichever role Comptes assigns the right to at the moment the rule runs) |

---

## 5. What this design does NOT draw

- **The tracker's own publication rules, enforced.** § 7 Q3's reading A — the backend enforces them, the
  interface never pre-validates — is this document's own DEFAULT reading (the D7 discipline this codebase already
  holds everywhere: declare what is required, let the backend refuse with a clear reason); reading B, if ruled, is
  a materially bigger surface this document explicitly declines to draw ahead of that ruling.
- **A per-tracker upload switch, distinct from the cross-seed switch.** § 7 Q2's reading B, named but not drawn —
  a mechanism, not a choice, waiting on the operator.
- **A history of failed publications, kept until seen.** § 7 Q4's reading B, named (state 8, § 3) but not drawn.
- **A third origin-colour value on L16's own field.** § 7 Q5, open; L16's DESIGN is read, never amended here.
- **Which media may be uploaded, beyond « the engine already has files for it ».** § 7 Q1, open.
- **Anything the engine does.** The backend follows the interface, after the freeze (§ 15) — this lot files
  demands, never an implementation.
- **`docs/reference/backend-demands-architecture.md`.** Its own § 5 (L17's demands) names the reserved slot
  already; this document's § 2 states the SHAPE the operator can read now, but the file itself is amended by the
  steward in a LATER gesture, outside this pull request's scope (§ Non-goals of the brief this design answers to).
- **`docs/reference/operator-method.md`, `product-intent-map.md`, the constitution's own § 19.** The operator's,
  by his own word at round 8 Q18 (« le § 19 de la constitution recevra une phrase, de sa main »).
- **L16, L17 and L18's own DESIGN.md files.** Read, never amended — a contradiction found while reading them is
  reported to the orchestrator, not fixed here.

---

## 6. The register rows and the demands touched

**BUGS.md**, read, not edited (no BUGS.md edit — this PR is documentation only):

- **B-145** — « 797 lines of engine that inject torrents at third parties, and no way to know it happened » —
  `open`, L17's row. L23 touches neither its state nor its text; its own reading half is L17's to close.

**`docs/reference/product-intent-map.md`**, read, amended by the OPERATOR, not by this PR:

- **DOIT-14** — « rendre le cross-seed visible et décidable (§19) » — reads `to draw`, owner **L17** today. L23
  adds no proposal to this row: § 19 point 5 is served by L23's own surfaces once built, and the map's own owner
  field is the operator's to move, not this document's.

**`docs/reference/backend-demands-architecture.md` § 5**, NOT edited by this PR (§ 5 above) — the typed form this
document's § 2 states is what a later steward's gesture is expected to carry into that file's own § 5, alongside
L17's own demands, once L23's questions are ruled.

---

## 7. The five open questions — written OPEN, no choice

Every question below is the brief's own list, transcribed, minus one: the brief's own sixth item, « who holds the
right by default », is corrected in § 0.2, on the orchestrator's reading of organisation ruling 21 — the DEFAULT
holder of any right is configuration (Comptes), never a design choice the operator rules through this document;
what this document owed instead was the right's own NAME and a proposed starting value, both drawn in § 0.2.
Neither reading of the five below is chosen; each carries its two readings and their cost, so the operator
answers with the cost already in view, and this document is amended in ONE LINE per answer, never redrawn from a
blank page.

**OPEN 1 — what may be uploaded.** *Reading A*: only a torrent this application already owns AND is currently
seeding — a complete, healthy copy, never a partial or already-removed one — may have a torrent created from it
and published. *Reading B*: any owned medium's files, even one with no active torrent today (dispatched to
storage, never grabbed as a torrent, or grabbed and long since removed), may have one created — a broader
« make-findable » tool, reachable from the library or the media sheet, not only from the Torrents tab. **Cost**: A
needs no new surface beyond S1 (§ 2.3), drawn on an existing row; B needs a new gesture OUTSIDE
`features/trackers` (the library, or the media sheet), a new eligibility read, and a new confirmation naming why a
file with no active torrent is safe to publish — a materially larger lot.

**OPEN 2 — to which trackers.** *Reading A*: any tracker whose EXISTING cross-seed switch (L17's own, DESIGN §
3.2) is ON — upload rides the same per-tracker gate as ordinary cross-seed, no new switch. *Reading B*: a SEPARATE
per-tracker « accepts uploads » switch, because a tracker may welcome being cross-seeded onto (an injection it did
not itself index) yet forbid a member from creating and publishing a NEW torrent there (many private trackers
require an uploader of record, or forbid duplicate uploads by non-staff). **Cost**: A costs nothing new in
configuration; B needs one new per-tracker boolean — a new Réglages row, mirrored on the tracker's own entry, the
SAME « one write, two doors » pattern L16/L17 already use (cheap in KIND, but a new key nonetheless), and the
named state `tracker-upload-disabled` (§ 3, state 6) becomes real rather than merely proposed.

**OPEN 3 — what the tracker's rules require.** *Reading A*: the maquette draws NOTHING of a tracker's own upload
rules (category, private flag, source tag, a minimum ratio to be ALLOWED to upload) — the backend enforces them
and answers a refusal with its own reason, the SAME discipline every other refusal in this codebase already
carries (NE-DOIT-PAS-4); the interface never pre-validates. *Reading B*: the interface reads a per-tracker rule
SET and blocks or pre-fills the gesture before the call, so a doomed publication never reaches the network. **Cost**:
A is the D7 discipline this codebase already holds everywhere — no new read, no new schema beyond § 2.1's Q and R;
B needs a new per-tracker rule read, a new mock shape, and a form — a materially bigger surface for a case
NE-DOIT-PAS-8 already treats as the backend's to enforce, and named state 7 (§ 3) becomes real only under B.

**OPEN 4 — what a failed or refused publication leaves behind.** *Reading A*: NOTHING beyond the pair's own row
reading « erreur de cross-seed » with its reason (§ 2.2) — no temporary file, no partial record, ever surfaces;
the same discipline as an ordinary cross-seed refusal. *Reading B*: a failed attempt is recorded on the TRACKER's
own entry, the SAME shape L16 already built for a broken obligation (« N obligations rompues », round 10 Q4) —
« N publications échouées », unfolding, a « vu » per row — kept because a tracker that repeatedly refuses this
account's uploads is a signal worth accumulating, unlike an ordinary search miss. **Cost**: A needs nothing beyond
what L17 already draws; B repeats a mechanism L16 already had to build once (a new sub-disclosure, a new « vu »
write, a new demand) — not a new KIND of cost, but a second instance of one, and named state 8 (§ 3) becomes real
only under B.

**OPEN 5 — how the ratio counts an uploaded torrent.** *Reading A*: EXACTLY like any other cross-seed entry (L16's
own rule, ruling 18) — the ratio on that tracker is computed on the torrent's own SIZE, never a division by zero,
whether the pair got there by search or by upload; nothing here changes L16's own derivation, and the uploaded
pair is simply one more `active` row of it. *Reading B*: an uploaded-and-published torrent is, on THAT tracker, an
ORIGIN in its own right — the application created it there, it did not merely cross-seed an existing community
torrent — so L16's own origin-colour mark (§ 2.3 item 3 of its DESIGN) should read a THIRD value, distinct from
« the original grab » and « a cross-seed of it », because an operator auditing where a title's copies come from
would otherwise read a self-created original as a plain cross-seed and misjudge which copy exists by the
application's own hand. **Cost**: A costs nothing beyond what L16/L17 already carry; B is one new enum value on an
EXISTING field, touching the one place S3's own colour mark is drawn (L16's, read never amended by this document)
— cheap in the writing, but a value nothing today anticipates, and it is the one reading among the five that
reaches INTO another lot's own field rather than adding a field of L23's own.
