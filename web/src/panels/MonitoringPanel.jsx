// Monitoring tab (helm PR 2-bis) — read-only live board + ticket detail + agent panel + pane tail.
// Polling: agents + pane ~3 s, board + tracks ~4 s, ticket detail on open. The board placement now
// reads the LOCAL board.json (keel STEP 2 — <5 ms, no GitHub gating), so a 4 s cadence matching the
// agents poll is affordable; the version int the board API returns lets the SPA skip re-render when
// unchanged. Pauses when the tab is hidden. Read-only — to interact with an agent use `tmux attach`.
import React from "react";
import {
  ChevronDown,
  ChevronRight,
  Pencil,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { renderMarkdown } from "../lib/markdown.js";
import { extractFreeform } from "../lib/body.js";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { MobileBack } from "../components/MobileMasterDetail.jsx";
import AgentTerminal from "../components/AgentTerminal.jsx";
import MarkdownReader from "../components/MarkdownReader.jsx";
import MarkdownField from "../components/MarkdownField.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const { KeyChip, Badge, Banner, Button, Select, Tooltip } =
  window.KanbanMateDesignSystem_2463ad;

const STATE_TONE = { running: "accent", waiting: "amber", blocked: "red" };

// Fast-track lane options (skiff). The closed vocabulary is full/lite/express; "" (Auto) clears the
// label. Shared by the detail-panel Track selector and the compact per-row selector so they can't
// drift. `t` is the i18n lookup so the labels localize.
function trackOptions(t) {
  return [
    { value: "", label: t("monitor.track_auto", "Auto") },
    { value: "full", label: t("monitor.track_full", "Full") },
    { value: "lite", label: t("monitor.track_lite", "Lite") },
    { value: "express", label: t("monitor.track_express", "Express") },
  ];
}

// Square icon-button used to collapse/expand the master ticket-list column (sidebar-style).
// Same footprint as a collapsed-rail ticket chip (34×28, radius 7) so the toggle aligns vertically
// with the minified ticket buttons below it.
const MASTER_TOGGLE_STYLE = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 34,
  height: 28,
  padding: 0,
  flexShrink: 0,
  background: "transparent",
  border: "1px solid var(--border)",
  borderRadius: 7,
  color: "var(--muted-foreground)",
  cursor: "pointer",
};

// Compact, dark-mode-aware status note (colored dot + text). Replaces the Banner "sections" that were
// illegible (light-on-light) in dark mode for launch/move feedback.
function StatusNote({ tone, children }) {
  const dot =
    tone === "red"
      ? "var(--health-blocked-fg, #e0494e)"
      : tone === "amber"
        ? "var(--health-waiting-fg, #d98e29)"
        : "var(--health-active-fg, #1f9d54)";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 12,
        color: "var(--muted-foreground)",
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: dot,
          flexShrink: 0,
        }}
      />
      <span>{children}</span>
    </div>
  );
}

// Poll an intent's result so the UI shows the REAL outcome (done / rejected / held) instead of an
// optimistic "queued". Returns the terminal result, or null if it stays pending past the budget.
async function pollIntentResult(intentId, project) {
  for (let i = 0; i < 8; i++) {
    await new Promise((r) => setTimeout(r, 1200));
    try {
      const res = await api.intentResult(intentId, project);
      if (
        res &&
        res.state &&
        res.state !== "pending" &&
        res.state !== "claimed"
      ) {
        return res;
      }
    } catch (_) {
      /* keep polling — a transient error shouldn't abort */
    }
  }
  return null;
}

// Format a GitHub ISO timestamp ("2026-06-21T08:48:01Z") into the operator's locale, in LOCAL time:
//   fr → DD/MM/YYYY HH:MM:SS   ·   en → YYYY/MM/DD HH:MM:SS
// Falls back to the raw string when unparseable.
function fmtCommentDate(iso, lang) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n) => String(n).padStart(2, "0");
  const Y = d.getFullYear();
  const M = p(d.getMonth() + 1);
  const D = p(d.getDate());
  const time = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  return lang === "fr" ? `${D}/${M}/${Y} ${time}` : `${Y}/${M}/${D} ${time}`;
}

// Poll `fn` every `ms` while the tab is visible; runs once immediately. `deps` re-arm the interval.
function usePoll(fn, ms, deps) {
  React.useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") fn();
    };
    tick();
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

