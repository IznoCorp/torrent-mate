// SSE subscription hook for sub-second Monitoring + board updates (keel STEP 4).
//
// Opens an EventSource on /api/monitor/stream?project=… and invokes `onChange` whenever the server
// reports a board change (the board.json `version` int or the daemon heartbeat `tick` changed). The
// consumer (MonitoringPanel / BoardPanel) refetches the real payloads on that callback — the stream
// carries only the change signal, never board state, so a dropped event costs at most one extra
// refetch and the panels KEEP their own backstop poll (graceful degradation to polling).
//
// Discipline this hook enforces:
// - Reconnect BACK-OFF: the browser's built-in EventSource auto-reconnect storms a flapping daemon
//   (it retries ~immediately). We instead CLOSE on error and reopen via setTimeout with exponential
//   back-off (1s → 2s → 4s … capped), resetting to the floor once a message arrives. No reconnect
//   storm on a daemon that is bouncing.
// - Visibility pause: no stream while the tab is hidden (mirrors the panels' visibility-gated polls);
//   reopen when it becomes visible again. A backgrounded tab holds no connection.
// - De-dupe: `onChange` fires only when version OR tick actually changed vs the last delivered event,
//   so a redundant reconnect priming event doesn't trigger a needless refetch.
import React from "react";
import { monitorStreamUrl } from "./api.js";

const BACKOFF_FLOOR_MS = 1000;
const BACKOFF_CEIL_MS = 30000;

export default function useMonitorStream(project, onChange) {
  // Keep the latest callback in a ref so re-opening the stream doesn't depend on a stable callback
  // identity (the consumer can pass an inline arrow without re-arming the connection every render).
  const cbRef = React.useRef(onChange);
  cbRef.current = onChange;

  React.useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return undefined; // SSR / unsupported environment — the backstop poll covers it.
    }
    let es = null;
    let retryTimer = null;
    let backoff = BACKOFF_FLOOR_MS;
    let closed = false; // set on cleanup so a pending reconnect never fires after unmount
    // Last delivered signal, so we only call onChange on a real change (de-dupe reconnect priming).
    let lastVersion;
    let lastTick;
    let seeded = false;

    const clearRetry = () => {
      if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
    };

    const close = () => {
      clearRetry();
      if (es) {
        es.close();
        es = null;
      }
    };

    const open = () => {
      if (closed || document.visibilityState !== "visible") return;
      // Guard against a double-open (e.g. a visibility flap racing a reconnect timer).
      if (es) return;
      es = new EventSource(monitorStreamUrl(project));
      es.addEventListener("change", (ev) => {
        // A successful message → reset the back-off to the floor for the next disconnect.
        backoff = BACKOFF_FLOOR_MS;
        let data = null;
        try {
          data = JSON.parse(ev.data);
        } catch (_) {
          return; // ignore a malformed frame
        }
        const v = data ? data.version : undefined;
        const tk = data ? data.tick : undefined;
        const changed = !seeded || v !== lastVersion || tk !== lastTick;
        seeded = true;
        lastVersion = v;
        lastTick = tk;
        if (changed && cbRef.current) cbRef.current(data);
      });
      es.onerror = () => {
        // EventSource auto-retries with no back-off → close it and reconnect ourselves with
        // exponential back-off so a flapping daemon doesn't get a reconnect storm.
        close();
        if (closed || document.visibilityState !== "visible") return;
        clearRetry();
        retryTimer = setTimeout(open, backoff);
        backoff = Math.min(backoff * 2, BACKOFF_CEIL_MS);
      };
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        backoff = BACKOFF_FLOOR_MS; // a fresh foreground attempt starts at the floor
        open();
      } else {
        close(); // backgrounded → drop the connection
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    open();

    return () => {
      closed = true;
      document.removeEventListener("visibilitychange", onVisibility);
      close();
    };
  }, [project]);
}
