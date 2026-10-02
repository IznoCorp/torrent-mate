# FCM HTTP v1 answers — hand-written from Firebase's documentation

Not captured: no Firebase project existed when these were written. Each file is one answer of
`POST https://fcm.googleapis.com/v1/projects/{projectId}/messages:send` as Firebase documents it
(`https://firebase.google.com/docs/cloud-messaging/error-codes`,
`https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode`): the HTTP status, the headers
the sender reads (`Retry-After`), and the body — `error.status` and, for an FCM-specific failure,
the `google.firebase.fcm.v1.FcmError` detail carrying `errorCode`. The `message` texts are
illustrative; the sender never reads them.

`permission-denied-403.json` is a 403 WITHOUT an FCM `errorCode` — a credential that lacks the
messaging permission: our configuration, not the device token.

The operator's `scripts/fcm-probe.py --validate-only` (after the Firebase project exists) checks
the real shape of the `INVALID_ARGUMENT` answer; a live envelope replaces a file here only from
that run.
