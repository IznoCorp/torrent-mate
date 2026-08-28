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

**What would close it**: `data.provider` and `data.provider_id` on those three events. The
rule then keys on the identity it was given, and the widening goes.

## 2. A progress event needs somewhere to go that is not a list

**Asked for by** `frontend/maquette/design/src/features/acquisition/live.ts`.

`DownloadProgressed` fires per torrent per tick. It is deliberately mapped to nothing:
pointing it at the queue would invalidate that list continuously — **a poll wearing an
event's clothes**, and this lot's third contract clause (« no polling remains where an event
exists ») read backwards, since a `setInterval` any grep can find would at least be visible.

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

## 4. A hello that says more than the commit

**Asked for by** `frontend/maquette/design/src/lib/relay.ts`.

`ws.hello` carries `build_commit`, and the relay keeps it. B-079 and B-080 both want it —
the design host cannot say which commit it serves, and the drawer shows a hard-coded version
and calls itself up to date. Neither is L10's to close, and the relay is what will make
closing them possible.

**What would close them**: nothing new on the wire. They are recorded here so the next reader
knows the value has arrived and is waiting for a surface.
