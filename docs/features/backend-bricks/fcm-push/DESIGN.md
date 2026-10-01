# fcm-push — the push channel: Firebase Cloud Messaging to the installed PWA · DESIGN

A backend BRICK, drawn before the operator's « Go, design prêt »: delivering one notification to one device of one
account does not depend on what the maquette may still move. WHAT is said, WHEN (the ratio threshold), to WHOM, and
the surface where an account turns notifications on, are K5's and the maquette's. **Written 2026-10-01, on `main` at
`fe3d2b012`. Nothing under `personalscraper/` or `frontend/` was touched; no Firebase project or account was created
and no Google endpoint was called — the facts below are Firebase's and WebKit's public documentation, each cited.**

---

## 0. His words, and the rows this brick serves

- § 18, tranché 2026-08-30: « Si le ratio d'un tracker descend trop bas, l'application le signale par une alerte — et,
  à terme, par notification push (FCM, iOS et Android), qui devient une demande de plateforme. »
- Q10, 2026-10-01 (`backend-brief.md` § 5): FCM is the channel — « Telegram est pollué et je veux m'en débarrasser »
  (Telegram refused as the alert's channel; its removal NOT ordered); « pas pressé, mais le projet FCM peut être
  préparé dès maintenant : notifications et web push sur la PWA installée, Android et iOS » ; threshold 1.2 by default,
  tracker by tracker.
- 2026-10-01: « on peut préparer déjà certains briques, SSO Plex, FCM, … tout ce qui sera néccéssaire à la refonte et
  ne sera pas affecté par mes changements/adaptations/ajouts sur le design. »
- Q2, 2026-10-01: three stores by owner, one file per environment — push subscriptions belong to the new `app` store
  (`app-dev.db`, `app-staging.db`, `app.db`); brief § 3.2 lists « push subscriptions (FCM, § 5 Q10) » as new data.

| Brief row | What it asks | What this brick gives it |
| --- | --- | --- |
| § 1.3 « the ratio alert by push » (platform, § 18, Q10) | FCM, web push on the installed PWA, Android and iOS; Telegram is not the channel | the channel: a sender, a subscription store, the service worker's push handling, the client's registration (no UI) |
| § 6 K5 | « the alert threshold (default 1.2, per tracker) and its channel FCM (… may be prepared from K0 on, no hurry) » | everything but the trigger and the words |
| § 3.2 | push subscriptions in `app`, per environment | the table's shape and its store, for K0's `app.db` baseline |

---

## 1. What exists today (measured)

| Fact | Command |
| --- | --- |
| The notify family: `Notifier` (`send(message, parse_mode)`, `send_report(report)` — one chat, free text) and `HealthChecker`; both fail-soft (never raise, log and return `False`); two providers, `telegram.py`, `healthchecks.py` | `sed -n 1,60p personalscraper/api/notify/_contracts.py` |
| No push code anywhere: no FCM, no Web Push, no subscription | `rg -n -i "fcm\|firebase\|webpush\|vapid" --type py personalscraper` → nothing |
| The maquette's service worker `frontend/maquette/design/sw.js` (220 lines): `install`, `activate`, `message`, `fetch` — NO `push`, NO `notificationclick`; a built source whose placeholders (`__BUILD__`, `__SHELL__`, `__EXTRAS__`) `vite.config.mjs` substitutes | `grep -n addEventListener frontend/maquette/design/sw.js`; `grep -n __SHELL__ frontend/maquette/design/vite.config.mjs` |
| Registration split: `index.html`'s inline script registers the worker (the sign-in gate borrows it); `src/app/worker-registration.ts` owns the update discipline | `sed -n 1,40p frontend/maquette/design/src/app/worker-registration.ts` |
| The manifest (`frontend/maquette/installable.py`): `"display": "standalone"`, `start_url` and `scope` `/` — what iOS requires of a web app for push | `sed -n 73,90p frontend/maquette/installable.py` |
| The maquette draws no notification opt-in: no `Notification.requestPermission`, no `pushManager` | `rg -n "requestPermission\|pushManager" -g '*.ts' -g '*.tsx' frontend/maquette/design/src` → nothing |
| Python dependencies: `requests`, `httpx`, `PyJWT` declared; `cryptography` present only transitively; `google-auth` absent | `grep -n -i "jwt\|httpx\|google" pyproject.toml` |
| The `app` store does not exist yet (K0 creates it, Q2) | `rg -n "app\.db\|app-dev" --type py personalscraper` → nothing |

### 1.1 The platform — public sources

- **Send** (CONFIRMED, `https://firebase.google.com/docs/cloud-messaging/send/v1-api`, `…/reference/fcm/rest/v1/projects.messages`):
  `POST https://fcm.googleapis.com/v1/projects/{projectId}/messages:send`, `Authorization: Bearer <access token>` from
  a service account with the scope `https://www.googleapis.com/auth/firebase.messaging`. A `Message` targets a
  `token`; its `webpush` part carries `headers` (`TTL`, `Urgency`), `data`, `notification`, `fcm_options.link`. A
  `validate_only` flag checks a request without delivering it. The legacy API is gone (2024).
- **Errors** (CONFIRMED, `https://firebase.google.com/docs/cloud-messaging/error-codes`): `UNREGISTERED` (404) and
  `SENDER_ID_MISMATCH` (403) ⇒ the token is dead, remove it; `INVALID_ARGUMENT` (400) ⇒ a bad request — a dead token
  only once the payload is known good; `QUOTA_EXCEEDED` (429) ⇒ back off, ≥ 1 min; `UNAVAILABLE` (503) /
  `INTERNAL` (500) ⇒ retry, honouring `Retry-After`; `THIRD_PARTY_AUTH_ERROR` (401) ⇒ the project's web-push
  credentials are wrong (configuration, not the token).
- **Client** (CONFIRMED, `https://firebase.google.com/docs/cloud-messaging/js/client`): HTTPS only; a « Web Push
  certificate » (VAPID key pair) generated in the console, its public key given to the SDK; by default a
  `firebase-messaging-sw.js` at the root. An EXISTING worker can be used instead by passing its registration
  (`serviceWorkerRegistration`) — INFERRED from SDK discussions, not from the page. **The current page presents a
  newer `register()` / `onRegistered()` API keyed by the Firebase Installation id and calls `getToken()` deprecated**;
  whether `messages:send`'s `token` accepts that id was NOT confirmed — phase 3 settles it against the pinned SDK
  version (§ 6).
- **Token lifetime** (CONFIRMED, `https://firebase.google.com/docs/cloud-messaging/manage-tokens`): a token idle 270
  days expires; Firebase recommends refreshing it monthly and storing a timestamp with each upload.
- **iOS** (CONFIRMED, `https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/`,
  `https://firebase.blog/posts/2023/08/fcm-for-safari/`): iOS / iPadOS **≥ 16.4**, ONLY for a web app ADDED TO THE
  HOME SCREEN with `display: standalone` (or `fullscreen`); the permission asked from a DIRECT user gesture; no Apple
  developer account; delivery through `*.push.apple.com`. Every push must SHOW a notification (no silent push).
  Known: on an iOS PWA the permission may read `default` after a reload (`firebase-js-sdk#8269`), so the client
  re-sends its token at every start while the push subscription exists, whatever the permission reads, and the
  server UPSERTS. The EU's iOS 17.4 removal of home-screen apps (Feb. 2024) was
  reverted before release.
- **Server library** (PyPI): `firebase-admin` 7.x pulls gRPC, Firestore and Storage; `google-auth` 2.x (+
  `cryptography`, `pyasn1-modules`) mints the access token, and the send is one HTTP call — Firebase's own Python
  example for v1.

---

## 2. The boundary

### 2.1 What this brick builds NOW

1. **The sender** — `personalscraper/api/notify/fcm.py`, `FcmSender`: one message to one token over HTTP v1, the
   access token from the service-account file via `google-auth` (one new declared dependency, not `firebase-admin`),
   the answer mapped to an OUTCOME CODE (§ 3.2). Fail-soft like the family: it never raises on a delivery failure.
2. **The subscription store** — `personalscraper/push/store.py`: the table's DDL (adopted by K0's `app.db` baseline,
   one file per environment), a `PushSubscriptionStore` protocol and its SQLite implementation over a connection it
   is given; tested on `:memory:`.
