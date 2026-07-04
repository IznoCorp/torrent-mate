/**
 * A controllable in-memory ``WebSocket`` double for Vitest.
 *
 * Install it with ``vi.stubGlobal("WebSocket", MockWebSocket)``; the code under
 * test constructs it exactly like the real global. Tests drive the "server" side
 * with the ``emit*`` helpers and inspect ``instances`` / ``sent`` / ``url``.
 *
 * Only the surface {@link useEventStream} touches is implemented: the four
 * ``on*`` handler slots, ``send``, ``close``, plus the reconnect-relevant
 * bookkeeping (``instances``, ``closed``, ``url``).
 */
export class MockWebSocket {
  /** Every socket constructed since the last reset, oldest first. */
  static instances: MockWebSocket[] = [];

  /** Reset the shared instance list — call from ``beforeEach``. */
  static reset(): void {
    MockWebSocket.instances = [];
  }

  readonly url: string;
  /** Frames passed to {@link send} (the client's ``pong`` replies). */
  readonly sent: string[] = [];
  /** ``true`` once {@link close} has been called on this socket. */
  closed = false;

  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  /** Record a client-sent frame (the hook only ever sends ``"pong"``). */
  send(data: string): void {
    this.sent.push(data);
  }

  /** Mark the socket closed and fire ``onclose`` (idempotent). */
  close(code?: number): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.emitClose(code ?? 1000);
  }

  /** Simulate the transport opening. */
  emitOpen(): void {
    this.onopen?.();
  }

  /** Simulate a server text frame carrying ``payload`` as JSON. */
  emitMessage(payload: unknown): void {
    this.emitRaw(JSON.stringify(payload));
  }

  /** Simulate a raw server text frame (for malformed-input coverage). */
  emitRaw(data: string): void {
    this.onmessage?.({ data } as unknown as MessageEvent);
  }

  /** Simulate the socket closing with ``code`` (e.g. ``4401`` for auth loss). */
  emitClose(code: number): void {
    this.onclose?.({ code } as unknown as CloseEvent);
  }

  /** The most recently constructed socket, or ``null`` when none exist yet. */
  static latest(): MockWebSocket | null {
    return MockWebSocket.instances.at(-1) ?? null;
  }
}
