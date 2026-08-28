# What the interface asks of the EVENT STREAM

**WRITTEN BY HAND, and that is a finding rather than a choice (B-153).**
`docs/reference/frontend-backend-demands.md` is COMPUTED — `scripts/compare-contracts.py`
diffs the maquette's contract against the backend's, operation by operation, and `--check`
refuses a committed register that differs. It cannot describe anything here: **OpenAPI does
not describe a WebSocket**, so neither document declares `/ws/events`, and the computed
register will go on reporting nothing about the stream. Nothing reads as identical to
no demands, which is why this file exists beside it rather than as a section inside it.

**NOBODY IS BUILDING THIS YET, and that is D7.** No backend work happens until the interface
is frozen. What this file is for is that the specification arrives as a diff rather than a
blank page.

**The protocol as it stands** is `docs/reference/web-ui.md` § WebSocket Protocol, and L10
implements against it exactly: accept-then-close `4401`, one `ws.hello` carrying
`build_commit`, `{id, type, data}` per event, `ws.ping` after 30 s of silence, and replay
from `?last_id=` with an exclusive lower bound. Every demand below is something the
interface needs and that protocol does not offer.

---

## 1. An event should say WHICH title it is about

**Asked for by** `frontend/maquette/design/src/features/media/live.ts`.

`ItemDispatched`, `SeasonAbsorbedEpisodes` and `FilmAcquired` each change whether we own a
title, or how much of it — which is half of what a media sheet shows (§11). Their payloads
carry no provider identity the interface can read, so the sheet's rule invalidates
`["/api/media"]`: **every open sheet, on every such event.**

A sheet is keyed per identity (`["/api/media", provider, identifier]`) and that key is the
narrowest in the whole map. Widening it is the one place this lot knowingly refreshes more
than it should, and it is written down here rather than left as a shape nobody remembers
choosing.

**CORRECTED after an adversarial review, and the correction is the point.** This demand first
named all three events and said none carried an identity. Two of them do: `FilmAcquired` and
`SeasonAbsorbedEpisodes` both carry `media_ref: MediaRef` — `tvdb_id | tmdb_id | imdb_id` —
and `event_to_dict` encodes it as a nested object, so it arrives as `data.media_ref.tvdb_id`.
**The demand was asking the backend for work already done.**

`ItemDispatched` genuinely carries only a source-folder basename, and it is the one event that
justifies the widening.

**What would close it**: a provider identity on `ItemDispatched`. The rule then keys on what it
was given, and the widening goes.

## 2. A progress event needs somewhere to go that is not a list

**Asked for by** `frontend/maquette/design/src/features/acquisition/live.ts`.

**THIS DEMAND'S PREMISE WAS FALSE AND THE EVENTS ARE MAPPED NOW.** It said `DownloadProgressed`
"fires per torrent per tick". Its own docstring says the opposite: only the HIGHEST threshold
crossed per reconcile pass fires, the persisted mark only moves forward, and the thresholds are
25/50/75 — **three emissions for a whole download**. `DownloadStarted` fires once per info-hash,
exactly once. Meanwhile `ItemProgressed`, which the map DOES point at a list, fires once per item
per step across nine steps. The volume argument was applied to the bounded events and not to the
unbounded one.

Both are rules in `features/acquisition/live.ts` now, and the card no longer freezes on
« Téléchargement 68 % » for the life of the tab.

A progress bar is a real want. It is a different mechanism: a value pushed into the component
that draws it, never a list refetched from the top.

**What would close it**: nothing on the backend, necessarily — this is an interface decision
first, and it belongs to whichever lot draws a progress bar. It is recorded here because the
event EXISTS and the interface refuses it, which is exactly the kind of decision that reads
as an oversight when nobody wrote it down.

## 3. The events of §18 and §19 reach the browser and no surface

**Asked for by** the same two files, as exemptions.

`RatioMeasured`, `SeedObligationRecorded` / `Satisfied` / `Breached`, `CrossSeedInjected` and
`CrossSeedRejected` are emitted, reach the stream, and are claimed by no rule — because the
surfaces they belong to have no page in the maquette yet (B-144, B-145).

**What would close it**: the pages, not the backend. Listed here so that « the map does not
name them » reads as a consequence of a known gap rather than as an omission.

## 4. Nothing says a SERVICE stopped answering

**Asked for by** `frontend/maquette/design/src/features/system/live.ts`, as its exemption —
and it is the exemption nobody should be happy with.

**HALF OF THIS DEMAND WAS ALREADY BUILT, and an adversarial review is what found that out.**
It first said that neither `/api/system/services` nor `/api/system/dependencies` could arrive
as news, and asked for "an event when a probed service or dependency changes state — one per
transition, never per probe".

`CircuitBreakerOpened`, `CircuitBreakerClosed` and `CircuitBreakerHalfOpened`
(`personalscraper/core/circuit.py`) fire **on transition and never per probe** — the exact
shape asked for. And the dependencies read's own rendering says so: its second line is
« aucun disjoncteur ouvert ». They are a rule in `features/system/live.ts` now.

They were invisible for a compounding reason worth recording: `check-live-relay.py`'s event
corpus was a hand-written list of six files, and `core/circuit.py` was not among them — nor was
`api/metadata/registry/_events.py`, six more. **Nine real events reached the browser outside
everything that counts them.** The corpus is derived from `Event` subclasses now, and the total
went from 40 to 48.

**What is left, and it is genuinely missing**: nothing is emitted when a SERVICE itself stops
answering — process liveness, as opposed to a provider call failing. `/api/system/services` is
refreshed by nothing.

**What would close it**: an event on a service's up/down transition. One per transition, never
per probe: a per-probe event is a poll wearing an event's clothes, which is demand 2's subject.

**What must NOT close it**: a `refetchInterval` on those two reads. It would satisfy the
page and break this lot's third contract clause, and it is written here so that the easy
answer is refused on the record rather than in a review.

## 5. A hello that says more than the commit

**Asked for by** `frontend/maquette/design/src/lib/relay.ts`.

`ws.hello` carries `build_commit`, and the relay keeps it. B-079 and B-080 both want it —
the design host cannot say which commit it serves, and the drawer shows a hard-coded version
and calls itself up to date. Neither is L10's to close, and the relay is what will make
closing them possible.

**What would close them**: nothing new on the wire. They are recorded here so the next reader
knows the value has arrived and is waiting for a surface.
