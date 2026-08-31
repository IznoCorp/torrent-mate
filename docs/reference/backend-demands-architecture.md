# Backend demands — architecture and design, for the backend brief

**What this file is.** The maquette replaces the shipped frontend, and **the backend follows the
interface** (`product-intent.md` §15): the engine is adapted to what the frozen interface needs,
after the interface is frozen and validated. Two registers already carry the OPERATION-level
demands — `frontend-backend-demands.md` (computed from the two OpenAPI contracts) and
`frontend-backend-demands-stream.md` (the event stream, by hand). Neither can carry a decision of
ARCHITECTURE: a computed register knows paths and schemas, not « the pipeline becomes a tunnel per
media ». This file does.

**What it is not.** It schedules nothing. The maquette's lots carry the letter L; the backend's
work will carry another letter, in a **backend brief** written once the maquette is finished and
validated, which will take this file, the two registers and the maquette's contract as its inputs.
**Recording a decision here is not deciding its implementation** — that is taken in its time, by
that brief (operator, 2026-08-30). Every entry names the constitution section it comes from, so the
brief can read the reason and not only the requirement.

---

## 1. The pipeline becomes a tunnel per media — §20

- One execution attaches to ONE arrival and follows it to its assimilation and the validation of
  its Plex match (§4). Several tunnels run in parallel, bounded by a configuration variable (the
  number of concurrent tunnels); an arrival that meets the bound is **queued visibly** (§6).
- **A blocked tunnel is not a waiting process.** A block (a match to confirm, §3) ENDS the
  execution and **persists its state**; the tunnel resumes where it stopped once unblocked — by
  the operator, or automatically according to the block's reason. This asks for a persisted tunnel
  state with its step, its reason and what it needs to resume, and a resume verb.
- The single trigger authority stays single (NE-DOIT-PAS-7): one lock discipline for N tunnels is
  a design question for the brief, not a licence for a second mechanism.
- Open in the constitution, to be dictated: which block reasons resume automatically; a tunnel
  whose media disappears; the granularity for a series (episode, season, release).
- **What the interface will ask of the stream**: per-media progress events carrying the media's
  identity (`frontend-backend-demands-stream.md` § 1 already asks for it), a tunnel's block and
  resume as events, and the global levers' state.

## 2. The requester, and rights — §17

- **Every acquisition has a requester.** A new request carries the connected user; existing
  requests, which have none, are attributed to the Plex server's owner account (Izno). An Operator
  may reassign a request to another user and manages every requester's requests.
- **A rights model with three roles and two per-account options** (Operator — bypasses ACLs;
  Household member; Plex guest; options: see others' acquisitions, set the quality profile of
  one's own). `GET /api/auth/me` must carry the role and the options; every mutating operation is
  authorised against the requester where the clause says « ses propres acquisitions ».
- **Plex SSO is added, not substituted.** Only Operator accounts may hold a password without SSO.
  A locally created account carries a mandatory e-mail; an e-mail matching a Plex account LINKS
  the two, and the user signs in either way. A Plex user with no rights here is admitted
  read-only, library only.
- **The read-only role becomes an instance ceiling**: on the staging instance every account is
  capped to read-only whatever its role. `require_not_staging` is absorbed by the model as that
  ceiling — one authorisation path, never two (NE-DOIT-PAS-7).
- **A right is proved on both sides, separately** (§17): the action absent from the surface for
  the account without it, AND the call refused for one that forces it. The backend owes the
  second half.

## 3. A quality profile override per acquisition — §17, §9

- The maquette already offers « Profil de qualité » on an acquisition, landing on the choice of a
  profile. That choice is a **per-acquisition override** of the profile that applies to it — never
  an edit of the profile itself, which stays global configuration reserved to the Operator. The
  backend must persist the override on the follow and honour it on the whole acquisition path
  (§9, « le profil qualité est respecté sur tout le chemin d'acquisition »).

## 4. The ratio is steered — §18 (L16's demands)

- The per-tracker policy (`min_ratio`, `min_seed_time`) becomes **writable from the interface**:
  one write operation, absent from both contracts today. The displayed ratio is the one the
  TRACKER recognises (NE-DOIT-PAS-1), never a locally computed figure.
- `obligations`, `stalled-grabs`, `downloads` exist and are called by nothing yet; their shapes
  are the interface's to diverge from if the drawn surface needs more (D7).
- **Dictated 2026-08-30 (§18 completed):** a verb to RELEASE an obligation early; reconciliation of
  an EXTERNAL removal (a torrent taken out of qBittorrent by hand closes its obligation as
  « released by removal », never a silent anomaly); a per-tracker ratio-alert threshold and a push
  channel to carry it (**FCM, iOS and Android** — a platform demand); a ranking input that
  subtracts points from releases on low-ratio trackers. Per-tracker Download / Upload volumes and
  trend, and per-active-torrent deadline and ratio, must be readable.

## 5. Cross-seed is seen and decided — §19 (L17's demands)

- **Nothing exists to call.** The maquette will declare the routes its experience requires — the
  feed of injections and refusals with their reasons, the per-tracker state, the verbs to prevent
  and to provoke — and the engine's `CrossSeedInjected` / `CrossSeedRejected` events must reach
  the stream. NE-DOIT-PAS-8 is the hard limit on any automation the surface offers.
- **Dictated 2026-08-30 (§19 completed):** cross-seed runs AUTOMATICALLY, on by default, with a
  per-tracker off switch — a config WRITE per tracker; and a per-torrent, per-tracker state route
  carrying four states (« actif », « stoppé », « tracker sans cross-seed », « erreur de
  cross-seed »). The media-sheet block is admin-only, so the route's answer is role-aware (§17).

## 6. The failure SHAPE the binding lot must reconcile first — B-267

Latent today, fatal at switchover: `personalscraper/web` raises `HTTPException(detail=…)` and
FastAPI serialises `{"detail": …}`, while the maquette's `isRequestFailure` requires
`{status, title, detail}` — so against the real backend EVERY refusal (403 read-only, 401, 400,
409) fails the shape test, takes the outage branch and is QUEUED over an action the server
refused. The fix is one side's reshaping, and it is the binding lot's first gesture; the full
entry is `BUGS.md` B-267. The mocks emit the right shape, which is why nothing is wrong today
and why nothing will warn tomorrow.

## 7. What the existing operation-level registers already ask, and this file does not repeat

`frontend-backend-demands.md` § 1–3 (operations the interface requires and the backend lacks,
renamed properties, pre-formatted fields) and `frontend-backend-demands-stream.md` § 1–6 (the
event's subject, a progress channel, the §18/§19 events, a service that stopped answering, the
ownership index, a richer hello). This file adds the decisions those registers cannot express.