3. **The dispatcher** — `personalscraper/push/dispatch.py`, `PushDispatcher.notify_account(account_id, message)`: fans
   one message out to every live subscription of an account, revokes a dead token, records each outcome, honours a
   back-off. No trigger, no recipient policy.
4. **The service worker's push handling** — in `frontend/maquette/design/sw.js`: a `push` listener that ALWAYS shows
   a notification (iOS's rule), and a `notificationclick` listener that focuses an open window of the application or
   opens one at the message's link. Non-visual, no new screen.
5. **The client's registration module** — `frontend/maquette/design/src/lib/push-registration.ts`, no UI: feature
   detection (`supported`, `installed` — iOS's condition —, `permission`), `register()` (asks the permission —
   callable ONLY from a gesture —, obtains the FCM token through the application's own worker registration) and
   `unregister()`. It hands the token to a function it is given; the route it posts to is K5's.
6. **The operator's setup steps** (§ 5 F-1) and a credential probe `scripts/fcm-probe.py` (§ 4).
7. **The reference** `docs/reference/fcm-api.md`.

### 2.2 What it leaves to its lot, after the « Go »

| Left | To | Why |
| --- | --- | --- |
| the TRIGGER: a tracker's ratio under `economy.alert_threshold` (default 1.2), its hysteresis, how often it may repeat | K5 | brief § 1.3, Q10 — « only the channel is drawn » |
| WHO receives a message: for the ratio alert, every account holding `trackers.view` (F-4 = A) | K5 + K1 | rights are K1's |
| the WORDS of each message and where its click lands | the maquette (`fr.json`) + K5 | every UI string lives in `fr.json`; the target page is a design decision |
| the opt-in SURFACES (F-3): the offer « Activer les notifications sur cet appareil » at the opening of the installed PWA, AND the Profil per-device line with the four states (not installed on iOS, denied, unsupported, on for this device) | the maquette, FIRST | a surface is drawn before it is coded; the maquette draws none today (§ 1) |
| the routes: post a subscription, remove one, list this account's devices | K5 (+ the contract) | shaped by the opt-in surface |
| the subscription table's place in `app.db`'s baseline and its foreign key to the accounts table | K0 / K1 | the store and the accounts do not exist yet |
| Telegram | nobody | Q10: its removal is NOT ordered; this brick neither touches nor replaces it |

---

## 3. Modules and signatures

### 3.1 The message — codes, never sentences

```python
@dataclass(frozen=True)
class PushMessage:
    """One notification, as FACTS (X4): the device's worker turns the code into words from ``fr.json``.

    Attributes:
        code: a member of the closed push code set (e.g. ``"tracker.ratio_low"``), declared by K5.
        params: the code's typed parameters (``{"tracker": "c411", "ratio": 1.12, "threshold": 1.2}``).
        link: the in-app path the click opens (``"/trackers/c411"``) — same-origin, never absolute.
        tag: collapses a newer message onto an older one of the same tag on the device (one per tracker).
        ttl_seconds: how long FCM keeps it for an offline device.
        urgency: ``"normal" | "high"`` (Web Push ``Urgency``).
    """
    code: str
    params: Mapping[str, str | int | float]
    link: str
    tag: str | None = None
    ttl_seconds: int = 86_400
    urgency: Literal["normal", "high"] = "normal"
```

It is sent as a **data-only** web-push message (`webpush.data` = `{code, params (JSON), link, tag}`), so the worker —
not the browser — composes what is shown; the wire carries no French and no English sentence.

### 3.2 `personalscraper/api/notify/fcm.py`

```python
class PushOutcome(StrEnum):
    DELIVERED = "delivered"        # 200
    TOKEN_DEAD = "token_dead"      # UNREGISTERED 404, SENDER_ID_MISMATCH 403 — revoke the subscription
    REJECTED = "rejected"          # INVALID_ARGUMENT 400 — our payload or the token's format; kept, counted
    RETRY_LATER = "retry_later"    # 429, 500, 503 — with retry_after
    MISCONFIGURED = "misconfigured"  # THIRD_PARTY_AUTH_ERROR, 401/403 on OUR credentials, no service-account file
    UNREACHABLE = "unreachable"    # no answer, a timeout


@dataclass(frozen=True)
class PushResult:
    outcome: PushOutcome
    retry_after_seconds: float | None = None
    fcm_error: str | None = None   # FCM's errorCode, a code, never a body


class FcmSender:
    """Firebase Cloud Messaging HTTP v1 — one message, one token. Fail-soft: never raises on delivery."""

    provider_name: ClassVar[str] = "fcm"
    REQUIRED_CREDS: ClassVar[list[str]] = ["FCM_SERVICE_ACCOUNT_FILE"]

    @classmethod
    def from_service_account_file(cls, path: Path, *, session: requests.Session | None = None) -> Self:
        """Reads the project id from the file; the private key stays inside the credentials object."""

    def send(self, token: str, message: PushMessage, *, validate_only: bool = False) -> PushResult: ...

    def __repr__(self) -> str:
        """``FcmSender(project_id=…)`` — no key, no token."""
```

**Token hygiene, as `api/plex.py`'s**: a device token and the access token travel in the body / the
`Authorization` header only; failures log `error=type(exc).__name__` and the FCM `errorCode`, never `exc_info`,
never a token; `allow_redirects=False`.

### 3.3 `personalscraper/push/store.py`

```sql
CREATE TABLE push_subscription (
    id              INTEGER PRIMARY KEY,
    account_id      TEXT    NOT NULL,             -- K1's account key; the FOREIGN KEY lands with K1
    token           TEXT    NOT NULL UNIQUE,      -- the FCM registration token of ONE browser on ONE device
    platform        TEXT    NOT NULL CHECK (platform IN ('android', 'ios', 'desktop', 'unknown')),
    user_agent      TEXT,
    created_at      REAL    NOT NULL,             -- epoch time.time(), as pipeline_run
    refreshed_at    REAL    NOT NULL,             -- the client's last re-send (monthly refresh, every start)
    last_sent_at    REAL,
    last_outcome    TEXT,                         -- a PushOutcome code
    failure_count   INTEGER NOT NULL DEFAULT 0,   -- consecutive REJECTED / UNREACHABLE
    revoked_at      REAL,
    revoked_reason  TEXT CHECK (revoked_reason IN ('token_dead', 'unregistered', 'signed_out', 'stale'))
);
CREATE INDEX push_subscription_account ON push_subscription(account_id) WHERE revoked_at IS NULL;
```

```python
class PushSubscriptionStore(Protocol):
    def upsert(self, *, account_id: str, token: str, platform: PushPlatform,
               user_agent: str | None, now: float) -> PushSubscription: ...
        # a known token moves to the account presenting it (one browser, one owner) and is un-revoked
    def live_for(self, account_id: str) -> list[PushSubscription]: ...
    def revoke(self, token: str, *, reason: RevokeReason, now: float) -> None: ...
    def record(self, token: str, result: PushResult, *, now: float) -> None: ...
    def revoke_stale(self, *, not_refreshed_since: float, now: float) -> int: ...   # 270 days, Firebase's figure


class SqlitePushSubscriptionStore:   # implements PushSubscriptionStore over a given sqlite3.Connection
    DDL: ClassVar[str]
```

The store is **per environment** by construction: it lives in the environment's `app` file (Q2). dev, staging and
prod are three origins, so a device subscribed on two of them holds two tokens, one in each file.

### 3.4 `personalscraper/push/dispatch.py`

```python
@dataclass(frozen=True)
class DispatchReport:
    delivered: int
    revoked: int
    deferred: int             # RETRY_LATER — the caller decides whether to re-send after retry_after
    failed: int               # REJECTED, UNREACHABLE, MISCONFIGURED
    misconfigured: bool       # True ⇒ Système should say the channel is broken, not the device


class PushDispatcher:
    def __init__(self, sender: FcmSender, store: PushSubscriptionStore,
                 clock: Callable[[], float] = time.time) -> None: ...

    def notify_account(self, account_id: str, message: PushMessage) -> DispatchReport:
        """Every live subscription of the account, one send each; TOKEN_DEAD ⇒ revoke; every result recorded.
        No retry loop inside (NE-DOIT-PAS-8): a deferral is reported, its re-send is the caller's."""
```

### 3.5 The service worker — `frontend/maquette/design/sw.js`

```js
// PUSH — a data-only FCM message: { data: { code, params, link, tag } } (the envelope read from the capture, § 4).
self.addEventListener("push", (event) => {
  event.waitUntil(showFrom(event.data));   // ALWAYS shows: an unknown code shows the catalogue's generic line
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(focusOrOpen(event.notification.data.link));   // a same-origin path only; anything else → "/"
});
```

**The words come from `fr.json`, never from the wire.** The build already substitutes placeholders into `sw.js`; it
gains a fourth, `__PUSH_TEXTS__`, the `push` namespace of `fr.json` (each code's title and body, with `{{param}}`
interpolation, plus one generic line). A code with no entry shows the generic line — a push is never silent, and
never French typed into the worker. Nothing under `/api/` is cached by the change: the worker's `NEVER` rule stands.

### 3.6 The client — `frontend/maquette/design/src/lib/push-registration.ts`

```ts
export type PushSupport =
  | { kind: "unsupported" }                        // no Notification / PushManager / serviceWorker
  | { kind: "needs-install" }                      // iOS / iPadOS, not launched from the home screen
  | { kind: "available"; permission: NotificationPermission };

export function pushSupport(): PushSupport;
/** Asks the permission — MUST be called inside a user gesture (iOS) — and returns the FCM token, obtained through
 *  the application's OWN worker registration (no second worker). */
export function registerPush(config: FcmWebConfig, submit: (token: string) => Promise<void>): Promise<"on" | "denied">;
/** Re-sends the current token at every start while this device's push subscription exists, whatever the permission
 *  reads — iOS may read `default` (#8269), and `unregisterPush` leaves it granted (Firebase's refresh). */
export function refreshPush(config: FcmWebConfig, submit: (token: string) => Promise<void>): Promise<void>;
export function unregisterPush(revoke: (token: string) => Promise<void>): Promise<void>;
```

`FcmWebConfig` is the Web app's public `firebaseConfig` and the VAPID public key — not secrets (Firebase's own
statement); served to the page by K5 from the configuration, the same on every environment if one project serves
them all (F-2 = A: one Firebase project serves the three).

---

## 4. Tests

**Unit, never a live call:**

- `FcmSender` over a fake session, on the documented answers recorded as fixtures
  (`docs/reference/_samples/fcm/`): 200, `UNREGISTERED` 404, `SENDER_ID_MISMATCH` 403, `INVALID_ARGUMENT` 400,
  `QUOTA_EXCEEDED` 429 with `Retry-After`, `UNAVAILABLE` 503, `INTERNAL` 500, `THIRD_PARTY_AUTH_ERROR` 401, a timeout
  → each to its `PushOutcome`; the request: URL with the project id, `Authorization: Bearer`, a data-only `webpush`
  body with `TTL` / `Urgency`, `validate_only` when asked; the access token minted from a TEST service-account file
  generated for the suite (a throwaway RSA key), with the token endpoint faked.
- **No secret leaks**: over every failure path, no log record, exception text or `repr` carries the device token, the
  access token or the private key.
- `SqlitePushSubscriptionStore` on `:memory:`: upsert creates, re-upsert refreshes and moves a token to the presenting
  account, revoke excludes from `live_for`, `revoke_stale` at 270 days, `record` counts consecutive failures.
- `PushDispatcher` with a fake sender: fan-out to every live subscription; `TOKEN_DEAD` revokes; `MISCONFIGURED`
  stops the fan-out and sets `misconfigured`; nothing retried inside.
- The maquette (vitest): the worker's text composition from a catalogue (`{{param}}` filled, unknown code → generic
  line), the link guard (same-origin path or `/`); `pushSupport()` under each environment (no API; iOS not
  standalone; available with each permission); `registerPush` passes the application's registration and never
  creates a second worker.

