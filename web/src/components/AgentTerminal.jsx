// AgentTerminal — interactive xterm.js terminal for a running agent session (tiller §5).
// Opens a WebSocket to /api/monitor/agent/{issue}/attach; streams ANSI pane snapshots to the
// xterm Terminal; sends operator keystrokes back. Read-only by default; "take control" arms writes.
//
// Rendering model (tiller robustness, 2026-06-21):
//   The server resends the WHOLE pane (visible screen + scrollback history) every ~300ms — it is a
//   MIRROR, not a delta stream. The browser xterm is therefore sized to the pane's REAL width
//   (reported by the server) and the operator zooms with A-/A+; we never reflow the *running agent's*
//   tmux pane down to the viewer (that would corrupt the live agent's TUI). On each changed frame we
//   repaint but PRESERVE the operator's scroll position unless they are pinned to the bottom, so they
//   can scroll back through history without being yanked down every 300ms.
import React from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import "xterm/css/xterm.css";
import { useT } from "../i18n/index.jsx";

const { Banner, Button } = window.KanbanMateDesignSystem_2463ad;

const MIN_FONT = 7;
const MAX_FONT = 28;
const DEFAULT_FONT = 13;
const TERM_FONT_FAMILY =
  'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace';

/**
 * Interactive xterm.js terminal for a running agent session.
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
  // Pane geometry reported by the server (the agent's real tmux pane width). The xterm grid is
  // pinned to this width; only the ROW count is fitted to the container so the full pane is shown.
  const paneColsRef = React.useRef(80);
  const lastDataRef = React.useRef(null); // skip identical repaints (no scroll churn when idle)
  const autoFontDoneRef = React.useRef(false); // one-shot: pick a font that fits the viewport width
  const [armed, setArmed] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [ended, setEnded] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [fontSize, setFontSize] = React.useState(DEFAULT_FONT);
  const mobileInputRef = React.useRef(null);

  // Fit only the ROW count to the container (keep cols = the agent pane's real width).
  const fitRows = React.useCallback(() => {
    const term = termRef.current;
    const fit = fitRef.current;
    if (!term || !fit) return;
    let rows = 24;
    try {
      const dims = fit.proposeDimensions();
      if (dims && dims.rows > 0) rows = dims.rows;
    } catch (_) {
      /* container not laid out yet — keep the fallback */
    }
    try {
      term.resize(paneColsRef.current || 80, rows);
    } catch (_) {
      /* resize can throw mid-teardown — ignore */
    }
  }, []);

  // Repaint a full snapshot while preserving the operator's scroll position (sticky-bottom).
  const writeFrame = React.useCallback((data) => {
    const term = termRef.current;
    if (!term) return;
    if (data === lastDataRef.current) return; // unchanged → don't disturb scroll
    const buf = term.buffer.active;
    const distFromBottom = buf.baseY - buf.viewportY; // 0 ⇒ pinned to the bottom
    const wasPinned = distFromBottom <= 1;
    term.reset();
    term.write(data, () => {
      // When the operator had scrolled UP to read history, restore that offset instead of
      // snapping to the bottom. History is stable frame-to-frame, so the same offset lands on
      // the same content. Pinned-to-bottom keeps xterm's default follow behaviour.
      if (!wasPinned) {
        const nb = term.buffer.active;
        term.scrollToLine(Math.max(0, nb.baseY - distFromBottom));
      }
    });
    lastDataRef.current = data;
  }, []);

  // Mount xterm + open WebSocket
  React.useEffect(() => {
    const term = new Terminal({
      convertEol: true,
      scrollback: 6000,
      fontSize: DEFAULT_FONT,
      fontFamily: TERM_FONT_FAMILY,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fitRows();
    termRef.current = term;
    fitRef.current = fit;

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/monitor/agent/${issue}/attach`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);

        if (msg.alive === false) {
          setEnded(true);
          term.write("\r\n[session ended]\r\n");
          ws.close();
          return;
        }

        // Full ANSI pane snapshot (visible screen + scrollback history).
        if (msg.alive === true && msg.data !== undefined) {
          // Sync the xterm grid width to the agent pane's real width (so the full pane shows
          // without reflowing the running agent).
          if (typeof msg.cols === "number" && msg.cols > 0) {
            if (msg.cols !== paneColsRef.current) {
              paneColsRef.current = msg.cols;
              fitRows();
            }
            // One-shot: on first geometry, pick a font size that fits the full width into the
            // viewport (so narrow/mobile screens see everything; the operator zooms from there).
            if (!autoFontDoneRef.current && containerRef.current) {
              autoFontDoneRef.current = true;
              const cw = containerRef.current.clientWidth || 360;
              const target = Math.max(
                MIN_FONT,
                Math.min(DEFAULT_FONT, Math.floor(cw / (msg.cols * 0.62))),
              );
              if (target !== DEFAULT_FONT) setFontSize(target);
            }
          }
          writeFrame(msg.data);
        }

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

    // ResizeObserver → re-fit ROWS locally only. We deliberately DO NOT send a resize frame to the
    // server: shrinking the running agent's tmux pane to the viewer would corrupt its live TUI.
    const ro = new ResizeObserver(() => fitRows());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      ws.close();
      term.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [issue]);

  // Apply font-size changes (zoom) → re-fit rows for the new cell height.
  React.useEffect(() => {
    const term = termRef.current;
    if (!term) return;
    term.options.fontSize = fontSize;
    fitRows();
  }, [fontSize, fitRows]);

  // Focus the hidden input when armed so the mobile soft-keyboard opens.
  React.useEffect(() => {
    if (armed && mobileInputRef.current) {
      mobileInputRef.current.focus();
    }
  }, [armed]);

  // Refit on fullscreen toggle (wait one tick for DOM layout).
  React.useEffect(() => {
    const id = setTimeout(() => fitRows(), 0);
    return () => clearTimeout(id);
  }, [fullscreen, fitRows]);

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

  const zoom = React.useCallback((delta) => {
    setFontSize((prev) => Math.max(MIN_FONT, Math.min(MAX_FONT, prev + delta)));
  }, []);

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
                // Horizontal scroll when the pane is wider than the viewport; xterm's own
                // viewport handles vertical scrollback.
                overflowX: "auto",
                overflowY: "hidden",
                border: armed ? "2px solid var(--destructive)" : "none",
              }
            : {
                height: 320,
                background: "#1e1e1e",
                borderRadius: 6,
                overflowX: "auto",
                overflowY: "hidden",
                border: armed
                  ? "2px solid var(--destructive)"
                  : "1px solid var(--border)",
              }
        }
      />
      <ControlBar
        armed={armed}
        fullscreen={fullscreen}
        fontSize={fontSize}
        onToggle={toggleControl}
        onToggleFullscreen={toggleFullscreen}
        onSendKey={sendKey}
        onZoom={zoom}
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

/** Toolbar: control toggle, quick-keys, zoom, fullscreen, close. */
function ControlBar({
  armed,
  fullscreen,
  fontSize,
  onToggle,
  onToggleFullscreen,
  onSendKey,
  onZoom,
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
      {/* Zoom controls (operator-driven; never reflows the running agent's pane). */}
      <Button
        size="sm"
        variant="outline"
        onClick={() => onZoom(-1)}
        title={t("terminal.zoom_out", "Zoom out")}
      >
        A−
      </Button>
      <span
        style={{
          fontSize: 12,
          color: "var(--muted-foreground)",
          minWidth: 22,
          textAlign: "center",
        }}
      >
        {fontSize}
      </span>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onZoom(1)}
        title={t("terminal.zoom_in", "Zoom in")}
      >
        A+
      </Button>
      <Button size="sm" variant="outline" onClick={onToggleFullscreen}>
        {fullscreen ? "⤱" : "⤢"}
      </Button>
      <Button size="sm" variant="ghost" onClick={onClose}>
        {t("terminal.close", "Close")}
      </Button>
    </div>
  );
}
