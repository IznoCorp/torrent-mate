# Plex API — Reference

> Plex Media Server HTTP API — reference for `api/plex.py` (`PlexClient`) and
> `subscribers/plex.py` (`PlexSubscriber`).
> Scope: the post-dispatch library refresh, nothing else.
> Last updated: 2026-07-28

---

## Table of Contents

- [Why this client exists](#why-this-client-exists)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
- [Section resolution — longest prefix](#section-resolution--longest-prefix)
- [Sections cache — lifetime](#sections-cache--lifetime)
- [Fail-soft contract](#fail-soft-contract)
- [Timeouts, attempts, and the no-circuit-breaker trade-off](#timeouts-attempts-and-the-no-circuit-breaker-trade-off)
- [Particularities](#particularities)
- [Configuration](#configuration)
- [Manual probe](#manual-probe)

---

## Why this client exists

The storage disks are macFUSE/NTFS mounts. They deliver **no filesystem events**
to Plex, so Plex's own watcher never notices a new folder: the media stays
invisible until somebody triggers a scan by hand.

Proven by the Margin Call incident (2026-07-28): acquisition → dispatch →
indexation all succeeded, the film sat on disk with NFO and artwork, and Plex
showed nothing. A manual partial scan (HTTP 200) made it appear instantly.

`PlexClient` is that trigger, fired by `PlexSubscriber` on every
`ItemDispatched`. It is deliberately **not** a general Plex API wrapper: two
calls, one purpose.

---

## Authentication

**`X-Plex-Token` header. Never a query parameter, never logged.**

```
X-Plex-Token: <token>
```

Plex also accepts `?X-Plex-Token=` in the query string — this client does not
use it. A token in a URL ends up in server access logs, in `Referer` headers,
and in any exception whose text carries the URL. The header keeps it out of all
three.

Stored in `.env`:

```bash
PLEX_URL=http://localhost:32400   # server root, default when unset
PLEX_TOKEN=                       # empty ⇒ the subscriber is never wired
```

Guarantees, each pinned by a test (`tests/unit/test_plex_refresh.py`):

- the token never appears in a log record — asserted over five failure paths
  (server down, 401, refresh 403, refresh timeout, unparseable body), scanning
  `record.getMessage()`, `record.args`, `record.msg` and `caplog.text`;
- the token never appears in the **rendered console output** either — asserted
  against the formatter production actually installs, over the failure that
  used to leak it (see below);
- `repr(PlexClient)` prints the base URL only;
- `PLEX_TOKEN` is registered in `Settings._SECRET_FIELDS`, so `repr(Settings)`
  shows `plex_token=<masked>`;
- every request asserts `token not in url` and `token not in params`.

### Three rules that keep the header out of the output

A log record without the token is **not** sufficient: the console handler
(`logger.py`, `structlog.dev.ConsoleRenderer`) expands `exc_info` into a rich
traceback **with frame locals**, and every frame between `_get` and the socket
holds the header dict. Printing a traceback of a failed Plex call therefore
printed `X-Plex-Token: <token>` in clear on stderr — the operator's terminal,
PM2 log capture, cron mail. (The JSON file handler uses `format_exc_info`, which
has no locals, and was never affected.)

1. **Never `exc_info`, anywhere on this path.** Failures log
   `error=type(exc).__name__`, which is what an operator can act on anyway.
2. **Catch `Exception`, not `requests.RequestException`.** The narrow catch let
   a token-bearing stack escape to a caller that logged it with a traceback.
   The trigger is real, not theoretical: preparing a URL whose path carries a
   surrogate — an undecodable macFUSE/NTFS filename — raises
   `UnicodeEncodeError`, which is a `ValueError`.
3. **`allow_redirects=False`.** `requests` strips only `Authorization` when a
   redirect changes host; a custom header is forwarded, so a 302 would hand the
   token to whatever origin the response names.

Finding the token: Plex Web → any item → ⋯ → **Get Info** → **View XML**; the
`X-Plex-Token` query parameter of the opened URL is it.

---

## Base URL

`Settings.plex_url`, default `http://localhost:32400`. Trailing slashes are
trimmed at construction. The server is reached over plain HTTP on the local
host — no TLS assumption, no discovery, no plex.tv round-trip.

---

## Endpoints

| Call            | Endpoint                                           | Used by                    |
| --------------- | -------------------------------------------------- | -------------------------- |
| List sections   | `GET /library/sections`                            | `PlexClient.sections()`    |
| Partial refresh | `GET /library/sections/{id}/refresh?path=<folder>` | `PlexClient.refresh(path)` |

Both send `Accept: application/json`; Plex otherwise answers XML.

### `GET /library/sections`

```json
{
  "MediaContainer": {
    "Directory": [
      {
        "key": "1",
        "title": "Films",
        "Location": [
          { "path": "/Volumes/Disk1/medias/films" },
          { "path": "/Volumes/Disk2/medias/films" }
        ]
      }
    ]
  }
}
```

Only `key`, `title` and `Location[].path` are read. Parsing is tolerant: a
missing or wrongly-typed field yields fewer sections, never an exception — a
malformed payload must degrade the trigger, not break a dispatch.

### `GET /library/sections/{id}/refresh?path=<folder>`

A **partial** scan: Plex walks that one folder instead of the whole section. Any
2xx means accepted. The response body is not read — Plex answers before the scan
finishes, so the status is the only signal available (and the only one needed).

`/library/sections/{id}/refresh` **without** `path` would rescan the entire
section: minutes of disk churn on NTFS mounts for one added folder. The `path`
parameter is what makes this cheap enough to fire on every dispatched item.

---

## Section resolution — longest prefix

The section id is **never hardcoded**. It is resolved from the server's own
`Location` paths, by the **longest matching prefix** of the dispatched folder:

```
Section 3 "Tout Disk3"  →  /Volumes/Disk3/medias
Section 2 "Séries"      →  /Volumes/Disk3/medias/series

/Volumes/Disk3/medias/series/Severance   → section 2   (longest match)
/Volumes/Disk3/medias/documentaires/X    → section 3   (only match)
```

Two reasons this is not a first-match:

1. **Nested roots are real here** — the four disks each carry several libraries,
   and a parent root (`…/medias`) can contain a child root (`…/medias/series`).
   First-match returns whichever section Plex happened to list first, which
   would scan the wrong library.
2. **Section ids differ per server** and change when libraries are recreated. A
   hardcoded map silently rots; resolution against live `Location` paths cannot.

Matching is done on a **path boundary** (`root` or `root/…`), so `/…/medias`
never matches `/…/medias-old` — a sibling naming pattern that exists on these
disks.

No matching section ⇒ `refresh()` logs `plex.no_section_for_path` and returns
`False`. That is the honest outcome for a library Plex does not know about.

### Operator action — two dispatch targets are in no section

Resolution can only work for roots Plex actually indexes. Cross-checking the
live `GET /library/sections` against every `(disk, category)` the config allows
to dispatch (via `conf.resolver.folder_for`) gives **25 covered / 2 uncovered**:

| Disk     | Category             | Folder                                    |
| -------- | -------------------- | ----------------------------------------- |
| `disk_1` | `anime`              | `/Volumes/Disk1/medias/series animes`     |
| `disk_4` | `tv_shows_animation` | `/Volumes/Disk4/medias/series animations` |

Media dispatched to those two folders logs `plex.no_section_for_path` and is
**never scanned** — the Margin Call symptom persists there. This is a Plex-side
configuration gap, not a code one: add both folders to the `Séries TV` section
(section 5) and the trigger covers the whole dispatch surface. Re-run the
cross-check after any disk or library reorganisation.

---

## Sections cache — lifetime

`sections()` fetches lazily and caches for the **process lifetime**. Sections
are stable configuration; re-reading them per dispatched item would be one HTTP
request per file for data that does not move.

Consequences, deliberate:

- a library added to Plex **mid-run** is invisible to the current process; the
  next pipeline run picks it up (the daemon paths are short-lived);
- a **failed** fetch is not cached — the empty list is returned for that call
  only, so a Plex that comes back up is used again without a restart;
- the cache is an **optimisation, not an invariant**. One daemon thread runs per
  dispatched item, so a burst can find the cache empty concurrently and fetch
  `/library/sections` more than once (measured: 10 simultaneous items ⇒ 10
  fetches). It is left unlocked on purpose — a lock would serialise the worker
  threads for a best-effort trigger, and the duplicate fetches all store the
  same answer. The shared `requests.Session` is likewise used concurrently,
  which `requests` does not guarantee; the cost of a lost race is one missed
  refresh, which the next dispatch repairs.

---

## Fail-soft contract

**Absolute.** The dispatch already happened; reporting it as a failure because
its notifier could not reach a media server would be a lie about what the
pipeline did (NE-DOIT-PAS-5 forbids the _silent_ failure, not the _survived_
one — hence a warning at every exit).

| Situation                       | Log                                                                | Result              |
| ------------------------------- | ------------------------------------------------------------------ | ------------------- |
| Server unreachable              | `plex.sections_unreachable` / `plex.refresh_unreachable` (warning) | `refresh → False`   |
| Bad token (401)                 | `plex.sections_http_error` with the status (never the token)       | `refresh → False`   |
| Refresh rejected (4xx/5xx)      | `plex.refresh_http_error`                                          | `refresh → False`   |
| Path in no section              | `plex.no_section_for_path`                                         | `refresh → False`   |
| Non-JSON / unparseable body     | `plex.sections_unparseable` with `error=<type>`                    | `refresh → False`   |
| Malformed `Location` shape      | parsed to a section with no roots                                  | `refresh → False`   |
| Transport raises a non-HTTP exc | `plex.refresh_unreachable` with `error=<type>`                     | `refresh → False`   |
| Section resolution raises       | `plex.section_resolution_failed` with `error=<type>`               | `refresh → False`   |
| Client raises anything          | `plex.refresh_failed` (subscriber, `error=<type>`)                 | dispatch unaffected |
| Success                         | `plex.refresh_triggered` (path, section, title)                    | `refresh → True`    |

`refresh()` is **total**: every caller of `_get` catches `Exception`, not just
`requests.RequestException`. That matters twice. Fail-soft is the obvious
reason; the other is the token — see below, a stack that escapes to a caller
which logs a traceback prints the credential.

The subscriber runs the call on a **daemon thread** (`plex-refresh`), per the
event-bus performance contract: subscribers return fast or hand the work off. Its
thread body catches `Exception` as a second belt, because an exception escaping a
daemon thread prints to stderr and would pollute an operator's run output.

Independently of both belts, `EventBus.emit` wraps every subscriber callback in
its own `try/except`, so even a failure to _start_ the thread cannot reach the
dispatcher.

An `ItemDispatched` whose `target_path` is `None` is skipped at DEBUG — the field
is additive (D1), so a `None` means "this emitter carried no folder", never
"guess one".

---

## Timeouts, attempts, and the no-circuit-breaker trade-off

```python
_TIMEOUT  = (2.0, 5.0)   # connect, read
_ATTEMPTS = 1
```

One attempt, short timeouts: this is a **trigger**, not a business API. A retry
loop against a dead server would multiply the delay the pipeline pays for
nothing, and the next dispatch (or the operator) retries naturally.

This client uses **raw `requests`**, not the shared `HttpTransport`. The reason
is the token: the transport logs URLs and wraps errors in messages this module
does not control, and the one hard guarantee here is that the credential appears
nowhere. Owning the HTTP call is what makes that provable.

The cost, stated plainly: **no circuit breaker**. A permanently-dead Plex is
paid at up to ~7 s per dispatched item, on a daemon thread — it never blocks the
bus, but a large batch against a dead server spawns one short-lived thread per
item. A failed `sections()` short-circuits before the second call, which bounds
most of it. If this ever hurts, the fix is a breaker around `sections()`, not a
move to the shared transport.

---

## Particularities

- **JSON only on request.** Without `Accept: application/json`, Plex answers XML
  for both endpoints.
- **`key` is a string** (`"3"`), not an int. It is interpolated into the refresh
  URL verbatim.
- **Refresh is asynchronous.** A 200 means _accepted_, not _scanned_. There is no
  completion signal short of polling the section, which this client does not do.
- **`Location` paths are server-side paths.** They match the pipeline's paths
  only because Plex and the pipeline run on the same host, against the same
  mounts. A containerised Plex with remapped volumes would need a translation
  layer — out of scope, and it would surface as `plex.no_section_for_path`
  rather than as a wrong scan.
- **Temporary sections (`097-TEMP`) are out of scope** — the staging area is not
  a Plex library.

---

## Configuration

| Variable     | Default                  | Effect                                                                                                                           |
| ------------ | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| `PLEX_URL`   | `http://localhost:32400` | Server root                                                                                                                      |
| `PLEX_TOKEN` | _(empty)_                | **Gates the feature.** Empty ⇒ the subscriber is never constructed, zero requests, one `plex_refresh_disabled` info line at boot |

Wiring goes through `subscribers.plex.build_plex_subscriber`, the **single
owner** of the gate, and both dispatch composition roots call it:

- `commands/pipeline.py::run` — the full pipeline;
- `commands/pipeline.py::dispatch` — the standalone step.

Both, not one: `personalscraper dispatch` emits `ItemDispatched` exactly like the
full run, so wiring only `run` left the documented step-by-step path dispatching
media that never reached Plex — the Margin Call bug, reproduced verbatim. Same
reasoning as `resolve_dispatch_authority` and
`maybe_run_post_dispatch_maintenance`, which are single owners for the same
parity reason.

The gate is the token alone and deliberately **outside** the `--headless` gate:
the other subscribers produce operator output a cron run may silence, while this
one makes the dispatched media visible — a headless run needs it exactly as
much. Construction is fail-soft too: a malformed `PLEX_URL` yields `None` and a
`plex_refresh_unavailable` warning rather than a failed boot.

---

## Manual probe

Read-only check that the server answers and the token is valid (never paste the
token into a shell history you keep — prefer the env var):

```bash
curl --connect-timeout 10 --max-time 30 -s \
  -H "X-Plex-Token: $PLEX_TOKEN" -H "Accept: application/json" \
  "$PLEX_URL/library/sections" | head -c 400
```

Triggering a real partial scan of one folder:

```bash
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}\n' \
  -H "X-Plex-Token: $PLEX_TOKEN" \
  --get --data-urlencode "path=/Volumes/Disk2/medias/films/Margin Call (2011)" \
  "$PLEX_URL/library/sections/1/refresh"
```

`200` = accepted. This writes nothing to the media; it only asks Plex to look.
