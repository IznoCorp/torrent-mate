# L18 — Accounts, rights and Plex identity (§ 17) · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L18 — §17, accounts, rights and Plex identity`
(its « Where it lives » and « Done when » lines). It is not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every figure carries the
command that produces it, every decision carries its reason, every screen carries its named states. **Nothing under
`frontend/maquette/design/` was touched to write it** — it is prose and numbers.

**Amended 2026-09-27** (this pass), on `origin/main` after merging L16's re-drawing (#623, `a6fb6fc1d`) and L17's
design and plan (#617, `709dbb3e9`) — both now LANDED, not pending. **L22b has NOT landed** (`Agent : l22b 2`
still builds it on `feat/maquette-l22b`); every figure about a file L22b creates or moves is still taken from ITS
plan, and the phase that reads it re-takes it at its own opening. This amendment ports: the operator's rulings of
2026-09-27 (round 8, 17 L17+L18 questions; round 9, 17 organisation-and-coherence questions, rulings 20–23; the
auditor's decision-coherence round M1–M9; round 10, 7 questions), and the steward's triage of the coherence audit
`review-archive/coherence-2026-09-27.md` (§ C: F2, F9+C8, F25, F27–F38, F46, F47, F49, F65–F68, C2 (L18 half), and
the L18 porting checklist). **No question a ruling answers stays OPEN** (§ 7 below is now empty of choices); every
audit fix in this lot's scope is applied or named SUPERSEDED with the ruling that replaces it (§ 8).

**Three consequences of the rulings, said before anything else.**

1. **The model inverts: rights belong to ROLES, never to an account** (organisation ruling 20, refining ruling 17).
   The first drawing's table (role → rights, three fixed roles, two per-account "options") is WRONG in its
   mechanism, though right in its DEFAULTS: an account holds exactly the rights of its ONE role; what the first
   drawing called a per-account "option" is now a right some roles hold and others do not — to give ONE household
   member a right the others lack, the Operator creates a NEW role for them (organisation ruling 20's own words:
   « Si je veux donner des droits particuliers à un utilisateur je lui crée un rôle particulier »). § 1.2 redraws
   the model on this basis; § 2.2's identities are now genuinely DIFFERENT ROLES, not one role with a toggle.
2. **Two roles are the system's, indelible** (organisation ruling 22): a DEFAULT role every new account receives
   (its rights are configurable, it is not deletable) and an ADMIN role that holds NO rights list — it bypasses
   the ACL entirely, including rights created later, and cannot be modified or removed. Every other role — the
   provided Household Member, Plex Guest, and any variant — is ORDINARY configuration, seeded as a starting value,
   never hardcoded as a case the interface tests for.
3. **The mock still gains identities, and they are still INVENTED** (§ 2.2, unchanged in spirit): marked
   `x-unseeded`, turned on only by a named state, never presented as lived data (`product-intent.md` § 13). The
   resting maquette stays the Operator's — that property is proved, not asserted (R-L18-a).

**Its spine is not mine.** `product-intent.md` § 17, as amended 2026-09-27, dictates the lot: roles hold rights, one
role per account, two system roles, a requester (now requesterS, plural) on every acquisition, the Plex SSO ADDED
with e-mail linking, a rights-less Plex user admitted read-only through the DEFAULT role's own seed, the
Acquisition section absent for an account that can neither request nor see, the staging ceiling generalised to a
per-instance list of forbidden writes (preprod), and a right proved on BOTH sides. This document transcribes the
operator's rulings, citing each as « ruling N » or « round R, question Q » (`docs/reference/operator-method.md`);
where the drawing itself makes a call the rulings leave to configuration (organisation ruling 21's own principle),
it says so and marks the value a PROPOSED seed, never a forced choice.

---

## 0. What L18 owes, said once

The application stopped being a single-occupant control post on 2026-08-26 (§ 17), and the interface still is one:
`readAccount` answers a name, an e-mail and an avatar; no surface asks « may this account do this? »; the only
read-only mechanism is a flag one page reads (§ 0.2, fact 6). L18 makes the interface show **what THIS account can
do**, and lets the Operator manage roles, their rights, and who holds each role.

### 0.1 The clauses, one by one, each with its surface

| # | What is dictated | Source | Surface (§ 3) | Phases |
| --- | --- | --- | --- | --- |
| 1 | An action the account may not exercise is **not offered, then refused** — the offer disappears; a `403` after a gesture is an interface defect | § 17 point 1; NE-DOIT-PAS-3 applied to rights | every S; § 5's rule (« absent side ») | all |
| 2 | What the account cannot do stays **visible and explained** where hiding it would mislead (§ 8: nothing in silence) | § 17 point 2 | S3 (a place not held), S4 (a card read-only), S7 (the ceiling) — resolved OPEN 3 = B, every such place | 6, 7, 13, 17 |
| 3 | The read-only role is **absorbed**: one authorisation path, an instance-scoped list of forbidden writes, never a second mechanism | § 17 point 3; ruling 23 (preprod) | S7; the model (§ 1.2) | 3, 17 |
| 4 | **The bottom bar is composed by rights**: Acquisition and Découvrir for the accounts that hold `acquisition.request`; Médiathèque for `library.read`; Trackers for `trackers.view` | § 17 point 4; ruling 17 (everything is ACL) | S2 | 5, 9 |
| 5 | **Rights belong to roles**, one role per account; two system roles (Default, Admin); Admin bypasses the ACL entirely and cannot be modified; Default's rights are configurable and it cannot be deleted; every other role is ordinary configuration | ruling 20, ruling 22 | the model (§ 1.2) | 3, 22 |
| 6 | **Every access — a view or an act — is an ACL right**, and its default holder is what the first drawing called a "role"; « réservé à l'Opérateur » in the constitution and this design reads « not granted by default to any role but Admin » | ruling 17 | § 1.2's rights table, throughout | 3–7 |
| 7 | **Every acquisition has a requester, and MAY HAVE SEVERAL** — a follow's own table of requesters; each pilots it, each has per-requester settings (quality, pause), the highest quality wins, pause needs every requester who holds the pause right | round 9 Q16 (= B); round 10 Q6 (= C, precised) | S4 (the plural line, L22b's port); S9 | 8, 11, 12, 14 |
| 8 | **Own tunnel**: a requester pilots the tunnel of an acquisition they requested, read-only on the others' | § 17 | S4 | 13 |
| 9 | **A per-acquisition quality override**, and now a **per-acquisition pause**, are ROLE rights, never account options; only requesters whose role holds the right enter the "highest/all" computation | § 17; round 10 Q6 precision | S4 | 14 |
| 10 | **Plex SSO is ADDED, not substituted**; the password right (`auth.password`) is held by Admin by default and grantable to any account in Comptes; a local account carries a mandatory e-mail; a matching e-mail LINKS the two, and either way in works for the account that holds the right | § 17; C3 reading C, proposed as the reconciling seed | S1; S9 | 20, 21, 26 |
| 11 | **A Plex user with no granted right beyond the Default role is admitted read-only**, library only — the Default role's own seed IS this case, not a distinct mechanism | § 17 | S1; S2 (one place, no bar — OPEN 7 = A) | 9, 21 |
| 12 | **What an account sees by default**: not the acquisitions it did not request. An account holding neither `acquisition.request` nor `acquisition.see.others` **does not see the Acquisition section** — the named exception to rule 2; pipeline and configuration stay visible, marked and explained as reserved (OPEN 3 = B), never silently absent | § 17 | S2, S3, S4 | 6–9 |
| 13 | **A per-instance list of forbidden writes**, generalising the staging ceiling — the current `:8711` instance forbids every write; the future preprod forbids only `library.delete` | ruling 23 | S7 | 17 |
| 14 | **A right is proved on BOTH sides, separately** | « Ce que cela impose à la preuve » | § 5 — every rule names its two halves | all |
| 15 | **Accounts and roles are managed by the Operator alone**, on a first-level « Comptes » page of the menu, in the `configuration` group | ruling 14; round 8 Q9 (= B, RULED, closing OPEN 1) | S9 | 22–26 |
| 16 | **Profil is the connected account and its preferences, for everyone**; « Les autres comptes » leaves Profil | ruling 14 | S8 | 18, 19 |
| 17 | Every place speaks where it lives, and **the rights filter the badges with the bar, with no rule more** — and the badge sum, and every count, is by RIGHTS, never by the account's raw ownership (M3) | ruling 12; auditor's M3 | S2, S3 | 5, 6 |
| 18 | Système is reached from the drawer, **at its right**; Maintenance opens under the SAME right as Système (ruling 13) | ruling 15; ruling 13 | S3 | 6 |
| 19 | The media sheet's cross-seed block is gated by the SAME right as the Trackers page it summarises — **drawn here, not L17's** | § 19; L17 OPEN 1 = B; F25 | S6 | 27 |
| 20 | **A role that opens no page** lands on a dedicated route saying so, with sign-out only — no bar, no menu | ruling 22, precision | S1-bis | 9 |
| 21 | **An account's entry page** — where Back lands, where the exit guard arms — is the first page of its role's bar, in bar order, or its only page, or (no bar page) the first menu page it opens | round 10 Q7 (= A); `product-intent.md` § 16.2 | S2, addressing throughout | 9 |
| 22 | **Découvrir is a bar row**, gated by `acquisition.request`, fourth place; Acquisition keeps three tabs | round 8 Q20 (= A) | S2, S4 | 9 |
| 23 | **Escalation**: a manager who is not Admin creates, sets and assigns only roles whose rights are INCLUDED in their own role's, never touches their own role, and never touches an Admin account (M7) | round 9 Q14 (= A, measured ≤ 15 points — § 3.9); auditor's M7 | S9 | 25 |

L16's OPEN 2 (ruled A: no right declared at L16; « hidden from other accounts » is proved by L18) is discharged by
R-L18-d on the Trackers row. L22's OPEN 11 (ruled B: the reassign gesture is born with L18) is discharged by S5.

### 0.2 What the tree measures — found while drawing

Each line carries its command; run from the worktree root, on `825fdeaad` (this amendment's merge of L16 #623 and
L17 #617 into the branch). Facts unaffected by the merge are re-cited from the first drawing (46806a88d) with no
re-measurement claimed; a phase re-takes each at its own opening (INDEX.md).

| # | Fact | Command / where |
| ---: | --- | --- |
| 1 | **There is no `app/sign-in.tsx`.** The gate's LOGIC is `app/entry.ts` and its MARKUP is `frontend/maquette/design/index.html` between `login:markup:start` and `login:markup:end`, extracted by `frontend/maquette/serve.py` as the design host's own password page (**F49**) | `git grep -n "login:markup" -- frontend`; `sed -n 1,30p frontend/maquette/design/src/app/entry.ts` |
| 2 | **The drawer's « identity block » is the host's served identity, not the account** (`lib/served-identity.ts`); the account's identity is the header avatar and its menu (`features/account/panel-account.ts`). L18 edits the drawer's ENTRIES, not an identity block (**F49**) | `git grep -n "servedIdentityLines" -- frontend/maquette/design/src` |
| 3 | **`readAccount` answers three fields** — `name`, `email`, `avatar` — and the backend's `GET /api/auth/me` answers `{username}`. No account role is served anywhere on this head (fact confirmed again post-merge) | `personalscraper/web/auth/routes.py:182–194` |
| 4 | **The contract declares a `403` on 62 of its 63 operations** (`takeQueued` WAS the exception; L22b phase 33 retired it in favour of `grabForFollow`, per-follow, § 2.1) | `git grep -c "refused(" -- frontend/maquette/design/src/mocks ':!*.test.ts'` |
| 5 | **No surface asks « may this account? ».** No per-row right exists in `app/navigation.ts` on this head; the bar is `NAVIGATION.filter((row) => row.inBar)` | `git grep -n -i -E "rights\|permission\|isOperator\|isAdmin\|\.role\b" -- frontend/maquette/design/src/app frontend/maquette/design/src/features` |
| 6 | **Read-only exists in the maquette, in miniature** — `SETTINGS_STATE.readOnly`, 24 lines in 12 files, connected to nothing served. Phase 17 kills it (**R-L18-o**) | `git grep -c "readOnly" -- frontend/maquette/design/src ':!*.d.ts' ':!*.json'` |
| 7 | **The backend's staging role is not read-only for acquisition and decision writes today**, and § 17 (ruling 23) now asks for a PER-INSTANCE list rather than a blanket ceiling — the current `:8711` instance's own list is « every write »; preprod's is `library.delete` alone | `tests/unit/web/routes/test_staging_write_policy.py:14–24`; ruling 23 |
| 8 | **After L16 and L17 (both landed), the navigation table holds a `trackers` row, `inBar: true`, no right field** (L16's OPEN 2 = A: no right until L18). **L22b (not landed) will add `discover` and remove `arr`** — this lot's phases that touch the bar re-take the row count at their own opening | `git grep -n "inBar" -- frontend/maquette/design/src`; L16 DESIGN § 4.1; round 8 Q20 |
| 9 | **« Les autres comptes » is still a reserved empty place in Profil** on this head — ruling 14 sends it out (phase 18) | `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(sorted(d['screens']['accountPage']))"` |
| 10 | **Réglages' rubrics are DATA** (`readSettings`, six topics); « Comptes » is not one of them and does not become one — round 8 Q9 rules it a first-level menu page instead (OPEN 1 = B, closing the question the first drawing left to this document) | `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/settings.json'))))"` |
| 11 | **The « quality profile » screen is a client-store write**; the contract has no `quality` operation (0 matches). A `pause` operation does not exist either (round 10 Q6 is new since the first drawing) | `python3 -c "import re;print(len(re.findall('quality',open('frontend/maquette/contract/openapi.json').read(),re.I)))"` |
| 12 | **`requester` exists in the contract as a singular, unaccompanied field.** L22b (its own plan, not landed) is expected to add it to arrival cards only; **F27**: it must also reach `Follow` and every `QueueCard`, as an account id, before L18's filters and reassign can read it — L18 phase 1 adds it if L22b has not by the time L18 opens | `git grep -ci requester -- frontend/maquette/contract frontend/maquette/design/src`; **F27** |
| 13 | **The mock's dials are the fit for an identity**; `MockDials` holds them (`mocks/state.ts`, or L17's own dials module — **F38** moves L18's four dials there rather than growing `state.ts` past 400 non-blank lines) | `sed -n 336,372p frontend/maquette/design/src/mocks/state.ts` |
| 14 | **The design host serves the gate itself, and has no Plex** — a Plex button must stay inside its own marker pair, never the extracted `login:markup` region (**R-L18-q**) | `sed -n 349,395p frontend/maquette/serve.py` |
| 15 | **`app/entry.ts` is 372 lines and `lib/addresses.ts` is 394**, both non-blank — under the 400-line ceiling today, both crossed by this lot's own edits unless split first (**F38**) | `grep -cve '^[[:space:]]*$'` on each file, re-taken at phases 2, 20, 23 |
| 16 | **The engine stops cross-seed at the first verified injection per torrent**, though the mock will show a per-tracker state (L17's own § 0.2 fact, F26 — not this lot's to fix, cited because § 1.2's `trackers.control` right reads L17's shapes) | `personalscraper/acquire/cross_seed.py:229,455` |

