// AgentTerminal — interactive xterm.js terminal for a running agent session (tiller §5).
// Opens a WebSocket to /api/monitor/agent/{issue}/attach; streams ANSI pane snapshots to the
// xterm Terminal; sends operator keystrokes back. Read-only by default; "take control" arms writes.
import React from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import "xterm/css/xterm.css";
import { useT } from "../i18n/index.jsx";

const { Banner, Button } = window.KanbanMateDesignSystem_2463ad;

/**
 * Interactive xterm.js terminal for a running agent session.
 *
 * Opens a WebSocket to the tiller agent-attach endpoint and renders full ANSI pane
 * snapshots (reset + write per frame — the server resends the whole visible pane
 * every ~300ms, NOT a delta). Keystrokes are forwarded only when the operator has
 * taken control.
 *
 * @param {{ issue: number, onClose: () => void }} props
 */
export default function AgentTerminal({ issue, onClose }) {
  const { t } = useT();
  const containerRef = React.useRef(null);
  const termRef = React.useRef(null);
  const fitRef = React.useRef(null);
  const wsRef = React.useRef(null);
  const armedRef = React.useRef(false);
  const [armed, setArmed] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [ended, setEnded] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const mobileInputRef = React.useRef(null);

  // Mount xterm + open WebSocket
  React.useEffect(() => {
    const term = new Terminal({ convertEol: true, scrollback: 1000 });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();
    termRef.current = term;
    fitRef.current = fit;

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/monitor/agent/${issue}/attach`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);

        // Server → Client frames (agent_terminal.py read_loop + write_loop)
        if (msg.alive === false) {
          setEnded(true);
          term.write("\r\n[session ended]\r\n");
          ws.close();
          return;
        }

        // Full ANSI pane snapshot — reset + write (NOT a delta).
        if (msg.alive === true && msg.data !== undefined) {
          term.reset();
          term.write(msg.data);
        }

        // Control state acknowledgements
        if (msg.control === "armed") {
          setArmed(true);
          armedRef.current = true;
        }
        if (msg.control === "released") {
          setArmed(false);
          armedRef.current = false;
        }

        if (msg.error) setError(msg.error);
      } catch (_) {
        /* ignore malformed frames */
      }
    };

    ws.onerror = () => setError("WebSocket error");
    ws.onclose = () => setEnded(true);

    // Forward keystrokes to the server when armed (ref avoids stale closure).
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN && armedRef.current) {
        ws.send(JSON.stringify({ type: "text", data }));
      }
    });

    // ResizeObserver → fit + send resize frame
    const ro = new ResizeObserver(() => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }),
        );
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      ws.close();
      term.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [issue]);

  // Focus the hidden input when armed so the mobile soft-keyboard opens.
  React.useEffect(() => {
    if (armed && mobileInputRef.current) {
      mobileInputRef.current.focus();
    }
  }, [armed]);

  // Refit on fullscreen toggle (wait one tick for DOM layout).
  React.useEffect(() => {
    const fit = fitRef.current;
    if (fit) {
      const id = setTimeout(() => fit.fit(), 0);
      return () => clearTimeout(id);
    }
  }, [fullscreen]);

  const sendMsg = React.useCallback((msg) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }, []);

  const toggleControl = React.useCallback(() => {
    if (!armedRef.current) {
      sendMsg({ type: "take_control" });
      // Optimistic — server ack will confirm/revert via ws.onmessage.
      setArmed(true);
      armedRef.current = true;
    } else {
      sendMsg({ type: "release_control" });
      setArmed(false);
      armedRef.current = false;
    }
  }, [sendMsg]);

  const sendKey = React.useCallback(
    (name) => {
      if (armedRef.current) sendMsg({ type: "key", name });
    },
    [sendMsg],
  );

  // Hidden input handler — captures mobile soft-keyboard input and forwards it.
  const handleMobileInput = React.useCallback(
    (e) => {
      const val = e.target.value;
      if (!val) return;
      sendMsg({ type: "text", data: val });
      e.target.value = "";
    },
    [sendMsg],
  );

  const toggleFullscreen = React.useCallback(() => {
    setFullscreen((prev) => !prev);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {error && <Banner tone="red">{error}</Banner>}
      {ended && (
        <Banner tone="amber">
          {t("terminal.session_ended", "Session ended")}
        </Banner>
      )}
      <div
        ref={containerRef}
        style={
          fullscreen
            ? {
                position: "fixed",
                inset: 0,
                zIndex: 9999,
                background: "#1e1e1e",
                borderRadius: 0,
                overflow: "hidden",
                border: armed ? "2px solid var(--destructive)" : "none",
              }
            : {
                height: 320,
                background: "#1e1e1e",
                borderRadius: 6,
                overflow: "hidden",
                border: armed
                  ? "2px solid var(--destructive)"
                  : "1px solid var(--border)",
              }
        }
      />
      <ControlBar
        armed={armed}
        fullscreen={fullscreen}
        onToggle={toggleControl}
        onToggleFullscreen={toggleFullscreen}
        onSendKey={sendKey}
        onClose={onClose}
        t={t}
      />
      {/* Hidden input — captures mobile soft-keyboard input when the terminal is armed.
          Keystrokes are forwarded as {type:"text"} frames. */}
      <input
        ref={mobileInputRef}
        style={{
          position: "absolute",
          opacity: 0,
          width: 1,
          height: 1,
          pointerEvents: "none",
        }}
        onInput={handleMobileInput}
        aria-hidden="true"
        tabIndex={-1}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
      />
    </div>
  );
}

/** Toolbar: control toggle, quick-keys, fullscreen, close. */
function ControlBar({
  armed,
  fullscreen,
  onToggle,
  onToggleFullscreen,
  onSendKey,
  onClose,
  t,
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      <Button tone={armed ? "destructive" : "secondary"} onClick={onToggle}>
        {armed
          ? t("terminal.release", "Release control")
          : t("terminal.take_control", "Take control")}
      </Button>
      {armed && (
        <>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSendKey("Enter")}
          >
            ↵ Enter
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSendKey("Escape")}
          >
            Esc
          </Button>
          <Button size="sm" variant="outline" onClick={() => onSendKey("C-c")}>
            Ctrl-C
          </Button>
        </>
      )}
      <Button size="sm" variant="outline" onClick={onToggleFullscreen}>
        {fullscreen ? "⤱" : "⤢"}
      </Button>
      <Button size="sm" variant="ghost" onClick={onClose}>
        {t("terminal.close", "Close")}
      </Button>
    </div>
  );
}