// Track which edges of a soft-scroll container should fade: bottom while there is more below, top
// once you've scrolled down (so you can tell you can scroll back up). Recomputes on scroll, on
// resize, and whenever `deps` change the content (board poll / collapse). Returns { top, bottom }.
function useScrollFade(ref, deps) {
  const [edges, setEdges] = React.useState({ top: false, bottom: false });
  React.useEffect(() => {
    const el = ref.current;
    if (!el) {
      setEdges({ top: false, bottom: false });
      return;
    }
    const update = () => {
      const top = el.scrollTop > 4;
      const bottom = el.scrollTop + el.clientHeight < el.scrollHeight - 4;
      setEdges((e) =>
        e.top === top && e.bottom === bottom ? e : { top, bottom },
      );
    };
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return edges;
}

// CSS mask gradient for the active fade edges (a `px`-tall fade). "none" when neither edge fades, so
// a non-overflowing list is fully crisp. Alpha gradient: transparent = hidden, #000 = shown.
function fadeMask({ top, bottom }, px = 24) {
  if (!top && !bottom) return "none";
  const head = top ? `transparent 0, #000 ${px}px` : "#000 0";
  const tail = bottom
    ? `#000 calc(100% - ${px}px), transparent 100%`
    : "#000 100%";
  return `linear-gradient(to bottom, ${head}, ${tail})`;
}

export default function MonitoringPanel({ project }) {
  const { t, lang } = useT();
  const isMobile = useIsMobile();
  const [board, setBoard] = React.useState(null);
  const [agents, setAgents] = React.useState([]);
  // Persisted across reloads (#47): the open ticket + the per-group collapse overrides.
  const [sel, setSel] = React.useState(() => {
    try {
      const v = localStorage.getItem("bridge.monitor.ticket");
      return v ? Number(v) : null;
    } catch (_) {
      return null;
    }
  });
  const [detail, setDetail] = React.useState(null);
  const [pane, setPane] = React.useState(null);
  const [error, setError] = React.useState(null); // ticket-detail / save errors (not the board)
  // Board-poll health is tracked SEPARATELY so the stale-board note self-heals on the next good poll
  // and can't be triggered by an unrelated ticket-detail/save failure (cycle-2 regression fix).
  const [boardError, setBoardError] = React.useState(null);
  const [collapsedOverride, setCollapsedOverride] = React.useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem("bridge.monitor.collapsed") || "{}",
      );
    } catch (_) {
      return {};
    }
  });
  React.useEffect(() => {
    try {
      if (sel == null) localStorage.removeItem("bridge.monitor.ticket");
      else localStorage.setItem("bridge.monitor.ticket", String(sel));
    } catch (_) {
      /* storage may be unavailable (private mode) */
    }
  }, [sel]);
  const [terminalOpen, setTerminalOpen] = React.useState(false);
  // Ad-hoc agent launch (no transition) — shown when the selected ticket has no running agent.
  const [launchPrompt, setLaunchPrompt] = React.useState("");
  const [launchProfile, setLaunchProfile] = React.useState("dev");
  const [launching, setLaunching] = React.useState(false);
  const [launchMsg, setLaunchMsg] = React.useState(null); // { tone, text } | null
  // Status-change (column move) from the ticket detail.
  const [moving, setMoving] = React.useState(false);
  const [moveMsg, setMoveMsg] = React.useState(null); // { tone, text } | null
  // Optimistic destination KEY after a successful move: the detail/board snapshot can lag (the
  // mirror to GitHub is eventual + cached), so without this the controlled Select snaps back to the
  // old column. Cleared on ticket switch and once the snapshot reconciles to it.
  const [optimisticCol, setOptimisticCol] = React.useState(null);
  // Fast-track lane per ticket (skiff): { "<number>": "full"|"lite"|"express" } from the board poll.
  // The row + detail Track selectors read their current value here; an optimistic write updates it
  // immediately, then the next board poll reconciles. A ticket absent from the map = Auto (no label).
  const [boardTracks, setBoardTracks] = React.useState({});
  const [tracking, setTracking] = React.useState(false); // a track write is in flight (disable selects)
  const [trackMsg, setTrackMsg] = React.useState(null); // { tone, text } | null (detail-panel note)
  // Edit description state (tiller §3.4) — marker-safe freeform edit via PATCH endpoint.
  const [editMode, setEditMode] = React.useState(false);
  const [editFreeform, setEditFreeform] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [descOpen, setDescOpen] = React.useState(() => {
    try {
      return localStorage.getItem("bridge.monitor.descOpen") === "true";
    } catch (_) {
      return false;
    }
  });
  // Collapse the master ticket-list column (like the sidebar) so the detail spans the full width.
  const [masterCollapsed, setMasterCollapsed] = React.useState(() => {
    try {
      return localStorage.getItem("bridge.monitor.masterCollapsed") === "true";
    } catch (_) {
      return false;
    }
  });
  const toggleMaster = () => {
    setMasterCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("bridge.monitor.masterCollapsed", String(next));
      } catch (_) {
        /* storage may be unavailable */
      }
      return next;
    });
  };
  // Keep the selected ticket visible in the (full-height, scrollable) master list: scroll it into
  // view when the selection changes, the list is collapsed/expanded, or the board first loads (a
  // persisted #47 selection on reload). block:"nearest" scrolls only the list container, not the
  // page. The ref attaches to whichever the selected ticket renders as (expanded row / rail chip).
  const selectedRowRef = React.useRef(null);
  React.useEffect(() => {
    selectedRowRef.current?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
    });
  }, [sel, masterCollapsed, board != null]);
  // Soft-scroll fade for the master list / rail (native scrollbar hidden via km-scroll-soft). One
  // ref is attached to whichever of the two containers is rendered (expanded vs collapsed rail);
  // recompute when the content/element changes (board poll, collapse toggle, per-group collapse).
  const listRef = React.useRef(null);
  const scrollFade = useScrollFade(listRef, [
    board,
    masterCollapsed,
    collapsedOverride,
  ]);
  const scrollMask = fadeMask(scrollFade);
  // Reset terminal visibility when the selected ticket changes.
  React.useEffect(() => {
    setTerminalOpen(false);
    setLaunchPrompt("");
    setLaunchMsg(null);
    setLaunching(false);
    setMoveMsg(null);
    setMoving(false);
    setTrackMsg(null);
  }, [sel]);
  const doMove = async (toCol) => {
    if (sel == null || !toCol) return;
    setMoving(true);
    setMoveMsg({
      tone: "amber",
      text: t(
        "monitor.move_queued",
        "Move queued — the board updates shortly.",
      ),
    });
    try {
      const r = await api.moveTicket(sel, toCol, project);
      const res =
        r && r.intent_id ? await pollIntentResult(r.intent_id, project) : null;
      if (res && res.state !== "done") {
        setMoveMsg({ tone: "red", text: res.detail || res.state });
      } else if (res) {
        setMoveMsg({
          tone: "green",
          text: t("monitor.move_done", "Card moved."),
        });
        // Reflect the new column in the Select NOW (the snapshot lags); the override clears once the
        // board catches up.
        setOptimisticCol(toCol);
        // Re-fetch the detail so the status select reflects the NEW column immediately (the select
        // value derives from detail.move_targets/column_key; the [sel] effect won't re-run here).
        try {
          const d = await api.monitorTicket(sel, project);
          setDetail(d);
        } catch (_) {
          /* the 15s board poll will reconcile if this fails */
        }
      }
    } catch (e) {
      setMoveMsg({ tone: "red", text: String((e && e.message) || e) });
    } finally {
      setMoving(false);
    }
  };
  // Set (or clear) a ticket's fast-track lane (skiff). `track` is "full"|"lite"|"express" or "" → null
  // (the "Auto" choice, which clears the label). Optimistic: update the boardTracks map NOW so both the
  // row and the detail selector reflect the choice immediately, then refetch the ticket detail to
  // reconcile (mirrors the move handler). The 15s board-tracks poll is the eventual backstop.
  const doTrack = async (number, track) => {
    if (number == null) return;
    const lane = track || null; // "" (Auto) → null clears the label
    const prev = boardTracks; // snapshot for rollback on failure
    setTracking(true);
    setTrackMsg({
      tone: "amber",
      text: t("monitor.track_queued", "Track update queued…"),
    });
    // Optimistic update of the per-ticket map (drop the key when clearing to Auto).
    setBoardTracks((m) => {
      const next = { ...m };
      if (lane) next[String(number)] = lane;
      else delete next[String(number)];
      return next;
    });
    try {
      await api.setTicketTrack(number, lane, project);
      setTrackMsg({
        tone: "green",
        text: t("monitor.track_done", "Track updated."),
      });
      // Refetch the detail so its `track` field reflects the new label (the [sel] effect won't re-run).
      if (sel === number) {
        try {
          const d = await api.monitorTicket(number, project);
          setDetail(d);
        } catch (_) {
          /* the board-tracks poll will reconcile if this fails */
        }
      }
    } catch (e) {
      setBoardTracks(prev); // roll back the optimistic change
      setTrackMsg({ tone: "red", text: String((e && e.message) || e) });
    } finally {
      setTracking(false);
    }
  };
  const doLaunch = async () => {
    // Prompt is OPTIONAL — an empty prompt launches a bare claude the operator drives via the terminal.
    const prompt = launchPrompt.trim();
    if (sel == null) return;
    setLaunching(true);
    setLaunchMsg({
      tone: "amber",
      text: t(
        "monitor.launch_queued",
        "Agent launch queued — it will appear shortly.",
      ),
    });
    try {
      const r = await api.launchAgent(
        sel,
        { prompt, profile: launchProfile },
        project,
      );
      setLaunchPrompt("");
      const res =
        r && r.intent_id ? await pollIntentResult(r.intent_id, project) : null;
      if (res && res.state !== "done") {
        // e.g. an older daemon that doesn't know the launch kind → show the real rejection.
        setLaunchMsg({ tone: "red", text: res.detail || res.state });
      } else if (res) {
        setLaunchMsg({
          tone: "green",
          text: t("monitor.launch_done", "Agent launched."),
        });
      }
    } catch (e) {
      setLaunchMsg({ tone: "red", text: String((e && e.message) || e) });
    } finally {
      setLaunching(false);
    }
  };
  const toggleCollapse = (key, isCollapsed) => {
    setCollapsedOverride((prev) => {
      const next = { ...prev, [key]: !isCollapsed };
      try {
        localStorage.setItem("bridge.monitor.collapsed", JSON.stringify(next));
      } catch (_) {
        /* storage may be unavailable */
      }
      return next;
    });
  };
  const toggleDesc = () => {
    setDescOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("bridge.monitor.descOpen", String(next));
      } catch (_) {
        /* storage may be unavailable */
      }
      return next;
    });
  };

  usePoll(
    () =>
      api
        .monitorBoard(project)
        .then((b) => {
          // Skip the state update (→ no re-render) when the board is byte-identical to the last
          // poll: with the keel STEP 2 local-placement read + the faster 4 s cadence, most polls
          // return an unchanged board, so a deep-equal guard avoids needless re-renders.
          setBoard((prev) =>
            prev && JSON.stringify(prev) === JSON.stringify(b) ? prev : b,
          );
          setBoardError(null); // a good poll clears the staleness note
        })
        .catch((e) => setBoardError(e.message)),
    4000,
    [project],
  );
  // Per-ticket fast-track lanes (skiff), polled alongside the board (~4 s, matching the board +
  // agents cadence). Skip while a track write is in flight so a mid-poll response can't clobber the
  // optimistic boardTracks update; the next poll reconciles. A bad poll is swallowed (the selectors
  // just keep their last-known values). NOTE: this read still hits GitHub for the track:* labels, so
  // it is the one poll that is NOT purely local — kept at the same cadence for a coherent refresh.
  usePoll(
    () => {
      if (tracking) return;
      api
        .getBoardTracks(project)
        .then((r) =>
          setBoardTracks(
            r && r.tracks && typeof r.tracks === "object" ? r.tracks : {},
          ),
        )
        .catch(() => {});
    },
    4000,
    [project, tracking],
  );
  usePoll(
    () =>
      api
        .monitorAgents(project)
        // Guard against a 200 body lacking `agents` (contract drift / 200 error envelope): keep
        // `agents` ALWAYS an array, else later `agents.find/.some` would crash the panel.
        .then((r) => setAgents(Array.isArray(r?.agents) ? r.agents : []))
        .catch(() => {}),
    3000,
    [project],
  );

  React.useEffect(() => {
    if (sel == null) return;
    setDetail(null);
    setOptimisticCol(null); // new ticket → drop any optimistic move override
    setError(null); // clear a previous ticket's detail/save error (no latch)
    api
      .monitorTicket(sel, project)
      .then((d) => {
        setDetail(d);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [sel, project]);

  const selAgent = agents.find((a) => a.issue === sel);
  usePoll(
    () => {
      if (sel != null && selAgent)
        api
          .monitorPane(sel, project)
          .then(setPane)
          .catch(() => {});
      else setPane(null);
    },
    3000,
    [sel, project, !!selAgent],
  );

  // Artifact reader (brainstorm/design/plans) — opened from the ticket detail.
  const [reader, setReader] = React.useState(null);
  const openFile = (title, path) => {
    setReader({
      title,
      subtitle: path,
      loading: true,
      content: "",
      error: null,
    });
    api
      // Pass the ticket (sel) so the endpoint can fall back to the kanban/ticket-<n> WIP branch
      // when an in-flight design/plan isn't on the clone's checked-out tree.
      .monitorFile(path, project, sel)
      .then((r) =>
        setReader({
          title,
          subtitle: r.path,
          loading: false,
          content: r.content,
          error: null,
        }),
      )
      .catch((e) =>
        setReader({
          title,
          subtitle: path,
          loading: false,
          content: "",
          error: e.message,
        }),
      );
  };
  const openText = (title, content) =>
    setReader({ title, subtitle: "", loading: false, content, error: null });

  // Open the body edit mode — extract freeform from the current body.
  const openEdit = () => {
    setEditFreeform(extractFreeform(detail?.body || ""));
    setEditMode(true);
    setDescOpen(true); // expand accordion so the editor is visible
  };
  // Save edited freeform via PATCH, then refresh the ticket detail.
  const saveEdit = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.patchTicketBody(sel, editFreeform, project);
      setEditMode(false);
      const d = await api.monitorTicket(sel, project);
      setDetail(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  // Drop the optimistic column override once the real snapshot reflects it (or the card moved
  // elsewhere), so it never masks reality. Hoisted ABOVE the board/detail early-returns below so it
  // runs on EVERY render — a hook placed after a conditional return crashes with React #310 ("more
  // hooks than the previous render") the moment `board` flips from null (loading) to loaded.
  React.useEffect(() => {
    if (!optimisticCol || !board) return;
    const opts =
      detail?.move_targets ||
      board.columns.map((c) => ({
        key: c.key,
        current: c.name === detail?.column_key || c.key === detail?.column_key,
      }));
    const reconciled =
      (opts.find((m) => m.current) || {}).key ||
      (detail ? detail.column_key : "");
    if (reconciled === optimisticCol) setOptimisticCol(null);
  }, [optimisticCol, detail, board]);

  // Derived artifact sources from the loaded detail (null/[] when no detail yet).
  const brainstorm = detail ? brainstormSection(detail.body) : null;
  const planPaths = detail?.markers?.plans
    ? detail.markers.plans
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean)
    : [];

  if (boardError && !board)
    return (
      <Banner tone="error" title={t("monitor.intro_title")}>
        {boardError}
      </Banner>
    );
  if (!board) return <div style={{ padding: 24 }}>{t("common.loading")}</div>;

  const s = board.agents_summary;

  // Column options for the status-change select. Prefer the backend's workflow-aware `move_targets`
  // (allowed = a transition exists from the current column); fall back to all columns when absent.
  const moveOptions = detail
    ? detail.move_targets ||
      board.columns.map((c) => ({
        key: c.key,
        name: c.name,
        current: c.name === detail.column_key || c.key === detail.column_key,
        allowed: c.name !== detail.column_key && c.key !== detail.column_key,
      }))
    : [];
  // Fall back to the ticket's actual column when no option is flagged current, so the Select never
  // renders blank (which would misrepresent the ticket's column and move from an unknown baseline).
  const reconciledMoveKey =
    (moveOptions.find((m) => m.current) || {}).key ||
    (detail ? detail.column_key : "");
  // Prefer the optimistic destination until the (lagging) snapshot catches up to it.
  const currentMoveKey = optimisticCol || reconciledMoveKey;

  // Per-ticket state dot — the colored summary line (running/waiting/blocked) is its legend. The
  // state is the board's own server-computed `agent_state` (running/waiting/blocked, or null for a
  // ticket with no live agent → a muted dot).
  const stateDotColor = (st) => {
    if (st === "running" || st === "active")
      return "var(--health-active-fg, #1f9d54)";
    if (st === "waiting") return "var(--health-waiting-fg, #d98e29)";
    if (st === "blocked") return "var(--health-blocked-fg, #e0494e)";
    return "var(--border)";
  };

  return (
    <div
      style={{
        width: "100%",
        // Desktop: fill the available height so the page itself never scrolls — the master list and
        // the ticket detail scroll INTERNALLY instead. Mobile keeps natural document scroll.
        ...(isMobile
          ? {}
          : {
              height: "100%",
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
            }),
      }}
    >
      <PageIntro title={t("monitor.intro_title")} scope="board">
        {t("monitor.intro_body")}
      </PageIntro>
      {/* Non-blocking staleness indicator: once `board` has loaded, the full-screen error banner
          (gated on `!board`) never renders again, so a later poll failure (token expiry, daemon
          down, 5xx) would silently leave a stale board. Surface it inline as an amber note. */}
      {boardError && (
        <div style={{ marginBottom: 12 }}>
          <StatusNote tone="amber">
            {t("monitor.stale", "Board may be stale — last refresh failed:")}{" "}
            {boardError}
          </StatusNote>
        </div>
      )}
      {/* Ticket-detail / description-save failures (token expiry, 5xx, GitHub 4xx). Cleared on a
          successful detail load / save / ticket switch so it never latches. */}
      {error && (
        <div style={{ marginBottom: 12 }}>
          <StatusNote tone="red">{error}</StatusNote>
        </div>
      )}
      {/* Collapse toggle (fixed, left of the legend so it never shifts the list) + colored summary
          bullets — the legend for the per-ticket state dots in the list. */}
      <div
        style={{
          marginBottom: 12,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        {!isMobile && (
          // When collapsed, center the toggle in a rail-width box (46px) so it sits directly above
          // the minified ticket chips (also centered in the 46px rail) — vertically aligned.
          <div
            style={{
              width: masterCollapsed ? 46 : "auto",
              display: "flex",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <button
              type="button"
              onClick={toggleMaster}
              title={
                masterCollapsed
                  ? t("monitor.show_list", "Show tickets")
                  : t("monitor.hide_list", "Hide tickets")
              }
              style={MASTER_TOGGLE_STYLE}
            >
              {masterCollapsed ? (
                <PanelLeftOpen size={18} strokeWidth={1.75} />
              ) : (
                <PanelLeftClose size={18} strokeWidth={1.75} />
              )}
            </button>
          </div>
        )}
        <div
          style={{
            fontSize: 12,
            color: "var(--muted-foreground)",
            display: "flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "var(--health-active-fg, #1f9d54)",
              flexShrink: 0,
            }}
          />
          <span>
            {s.running} {t("monitor.running")}
          </span>
          <span aria-hidden>·</span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "var(--health-waiting-fg, #d98e29)",
              flexShrink: 0,
            }}
          />
          <span>
            {s.waiting} {t("monitor.waiting")}
          </span>
          <span aria-hidden>·</span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "var(--health-blocked-fg, #e0494e)",
              flexShrink: 0,
            }}
          />
          <span>
            {s.blocked} {t("monitor.blocked")}
          </span>
        </div>
      </div>

      {isMobile && sel != null && (
        <MobileBack onClick={() => setSel(null)} label={`#${sel}`} />
      )}
      <div
        style={{
          display: isMobile ? "block" : "grid",
          gridTemplateColumns: isMobile
            ? undefined
            : `${masterCollapsed ? "46px" : "360px"} 1fr`,
          gap: 16,
          // Desktop: a single full-height row so master + detail scroll internally (no page scroll).
          ...(isMobile
            ? { alignItems: "start" }
            : { flex: 1, minHeight: 0, gridTemplateRows: "minmax(0, 1fr)" }),
        }}
      >
        {/* board overview — columns as groups */}
        {!isMobile && masterCollapsed ? (
          // Minified ticket-list bar: a per-status separator (column abbreviation, like the expanded
          // headers) then one chip per ticket — its BORDER colored by the agent state (legend = the
          // running/waiting/blocked line above). Click a chip to select.
          <div
            ref={listRef}
            className="km-scroll-soft"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              alignItems: "center",
              // Vertical scroll only: a space-taking vertical scrollbar (classic / mouse) would
              // otherwise make the 34–38px chips overflow the 46px rail → a parasitic horizontal
              // scrollbar. overflowX:hidden kills it (overlay scrollbars never showed it).
              overflowX: "hidden",
              overflowY: "auto",
              minHeight: 0,
              paddingTop: 2,
              // Hidden native scrollbar (km-scroll-soft) → top/bottom fade signals scrollability.
              maskImage: scrollMask,
              WebkitMaskImage: scrollMask,
            }}
          >
            {board.columns.map((c) => {
              const tix = board.tickets.filter((tk) => tk.column_key === c.key);
              if (!tix.length) return null;
              return (
                <React.Fragment key={c.key}>
                  {/* Status separator: the column name abbreviated (full name on hover). */}
                  <div
                    title={`${c.name} · ${tix.length}`}
                    style={{
                      width: 38,
                      flexShrink: 0,
                      marginTop: 4,
                      fontFamily: "var(--font-mono)",
                      fontSize: 8,
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                      textAlign: "center",
                      color: "var(--muted-foreground)",
                      borderTop: "1px solid var(--border)",
                      paddingTop: 3,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.name.slice(0, 3)}
                  </div>
                  {tix.map((tk) => {
                    const selected = sel === tk.number;
                    return (
                      <button
                        key={tk.number}
                        ref={selected ? selectedRowRef : undefined}
                        type="button"
                        onClick={() => setSel(tk.number)}
                        title={`#${tk.number} · ${c.name}`}
                        style={{
                          position: "relative",
                          width: 34,
                          height: 28,
                          flexShrink: 0,
                          borderRadius: 7,
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          fontWeight: selected ? 700 : 400,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          // No border (it read like a state color). State = the dot only; selection =
                          // a neutral filled background.
                          border: "none",
                          background: selected ? "var(--muted)" : "var(--card)",
                          color: "var(--foreground)",
                        }}
                      >
                        {tk.number}
                        {/* State dot (same legend as the summary line), top-right corner. */}
                        <span
                          style={{
                            position: "absolute",
                            top: -3,
                            right: -3,
                            width: 9,
                            height: 9,
                            borderRadius: "50%",
                            background: stateDotColor(tk.agent_state),
                            border: "1.5px solid var(--card)",
                          }}
                        />
                      </button>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </div>
        ) : (
          (!isMobile || sel == null) && (
            <div
              ref={listRef}
              className="km-scroll-soft"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 12,
                // Desktop: fill the available height + scroll INTERNALLY (page stays fixed). Mobile:
                // natural document scroll. The group cards below carry flexShrink:0 so they keep
                // their full height and the LIST overflows (→ scrolls) instead of each card being
                // crushed and clipped by its own overflow:hidden (the truncation bug).
                ...(isMobile ? {} : { overflowY: "auto", minHeight: 0 }),
                // Hidden native scrollbar (km-scroll-soft) → top/bottom fade signals scrollability.
                maskImage: scrollMask,
                WebkitMaskImage: scrollMask,
              }}
            >
              {board.columns.map((c) => {
                const tix = board.tickets.filter(
                  (tk) => tk.column_key === c.key,
                );
                // Monitoring shows only columns with at least one ticket (operator 2026-06-21).
                if (!tix.length) return null;
                // Non-empty groups are expanded by default; operator collapse toggles persist (#47).
                const collapsed =
                  c.key in collapsedOverride ? collapsedOverride[c.key] : false;
                return (
                  <div
                    key={c.key}
                    style={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-lg)",
                      overflow: "hidden",
                      boxShadow: "var(--shadow-xs)",
                      // Do NOT shrink: in the fixed-height flex list, the default flex-shrink:1 would
                      // crush a tall group (e.g. Backlog) and its overflow:hidden would clip the rows
                      // → truncated + non-scrollable. Full height makes the LIST overflow → scrolls.
                      flexShrink: 0,
                    }}
                  >
                    <button
                      onClick={() => toggleCollapse(c.key, collapsed)}
                      aria-expanded={!collapsed}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 7,
                        width: "100%",
                        textAlign: "left",
                        border: "none",
                        cursor: "pointer",
                        padding: "8px 12px",
                        background: "var(--muted)",
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                      }}
                    >
                      {collapsed ? (
                        <ChevronRight size={13} strokeWidth={2} />
                      ) : (
                        <ChevronDown size={13} strokeWidth={2} />
                      )}
                      <span style={{ flex: 1 }}>{c.name}</span>
                      <span>· {tix.length}</span>
                    </button>
                    {!collapsed &&
                      tix.map((tk) => (
                        // A div (role=button), NOT a <button>, because the row now contains an
                        // interactive Track <select> — nested interactive controls inside a <button>
                        // are invalid HTML. Keyboard select kept via Enter/Space on the row.
                        <div
                          key={tk.number}
                          ref={sel === tk.number ? selectedRowRef : undefined}
                          role="button"
                          tabIndex={0}
                          onClick={() => setSel(tk.number)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSel(tk.number);
                            }
                          }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            width: "100%",
                            textAlign: "left",
                            border: "none",
                            borderBottom: "1px solid var(--border)",
                            borderLeft: `3px solid ${sel === tk.number ? "var(--primary)" : "transparent"}`,
                            background:
                              sel === tk.number
                                ? "var(--muted)"
                                : "transparent",
                            cursor: "pointer",
                            padding: "8px 12px",
                          }}
                        >
                          {/* State dot — legend is the running/waiting/blocked summary line. */}
                          <span
                            style={{
                              display: "inline-block",
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              flexShrink: 0,
                              background: stateDotColor(tk.agent_state),
                            }}
                          />
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: 11,
                              color: "var(--muted-foreground)",
                              // Fixed width + right align so titles line up regardless of how many
                              // digits the ticket number has (#2 vs #1243).
                              minWidth: 44,
                              textAlign: "right",
                              flexShrink: 0,
                            }}
                          >
                            #{tk.number}
                          </span>
                          <span
                            style={{
                              flex: 1,
                              minWidth: 0,
                              fontSize: 12.5,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {tk.title}
                          </span>
                          {tk.agent_state && (
                            <Badge
                              tone={STATE_TONE[tk.agent_state] || "neutral"}
                              size="sm"
                            >
                              {tk.agent_state}
                            </Badge>
                          )}
                          {/* Compact Track selector. Wrapped in a stopPropagation div so changing
                              the lane (or just opening the dropdown) doesn't select the row. Its
                              value comes from the boardTracks map ("" = Auto / no label). */}
                          <div
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => e.stopPropagation()}
                            style={{ flexShrink: 0 }}
                          >
                            <Select
                              size="sm"
                              mono={false}
                              value={boardTracks[String(tk.number)] || ""}
                              disabled={tracking}
                              onChange={(e) =>
                                doTrack(tk.number, e.target.value)
                              }
                              options={trackOptions(t)}
                            />
                          </div>
                        </div>
                      ))}
                  </div>
                );
              })}
            </div>
          )
        )}

        {/* ticket detail */}
        {(!isMobile || sel != null) && (
          <div
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: 18,
              // Desktop: the detail scrolls internally so the page itself stays fixed-height.
              ...(isMobile
                ? { minHeight: 200 }
                : { minHeight: 0, overflowY: "auto" }),
            }}
          >
            {sel == null ? (
              <div
                style={{
                  color: "var(--muted-foreground)",
                  textAlign: "center",
                  padding: "40px 0",
                }}
              >
                {t("monitor.select_hint")}
              </div>
            ) : !detail ? (
              <div>{t("common.loading")}</div>
            ) : (
              <div
                style={{ display: "flex", flexDirection: "column", gap: 14 }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 9,
                    // Wrap so a long ticket title can't overflow the box on narrow screens.
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      color: "var(--muted-foreground)",
                    }}
                  >
                    #{detail.number}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: "var(--text-md)",
                      minWidth: 0,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {detail.title}
                  </span>
                  <KeyChip>{detail.column_key}</KeyChip>
                </div>

                {/* Status / column change (operator move intent). Disallowed columns are disabled. */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                  }}
                >
                  <label
                    style={{ fontSize: 12, color: "var(--muted-foreground)" }}
                  >
                    {t("monitor.move_to", "Status")}
                  </label>
                  <Select
                    size="sm"
                    mono={false}
                    value={currentMoveKey}
                    disabled={moving}
                    onChange={(e) => doMove(e.target.value)}
                    options={moveOptions.map((m) => ({
                      value: m.key,
                      label: m.current
                        ? `${m.name} ✓`
                        : m.allowed
                          ? m.name
                          : `${m.name} —`,
                      disabled: !m.allowed && !m.current,
                    }))}
                  />
                  {moving && (
                    <span
                      style={{
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                      }}
                    >
                      {t("monitor.moving", "Moving…")}
                    </span>
                  )}
                </div>
                {moveMsg && (
                  <StatusNote tone={moveMsg.tone}>{moveMsg.text}</StatusNote>
                )}

                {/* Fast-track lane (skiff). "" (Auto) clears the track:* label; full/lite/express set
                    it. The detail's `track` field is authoritative; the boardTracks map is the
                    fallback so an optimistic row change is reflected here even before the detail
                    refetch lands. */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                  }}
                >
                  <label
                    style={{ fontSize: 12, color: "var(--muted-foreground)" }}
                  >
                    {t("monitor.track", "Track")}
                  </label>
                  <Select
                    size="sm"
                    mono={false}
                    value={
                      detail.track || boardTracks[String(detail.number)] || ""
                    }
                    disabled={tracking}
                    onChange={(e) => doTrack(detail.number, e.target.value)}
                    options={trackOptions(t)}
                  />
                  {tracking && (
                    <span
                      style={{
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                      }}
                    >
                      {t("monitor.track_saving", "Updating track…")}
                    </span>
                  )}
                </div>
                {trackMsg && (
                  <StatusNote tone={trackMsg.tone}>{trackMsg.text}</StatusNote>
                )}

                {/* Description accordion (collapsible) + pencil edit button.
                    Read view renders body as markdown; pencil opens the freeform editor. */}
                <div
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      padding: "8px 12px",
                      background: "var(--muted)",
                    }}
                  >
                    <button
                      onClick={toggleDesc}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        border: "none",
                        background: "none",
                        cursor: "pointer",
                        padding: 0,
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                      }}
                    >
                      {descOpen ? (
                        <ChevronDown size={13} strokeWidth={2} />
                      ) : (
                        <ChevronRight size={13} strokeWidth={2} />
                      )}
                      {t("monitor.description", "Description")}
                    </button>
                    {!editMode && (
                      <Tooltip
                        label={t(
                          "tip.edit_description",
                          "Edit the description",
                        )}
                        style={{ marginLeft: "auto" }}
                      >
                        <button
                          onClick={openEdit}
                          style={{
                            border: "none",
                            background: "none",
                            cursor: "pointer",
                            padding: 2,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          <Pencil size={13} strokeWidth={2} />
                        </button>
                      </Tooltip>
                    )}
                  </div>
                  {descOpen && !editMode && (
                    <div
                      className="km-timeline-md"
                      style={{
                        padding: "10px 14px",
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                      dangerouslySetInnerHTML={{
                        __html: renderMarkdown(detail.body || ""),
                      }}
                    />
                  )}
                  {editMode && (
                    <div
                      style={{
                        padding: "10px 14px",
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      <MarkdownField
                        value={editFreeform}
                        onChange={setEditFreeform}
                        minRows={12}
                        placeholder={t(
                          "monitor.desc_placeholder",
                          "Describe the ticket (markdown)…",
                        )}
                      />
                      <div style={{ display: "flex", gap: 6 }}>
                        <Tooltip
                          label={t(
                            "tip.save_description",
                            "Save the description to the GitHub issue",
                          )}
                        >
                          <Button
                            onClick={saveEdit}
                            disabled={saving}
                            loading={saving}
                          >
                            {saving ? t("body.saving") : t("body.save")}
                          </Button>
                        </Tooltip>
                        <Tooltip
                          label={t("tip.cancel_edit", "Discard your changes")}
                        >
                          <Button
                            variant="outline"
                            onClick={() => setEditMode(false)}
                          >
                            {t("body.cancel")}
                          </Button>
                        </Tooltip>
                      </div>
                    </div>
                  )}
                </div>

                {/* artifacts: info chips (roadmap/codename) + clickable readable docs
                    (brainstorm/design/plans) opening the markdown reader */}
                {(Object.values(detail.markers).some(Boolean) ||
                  brainstorm) && (
                  <div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                        marginBottom: 6,
                      }}
                    >
                      {t("monitor.artifacts")}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}
                    >
                      {detail.markers.roadmap && (
                        <span title={detail.markers.roadmap}>
                          <KeyChip>roadmap: {detail.markers.roadmap}</KeyChip>
                        </span>
                      )}
                      {detail.markers.codename && (
                        <KeyChip>codename: {detail.markers.codename}</KeyChip>
                      )}
                      {brainstorm && (
                        <DocLink
                          onClick={() =>
                            openText(t("monitor.doc_brainstorm"), brainstorm)
                          }
                        >
                          {t("monitor.doc_brainstorm")}
                        </DocLink>
                      )}
                      {detail.markers.design && (
                        <DocLink
                          title={detail.markers.design}
                          onClick={() =>
                            openFile(
                              t("monitor.doc_design"),
                              detail.markers.design,
                            )
                          }
                        >
                          {t("monitor.doc_design")}
                        </DocLink>
                      )}
                      {planPaths.map((p) => (
                        <DocLink
                          key={p}
                          title={p}
                          onClick={() => openFile(t("monitor.doc_plan"), p)}
                        >
                          {baseName(p)}
                        </DocLink>
                      ))}
                    </div>
                  </div>
                )}

                {/* agent panel + pane tail */}
                {selAgent ? (
                  <div
                    style={{
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-md)",
                      padding: 12,
                      background: "var(--muted)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        gap: 14,
                        // Wrap on narrow screens; the mono branch name can be long and must not
                        // push the detail box past the viewport (mobile horizontal-scroll bug).
                        flexWrap: "wrap",
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                        marginBottom: 8,
                      }}
                    >
                      <span>
                        {t("monitor.state")}: <b>{selAgent.state}</b>
                      </span>
                      <span>
                        {t("monitor.stage")}: {selAgent.stage}
                      </span>
                      <span style={{ overflowWrap: "anywhere", minWidth: 0 }}>
                        {t("monitor.branch")}: {selAgent.branch}
                      </span>
                    </div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        color: "var(--muted-foreground)",
                        marginBottom: 4,
                      }}
                    >
                      {t("monitor.terminal")}
                    </div>
                    {!terminalOpen && (
                      <pre
                        style={{
                          margin: 0,
                          padding: 10,
                          background: "var(--surface-inverse, #1e1e1e)",
                          color: "#e2e2d6",
                          borderRadius: "var(--radius-sm)",
                          maxHeight: 320,
                          overflow: "auto",
                          fontFamily: "var(--font-mono)",
                          fontSize: 11.5,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {pane && pane.alive
                          ? pane.lines
                          : t("monitor.session_ended")}
                      </pre>
                    )}
                  </div>
                ) : (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--muted-foreground)",
                      }}
                    >
                      {t("monitor.no_agent")}
                    </div>
                    {/* Ad-hoc launch (no transition): run a Claude agent on this ticket
                        with a one-off prompt — for a quick fix without exercising the flow. */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-md)",
                        padding: 10,
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 600 }}>
                        {t("monitor.launch_title", "Launch an agent")}
                      </div>
                      <MarkdownField
                        value={launchPrompt}
                        onChange={setLaunchPrompt}
                        minRows={6}
                        mono
                        placeholder={t(
                          "monitor.launch_placeholder",
                          "Prompt for the agent (e.g. fix the failing test in …)",
                        )}
                      />
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          flexWrap: "wrap",
                        }}
                      >
                        <label
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            fontSize: 12,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          {t("monitor.launch_profile", "Profile")}
                          <Select
                            size="sm"
                            value={launchProfile}
                            onChange={(e) => setLaunchProfile(e.target.value)}
                            options={["dev", "check", "prepare", "docs"]}
                          />
                        </label>
                        <Tooltip
                          label={t(
                            "tip.launch_agent",
                            "Run a Claude agent on this ticket now",
                          )}
                        >
                          <Button
                            size="sm"
                            onClick={doLaunch}
                            disabled={launching}
                            loading={launching}
                          >
                            {launching
                              ? t("monitor.launching", "Launching…")
                              : t("monitor.launch_button", "Launch agent")}
                          </Button>
                        </Tooltip>
                      </div>
                      {launchMsg && (
                        <StatusNote tone={launchMsg.tone}>
                          {launchMsg.text}
                        </StatusNote>
                      )}
                    </div>
                  </div>
                )}

                {/* interactive terminal (tiller §5) — shown when the selected ticket
                    has a running agent. Replaces the static pane tail above. */}
                {sel != null &&
                  agents.some((a) => a.issue === sel && a.session_alive) && (
                    <div style={{ marginTop: 12 }}>
                      {!terminalOpen ? (
                        <Tooltip
                          label={t(
                            "tip.open_terminal",
                            "Attach to the agent's live terminal",
                          )}
                        >
                          <Button
                            size="sm"
                            onClick={() => setTerminalOpen(true)}
                          >
                            {t("terminal.interactive", "Interactive terminal")}
                          </Button>
                        </Tooltip>
                      ) : (
                        <AgentTerminal
                          issue={sel}
                          onClose={() => setTerminalOpen(false)}
                        />
                      )}
                    </div>
                  )}

                {/* timeline */}
                {detail.timeline.length > 0 && (
                  <div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                        marginBottom: 6,
                      }}
                    >
                      {t("monitor.timeline")}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        // More breathing room between comment blocks (operator).
                        gap: 12,
                      }}
                    >
                      {detail.timeline
                        // Newest first (date DESC). Keep original index as a stable tiebreaker for
                        // undated / same-instant entries.
                        .map((e, i) => ({ e, i }))
                        .sort((a, b) => {
                          const ta = a.e.at ? Date.parse(a.e.at) : 0;
                          const tb = b.e.at ? Date.parse(b.e.at) : 0;
                          return tb - ta || b.i - a.i;
                        })
                        .map(({ e, i }) => {
                          const isComment = e.kind === "comment";
                          // The kind + date header — placed INSIDE the comment block (operator),
                          // or above the text for non-comment events.
                          const header = (
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                              }}
                            >
                              <KeyChip>{e.kind}</KeyChip>
                              {e.at && (
                                <span
                                  style={{
                                    color: "var(--muted-foreground)",
                                    fontSize: 11,
                                  }}
                                >
                                  {fmtCommentDate(e.at, lang)}
                                </span>
                              )}
                            </div>
                          );
                          return (
                            <div
                              key={i}
                              style={{ fontSize: 12.5, lineHeight: 1.5 }}
                            >
                              {isComment ? (
                                // Header bar (kind + date) and the markdown body share one block.
                                <div
                                  style={{
                                    border: "1px solid var(--border)",
                                    borderRadius: "var(--radius-md)",
                                    background: "var(--muted)",
                                    overflow: "hidden",
                                  }}
                                >
                                  <div
                                    style={{
                                      padding: "6px 11px",
                                      borderBottom: "1px solid var(--border)",
                                    }}
                                  >
                                    {header}
                                  </div>
                                  <div
                                    className="km-timeline-md"
                                    style={{ padding: "9px 11px" }}
                                    dangerouslySetInnerHTML={{
                                      __html: renderMarkdown(e.text || ""),
                                    }}
                                  />
                                </div>
                              ) : (
                                <>
                                  <div style={{ marginBottom: 3 }}>
                                    {header}
                                  </div>
                                  <div
                                    style={{
                                      whiteSpace: "pre-wrap",
                                      color: "var(--muted-foreground)",
                                    }}
                                  >
                                    {e.text}
                                  </div>
                                </>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <MarkdownReader
        open={reader != null}
        title={reader?.title}
        subtitle={reader?.subtitle}
        content={reader?.content}
        loading={reader?.loading}
        error={reader?.error}
        onClose={() => setReader(null)}
      />
    </div>
  );
}

// Extract the issue body's `## Brainstorm` section (heading → next `##` or end), or null.
function brainstormSection(body) {
  if (!body) return null;
  const m = body.match(/(^|\n)(##\s+Brainstorm[\s\S]*?)(?=\n##\s|$)/i);
  return m ? m[2].trim() : null;
}

// Extract freeform prose from the body — strip marker/status regions and ## Brainstorm.
// Last path segment — a compact label for plan files (paths can be long / multiple).
function baseName(path) {
  const parts = String(path).split("/");
  return parts[parts.length - 1] || path;
}

// A clickable artifact "link" rendered as a chip with a 📄 affordance.
function DocLink({ onClick, title, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        border: "1px solid var(--primary)",
        background: "color-mix(in oklch, var(--primary) 10%, transparent)",
        color: "var(--primary)",
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: 11.5,
        padding: "3px 9px",
        maxWidth: 240,
      }}
    >
      <span aria-hidden>📄</span>
      <span
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {children}
      </span>
    </button>
  );
}
