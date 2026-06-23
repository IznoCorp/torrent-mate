"""``kanban serve`` — the hardened GitHub webhook receiver (ingress-multiproject §4).

KEY DECISION (DESIGN §0/§4.4): the receiver does NOT synthesize Transitions or a fake
``BoardSnapshot``. GitHub ``projects_v2_item`` payloads do not carry the Status column reliably, and
the engine's ``diff(persisted, snapshot)`` is already the authoritative "what moved" computation. So
the receiver only (a) verifies the HMAC, (b) identifies WHICH project the event hit
(``project_node_id`` → :func:`~kanbanmate.core.registry_resolve.resolve_by_project_id`), and (c)
bumps that runtime root's daemon-wake nudge sentinel (the EXACT
:meth:`~kanbanmate.adapters.store.fs_intents.IntentsStateMixin.nudge_daemon` mechanism the cockpit
intent queue uses → the daemon's interruptible sleep early-returns). The daemon then runs its NORMAL
tick. This is idempotent by construction (a webhook nudge and the slow safety sweep converge on the
same diff against persisted state — no double-fire) and reuses the proven one-writer model (the
daemon is the sole board writer; the receiver is stateless and trivially restartable).

Hardening (CLAUDE.md HTTP-receiver rules / DESIGN §4.2):

* **Bounded body read** — ``Content-Length`` required; absent or ``> MAX_BODY`` (1 MiB) → ``413``;
  chunked transfer rejected (``411``) — GitHub always sends ``Content-Length``.
* **Socket timeouts** — ``server.timeout`` + a per-connection read timeout, so a slow-loris cannot
  hang a worker (the same connect+read-timeout discipline the urllib GitHub client enforces).
* **Method/path allow-list** — only ``POST /webhook`` + ``GET /healthz``; everything else 404/405.
* **HMAC verify FIRST** — on the RAW bytes BEFORE any JSON parse (:func:`verify_signature`); a
  missing/invalid signature → ``401`` with NO nudge.
* **Loopback bind by default** — ``127.0.0.1`` (the operator fronts TLS via their reverse proxy);
  ``--host 0.0.0.0`` is opt-in. No in-process TLS.
* **Non-root + unprivileged port** — refuse to run as root; default port 8765; refuse a privileged
  port (< 1024).
* **No reflection** — fixed response bodies only; request bytes are never echoed.

Layering: ``http`` is a top entrypoint (DESIGN §4.1) — it may import ``app`` / ``adapters`` / ``core``
but not the sibling entrypoints. ``core`` stays pure.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kanbanmate.core.webhook_sig import SIGNATURE_HEADER, verify_signature
from kanbanmate.http.webhook_ingest import IngestOutcome, ingest_external_move  # keel step 5 (B)

logger = logging.getLogger(__name__)

# The default loopback bind + unprivileged port (DESIGN §4.2). The operator fronts TLS + public
# exposure with their existing reverse proxy; ``--host 0.0.0.0`` is opt-in and documented.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# The webhook-secret filename under the runtime root (mode 0600; never in git). The receiver REFUSES
# to start without it — an unsigned-accepting receiver is a security hole (DESIGN §4.3).
WEBHOOK_SECRET_FILENAME = "webhook_secret"

# Max accepted request body (1 MiB). A larger Content-Length → 413 (GitHub payloads are well under
# this; the bound stops a memory-exhaustion body).
MAX_BODY_BYTES = 1 * 1024 * 1024

# Per-connection socket timeout (seconds) — the slow-loris guard. A connection that does not finish
# sending its body within this window is dropped, so one slow client cannot pin a worker thread.
SOCKET_TIMEOUT_SECONDS = 15.0

# The only GitHub event type the receiver acts on. ``ping`` (the setup handshake) → 200; anything
# else → 204 (acknowledged, ignored — never 4xx an event class so GitHub does not disable the hook).
ACTED_EVENT = "projects_v2_item"

# The method/path allow-list (DESIGN §4.2): each KNOWN path maps to the set of methods it accepts.
# A request to an UNKNOWN path → 404; a known path with a DISALLOWED method → 405 (matching DESIGN
# §4.2 — distinct from the stdlib's default 501 for an unrecognised verb). One source of truth so
# do_GET/do_POST and the other-verb catch-all all read the same map.
_ALLOWED_METHODS: dict[str, frozenset[str]] = {
    "/webhook": frozenset({"POST"}),
    "/healthz": frozenset({"GET"}),
}


class WebhookSecretMissingError(RuntimeError):
    """Raised when ``<root>/webhook_secret`` is absent / unusable at ``serve`` start (DESIGN §4.3).

    The receiver refuses to start without a REAL secret: an unsigned-accepting receiver would let any
    caller nudge the daemon, and a PLACEHOLDER/empty/comment-only file is just as dangerous (its
    bytes are public in the source, so it is a publicly-known HMAC key — #3). The operator pastes a
    strong random secret (``kanban install``/``init`` seed an unusable placeholder) and sets the SAME
    value on the GitHub org/repo webhook.
    """


class PrivilegedPortError(RuntimeError):
    """Raised when ``serve`` is asked to bind a privileged port (< 1024) (DESIGN §4.2 non-root)."""


class RootPrivilegeError(RuntimeError):
    """Raised when ``serve`` is invoked as root (``uid 0``) (DESIGN §4.2: the daemon runs non-root)."""


@dataclass(frozen=True)
class WebhookConfig:
    """The receiver's runtime configuration (resolved once at ``serve`` start).

    Attributes:
        root: The runtime root holding ``projects.json`` + ``webhook_secret`` + ``intents/.nudge``.
        secret: The shared webhook secret bytes (loaded from ``<root>/webhook_secret``).
        host: The bind host (loopback by default).
        port: The bind port (unprivileged; 8765 default).
    """

    root: Path
    secret: bytes
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


def _extract_secret(raw: bytes) -> bytes:
    """Extract the REAL secret from the file bytes, ignoring comment lines + whitespace (#3).

    The seeded skeleton is a COMMENT-ONLY block (every line starts with ``#``) whose exact bytes are
    public in the source — accepting it would run the receiver with a publicly-known HMAC key. This
    drops every full-line comment (a line whose first non-whitespace char is ``#``) and surrounding
    whitespace; what survives is the operator's pasted secret. A file that is empty / all-whitespace
    / comment-only yields ``b""`` (the caller refuses to start). A real secret typically sits on its
    own line; internal whitespace WITHIN a non-comment line is preserved (only the line ends + the
    overall surrounding whitespace are stripped).

    Args:
        raw: The raw file bytes.

    Returns:
        The extracted secret bytes (``b""`` when nothing real survives the comment/whitespace strip).
    """
    real_lines = [line for line in raw.splitlines() if not line.lstrip().startswith(b"#")]
    return b"\n".join(real_lines).strip()


def load_webhook_secret(root: Path) -> bytes:
    """Load the shared webhook secret from ``<root>/webhook_secret`` (fail-loud when absent/unusable).

    Refuses (raises) when the file is absent OR holds no REAL secret — empty, all-whitespace, or the
    COMMENT-ONLY seeded placeholder whose bytes are public in the source (#3). Comment lines (first
    non-whitespace char ``#``) and surrounding whitespace are stripped; whatever real bytes remain
    are the secret.

    Args:
        root: The runtime root the secret file lives under.

    Returns:
        The real secret bytes (comment lines + surrounding whitespace stripped).

    Raises:
        WebhookSecretMissingError: When the secret file is absent, OR contains no real secret (empty
            / whitespace-only / comment-only placeholder) — the receiver refuses to start.
    """
    path = root / WEBHOOK_SECRET_FILENAME
    if not path.exists():
        raise WebhookSecretMissingError(
            f"no webhook secret at {path}: `kanban serve` refuses to start without one "
            "(an unsigned-accepting receiver is a security hole). Seed it (0600) and set the SAME "
            "value on the GitHub org/repo webhook."
        )
    secret = _extract_secret(path.read_bytes())
    if not secret:
        # Empty / whitespace-only / the seeded comment-only placeholder → a publicly-known key (#3).
        raise WebhookSecretMissingError(
            f"webhook secret at {path} is empty or still the placeholder: `kanban serve` refuses to "
            "start with a publicly-known HMAC key. Paste a strong random secret (0600) and set the "
            "SAME value on the GitHub org/repo webhook."
        )
    return secret


def project_id_from_payload(payload: dict[str, Any]) -> str | None:
    """Extract the Project v2 node id from a ``projects_v2_item`` webhook payload (best-effort).

    GitHub nests the project node id under ``projects_v2_item.project_node_id``. This reads it
    defensively (any shape mismatch → ``None``, so a malformed payload is a no-op, never a crash).

    Args:
        payload: The decoded webhook JSON body.

    Returns:
        The ``project_node_id`` string when present, else ``None``.
    """
    item = payload.get("projects_v2_item")
    if isinstance(item, dict):
        pid = item.get("project_node_id")
        if isinstance(pid, str) and pid:
            return pid
    # Some payload shapes carry it at the top level — accept that as a fallback.
    top = payload.get("project_node_id")
    return top if isinstance(top, str) and top else None


def _resolve_entry(config: WebhookConfig, project_id: str | None) -> Any | None:
    """Return the registry entry for ``project_id``, or ``None`` for an unmanaged/absent project.

    Resolves the registry entry via :func:`~kanbanmate.core.registry_resolve.resolve_by_project_id`.
    An UNKNOWN project (one this daemon does not manage) → ``None`` (the caller responds ``202`` and
    does NOT nudge / ingest — we never 4xx a board we do not manage, so GitHub keeps the hook
    enabled). A KNOWN project → its :class:`~kanbanmate.cli.init.ProjectEntry`, which the caller uses
    both to INGEST the external Status into ``board.json`` (keel step 5 B) and to nudge the daemon
    (the nudge sentinel is DAEMON-LEVEL — one daemon, one wake — so any managed project's event wakes
    the single sweep, which re-probes all boards cheaply and snapshots only the changed one).

    Args:
        config: The receiver config (carries the runtime root + the registry location).
        project_id: The project node id extracted from the payload (``None`` when absent).

    Returns:
        The resolved registry entry, or ``None`` when the project is unknown / absent.
    """
    if project_id is None:
        return None
    # Lazy imports: keep the module import surface lean (the registry loader is in the cli layer,
    # which ``http`` may import as a top entrypoint).
    from kanbanmate.cli.init import _load_registry, _projects_path
    from kanbanmate.core.registry_resolve import resolve_by_project_id

    projects_path = _projects_path(config.root)
    registry = _load_registry(projects_path) if projects_path.exists() else {}
    return resolve_by_project_id(registry, project_id)


def nudge_root(root: Path) -> None:
    """Bump the runtime root's daemon-wake nudge sentinel (the cockpit ``nudge_daemon`` mechanism).

    Builds an :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` at the runtime root purely to
    reuse its atomic, fail-soft ``nudge_daemon`` (which bumps ``<root>/intents/.nudge`` — the SAME
    sentinel the daemon's interruptible sleep watches). The daemon then runs its normal tick.

    Args:
        root: The runtime root whose nudge sentinel to bump.
    """
    from kanbanmate.adapters.store.fs_store import FsStateStore

    FsStateStore(root).nudge_daemon()


def make_handler(
    config: WebhookConfig,
    *,
    nudge: Callable[[Path], None] = nudge_root,
    ingest: Callable[[Path, Any, dict[str, Any]], IngestOutcome] = ingest_external_move,
) -> type[BaseHTTPRequestHandler]:
    """Build the :class:`BaseHTTPRequestHandler` subclass closed over ``config`` (testable factory).

    The handler is defined inside this factory so it captures the resolved ``config`` + the injected
    ``nudge`` / ``ingest`` callables WITHOUT module-global state — so tests drive the handler directly
    (a fake request) with fakes, and a real server gets the production callables. All hardening
    (bounded read, HMAC-first, method/path allow-list, fixed responses) lives here.

    Args:
        config: The receiver config (root, secret, host, port).
        nudge: The daemon-wake callable, injected for tests; defaults to :func:`nudge_root`.
        ingest: The external-move ingestion callable (keel step 5 B), injected for tests; defaults
            to :func:`~kanbanmate.http.webhook_ingest.ingest_external_move`. Called with the runtime
            root, the resolved registry entry, and the verified payload; its
            :class:`~kanbanmate.http.webhook_ingest.IngestOutcome` is reflected in the 202 body.

    Returns:
        A ``BaseHTTPRequestHandler`` subclass ready to hand to a :class:`ThreadingHTTPServer`.
    """

    class _WebhookHandler(BaseHTTPRequestHandler):
        """The webhook request handler (one instance per connection, hardened per DESIGN §4.2)."""

        def setup(self) -> None:
            """Apply the slow-loris read timeout to THIS accepted connection socket (#2).

            The stdlib's ``BaseHTTPRequestHandler.setup`` wraps the ACCEPTED socket (``self.request``,
            which it aliases to ``self.connection``) into the ``rfile``/``wfile`` buffered streams.
            The listening socket's timeout does NOT propagate to accepted sockets, so a per-connection
            deadline must be set on the accepted socket itself — otherwise a slow client that dribbles
            its body (or never finishes the request line/headers) pins this worker thread indefinitely
            (the documented slow-loris guard was previously ineffective: it sat on the listening socket
            only). The deadline is set on ``self.request`` BEFORE ``super().setup()`` builds ``rfile``,
            so every subsequent read (request line, headers, AND body) inherits it; any read that
            stalls past :data:`SOCKET_TIMEOUT_SECONDS` raises ``socket.timeout`` and the connection is
            dropped, freeing the worker.
            """
            self.request.settimeout(SOCKET_TIMEOUT_SECONDS)
            super().setup()

        # Quieter than the stdlib default (which prints every request to stderr); route through the
        # module logger so the receiver's noise lands in the operator's normal log surface.
        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002 — stdlib signature
            logger.info("kanban serve: " + fmt, *args)

        def _send(self, status: int, body: str = "") -> None:
            """Send a FIXED response (status + a short plain-text body); never echoes request bytes."""
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def _reject_path_or_method(self) -> None:
            """Send 404 (unknown path) or 405 (known path, disallowed method) per the allow-list.

            DESIGN §4.2 method/path allow-list: an unknown path is 404; a known path hit with a
            method it does not accept is 405 (with an ``Allow`` header listing the permitted verbs) —
            NOT the stdlib's default 501. Called by every handler branch that did not match its
            method's allowed (path, method) pair, and by the other-verb catch-all.
            """
            allowed = _ALLOWED_METHODS.get(self.path)
            if allowed is None:
                self._send(404, "not found")
                return
            # Known path, wrong method → 405 with the canonical Allow header (sorted for determinism).
            self.send_response(405)
            self.send_header("Allow", ", ".join(sorted(allowed)))
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 — stdlib handler method name
            """Liveness only: ``GET /healthz`` → 200 (PM2 / the operator probe); else 404/405."""
            if self.path == "/healthz":
                self._send(200, "ok")
            else:
                # /webhook (known, wrong method) → 405; any other path → 404.
                self._reject_path_or_method()

        # Other HTTP verbs (PUT/DELETE/PATCH/HEAD/OPTIONS) route to the allow-list reject so a known
        # path returns 405 and an unknown path 404 — never the stdlib's default 501 (DESIGN §4.2).
        def do_PUT(self) -> None:  # noqa: N802 — stdlib handler method name
            """Disallowed verb → 405/404 via the allow-list (no PUT route)."""
            self._reject_path_or_method()

        def do_DELETE(self) -> None:  # noqa: N802 — stdlib handler method name
            """Disallowed verb → 405/404 via the allow-list (no DELETE route)."""
            self._reject_path_or_method()

        def do_PATCH(self) -> None:  # noqa: N802 — stdlib handler method name
            """Disallowed verb → 405/404 via the allow-list (no PATCH route)."""
            self._reject_path_or_method()

        def do_HEAD(self) -> None:  # noqa: N802 — stdlib handler method name
            """Disallowed verb → 405/404 via the allow-list (no HEAD route)."""
            self._reject_path_or_method()

        def do_OPTIONS(self) -> None:  # noqa: N802 — stdlib handler method name
            """Disallowed verb → 405/404 via the allow-list (no OPTIONS route)."""
            self._reject_path_or_method()

        def do_POST(self) -> None:  # noqa: N802 — stdlib handler method name
            """Handle ``POST /webhook``: verify HMAC, route to a project, nudge (DESIGN §4.2–§4.4)."""
            if self.path != "/webhook":
                # /healthz (known, wrong method) → 405; any other path → 404.
                self._reject_path_or_method()
                return

            body = self._read_bounded_body()
            if body is None:
                return  # _read_bounded_body already sent the 411/413 response.

            # HMAC verify FIRST, on the RAW bytes, BEFORE any JSON parse (DESIGN §4.3). A
            # missing/invalid signature → 401 with NO nudge.
            signature = self.headers.get(SIGNATURE_HEADER)
            if not verify_signature(config.secret, body, signature):
                self._send(401, "invalid signature")
                return

            event = self.headers.get("X-GitHub-Event", "")
            if event == "ping":
                # The GitHub setup handshake — acknowledge so the hook shows green.
                self._send(200, "pong")
                return
            if event != ACTED_EVENT:
                # Acknowledged but not acted on (we only react to projects_v2_item moves).
                self._send(204)
                return

            # Decode the (verified) JSON to route by project; a decode failure → 400 (the body was
            # signed by us, so a malformed JSON is a genuine error, not an attack to silently drop).
            try:
                payload = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, "bad json")
                return
            if not isinstance(payload, dict):
                self._send(400, "bad json")
                return

            project_id = project_id_from_payload(payload)
            entry = _resolve_entry(config, project_id)
            if entry is None:
                # Unknown / unmanaged project (or no project id) → accept + no-op. Never 4xx a board
                # we do not manage, so GitHub keeps the hook enabled (DESIGN §4.4).
                self._send(202, "accepted (unmanaged project)")
                return

            # keel step 5 (B): ingest an EXTERNAL GitHub drag into board.json BEFORE nudging, so the
            # daemon's diff fires the launch. Echo-safe (an incoming Status equal to the current
            # native placement — our own mirror echo — is dropped) and flock-safe (the FsBoardStateStore
            # lock). Fail-soft: any ingest failure is an outcome, never an exception, so we always fall
            # through to the nudge (the safety sweep reconciles). A non-native project / a non-Status
            # event ingests nothing and degrades to today's nudge-only behaviour.
            outcome = ingest(config.root, entry, payload)

            # Bump the daemon-wake nudge so the next sweep reconciles the changed board (<1 s). Always
            # nudge a managed project (even an echo-drop / no-status): the diff is a harmless no-op
            # when board.json did not change, preserving today's no-lost-trigger contract.
            # Fail-soft: nudge_daemon swallows its own errors; wrap defensively so a nudge failure
            # still returns 202 (the slow safety sweep is the always-on fallback).
            try:
                nudge(config.root)
            except Exception:  # noqa: BLE001 — a nudge failure degrades to the slow fallback sweep
                logger.warning("kanban serve: nudge failed; the safety sweep will reconcile")
            self._send(202, f"accepted ({outcome.value})")

        def _read_bounded_body(self) -> bytes | None:
            """Read the request body within the size + transfer-encoding bounds, or send an error.

            Returns the body bytes on success. On a bound violation it SENDS the error response
            (411 for chunked / absent length, 413 for oversize) and returns ``None`` so the caller
            stops. Reading is via the timeout-bounded ``rfile`` (the slow-loris guard).

            Returns:
                The body bytes, or ``None`` when an error response was already sent.
            """
            # GitHub always sends Content-Length; reject chunked transfer (we never stream-decode).
            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                self._send(411, "length required")
                return None
            raw_len = self.headers.get("Content-Length")
            if raw_len is None:
                self._send(411, "length required")
                return None
            try:
                length = int(raw_len)
            except ValueError:
                self._send(411, "length required")
                return None
            if length < 0 or length > MAX_BODY_BYTES:
                self._send(413, "payload too large")
                return None
            # Exact-length read on the timeout-bounded socket file; a short/slow body raises and the
            # connection is dropped (the slow-loris guard via the server's socket timeout).
            return self.rfile.read(length)

    return _WebhookHandler


def build_server(
    config: WebhookConfig,
    *,
    nudge: Callable[[Path], None] = nudge_root,
    ingest: Callable[[Path, Any, dict[str, Any]], IngestOutcome] = ingest_external_move,
) -> ThreadingHTTPServer:
    """Build (do NOT start) the hardened :class:`ThreadingHTTPServer` for the webhook receiver.

    The slow-loris guard (#2) is the per-CONNECTION read deadline applied in the handler's
    :meth:`_WebhookHandler.setup` (on each ACCEPTED socket) — NOT on the listening socket, whose
    timeout does not propagate to accepted connections. ``server.timeout`` is still set so a
    ``handle_request``-driven caller (used in some tests) does not block forever waiting to accept.
    The caller runs ``serve_forever`` (production) or drives the handler in tests.

    Args:
        config: The receiver config (host/port/root/secret).
        nudge: The daemon-wake callable, injected for tests; defaults to :func:`nudge_root`.
        ingest: The external-move ingestion callable (keel step 5 B), injected for tests; defaults
            to :func:`~kanbanmate.http.webhook_ingest.ingest_external_move`.

    Returns:
        A ready-but-not-serving :class:`ThreadingHTTPServer`.
    """
    handler_cls = make_handler(config, nudge=nudge, ingest=ingest)
    server = ThreadingHTTPServer((config.host, config.port), handler_cls)
    # The accept-poll timeout for ``handle_request`` (the per-CONNECTION read deadline that actually
    # stops a slow-loris lives in the handler's ``setup`` on the accepted socket, #2).
    server.timeout = SOCKET_TIMEOUT_SECONDS
    return server


def main(
    root: Path | None = None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    geteuid: Callable[[], int] = os.geteuid,
) -> None:
    """Console entry for ``kanban serve``: start the blocking webhook receiver (DESIGN §4).

    Refuses to run as root and refuses a privileged port (the daemon + agents run unprivileged),
    loads the shared secret (fail-loud when absent), builds the hardened server, and blocks in
    ``serve_forever`` until SIGTERM/SIGINT. Side-effect-free at import time.

    Args:
        root: The runtime root (default ``~/.kanban``); ``--root`` points at an alternate root so a
            second receiver can front a second daemon.
        host: The bind host (loopback by default; ``0.0.0.0`` is opt-in, behind a TLS proxy only).
        port: The bind port (unprivileged; 8765 default).
        geteuid: The effective-uid probe (injected for tests); defaults to :func:`os.geteuid`.

    Raises:
        RootPrivilegeError: When invoked as root.
        PrivilegedPortError: When asked to bind a privileged port (< 1024).
        WebhookSecretMissingError: When ``<root>/webhook_secret`` is absent.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if geteuid() == 0:
        raise RootPrivilegeError(
            "kanban serve must not run as root: the daemon + agents run unprivileged. Re-run as "
            "your user (front public exposure + TLS with your reverse proxy)."
        )
    if port < 1024:
        raise PrivilegedPortError(
            f"kanban serve refuses to bind privileged port {port} (< 1024); use the default 8765 "
            "or another unprivileged port and front it with your reverse proxy."
        )
    resolved_root = Path("~/.kanban/").expanduser() if root is None else Path(root)
    secret = load_webhook_secret(resolved_root)
    config = WebhookConfig(root=resolved_root, secret=secret, host=host, port=port)
    server = build_server(config)
    logger.info("kanban serve listening on %s:%d (root %s)", host, port, resolved_root)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("kanban serve stopped")
    finally:
        server.server_close()
