# L18 — Accounts, rights and Plex identity (§ 17) · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L18 — §17, accounts, rights and Plex identity`
(its « Where it lives » and « Done when » lines). It is not restated here; what follows is the drawing the plan executes.

This document is written for a session that has none of the context it was produced in. Every figure carries the
command that produces it, every decision carries its reason, every screen carries its named states. **Nothing under
`frontend/maquette/design/` was touched to write it** — it is prose and numbers, written on `origin/main` at
`46806a88d` (2026-09-27), and the lot opens after L17 (the plan's order is L13 · L22 · L16 · L17 · L18). It is drawn IN
ADVANCE, by the auditor's order 47: a drawing ruled before the code costs zero rework. The plan (`docs/features/maquette-l18/plan/INDEX.md`) cuts the lot in two, at phase 17.

**Three consequences of that date, said before anything else.**

1. **Three lots change the tree this lot reads, and none has landed.** L22 kills Arrivées and gives the card a
   requester line (`docs/features/maquette-l22/DESIGN.md`, merged #612); L16 adds the Trackers row to the bar
   (`docs/features/maquette-l16/DESIGN.md`, merged #614); L17 extends Trackers and draws a media-sheet block for the
   administrator (its design is on the open branch `origin/docs/maquette-l17-design`, read and not amended). Every
   figure below about a file one of them creates or moves is taken from THEIR plans, and the phase that reads it says
   so and re-takes it at its opening. **Figures about files none of them touches are measured on this head.**
2. **The mock gains identities, and every one of them is INVENTED.** The mock has one account (`seeds/account.json`,
   the Plex owner by construction). The proofs need more, and § 2.2 draws them: each is marked `x-unseeded`, exists
   only when a named state turns a dial, and is never presented as lived data (`product-intent.md` § 13). **The resting
   maquette is untouched by them** — that property is proved, not asserted (R-L18-a).
3. **The constitution sentences this lot draws on are on `main`**: § 17 whole, including point 4 as amended
   2026-09-26 (#611, #613). This branch has `origin/main`'s text.

**Its spine is not mine.** `product-intent.md` § 17 « Ce que cela tranche » (dictated 2026-08-30) dictates the lot:
three roles, two per-account options, a requester on every acquisition, the Plex SSO ADDED with e-mail linking, a
rights-less Plex user admitted read-only, the Acquisition section absent for an account that can neither request nor
see, the staging role absorbed as an instance ceiling, and a right proved on BOTH sides. The organisation rulings of
2026-09-26 place the surfaces. This document transcribes them, citing each as « organisation ruling N (2026-09-26,
`docs/reference/operator-method.md`) »; where a ruling left a hole it says OPEN and draws no choice (§ 7.2).

---

## 0. What L18 owes, said once

The application stopped being a single-occupant control post on 2026-08-26 (§ 17), and the interface still is one:
`readAccount` answers a name, an e-mail and an avatar; no surface asks « may this account do this? »; the only
read-only mechanism is a flag one page reads (§ 0.2, fact 6). L18 makes the interface show **what THIS account can
do**, and lets the operator manage who those accounts are.

### 0.1 The clauses, one by one, each with its surface

| # | What is dictated | Source | Surface (§ 3) | Phases |
| --- | --- | --- | --- | --- |
| 1 | An action the account may not exercise is **not offered, then refused** — the offer disappears; a `403` after a gesture is an interface defect | § 17 point 1; NE-DOIT-PAS-3 applied to rights | every S; the rule of § 5 (« absent side ») | 5–17 |
| 2 | What the account cannot do stays **visible and explained** where hiding it would mislead (§ 8: nothing in silence) | § 17 point 2 | S3 (reserved places), S4 (a card read-only), S7 (the ceiling) — OPEN 3 says which places | 7, 13, 17 |
| 3 | The read-only role is **absorbed**: one authorisation path, an instance CEILING that caps every account, never a second mechanism | § 17 point 3; « Ce que cela tranche »; NE-DOIT-PAS-7 (the map's row assigns the interface's share to this lot) | S7; the model (§ 1.2) | 3, 17 |
| 4 | **The bottom bar is composed by rights**: Acquisition and Médiathèque for all who may open them; Trackers for the accounts that hold the right; Système is not in the bar; the bar draws only its buttons, in equal shares, two to four | § 17 point 4 (2026-09-26); organisation rulings 11, 15 | S2 | 5, 9 |
| 5 | **Three roles** — the Operator bypasses the ACLs and may reassign; the Household member consults the library, follows, proposes, pilots the tunnel of what they requested, reads the others read-only, sets the quality profile of their own, has no configuration; the Plex guest reads the library, requests, pilots their own requests only, has no configuration | « Ce que cela tranche » | the model (§ 1.2, the rights table) | 3 |
| 6 | **Two options per account**, set by the Operator: see the acquisitions one did not request (yes/no); set the quality profile of one's own (always yes for the Member; to enable for the guest) | same | the model; S4; S9 (where the Operator sets them) | 3, 8, 14, 25 |
| 7 | **A requester on every acquisition**; a new request carries the connected user; existing ones belong to the Plex owner (Izno); the Operator manages every requester's requests and may **reassign** | same; organisation ruling 9 | S4 (the line is L22's, drawn from the answer); S5 (the gesture, **born here** — L22's OPEN 11 = B) | 8, 11, 12 |
| 8 | **Own tunnel**: the Member and the guest pilot the tunnel of the acquisitions they requested, and read the others read-only | same | S4 | 13 |
| 9 | « Set the quality profile of an acquisition » is a **per-acquisition override**, never the edit of the profile (configuration, the Operator's) | same; `backend-demands-architecture.md` § 3 | S4 | 14 |
| 10 | **Plex SSO is ADDED, not substituted**; only Operator accounts may hold a password without SSO (the emergency door when Plex is unreachable); a local account carries a mandatory e-mail; an e-mail matching a Plex account **links** the two | same | S1 (the gate); S9 (creation, the link) | 20, 21, 26 |
| 11 | **A Plex user with no right here is admitted read-only**, library only | same | S1 (the outcome); S2 (a bar with one place — OPEN 7) | 9, 21 |
| 12 | **What an account sees by default**: not the acquisitions it did not request. An account that can neither request nor see the others' **does not see the Acquisition section** — the named exception to rule 2; the pipeline and the configuration stay visible and explained as reserved, never silently absent | same | S2, S3, S4 — the last sentence is OPEN 3 | 6–7, 8, 9 |
| 13 | The staging role is **an instance ceiling**: on that instance every account is brought down to read-only, whatever its role | same | S7 | 17 |
| 14 | **A right is proved on BOTH sides, separately**: the action absent from the surface for the account without it; the call refused for one that forces it | « Ce que cela impose à la preuve » | § 5 — every rule names its two halves | all |
| 15 | **Accounts are managed by the Operator alone** — list, rights, Plex link — in a « Comptes » rubric of Réglages OR a first-level entry of the drawer; the choice « revient au dessin de L18 sauf mot contraire »; **never in Profil** | organisation ruling 14 | S9 — the place is OPEN 1 | 22–26 |
| 16 | **Profil is the connected account and its preferences, for everyone**; « Les autres comptes » leaves Profil | organisation ruling 14 | S8 | 18, 19 |
| 17 | Every thing speaks where it lives, and **the rights filter the badges with the bar, with no rule more** | organisation ruling 12 | S2, S3 (one derivation; proved once, R-L18-e) | 5, 6 |
| 18 | Système is reached from the drawer, **at its right** | organisation ruling 15 | S3 | 6 |
| 19 | The media sheet's cross-seed block is **for the administrator only** | § 19 (dictated 2026-08-30); L17's S5 | S6 — conditional on L17's OPEN 1 | 27 |

L16's OPEN 2 (ruled A: no right declared at L16; « hidden from other accounts » is proved by L18) is discharged by
R-L18-d on the Trackers row. L22's OPEN 11 (ruled B: the reassign gesture is born with L18) is discharged by S5.

### 0.2 What the tree measures — found while drawing

Each line carries its command; run from the worktree root, on `46806a88d`.

| # | Fact | Command / where |
| ---: | --- | --- |
| 1 | **There is no `app/sign-in.tsx`.** The contract's « the gate stays `app/sign-in.tsx` » names a file that was never made: the gate's LOGIC is `app/entry.ts` (399 lines) and its MARKUP stays in `frontend/maquette/design/index.html` between `login:markup:start` and `login:markup:end` (lines 429–480), **extracted by `frontend/maquette/serve.py`** and served as the design host's own password page. Its style is the `login:entry` region of `styles/base.css` (lines 1067–1268, ~200 lines) | `git grep -n "login:markup" -- frontend`; `sed -n 1,30p frontend/maquette/design/src/app/entry.ts` |
| 2 | **The drawer's « identity block » is not the account.** It is the host's served identity — branch, commit, dirty mark (`lib/served-identity.ts`, drawn by `app/drawer.tsx`). The account's identity is drawn by the header avatar (`index.html:270–291`, `data-account`) and the menu it opens (`features/account/panel-account.ts`, state `sheet-user`). The frame edits this lot makes are therefore: the gate, the navigation table's rows, `app/tab-bar.tsx`, `app/drawer.tsx`'s entries, the menu button's badge — **not** a drawer identity block | `git grep -n "servedIdentityLines" -- frontend/maquette/design/src`; `sed -n 270,291p frontend/maquette/design/index.html` |
| 3 | **`readAccount` answers three fields** — `name`, `email`, `avatar`, all required — and the backend's `GET /api/auth/me` answers one, `{username}`. **Four readers** in the maquette (`features/account/queries.ts`, `avatar.ts`, `page.tsx`, `panel-account.ts`) and **eleven** harness files read the account | `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(json.dumps(d['components']['schemas']['Account']))"`; `git grep -l -i -E "readAccount|/api/auth/me|data-account|sheet-user" -- 'frontend/maquette/harness/*.py' \| wc -l` → 11; `personalscraper/web/auth/routes.py:182–194` |
| 4 | **The contract declares a `403` on 62 of its 63 operations** (34 reads, 29 writes) — the one without is `takeQueued` — and **the mock answers a `403` nowhere**: `refused()` (`mocks/router.ts`) exists and is used three times in two handler files (`acquisition.ts` 1, `pipeline.ts` 2), none with 403. The refusal side of a right therefore has a shape already declared and no producer | `python3` over `openapi.json` counting `'403' in responses`; `git grep -c "refused(" -- frontend/maquette/design/src/mocks ':!*.test.ts'` |
| 5 | **No surface asks « may this account? ».** `git grep -n -i -E "rights\|permission\|isOperator\|isAdmin\|administrator\|canDo\|\.role\b" -- frontend/maquette/design/src/app frontend/maquette/design/src/features frontend/maquette/design/src/lib frontend/maquette/design/src/ui frontend/maquette/design/src/routes` finds three lines, all comments, and no account-rights reader; the navigation table (`app/navigation.ts`, 216 lines) has no per-row right, the bar is `NAVIGATION.filter((row) => row.inBar)` (`tab-bar.tsx`) and the drawer groups the rows that have a `group` | the lines cited |
| 6 | **Read-only exists in the maquette, in miniature, and it is the second mechanism § 17 point 3 forbids.** One flag, `SETTINGS_STATE.readOnly` (`features/settings/state.ts`), is set true by exactly one place — the named state `settings-read-only` (`harness/states/settings.ts:113`) — and read by the settings banner, the save button and the field/secret panels. **24 lines in 12 files read `readOnly`.** The served status `readConfigurationStatus` answers `{readOnly, restartRequired}` from the mock's own `readOnly` (false, `mocks/state.ts:319`), **and the two are not connected**. No other surface — the library's delete, the pipeline's levers, the maintenance runs — looks at a read-only anywhere | `git grep -c "readOnly" -- frontend/maquette/design/src ':!*.d.ts' ':!*.json'`; `git grep -n "readOnly = true" -- frontend/maquette/design/src` |
| 7 | **The backend's staging role is not « read-only » today, and § 17 says it is.** `require_not_staging` guards the four families that MOVE FILES or hold SHARED state — `/api/pipeline`, `/api/maintenance`, `/api/config`, `/api/staging` — and A18 deliberately leaves acquisition and decision writes open on staging (« worst case: a wrong follow row », so the mobile journeys can be validated there). § 17: « tout compte est ramené à la lecture seule ». **Not asked: § 17 is not ambiguous, the constitution wins and the engine follows the interface** (§ 6.2, row N) | `tests/unit/web/routes/test_staging_write_policy.py:14–24`; `personalscraper/web/deps.py:106–` |
| 8 | **The navigation table has eight rows and four are in the bar** (`acq`, `lib`, `arr`, `sys`). After L22 the bar holds `acq`, `lib`; after L16 also `trackers` (`inBar: true`, group `supervision`, no right — L16's OPEN 2 = A). The menu button is static markup (`index.html:231–234`) that L22 gives a badge; the badge sums `badge()` over the rows the bar does not hold | `git grep -n "inBar" -- frontend/maquette/design/src \| wc -l` → 12; L22 DESIGN § 3.6; L16 DESIGN § 4.1 |
| 9 | **« Les autres comptes » is a reserved empty place in Profil**: three `fr.json` keys (`screens.accountPage.others`, `othersEmptyTitle`, `othersEmptyBody`) and the page section that draws them (`features/account/page.tsx`, 83 lines) — « reserved so the form is settled ». Ruling 14 sends it out of Profil | `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(sorted(d['screens']['accountPage']))"` → 21 keys |
| 10 | **Réglages' rubrics are DATA**: six topics served by `readSettings` (`seeds/settings.json`, a list of 6); the drawer has three groups (`supervision`, `system`, `configuration`). A « Comptes » rubric is not a setting of the schema | `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/settings.json'))))"` → 6 |
| 11 | **The « quality profile » screen is a client-store write.** `/quality/$name` (`features/releases/quality-screen.tsx`, 306 lines) writes `state.profile` with `writeUiState`; **the contract contains no occurrence of « quality »** (0 matches in `openapi.json`). The per-acquisition override of `backend-demands-architecture.md` § 3 has no operation — it is DRAWN as owed here | `python3 -c "import re;print(len(re.findall('quality',open('frontend/maquette/contract/openapi.json').read(),re.I)))"` → 0 |
| 12 | **No `requester` exists** in the contract or the design (`git grep -ci requester -- frontend/maquette/contract frontend/maquette/design/src` → no match). L22 phases 1 and 7 add it and draw the line; the answers name a requester per card and per follow from then on | L22 DESIGN § 2.1 |
| 13 | **The mock's dials are the fit for an identity.** `MockDials` (`mocks/state.ts:346–356`) holds nine dials, each « what the machine IS » — a lock stale, a sweep unfinished — never how an operation ANSWERS (that is the scenario). Who is signed in is what the machine IS | `sed -n 336,372p frontend/maquette/design/src/mocks/state.ts` |
| 14 | **The design host serves the gate itself, and has no Plex.** `serve.py`'s `login_page` clones the extracted markup and posts it to its own `/login`, checked against a scrypt hash. A Plex button drawn inside the extracted markers would appear on the real password page and could do nothing — an offer the surface cannot honour (§ 17 point 1) | `sed -n 349,395p frontend/maquette/serve.py` |

Two of these are corrections the contract needs (facts 1, 2) and one a discrepancy between the constitution and the
engine (fact 7). All three are recorded in § 8, not amended here.

---

## 1. What L18 builds on, and does not redraw

### 1.1 What exists and stays

- **The header avatar and its menu** (`features/account/panel-account.ts`): the menu already carries the account's
  name, e-mail and avatar and two acts (« Profil et préférences », « Se déconnecter »). L18 adds the ROLE to its
  subtitle line and nothing else; its two acts are for every account.
- **Sign-out and the session facts** on Profil (duration, transport, where) — unchanged.
- **The requester line of L22** (« ajouté par Izno, dans qBittorrent », drawn from the answer): L18 makes the
  answer differ by account and gives the Operator the gesture to change it (S5). The line's drawing is L22's.
- **The equal-shares bar** (L22's R-L22-s, a frame rule: the bar draws only the buttons present, 1/n, n from 2 to 4):
  L18 makes the count VARY by account and reads that rule at each count it produces.
- **The Trackers row** (L16) and its badge; **the cross-seed block** (L17, if drawn there): L18 gates them.
- **The confirmation dialogs** of B-300 and B-335 (« … pour tous les comptes du foyer »): the sentences stay
  true, because only the Operator writes configuration (§ 3.7). They are not touched.

### 1.2 The model — one derivation, the rest reads it

The lot's first act is a MODEL (the architecture's « A rights MODEL first, then surfaces »): **one function from what
the server answered to what this account may do**, in `features/account/`, read by every surface through one door.
Its inputs are the account's role, its two options, and the instance's ceiling (S7); its output is a closed set of
named RIGHTS. No surface compares a role string; the guard of § 5 (R-L18-b) reads the source for exactly that.

**The rights, drawn from § 17 — the names adjust at the phase; the set is what matters.**

| Right | Operator | Household member | Plex guest | Rights-less Plex user | What hangs on it — OFFER side | The call — REFUSAL side (operations of the contract) |
| --- | :---: | :---: | :---: | :---: | --- | --- |
| `library.read` | yes | yes | yes | yes | the Médiathèque, the media sheet, the follows' read | the reads themselves |
| `library.write` | yes | — | — | — | the selection and delete flow (`features/library/delete-dialog.ts`); « Re-scraper » on the sheet | `deleteLibraryItems`, `rescrapeMedia` |
| `acquisition.request` | yes | yes | yes | — | the Acquisition section; « Découvrir »; the add flow | `createFollow` (and the punctual request — OPEN 6) |
| `acquisition.follow` | yes | yes | OPEN 6 | — | « Suivis »; « Suivre » | `createFollow`, `updateFollow`, `deleteFollow`, `restoreFollow` — on one's own |
| `acquisition.pilot.own` | yes | yes | yes | — | the tunnel's acts on a card one requested: « Relancer », « Re-scraper », « Récupérer », the grab and search acts | `requeueJourney`, `rescrapeJourney`, `takeQueued`, `grabForFollow`, `searchForFollow`, `grabSeasonForFollow` — where the target's requester is the caller |
| `acquisition.pilot.any` | yes | — | — | — | the same acts on ANY card | the same operations, any target |
| `acquisition.see.others` | yes | option | option | — | the cards and follows one did not request, read-only | `readAcquisitionQueue`, `readFollows` answer the caller's subset unless it holds the right |
| `acquisition.quality.own` | yes | yes | option | — | « Profil de qualité » on one's own acquisition | the new override operation (§ 2.1, demand K), on one's own |
| `acquisition.reassign` | yes | — | — | — | the reassign gesture (S5) | the new reassignment operation (demand I) |
| `pipeline.control` | yes | — | — | — | Système's levers, « Lancer maintenant » on the Veille, the maintenance runs, the resolution of an arrival's identity | `runPipeline`, `pausePipeline`, `resumePipeline`, `killPipeline`, `setWatcher`, `runDetection`, `runMaintenanceAction`, `continueStagedMedia`, `discardStagedMedia`, and the decisions' `resolveDecision`, `dismissDecision`, `searchForDecision` |
| `configuration.write` | yes | — | — | — | the config editor, the secrets, the restart | `updateConfigurationFile`, `updateSecrets`, `restartWeb` |
| `accounts.manage` | yes | — | — | — | S9 | the account operations (§ 2.1) |
| `trackers.view` / `system.view` | yes | **OPEN 4** | **OPEN 4** | — | the Trackers row; Système, Maintenance, Réglages in the drawer | the reads under `/api/system`, `/api/maintenance` — and the tracker reads L16 declares |

Two rows of the table are the design's reading, not the constitution's, and it says so: **`pipeline.control` covers the
decisions and the staging writes** because those move real files and the Member/guest rows of § 17 name no such
power; and **`acquisition.pilot.own` covers every act on the tunnel** because § 17 says « piloter le tunnel des
acquisitions dont il est le demandeur » without listing acts. A phase that finds an act the table misclassifies
reports it (STOP D); it does not reclassify.

**The ceiling** subtracts EVERY write right for every account on an instance that carries it (S7) — § 17: « quel que soit son
rôle » — the session acts aside. **Signing in and out are session acts, never rights** — `signIn`, `signOut` and the new
`signInWithPlex` are open to everyone by construction, as `test_session_routes_are_never_guarded_on_staging` says of
their backend twins.

---

## 2. The contract (D7) — and it comes FIRST

D7: the maquette declares the contract its interface REQUIRES, and every divergence from the backend's is a demand. **A
demand is filed by EDITING THE CONTRACT** (`frontend/maquette/contract/openapi.json`) and regenerating
`docs/reference/frontend-backend-demands.md` (`python3 scripts/compare-contracts.py --write`, then `--check`); the
register is « COMPUTED, NEVER WRITTEN ». **It invents no shape the constitution and the demands do not name**: what
the design needs and the register lacks is PROPOSED in § 6.2 in the register's own form, and the lot files it by
editing the contract in the phase that draws its surface (L22's precedent: a demand is filed where its surface is
drawn).

### 2.1 What the surfaces read, and what already exists

| Surface | Reads / acts through | Declared today |
| --- | --- | --- |
| every surface — the rights | `GET /api/auth/me` (`readAccount`) | **re-shaped** — L22's demand D asked for the row; **the shape is drawn here** (§ 6.2 D): the role, the two options, whether a Plex account is linked, and the instance's ceiling |
| the gate — Plex sign-in | — | **no operation** — demand J (`signInWithPlex`) |
| S4 — the requester, the lists | `readAcquisitionQueue`, `readFollows`, `readJourney` | the requester is L22's demand A; the FILTER by account is the backend's, drawn here as the answers differing by identity |
| S5 — the reassign gesture | — | **no operation** — demand I |
| S4 — quality per acquisition | — | **no operation** (fact 11) — demand K; `backend-demands-architecture.md` § 3 |
| S7 — the ceiling | `readConfigurationStatus` (`{readOnly, restartRequired}`) | yes — **its `readOnly` has a reader nobody connected** (fact 6); **the ceiling is carried by `readAccount`** (demand D): one read carries the rights and the ceiling, because a model composing two reads would be a second authorisation path (NE-DOIT-PAS-7) |
| S9 — the roster, rights, creation | — | **no operation** — demands F, G, H |
| the refusal side, everywhere | `Problem` responses | **62 of 63 declare 403**; `takeQueued` gains it in phase 1 (an edit of an operation, not a demand) |

### 2.2 The mock: identities, dials, one guard

**The identities.** `seeds/accounts.json` (new; `seeds/account.json` stays and is the Operator's row) holds six
accounts. The Operator is the real one; **the five others are INVENTED** and every row is marked `x-unseeded` in the
fixture register (`frontend/maquette/fixture-register.json`), the contract's own word for « nothing was invented
here » and « nobody looked » being different things:

| Id (a label, not a person) | Role | Option: see the others' | Option: quality of one's own | Plex | Proves |
| --- | --- | :---: | :---: | --- | --- |
| `izno` (real, `account.json`) | Operator | implicit | implicit | linked, the server's owner | the resting maquette; every right present |
| `household-member` | Household member | no | yes (always) | linked | the Member's offer and refusal sides; the default of « see the others' » |
| `household-member-sees-all` | Household member | **yes** | yes | linked | the option, ON |
| `guest` | Plex guest | no | **no** | linked | the guest's offer and refusal sides; the option, OFF |
| `guest-with-quality` | Plex guest | no | **yes** | linked | the second option, ON |
| `plex-without-rights` | none (admitted read-only) | — | — | linked, no rights | the Acquisition section absent; a bar of one place (OPEN 7) |

Names are neutral labels, with a reserved e-mail domain (`example.invalid`, RFC 2606), so nobody reads an invented row
as a person. **The two pairs of an option are the point**: an option proved on one value proves nothing.

**The dials** (`MockDials`, fact 13): `setIdentity(id)`, `setCeiling(on)`, `setPlexReachable(on)`,
`setInventedRequests(on)`. The last is what keeps the resting maquette whole: **the invented cards and follows —
requested by the invented accounts, so that « see the others' » has something to see — exist only while the dial is
on**, and only the named states that need them turn it on. With the dial off and the identity at `izno`, no seed row
this lot adds is readable, and the oracle diverges on no state that existed before (§ 4.1). The Operator's real rows keep the
requester L22 gives them (Izno); **no real row is ever re-attributed to an invented account** (§ 13).

**The mocks MOVE** (D7: « a mock that answers without moving certifies nothing »): a reassignment changes whose list
the card is on and the requester line it draws; a rights change moves the affected account's next `readAccount`; an
override changes the card's chosen profile; a created account appears in the roster; a Plex sign-in answers the
identity the dial holds.

**The refusal — ONE guard, not thirty.** `route()` (`mocks/handlers/shared.ts`) gains a declared RIGHT; a single check in
the mock layer compares it with the dialled identity's rights (the model of § 1.2, imported) and the ceiling, and
answers `refused(403, …)` with the contract's `Problem` body, recorded by `answered()` like any answer. This is
NE-DOIT-PAS-7 kept in the mock as in the engine: **one authorisation path**, and 29 handler sites that only NAME
their right. The route table of the mock has 63 `route(` calls (`git grep -c 'route(' -- frontend/maquette/design/src/mocks/handlers`
sums 64 with the definition); the 29 writes are the sites edited (phase 4).

### 2.3 The stream

`docs/reference/frontend-backend-demands-stream.md` names no account event. **One is PROPOSED there by hand** (§ 6.2,
demand M): an account's rights changed (a role, an option, a Plex link). Without it a demoted account keeps a bar
and a drawer it no longer has until it re-reads, and NE-DOIT-PAS-8 allows no poll. The mock's relay carries it and
`features/account/live.ts` — today an EMPTY table, `accountLiveRules: readonly LiveRule[] = []` — claims it. The stream
carries no rights themselves: the account re-reads `readAccount`, and the model re-derives.

---

## 3. The surfaces, drawn

### 3.0 The two sides, and where hiding would mislead

Every right of § 1.2 is drawn on **two sides**, and each surface below names both.

- **The OFFER side (§ 17 point 1).** For the account without the right the act is ABSENT from the surface — not
  disabled, not greyed, not present-and-refused. Absent means absent from the DOM (the form the L17 design already
  uses for its block).
- **The REFUSAL side.** The call, forced by hand, answers `403` with the contract's body, and the answer is recorded.

**Where hiding would mislead, and so where § 17 point 2 requires an explanation.** Measured against the surfaces:

| Where | Would hiding mislead? | Drawn as |
| --- | --- | --- |
| a card of another account (option « see the others' » ON) with its acts absent | yes — the acts exist for the requester | the requester line (« demandé par … ») and one line saying the card is read-only for this account (S4) |
| the instance ceiling — every write absent | **yes, most of all**: an Operator who finds no lever would think the application broken | one statement, said where a write would have been, and on Profil (S7) |
| Trackers, Système, Maintenance, Réglages for an account that lacks them | § 17 « Ce qu'un compte voit par défaut » says the pipeline and the configuration « restent visibles et expliqués comme réservés »; § 17 point 4 says a page absent from the BAR is point 1 | **OPEN 3** |
| the Acquisition section for the rights-less account | **no** — the named exception: nothing concerns that account | absent (S4) |
| the library's write acts for the Member and the guest | no — the library is complete; nothing is missing from it | absent (S6) |
| the other accounts, from Profil | no — Profil is the connected account | absent (S8) |

### 3.1 S1 — The gate: Plex is added beside the password

**What exists.** The gate is a layer, not a page (`app/entry.ts`), whose markup is static in `index.html` (fact 1). It
carries a title, a subtitle, two fields and one button, and a refusal line. Its two named states are `signin` and
`signin-error` (`harness/states/entry.ts`).

**What is drawn.** A second way in, « Se connecter avec Plex », that ADDS to the password form and replaces
nothing (§ 17). **How the two are arranged is OPEN 2.** Whatever the arrangement:

1. **The Plex block has its own marker pair** (`login:plex:start … end`) in `index.html`, outside the extraction the
   design host performs (fact 14): the host's password page is unchanged and carries no offer it cannot honour, and
   R72's bridge (`serve.py` and the harness reading the same inputs) still holds. The gate's style gains its rules in
   the `login:entry` region of `styles/base.css` — a frame edit, said as one.
2. **A password is for the Operator.** A password sign-in by a non-Operator account is refused with a reason
   (« ce compte se connecte avec Plex »), never a bare « Identifiants invalides » that would send the account to try
   again (§ 8).
3. **When Plex is unreachable**, the gate says so — one line, from the answer, not a constant — and the password form
   stays whole: it is the door of last resort, and « Seuls les comptes Opérateur peuvent avoir un mot de passe sans
   SSO » is why it exists.
4. **A Plex user with no right here is admitted**, read-only, and lands on the Médiathèque (S2). The gate does not
   know what is behind it (`docs/reference/frame-model.md` § « Part 9 »: « rights are a feature's to read from
   `/api/auth/me`, never the gate's »): the OUTCOME is drawn by the frame reading the account after the sign-in, not
   by the gate reading a role.

**Named states.** `signin-plex` (the gate with both ways in); `signin-plex-unreachable`; `signin-password-refused`
(a non-Operator's password, with its reason); `signin-plex-bare` (a rights-less Plex user's outcome, the first frame after the
gate). The two existing states keep their ids and gain the Plex block.

### 3.2 S2 — The bar, composed by rights

**The bar is the table's** (L22 § 3.6): `app/navigation.ts` declares the pages, `tab-bar.tsx` draws the rows with
`inBar`. L18 adds ONE thing to the table — **the right that opens a row** — and one filter to the bar: a row is drawn
when it is `inBar` AND the model says the account may open it. The table's header comment, which L22 rewrites to say the
frame rule, says this too. **This is a frame edit after L15's** (the gate, S1, is another), and the plan says so
(`plan/INDEX.md`).

| Row | Right that opens it | Operator | Household member | Plex guest | Rights-less |
| --- | --- | :---: | :---: | :---: | :---: |
| `acq` Acquisition | `acquisition.request` or `acquisition.see.others` | yes | yes | yes | **no** |
| `lib` Médiathèque | `library.read` | yes | yes | yes | yes |
| `trackers` (L16) | `trackers.view` — OPEN 4 | yes | OPEN 4 | OPEN 4 | no |

So the bar has **three places** for the Operator, **two** for a Member or guest under the reading of OPEN 4 that gives
them no Trackers, and **one** for the rights-less account. **A bar of one place contradicts the operator's own rule** —
« 4 boutons c'est le max, 2 boutons le min » (L22's OPEN 2, ruled A) — and the two dictations, § 17's « médiathèque
uniquement » and that one, do not agree. **OPEN 7.**

**The menu button's badge** (L22's ruling 15 reading: the sum of `badge()` over the rows the bar does not hold) is
filtered the same way: a row the account cannot open contributes nothing, so a seeded Système fault gives the Operator
a badge and a Member none (R-L18-e). Ruling 12 says this needs « no rule more »; the rule of § 5 is what holds that
sentence.

**Named states.** `bar-household`, `bar-guest`, `bar-rightless` — the bar for each identity; `bar-operator` is the
existing bar (L16's `bar-trackers-alert`).

### 3.3 S3 — The drawer, and the places an account does not hold

The drawer groups the rows that have a `group` (`app/drawer.tsx`, 199 lines): `supervision`, `system`,
`configuration`. L18 filters its entries by the same model. **What an account that lacks a place sees in its
stead is OPEN 3**, and it covers three surfaces at once, because they are one question: the drawer entry, a cold
address (`/system`, `/maintenance`, `/settings`, `/trackers`, `/accounts`), and the place itself.

The drawer itself is the frame's, and this lot edits it as it edits the bar: its entries by right, and its `Comptes`
entry if OPEN 1 goes that way (S9). Its « Apparence » group and the host's served identity are for everyone.

### 3.4 S4 — Acquisition by rights and by requester

Acquisition's four tabs are L22's (« Suivis · En cours · À traiter · Découvrir »). L18 composes what the account
sees of them.

1. **The lists are the account's.** By default an account sees only the cards and follows it requested; with the
   option « see the others' » it sees the rest too, **read-only**. The filter is the BACKEND's (the answers differ by
   caller, § 2.1); the maquette's mock answers the dialled identity's subset. **Every count reads the same subset**: the
   tab counts, the bar's badge (the « À traiter » count, L22) and the list — one derivation (§ 13; R-L18-g).
2. **The tabs are composed by rights.** « Suivis » needs `acquisition.follow` (for the guest, OPEN 6); « En cours »,
   « À traiter » and « Découvrir » need `acquisition.request`. **L22's default-tab rule** (« Suivis » first, then the
   last tab opened, kept in local storage under try/catch) meets an account that has no « Suivis » — and, worse, a
   remembered tab from ANOTHER account on the same device: **the default falls to the first tab the account has, and a
   remembered tab it no longer holds is ignored** (R-L18-x). Per-viewer memory in the browser is not per-account
   unless the design says so.
3. **The requester line names the account** (L22 draws it from the answer): « ajouté par Izno, dans qBittorrent » for
   the Plex owner's direct add, the requester's name otherwise. On another account's card it is followed by one line —
   the card is read-only for this account — which is § 17 point 2 applied to a card: hiding the acts would mislead,
   the acts exist for the requester.
4. **Own tunnel** (§ 17): the acts of `acquisition.pilot.own` are offered on a card the account requested and ABSENT on
   the others'; the Operator holds `acquisition.pilot.any`. The refusal side: the same operations, forced on another's
   card, answer `403` (R-L18-k).
5. **The quality profile of an acquisition** is offered where `acquisition.quality.own` holds, on one's own
   acquisition only, and it says what it does: **a choice for THIS acquisition**, never the edit of the profile (fact
   11; `backend-demands-architecture.md` § 3). The screen's write becomes a served one (demand K) — until now it
   was the interface's own state, which is not a right that can be refused.
6. **« Suivre » and the request** — what the guest's « demande d'acquisition » IS in the maquette's vocabulary is
   **OPEN 6**.
7. **The section absent** (§ 17: the named exception): an account that holds neither `acquisition.request` nor
   `acquisition.see.others` has no Acquisition row, no tabs, no badge — and no explanation, because nothing concerns it
   (§ 3.0). Its landing is the Médiathèque; a cold `/acquisition` for it is OPEN 3's address question.

**Named states.** `acq-household` (the Member's Acquisition, own cards only); `acq-household-sees-all` (the same with the
option: others' cards read-only, their line); `acq-guest` (no « Suivis », under the reading of OPEN 6 that gives the
guest none); `acq-operator-all` (the Operator sees every requester's cards); `acq-card-read-only` (one card of another
account, acts absent, the line saying why); `quality-own-offered` / `quality-own-absent`.

### 3.5 S5 — The reassign gesture (born here)

**Ruled elsewhere:** organisation ruling 9 (a card born of a direct add in qBittorrent carries the Plex owner as
requester, « réaffectable depuis la carte »); L22's OPEN 11 = B (L22 draws the line, the gesture is L18's). **It is the
Operator's** (§ 17: « peut réaffecter une demande à un autre utilisateur »).

**What it does.** From a card, the Operator picks another account; the card's requester becomes that account
(demand I), the line reads it, and the card moves to that account's list. Nothing else changes: the tunnel is
unaffected — a tunnel belongs to the medium (§ 20), the requester is a property of the medium's acquisition.

**What it draws.** A chooser panel (a descriptor through `ui/panel`, the way the account menu and the journey sheet are
drawn) listing the accounts by name, role and Plex link, the current requester marked, and a confirmation in the
panel's own idiom: the sentence names the medium and the two accounts (« … passera de Izno à … »). **Where the gesture
starts from is OPEN 5.** Absent for every account but the Operator, on its own cards too (§ 17: the Member pilots, does not
reassign).

**Named states.** `acq-reassign-chooser`; `acq-reassign-done` (the card on its new account's list, its line updated).

### 3.6 S6 — The Médiathèque and the sheet are read-only, but for the Operator

`library.write` is the Operator's. For the Member, the guest and the rights-less account the library draws no selection
and no delete (`features/library/delete-dialog.ts`, 193 lines; the selection bar replaces the tab bar today on `lib`,
`slotReplacesTabBar`), and the sheet draws no « Re-scraper » (`features/media/media-verbs.ts`, 141 lines). Nothing is
missing from a library the account can read whole, so nothing is explained (§ 3.0).

**The sheet's administrator block (L17).** L17's S5 draws a per-tracker cross-seed block « for the administrator only »
and asks (its OPEN 1, **unruled on this head**) whether it is gated at L17 behind a second mock identity (reading A) or
held for L18 (reading B). L18 does not choose. **Phase 27's SIZE is conditional, not its existence**: under A, L17 has already drawn the block
behind an `admin` fact and a second identity, and phase 27 re-aims that gate onto the model and deletes L17's stand-in
(9 points); under B, phase 27 draws the block itself and its gate here, on the model (22 points, cut into 27 and 27-bis). Either way the rule is L17's R-L17-f
proved on the six identities of § 2.2.

### 3.7 S7 — The ceiling absorbs the staging role

`PERSONALSCRAPER_WEB_ROLE=staging` stops being a role (§ 17). What the maquette draws:

1. **The flag dies.** `SETTINGS_STATE.readOnly` and the mock's `readOnly` are replaced by the model's ceiling: the
   24 lines in 12 files of fact 6 read the model, and `settings-read-only` becomes a state that turns the ceiling
   dial (`setCeiling(true)`) — not a state that sets a page's own flag.
2. **Every write is absent on a ceilinged instance, for every role** — the Operator included — because the ceiling
   subtracts before the role adds (§ 1.2). It subtracts every write, and the mock's guard reads that (§ 2.2); the engine's policy is § 6.2's row N.
3. **It says why**, once, where a write would have been — the settings banner exists (« Lecture seule. ») and stays —
   and on Profil, in the list of what the account can do (S8). This is § 17 point 2 at its strongest: the Operator on
   the staging instance must not conclude the application is broken.
4. **The refusal side is the mock's guard** (§ 2.2): with the ceiling on, every write it names answers `403`.

**Named states.** `ceiling-operator` (the Operator's Système, Réglages and library on a ceilinged instance);
`settings-read-only` (existing id, re-driven).

### 3.8 S8 — Profil is the connected account, and says what it can do

Profil keeps its identity and session sections. **« Les autres comptes » leaves** (ruling 14): the section, its three
keys and its empty note go. It gains, from the model and nowhere else (§ 13: one derivation, R-L18-p): the ROLE in a
line; a section **« Ce que ce compte peut faire »** listing the rights the account holds, and — the explanation § 17
point 2 wants — the reason behind each right it does NOT hold that would otherwise surprise (« l'instance est en lecture
seule », « ce droit se règle par l'Opérateur ») ; the Plex link's state (linked to which Plex account, or not). It offers
no act on other accounts.

**Named states.** `profile-operator` (the existing `profile`, gaining its lines); `profile-household`; `profile-guest`;
`profile-ceiling`.

### 3.9 S9 — « Comptes »: the Operator manages accounts

**What is drawn, whatever its place.** A surface reserved to `accounts.manage`:

1. **The roster.** One row per account: its name, its role, whether it is linked to a Plex account, and its two
   options as they stand. A Plex user admitted with no right is a row too — « sans droits », so the Operator sees who
   is in and has not been qualified (an account admitted read-only is not a hidden one, § 8).
2. **An account's rights.** Its role (a choice of the three), and the two options, each with what it does in a sentence.
   A change is answered on the network (demand H), moves the roster, and reaches the affected account through the
   stream event (demand M). **The Operator cannot demote the last Operator** — the surface says why and the operation
   refuses it (the door of last resort, § 3.1, must remain).
3. **A new account.** A name, an e-mail — **mandatory** (« Un compte créé hors Plex porte un e-mail obligatoire ») —
   and a role. If the e-mail is a Plex account's, the two are **linked** and the roster says so; if not, and the role is
   not Operator, the account cannot sign in with a password and the surface says it will sign in with Plex when its
   e-mail matches one (demand G).
4. **The Plex link**, as a line on each row and in the detail: linked to which Plex identity, or not linked and why.

**Where it lives is OPEN 1** — both placements are drawn in the plan (phase 23 carries one per reading) and this
document says what each costs. Neither is in Profil (ruling 14, refused B).

**Named states.** `accounts-roster`; `accounts-detail`; `accounts-create`; `accounts-create-refused` (empty e-mail);
`accounts-last-operator`; `accounts-forbidden` (the address, for an account without the right — its form is OPEN 3's).

---

## 4. The named states

**Measured before naming them** (the counting command of L22's DESIGN § 4, unchanged, run on this head):

    python3 -c "import re,glob;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open(f).read(), re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"

L22 (own count on `94a369879`: 114) adds 23 and removes 8; L16 and L17 add their own. **This lot adds up to 31 states** (29 without the two conditional ones, ids 5 and 31),
in a NEW file `harness/states/rights.ts` (the way L22 opened `tunnel.ts`), composed by `harness/index.ts` beside the others, so no
existing state file crosses invariant 6's 400 lines. Every new state is reachable by `window.__go("<id>")`, has an
English id, and its French label is what the panel says. **Each state that needs an identity turns the dial itself**
(`setIdentity`), so the driver's reset returns to the Operator between states.

| # | id | Label (French) | Lands in phase |
| --- | --- | --- | ---: |
| 1 | `bar-household` | « Barre — membre du foyer » | 5 |
| 2 | `bar-guest` | « Barre — invité Plex » | 5 |
| 3 | `bar-rightless` | « Barre — Plex sans droits » | 9 |
| 4 | `drawer-household` | « Tiroir — membre du foyer » | 6 |
| 5 | `place-reserved` | « Une place réservée s'explique » — **only if OPEN 3 is ruled B** | 7 |
| 6 | `acq-household` | « Acquisition — membre du foyer » | 8 |
| 7 | `acq-household-sees-all` | « Acquisition — membre du foyer qui voit tout » | 8 |
| 8 | `acq-guest` | « Acquisition — invité Plex » | 9 |
| 9 | `acq-operator-all` | « Acquisition — l'Opérateur voit tout » | 8 |
| 10 | `acq-card-read-only` | « Carte d'un autre — lecture seule, et pourquoi » | 13 |
| 11 | `acq-reassign-chooser` | « Réaffecter — le choix du compte » | 11 |
| 12 | `acq-reassign-done` | « Réaffecter — la carte a changé de main » | 12 |
| 13 | `quality-own-offered` | « Profil de qualité — offert sur la sienne » | 14 |
| 14 | `quality-own-absent` | « Profil de qualité — absent sur celle d'un autre » | 14 |
| 15 | `lib-read-only` | « Médiathèque — lecture seule » | 16 |
| 16 | `sheet-read-only` | « Fiche — lecture seule » | 16 |
| 17 | `ceiling-operator` | « Instance en lecture seule — l'Opérateur » | 17 |
| 18 | `profile-household` | « Profil — membre du foyer » | 18 |
| 19 | `profile-guest` | « Profil — invité Plex » | 18 |
| 20 | `profile-ceiling` | « Profil — instance en lecture seule » | 19 |
| 21 | `signin-plex` | « Connexion — mot de passe et Plex » | 20 |
| 22 | `signin-plex-unreachable` | « Connexion — Plex injoignable » | 21 |
| 23 | `signin-password-refused` | « Connexion — mot de passe refusé à un non-opérateur » | 21 |
| 24 | `signin-plex-bare` | « Après la connexion — Plex sans droits » | 21 |
| 25 | `accounts-roster` | « Comptes — la liste » | 24 |
| 26 | `accounts-detail` | « Comptes — les droits d'un compte » | 25 |
| 27 | `accounts-last-operator` | « Comptes — le dernier Opérateur » | 25 |
| 28 | `accounts-create` | « Comptes — un nouveau compte » | 26 |
| 29 | `accounts-create-refused` | « Comptes — e-mail obligatoire » | 26 |
| 30 | `accounts-forbidden` | « Comptes — adresse fermée à ce compte » | 23 |
| 31 | `media-cross-seed-hidden` | L17's state, driven on the six identities — **only if L17 leaves it to L18** | 27 |

Four ids of § 3 are not in the table on purpose: `bar-operator` is the existing bar, `profile-operator` is `profile`
grown, `settings-read-only` is re-driven, and `signin` / `signin-error` gain the Plex block (phase 20) with the ids they
have.

### 4.1 What the oracle will do (D8)

The new states are NEW, so the reference RECORDS them and proves nothing about them. What the oracle is for here is
the other direction — **no existing state may diverge unless a phase names it**. The resting maquette is the Operator's
(§ 2.2), so **for every state that existed, the Operator's surface is what it was**, and the oracle's job is to prove it:

| Phase | Existing states that WILL diverge | Reason (accepted by name, D8) |
| --- | --- | --- |
| 1–4 | **none** — a contract, a seed that is unreadable at rest, a model no surface reads yet, a guard that lets the Operator through | the whole point of the dial (§ 2.2) |
| 5 | none by the oracle — **the oracle is silent over the bar by construction** (D8 reads the `<nav>`'s rectangle, never a button; L22 § 4.1 said it first). The Operator's bar is unchanged | R-L18-d reads the buttons, or nobody does |
| 6 | none for the Operator | the same, for the drawer |
| 8 | `acq-*` states only if a tab or a count changes for the Operator — it must not | STOP A otherwise |
| 11, 12 | the states that draw a card of L22's, **only if the reassign entry point (OPEN 5) adds a mark to the Operator's card** | « L18 § 3.5: the requester line as a control » — reading B of OPEN 5 only |
| 17 | `settings-read-only` and the settings states that draw the banner (the flag was a module state; the ceiling is served) | « L18 § 3.7: the flag dies » |
| 18, 19 | `profile` (loses the others' place, gains its lines) | « L18 § 3.8 » |
| 20 | `signin`, `signin-error` on `login/form` | « L18 § 3.1: the Plex block » |
| 21–26 | none for the existing states; the placement's own reading (OPEN 1) adds a drawer entry or a rubric to `drawer-navigation` / the settings states — named in phase 23 | « L18 § 3.9 » |
| all others | none | STOP A |

**The oracle's silence over what an account cannot see proves nothing, and this design says so before any phase
does.** The oracle draws the Operator's application; a right absent for the Member is invisible to it by construction.
**This lot is held by § 5's rules or by nobody** — L11 is the measured case: no divergence over 2 958 measurements
while four adversarial rounds found ~40, 13, 7 and 0 defects (L20 § 7). The accessibility tier is re-read at phases 5,
6, 20 and 23.

---

## 5. The rules that bite

Numbers: the harness's highest rule number is re-taken by phase 2 against `origin/main` at the moment it runs —
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` (**R223** on this head) — and every label
below is bound to a consecutive free number then, the mapping written into the report. **A number taken from this
document without re-measuring is a collision.** Each is written RED FIRST; where the surface does not exist on `main`
the rule is red for that reason and needs no mutation; where it changes behaviour that exists, the mutation comes
after the move. **Every rule proving a right names its TWO halves** — the absent side (read on the DOM, for the
identity that lacks the right) and the refused side (the call forced by hand, answered `403` on the network, read
through `window.__mocks.answered()`) — and a rule that has only one is refused by the review.

| Rule | Phase | What it READS | The mutation that fells it |
| --- | ---: | --- | --- |
| **R-L18-a** — the account, from the answer; the resting maquette whole | 2 | the avatar menu, Profil and the requester line name the DIALLED identity; **at rest (dial off, identity `izno`) no invented row is readable from any list and every existing state is unmoved** | print a constant name → falls; leave an invented card in the resting seed → the rest hold falls |
| **R-L18-b** — one derivation, no second path | 3, 17 | a unit table: every combination of role × the two options × the ceiling gives the rights § 1.2 says; **and a source hold: no file outside the model compares a role string**; phase 17 adds the hold that none reads `readOnly` (`SETTINGS_STATE.readOnly` and the mock's are gone by then) | compare `role === "operator"` in a surface → the source hold falls; flip one cell of the table → the unit falls |
| **R-L18-c** — the refusal side, everywhere | 4 | for each of the 29 writes and each identity lacking its right: forced by `fetch`, the mock answers `403` with the contract's `Problem` body and `answered()` records `403`; for the Operator, the same call answers as it did; **under the ceiling, every write the ceiling subtracts is refused for the Operator too** | drop the right from one route's declaration → the sweep names that operation; make the guard let an option through unread → falls |
| **R-L18-d** — the bar by rights, both sides | 5, 9 | on each identity's bar state: the buttons drawn are exactly those the model opens, each of width 1/n (L22's R-L22-s read at 1, 2 and 3), each ≥ 44 px, **and the absent pages are ABSENT from the DOM, not hidden**; the refusal half: the pages' reads refused (R-L18-c). **Discharges L16's OPEN 2** — the Trackers row is proved hidden for the accounts without it | draw a row without its right → the absent hold falls; hard-code the Operator's bar → falls on each other identity |
| **R-L18-e** — one derivation for the badges | 5, 6 | the menu button's badge equals the sum over the rows the account can open, and the drawer draws exactly the entries the model opens; a seeded Système fault moves the Operator's badge and leaves the Member's absent; **the Member's Acquisition badge counts their own « À traiter » cards only** | sum over every row → falls for the Member |
| **R-L18-f** — a place not held explains itself (OPEN 3 = B only) | 7 | on `place-reserved`: the drawer entry and the cold address say the place exists, that this account does not hold it, and who can open it | render the page instead → falls |
| **R-L18-g** — the lists are the account's, and every count agrees | 8 | for each of `household-member`, `household-member-sees-all`, `guest`, `izno`: the cards and follows drawn are exactly the identity's subset, the tab counts and the bar badge equal the list; **the option proved on both values** | read the unfiltered answer → falls; count the unfiltered set in the badge → the count hold falls |
| **R-L18-h** — the section absent | 9 | `plex-without-rights`: no Acquisition row, tab, badge or address; the landing is the Médiathèque; a bar of the count OPEN 7 says | leave the row → falls |
| **R-L18-i** — the reassign offer | 11 | on the Operator's card: the gesture is offered, the chooser lists the accounts with the current requester marked; on every other identity, **on its own card too**, no trace of it in the DOM | offer it on the Member's own card → falls |
| **R-L18-j** — the reassignment moves | 12 | a reassignment is ANSWERED on the network (demand I), the card is on the new account's list and off the old one's, its line reads the new name; **forced by the Member, the call answers `403`** | toast without calling → the network hold falls; do not move the card → falls |
| **R-L18-k** — own tunnel, both sides | 13 | on the Member's own card the acts of `acquisition.pilot.own` are offered and answer; on another's card (option ON) they are absent, the line says the card is read-only, and the same operations forced answer `403`; the Operator holds them on both | offer an act on another's card → falls |
| **R-L18-l** — the quality choice of an acquisition | 14 | offered on one's own acquisition for the Member, and for the guest exactly when the option is ON (both pairs of § 2.2); absent on another's; the write is ANSWERED (demand K) and changes only THAT acquisition's choice; no act edits the profile itself | give the guest the offer without the option → falls; write the choice into the profile → falls |
| **R-L18-m** — « Suivre » and the request (OPEN 6) | 15 | per the ruled reading: the offer per role; the guest's act as ruled | offer « Suivre » to the guest under reading B → falls |
| **R-L18-n** — the library, read-only | 16 | for the Member, the guest, the rights-less: no selection, no delete on the library; no « Re-scraper » on the sheet; forced `deleteLibraryItems` / `rescrapeMedia` answer `403`; for the Operator both exist | leave the selection bar → falls |
| **R-L18-o** — the ceiling absorbs the role | 17 | with the ceiling on, on Système, Réglages, Maintenance, the library and every Acquisition act: no write offered, **for the Operator**; the statement of why is drawn; **`SETTINGS_STATE.readOnly` and the mock's `readOnly` do not exist** (source hold); every write refused (R-L18-c) | re-add a settings-only flag → the source hold falls; leave one lever offered → falls naming it |
| **R-L18-p** — Profil is the connected account | 18 | Profil draws no other account and no reserved place for them; it names the role of the connected account, for each identity | draw « Les autres comptes » → falls; print a constant role → falls under a changed identity |
| **R-L18-q** — the gate offers Plex, and the host's page is unchanged | 20 | the gate draws both ways in (arranged per OPEN 2); **the design host's password page is byte-identical to the one before the phase and carries no Plex offer** (R72's bridge still passes) | move the Plex block inside the extraction markers → the host hold falls |
| **R-L18-r** — the gate's outcomes | 21 | a non-Operator's password is refused with its reason; Plex unreachable is said from the answer; a rights-less Plex user's first frame is the Médiathèque; the Operator's password still signs in when Plex is unreachable | let a non-Operator's password through → falls; drop the door of last resort → falls |
| **R-L18-s** — Comptes, both sides | 23 | for the Operator: the entry and the surface exist; for every other identity: **the entry is absent from the DOM** and the address is refused as OPEN 3 says; forced `readAccounts` / `createAccount` / `updateAccount` answer `403` | leave the entry for the Member → falls |
| **R-L18-t** — the roster, from the answer | 24 | one row per account of the answer; role, link and options read from it; change the seed, the row follows | print a constant → falls |
| **R-L18-u** — a rights change moves | 25 | a change is ANSWERED on the network; the roster moves; the affected identity's bar recomposes on the stream event with no refetch; the last Operator cannot be demoted, said and refused | apply on a timer instead of the event → falls; allow the last demotion → falls |
| **R-L18-v** — a new account | 26 | the e-mail is required (refused with its reason on the surface AND by the operation); an e-mail matching a Plex account links; a non-Operator without a Plex match cannot sign in by password and the surface says so | accept an empty e-mail → falls |
| **R-L18-w** — the administrator block on the model | 27 | L17's R-L17-f on the six identities: shown to the Operator, absent from the DOM for the others; forced route `403` | show it to the Member → falls |
| **R-L18-x** — the viewer's memory is the viewer's | 9 | after a switch of identity, a remembered tab the new account does not hold is ignored, the default falls to its first tab | read the stored tab without asking the model → falls |
| **R-L18-y** — a closed address | 6, 7 | a cold `/system`, `/maintenance`, `/settings`, `/trackers`, `/accounts` for an account that does not hold the place draws what OPEN 3 says (A: the not-found page, the address unchanged; B: the reserved place) and never the page; the page's reads answer `403`; the same addresses for the Operator draw the pages | remove the address guard → falls; answer a closed address with the page itself → falls |
| **R-L18-z** — Profil's list is the model's | 19 | the rights Profil lists equal the model's for each identity (`household-member`, `guest`, `izno` differ); the ceiling appears as a reason when on; no sentence is keyed to a role | retype one right's sentence keyed to a role → the agreement falls; drop the ceiling's reason → falls |

### 5.1 Rules the earlier lots wrote that this lot re-aims

- **L22's R-L22-s** (the bar's shares) is read at one, two and three places (phases 5, 9); it stays green over each,
  and OPEN 7 says whether it must be amended.
- **L22's default-tab rule** (R-L22-a as amended 2026-09-26) gains the fall-back of R-L18-x.
- **L16's « hidden from other accounts »** is discharged by R-L18-d; L16's rules said it was not provable until now.
- **`harness/settings.py`'s read-only hold** (lines ~398–401: the « lecture seule » text on the banner) is re-aimed onto the
  ceiling dial in phase 17 — the assertion stays, its trigger changes.

---

## 6. The register rows and the demands touched

### 6.1 The register rows

- **B-143** — « §17 (accounts, rights, Plex SSO) has no surface, no contract operation and no lot »: **closed by this
  lot's close** (phase 29) — `open` today, `by audit`. Its own sentence names the one requirement on EXISTING code: the read-only
  role absorbed. Phase 17 is that.
- **B-300 / B-335** name « tous les comptes du foyer » in two confirmations. The sentences stay true (only the Operator
  writes configuration) — **not touched**, not a row of this lot.
- The rows this lot finds are written as they are found, by the phase that finds them. **None is pre-written here.**

### 6.2 The demands PROPOSED (D7) — in the register's own form, not asserted

Eight rows the register lacks. **The lot files each by editing `frontend/maquette/contract/openapi.json` and
regenerating the register**, in the phase that draws its surface. OperationIds and paths are proposals and adjust.

| # | operation | operationId | what it is for | Filed in phase |
| --- | --- | --- | --- | ---: |
| D | `GET /api/auth/me` | `readAccount` (re-shaped) | The account: its **role** (operator, household member, guest, none), its **two options**, whether a **Plex account is linked** and which, and the instance's **ceiling**. L22's row D asked for the row; this is its shape. § 17; `backend-demands-architecture.md` § 2 | 1 |
| E | `POST /api/auth/plex` | `signInWithPlex` (new) | The Plex SSO: begin and complete a sign-in with a Plex identity; answers the account (with its role) or the reason it is not admitted. Only Operators may hold a password without SSO. § 17 | 1 |
| I | `PUT /api/acquisition/…/requester` | `reassignRequester` (new) | Change the requester of an acquisition — the Operator's right. **Keyed by the card's own identity** (the contract's card carries `ids` and the routes `mediaId` / `followedId`): one row if the phase finds one identity, two if it finds two. Organisation ruling 9; § 17 | 1 |
| K | `PUT /api/acquisition/…/quality` | `setAcquisitionQuality` (new) | The per-acquisition override of the quality profile (fact 11) — never an edit of the profile. `backend-demands-architecture.md` § 3; § 17 | 1 |
| F | `GET /api/accounts` | `readAccounts` (new) | The roster — `accounts.manage` only; each account with its role, options and Plex link. Organisation ruling 14 | 10 |
| G | `POST /api/accounts` | `createAccount` (new) | A new account: a name, a **mandatory e-mail**, a role; links to a Plex account whose e-mail matches; refuses an empty e-mail | 22 |
| H | `PATCH /api/accounts/{accountId}` | `updateAccount` (new) | Change an account's role and its two options; **refuses to demote the last Operator** | 22 |
| L | `POST /api/acquisition/to-handle/{mediaId}/take` | `takeQueued` (edited) | Declares the `403` the 62 other operations already declare — an edit of an operation, not a row | 1 |

And **one by-hand row in `docs/reference/frontend-backend-demands-stream.md`** (§ 2.3), the operator amends that file, not this
lot: **M — an account's rights changed** (a role, an option, a Plex link), so the affected account's bar and drawer
recompose without a poll (NE-DOIT-PAS-8).

**And one architecture row, N, PROPOSED for `docs/reference/backend-demands-architecture.md` § 2 (the operator amends that
file, not this lot): the instance ceiling covers EVERY write** — § 17: « tout compte est ramené à la lecture seule quel
que soit son rôle » — which **reverses A18** (`tests/unit/web/routes/test_staging_write_policy.py`: acquisition and decision
writes stay open on staging so the mobile journeys can be validated there). The interface is drawn on § 17; the engine
follows. **The consequence is stated, not hidden**: once the engine follows, a mutating journey can no longer be walked on
the staging instance, and the operator weighs that when he reads this row.

### 6.3 The clause-map rows PROPOSED (the operator amends the map; this lot does not)

| Clause | Today | After the lot | Proof |
| --- | --- | --- | --- |
| **DOIT-12** — « montrer l'application de CE compte (§17) » | `to draw` | `served` | R-L18-b, c, d, g, k, n, o — each right on both sides |
| **NE-DOIT-PAS-7** — the rights model absorbing the read-only role | `outside the interface` (the interface's share assigned to this lot) | the interface's share `served` | R-L18-b's source hold (no second read-only path), R-L18-o |
| **NE-DOIT-PAS-3** applied to rights (§ 17 point 1) | `served` for busy/409 only | extended to rights: no `403` after a gesture on a right the model says is absent | R-L18-d, i, k, n |

**The README's cut table and `docs/reference/frame-model.md` rows** (Part 9, « the gate is the frame's »; the bar's
composition) are rewritten by the close (phase 29); the sentences are directives, so they change in the same move as
the decision.

---

## 7. What this design does NOT draw, and what is OPEN

### 7.1 Not drawn — and whose it is

- **The backend** — the rights model's enforcement, the requester's persistence, the SSO flow, the account store, the
  staging ceiling — **after the freeze of the interface** (`product-intent.md` § 15; D7). This lot draws what the
  backend owes and mocks it, on invented identities marked as such.
- **Deleting or disabling an account.** § 17 and ruling 14 dictate « list, rights, Plex link » and creation; nothing dictates
  removal. **Not drawn, not proposed** — the operator's word first.
- **An approval flow for proposals.** § 17 says the Member « propose » acquisitions and the guest « demande » one;
  nothing dictates a validation step. None is drawn; OPEN 6 asks only what the guest's act is.
- **Sessions of other accounts** (who is signed in, a forced sign-out): not dictated.
- **A per-account audit trail** of who changed what: not dictated; L20's history is the machine's.
- **Push notifications** to an account: a platform demand (L16's), not this lot's.
- **The Trackers page, the ratio, the cross-seed** — L16, L17. This lot gates them; it draws none of them.
- **The media sheet's « acquis le …, requester » trace** — a debt L22's design named (its § 3.5); L18 makes it possible
  (the requester is now the account's) and does not draw it: it is the steward's to assign.
- **The engine of L13 and the frame's code beyond the five edits of § 3.2–3.3, § 3.1** — untouched.
- **Multiple Plex servers, a second household, invitations by link**: not dictated.

### 7.2 Seven OPEN design questions — each with TWO readings and NO choice

The rule of this section: **a reading is a complete drawing with its cost, and this document chose none.** Where a
question is a placement the operator may want to SEE, the plan draws both (phase 23) and the operator rules on what he saw.

**OPEN 1 — where accounts are managed.** Organisation ruling 14 accepts two forms and leaves the choice to this
drawing « sauf mot contraire ». *Reading A — a rubric « Comptes » of Réglages.* The account roster sits beside the
configuration's six rubrics; one settings page holds every reserved thing. It costs a rubric that is NOT a schema
topic (fact 10: the rubric list is the server's data, so the page composes one rubric of its own) and inherits the
settings page's ceiling banner and its « Lecture seule » pattern; it hides behind the configuration right, so the
drawer holds no new entry. *Reading B — a first-level entry of the drawer.* « Comptes » becomes a page of its own
(`accounts`, a row in the table, an address, a route), grouped in `configuration` beside Réglages. It costs a row, a
path in `lib/addresses.ts`, a thin route and a region — and it puts accounts one tap from the menu, apart from the
settings' six rubrics, which the operator's own words (« une page Comptes complètement séparée de premier niveau »)
name. The surface of § 3.9 is the same in both; phase 23 draws the placement, once per reading.

**OPEN 2 — how the gate offers Plex beside the password.** *Reading A — side by side.* The password form stays where it is;
under it, a separator and « Se connecter avec Plex », equal in weight. It costs the least and shows the two ways
equally, which is « s'ajoute, ne remplace pas » to the letter. *Reading B — Plex first.* « Se connecter avec Plex » is
the primary act and the password form sits behind a « Utiliser un mot de passe » disclosure. It costs a disclosure state,
and it reads the fact that only Operator accounts may hold a password at all: most accounts sign in with Plex, and the
form is the emergency door of § 3.1 point 3.

**OPEN 3 — what an account sees of a place it does not hold** (Trackers, Système, Maintenance, Réglages, Comptes), in the
drawer AND at a cold address. *Reading A — absent.* The drawer draws no entry; a cold `/system` draws the not-found page
(the address is treated as unknown, ruling of L22's OPEN 5 form). § 17 point 1 to the letter, and § 17 point 4's « une
page absente de la barre relève du point 1 » extended to the drawer; it costs an account that cannot tell « does not
exist » from « not for me ». *Reading B — reserved and explained.* The drawer draws the entry marked as reserved; the
place, opened, says what it is, that this account does not hold it and who can (« Réservé à l'Opérateur »). § 17 « Ce
qu'un compte voit par défaut » — the pipeline and the configuration « restent visibles et expliqués comme réservés » —
and point 2. It costs a reserved-place component and five sentences (phase 7 is drawn ONLY under this reading) and a
drawer that shows an account entries it cannot use. **The bar is outside this question** (§ 17 point 4 dictates it
absent).

**OPEN 4 — who holds the right that opens Trackers and Système.** Ruling 11 says these appear « que pour ceux qui y ont
droits » and § 17 lists no such right among the three roles' powers or the two options. *Reading A — the Operator
alone; no option is added.* The Member and the guest see Acquisition and Médiathèque only, which is the operator's
own example (« certains n'auront accès qu'à acquisitions et mediatheque »). It costs nothing in the model and a
Member who wants to see the ratio cannot. *Reading B — a third per-account option, set by the Operator.* « voir les
trackers » (and one for Système), independent of the role. It costs an amendment of § 17's « deux options », which is
the operator's to make, a third and fourth toggle in S9, and two more identities' worth of proof.

**OPEN 5 — where the reassign gesture starts.** *Reading A — an act in the card's sheet.* « Réaffecter… » is one more act
in the journey sheet (`panel-journey.ts`, three acts today) and the follow's, offered to the Operator. It adds nothing to
the card itself, so every existing state is unmoved for the Operator. *Reading B — the requester line is the control.* On
the card, the line L22 draws (« ajouté par Izno ») is tappable for the Operator, and opens the chooser directly. It puts
the gesture where ruling 9 says it lives (« depuis la carte ») and costs a mark on the Operator's card — the states that
draw a card diverge (§ 4.1, phases 11–12) — and a line that is a control for one account and text for the others.

**OPEN 6 — what the guest's « demande d'acquisition » is.** The maquette's only way to ask is « Suivre » (`createFollow`,
which L22's ruling 1 keeps distinct from a PUNCTUAL acquisition). *Reading A — the same act.* The guest follows like the Member:
the tab « Suivis », the add flow, unchanged; the roles differ by the quality option and the rest of § 17. It costs the
distinction between « suivre » (the Member's, § 17) and « demande » (the guest's). *Reading B — a distinct act.* The guest
asks for a PUNCTUAL acquisition (a film, a season) with no follow: a « Demander » on Découvrir, an operation of its own
(one more demand row), no « Suivis » tab for the guest. It keeps § 17's two verbs apart and costs an act, a row and a
phase (phase 15 costs 6 points under A, 17 under B, cut into 10 + 7).

**OPEN 7 — a bar of one place.** The rights-less Plex user holds the Médiathèque alone (§ 17: « médiathèque uniquement »),
and the operator dictated « 2 boutons le min » (L22's OPEN 2). *Reading A — the bar is not drawn for one place.* The frame
rule stays (2 to 4); a single destination needs no bar, and the account reaches everything else through the menu. It costs
the bar's height contribution (`app/bar-height.ts`, the content's padding) and a state where the bottom slot is empty.
*Reading B — the bar draws its one place at full width.* The rule is amended to « 1 to 4 »; it costs an amendment of the
operator's own words and a bar that carries no choice.

---

## 8. What this design believes the contract gets wrong

Recorded, not amended — the steward amends the plan, the operator the constitution and the map. **No file outside
`docs/features/maquette-l18/` is edited for them, except the one dated line under the L18 heading of
`docs/reference/frontend-architecture.md`.**

1. **« The gate stays `app/sign-in.tsx` »** — there is no such file (fact 1). The gate is `app/entry.ts` and markup in
   `index.html` extracted by `serve.py`. The plan edits the three, and the L18 entry's « Where it lives » reads short.
2. **« The drawer's identity block »** — the drawer's block is the host's served identity, not the account (fact 2); the
   account's identity is the header avatar and its menu. The lot edits the drawer's ENTRIES, not an identity block.
3. **« Behind the served role the backend already exposes »** (L17's « Dictated »): the backend serves no account role
   (its `/auth/me` answers `{username}`), only the instance's deployment role (L17's own finding).
4. **§ 17 says the staging role is a ceiling that makes every write read-only; the engine's policy (A18) leaves
   acquisition and decision writes open** (fact 7). **The constitution wins and the engine follows the interface** (steward, 2026-09-27): § 6.2's row N proposes it, and states the consequence — the mobile journeys A18 wanted to validate on staging can no longer mutate there.
5. **§ 17 « ce que cela impose à la preuve » cannot be met by the oracle.** The oracle draws the Operator's application
   (§ 4.1); a right absent for another account is invisible to it. The lot's proof is § 5's rules, each on both sides.
6. **« Les autres comptes » is a Profil section reserved « so the shape is settled »** (`features/account/page.tsx`);
   ruling 14 sends it out. Its three keys and its section are deleted by phase 18, not kept « just in case ».
7. **The organisation rulings of 2026-09-26 (10–15) are cited « organisation ruling N (2026-09-26,
   `docs/reference/operator-method.md`) »** but the committed text of that file has no entry of that date yet: they are
   in the auditor's copy and land in a later docs PR. The words quoted here are the operator's, as relayed.
