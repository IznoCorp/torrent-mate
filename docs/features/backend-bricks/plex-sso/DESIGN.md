# plex-sso — the Plex account sign-in, as a client module · DESIGN

A backend BRICK, drawn before the operator's « Go, design prêt »: the conversation with plex.tv (a PIN, a token, the
account's identity, its access to THIS server) does not depend on anything the maquette may still move. The route
that uses it, the session it opens and the account it creates are K1's. **Written 2026-10-01, on `main` at
`fe3d2b012`. Nothing under `personalscraper/` was touched; plex.tv was not called — every protocol fact below comes
from Plex's public article, or from the public source of projects that implement it, each cited.**

---

## 0. His words, and the rows this brick serves

- § 17 (dictated 2026-08-26): « Les utilisateurs Plex sont des utilisateurs de l'application, et ils s'authentifient
  par le SSO Plex. Quelqu'un qui a accès au serveur Plex du foyer n'a pas à se voir attribuer un second mot de passe
  pour consulter la médiathèque : il se connecte avec son compte Plex. »
- § 17, tranché 2026-08-30: « Le SSO Plex s'ajoute, il ne remplace pas. […] Un compte créé hors Plex porte un e-mail
  obligatoire ; s'il est celui d'un compte Plex, les deux sont liés » ; « Un utilisateur Plex sans aucun droit ici est
  admis en lecture seule, médiathèque uniquement » ; « les demandes existantes […] sont attribuées au compte
  propriétaire du serveur Plex (Izno) ».
- 2026-10-01: « on peut préparer déjà certains briques, SSO Plex, FCM, nouveaux tracker à ajouter, ... tout ce qui sera
  néccéssaire à la refonte et ne sera pas affecté par mes changements/adaptations/ajouts sur le design. »

| Brief row | What it asks | What this brick gives it |
| --- | --- | --- |
| `backend-brief.md` § 1.4 `signInWithPlex` (new, § 17, L18 E) | « Plex SSO; a first sign-in gets the Default role; an e-mail matching a local account LINKS them » | the verified Plex identity (stable id, e-mail, name, avatar) and its access to this server — what K1 creates, links or refuses on |
| § 1.4 « existing acquisitions » (ruling 9) | attributed to the Plex server's OWNER account | `server_access(...) == OWNER` names the owner at his first sign-in |
| § 2.4 « accounts, roles, rights, Plex SSO — rebuild » | « `api/plex.py` speaks to the SERVER, the Plex account sign-in (PIN / OAuth) is new » | the ACCOUNT side, as its own module |
| § 6 K1 | « the sign-in gate (Plex first) » | the client K1's route calls |
| L18 § 3.1 S1, F47 | « When Plex is unreachable, the disclosure OPENS BY ITSELF » — the gate tells unreachable from refused | two distinct errors: `PlexAccountUnreachable` vs `PlexTokenRefused` (§ 3.2) |

---

## 1. What exists today (measured)

| Fact | Command |
| --- | --- |
| `api/plex.py` (779 lines) is the SERVER client: `PlexClient(base_url, token)` — `sections`, `refresh`, `section_items`, `item`, `matches`, `match` — over the operator's `PLEX_TOKEN`; no plex.tv call anywhere | `grep -n "    def " personalscraper/api/plex.py`; `rg -n "plex\.tv" --type py personalscraper` → only support-article URLs in `trailers/placement.py` |
| Its token discipline, pinned by tests: the token in the `X-Plex-Token` header only, never logged, never `exc_info`, `except Exception`, `allow_redirects=False`, a `__repr__` without it | `sed -n 40,60p personalscraper/api/plex.py`; `docs/reference/plex-api.md` § Authentication |
| The server's `machineIdentifier` is read nowhere | `rg -n "machineIdentifier\|machine_identifier" --type py personalscraper` → nothing |
| The web sign-in: ONE user (`config.web.username`), a scrypt hash, a JWT `tm_session` cookie (`sub` = the username, HS256, `SameSite=Strict`, `HttpOnly`) | `sed -n 60,160p personalscraper/web/auth/routes.py`; `personalscraper/web/auth/tokens.py` |
| The perimeter: `guarded_api` with `Depends(require_session)`; no users table, no account id | `rg -n "require_session\|guarded_api" --type py personalscraper/web/app.py` |
| The maquette's contract: `POST /api/auth/plex` `signInWithPlex` → `200 Account`, refusals `400/401/403/409/500/503` as `Problem`; **no request body declared** (« x-unseeded: invented: the Plex SSO does not exist yet ») | `python3 -c "import json;print(json.load(open('frontend/maquette/contract/openapi.json'))['paths']['/api/auth/plex'])"` |
| The gate's copy: « Se connecter avec Plex », « Plex ne répond pas : connectez-vous avec un mot de passe. », « Ce compte se connecte avec Plex : il n'a pas de mot de passe ici. » | `rg -n "plexUnreachable\|passwordRefused" -g '*.json' frontend/maquette/design/src/i18n/fr.json` |