**Manual E2E, by the operator's hand** (he owns the Google account; no agent reads a credential):

1. **Credentials** (after phase 1): `! python scripts/fcm-probe.py --validate-only` — mints an access token from his
   service-account file and sends a `validate_only` message to a placeholder token: `INVALID_ARGUMENT` on the token
   (expected — a credential fault answers 401 / 403 before the token is read) proves the project, the key and the API
   are right; `MISCONFIGURED` names what is not.
2. **Delivery** (after phase 3 AND the opt-in surface drawn and bound): on his Android phone and on his iPhone (iOS ≥
   16.4, the PWA added to the home screen), turn notifications on; `! python scripts/fcm-probe.py --account <id>`
   sends one test code to both; he reads one notification on each, taps it, lands in the application. With
   `--record`, the probe writes the received envelope's shape (the worker logs it once, redacted) to
   `docs/reference/_samples/fcm/push-envelope.json`.

---

## 5. DECIDED — his rulings of 2026-10-01 (decision round 4)

**F-1 — The Firebase project: the steps HE takes, with his Google account** (nothing is assumed created):

1. Firebase console → « Add project » (name e.g. « TorrentMate »); Google Analytics NOT needed.
2. In the project → « Add app » → **Web**; copy the `firebaseConfig` (`apiKey`, `authDomain`, `projectId`,
   `messagingSenderId`, `appId`) — public values.
