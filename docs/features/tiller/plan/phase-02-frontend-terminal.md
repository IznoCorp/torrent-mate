# Phase 2 — Frontend terminal

## Gate

**Phase 1 must be COMPLETE before starting Phase 2.**

Required artifacts:

- `src/kanbanmate/http/agent_terminal.py` exists and is registered.
- `GET /api/monitor/agent/{issue}/attach` WS endpoint reachable (manually verify with `kanban
config serve` + a browser WS client, or trust the Phase 1 tests).
- `make check` green on the Phase 1 commit.

## Overview

Install xterm.js, implement `AgentTerminal.jsx` (WS client, pane render, onData, fit-addon resize),
add the control toggle + quick-keys + fullscreen + mobile soft-keyboard, and mount the terminal in
`MonitoringPanel.jsx`. Five commits — one per sub-phase. No Python changes in this phase.

---

## Sub-phase 2.1 — xterm.js dependency

**Commit:** `chore(tiller): add xterm.js + addon-fit to web deps`

**Files touched:**

- Modify: `web/package.json`

**What to implement:**

Add to the `"dependencies"` object in `web/package.json`:

```json
"xterm": "^5.3.0",
"@xterm/addon-fit": "^0.8.0"
```

The full `dependencies` block becomes:

```json
"dependencies": {
  "@codemirror/lang-markdown": "^6.5.0",
  "@codemirror/language-data": "^6.5.2",
  "@uiw/react-codemirror": "^4.25.10",
  "@xterm/addon-fit": "^0.8.0",
  "marked": "^14.1.0",
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "xterm": "^5.3.0"
}
```

Then install:

```bash
npm --prefix web install
```

Expected: package-lock.json updated, `web/node_modules/xterm/` present.

Verify:

```bash
ls web/node_modules/xterm/package.json
```

Expected: file exists.

---

## Sub-phase 2.2 — AgentTerminal.jsx (core WS + render)

**Commit:** `feat(tiller): add AgentTerminal.jsx — WS client + xterm render`

**Files touched:**

- Create: `web/src/components/AgentTerminal.jsx`

**What to implement:**

```jsx
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
 * @param {{ issue: number, onClose: () => void }} props
 */
export default function AgentTerminal({ issue, onClose }) {
  const { t } = useT();
  const containerRef = React.useRef(null);
  const termRef = React.useRef(null);
  const fitRef = React.useRef(null);
  const wsRef = React.useRef(null);
  const [armed, setArmed] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [ended, setEnded] = React.useState(false);

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
        if (msg.alive === false) {
          setEnded(true);
          term.write("\r\n[session ended]\r\n");
          ws.close();
          return;
        }
        if (msg.data) term.write(msg.data);
        if (msg.error) setError(msg.error);
      } catch (_) {}
    };
    ws.onerror = () => setError("WebSocket error");
    ws.onclose = () => setEnded(true);

    // onData → send text frames when armed
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN && armed) {
        ws.send(JSON.stringify({ type: "text", data }));
      }
    });

    // ResizeObserver → fit + resize frame
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

  // Keep onData closure fresh when `armed` changes
  React.useEffect(() => {
    const term = termRef.current;
    if (!term) return;
    const d = term.onData((data) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && armed) {
        ws.send(JSON.stringify({ type: "text", data }));
      }
    });
    return () => d.dispose();
  }, [armed]);

  const sendMsg = (msg) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  };

  const toggleControl = () => {
    if (!armed) {
      sendMsg({ type: "take_control" });
      setArmed(true);
    } else {
      sendMsg({ type: "release_control" });
      setArmed(false);
    }
  };

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
        style={{
          height: 320,
          background: "#1e1e1e",
          borderRadius: 6,
          overflow: "hidden",
          border: armed
            ? "2px solid var(--destructive)"
            : "1px solid var(--border)",
        }}
      />
      <ControlBar
        armed={armed}
        onToggle={toggleControl}
        onSendKey={(k) => armed && sendMsg({ type: "key", name: k })}
        onClose={onClose}
        t={t}
      />
    </div>
  );
}

function ControlBar({ armed, onToggle, onSendKey, onClose, t }) {
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
          ? t("terminal.release", "Rendre la main")
          : t("terminal.take_control", "Prendre le contrôle")}
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
      <Button size="sm" variant="ghost" onClick={onClose}>
        {t("terminal.close", "Fermer")}
      </Button>
    </div>
  );
}
```

Verify the build:

```bash
npm --prefix web run build 2>&1 | tail -5
```

Expected: exit 0, no errors about missing `xterm` imports.

---

## Sub-phase 2.3 — Control toggle + quick-keys + i18n strings

**Commit:** `feat(tiller): control toggle, quick-keys, i18n strings for AgentTerminal`

**Files touched:**

- Modify: `web/src/components/AgentTerminal.jsx` — already contains the control bar from 2.2;
  this sub-phase adds the i18n keys to the locale files.