### 1.1 The protocol — public sources

- **Plex's article** « Authenticating with Plex » (`https://forums.plex.tv/t/authenticating-with-plex/609370`),
  CONFIRMED:
  - the application picks a product name and generates a client identifier ONCE, stores it and re-uses it;
  - `POST https://plex.tv/api/v2/pins` with `strong=true` and the headers `X-Plex-Product`,
    `X-Plex-Client-Identifier`, `Accept: application/json` → `{id, code, …, authToken: null}`;
  - the user signs in at `https://app.plex.tv/auth#?clientID=<id>&code=<code>&context%5Bdevice%5D%5Bproduct%5D=<name>&forwardUrl=<url>`
    (`forwardUrl` optional — without it the window simply stays on Plex);
  - `GET https://plex.tv/api/v2/pins/<id>` (with `code` and the client identifier) — `authToken` set means claimed;
    polled once per second;
  - a token is checked by `GET https://plex.tv/api/v2/user`: 200 valid, 401 invalid; **any other status or no answer
    is NOT proof of invalidity**.
- **Overseerr** (`github.com/sct/overseerr`, `src/utils/plex.ts`, `server/api/plextv.ts`, `server/routes/auth.ts`),
  CONFIRMED: the PIN created and polled IN THE BROWSER (a popup, 1 s), the `authToken` posted to its server, which
  reads the identity and admits the owner or a user the owner's server is shared with (`checkUserAccess`:
  `GET https://plex.tv/api/users` with the OWNER's token, then the user's `Server[].machineIdentifier`).
- **python-plexapi** (`plexapi/myplex.py`), CONFIRMED: `MyPlexPinLogin` (the same PIN flow), `MyPlexResource` — a
  resource of `GET https://plex.tv/api/v2/resources?includeHttps=1` carries `clientIdentifier` (= a server's
  `machineIdentifier`), `owned`, `ownerId`, `provides`. On master, a newer **JWT device flow** (`MyPlexJWTLogin`,
  host `clients.plex.tv`, an Ed25519 key, a JWT valid 7 days and refreshable — forum
  `https://forums.plex.tv/t/jwt-authentication/931646`); Overseerr and Tautulli still use the classic PIN.
- The identity's fields (Overseerr's `PlexUser`): `id` (stable integer account id), `uuid`, `username`, `title`,
  `email`, `thumb`, `subscription`, `roles`, `authToken`.
- The server's own identifier: `GET <server>/identity` → `MediaContainer.machineIdentifier` (python-plexapi
  `server.py`). Whether it answers WITHOUT a token is INFERRED, not shown — the brick sends the token anyway.
- NOT established publicly: the PIN's lifetime (`expiresIn` is in no source read; python-plexapi waits 120 s by
  default), the answer to a poll of an expired PIN, any rate limit. Each is read from the capture (§ 4).

---

## 2. The boundary

### 2.1 What this brick builds NOW

1. **`personalscraper/api/plex_account.py`** — `PlexAccountClient`, the plex.tv ACCOUNT client: create a strong PIN,
   build the sign-in URL, check a PIN once, read the identity behind a token, and tell whether that identity is the
   OWNER of this server, a user it is SHARED with, or neither (§ 3.2). Stateless: every call takes what it needs;
   nothing is stored.
2. **`PlexClient.machine_identifier()`** on the existing SERVER client (adapt, `api/plex.py`): `GET /identity`, read
   once and cached for the process, fail-soft (`None`), under the module's three token rules.
