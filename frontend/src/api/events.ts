/**
 * Typed WebSocket message contracts for the live event stream (tm-shell §4.5).
 *
 * These types mirror the server wire shapes **exactly** — the source of truth is
 * ``personalscraper/web/ws/routes.py`` (handshake + ping) and
 * ``personalscraper/web/ws/relay.py`` (event fan-out / replay):
 *
 * - **Event**  ``{"id": "<stream-id>", "type": "<EventClass>", "data": {…}}``
 * - **Hello**  ``{"type": "ws.hello", "data": {"build_commit": "…"}}``  (once, on connect)
 * - **Ping**   ``{"type": "ws.ping"}``  (keep-alive; client replies ``pong``)
 *
 * Narrowing goes through :func:`parseServerMessage` (safe over untrusted JSON)
 * and the total type guards :func:`isEvent` / :func:`isHello` / :func:`isPing`.
 * No ``any`` crosses this boundary.
 */

/** The literal ``type`` tag of the handshake message. */
export const HELLO_TYPE = "ws.hello";
/** The literal ``type`` tag of the keep-alive ping message. */
export const PING_TYPE = "ws.ping";

/**
 * Pipeline run-lifecycle + step-boundary event class names.
 *
 * These are the events that shift the pipeline status, the Flow Board and the
 * staging tree — a run starting/ending/pausing/resuming, or a step boundary.
 * The ONE definition of this set: it used to be pasted verbatim as an
 * ``INVALIDATE_EVENT_TYPES`` const in three hooks (FRONTEND-DATA-03). The
 * WS-event → cache-invalidation map ({@link useWsInvalidation}) imports it here.
 */
export const PIPELINE_LIFECYCLE_EVENT_TYPES: ReadonlySet<string> = new Set([
  "PipelineStarted",
  "PipelineEnded",
  "PipelinePaused",
  "PipelineResumed",
  "StepStarted",
  "StepCompleted",
]);

/**
 * Events that change the shell nav badges and their cross-page caches.
 *
 * An item advancing (``ItemProgressed``) or a run starting/ending flips the
 * staging awaiting-action count, may have queued/cleared decision rows, and
 * reserves/updates a pipeline_run row — so the shell refreshes the staging
 * counts, the decisions queue and the pipeline history on these.
 */
export const SHELL_BADGE_EVENT_TYPES: ReadonlySet<string> = new Set([
  "ItemProgressed",
  "PipelineEnded",
  "PipelineStarted",
]);

/**
 * A live or replayed domain event, carrying the Redis-stream cursor ``id``.
 *
 * ``type`` is the emitting event class name (e.g. ``"PipelineStepStarted"``);
 * ``data`` is the serialized envelope payload, kept opaque here — consumers
 * narrow it per event type when they need specific fields.
 */
export interface EventMessage {
  readonly id: string;
  readonly type: string;
  readonly data: Record<string, unknown>;
}

/**
 * The handshake frame sent immediately after ``accept`` and before any replay
 * or live message. Its ``build_commit`` stamps the backend the socket is bound
 * to (surfaced by the shell / dashboard).
 */
export interface HelloMessage {
  readonly type: typeof HELLO_TYPE;
  readonly data: { readonly build_commit: string };
}

/**
 * A server keep-alive. The server sends one after ``PING_INTERVAL`` (30 s) of
 * client silence; the client replies with a ``pong`` text frame to reset it.
 */
export interface PingMessage {
  readonly type: typeof PING_TYPE;
}

/** Discriminated union of every message the server may push over the socket. */
export type ServerMessage = EventMessage | HelloMessage | PingMessage;

/**
 * Narrow a :class:`ServerMessage` to the {@link HelloMessage} arm.
 *
 * Args:
 *   msg: A parsed server message.
 *
 * Returns:
 *   ``true`` (and narrows) when ``msg`` is the handshake frame.
 */
export function isHello(msg: ServerMessage): msg is HelloMessage {
  return msg.type === HELLO_TYPE;
}

/**
 * Narrow a :class:`ServerMessage` to the {@link PingMessage} arm.
 *
 * Args:
 *   msg: A parsed server message.
 *
 * Returns:
 *   ``true`` (and narrows) when ``msg`` is a keep-alive ping.
 */
export function isPing(msg: ServerMessage): msg is PingMessage {
  return msg.type === PING_TYPE;
}

/**
 * Narrow a :class:`ServerMessage` to the {@link EventMessage} arm.
 *
 * Anything that is neither the hello handshake nor a ping is, by construction of
 * :func:`parseServerMessage`, a fully-formed event (string ``id`` + object
 * ``data``).
 *
 * Args:
 *   msg: A parsed server message.
 *
 * Returns:
 *   ``true`` (and narrows) when ``msg`` is a domain event.
 */
export function isEvent(msg: ServerMessage): msg is EventMessage {
  return msg.type !== HELLO_TYPE && msg.type !== PING_TYPE;
}

/** Type guard for a non-null JSON object (the only shape we accept). */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Safely parse a raw WebSocket text frame into a typed {@link ServerMessage}.
 *
 * Rejects (returns ``null``) on: malformed JSON, non-object payloads, a missing
 * or non-string ``type``, a hello without a string ``build_commit``, or an event
 * without a string ``id`` / object ``data``. Never throws, never yields ``any``.
 *
 * Args:
 *   raw: The raw frame body (``MessageEvent.data`` as a string).
 *
 * Returns:
 *   The narrowed message, or ``null`` when the frame is not a recognised /
 *   well-formed server message.
 */
export function parseServerMessage(raw: string): ServerMessage | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }

  if (!isRecord(parsed)) {
    return null;
  }

  const type = parsed.type;
  if (typeof type !== "string") {
    return null;
  }

  if (type === HELLO_TYPE) {
    const data = parsed.data;
    if (!isRecord(data) || typeof data.build_commit !== "string") {
      return null;
    }
    return { type: HELLO_TYPE, data: { build_commit: data.build_commit } };
  }

  if (type === PING_TYPE) {
    return { type: PING_TYPE };
  }

  // Otherwise it must be a domain event: a string cursor id + an object payload.
  const id = parsed.id;
  const data = parsed.data;
  if (typeof id !== "string" || !isRecord(data)) {
    return null;
  }
  return { id, type, data };
}