Corrections the contract needs (facts 1, 2) and the constitution/engine discrepancy (fact 7, now reframed by ruling 23)
are recorded in § 8, not amended here.

---

## 1. What L18 builds on, and does not redraw

### 1.1 What exists and stays

- **The header avatar and its menu** (`features/account/panel-account.ts`): L18 adds the ROLE NAME to its subtitle
  line — never a hardcoded role string, always what the model reads off the role the account holds — and nothing
  else; its two acts are for every account.
- **Sign-out and the session facts** on Profil — unchanged.
- **The requester line** (L22b's drawing): L18 makes the line PLURAL where a follow has several requesters
  (« demandé par Izno et Léa »), gives the Operator the reassign gesture, and gates the whole line's read on
  `acquisition.see.others` for a card that is not the viewer's own (§ 3.4).
- **The equal-shares bar** (a frame rule, R-L22-s): L18 makes the count VARY by role and reads the rule at each
  count it produces — two, three or four; a role with one page draws no bar at all (OPEN 7 = A, R232's own
  reading: one page IS no bar, not a bar of one).
- **The Trackers row** (L16) and its badge; **the media sheet's cross-seed block** (L17, held for here): L18 gates
  both on `trackers.view`.
- **The confirmation dialogs** of B-300 and B-335 (« … pour tous les comptes du foyer »): unchanged — only
  `configuration.write` holders write configuration, and that stays Admin by default.

### 1.2 The model — one derivation, the rest reads it

The lot's first act is a MODEL: **one function from what the server answered to what THIS account may do**, in
`features/account/`, read by every surface through one door. Its input is the account's role's rights, subtracted
by the instance's forbidden-writes list (S7); its output is a closed set of named RIGHTS, plus the entry page and
the forbidden-writes set for the ceiling banner. **No surface compares a role string** — the guard of § 5
(R-L18-b) reads the source for exactly that. **Admin bypasses the model entirely**: its rights answer is « every
right that exists, including one declared after this account signed in » — the function never enumerates them for
Admin, it short-circuits (ruling 22: « il contourne les ACL »).

#### 1.2.1 Two system roles, and the rest is configuration (ruling 20, 22)

| Role | Deletable? | Rights list | Rule |
| --- | --- | --- | --- |
| **Admin** | no, and unmodifiable | none held — bypasses the ACL, every right present and future | at least one account must hold Admin at all times (R-L18-u's guard) |
| **Default** | no, rights ARE configurable | seeded to exactly `{library.read}` | every new account (a first Plex sign-in) receives it |
| **Household member**, **Plex guest**, and any variant | ordinary configuration | seeded per § 2.2 below | created, renamed, and re-armed from « Comptes »; not hardcoded anywhere in the frame |

An account with no OTHER role than Default is, by construction, § 17's « utilisateur Plex sans aucun droit ici » —
read-only, library only. **This is not a special case the interface tests for; it falls out of the model.**

#### 1.2.2 The rights, drawn from § 17 and the round 8/9/10 rulings

Names adjust at the phase that files them; the set and its DEFAULT holders are what matters. « Default holder »
names which of the seed roles below carries the right out of the box (§ 2.2); Admin is never listed because it
bypasses every row.

| Right | Default holder(s) | What hangs on it — OFFER side | The call — REFUSAL side |
| --- | --- | --- | --- |
| `library.read` | Default (and so every role that includes it) | Médiathèque, the media sheet, follows' read | the reads themselves |
| `library.delete` | — (Admin only) | the selection and delete flow | `deleteLibraryItems` |
| `library.rescrape` | — | « Re-scraper » on the sheet | `rescrapeMedia` |
| `acquisition.request` | Household member, Plex guest | Acquisition section, Découvrir's bar row, the add/follow flow | `createFollow` and the one-off acquisition act |
| `acquisition.follow` | Household member, Plex guest | « Suivis »; managing one's own follows | `updateFollow`, `deleteFollow`, `restoreFollow` — on one's own |
| `acquisition.pilot.own` | Household member, Plex guest | the tunnel's acts on a card one is a requester of | `requeueJourney`, `rescrapeJourney`, `grabForFollow`, `searchForFollow`, `grabSeasonForFollow` — where the caller is among the target's requesters |
| `acquisition.pilot.any` | — | the same acts on ANY card | the same operations, any target |
| `acquisition.see.others` | — (a variant role adds it) | cards and follows one did not request, read-only | `readAcquisitionQueue`, `readFollows` answer the caller's subset unless held |
| `acquisition.quality.own` | Household member | « Profil de qualité » on one's own requested acquisition | `setAcquisitionQuality`, on one's own |
| `acquisition.pause.own` | Household member | a pause preference on one's own requested acquisition | `setAcquisitionPause`, on one's own |
| `acquisition.reassign` | — | the reassign gesture (S5) | `reassignRequester` |
| `pipeline.control` | — | Système's levers, maintenance runs, `resolveDecision` / `dismissDecision` / `searchForDecision`, the staging writes (`reclassifyStagedMedia`, `restoreReclassifiedMedia`, `resolvePlexMatch`, the staging delete of round 8 Q16) — **F28** | the same operations |
| `trackers.view` | — | the Trackers row and page; **also gates the media sheet's cross-seed block (§ 19)** — same right, reused, because both show tracker cross-seed state from a different entry point (granularity justified: splitting it would let an account see the block without the page it summarises, which serves no reading of § 19) | the tracker reads, `readMediaCrossSeed` |
| `trackers.control` | — | the tracker's cross-seed switch (with its confirmation option), « Retirer de qBittorrent », « couper le cross-seed » per torrent/tracker, « Chercher un cross-seed », « Ne plus partager ce titre » — **F28**, as these acts stand once L16/L17 land | the matching write operations |
| `system.view` | — | Système AND Maintenance, same right (ruling 13) | reads under `/api/system`, `/api/maintenance` |
| `configuration.view` | — (implied by `configuration.write`) | Réglages, `/settings/*`, including `/settings/ranking` — **F31** | the configuration reads |
| `configuration.write` | — | the config editor, secrets, restart, ranking preview | `updateConfigurationFile`, `updateSecrets`, `restartWeb` |
| `accounts.manage` | — | « Comptes »: roles, their rights, assigning a role to an account | the account/role operations (§ 2.1); escalation guard applies (§ 3.9) |
| `auth.password` | — (Admin holds it by default; grantable) | signing in with a password | the password door — refused, with a reason, to an account that does not hold it |

**`§ 1.2's split of the first drawing's single `trackers.view`/`system.view` row into three (`trackers.view`,
`system.view`, `configuration.view`) is F31**: § 17 keeps Trackers, Système and the configuration apart (the
Member holds « ni visualisation ni modification de la configuration » even where a variant role might one day open
Trackers or Système), so one row conflated three doors that must open independently.

**The ceiling** (S7) subtracts a NAMED LIST of forbidden writes — never a blanket « every write », except that on
the current `:8711` instance the served list names every write right by construction (ruling 23); on preprod it
names `library.delete` alone. The list is read from the server, never guessed from an environment variable name —
**the source hold of R-L18-b covers this too**. **Signing in and out are session acts, never rights** — `signIn`,
`signOut` and `signInWithPlex` answer for every identity including under any ceiling (F28).

---

## 2. The contract (D7) — and it comes FIRST

D7: the maquette declares the contract its interface REQUIRES; a divergence is filed by EDITING THE CONTRACT
(`frontend/maquette/contract/openapi.json`) and regenerating `docs/reference/frontend-backend-demands.md`
(`python3 scripts/compare-contracts.py --write`, then `--check`). It invents no shape the constitution and the
demands do not name.

### 2.1 What the surfaces read, and what already exists

| Surface | Reads / acts through | Declared today |
| --- | --- | --- |
| every surface — the rights | `GET /api/auth/me` (`readAccount`) | **re-shaped** (demand D): the role's NAME (for display only — never compared), the closed set of rights it carries, whether a Plex account is linked, the entry page, and the instance's forbidden-writes list |
| the gate — Plex sign-in | — | **no operation** — demand E (`signInWithPlex`) |
| S4 — the requester(s), the lists | `readAcquisitionQueue`, `readFollows`, `readJourney` | `Follow` and every `QueueCard` gain a `requesters: AccountId[]` field (**F27**, plural from the start — round 9 Q16 lands before this lot opens); the answers differ by caller's membership in that list |
| S5 — the reassign gesture | — | **no operation** — demand I, keyed for both card and follow (F27); its read of the chooser's account list is a NARROW read (names, roles, Plex link) implied by holding `acquisition.reassign` itself, not a separate operation (**F46**, the narrow-read branch) |
| S4 — quality per acquisition | — | **no operation** — demand K; `backend-demands-architecture.md` § 3 |
| S4 — pause per acquisition | — | **no operation** — demand P (`setAcquisitionPause`); round 10 Q6 precision |
| S6 — the media sheet's cross-seed block | — | **no operation** — demand C (`readMediaCrossSeed`), taken over from L17's own first drawing per **F25**: L18 files it, gated by `trackers.view`, refused `403` when forced |
| S7 — the ceiling | carried by `readAccount` (demand D) | its shape changes from `{readOnly, restartRequired}` to a forbidden-writes list; `readConfigurationStatus` DROPS `readOnly`, keeps `restartRequired` (**F66**) |
| S9 — the roster, roles, rights, creation | — | **no operation** — demands F, G, H |
| the reads' refusal side | — | every VIEW right also gains a `403` on the reads it gates — Système, Maintenance, Trackers, Réglages, the configuration reads (**F30**); no new operation, an edit of existing ones, like `grabForFollow`'s |
| the refusal side, writes | `Problem` responses | 62 of 63 already declare `403`; `grabForFollow`, the per-follow grab operation, gains it (**F42** — L22b phase 33 retired `takeQueued` in its favour; row L re-aims at it, settled, not conditional) |

### 2.2 The mock: identities as ROLES, dials, one guard

**The identities.** `seeds/accounts.json` (new; `seeds/account.json` stays, the Operator's row, role Admin) holds
five invented accounts, each a genuinely DIFFERENT ROLE now (§ 0, consequence 1) — no per-account "option" field
survives:

| Id (a label, not a person) | Role held | Role's own rights beyond `library.read` | Plex | Proves |
| --- | --- | --- | --- | --- |
| `izno` (real, `account.json`) | Admin | bypasses the ACL | linked, the server's owner | the resting maquette; every right present |
| `household-member` | Household member | `acquisition.request`, `.follow`, `.pilot.own`, `.quality.own`, `.pause.own` | linked | the Member's offer and refusal sides; quality/pause held |
| `household-member-sees-all` | Household member (voit tout) | the above **+ `acquisition.see.others`** | linked | a DIFFERENT role proving the right on, per ruling 20's own mechanism |
| `guest` | Plex guest | `acquisition.request`, `.follow`, `.pilot.own` | linked | the guest's offer and refusal sides; quality/pause absent by default |
| `guest-with-quality` | Plex guest (qualité) | the above **+ `.quality.own`, `.pause.own`** | linked | the two rights held by a variant role |
| `plex-without-rights` | Default (nothing beyond it) | — | linked, no extra role | the Acquisition section absent; no bar (OPEN 7 = A) |

Names are neutral labels, `example.invalid` e-mails (RFC 2606). **The point is now the ROLE, not a toggle**: an
account's rights ARE its role's, so proving an option is proving a SECOND role that adds exactly one right —
exactly what the profile's role-name line will show truthfully (ruling 20: « il ne ment jamais »).

**The dials** (`MockDials`, moved to its own module per F38 if `mocks/state.ts` is already past 400 non-blank
lines at phase 2's opening): `setIdentity(id)`, `setForbiddenWrites(list)` (replacing `setCeiling(on)` — a named
list, not a boolean, per ruling 23), `setPlexReachable(on)`, `setInventedRequests(on)`. The resting maquette
proof (R-L18-a) is unchanged in shape: dial off, identity `izno`, no invented row readable, no existing state
moved.

**The mocks MOVE**: a role change moves the affected account's next `readAccount`; a reassignment changes whose
list a card is on; an override changes the acquisition's chosen profile or pause; a created role or account
appears in Comptes; a Plex sign-in answers the dialled identity.

**The refusal — ONE guard.** `route()` gains a declared RIGHT; one check in the mock layer compares it with the
dialled identity's role's rights (imported from § 1.2's model) and the forbidden-writes list, answering
`refused(403, …)`. **Every write AND every gated read names its right** (F28, F30) — the sweep phase refuses a
route that declares none.

### 2.3 The stream

**Demand M** (unchanged in kind, restated): an account's rights changed (a role's rights, a role assignment, a
Plex link) — the affected account re-reads `readAccount` on the event, no poll (NE-DOIT-PAS-8). Carried by an
existing emitted event with its `because`, or by `updateAccount`'s own answer invalidating the affected identity's
cached read (**F37** — the live-relay guard refuses an event the backend never emits; the mock and the demand's
prose both name a REAL carrier before phase 25 builds against it). The stream carries no rights themselves: the
account re-reads, the model re-derives.

---

## 3. The surfaces, drawn

### 3.0 The two sides, and where hiding would mislead

Every right of § 1.2 is drawn on **two sides** (§ 17 point 1, point 2).

- **The OFFER side.** For the account without the right the act is ABSENT from the DOM — not disabled, not
  greyed, not present-and-refused.
- **The REFUSAL side.** The call, forced by hand, answers `403`, recorded by `answered()`.

**Where hiding would mislead** — resolved, not open, per round 8 question 11 (OPEN 3 = B):

| Where | Drawn as |
| --- | --- |
| a card of another requester (`acquisition.see.others` held) | the requester line and a read-only sentence (S4) |
| the instance's forbidden writes | one statement where each write would have been, and on Profil (S7) |
| Trackers, Système, Maintenance, Réglages, Comptes for an account without the right | **stays in the MENU, marked** — opened (menu or a cold address), it says what it is, that this account lacks the right, and WHO holds it by default (ruling 17's own reading, § 3.3) |
| the Acquisition section for an account with neither `acquisition.request` nor `.see.others` | absent — the named exception (S4) |
| the library's write acts | absent, no explanation (the library is complete) |
| the other accounts, from Profil | absent (S8) |

### 3.1 S1 — The gate: Plex first, the password behind a disclosure

**What exists.** `app/entry.ts` (logic) plus `index.html`'s static markup (fact 1). Named states `signin`,
`signin-error`.

**What is drawn — round 8 question 10 (OPEN 2 = B, Plex first).** « Se connecter avec Plex » is the PRIMARY act;
the password form sits behind a « Utiliser un mot de passe » disclosure, closed by default (**F47**, correcting the
first drawing's own mutation, which had asked to HIDE the form when Plex is offered — the ruled shape keeps it
reachable, collapsed):

1. **The Plex block and the disclosure both live in their OWN marker pair** (`login:plex:start … end`), outside
   `login:markup:start/end` — the design host's password page stays byte-identical (**R-L18-q**).
2. **`auth.password` gates who a password admits** (§ 1.2, C3 reading C): refused, with the reason « ce compte se
   connecte avec Plex », to an account that does not hold it — by default only Admin, grantable to any account
   in Comptes, linked or not. A linked account without the right still signs in with Plex; the right adds a
   password as a SECOND way in for the account that holds it. This reconciles Q10's default gloss (« Opérateur
   seul ») with § 17's letter (« l'utilisateur se connecte par l'un ou l'autre ») — both hold, at different
   points of the same right.
3. **When Plex is unreachable, the disclosure OPENS BY ITSELF** (F47): the gate says so from the answer, and the
   password form is the door of last resort. When Plex is reachable, the disclosure stays closed until tapped.
4. **A Plex user with no role beyond Default is admitted**, read-only, landing on the Médiathèque (S2) — the gate
   reads nothing of rights; the OUTCOME is the frame reading the account after sign-in (`frame-model.md` § « Part
   9 »).

**Named states.** `signin-plex-first` (both ways in, password collapsed); `signin-password-open` (the disclosure
tapped open); `signin-plex-unreachable-open` (the disclosure auto-open, F47); `signin-password-refused` (a
non-holder's password, with its reason); `signin-plex-bare` (a Default-only account's first frame). `signin` /
`signin-error` gain the Plex block and the collapsed disclosure with their existing ids.

### 3.2 S2 — The bar, composed by rights

`app/navigation.ts` declares the pages, `tab-bar.tsx` draws `inBar` rows. L18 adds the right that opens each row;
the bar draws a row when it is `inBar` AND the model grants that right.

| Row | Right that opens it | Admin | Household member | Plex guest | Default only |
| --- | --- | :---: | :---: | :---: | :---: |
| `acq` Acquisition | `acquisition.request` or `acquisition.see.others` | yes | yes | yes | no |
| `lib` Médiathèque | `library.read` | yes | yes | yes | yes |
| `trackers` (L16) | `trackers.view` | yes | no (default) | no (default) | no |
| `discover` Découvrir (round 8 Q20) | `acquisition.request` | yes | yes | yes | no |

**Counts, resolved (round 8 Q20; OPEN 7 = A):** Admin — 4; Household member / Plex guest (default seeds) — 3
(Acquisition, Médiathèque, Découvrir); **Default-only — 0, no bar at all** (§ 17 point 4's own text, amended
2026-09-26: « Une place que la barre n'a pas n'est pas un défaut »; R232's reading: one page IS no bar, never a
bar of one — closes the first drawing's OPEN 7 without amending the operator's « 2 à 4 boutons » rule, which
never claimed to cover zero). **R-L18-d reads 3 and 4 buttons plus « no bar »** for a Default-only identity.

**The menu button's badge** sums `badge()` over the rows the bar does not hold, filtered by the SAME rights (M3:
« le badge du menu compte par droits »); a seeded Système fault gives Admin a badge and a Household member none.

**A role that opens no page** (ruling 22 precision, § 0.1 row 20) lands on a DEDICATED route (`/no-access`) that
says so and offers only sign-out — no bar, no menu drawn around it. This is the Default role emptied of even
`library.read`, a configuration act the Comptes editor allows and the interface must survive without failing at
sign-in.

**Named states.** `bar-household`, `bar-guest`, `bar-rightless` (no bar drawn, height 0); `bar-operator` is the
existing bar at four.

### 3.3 S3 — The drawer: every entry drawn, marked where not held

**Resolved (round 8 question 11, OPEN 3 = B), correcting the first drawing's refused reading A (F29).** The
drawer draws EVERY entry (`app/drawer.tsx`'s groups). An entry the account does not hold is MARKED (a lock glyph,
« Réservé ») and carries **no count** — `drawer.tsx` calls `row.badge()` on every row today; the marked row's
`badge()` returns nothing rather than a real count, so a reserved entry never shows a live number it cannot
explain. Opened — from the drawer or a cold address (`/system`, `/maintenance`, `/settings`, `/trackers`,
`/accounts`) — the place renders the RESERVED explanation, never the page: what it is, one sentence naming the
missing RIGHT (never a role, never an account — ruling 17's own reading), and which role(s) hold it by default.
« Comptes » is a drawer entry under this same rule, present and marked for an account without `accounts.manage`.

**Named states.** `drawer-household` (marked entries visible); `place-reserved` (the explanation, now STANDING —
no longer conditional on a ruling, F29). The table of right-name sentences is built once, in the phase that draws
S3, and reused by Profil (S8, § 3.8) and by S9's own reserved form.

### 3.4 S4 — Acquisition by rights and by requester(s)

Acquisition's three tabs — « Suivis · En cours · À traiter » — are L22b's (Découvrir left the section, round 8 Q20;
the section keeps three, not four — F33 and the porting checklist both note this explicitly).

1. **The lists are the account's** — its own requester membership, or, with `acquisition.see.others`, everyone's
   read-only. **An account holding ONLY `see.others` (no `request`) still opens Acquisition with content** — the
   first drawing's OPEN-3-A-shaped assumption that the section needs `request` is wrong and corrected (**F33**):
   the row's own right is `acquisition.request` OR `acquisition.see.others`, matching § 3.2's bar row exactly.
   **Every count reads the same filtered subset, and NEVER counts another account's read-only cards** (R-L18-g,
   corrected for `household-member-sees-all`'s role, F33).
2. **The tabs are composed by rights**, unchanged in mechanism from the first drawing; « Suivis » now needs
   `acquisition.follow`, held by both seed roles by default (OPEN 6 = A closes the first drawing's guest
   distinction — § 3.4 point 6 below).
3. **The requester line is PLURAL where a follow has several requesters** (round 9 Q16): « demandé par Izno et
   Léa ». **Whether a medium is followed AT ALL is read across every account, never from the caller's filtered
   subset** (**F36**): `followOffered` and Découvrir's « déjà suivi » flag read the UNFILTERED answer; when
   another account already follows it and the caller lacks `acquisition.see.others`, the offer shows a NEUTRAL
   « déjà suivi », naming no one (§ 17 point 2's own explanation rule, applied without breaking the see-others
   option's own privacy).
4. **Own tunnel** — offered on a card the caller is AMONG the requesters of; the Operator (via `pilot.any`) on
   every card. Refused the same way on another's.
5. **Quality and pause are per-acquisition, role-gated, and now MULTI-REQUESTER** (round 10 Q6, precised): only a
   requester whose role holds `acquisition.quality.own` has a quality setting on that acquisition, and only THOSE
   settings enter « the highest wins »; the rest follow the default profile. `acquisition.pause.own` the same —
   « paused » holds only when every requester who holds the right has asked for it. Setting either is offered on
   one's own requested acquisition, under its own right; absent on another's.
6. **« Suivre » and « Ajouter » — resolved (round 8 question 14, OPEN 6 = A).** No distinct guest act. The SAME
   gesture for everyone: « Suivre » on a series (durable, until retrait), « Ajouter » on a film (until its Plex
   confirmation, ruling 3). What differs is which requesters hold `acquisition.request`/`.follow`, never the verb.
7. **The floating « ＋ » is gated by `acquisition.request` through the model** (**F65**) — absent for a
   `see.others`-only identity and for an account under a forbidden-writes list that covers it.
8. **The section absent** (the named exception, unchanged): an account holding neither `acquisition.request` nor
   `acquisition.see.others` has no Acquisition row, no tabs, no badge, no address — its landing is elsewhere in
   its own bar order (§ 3.2's entry-page rule).

**Named states.** `acq-household`; `acq-household-sees-all`; `acq-see-only` (**F33**, holding only `see.others`,
tabs populated with everyone's read-only content, no `+`); `acq-guest`; `acq-operator-all`; `acq-card-read-only`;
`acq-card-plural-requesters` (the line names two or more); `quality-own-offered` / `quality-own-absent`;
`pause-own-offered` / `pause-own-absent`.

### 3.5 S5 — The reassign gesture, resolved (round 8 question 13, OPEN 5 = A)

**« Réaffecter… » is an act of the card's panel and the follow's panel**, offered to whoever holds
`acquisition.reassign` (Admin by default). **Reading A only** — an act in `panel-journey.ts` (three acts today)
and the follow's panel; nothing added to the card's own DOM, so every existing state is unmoved for Admin.

**M9 (auditor's coherence round): the chooser lists only accounts that SEE the card** — those holding
`acquisition.see.others`, or already a requester of it, or Admin — never the full roster, which would let a
reassignment hand a card to an account with no way to find it again.

**What it does.** Picks another eligible account; `reassignRequester` (demand I, keyed on card AND follow — F27)
moves ONE requester off and the chosen account on; the line updates and, where the follow keeps other requesters,
stays plural. The tunnel is unaffected (§ 20: it belongs to the medium).

**Named states.** `acq-reassign-chooser` (accounts filtered to those who see the card, M9); `acq-reassign-done`.

### 3.6 S6 — The Médiathèque and the sheet, split by right

`library.delete` and `library.rescrape` (split from the first drawing's single `library.write`, § 1.2 — the
granularity ruling 23's preprod list needs: it forbids DELETION alone, and a single combined right could not
express that). Neither held by default outside Admin. Nothing is missing from a library the account can read
whole, so nothing is explained (§ 3.0).

**The sheet's cross-seed block, drawn HERE (F25), not L17's.** L17's OPEN 1 = B held it; this lot takes demand C
(`readMediaCrossSeed`), gates the block on `trackers.view` (§ 1.2's granularity note), and refuses it `403` when
forced. The block's own refresh key and its holds (L17's R-L17-b, R-L17-k, as they stood before L17 dropped
them — F25) are carried here as **R-L18-w**, proved on the SAME six identities as every other right (§ 2.2), not
a seventh invented for this purpose alone.

### 3.7 S7 — The forbidden-writes list absorbs the staging ceiling (ruling 23)

1. **The flag dies** (fact 6): the model reads a served LIST, never a boolean; `settings-read-only` turns
   `setForbiddenWrites([...every write...])` rather than a page-local flag.
2. **Every write the list names is absent, for every role — Admin included** — the list subtracts before the
   role adds (§ 1.2). **The current `:8711` instance's list is every write**; **preprod's list is `library.delete`
   alone** (ruling 23, precised: preprod writes into the PROD library — replace, merge, NFO rewrite — and only
   explicit deletion is forbidden there). This lot draws the MECHANISM (a named list, read from the server); which
   instance serves which list is the backend's, not drawn here.
3. **It says why**, once, where a write would have been, and on Profil (S8) — naming the forbidden right(s), not
   a generic « lecture seule » where the list is partial (preprod's own case).
4. **The refusal side is the mock's guard** (§ 2.2).

**Named states.** `ceiling-operator` (every write absent, Admin); `ceiling-preprod` (only `library.delete`
absent — **new since the first drawing**, ruling 23); `settings-read-only` (re-driven).

### 3.8 S8 — Profil: the connected account, its role, what it can do

« Les autres comptes » leaves (ruling 14). Profil gains: the ROLE's NAME (never compared, only displayed — it
never lies, ruling 20); a section « Ce que ce compte peut faire », listing the held rights and, for each one it
lacks that would otherwise surprise, the reason and WHICH role(s) hold it by default (reusing S3's sentence table,
§ 3.3); the Plex link's state; the forbidden-writes reason when the instance carries one.

**Named states.** `profile-operator`; `profile-household`; `profile-guest`; `profile-ceiling`;
`profile-preprod` (a partial list, **new**).

### 3.9 S9 — « Comptes »: roles, their rights, and who holds each (ruling 20)

**Resolved (round 8 question 9, OPEN 1 = B): a first-level menu page**, address `/accounts`, route, navigation
row — grouped `configuration`, beside Réglages — reserved to `accounts.manage`. Not a Réglages rubric (fact 10;
ruling 14's B refused A).

**What is drawn:**

1. **The roster.** One row per account: name, ROLE (a role, never a raw rights list), Plex link, marked « sans
   droits » for a Default-only account.
2. **The roles editor.** Create, rename, and set the rights of an ORDINARY role (never Default's name, never
   Admin at all — its row is not editable). A role's rights are toggled from § 1.2's own list, each with a
   one-sentence explanation.
3. **Assigning a role to an account.** One role per account (ruling 20's precision, verbatim « 1 seul »); changing
   it moves the roster and reaches the affected account through demand M's event.
4. **A new account.** Name, MANDATORY e-mail, an initial role (never Admin by a non-Admin manager — the
   escalation guard below); a matching e-mail LINKS to Plex.
5. **The Plex link**, per row and in the detail.

**Escalation (round 9 Q14 = A, measured).** A manager who is not Admin: creates, renames or assigns only a role
whose rights are a SUBSET of their own role's — greyed on screen, refused by the guard if forced; never modifies
their own role; **never touches an account whose role is Admin, to view or to change** (M7, the coherence round's
own addition to Q14). **Measure**: the guard is a set-inclusion check plus its greying and one hold with its
mutation — no new contract shape, no new screen, ≈ 8–10 points inside phase 25's existing budget (already ≤ 15
without it per INDEX.md; the phase's own re-measure at opening confirms it stays under 15 with the guard added,
or the guard is cut into its own phase). **Reading A stands**; B (« managing accounts = Admin only », no
escalation logic) is not needed unless the re-measure at phase 25's opening says otherwise, in which case the
phase records which and why, per Q14's own instruction.

**Guards, restated on rights (F2, superseded from the first drawing's role-string version):** the operation
refuses to remove `accounts.manage` from the last account holding it, and to remove `auth.password` from the last
account holding it (the door of last resort must remain); it refuses to leave zero accounts on the Admin role.

**Named states.** `accounts-roster`; `accounts-roles` (the roles editor, **new** — the first drawing had no
surface for editing a role's own rights, since it assumed roles were fixed); `accounts-detail`;
`accounts-last-admin`; `accounts-create`; `accounts-create-refused`; `accounts-escalation-greyed` (**new**, M7);
`accounts-forbidden` (the address, for an account without `accounts.manage` — S3's reserved form).

---

## 4. The named states

**Measured before naming them** (L22's counting command, re-run on this head after the L16/L17 merge):

    python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"

The count is re-taken at phase 2's opening (L16 and L17 have both moved it since the first drawing; L22b has not
landed and will move it again before L18 opens). **This lot adds up to 37 states**, up from the first drawing's 31,
in a new `harness/states/rights.ts` file: 8 more than before — `signin-plex-first`/`signin-password-open`/
`signin-plex-unreachable-open` replace the first drawing's two Plex states (net +1, F47); `acq-see-only`,
`acq-card-plural-requesters`, `pause-own-offered`/`pause-own-absent` are new (F33, round 9 Q16, round 10 Q6);
`ceiling-preprod`, `profile-preprod` are new (ruling 23); `accounts-roles`, `accounts-escalation-greyed` are new
(ruling 20, round 9 Q14/M7); `place-reserved` moves from conditional to STANDING (net +0, it already existed in
the count); `media-cross-seed`/`media-cross-seed-hidden` are drawn here now, not conditionally carried from L17
(net +0, already counted). Every id is English, reachable by `window.__go`, French-labelled in the panel.

### 4.1 What the oracle will do (D8)

Unchanged in method from the first drawing: **the oracle draws Admin's application and is blind to another
role's absence.** For every state that existed before this lot, Admin's surface is unmoved; the phases below name
exactly where it diverges (unchanged rows omitted from the first drawing's table are not repeated — only what
this amendment adds or changes):

| Phase | Existing states that WILL diverge | Reason |
| --- | --- | --- |
| 5 | none by the oracle (it is silent over the bar's own buttons, D8) | R-L18-d reads the buttons, or nobody does |
| 6 | none for Admin — every drawer entry Admin held before still renders, now unmarked | F29: marked entries are new states, not divergences |
| 8, 9 | `acq-*` states only if a tab or count changes for Admin — it must not | STOP A otherwise |
| 20 | `signin`, `signin-error` on `login/form` — the Plex block AND the disclosure | F47 |
| 27 | `media-cross-seed*` for Admin, drawn fresh here | R-L18-w |
| all others | none | STOP A |

**This lot is held by § 5's rules or by nobody** — the oracle proves nothing about a right absent for another role.

---

## 5. The rules that bite

Numbers re-bound at phase 2's opening against `origin/main` at that moment (order 38, F68 — the highest number
across the branch's own head AND every open branch running beside it, since L22b is still open). **Every rule
proving a right names its TWO halves.**

| Rule | Phase | What it READS | The mutation that fells it |
| --- | ---: | --- | --- |
| **R-L18-a** — the account, from the answer; the resting maquette whole | 2 | unchanged in shape from the first drawing (§ 2.2) | leave an invented row readable at rest → falls |
| **R-L18-b** — one derivation, source holds | 3, 17 | role × rights → the set § 1.2 says; **no file compares a role string**; **no file reads `readOnly`** (phase 17); **the forbidden-writes list is read from the server, never an env-style guess** (new hold, ruling 23) | flip one cell → falls; guess the list → the new source hold falls |
| **R-L18-c** — the refusal side, everywhere, READS AND WRITES | 4, and a new phase before 5 (F30) | every write (§ 1.2's full enumeration, F28) AND every gated READ (Système, Maintenance, Trackers, Réglages — F30) answers `403` for an identity lacking the right; `see.others` stays a subset filter on a 200, never a 403 | drop a right from a route → the sweep names it |
| **R-L18-d** — the bar by rights, both sides | 5, 9 | buttons drawn = exactly the rights open; 2, 3 or 4 buttons, or NONE for Default-only (OPEN 7 = A); absent pages ABSENT from the DOM | hard-code Admin's bar → falls elsewhere |
| **R-L18-e** — one derivation for badges, BY RIGHTS (M3) | 5, 6 | menu badge = sum over rows the account can open; drawer draws every entry, **marked ones carry no count** (F29) | sum unfiltered → falls; show a count on a marked row → falls |
| **R-L18-f** — a place not held explains itself, STANDING (F29, no longer conditional) | 7 | the drawer entry, marked; opened, names the missing right and who holds it | render the page instead → falls |
| **R-L18-g** — the lists are the account's, every count agrees, INCLUDING a see-only role (F33) | 8 | for `household-member`, `household-member-sees-all`, `guest`, `izno`, and a see-only identity: the subset, the tab counts, the badge agree; **never counts another's read-only cards** | count the unfiltered set → falls |
| **R-L18-h** — the section absent | 9 | no `acquisition.request` and no `.see.others` → no row, tab, badge, address; lands per the entry-page rule (round 10 Q7) | leave the row → falls |
| **R-L18-i** — the reassign offer, filtered by who sees the card (M9) | 11 | offered to `acquisition.reassign` holders only; the chooser excludes accounts that cannot see the card | list every account → falls |
| **R-L18-j** — the reassignment moves, on card AND follow | 12 | `reassignRequester` answered; one requester off, one on; forced by a non-holder → `403` | toast without calling → falls |
| **R-L18-k** — own tunnel, membership not single ownership | 13 | offered where the caller is AMONG the requesters | offer on a non-member's card → falls |
| **R-L18-l** — quality, role-gated, multi-requester (round 10 Q6) | 14 | only requesters whose role holds the right enter « highest wins »; absent for the rest | count an unrighted requester's setting → falls |
| **R-L18-l-bis** — pause, role-gated, multi-requester | 14 | « all » = all requesters holding `acquisition.pause.own`; absent for the rest | count an unrighted requester → falls |
| **R-L18-n** — the library, split rights | 16 | `library.delete`/`.rescrape` absent for non-holders; `403` when forced | leave the selection bar → falls |
| **R-L18-o** — the forbidden-writes list absorbs the role, every case | 17 | with a list on, every write it names is absent, for EVERY role; `SETTINGS_STATE.readOnly` does not exist (source hold) | leave one lever offered → falls naming it |
| **R-L18-p** — Profil is the connected account, role NEVER hardcoded | 18 | no other account, no reserved place; role read from the model, per identity | print a constant role → falls |
| **R-L18-q** — the gate offers Plex first, host page unchanged | 20 | both ways in, per OPEN 2 = B; the password page byte-identical (R72's bridge) | move a block inside the extraction → falls |
| **R-L18-r** — the gate's outcomes, `auth.password`-gated | 21 | a non-holder's password refused with reason; Plex unreachable auto-opens the disclosure (F47); the door of last resort for holders | let a non-holder's password through → falls |
| **R-L18-s** — Comptes, both sides, marked not absent | 23 | present and marked for non-holders (F29); `403` on forced calls | leave the entry absent for a non-holder → falls (matches F29, not the first drawing's own mutation) |
| **R-L18-t** — the roster and the roles editor, from the answer | 24, 25 | one row per account; a role's rights editable, Admin's row not | print a constant → falls |
| **R-L18-u** — a rights change moves, on the real event (F37) | 25 | answered on a REAL emitted carrier; the roster moves; the affected identity recomposes with no refetch; last-Admin and last-`auth.password`-holder guards refuse (F2); **escalation refuses a subset violation and touching an Admin account** (M7) | apply on a timer → falls; allow the last demotion → falls |
| **R-L18-v** — a new account, mandatory e-mail, Plex link | 26 | as the first drawing, unchanged | accept an empty e-mail → falls |
| **R-L18-w** — the media-sheet block, on the model, carrying L17's own holds (F25) | 27 | shown to `trackers.view` holders, absent for others; `403` forced; the block's refresh key and L17's R-L17-b/-k holds proved here | show it to a non-holder → falls |
| **R-L18-x** — the viewer's memory is the viewer's | 9 | a remembered tab the new role does not hold is ignored | read the stored tab unchecked → falls |
| **R-L18-y** — a closed address, marked not absent (F29, F32) | 6, 7 | every `SCREEN_PARENTS` key whose parent the account cannot open, and every in-page link into a gated page, answers the reserved form; the page's reads `403` | remove the guard → falls; render the page on a cold address → falls |
| **R-L18-z** — Profil's list is the model's, names the granting role(s) | 19 | rights held/lacking match the model per identity; a lacking right names who grants it | retype a sentence keyed to a role → falls |

### 5.1 Rules the earlier lots wrote that this lot re-aims

- **L22b's default-tab rule** gains R-L18-x's fall-back — read at L18's own opening, since L22b has not landed.
- **L16's « hidden from other accounts »** is discharged by R-L18-d.
- **`harness/settings.py`'s read-only hold** re-aims onto the forbidden-writes dial in phase 17.
- **L17's R-L17-b, R-L17-k** (the media-sheet block's holds) are CARRIED, not re-derived, into R-L18-w (F25).

---

## 6. The register rows and the demands touched

### 6.1 The register rows

- **B-143** — « §17 has no surface, no contract operation and no lot »: closed by this lot's close (phase 29).
- **B-300 / B-335** — unchanged, not this lot's row.
- Rows this lot finds are written as found, by the phase that finds them.

### 6.2 The demands PROPOSED (D7) — in the register's own form

| # | operation | operationId | what it is for | Filed in phase |
| --- | --- | --- | --- | ---: |
| C | `GET /api/media/{provider}/{providerId}/cross-seed` | `readMediaCrossSeed` (taken over from L17, F25) | the media sheet's cross-seed block, gated by `trackers.view` | 27 |
| D | `GET /api/auth/me` | `readAccount` (re-shaped) | the role's name, its closed rights set, the Plex link, the entry page, the forbidden-writes list | 1 |
| E | `POST /api/auth/plex` | `signInWithPlex` (new) | the Plex SSO | 1 |
| F | `GET /api/accounts` | `readAccounts` (new) | the roster and the roles editor's data, `accounts.manage` only | 10, 24 |
| G | `POST /api/accounts` | `createAccount` (new) | a new account, mandatory e-mail, an initial role | 22 |
| H | `PATCH /api/accounts/{accountId}` / role operations | `updateAccount`, plus role create/rename/set-rights (new) | roles, their rights, role assignment; refuses the last-Admin and last-`auth.password`-holder demotions, and an escalation violation (F2) | 22, 25 |
| I | `PUT /api/acquisition/…/requester` | `reassignRequester` (new) | moves ONE requester off, one on; keyed for card and follow (F27) | 1 |
| K | `PUT /api/acquisition/…/quality` | `setAcquisitionQuality` (new) | the per-acquisition, per-requester quality override | 1 |
| L | `POST /api/acquisition/followed/{followedId}/grab` | `grabForFollow` (F42 — L22b phase 33 retired `takeQueued` in its favour; row re-aimed, settled) | declares `403` | 1 |
| P | — (new) | `setAcquisitionPause` (new) | the per-acquisition, per-requester pause preference (round 10 Q6 precision) | 1 |
| — | every read under `/api/system`, `/api/maintenance`, `/api/trackers`, `/api/config` | (edited, not new) | gains `403` for a non-holder (F30) | new phase before 5 |

**M** — an account's rights changed, a stream row (§ 2.3), carried on a REAL emitted event or `updateAccount`'s own
invalidation (F37) — the operator amends `frontend-backend-demands-stream.md`.

**N** — the forbidden-writes list is per-instance, not a single boolean ceiling (ruling 23, superseding the first
drawing's blanket reading) — the operator amends `backend-demands-architecture.md` § 2.

### 6.3 The clause-map rows PROPOSED (the operator amends the map)

| Clause | Today | After the lot | Proof |
| --- | --- | --- | --- |
| **DOIT-12** — « montrer l'application de CE compte » | `to draw` | `served` | R-L18-b, c, d, g, k, n, o |
| **NE-DOIT-PAS-7** — absorbed read-only | `outside the interface` | `served` | R-L18-b's source hold, R-L18-o |
| **NE-DOIT-PAS-3** on rights | `served` for busy/409 only | extended | R-L18-d, i, k, n |
| **DOIT-14** — the media block | `partly` at L17 | `served` at L18 | R-L18-w |

---

## 7. What this design does NOT draw

### 7.1 Not drawn — and whose it is

- **The backend** — enforcement, persistence, the SSO flow, the account/role store — after the freeze (`product-intent.md`
  § 15; D7). This lot mocks it on invented identities.
- **Deleting or disabling an account.** Not dictated. Not drawn.
- **An approval flow for a proposal.** Not dictated.
- **Sessions of other accounts, a forced sign-out, a per-account audit trail.** Not dictated.
- **Push notifications** — a platform demand, not this lot's.
- **The Trackers page, the ratio, the cross-seed mechanics** — L16, L17's; this lot gates the media-sheet block
  only (§ 19, F25).
- **The tunnel-history half of ruling 3's trace** — assigned by the audit to an L22b phase beside its media-sheet
  trace (C8); this lot's own media sheet edit (§ 3.6) is a DIFFERENT block (cross-seed), and does not draw C8's
  path — named here so it is not silently conflated with S6.
- **The engine of L13, the frame's code beyond §§ 3.1–3.3, 3.9** — untouched (F49 corrects the first drawing's
  own claim that this is the only lot to touch frame code after L15 — L22b and L16 both edit `app/` first; this
  lot re-reads what they left).
- **Multiple Plex servers, a second household, invitations by link.** Not dictated.

### 7.2 OPEN design questions

**None.** The first drawing's seven questions, and L17's OPEN 1, are all ruled (§ 0, § 3, table below). Kept as a
record, chosen nowhere else:

| # | Ruled | Where drawn |
| --- | --- | --- |
| OPEN 1 — where accounts are managed | B — a first-level menu page | § 3.9 |
| OPEN 2 — how the gate offers Plex | B — Plex first, password behind a disclosure | § 3.1 |
| OPEN 3 — a place not held | B — stays in the menu, marked and explained | § 3.0, § 3.3 |
| OPEN 4 — who holds Trackers/Système | B, widened by ruling 17 into « everything is ACL » | § 1.2 |
| OPEN 5 — where reassign starts | A — an act of the card's and follow's panel | § 3.5 |
| OPEN 6 — the guest's request | A — the same act as everyone's | § 3.4 point 6 |
| OPEN 7 — a bar of one place | A — no bar for a single-page role | § 3.2 |
| L17 OPEN 1 — the media-sheet block | B — drawn by L18 | § 3.6 |

No genuinely new OPEN question arose while drawing this amendment; the escalation measure (§ 3.9) is recorded as
a MEASURE and its resulting choice (A), per round 9 Q14's own instruction, not as a fresh open question.

---

## 8. What this design believes the contract or the rulings' letter get wrong

Recorded, not amended — the steward amends the plan, the operator the constitution and the map.

1. **« The gate stays `app/sign-in.tsx` »** — no such file (fact 1; F49). The gate is `app/entry.ts` plus
   `index.html` markup extracted by `serve.py`.
2. **« The drawer's identity block »** — the drawer's block is the host's served identity (fact 2; F49); the
   account's identity is the header avatar. The lot edits the drawer's ENTRIES.
3. **« Behind the served role the backend already exposes »** — the backend serves no account role at all
   (`/auth/me` answers `{username}`).
4. **§ 17 said the staging role makes every write read-only; ruling 23 SUPERSEDES the blanket reading with a
   per-instance list** — recorded as resolved, not as an open discrepancy any more (the first drawing's row 4 here
   is CLOSED by ruling 23, not merely stated).
5. **§ 17 « ce que cela impose à la preuve » cannot be met by the oracle** — unchanged: the oracle draws Admin's
   application; § 5's rules are the proof.
6. **« Les autres comptes » reserved « so the shape is settled »** — ruling 14 sends it out; deleted, not kept.
7. **The first drawing's own claim that this is « the only lot after L15 that edits frame CODE »** is WRONG once
   L22b and L16 are read: both edit `app/` first (L22b the tab bar and drawer badges, L16 the navigation row);
   this lot re-reads what they left rather than editing untouched frame code (F49, corrected in § 7.1).
8. **The first drawing's rights table conflated `trackers.view`/`system.view` into one row** — § 17 keeps
   Trackers, Système and configuration apart even under a role that might one day hold more than the defaults
   (F31); § 1.2 now splits them.
9. **The organisation rulings are cited by number and date** (`docs/reference/operator-method.md`); the branch
   `docs/operator-method-0927` carries the byte-identical file into its own PR (steward's C1, done separately —
   not this document's edit).