3. Project settings → **Cloud Messaging** → « Web configuration » → « Generate key pair »; copy the PUBLIC key
   (the VAPID key) — public.
4. Project settings → **Service accounts** → « Generate new private key »; a JSON file — the ONE secret. Store it as
   `~/.torrentmate/secrets/fcm-service-account.json`, mode 600, outside every checkout; `.env` gets
   `FCM_SERVICE_ACCOUNT_FILE=<that path>`.
5. Check that « Firebase Cloud Messaging API (V1) » is enabled for the project in Google Cloud (it usually is).
6. FCM has no per-message price (to confirm on `https://firebase.google.com/pricing` when he creates it).

The public values go into the configuration overlay (`push.fcm.web` — a new key, written at K5), never into git with
anything secret.

**F-1 stays his hand, as written above** — the project, the web app, the VAPID key pair and the service-account file are
created by him; no agent creates, reads or holds any of them.

**F-2 = A** — **one Firebase project for dev, staging and prod**: one service account, one web config; the three are
three origins, so their tokens never mix, and each environment's `app` file holds its own subscriptions (Q2).

**F-3 — BOTH surfaces**, his words « A l'ouverture (installation ?) de la PWA », then « proposition à l'ouverture et
aussi via profil »:

- an offer « Activer les notifications sur cet appareil » at the opening of the INSTALLED PWA — tapped, it is the user
  gesture iOS needs for the permission;
