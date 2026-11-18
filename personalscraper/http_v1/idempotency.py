"""v1's ``Idempotency-Key``: a replayed write answers its first answer and applies nothing.

Two halves, both installed by ``create_v1_app`` and never by a route:

- :func:`idempotency_guard`, a dependency every mutating operation that signs an account in
  carries right after the perimeter (``include_v1_router``). It needs the account the
  perimeter resolved — a key is scoped to (account, key, method and path) — so it cannot
  run before the route matches. It claims the key, or raises :class:`IdempotentReplay`,
  answered with the stored answer before the route runs.
- :class:`IdempotencyRecorder`, a pure ASGI layer outside ``ProblemOnCrash``: it reads the
  answer of a request that claimed a key and stores it before it leaves when it will not
  change (a success or a final refusal) — or releases the claim, so the retry applies.

A public operation (the sign-in doors ``signIn``, ``signInWithPlex``, ``startPlexSignIn``) is
not guarded: no account scopes its key, its answer's worth is the session cookie, which is
never stored, and the client never holds one offline.
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import FastAPI, Header, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.errors import AppInternalError, RefusalCode
from personalscraper.app.idempotency.service import Claimed, IdempotencyService, Replay, is_kept
from personalscraper.logger import get_logger

log = get_logger("http_v1.idempotency")

#: The request header a client names one write by.
IDEMPOTENCY_HEADER: Final = "Idempotency-Key"

#: The longest key accepted; a UUID is 36 characters.
_KEY_MAX_LENGTH: Final = 255

#: The request-state key a claim waits under for :class:`IdempotencyRecorder`.
_CLAIM_STATE_KEY: Final = "idempotency_claim"

_HEADER_DESCRIPTION: Final = (
    "Names this write. Sent again with the same request, the first answer is answered and "
    "nothing is applied again; sent with another request, it is refused 409 `request.key_reused`; "
    "sent while the first is still running, it is refused 409 `request.in_progress`. "
    "Kept 24 hours, per signed-in account. Only a success or a final refusal "
    "(400, 404, 405, 409, 410, 415, 422) is kept; any other answer keeps nothing and the retry applies. "
    "The public sign-in doors take none: they sign no account in, and are never held offline."
)


class IdempotentReplay(Exception):
    """A key's stored answer, raised by the guard to answer it instead of the route.

    Attributes:
        replay: The stored answer.
    """

    def __init__(self, replay: Replay) -> None:
        """Carry the stored answer.

        Args:
            replay: The stored answer.
        """
        super().__init__("idempotent replay")
        self.replay = replay


async def idempotency_guard(
    request: Request,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias=IDEMPOTENCY_HEADER,
            min_length=1,
            max_length=_KEY_MAX_LENGTH,
            pattern=r"^[\x21-\x7e]+$",
            description=_HEADER_DESCRIPTION,
        ),
    ] = None,
) -> None:
    """Claim the request's key, or answer its first answer.

    A request with no key goes through untouched.

    Args:
        request: The incoming request, already through the perimeter.
        idempotency_key: The ``Idempotency-Key`` header, if sent.

    Raises:
        IdempotentReplay: The same request was answered: its answer is answered again.
        AppConflict: ``request.key_reused`` or ``request.in_progress`` (from the service).
        AppInternalError: ``internal`` — no account was resolved: the guard sits on an
            operation that signs none in, a server defect.
    """
    if idempotency_key is None:
        return
    signed_in = getattr(request.state, "actor", None)
    if not isinstance(signed_in, Actor):
        raise AppInternalError("An idempotency key needs a signed-in account.", code=RefusalCode.INTERNAL)
    service: IdempotencyService = request.app.state.services.idempotency
    path = request.scope["path"]
    fingerprint = service.fingerprint(request.method, path, request.url.query, await request.body())
    outcome = await run_in_threadpool(
        service.claim, signed_in.account_id, idempotency_key, f"{request.method} {path}", fingerprint
    )
    if isinstance(outcome, Replay):
        raise IdempotentReplay(outcome)
    setattr(request.state, _CLAIM_STATE_KEY, outcome)


def install_idempotency(app: FastAPI) -> None:
    """Answer a replay with its stored answer, and record every claimed request's answer.

    Call it after ``ProblemOnCrash`` is added, so the recorder sits outside it and stores
    the 500 it answers as a released claim.

    Args:
        app: The v1 sub-application.
    """

    @app.exception_handler(IdempotentReplay)
    async def _replay(_: Request, exc: IdempotentReplay) -> Response:
        """Answer the stored answer.

        Args:
            _: The replayed request (unused).
            exc: The replay.

        Returns:
            The stored status, body and ``Content-Type``.
        """
        stored = exc.replay
        return Response(content=stored.body, status_code=stored.status, media_type=stored.content_type)

    app.add_middleware(IdempotencyRecorder, service=app.state.services.idempotency)


def _content_type(start: Message) -> str | None:
    """Read the ``Content-Type`` of a response's start.

    Args:
        start: The ``http.response.start`` message.

    Returns:
        Its value, or ``None`` when the answer has none.
    """
    for name, value in start.get("headers", []):
        if name.lower() == b"content-type":
            return str(value.decode("latin-1"))
    return None


class IdempotencyRecorder:
    """Pure ASGI: stores the answer of a request that claimed a key, or releases its claim.

    The claim is settled only on a complete answer, and the answer always leaves:

    - a success or a final refusal is stored before it leaves, so a crash once the client
      has it never leaves the claim to be applied again;
    - any other answer (401, 403, 408, 423, 429: nothing applied; a 5xx: taken as rolled
      back) releases the claim, so the retry applies;
    - a storage failure while settling is logged ``error`` and the answer forwarded anyway:
      the claim stays running, and the take-over arbitrates;
    - no complete answer (a crash mid-answer, a cancel at shutdown) settles nothing: the
      route may have committed, so the claim stays running for the take-over.

    Residuals, accepted and pinned by tests: a 5xx raised after the write committed
    releases the claim and the retry applies the write again; a request still running past
    the service's pending limit (300 s) is taken over and may be applied twice.
    """

    def __init__(self, app: ASGIApp, *, service: IdempotencyService) -> None:
        """Wrap the application.

        Args:
            app: The inner ASGI application.
            service: The idempotency service the claims were made through.
        """
        self.app = app
        self._service = service

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the inner application, keeping the answer of a claimed request.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # The dict ``request.state`` writes into, created here so the guard's claim reaches it.
        state: dict[str, object] = scope.setdefault("state", {})
        held: list[Message] = []
        body = bytearray()
        settled = False

        async def recording_send(message: Message) -> None:
            """Forward one message; a claimed request's answer is settled BEFORE it leaves.

            Args:
                message: The ASGI message.
            """
            nonlocal settled
            claim = state.get(_CLAIM_STATE_KEY)
            if not isinstance(claim, Claimed) or settled:
                await send(message)
                return
            held.append(message)
            if message["type"] != "http.response.body":
                return
            body.extend(message.get("body", b""))
            if message.get("more_body", False):
                return
            start = held[0]
            await self._settle(claim, start["status"], bytes(body), _content_type(start))
            settled = True
            for kept in held:
                await send(kept)

        await self.app(scope, receive, recording_send)

    async def _settle(self, claim: Claimed, status: int, body: bytes, content_type: str | None) -> None:
        """Store a claimed request's answer, or release its claim when the answer may change.

        Never raises: a storage failure is logged and the claim left running, so the answer
        still leaves and the write, which may have committed, is never released to a retry.

        Args:
            claim: The request's claim.
            status: The answer's status.
            body: The answer's body.
            content_type: The answer's ``Content-Type``, if any.
        """
        kept = is_kept(status)
        try:
            if kept:
                await run_in_threadpool(self._service.complete, claim, status, body, content_type)
            else:
                await run_in_threadpool(self._service.release, claim)
        except Exception:
            log.error("idempotency_store_failed", status=status, kept=kept, exc_info=True)
