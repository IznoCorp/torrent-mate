# plex.tv Account API — Reference

> plex.tv's account side — reference for `api/plex_account.py` (`PlexAccountClient`) and
> `PlexClient.machine_identifier()` in `api/plex.py`.
> Scope: the Plex sign-in — a PIN, the identity behind a token, and its access to THIS server.
> The server side (library refresh, match guard) is [`plex-api.md`](plex-api.md).
> Last updated: 2026-10-04

---

## Table of Contents

- [What this client is for](#what-this-client-is-for)
- [Sources and what is inferred](#sources-and-what-is-inferred)
- [Application identity](#application-identity)
- [Endpoints](#endpoints)
- [Access to this server](#access-to-this-server)
- [Errors — only a 401 refuses](#errors--only-a-401-refuses)
- [The user's token](#the-users-token)
- [The server's identifier](#the-servers-identifier)
- [Captures](#captures)
- [Manual probe](#manual-probe)
- [The Plex door on v1](#the-plex-door-on-v1)

---

## What this client is for

A person signs in with their Plex account (`docs/reference/product-intent.md` § 17). The client
creates a PIN on plex.tv, builds the page where the person confirms it, checks the PIN once per
call, reads the identity behind the token the PIN yields, and tells whether that identity owns
this server, belongs to its owner's Plex Home, is a user the server is shared with, or none of
these. What the application does with the answer (create, link, refuse an account; keep the
token; open a session) is not this client's: it is stateless.

Design: `docs/features/backend-bricks/plex-sso/DESIGN.md`.

---

## Sources and what is inferred

| Fact | Source |
| --- | --- |
| PIN create / check, sign-in URL, client identifier generated once, 1 s polling | Plex's article « Authenticating with Plex » (`forums.plex.tv/t/authenticating-with-plex/609370`) |
| `GET /api/v2/user`: 200 valid, 401 invalid, anything else proves nothing | the same article |
| `resources` carries `clientIdentifier` (= a server's `machineIdentifier`), `owned` | python-plexapi `MyPlexResource`; the operator's capture |
| Answer shapes (`expiresIn` 1800 s on a fresh PIN, 10 s once claimed; the 401 envelope code 1001) | the operator's captures, 2026-10-04 |
| **A check of an expired PIN answers 404 (410 handled the same)** | **INFERRED** — no capture; the probe's fake and python-plexapi point at a 404 with plex.tv's error envelope (code 1020). Approved by the orchestrator 2026-10-04 |
| **`home: true` on a not-owned resource = a member of the owner's Plex Home** | **INFERRED, to confirm with a real Home member's capture** — the operator's account is in no Home; the test fixture `resources-home-derived.json` is derived from his own capture. Approved by the orchestrator 2026-10-04 |

---

## Application identity

Every request carries three headers:

| Header | Value |
| --- | --- |
| `Accept` | `application/json` |
| `X-Plex-Product` | the product name, one per environment — what plex.tv lists under « Authorized Devices » |
| `X-Plex-Client-Identifier` | generated ONCE per environment and re-used (Plex's article); the caller persists it and passes it in |

plex.tv requires no application registration.

---

## Endpoints

Host `https://plex.tv`. Timeouts `(3.0, 10.0)`, one attempt (a person waits at the sign-in),
`allow_redirects=False`.

| Method | Call | Request | Answer → result |
| --- | --- | --- | --- |
| `create_pin()` | `POST /api/v2/pins?strong=true` | no token | 200/201 `{id, code, expiresAt, …}` → `PlexPin(id, code, expires_at)` (epoch from `expiresAt`, else `None`) |
| `sign_in_url(pin, forward_url=None)` | — (pure) | — | `https://app.plex.tv/auth#?clientID=…&code=…&context%5Bdevice%5D%5Bproduct%5D=…[&forwardUrl=…]` |
| `check_pin(pin_id, code)` | `GET /api/v2/pins/{id}?code=…` | no token | 200 with `authToken` → the token; 200 with `authToken: null` → `None` (pending); 404/410 → `PlexPinExpired` |
| `account(token)` | `GET /api/v2/user` | `X-Plex-Token` | 200 → `PlexAccount(plex_id, uuid, username, title, email, thumb, confirmed)`; 401 → `PlexTokenRefused` |
| `server_access(token, machine_identifier)` | `GET /api/v2/resources?includeHttps=1` | `X-Plex-Token` (the USER's) | 200 list → `PlexServerAccess`; 401 → `PlexTokenRefused` |

`check_pin` makes ONE call; the caller owns the cadence (at most once a second, Plex's own
figure — NE-DOIT-PAS-8).

An identity answer without an integer `id` or a non-empty `email` is « outside the protocol »
(`PlexAccountUnreachable`): the e-mail is what links a local account, the id is the key.
`confirmed` is true only when plex.tv answers the boolean `true` (the capture redacts it): an
e-mail plex.tv has not confirmed links nothing.

---

## Access to this server

`server_access` reads the account's resources with **the account's own token**, and looks for the
resource whose `clientIdentifier` equals this server's `machineIdentifier`:

| Resource | Result |
| --- | --- |
| present, `owned` | `OWNER` |
| present, not `owned`, `home` | `HOME` (inferred — see above) |
| present, neither | `SHARED` |
| absent, or the list is empty | `NONE` |

Why not Overseerr's way (`GET /api/users` with the OWNER's token): it would make the server hold
the owner's plex.tv token for every sign-in, a second long-lived secret for nothing. `owned`
names the owner just as well. plex.tv sends these booleans as JSON booleans; `1` / `"1"` are
read as true too.

---

## Errors — only a 401 refuses

| Error | When |
| --- | --- |
| `PlexTokenRefused` | plex.tv answered **401** to `account` or `server_access` |
| `PlexPinExpired` | `check_pin` got 404 / 410 |
| `PlexAccountUnreachable` | no answer, a timeout, any other status (5xx, 403, 429…), a body that is not JSON or not the expected shape |

Plex's article: only a 401 proves a token invalid. Every other failure is « unreachable », so a
person is never told « refused » because plex.tv was slow, and the sign-in page can open the
password fallback instead.

---

## The user's token

The token is the return value of `check_pin` and the argument of `account` / `server_access` —
nothing else. The server client's three rules (`plex-api.md` § « Three rules that keep the header
out of the output ») hold here too:

1. failures log `error=type(exc).__name__` and a path TEMPLATE (`/api/v2/pins/{id}`), never the
   exception and never `exc_info`;
2. every call catches `Exception` and raises a `PlexAccountError` outside the `except` block —
   **neither its cause nor its context** — whose text names the path and the status or exception
   type only;
3. no redirect is followed.

`PlexPin.code` and `PlexAccount.email` are kept out of their `repr`; `repr(PlexAccountClient)`
names the product only. `tests/unit/test_plex_account.py::TestNoLeak` plants a token, a PIN code
and an e-mail in every failure path and asserts none reaches a log record, the console
renderer's output, an exception text or a `repr`.

---

## The server's identifier

`PlexClient.machine_identifier()` — `GET <PLEX_URL>/identity` with the operator's server token →
`MediaContainer.machineIdentifier`. Read once and cached for the process lifetime (a server's
identifier does not change); fail-soft: `None` when the server does not answer, refuses the token
or answers something unparseable, and a failure is not cached. The sign-in never admits anyone
without it.

---

## Captures

`docs/reference/_samples/plex-account/` — the operator's run of
`scripts/plex-signin-probe.py --record` (2026-10-04), redacted by the probe's allow-list:
`server-identity`, `pin-created`, `pin-pending`, `pin-claimed`, `user-200`, `user-401`,
`resources-owner`. Plus `resources-home-derived.json`, **derived, not recorded** (its `derived`
key says how). Not captured: an expired PIN, a shared user's or a Home member's own resources.

---

## Manual probe

His hand only (it calls plex.tv and reads `PLEX_URL` / `PLEX_TOKEN`):

```bash
python scripts/plex-signin-probe.py            # sign in on the phone; prints plex_id, title, access
python scripts/plex-signin-probe.py --record   # also writes the redacted captures
python scripts/plex-signin-probe.py --record --record-expired   # also waits an unclaimed PIN out
```

The probe goes through `PlexAccountClient`; a recording session keeps the raw answers for
`--record`. A run with a household member's account would replace the derived Home fixture.

---

## The Plex door on v1

`personalscraper/app/accounts/plex_sign_in.py` (`PlexSignInService`) is this client's one caller in
the application, behind `startPlexSignIn` (`POST /api/v1/auth/plex/start`) and `signInWithPlex`
(`POST /api/v1/auth/plex`).

| Step | What happens |
| --- | --- |
| start | the client identifier read from `app_setting` `plex.client_identifier` (created once); `create_pin`; the PINs consumed or expired deleted (at most 100 a start); the PIN stored with the sha256 of a nonce; the nonce handed in the cookie `tm_v1_plex_pin` (HttpOnly, SameSite=Strict, Path=`/api/v1/auth/plex`, until the PIN expires) |
| finish | the PIN bound to the cookie's nonce, else `plex.pin_unknown`; past its expiry `plex.pin_expired`; a check claimed at most once a second (an atomic `UPDATE`), else 202 pending; `check_pin` → `account` → the server's identifier → `server_access` |
| owner | OWNER only when the identity's `plex_id` is the account behind `PLEX_TOKEN` (read once, cached); otherwise refused as no access |
| admit | one transaction: the account by `plex_id`, else a local account by e-mail (linked, only when plex.tv confirmed the e-mail), else a new one; the PIN used; the token sealed in the vault (no vault: not kept, `plex_token.not_kept`); then the session |

First role, applied at creation or link only: Admin for the owner, `Role.defaultFor` `plexHome` for a
Home member, `plexGuest` for any other user. `plex_link.server_access` stores `shared` for a Home
member (the column allows `owner` and `shared`). A local account linked by e-mail drops its password
and its role to its kind's (`account.demoted_from` keeps the role left, until an Admin gives one);
the owner keeps Admin and his password.

| Refusal | Code |
| --- | --- |
| no access, lost access, an owned resource under another account, an e-mail another identity holds, an e-mail plex.tv has not confirmed | 401 `auth.refused` |
| plex.tv refused the token the PIN yielded | 401 `plex.token_refused` |
| an account an Admin cut | 403 `auth.access_disabled` |
| plex.tv silent | 503 `plex.unreachable` |
| no `PLEX_TOKEN`, the server silent, its identifier empty, or plex.tv refusing the server's token | 503 `plex.server_unreachable` |

`web.plex_forward_url` (configuration, absolute `http(s)` address, default none) is where plex.tv
sends the sign-in window once confirmed; it is never derived from a request.