- Modify: `web/src/i18n/en.json` (or equivalent EN locale file) — add terminal keys.
- Modify: `web/src/i18n/fr.json` (or equivalent FR locale file) — add terminal keys.

First, locate the locale files:

```bash
find web/src/i18n -name "*.json" | head -5
```

Add to each locale file under a `"terminal"` key:

**EN additions:**

```json
"terminal": {
  "take_control": "Take control",
  "release": "Release control",
  "session_ended": "Session ended",
  "close": "Close",
  "interactive": "Interactive terminal"
}
```

**FR additions:**

```json
"terminal": {
  "take_control": "Prendre le contrôle",
  "release": "Rendre la main",
  "session_ended": "Session terminée",
  "close": "Fermer",
  "interactive": "Terminal interactif"
}
```

Verify build still passes:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Sub-phase 2.4 — Fullscreen + mobile soft-keyboard

**Commit:** `feat(tiller): fullscreen toggle + mobile soft-keyboard input for AgentTerminal`

**Files touched:**

- Modify: `web/src/components/AgentTerminal.jsx`

**What to add to `AgentTerminal`:**

Add `fullscreen` state and a toggle button; add a hidden managed `<input>` for mobile
soft-keyboard capture. Replace the container div's style when fullscreen:

```jsx
const [fullscreen, setFullscreen] = React.useState(false);
// Hidden input ref for mobile soft-keyboard
const mobileInputRef = React.useRef(null);

// When armed on mobile, focus the hidden input so the soft keyboard opens
React.useEffect(() => {
  if (armed && mobileInputRef.current) {
    mobileInputRef.current.focus();
  }
}, [armed]);

const handleMobileInput = (e) => {
  const val = e.target.value;
  if (!val) return;
  sendMsg({ type: "text", data: val });
  e.target.value = "";
};

// Fullscreen container style
const containerStyle = fullscreen
  ? {
      position: "fixed",
      inset: 0,
      zIndex: 9999,
      background: "#1e1e1e",
      borderRadius: 0,
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
    };
```

Add fullscreen toggle button to `ControlBar` (pass `fullscreen` + `onFullscreen` props):

```jsx
<Button size="sm" variant="outline" onClick={onFullscreen}>
  {fullscreen ? "⤡" : "⤢"}
</Button>
```

Add the hidden mobile input (rendered always, visible never):

```jsx
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
```

Fullscreen fit: in the ResizeObserver + on `fullscreen` state change, call `fit.fit()`.

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Sub-phase 2.5 — Mount in MonitoringPanel

**Commit:** `feat(tiller): mount AgentTerminal in MonitoringPanel for running agents`

**Files touched:**

- Modify: `web/src/panels/MonitoringPanel.jsx`

**What to add:**

1. Import `AgentTerminal` at the top:

```jsx
import AgentTerminal from "../components/AgentTerminal.jsx";
```

2. Add `terminalOpen` state (tracks whether the terminal is shown for the selected ticket):

```jsx
const [terminalOpen, setTerminalOpen] = React.useState(false);
// Reset terminal when selection changes
React.useEffect(() => {
  setTerminalOpen(false);
}, [sel]);
```

3. After the existing pane-tail render, add the terminal mount. The terminal is shown when:
   - A ticket is selected (`sel != null`)
   - It has a running agent (`agents.some(a => a.issue_number === sel && a.alive)`)
   - `terminalOpen` is true

```jsx
{
  sel != null && agents.some((a) => a.issue_number === sel && a.alive) && (
    <div style={{ marginTop: 12 }}>
      {!terminalOpen ? (
        <Button size="sm" onClick={() => setTerminalOpen(true)}>
          {t("terminal.interactive", "Terminal interactif")}
        </Button>
      ) : (
        <AgentTerminal issue={sel} onClose={() => setTerminalOpen(false)} />
      )}
    </div>
  );
}
```

4. When `terminalOpen` is true, collapse the static pane tail (the terminal is the live pane):

```jsx
{!terminalOpen && pane != null && (
  <pre style={{ ...existing pane tail styles... }}>{pane}</pre>
)}
```

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -5
```

Expected: exit 0. Verify xterm in bundle:

```bash
grep -r "xterm" web/dist/assets/*.js | head -3
```

Expected: matches found (xterm bundled).

---

## Definition of Done

- [ ] `npm --prefix web ci && npm --prefix web run build` → exit 0.
- [ ] `grep -r "xterm" web/dist/assets/*.js | head -1` → non-empty (xterm bundled).
- [ ] `make check` → green (Python side unchanged, lint covers JS via build).
- [ ] `web/src/components/AgentTerminal.jsx` exists with control toggle, quick-keys, fullscreen,
      and mobile input.
- [ ] `web/src/panels/MonitoringPanel.jsx` imports and mounts `AgentTerminal`.
