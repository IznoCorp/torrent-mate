// AgentTerminal — a REAL interactive terminal for a running agent session (tiller §5).
//
// Opens a WebSocket to /api/monitor/agent/{issue}/attach. The server attaches a PTY to the agent's
// tmux session and streams the master fd bidirectionally (like ttyd / wetty):
//   • binary frames  = raw terminal bytes → written straight to xterm (real-time, fluid; no polling)
//   • text frames    = JSON control (armed / released / error)
// The xterm fits its container (FitAddon) and we drive the tmux pane to that size via a
// {type:"resize"} message, so the terminal reflows fluidly — fullscreen genuinely enlarges it, and
// every key xterm emits (arrows, Home/End, Ctrl chords, function keys) is forwarded raw to the PTY.
// Read-only until "take control" arms input.
import React from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import "xterm/css/xterm.css";
import { useT } from "../i18n/index.jsx";

const { Banner, Button, Tooltip } = window.KanbanMateDesignSystem_2463ad;

const MIN_FONT = 7;
const MAX_FONT = 28;
const DEFAULT_FONT = 13;
const TERM_FONT_FAMILY =
  'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace';

// On-screen quick-key buttons (for keys phones lack) → the raw bytes a terminal expects.
const KEY_BYTES = { Enter: "\r", Escape: "\x1b", "C-c": "\x03" };