- the **Profil** per-device line « Notifications sur cet appareil », with the four states of § 3.6 (iOS: « à installer
  d'abord sur l'écran d'accueil »).

Both are drawn in the maquette first; this brick builds neither — `lib/push-registration.ts` serves both from one
gesture-bound `registerPush`.

**F-4 = A** — **every account holding `trackers.view` receives the ratio alert** (K5 applies it).

---

## 6. Phases

| Phase | What | Done when | Proving command |
| --- | --- | --- | --- |
| 1 | **The sender** — `google-auth` declared, `FcmSender`, `PushMessage`, `PushOutcome`, the fixtures, `scripts/fcm-probe.py` (`--validate-only`), `docs/reference/fcm-api.md` | every outcome mapped; the leak suite green; then HIS probe answers `INVALID_ARGUMENT` on the placeholder token | `pytest tests/unit/test_fcm_sender.py -q`; `! python scripts/fcm-probe.py --validate-only` (his hand, after F-1) |
| 2 | **The store and the dispatcher** — DDL, protocol, SQLite implementation, `PushDispatcher` | the store and fan-out suites green on `:memory:`; the DDL handed to K0's `app.db` baseline (a line in the brief's K0 row) | `pytest tests/unit/test_push_store.py tests/unit/test_push_dispatch.py -q` |
| 3 | **The device side** — `sw.js`'s two listeners, the `__PUSH_TEXTS__` substitution and the `push` namespace in `fr.json` holding its GENERIC line only (each code's words arrive with K5), `lib/push-registration.ts` with the SDK version PINNED and the token API (`getToken` vs `register` / installation id) settled against `messages:send` | typecheck and the vitest suites green; the build refuses a `sw.js` with an unsubstituted `__PUSH_TEXTS__` | `cd frontend/maquette/design && npm run typecheck && npm test` |
| — | **Delivery E2E** — after phase 3 and the opt-in surface (F-3) bound by K5 | one notification read and tapped on Android and on iOS (installed PWA) | `! python scripts/fcm-probe.py --account <id> --record` |

Gate per phase: `make lint`; the maquette's typecheck and tests for phase 3; pytest of the touched modules. Phase 1's
proof by his hand waits F-1; phases 2 and 3 wait nothing; the delivery E2E waits the two F-3 surfaces, drawn and bound.