3. **The token discipline of `api/plex.py`, applied to a token that is not ours.** The user's Plex token lives in a
   local variable for the length of one sign-in, then is handed to the caller and to nothing else (P-3): header only,
   never logged, never returned by any other path, never persisted by the brick, never in a `repr`, never in an
   exception text, no redirect followed (`allow_redirects=False`), `except Exception` at every call with
   `error=type(exc).__name__`.
4. **A probe script** `scripts/plex-signin-probe.py` — the operator's E2E and the fixtures' capture in one (§ 4).
5. **The reference** `docs/reference/plex-account-api.md` (the account side; `plex-api.md` keeps the server side and
   links to it).

### 2.2 What it leaves to its lot, after the « Go »

| Left | To | Why |
| --- | --- | --- |
| the route(s): `startPlexSignIn` → `{pinId, signInUrl}` and `signInWithPlex {pinId}` (P-2 = B), the server-side polling of the PIN, the `Problem` codes of each refusal (`403` for an account the server is not shared with, P-1 = A) | K1 + the maquette's contract (the new operation is drawn design-side) | the contract declares `signInWithPlex` and no body yet |
| the user's Plex token KEPT after the sign-in, encrypted (P-3 = B): the key, its rotation, the revocation | K1 | the store does not exist; the brick only hands the token to its caller |
| the account it creates or links: the Default role at a first sign-in, the e-mail link to a local account, `plexLinked`, the owner's attribution of existing acquisitions (ruling 9) | K1 | `app.db` accounts and roles do not exist (Q2) |
| the session the sign-in opens (today's `tm_session` reshaped onto an account id) | K1 | `web/auth` transform (brief § 2.4) |
| where the client identifier is persisted per environment | K0 / K1 (`app.db`, per environment — Q2) | the store does not exist; the brick takes the identifier as a parameter |
| the gate's states (Plex first, the disclosure, « Plex ne répond pas ») | drawn (L18 S1) | already in the maquette; the brick only gives K1 the two errors it needs to choose between them |

---

## 3. Modules and signatures

### 3.1 The types

```python
class PlexServerAccess(StrEnum):
    """What one Plex account is to THIS server — the codes K1 decides on."""
    OWNER = "owner"     # the resource whose clientIdentifier is this server's machineIdentifier, owned == 1
    SHARED = "shared"   # that resource present, owned == 0 — the server is shared with the account
    NONE = "none"       # no resource of this server in the account's list


@dataclass(frozen=True)
class PlexPin:
    """A strong PIN awaiting its sign-in. Carries no token.

    Attributes:
        id: plex.tv's PIN id (what a check reads).
        code: the PIN code (what the sign-in URL carries).
        expires_at: epoch seconds, from the answer when it carries an expiry, else None.
    """
    id: int
    code: str
    expires_at: float | None


@dataclass(frozen=True)
class PlexAccount:
    """The identity behind a token — the only facts K1 needs, and no token.

    Attributes:
        plex_id: plex.tv's stable account id (``id``) — the key, never the e-mail or the name.
        uuid: plex.tv's account uuid.
        username: the account's username.
        title: the display name (``title``), what the interface shows.
        email: the account's e-mail, as plex.tv holds it — what links a local account (§ 17).
        thumb: the avatar URL.
    """
    plex_id: int
    uuid: str
    username: str
    title: str
    email: str
    thumb: str | None
```

### 3.2 The errors — told apart because the gate is

```python
class PlexAccountError(Exception):
    """Base. Its text never carries a token, a PIN code or an e-mail."""

class PlexAccountUnreachable(PlexAccountError):
    """plex.tv did not answer, or answered 5xx / an unparseable body — the gate opens the password (F47)."""

class PlexTokenRefused(PlexAccountError):
    """plex.tv answered 401 to the token — the sign-in is refused, nothing is wrong with plex.tv."""

class PlexPinExpired(PlexAccountError):
    """The PIN is past its lifetime — the gesture starts again (status read from the capture, § 4)."""
```

Per the article, only a **401** proves a token invalid; every other failure is `PlexAccountUnreachable`, never a
refusal — the brick never tells someone « refused » because plex.tv was slow.

### 3.3 `personalscraper/api/plex_account.py`

```python
PLEX_TV = "https://plex.tv"
PLEX_AUTH_APP = "https://app.plex.tv/auth"
_TIMEOUT: tuple[float, float] = (3.0, 10.0)   # a person waits at the gate: bounded, one attempt


class PlexAccountClient:
    """The plex.tv ACCOUNT side. Stateless; the token it is handed never outlives the call."""

    def __init__(self, *, product: str, client_identifier: str,
                 session: requests.Session | None = None) -> None:
        """Args:
            product: ``X-Plex-Product`` and the sign-in URL's device product — the name plex.tv lists under
                « Authorized Devices » (one per environment: « TorrentMate », « TorrentMate (staging) », …).
            client_identifier: ``X-Plex-Client-Identifier`` — generated ONCE per environment and re-used
                (Plex's article); persisted by K0/K1, passed in here.
            session: injected in tests.
        """

    def create_pin(self) -> PlexPin:
        """``POST /api/v2/pins?strong=true``. Raises PlexAccountUnreachable."""

    def sign_in_url(self, pin: PlexPin, *, forward_url: str | None = None) -> str:
        """Pure. ``https://app.plex.tv/auth#?clientID=…&code=…&context%5Bdevice%5D%5Bproduct%5D=…[&forwardUrl=…]``."""

    def check_pin(self, pin_id: int, code: str) -> str | None:
        """ONE ``GET /api/v2/pins/{id}``: the token once claimed, None while pending. No loop here — the caller
        owns the cadence (≥ 1 s, Plex's own figure; NE-DOIT-PAS-8).
        Raises PlexPinExpired, PlexAccountUnreachable."""

    def account(self, token: str) -> PlexAccount:
        """``GET /api/v2/user``. Raises PlexTokenRefused (401 only), PlexAccountUnreachable."""

    def server_access(self, token: str, machine_identifier: str) -> PlexServerAccess:
        """``GET /api/v2/resources?includeHttps=1`` WITH THE USER'S OWN TOKEN: the resource whose
        ``clientIdentifier`` equals ``machine_identifier`` — owned ⇒ OWNER, present ⇒ SHARED, absent ⇒ NONE.
        Raises PlexTokenRefused, PlexAccountUnreachable."""

    def __repr__(self) -> str:
        """``PlexAccountClient(product=…)`` — no identifier, no token."""
```

**Why the user's own token for the access check, and not Overseerr's owner-token list.** `resources` answers « which
servers can THIS account reach, and does it own them » with the signing-in account's token alone. Overseerr's
`GET /api/users` needs the OWNER's plex.tv token on the server side for every sign-in; the brick would then hold a
second long-lived secret for nothing. The owner is recognised the same way (`owned`), which is what ruling 9 needs.

### 3.4 `api/plex.py` — one method added

```python
def machine_identifier(self) -> str | None:
    """``GET /identity`` → ``MediaContainer.machineIdentifier``, cached for the process lifetime.

    Fail-soft like every method here: None when the server does not answer — K1 then answers the sign-in
    with « Plex ne répond pas » (503), it never admits without the check.
    """
```

### 3.5 Decided here, and why (not his questions)

- **The classic strong PIN, not the JWT device flow.** The application needs the identity ONCE per sign-in, then
  opens its own session; a 7-day JWT to refresh buys nothing it uses, and the classic flow is what Plex's own article
  documents. If plex.tv retires it, only this module changes.
- **The brick keeps no Plex token** past the call that obtained it (P-3 = B decides the token is kept, by K1, encrypted,
  for a future feature — the brick stays stateless and only hands it to its caller). Nothing in the brief reads plex.tv
  on a user's behalf afterwards.
- **One client identifier and one product name per environment**, so plex.tv's « Authorized Devices » tells the
  three apart and a revocation of one leaves the others.

---

## 4. Tests

**Unit, on recorded captures** (`docs/reference/_samples/plex-account/`, tokens, PIN codes, e-mails, ids and uuids
REDACTED): a PIN created, a PIN pending, a PIN claimed, a PIN expired, `user` 200, `user` 401, `resources` for an
owner, `resources` for a shared user (if he has one at hand — else a hand-derived variant of the owner's capture,
marked as derived), the server's `/identity`.

- every request: the right URL, the three headers, the token in `X-Plex-Token` and never in the URL or the params,
  `allow_redirects=False`;
- every answer → the right type; 401 → `PlexTokenRefused`; 500, a timeout, a connection error, an HTML body →
  `PlexAccountUnreachable`; the expired PIN → `PlexPinExpired`;
- `server_access`: OWNER / SHARED / NONE from the captures, and NONE when the resource list is empty;
- **the token never leaks**, as `test_plex_refresh.py` asserts for the server token: over every failure path, no log
  record, `caplog.text`, exception text or `repr` carries the token, the PIN code or the e-mail — including the
  rendered console output with a traceback (the formatter production installs);
- `sign_in_url`: the four parameters, URL-encoded, `forwardUrl` present only when given;
- `machine_identifier`: parsed, cached (one request for two calls), `None` on failure.

**Manual E2E, by the operator's hand** — `scripts/plex-signin-probe.py` (no agent holds a Plex account):

1. it creates a PIN and prints the sign-in URL; he opens it on his phone and signs in with his Plex account;
2. it checks the PIN once per second until claimed or expired;
3. it prints his identity REDACTED (`plex_id` and `title` only) and his access to the server (`owner` expected);
4. with `--record`, it writes the redacted captures of § 4 into `docs/reference/_samples/plex-account/`.

A second run with a household member's Plex account, if he chooses, captures `shared`.

---

## 5. DECIDED — his rulings of 2026-10-01 (decision round 4)

**P-1 = A** — his words « A surtout pas B ! »: **access to this Plex server is the door.** Only the server's OWNER and
the accounts the server is SHARED with sign in (a first sign-in → the Default role); any other plex.tv account is
refused (`403`), whatever it is on plex.tv. « Sans aucun droit ici » means « no role beyond Default ». The brick
gives K1 the three codes it decides on (`server_access` → OWNER / SHARED / NONE); `NONE` is the refusal.

**P-2 = B** — **the PIN runs on the server.** `startPlexSignIn` answers `{pinId, signInUrl}`; the page opens the URL,
then calls `signInWithPlex {pinId}`, and the SERVER checks the PIN (`check_pin`, one call at a time, at the caller's
cadence ≥ 1 s). The user's Plex token never leaves the server; it works the same from an installed iOS PWA, whichever
window finishes on plex.tv. The contract's new operation is drawn design-side, with the maquette.

**P-3 = B** — **the user's Plex token is KEPT, encrypted**, for a future feature (a watchlist read, Plex's own
sharing). K1 owns the encrypted storage: the key, its rotation, the revocation. The brick stays stateless: nothing in
it may log, return or persist the token beyond handing it to its caller (`check_pin`'s return value, the argument of
`account` / `server_access`).

