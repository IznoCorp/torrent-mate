import { act, cleanup, renderHook } from "@testing-library/react";
import { StrictMode, type ReactElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  EVENTS_CAP,
  LAST_EVENT_ID_STORAGE_KEY,
  useEventStream,
} from "@/hooks/useEventStream";
import { MockWebSocket } from "@/test/mockWebSocket";

/**
 * Return the latest constructed socket, asserting one exists.
 *
 * Keeps every test's socket handle non-null without scattering ``?.`` guards.
 */
function latestSocket(): MockWebSocket {
  const socket = MockWebSocket.latest();
  if (socket === null) {
    throw new Error("Aucune instance WebSocket construite.");
  }
  return socket;
}

/** A hello frame carrying ``build_commit`` (the auth-confirming handshake). */
function helloFrame(buildCommit: string): Record<string, unknown> {
  return { type: "ws.hello", data: { build_commit: buildCommit } };
}

/** An event frame with a stream ``id`` (drives the events ring + cursor). */
function eventFrame(
  id: string,
  type = "PipelineStepStarted",
): Record<string, unknown> {
  return { id, type, data: { step: type } };
}

beforeEach(() => {
  MockWebSocket.reset();
  window.localStorage.clear();
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useEventStream", () => {
  it("passe à « connected » et mémorise le build_commit sur ws.hello", () => {
    const { result } = renderHook(() => useEventStream());

    expect(result.current.connectionState).toBe("connecting");

    act(() => {
      latestSocket().emitOpen();
      latestSocket().emitMessage(helloFrame("abc1234"));
    });

    expect(result.current.connectionState).toBe("connected");
    expect(result.current.buildCommit).toBe("abc1234");
  });

  it("empile chaque événement et persiste son id dans localStorage", () => {
    const { result } = renderHook(() => useEventStream());

    act(() => {
      latestSocket().emitMessage(helloFrame("abc1234"));
      latestSocket().emitMessage(eventFrame("42-0"));
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]?.id).toBe("42-0");
    expect(result.current.lastEventId).toBe("42-0");
    expect(window.localStorage.getItem(LAST_EVENT_ID_STORAGE_KEY)).toBe("42-0");
  });

  it("répond « pong » à un ws.ping", () => {
    renderHook(() => useEventStream());

    act(() => {
      latestSocket().emitMessage(helloFrame("abc1234"));
      latestSocket().emitMessage({ type: "ws.ping" });
    });

    expect(latestSocket().sent).toContain("pong");
  });

  it("ignore une trame JSON malformée sans planter", () => {
    const { result } = renderHook(() => useEventStream());

    act(() => {
      latestSocket().emitMessage(helloFrame("abc1234"));
      latestSocket().emitRaw("{ not json");
    });

    expect(result.current.connectionState).toBe("connected");
    expect(result.current.events).toHaveLength(0);
  });

  it("borne l’anneau d’événements à EVENTS_CAP", () => {
    const { result } = renderHook(() => useEventStream());

    act(() => {
      latestSocket().emitMessage(helloFrame("abc1234"));
      for (let i = 0; i < EVENTS_CAP + 5; i += 1) {
        latestSocket().emitMessage(eventFrame(`${String(i)}-0`));
      }
    });

    expect(result.current.events).toHaveLength(EVENTS_CAP);
    // The oldest five were evicted — the ring keeps the most recent EVENTS_CAP.
    expect(result.current.events[0]?.id).toBe("5-0");
    expect(result.current.events.at(-1)?.id).toBe(
      `${String(EVENTS_CAP + 4)}-0`,
    );
  });

  it("se reconnecte après un ping manqué, en rejouant depuis last_id", () => {
    vi.useFakeTimers();
    renderHook(() => useEventStream());

    const first = latestSocket();
    // No persisted cursor yet → the first connection carries no ?last_id=.
    expect(first.url).not.toContain("last_id");

    act(() => {
      first.emitOpen();
      first.emitMessage(helloFrame("abc1234"));
      first.emitMessage(eventFrame("77-0"));
    });

    // 45 s of silence → the watchdog force-closes → state flips to reconnecting.
    act(() => {
      vi.advanceTimersByTime(45_000);
    });
    // Advance past the (jittered ≤ 1 s) backoff so the reconnect actually fires.
    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    const second = latestSocket();
    expect(second).not.toBe(first);
    // Replay: the reconnect URL carries the persisted cursor.
    expect(second.url).toContain(`last_id=77-0`);
  });

  it("ne se reconnecte pas sur une fermeture 4401 (session perdue)", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useEventStream());

    const first = latestSocket();
    act(() => {
      first.emitOpen();
      first.emitMessage(helloFrame("abc1234"));
    });

    act(() => {
      first.emitClose(4401);
    });

    expect(result.current.connectionState).toBe("disconnected");

    // Even after a long wait, no new socket is opened.
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("ne laisse qu’un seul socket vivant sous le double-montage StrictMode", () => {
    const wrapper = ({ children }: { children: ReactNode }): ReactElement => (
      <StrictMode>{children}</StrictMode>
    );
    renderHook(() => useEventStream(), { wrapper });

    // StrictMode double-invokes the effect in dev: the first socket is torn down
    // and closed, the second survives — never two live connections.
    const alive = MockWebSocket.instances.filter((socket) => !socket.closed);
    expect(alive).toHaveLength(1);
  });

  it("ferme le socket au démontage", () => {
    const { unmount } = renderHook(() => useEventStream());
    const socket = latestSocket();

    expect(socket.closed).toBe(false);
    unmount();
    expect(socket.closed).toBe(true);
  });
});
