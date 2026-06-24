# rudder — directional arrow buttons for the agent terminal (mobile)

- **Ticket**: #84 · **track**: lite · **roadmap**: rudder · **bump**: minor (0.21.0 → 0.22.0)

## Problem

In the live agent terminal (`web/src/components/AgentTerminal.jsx`, tiller §5), when an agent
shows an interactive menu (e.g. choosing between several proposals, `/model`, `/effort`), the
selection is moved with the keyboard arrow keys. On **mobile**, the soft keyboard has **no arrow
keys**, so the operator cannot move the selection. The terminal already offers on-screen quick-key
buttons for keys phones lack (Enter / Esc / Ctrl-C); it is missing the directional ones.

## Change (bounded, mechanical)

Extend the existing on-screen quick-key mechanism with four directional buttons. No new dependency,
no server change — the buttons reuse the exact same `onSendKey` → `KEY_BYTES` → `{type:"input"}`
WebSocket path the existing quick keys already use (`AgentTerminal.jsx:253-261`, `:391-421`).

The bytes are the standard ANSI cursor-key (DECCKM-off / normal-mode) escape sequences that xterm
emits and Claude's Ink TUI / readline menus consume — same raw-byte style already used for
`Escape: "\x1b"` (`AgentTerminal.jsx:26`):

| Button | name   | bytes      |
| ------ | ------ | ---------- |
| ↑      | `Up`    | `\x1b[A`   |
| ↓      | `Down`  | `\x1b[B`   |
| →      | `Right` | `\x1b[C`   |
| ←      | `Left`  | `\x1b[D`   |

## Checklist plan

1. `web/src/components/AgentTerminal.jsx` — extend `KEY_BYTES` (`:26`) with the four entries above
   (`Up`/`Down`/`Right`/`Left`). `sendKey` (`:254`) already dispatches any `KEY_BYTES` name while
   armed, so no logic change is needed there.
2. Same file, `ControlBar` armed-quick-keys block (`:391-421`) — add four `Button` (`size="sm"
   variant="outline"`) wrapped in `Tooltip`, labelled `↑ ↓ ← →`, each calling
   `onSendKey("Up"|"Down"|"Right"|"Left")`. Place them in the existing `armed && (<>…</>)` group,
   next to Enter/Esc/Ctrl-C. Match the existing button/tooltip JSX shape exactly.
3. i18n — add the four tooltip strings under `tip:` in **both** `web/src/i18n/en.yaml` (`:524`) and
   `web/src/i18n/fr.yaml` (`:536`), mirroring the existing `tip.term_enter` / `term_esc` /
   `term_ctrlc` keys: `tip.term_up`, `tip.term_down`, `tip.term_left`, `tip.term_right`
   (EN: "Send the Up/Down/Left/Right arrow"; FR: "Envoie la flèche Haut/Bas/Gauche/Droite"). Use
   `t("tip.term_up", "Send the Up arrow")` with an English fallback, consistent with the file.
4. Optional polish: add an `Arrow keys` row to the `TerminalHelp` cheatsheet (`:543`) — non-blocking;
   keep if trivial, skip otherwise.

## Verification

The `web/` SPA has **no JS test framework** (only `dev`/`build`/`preview` scripts; zero `*.test.*`
files) — verification mirrors the repo's UI convention: `npm run build` succeeds, then manual check
in the live terminal that ↑/↓ move the selection in an agent menu and ←/→ move the cursor. No Python
layer is touched, so `make lint` / `make test` are unaffected; bump `VERSION`, `pyproject.toml`,
`src/kanbanmate/__init__.py` and the plugin manifest to `0.22.0` per the project's version-sync rule.

## Notes

- **No server-side change**: `/api/monitor/agent/{issue}/attach` already forwards raw input bytes
  verbatim; arrow sequences are just more raw bytes through the same `{type:"input"}` frame.
- **Not a re-routable decision**: this is a purely additive UI affordance over an existing,
  proven byte-forwarding path — no design question, no irreversible choice.
- **Known limitation (normal-mode only)**: the buttons always send the **DECCKM-off / normal-mode**
  sequences (`\x1b[A`…), whereas the native keyboard path (xterm.js `term.onData`) is DECCKM-aware
  and emits the SS3 form (`\x1bOA`…) when a TUI enables *application* cursor-keys mode. The two paths
  can therefore diverge for a full-screen app that flips DECCKM on (e.g. vim/less inside the agent
  shell): the button would be inert there. This is acceptable for the target use case — Claude's
  Ink/readline menus consume normal-mode sequences — and is reversible (a future enhancement could
  read `term.modes.applicationCursorKeysMode` and pick `O` vs `[` at send time to match the keyboard
  path). Worst case is a non-functional button, never an unsafe input.