**P-4 = A** — **nothing to build for Plex Home's managed profiles** (no plex.tv login of their own — INFERRED: they
cannot complete a plex.tv sign-in). One that must enter gets a local account with `auth.password` in Comptes.

**Accounts and credentials he must create: none.** plex.tv requires no application registration (Plex's article:
choose a product name, generate an identifier). The probe reads the server address from the existing `PLEX_URL`
and the server token from the existing `PLEX_TOKEN` for `/identity`, by his hand only.

---

## 6. Phases

| Phase | What | Done when | Proving command |
| --- | --- | --- | --- |
| 1 | **The probe** `scripts/plex-signin-probe.py` (raw `requests`, the redaction tested on planted values) — then HE runs it with `--record` | the redaction test green; the captures in `docs/reference/_samples/plex-account/`, holding no token, code, e-mail or real id | `pytest tests/unit/test_plex_signin_probe.py -q`; `! python scripts/plex-signin-probe.py --record` (his hand) |
| 2 | **`PlexAccountClient`** — types, errors, the five methods, the token-leak suite; the probe rewired onto the client (its `--record` path keeps the raw answers) | every test of § 4 green on the captures | `pytest tests/unit/test_plex_account.py -q` |
| 3 | **`PlexClient.machine_identifier()`** + `plex-account-api.md` (and the link from `plex-api.md`) | parsed, cached, fail-soft; the server suite still green | `pytest tests/unit/test_plex_refresh.py tests/unit/test_plex_account.py -q` |
| — | **The operator's E2E** — the probe, without `--record`, on the merged client | his identity and `owner` printed, through the client this time | `! python scripts/plex-signin-probe.py` |

Gate per phase: `make lint`; pytest of the touched modules. His rulings P-1 to P-4 are decided (§ 5) and applied by K1;
the brick's phases wait only the operator's `--record` (phase 2 reads his captures).
