# ACCEPTANCE Criteria — media-sheet

**Feature**: [#388] Fiche détail média — route dédiée, réutilisable partout (+ § constitution)
**Version**: 0.78.0
**Date**: 2026-08-04
**Status**: _(filled after exercise)_

> Convention: every criterion is an executable shell command with documented expected
> output (per `docs/reference/feature-lifecycle.md`). Criteria tagged `OPERATOR` require
> manual verification against the staging instance (`tm-staging.iznogoudatall.xyz`) or a
> real mobile device — they cannot be automated without a live environment.

## ACC-01 — MediaDetails carries the four new fields

```bash
python -c "
from personalscraper.api.metadata._base import MediaDetails
import dataclasses
fields = {f.name: f.type for f in dataclasses.fields(MediaDetails)}
for name in ('director', 'series_status', 'episode_count', 'trailer_url'):
    print(f'{name}: {fields.get(name, \"MISSING\")}')"
```

**Expected output** (PEP 604 union syntax — `_base.py` has `from __future__ import
annotations`, so `dataclasses.fields()` yields string annotations):

```
director: str | None
series_status: str | None
episode_count: int | None
trailer_url: str | None
```

## ACC-02 — Endpoint serves a movie sheet (authenticated)

OPERATOR — run against staging. Substitute `$SESSION_COOKIE` with a valid session
cookie obtained from the browser's dev tools (Application → Cookies →
`torrentmate_session`).

```bash
curl --connect-timeout 10 --max-time 30 -s \
  -H "Cookie: torrentmate_session=$SESSION_COOKIE" \
  "https://tm-staging.iznogoudatall.xyz/api/media/tmdb/27205?kind=movie" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['provider'], d['provider_id'], d['title'], d.get('overview','')[:50])"
```

**Expected output** (shape, exact text varies by provider):

```
tmdb 27205 Inception A thief who steals corporate secrets through
```

## ACC-03 — Endpoint serves a TV series sheet (authenticated)

OPERATOR — same session-cookie pattern as ACC-02.

```bash
curl --connect-timeout 10 --max-time 30 -s \
  -H "Cookie: torrentmate_session=$SESSION_COOKIE" \
  "https://tm-staging.iznogoudatall.xyz/api/media/tvdb/255968?kind=tv" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['provider'], d['provider_id'], d['title'], d['kind'], 'series_status' in d, 'seasons' in d)"
```

**Expected output** (shape):

```
tvdb 255968 Top Chef tv True True
```

## ACC-04 — Cache TTL: two calls produce one provider API hit

OPERATOR — requires access to the server logs. Make two successive calls, then grep
the server log for provider-call traces (TMDBClient / TVDBClient log lines).

```bash
# Call 1
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" \
  -H "Cookie: torrentmate_session=$SESSION_COOKIE" \
  "https://tm-staging.iznogoudatall.xyz/api/media/tmdb/27205?kind=movie"

sleep 1

# Call 2 — should hit the in-process cache (no second provider call).
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}\n" \
  -H "Cookie: torrentmate_session=$SESSION_COOKIE" \
  "https://tm-staging.iznogoudatall.xyz/api/media/tmdb/27205?kind=movie"
```

**Expected output**: both return `200`. The server log shows exactly **one** TMDB API
call (search for `GET /3/movie/27205` in the staging process output). A second call
within the cache TTL reuses the cached result.

## ACC-05 — Degraded response when provider fails

OPERATOR — requires temporarily disabling the TMDB API (e.g. point to an unreachable
host, or restart staging with a bogus TMDB API key).

1. Make the provider unreachable.
2. Call the endpoint for any provider id.
3. Verify the response is `200` (never 500), `degraded_reason` is a non-empty French
   string, and identity fields (provider, provider_id, title) are present.

```bash
curl --connect-timeout 10 --max-time 30 -s \
  -H "Cookie: torrentmate_session=$SESSION_COOKIE" \
  "https://tm-staging.iznogoudatall.xyz/api/media/tmdb/99999999?kind=movie" \
  | python -c "import json,sys; d=json.load(sys.stdin); print('degraded_reason' in d and d['degraded_reason'] is not None, d.get('title','N/A'))"
```

**Expected output** (degraded path — nonexistent TMDB id falls back to the provider id
as title when a real provider outage is in effect; the key assertion is `degraded_reason`
is a non-empty truthy string and the status is 200):

```
True 99999999
```

## ACC-06 — Frontend route renders the media sheet page

The frontend is a Vite SPA — `curl` returns the static `index.html` shell, never
client-rendered markup.  Prove the route exists via the route-mirror test, which
mounts the component in jsdom:

```bash
cd frontend && npx vitest run src/router.test.tsx -t "fiche média"
```

**Expected output** (1 passed, the route mounts `MediaSheet` and renders its
skeleton — the test is in the route-mirror suite):

```
 RUN  v… /Users/izno/dev/PersonalScraper/frontend

 ✓ src/router.test.tsx > App routes mirror … > monte la fiche média sur « /media/tmdb/27205 »
 Test Files  1 passed (1)
      Tests  1 passed | … skipped (…)
```

## ACC-07 — product-intent.md carries §11

```bash
grep -c "§11 — Tout média est consultable" docs/reference/product-intent.md
grep -c "DOIT-11 — Être consultable" docs/reference/product-intent.md
grep -c "NE-DOIT-PAS-9 — Afficher un média sans chemin" docs/reference/product-intent.md
```

**Expected output** (three lines, each ≥ 1):

```
1
1
1
```

## ACC-08 — Preuve mobile 390 px (MANUAL)

**This criterion is MANUAL** — a real mobile-width rendering cannot be automated on
the CLI.

Procedure (per `product-intent.md` §méthode and the mobile-truth rule from memory):

1. Open `https://tm-staging.iznogoudatall.xyz/media/tmdb/27205` in Chrome.
2. Set the viewport to **390 × 844 px** (iPhone 14 size) via DevTools.
3. Open the iframe harness at 390 px width (see memory
   `feedback_test_mobile_at_real_width_iframe_harness`).
4. Verify:
   - No horizontal scrollbar (DOIT-9).
   - The poster + title + metadata are fully visible without truncation.
   - The overview, director, genres, and trailer link are readable.
   - The ownership section renders (owned / not owned).
   - For a TV series: seasons are listed with episode counts.
5. Capture a full-page screenshot as proof.
6. Also test `/media/tvdb/255968?kind=tv` (a TV series) to verify the season list
   renders correctly at 390 px.

**Pass**: screenshot shows full content at 390 px width, no horizontal overflow,
all sections visible.

---

## Exercise log

| ACC    | Date | Result | Notes                              |
| ------ | ---- | ------ | ---------------------------------- |
| ACC-01 |      |        |                                    |
| ACC-02 |      |        |                                    |
| ACC-03 |      |        |                                    |
| ACC-04 |      |        |                                    |
| ACC-05 |      |        |                                    |
| ACC-06 |      |        |                                    |
| ACC-07 |      |        |                                    |
| ACC-08 |      |        | MANUAL — screenshot proof required |