/**
 * Interactive PTY-streamed terminal for a running agent session.
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
  const [fontSize, setFontSize] = React.useState(DEFAULT_FONT);
  const [killConfirm, setKillConfirm] = React.useState(false); // 2-step confirm for the destructive kill
  // Latest toggle callbacks, so the xterm custom-key handler (registered once at mount) always
  // calls the current ones without going stale.
  const toggleFullscreenRef = React.useRef(() => {});
  const toggleControlRef = React.useRef(() => {});

  // Send a JSON control / input / resize frame to the server.
  const send = React.useCallback((obj) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  // Last size we actually sent to the pane + the debounce timer for ResizeObserver bursts.
  const lastSizeRef = React.useRef({ cols: 0, rows: 0 });
  const resizeTimerRef = React.useRef(null);

  // Fit xterm to its container, then drive the tmux pane to match — but ONLY when the size really
  // changed. Re-sending an identical size fires a redundant SIGWINCH, which makes Claude Code's Ink
  // TUI repaint mid-menu and is a prime trigger of the redraw drift that garbles /model, /effort, …
  // (Claude #29937). Deduping the resize is the single biggest thing we control here.
  const fitAndResize = React.useCallback(() => {
    const term = termRef.current;
    const fit = fitRef.current;
    if (!term || !fit) return;
    try {
      fit.fit();
    } catch (_) {
      /* container not laid out yet — ignore */
    }
    const { cols, rows } = term;
    if (cols > 0 && rows > 0) {
      const last = lastSizeRef.current;
      if (cols !== last.cols || rows !== last.rows) {
        lastSizeRef.current = { cols, rows };
        send({ type: "resize", cols, rows });
      }
    }
  }, [send]);

  // Debounced fit for the ResizeObserver: a burst of layout callbacks (rotation, fullscreen toggle,
  // the mobile soft-keyboard opening) coalesces into ONE resize instead of a SIGWINCH storm.
  const scheduleFit = React.useCallback(() => {
    clearTimeout(resizeTimerRef.current);
    resizeTimerRef.current = setTimeout(fitAndResize, 180);
  }, [fitAndResize]);

  // Force Claude's Ink TUI to fully re-render — the reliable way to clear accumulated redraw drift
  // (Ctrl-L / tmux redraw do NOT, since the drift lives in Ink's virtual buffer, Claude #29937). A
  // one-row size nudge is the signal that makes Ink recompute its layout from scratch.
  const redraw = React.useCallback(() => {
    const term = termRef.current;
    if (!term || term.cols <= 0 || term.rows <= 0) return;
    const { cols, rows } = term;
    send({ type: "resize", cols, rows: Math.max(5, rows - 1) });
    setTimeout(() => {
      lastSizeRef.current = { cols, rows };
      send({ type: "resize", cols, rows });
    }, 120);
  }, [send]);

  // Mount xterm + open the PTY WebSocket.
  React.useEffect(() => {
    const term = new Terminal({
      cursorBlink: true,
      scrollback: 10000,
      fontSize: DEFAULT_FONT,
      fontFamily: TERM_FONT_FAMILY,
      theme: { background: "#1e1e1e" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    termRef.current = term;
    fitRef.current = fit;
    try {
      fit.fit();
    } catch (_) {
      /* not laid out yet */
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/monitor/agent/${issue}/attach`;
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      // Size the agent pane to our fitted geometry as soon as the socket is up.
      if (term.cols > 0 && term.rows > 0) {
        lastSizeRef.current = { cols: term.cols, rows: term.rows };
        ws.send(
          JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }),
        );
      }
      // Open already IN CONTROL (operator decision): keystrokes flow immediately and the soft
      // keyboard opens on mobile. "Release control" drops back to a read-only view.
      ws.send(JSON.stringify({ type: "take_control" }));
      setArmed(true);
      armedRef.current = true;
      term.focus();
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        // JSON control frame.
        try {
          const msg = JSON.parse(ev.data);
          if (msg.control === "armed") {
            setArmed(true);
            armedRef.current = true;
          } else if (msg.control === "released") {
            setArmed(false);
            armedRef.current = false;
            setKillConfirm(false); // drop any pending kill confirmation
          } else if (msg.error) {
            setError(msg.error);
          }
        } catch (_) {
          /* ignore malformed control frame */
        }
        return;
      }
      // Binary frame — raw terminal bytes straight into xterm.
      term.write(new Uint8Array(ev.data));
    };
    ws.onerror = () => setError("WebSocket error");
    ws.onclose = () => setEnded(true);

    // Forward every key sequence xterm produces to the PTY when armed (native key mapping).
    term.onData((data) => {
      if (armedRef.current && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Operator shortcuts intercepted BEFORE xterm forwards them to the agent (return false = handled).
    if (term.attachCustomKeyEventHandler) {
      term.attachCustomKeyEventHandler((e) => {
        if (e.type !== "keydown") return true;
        if (e.ctrlKey && e.shiftKey) {
          const k = e.key.toLowerCase();
          if (k === "f") {
            toggleFullscreenRef.current();
            return false;
          }
          if (k === "i") {
            toggleControlRef.current();
            return false;
          }
        }
        return true;
      });
    }

    // Refit + resize the pane whenever the container changes size (layout, rotate, fullscreen).
    // Debounced + deduped so a burst of layout callbacks never storms the pane with SIGWINCHs.
    const ro = new ResizeObserver(() => scheduleFit());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      clearTimeout(resizeTimerRef.current);
      // Detach handlers BEFORE closing: ws.close() is async, so an already-queued binary frame
      // could otherwise fire ws.onmessage → term.write() on a just-disposed Terminal and throw.
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      ws.close();
      term.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [issue]);

  // Font-size change (zoom) → refit (fewer/more cells) and resize the pane.
  React.useEffect(() => {
    const term = termRef.current;
    if (!term) return;
    term.options.fontSize = fontSize;
    fitAndResize();
  }, [fontSize, fitAndResize]);

  // Focus the terminal when armed so keystrokes flow (desktop) AND the mobile soft-keyboard opens.
  React.useEffect(() => {
    if (armed && termRef.current) termRef.current.focus();
  }, [armed]);

  // Refit after the DOM settles on a fullscreen toggle (the container grew / shrank).
  React.useEffect(() => {
    const id = setTimeout(() => fitAndResize(), 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullscreen]);

  const toggleControl = React.useCallback(() => {
    if (!armedRef.current) {
      send({ type: "take_control" });
      // Optimistic — the server ack confirms/reverts via ws.onmessage.
      setArmed(true);
      armedRef.current = true;
      if (termRef.current) termRef.current.focus(); // open the soft keyboard on mobile
    } else {
      send({ type: "release_control" });
      setArmed(false);
      armedRef.current = false;
      setKillConfirm(false); // drop any pending kill confirmation when leaving control
    }
  }, [send]);

  // On-screen quick keys → send the raw control bytes (only while in control).
  const sendKey = React.useCallback(
    (name) => {
      if (!armedRef.current) return;
      const bytes = KEY_BYTES[name];
      if (bytes != null) send({ type: "input", data: bytes });
    },
    [send],
  );

  const zoom = React.useCallback((delta) => {
    setFontSize((prev) => Math.max(MIN_FONT, Math.min(MAX_FONT, prev + delta)));
  }, []);

  const toggleFullscreen = React.useCallback(() => {
    setFullscreen((prev) => !prev);
  }, []);

  // End the Claude session/agent (kills the REPL; the surviving shell runs the clean teardown).
  const onKill = React.useCallback(() => {
    send({ type: "kill" });
    setKillConfirm(false);
  }, [send]);

  // Keep the refs the xterm key handler reads pointed at the latest callbacks.
  toggleFullscreenRef.current = toggleFullscreen;
  toggleControlRef.current = toggleControl;

  return (
    // In fullscreen the OUTER wrapper is the fixed overlay (flex column) so the ControlBar stays
    // a visible child — otherwise the exit-fullscreen button is buried under the terminal and the
    // operator is trapped. In normal flow it is a plain stacked column.
    <div
      style={
        fullscreen
          ? {
              position: "fixed",
              inset: 0,
              zIndex: 9999,
              background: "#1e1e1e",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              padding: 8,
            }
          : { display: "flex", flexDirection: "column", gap: 8 }
      }
    >
      {error && <Banner tone="error">{error}</Banner>}
      {ended && (
        <Banner tone="warning">
          {t("terminal.session_ended", "Session ended")}
        </Banner>
      )}
      <div
        ref={containerRef}
        style={
          fullscreen
            ? {
                // Fill the overlay; the ControlBar takes its natural height below.
                flex: 1,
                minHeight: 0,
                background: "#1e1e1e",
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
        fontSize={fontSize}
        killConfirm={killConfirm}
        onToggle={toggleControl}
        onToggleFullscreen={toggleFullscreen}
        onSendKey={sendKey}
        onZoom={zoom}
        onRedraw={redraw}
        onKill={onKill}
        onArmKill={() => setKillConfirm(true)}
        onCancelKill={() => setKillConfirm(false)}
        onClose={onClose}
        t={t}
      />
      {/* Help/cheatsheet — hidden in fullscreen (the terminal fills the screen there). */}
      {!fullscreen && <TerminalHelp t={t} />}
    </div>
  );
}

/** Toolbar: control toggle, quick-keys, zoom, fullscreen, close. */
function ControlBar({
  armed,
  fullscreen,
  fontSize,
  killConfirm,
  onToggle,
  onToggleFullscreen,
  onSendKey,
  onZoom,
  onRedraw,
  onKill,
  onArmKill,
  onCancelKill,
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
      <Tooltip
        label={
          armed
            ? t("tip.term_release", "Stop sending your keystrokes to the agent")
            : t("tip.term_take_control", "Send your keystrokes to the agent")
        }
      >
        <Button tone={armed ? "destructive" : "secondary"} onClick={onToggle}>
          {armed
            ? t("terminal.release", "Release control")
            : t("terminal.take_control", "Take control")}
        </Button>
      </Tooltip>
      {armed && (
        <>
          <Tooltip label={t("tip.term_enter", "Send the Enter key")}>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onSendKey("Enter")}
            >
              ↵ Enter
            </Button>
          </Tooltip>
          <Tooltip label={t("tip.term_esc", "Send the Escape key")}>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onSendKey("Escape")}
            >
              Esc
            </Button>
          </Tooltip>
          <Tooltip label={t("tip.term_ctrlc", "Send Ctrl-C (interrupt)")}>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onSendKey("C-c")}
            >
              Ctrl-C
            </Button>
          </Tooltip>
        </>
      )}
      {/* Zoom = font cell size; the pane reflows to the new cell count. */}
      <Tooltip label={t("terminal.zoom_out", "Zoom out")}>
        <Button size="sm" variant="outline" onClick={() => onZoom(-1)}>
          A−
        </Button>
      </Tooltip>
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
      <Tooltip label={t("terminal.zoom_in", "Zoom in")}>
        <Button size="sm" variant="outline" onClick={() => onZoom(1)}>
          A+
        </Button>
      </Tooltip>
      <Tooltip
        label={
          fullscreen
            ? t("tip.term_fs_exit", "Exit fullscreen")
            : t("tip.term_fs_enter", "Fullscreen")
        }
      >
        <Button size="sm" variant="outline" onClick={onToggleFullscreen}>
          {fullscreen ? "⤱" : "⤢"}
        </Button>
      </Tooltip>
      <Tooltip
        label={t(
          "tip.term_redraw",
          "Redraw — fixes a garbled display after interactive menus (/model, /effort…)",
        )}
      >
        <Button size="sm" variant="outline" onClick={onRedraw}>
          ⟳
        </Button>
      </Tooltip>
      <Tooltip label={t("tip.term_close", "Close the terminal")}>
        <Button size="sm" variant="ghost" onClick={onClose}>
          {t("terminal.close", "Close")}
        </Button>
      </Tooltip>
      {/* Kill = end the Claude session/agent. Destructive → 2-step confirm. Needs control. */}
      {armed &&
        (killConfirm ? (
          <>
            <Button size="sm" tone="destructive" onClick={onKill}>
              {t("terminal.kill_confirm", "Confirm kill?")}
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancelKill}>
              {t("body.cancel", "Cancel")}
            </Button>
          </>
        ) : (
          <Tooltip
            label={t(
              "tip.term_kill",
              "End the Claude session and the agent (no need to type exit)",
            )}
          >
            <Button size="sm" variant="outline" onClick={onArmKill}>
              {t("terminal.kill", "Kill")}
            </Button>
          </Tooltip>
        ))}
    </div>
  );
}

/** A single keycap, shadcn-style (mono, bordered, subtle bottom edge), theme-aware via tokens. */
function Kbd({ children }) {
  return (
    <kbd
      style={{
        display: "inline-block",
        fontFamily: TERM_FONT_FAMILY,
        fontSize: 11,
        lineHeight: 1.5,
        padding: "0 6px",
        color: "var(--foreground)",
        background: "var(--muted)",
        border: "1px solid var(--border)",
        borderBottomWidth: 2,
        borderRadius: 5,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </kbd>
  );
}

/** A chord (e.g. Ctrl + Shift + F) rendered as Kbd caps joined by "+". */
function Chord({ keys }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
      {keys.map((k, i) => (
        <React.Fragment key={k}>
          {i > 0 && (
            <span style={{ color: "var(--muted-foreground)", fontSize: 11 }}>
              +
            </span>
          )}
          <Kbd>{k}</Kbd>
        </React.Fragment>
      ))}
    </span>
  );
}

/**
 * Documentation / cheatsheet shown beneath the terminal: how the viewer works plus the useful
 * keys. The Ctrl+Shift chords are intercepted before they reach the agent (AgentTerminal mount
 * effect); the single keys are sent to the agent only while you hold control.
 */
function TerminalHelp({ t }) {
  const shortcuts = [
    {
      keys: ["Ctrl", "Shift", "I"],
      desc: t(
        "term_help.toggle_control",
        "Take / release control — start or stop typing to the agent",
      ),
    },
    {
      keys: ["Ctrl", "Shift", "F"],
      desc: t("term_help.toggle_fullscreen", "Enter / exit fullscreen"),
    },
    {
      keys: ["Enter"],
      desc: t("term_help.enter", "Send a newline (only while in control)"),
    },
    {
      keys: ["Esc"],
      desc: t("term_help.esc", "Send Escape (only while in control)"),
    },
    {
      keys: ["Ctrl", "C"],
      desc: t(
        "term_help.ctrlc",
        "Interrupt the running command (only while in control)",
      ),
    },
  ];
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        background: "var(--card)",
        padding: "10px 12px",
        fontSize: 12,
        lineHeight: 1.55,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          color: "var(--muted-foreground)",
        }}
      >
        {t("term_help.title", "Keyboard & how it works")}
      </div>
      <p style={{ margin: 0, color: "var(--muted-foreground)" }}>
        {t(
          "term_help.intro",
          "This is the agent's live terminal, read-only by default. Take control to send your keystrokes straight to the agent; the red border means you are in control. On mobile, Take control opens the keyboard. Click the terminal first so it has focus, then use the shortcuts below. If an interactive menu (/model, /effort…) garbles the display, press ⟳ Redraw, or type /clear in the agent.",
        )}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {shortcuts.map((s) => (
          <div
            key={s.keys.join("+")}
            style={{ display: "flex", alignItems: "center", gap: 9 }}
          >
            <span style={{ minWidth: 118 }}>
              <Chord keys={s.keys} />
            </span>
            <span style={{ color: "var(--muted-foreground)" }}>{s.desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
