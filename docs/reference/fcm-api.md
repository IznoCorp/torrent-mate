# Firebase Cloud Messaging (HTTP v1) — Reference

The push channel of the ratio alert (Q10, 2026-10-01): one data-only web-push message to one
browser of one device, Android and iOS (the installed PWA). Client:
`personalscraper/api/notify/fcm.py` (`FcmSender`). Design: `docs/features/backend-bricks/fcm-push/DESIGN.md`.
Nothing here was read from a live call: every fact is Firebase's or WebKit's public documentation,
cited per section; the operator's probe confirms the credential path once the project exists.

## Table of Contents

- [Authentication](#authentication)
- [Send endpoint](#send-endpoint)
- [Message shape](#message-shape)
- [Error handling](#error-handling)
- [Tokens and their lifetime](#tokens-and-their-lifetime)
- [The web client](#the-web-client)
- [iOS](#ios)
- [The worker](#the-worker)
- [The dispatcher](#the-dispatcher)
- [Setup — the operator's steps](#setup--the-operators-steps)
- [The probe](#the-probe)
- [Test samples](#test-samples)

## Authentication

Source: `https://firebase.google.com/docs/cloud-messaging/send/v1-api` (« Authorize send requests »).

- A **service account** of the Firebase project, as a JSON file (« Project settings → Service
  accounts → Generate new private key »). It is the ONE secret: `FCM_SERVICE_ACCOUNT_FILE` in `.env`
  names its path (`~/.torrentmate/secrets/fcm-service-account.json`, mode 600, outside every checkout).
- An OAuth 2.0 **access token** is minted from it with the scope
  `https://www.googleapis.com/auth/firebase.messaging` — by `google-auth`
  (`service_account.Credentials.from_service_account_file(...).refresh(Request(...))`), valid about an
  hour, reused until it expires. `firebase-admin` is NOT used: it pulls gRPC, Firestore and Storage
  for one HTTP call.
- Sent as `Authorization: Bearer <access token>`.
- The legacy server-key API is gone (2024).

**Secrets never appear anywhere** (the `api/plex.py` discipline): the access token in the header
only, the device token in the JSON body only; failures log the exception TYPE and FCM's
`errorCode`, never the exception, `exc_info` or a body; no redirect followed. google-auth's
`Request` closes its session when collected — the sender holds ONE for its lifetime, else each
refresh would close the session the sends use.

## Send endpoint

```
POST https://fcm.googleapis.com/v1/projects/{projectId}/messages:send
Authorization: Bearer <access token>
Content-Type: application/json

{"message": {...}, "validate_only": true?}
```

`projectId` is read from the service-account file (`project_id`). `validate_only` checks the request
without delivering it (the probe's credential check). 200 answers `{"name": "projects/…/messages/…"}`.

## Message shape

Source: `https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages`.

The application sends a **data-only** web-push message — the service worker, not the browser,
composes what is shown, from the catalogue of the recipient's language, `fr.json` or `en.json`
(no sentence on the wire):

```json
{
  "message": {
    "token": "<registration token>",
    "webpush": {
      "headers": {"TTL": "86400", "Urgency": "normal"},
      "data": {"code": "tracker.ratio_low", "params": "{\"ratio\": 1.12, \"tracker\": \"c411\"}",
               "link": "/trackers/c411", "tag": "ratio-c411", "language": "fr"}
    }
  }
}
```

- every `data` value is a STRING (FCM's rule) — `params` is JSON-encoded;
- `language` is the RECIPIENT ACCOUNT's language (`Account.language`, `"fr"` or `"en"`), filled by
  the server per account (FG-2 A; the contract's `PushCode`): the worker words the code in it, and in
  English when it is absent or names a language the interface does not speak (OPEN-2 B). The
  backend does not fill it yet — that is the push-language phase;
- `link` is a same-origin path (`PushMessage` refuses anything else); the worker's
  `notificationclick` opens or focuses it; `fcm_options.link` is NOT used (it wants an absolute HTTPS
  URL and applies only to notification messages);
- `TTL` (seconds FCM keeps it for an offline device) and `Urgency` (`normal` / `high`) are Web Push
  headers.

## Error handling

Source: `https://firebase.google.com/docs/cloud-messaging/error-codes`,
`https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode`.

An error answer is `{"error": {"code", "message", "status", "details": [...]}}`; an FCM-specific
failure carries a detail of `@type` `type.googleapis.com/google.firebase.fcm.v1.FcmError` with
`errorCode`. The sender reads `errorCode`, else `status`, else the HTTP status:

| errorCode / status | HTTP | `PushOutcome` | What the caller does |
| --- | --- | --- | --- |
| — | 200 | `delivered` | — |
| `UNREGISTERED` | 404 | `token_dead` | revoke the subscription |
| `SENDER_ID_MISMATCH` | 403 | `misconfigured` | stop the fan-out, revoke NOTHING — one project serves every environment (F-2), so another sender means our service account is the wrong project, not a dead token |
| `INVALID_ARGUMENT` | 400 | `rejected` | keep it, count it — the payload or the token's format |
| any 429: `QUOTA_EXCEEDED`, `RESOURCE_EXHAUSTED`, no code | 429 | `quota_exceeded` | the PROJECT's quota: stop the fan-out, back off ≥ 60 s (`Retry-After` when longer) |
| `UNAVAILABLE` / `INTERNAL` | 503 / 500 | `retry_later` | re-send after `Retry-After` |
| `THIRD_PARTY_AUTH_ERROR` | 401 | `misconfigured` | the project's web-push credentials (VAPID / APNs) |
| `UNAUTHENTICATED` / `PERMISSION_DENIED` / `NOT_FOUND` (no `errorCode`) | 401 / 403 / 404 | `misconfigured` | OUR credentials or project id — never the device's token |
| a refused token grant (`invalid_grant`), an unreadable file | — | `misconfigured` | Système says the channel is broken |
| no answer, a timeout | — | `unreachable` | the caller decides |

A 404 is a dead TOKEN only when FCM's own `errorCode` says so. The quota is decided once, in
`classify`, on the 429 itself; the dispatcher reads the outcome, never an error string.
`Retry-After` is read as seconds or as an HTTP date; a non-finite value (`inf`, `1e400`, `nan`) is
no answer, and a finite one is clamped to a day (`RETRY_AFTER_CEILING_SECONDS`: the default TTL of
a message — FCM drops it by then, so a longer wait is never useful). The sender retries nothing
(NE-DOIT-PAS-8); the one retry left is google-auth's, on a transient token-grant failure (5xx, 408,
429, `server_error`: 3 attempts with exponential back-off), each attempt bounded by the sender's
`_TIMEOUT` instead of google-auth's 120 s default.

## Tokens and their lifetime

Source: `https://firebase.google.com/docs/cloud-messaging/manage-tokens`.

- A registration token identifies ONE browser on ONE device, for ONE origin — dev, staging and prod
  hold different tokens for the same phone (one Firebase project serves the three, F-2 = A).
- A token idle 270 days expires; Firebase recommends a monthly refresh and a timestamp per upload.
  The client re-sends its token at every start; the store upserts it.

## The web client

Source: `https://firebase.google.com/docs/cloud-messaging/js/client`.

- HTTPS only; a « Web Push certificate » (VAPID key pair) generated in the console, its PUBLIC key
  given to the SDK; the web app's `firebaseConfig` and the VAPID public key are public values.
- The SDK registers its own `firebase-messaging-sw.js` by default; the application passes its OWN
  worker registration instead (`serviceWorkerRegistration`) — one worker, no second one.
- The permission is asked from a direct user gesture only.
- **The token API, settled against the pinned SDK** (`firebase` 12.19.0, exact pin in
  `webui/design/package.json`): `getToken` is marked deprecated there in favour of
  `register` + `onRegistered`, which deliver a Firebase Installation id (FID), the SDK noting that
  « the backend send API supports FID as a target ». The HTTP v1 reference documents `message.token`
  as an FCM REGISTRATION TOKEN, and that is what `getToken` returns — so the client uses `getToken`.
  The switch to the FID, once Firebase documents it as a v1 target, is confined to
  `src/lib/push-registration.ts`. The SDK is imported lazily, on the device that turns
  notifications on.
- `webui/design/src/lib/push-registration.ts`: `pushSupport()` (`unsupported`,
  `needs-install` — told BEFORE the API check, since a Safari tab on iOS defines no push API —,
  `available` with the permission), `registerPush(config, submit)` (asks first, before any await),
  `refreshPush(config, submit)` (every start, never asks; it re-sends the token only while this
  device's push subscription exists — `registration.pushManager.getSubscription()` not null —,
  WHATEVER the permission reads: `unregisterPush` removes the subscription and leaves the permission
  granted, so a device turned off stays off, and iOS may read `default` with the subscription still
  there), `unregisterPush(config, revoke)` (the server forgets the token, then the SDK deletes it — the
  configuration is needed to reach the SDK's messaging instance, which the DESIGN's signature omitted).
- `deleteToken` takes no registration and, on a messaging instance none is bound to, registers the
  default `firebase-messaging-sw.js`: the client's `forget` first binds the application's registration
  with `getToken` (the SDK's only public way; an existing token is read back, none minted).

## iOS

Source: `https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/`,
`https://firebase.blog/posts/2023/08/fcm-for-safari/`.

- iOS / iPadOS ≥ 16.4, ONLY for a web app added to the home screen with `display: standalone`
  (the manifest of `webui/installable.py` declares it); no Apple developer account.
- The permission from a direct user gesture — the opening offer's tap (F-3).
- Every push must SHOW a notification: the worker never stays silent (an unknown code shows the
  catalogue's generic line).
- The permission may read `default` after a reload (`firebase-js-sdk#8269`): the client re-sends its
  token at every start when the device's push subscription exists, whatever the permission reads; the
  server upserts.

## The worker

`webui/design/sw.js` — `push` composes the notification from the `push` namespace of
`fr.json` and `en.json` (both written into the worker at build time at `__PUSH_TEXTS__`, by
language; the build refuses a catalogue without `push.generic` and a worker where a placeholder
survived — `worker-source.mjs`): the catalogue the message's `language` names, else English
(`PUSH_DEFAULT_LANGUAGE`); the code looked up in it as a dotted path, `{{param}}` filled from the
JSON-encoded `params`, that language's generic line for anything it cannot word. `notificationclick` focuses an open window of the application and sends it
to the message's link, or opens one there; any link that is not a same-origin path opens `/`.

## The dispatcher

`personalscraper/push/dispatch.py` — `PushDispatcher.notify_account(account_id, message)`; its
`DispatchReport` adds `retry_after_seconds` (the longest back-off a deferral asked for) to the
DESIGN's fields, since the re-send is the caller's. A `misconfigured` answer and a
`quota_exceeded` one stop the fan-out; the store is `personalscraper/push/store.py`, its DDL adopted
by K0's `app` baseline.

## Setup — the operator's steps

F-1, his hand (nothing is assumed created): the Firebase project; a Web app (copy `firebaseConfig`);
Cloud Messaging → Web configuration → « Generate key pair » (copy the public key); Service accounts →
« Generate new private key » (the JSON file, mode 600, `FCM_SERVICE_ACCOUNT_FILE`); check that
« Firebase Cloud Messaging API (V1) » is enabled. FCM has no per-message price (to confirm at
`https://firebase.google.com/pricing` when he creates it).

## The probe

`! python scripts/fcm-probe.py --validate-only` — mints an access token from his file and sends a
`validate_only` message to a placeholder token. `INVALID_ARGUMENT` is the EXPECTED answer (a credential
fault answers 401 / 403 before the token is read); `misconfigured: <code>` names what is wrong. It
prints codes only.

## Test samples

`docs/reference/_samples/fcm/` — one file per documented answer (`{status, headers, body}`),
HAND-WRITTEN from the error-code pages above (no project existed); see its `README.md`. Suite:
`tests/unit/test_fcm_sender.py` (every outcome, the request's shape, the grant, the leak suite on the
production console renderer, the probe's verdict).
