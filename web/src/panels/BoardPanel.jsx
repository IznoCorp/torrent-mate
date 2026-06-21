// Native kanban board view (anchor follow-up "board-view"). Consumes /api/board/* — the native
// store is the placement authority; moves here drive the GitHub board via the mirror, and (in
// hybrid mode) a move made on GitHub is reconciled back. The autonomous transition workflow keeps
// firing on the native column.
//
// UX:
// - Desktop: a full-height horizontal multi-column board with smooth HTML5 drag-and-drop (move
//   across columns, drop on a card to reorder/insert, live insertion indicator). Columns can be
//   collapsed to a thin counter strip. Each column scrolls internally; the page itself does not.
// - Mobile: ONE column at a time via a scrollable tab strip (with counts), the column's cards as a
//   full-width list, a big "move" bottom-sheet per card (touch-first), and ↑/↓ reorder.
//
// Every mutation reports VERIFIED completion: the server reads the GitHub state back after a mirror
// write, so a toast distinguishes "synced to GitHub" from "saved locally, GitHub not confirmed".
import React from "react";
import { MonitorCheck } from "lucide-react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const { Banner, Button, Badge, Card, Tooltip } =
  window.KanbanMateDesignSystem_2463ad;

// One-shot <style> with the drag/hover effects (Item 2). Inline styles cannot express :hover or the
// .dragging class transition, so the board injects a scoped stylesheet once.
function BoardStyles() {
  return (
    <style>{`
      .km-card {
        transition: transform .12s ease, box-shadow .15s ease, opacity .12s ease;
      }
      .km-card:hover {
        transform: translateY(-2px);
      }
      .km-card.km-dragging {
        opacity: .35;
        transform: scale(.96);
      }
      .km-card.km-grab { cursor: grab; }
      .km-card.km-grab:active { cursor: grabbing; }
      .km-dropline {
        height: 3px;
        border-radius: 2px;
        background: var(--primary);
        margin: 2px 4px;
        transition: opacity .1s ease;
      }
      .km-colstrip { transition: background .12s ease, border-color .12s ease; }
      .km-colstrip:hover { background: var(--muted); }
    `}</style>
  );
}

export default function BoardPanel({ project }) {
  const { t } = useT();
  const isMobile = useIsMobile();
  const [data, setData] = React.useState(null); // {version, columns, cards, identity_degraded}
  const [error, setError] = React.useState(null);
  const [notNative, setNotNative] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState(null); // {tone, text} transient feedback
  const [actionError, setActionError] = React.useState(null); // mutation error (shown even with data)
  const [confirmImport, setConfirmImport] = React.useState(false); // 2-step destructive import
  const [pendingAction, setPendingAction] = React.useState(null); // which button is mid-flight (spinner)
  const noticeTimer = React.useRef(null);

  // Show a transient notice; success/info auto-dismiss, warnings/errors stay until the next action.
  const pushNotice = React.useCallback((tone, text) => {
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    setNotice({ tone, text });
    if (tone === "success" || tone === "info") {
      noticeTimer.current = setTimeout(() => setNotice(null), 4000);
    }
  }, []);
  React.useEffect(
    () => () => noticeTimer.current && clearTimeout(noticeTimer.current),
    [],
  );

  // Resolves to the fetched board on success, or null on a handled failure — so callers (e.g. the
  // Refresh button) can confirm/deny the action instead of guessing.
  const load = React.useCallback(() => {
    setError(null);
    return api
      .boardState(project)
      .then((d) => {
        setData(d);
        setNotNative(false);
        return d;
      })
      .catch((e) => {
        if (e.status === 409)
          setNotNative(true); // board_backend != native
        else setError(e.message);
        return null;
      });
  }, [project]);

  // Explicit refresh: a remote round-trip must never look like a no-op. Show busy, then confirm
  // success (with the board revision as tangible proof it re-synced) or surface the error.
  const refresh = React.useCallback(async () => {
    setBusy(true);
    setPendingAction("refresh");
    setActionError(null);
    try {
      const d = await load();
      if (d) pushNotice("success", t("board.refreshed", { rev: d.version }));
      else pushNotice("error", t("board.refresh_failed"));
    } finally {
      setBusy(false);
      setPendingAction(null);
    }
  }, [load, pushNotice, t]);

  React.useEffect(() => {
    setData(null);
    setNotice(null);
    load();
  }, [load]);

  // Apply a mutation then reload. 409 (stale version) → refetch + warn (someone else moved).
  const mutate = async (fn) => {
    setBusy(true);
    setActionError(null);
    try {
      const res = await fn();
      await load(); // AWAIT the refetch so the board isn't shown stale while busy is cleared
      return res;
    } catch (e) {
      if (e.status === 409) {
        pushNotice("warn", t("board.conflict"));
        await load();
      } else {
        // Surface the failure (the board view already has data, so the initial-load banner won't
        // show it) AND reload so the UI re-syncs to server truth instead of looking stale.
        setActionError(e.message);
        await load();
      }
      return undefined;
    } finally {
      setBusy(false);
    }
  };

  // Translate the server's verified mirror_state into a clear, honest toast (Item 1).
  const noticeForMove = (res) => {
    if (!res) return; // a 409/error already pushed its own notice
    switch (res.mirror_state) {
      case "synced":
        pushNotice("success", t("board.moved_synced"));
        break;
      case "disabled":
        pushNotice("success", t("board.moved_local"));
        break;
      case "unconfirmed":
        pushNotice("warn", t("board.moved_unconfirmed"));
        break;
      case "failed":
        pushNotice("error", t("board.moved_failed"));
        break;
      default:
        pushNotice("success", t("board.moved_local"));
    }
  };

  const moveTo = async (itemId, toColumn) => {
    const res = await mutate(() =>
      api.boardMove({ itemId, toColumn, ifVersion: data.version }, project),
    );
    noticeForMove(res);
  };
  const placeAt = async (itemId, columnKey, index) => {
    const res = await mutate(() =>
      api.boardPlace(
        { itemId, columnKey, index, ifVersion: data.version },
        project,
      ),
    );
    noticeForMove(res);
  };
  const reorder = async (columnKey, orderedItemIds) => {
    const res = await mutate(() =>
      api.boardReorder(
        { columnKey, orderedItemIds, ifVersion: data.version },
        project,
      ),
    );
    if (res) pushNotice("success", t("board.reordered"));
  };
  const onImport = async () => {
    setPendingAction("import");
    const res = await mutate(() =>
      api.boardImport({ dryRun: false }, project),
    ).finally(() => setPendingAction(null));
    if (res) {
      const summary = res.summary || {};
      const n = Object.values(summary).reduce(
        (a, b) => a + (Number(b) || 0),
        0,
      );
      pushNotice("success", t("board.imported", { n }));
    }
  };

  if (notNative) {
    return (
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <PageIntro title={t("board.intro_title")} scope="board">
          {t("board.intro_body")}
        </PageIntro>
        <Banner tone="amber" title={t("board.not_native_title")}>
          {t("board.not_native_body")}
        </Banner>
      </div>
    );
  }
  if (error && !data)
    return (
      <Banner tone="error" title={t("board.intro_title")}>
        {error}
      </Banner>
    );
  if (!data) return <div style={{ padding: 24 }}>{t("common.loading")}</div>;

  const cardsByCol = {};
  for (const c of data.columns) cardsByCol[c] = [];
  for (const card of data.cards)
    (cardsByCol[card.column_key] ||= []).push(card);
  for (const c of data.columns) cardsByCol[c].sort((a, b) => a.index - b.index);

  // Map a notice severity to a design-system Badge tone (accent = brand green = success).
  const noticeTone = {
    success: "accent",
    info: "blue",
    warn: "amber",
    error: "red",
  };
  const toolbar = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        marginBottom: 12,
        flexWrap: "wrap",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--muted-foreground)",
          cursor: "help",
        }}
        title={t(
          "board.revision_hint",
          "Board revision — increments on every change; used to detect concurrent edits (optimistic locking).",
        )}
      >
        {t("board.revision_label", "rev.")} {data.version}
      </span>
      {notice && (
        <Badge tone={noticeTone[notice.tone] || "neutral"} size="sm">
          {notice.text}
        </Badge>
      )}
      {data.identity_degraded && (
        <Badge tone="red" size="sm">
          {t("board.identity_degraded")}
        </Badge>
      )}
      <span style={{ flex: 1 }} />
      <Tooltip label={t("tip.board_refresh", "Reload the board from the server")}>
        <Button
          variant="secondary"
          size="sm"
          disabled={busy}
          loading={pendingAction === "refresh"}
          onClick={() => {
            setConfirmImport(false);
            refresh();
          }}
        >
          {t("board.refresh")}
        </Button>
      </Tooltip>
      {/* Import re-seeds placement from GitHub (overwrites native order) → 2-step confirm. */}
      <Tooltip
        label={t(
          "tip.board_import",
          "Re-seed card placement from GitHub (overwrites local order)",
        )}
      >
        <Button
          variant={confirmImport ? "primary" : "secondary"}
          size="sm"
          disabled={busy}
          loading={pendingAction === "import"}
          onClick={() => {
            if (confirmImport) {
              setConfirmImport(false);
              onImport();
            } else {
              setConfirmImport(true);
            }
          }}
        >
          {confirmImport ? t("board.import_confirm") : t("board.import")}
        </Button>
      </Tooltip>
    </div>
  );

  return (
    <div
      style={{
        maxWidth: 1600,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
      }}
    >
      <PageIntro title={t("board.intro_title")} scope="board">
        {t("board.intro_body")}
      </PageIntro>
      {toolbar}
      {actionError && (
        <div style={{ marginBottom: 12 }}>
          <Banner tone="error" title={t("board.action_failed")}>
            {actionError}
          </Banner>
        </div>
      )}
      {isMobile ? (
        <MobileBoard
          columns={data.columns}
          cardsByCol={cardsByCol}
          busy={busy}
          t={t}
          onMove={moveTo}
          onReorder={reorder}
        />
      ) : (
        <DesktopBoard
          project={project}
          columns={data.columns}
          cardsByCol={cardsByCol}
          busy={busy}
          t={t}
          onDropColumn={moveTo}
          onDropCard={placeAt}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Desktop: full-height multi-column board + smooth drag-and-drop + collapse
// ---------------------------------------------------------------------------

function DesktopBoard({
  project,
  columns,
  cardsByCol,
  busy,
  t,
  onDropColumn,
  onDropCard,
}) {
  const dragRef = React.useRef(null);
  const wrapRef = React.useRef(null);
  const [draggingId, setDraggingId] = React.useState(null);
  const [dropTarget, setDropTarget] = React.useState(null); // {col, idx} insertion indicator
  const [boardH, setBoardH] = React.useState(null); // measured full-height (Item 3)

  // Collapsed columns: override map {col: bool} persisted per project.
  // Effective collapsed = override[col] if the operator explicitly toggled,
  // else cardCount === 0 (empty columns collapse by default).
  const storageKey = `km:board:collapsed:${project || "default"}`;
  const [override, setOverride] = React.useState(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      // Migrate old array format (Set serialized as JSON array) → {col: true}.
      if (Array.isArray(parsed)) {
        const migrated = {};
        for (const k of parsed) migrated[k] = true;
        return migrated;
      }
      if (typeof parsed === "object" && parsed !== null) return parsed;
      return {};
    } catch (_) {
      return {};
    }
  });
  const toggleCollapsed = (col) => {
    setOverride((prev) => {
      const next = { ...prev, [col]: !prev[col] };
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next));
      } catch (_) {
        /* ignore persistence failure */
      }
      return next;
    });
  };

  // Auto-collapse/expand when a column's card count crosses the empty↔non-empty boundary.
  // A column going empty → non-empty auto-expands (clear override); non-empty → empty
  // auto-collapses (clear override). Columns that stay on the same side keep their override.
  const prevCountsRef = React.useRef({});
  // Keep a stable ref of override so the effect below doesn't re-trigger on every toggle.
  const overrideRef = React.useRef(override);
  overrideRef.current = override;
  React.useEffect(() => {
    const cur = {};
    for (const col of columns) cur[col] = (cardsByCol[col] || []).length;
    const prev = prevCountsRef.current;
    // Skip initial mount — no previous state to compare against.
    if (Object.keys(prev).length === 0) {
      prevCountsRef.current = cur;
      return;
    }
    let changed = false;
    const next = { ...overrideRef.current };
    for (const col of columns) {
      const was = prev[col] ?? -1;
      const now = cur[col];
      if ((was === 0 && now > 0) || (was > 0 && now === 0)) {
        if (col in next) {
          delete next[col];
          changed = true;
        }
      }
    }
    prevCountsRef.current = cur;
    if (changed) {
      setOverride(next);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next));
      } catch (_) {
        /* ignore persistence failure */
      }
    }
  }, [columns, cardsByCol, storageKey]);

  // Measure the available height so the board fills the viewport; only columns scroll internally.
  // A ResizeObserver on the document body re-measures when ANYTHING above the board reflows (a
  // notice/error banner appearing, the toolbar wrapping) — window 'resize' alone would miss those
  // and leave the board over/under-shooting the real available space.
  React.useLayoutEffect(() => {
    const measure = () => {
      const el = wrapRef.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top;
      // Leave a small bottom gutter so the board doesn't kiss the viewport edge.
      setBoardH(Math.max(360, Math.floor(window.innerHeight - top - 16)));
    };
    measure();
    window.addEventListener("resize", measure);
    let ro;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(measure);
      ro.observe(document.body);
    }
    return () => {
      window.removeEventListener("resize", measure);
      if (ro) ro.disconnect();
    };
  }, []);

  const endDrag = () => {
    dragRef.current = null;
    setDraggingId(null);
    setDropTarget(null);
  };

  return (
    <>
      <BoardStyles />
      <div
        ref={wrapRef}
        style={{
          display: "flex",
          gap: 12,
          overflowX: "auto",
          paddingBottom: 8,
          alignItems: "stretch",
          height: boardH ? `${boardH}px` : "auto",
          minHeight: 0,
        }}
      >
        {columns.map((col) => {
          const cardCount = (cardsByCol[col] || []).length;
          const collapsed = col in override ? override[col] : cardCount === 0;
          return collapsed ? (
            <CollapsedColumn
              key={col}
              col={col}
              count={cardCount}
              t={t}
              dragRef={dragRef}
              onExpand={() => toggleCollapsed(col)}
              onDropColumn={onDropColumn}
              onDragEnd={endDrag}
            />
          ) : (
            <DColumn
              key={col}
              col={col}
              cards={cardsByCol[col] || []}
              busy={busy}
              t={t}
              dragRef={dragRef}
              draggingId={draggingId}
              dropTarget={dropTarget}
              setDropTarget={setDropTarget}
              onCollapse={() => toggleCollapsed(col)}
              onDragStart={(id) => {
                dragRef.current = id;
                setDraggingId(id);
              }}
              onDragEnd={endDrag}
              onDropColumn={onDropColumn}
              onDropCard={onDropCard}
            />
          );
        })}
      </div>
    </>
  );
}

function DColumn({
  col,
  cards,
  busy,
  t,
  dragRef,
  draggingId,
  dropTarget,
  setDropTarget,
  onCollapse,
  onDragStart,
  onDragEnd,
  onDropColumn,
  onDropCard,
}) {
  const [over, setOver] = React.useState(false);
  // Clear the drop-highlight when the drag ends ANYWHERE — a drop landing ON a card stops
  // propagation, so the column's own onDrop (the other place that clears it) never fires.
  React.useEffect(() => {
    if (!draggingId) setOver(false);
  }, [draggingId]);
  return (
    <div
      className={over ? "km-col km-over" : "km-col"}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const itemId = dragRef.current;
        if (itemId) onDropColumn(itemId, col); // drop on column body → tail
        onDragEnd();
      }}
      style={{
        flex: "0 0 308px",
        minWidth: 308,
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        background: over ? "var(--muted)" : "var(--card)",
        border: `1px solid ${over ? "var(--primary)" : "var(--border)"}`,
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
      }}
    >
      <ColumnHeader
        col={col}
        count={cards.length}
        t={t}
        onCollapse={onCollapse}
      />
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          padding: 10,
          flex: "1 1 auto",
          minHeight: 48,
          overflowY: "auto", // Item 3: only the card list scrolls, when it overflows
        }}
      >
        {cards.map((card, idx) => (
          <React.Fragment key={card.item_id}>
            {dropTarget && dropTarget.col === col && dropTarget.idx === idx && (
              <div className="km-dropline" />
            )}
            <div
              className={
                "km-card" +
                (busy ? "" : " km-grab") +
                (draggingId === card.item_id ? " km-dragging" : "")
              }
              // Disable dragging while a mutation is in flight: a second drop would send the stale
              // pre-reload version and 409 against the user's own previous move.
              draggable={!busy}
              onDragStart={() => onDragStart(card.item_id)}
              onDragEnd={onDragEnd}
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (dragRef.current && dragRef.current !== card.item_id)
                  setDropTarget({ col, idx });
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                // Drop on a card → place at that card's index. After the store removes the dragged
                // item first, this yields the INTENTIONAL directional behaviour: a same-column drag
                // DOWN lands the card just after the target, a drag UP lands it just before (the
                // natural DnD feel; verified no off-by-one/data-loss). Cross-column lands before.
                const itemId = dragRef.current;
                if (itemId && itemId !== card.item_id)
                  onDropCard(itemId, col, idx);
                onDragEnd();
              }}
            >
              <Card
                padding="none"
                style={busy ? { cursor: "default" } : undefined}
              >
                <RichCardFace card={card} t={t} />
              </Card>
            </div>
          </React.Fragment>
        ))}
        {cards.length === 0 && <EmptyHint t={t} />}
      </div>
    </div>
  );
}

// A collapsed column: a thin vertical strip showing the name + card count, still a drop target.
function CollapsedColumn({
  col,
  count,
  t,
  dragRef,
  onExpand,
  onDropColumn,
  onDragEnd,
}) {
  const [over, setOver] = React.useState(false);
  return (
    <button
      className="km-colstrip"
      aria-label={t("board.expand")}
      title={`${col} — ${t("board.expand")}`}
      onClick={onExpand}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const itemId = dragRef.current;
        if (itemId) onDropColumn(itemId, col); // drop into a collapsed column → tail
        onDragEnd();
      }}
      style={{
        flex: "0 0 46px",
        width: 46,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        padding: "10px 0",
        background: over ? "var(--muted)" : "var(--card)",
        border: `1px solid ${over ? "var(--primary)" : "var(--border)"}`,
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        cursor: "pointer",
        color: "var(--muted-foreground)",
      }}
    >
      <Badge tone="neutral" size="sm">
        {count}
      </Badge>
      <span
        style={{
          writingMode: "vertical-rl",
          transform: "rotate(180deg)",
          fontFamily: "var(--font-mono)",
          fontSize: 11.5,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          maxHeight: "100%",
        }}
      >
        {col}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Mobile: one column at a time (tab strip) + move bottom-sheet + ↑/↓ reorder
// ---------------------------------------------------------------------------

function MobileBoard({ columns, cardsByCol, busy, t, onMove, onReorder }) {
  // Default to the first column that has cards, else the first column.
  const firstNonEmpty =
    columns.find((c) => (cardsByCol[c] || []).length) || columns[0];
  const [active, setActive] = React.useState(firstNonEmpty);
  const [sheet, setSheet] = React.useState(null); // the card being moved
  const cards = cardsByCol[active] || [];
  const activeTabRef = React.useRef(null);

  // Keep the active tab visible when following a card to an off-screen column.
  React.useEffect(() => {
    activeTabRef.current?.scrollIntoView({
      inline: "center",
      block: "nearest",
      behavior: "smooth",
    });
  }, [active]);

  const moveUpDown = (idx, delta) => {
    const ids = cards.map((c) => c.item_id);
    const j = idx + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    onReorder(active, ids);
  };

  return (
    <div>
      {/* column tab strip — scrollable, counts, active highlighted */}
      <div
        style={{
          display: "flex",
          gap: 8,
          overflowX: "auto",
          paddingBottom: 8,
          marginBottom: 10,
        }}
      >
        {columns.map((col) => {
          const on = col === active;
          const n = (cardsByCol[col] || []).length;
          return (
            <button
              key={col}
              ref={on ? activeTabRef : null}
              aria-label={col}
              onClick={() => setActive(col)}
              style={{
                flex: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "7px 12px",
                borderRadius: 999,
                border: `1px solid ${on ? "var(--primary)" : "var(--border)"}`,
                background: on ? "var(--primary)" : "var(--card)",
                color: on ? "var(--primary-foreground)" : "var(--foreground)",
                fontSize: 13,
                fontWeight: on ? 600 : 500,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {col}
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  opacity: 0.8,
                }}
              >
                {n}
              </span>
            </button>
          );
        })}
      </div>

      {/* active column's cards — full-width list, comfortable tap targets */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {cards.map((card, idx) => (
          <div
            key={card.item_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Card padding="none" style={{ flex: 1, minWidth: 0 }}>
              <RichCardFace card={card} t={t} />
            </Card>
            <div
              style={{
                display: "inline-flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <MiniBtn
                label="↑"
                ariaLabel={t("common.move_up")}
                disabled={busy || idx === 0}
                onClick={() => moveUpDown(idx, -1)}
              />
              <MiniBtn
                label="↓"
                ariaLabel={t("common.move_down")}
                disabled={busy || idx === cards.length - 1}
                onClick={() => moveUpDown(idx, 1)}
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => setSheet(card)}
            >
              {t("board.move")}
            </Button>
          </div>
        ))}
        {cards.length === 0 && <EmptyHint t={t} />}
      </div>

      {/* move bottom-sheet: big touch targets, current column marked */}
      {sheet && (
        <MoveSheet
          card={sheet}
          columns={columns}
          current={active}
          t={t}
          onPick={(to) => {
            setSheet(null);
            if (to !== active) {
              onMove(sheet.item_id, to);
              setActive(to); // follow the card to its new column
            }
          }}
          onClose={() => setSheet(null)}
        />
      )}
    </div>
  );
}

function MoveSheet({ card, columns, current, t, onPick, onClose }) {
  React.useEffect(() => {
    // Lock background scroll while the sheet is open (mobile: stop the board scrolling under it).
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        background: "rgba(0,0,0,0.45)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--card)",
          borderTopLeftRadius: 18,
          borderTopRightRadius: 18,
          borderTop: "1px solid var(--border)",
          padding: "14px 14px 22px",
          maxHeight: "80vh",
          overflowY: "auto",
        }}
      >
        <div
          style={{
            width: 40,
            height: 4,
            borderRadius: 2,
            background: "var(--border)",
            margin: "0 auto 12px",
          }}
        />
        <div
          style={{
            fontSize: 12,
            color: "var(--muted-foreground)",
            marginBottom: 4,
          }}
        >
          {t("board.move_to")}
        </div>
        <div
          style={{
            fontWeight: 600,
            fontSize: 14,
            marginBottom: 12,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {card.title || card.item_id}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {columns.map((col) => {
            const on = col === current;
            return (
              <button
                key={col}
                onClick={() => onPick(col)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  width: "100%",
                  textAlign: "left",
                  padding: "13px 14px",
                  borderRadius: "var(--radius-md)",
                  border: `1px solid ${on ? "var(--primary)" : "var(--border)"}`,
                  background: on ? "var(--muted)" : "var(--background)",
                  color: "var(--foreground)",
                  fontSize: 15,
                  cursor: "pointer",
                }}
              >
                <span style={{ flex: 1 }}>{col}</span>
                {on && (
                  <span style={{ color: "var(--primary)", fontWeight: 700 }}>
                    ✓
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

// Multi-line clamp helper (line-clamp via the webkit box model — supported in the Chromium target).
function textClamp(lines) {
  return {
    display: "-webkit-box",
    WebkitLineClamp: lines,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  };
}

// Rich card face: number + multi-line title + body excerpt inside a DS Card surface.
function RichCardFace({ card, t }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 4,
        padding: "9px 11px",
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
        {card.issue_number != null && (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-2xs)",
              color: "var(--muted-foreground)",
              flex: "none",
              paddingTop: 1,
            }}
          >
            #{card.issue_number}
          </span>
        )}
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: "var(--text-sm)",
            fontWeight: 600,
            lineHeight: 1.35,
            color: card.title ? "var(--foreground)" : "var(--muted-foreground)",
            ...textClamp(2),
          }}
        >
          {card.title || t("board.untitled")}
        </span>
        {/* Deep-link to this ticket in Monitoring (stops propagation so it never starts a drag). */}
        {card.issue_number != null && (
          <button
            type="button"
            title={t("board.open_monitoring", "View in Monitoring")}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              window.dispatchEvent(
                new CustomEvent("km:open-monitoring", {
                  detail: { issue: card.issue_number },
                }),
              );
            }}
            style={{
              flex: "none",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 22,
              height: 22,
              padding: 0,
              border: "none",
              background: "transparent",
              color: "var(--muted-foreground)",
              cursor: "pointer",
            }}
          >
            <MonitorCheck size={14} strokeWidth={1.75} />
          </button>
        )}
      </div>
      {card.excerpt && (
        <div
          style={{
            fontSize: "var(--text-2xs)",
            lineHeight: 1.35,
            color: "var(--muted-foreground)",
            marginTop: 2,
            ...textClamp(2),
          }}
        >
          {card.excerpt}
        </div>
      )}
    </div>
  );
}

function ColumnHeader({ col, count, t, onCollapse }) {
  return (
    <div
      style={{
        padding: "9px 12px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontFamily: "var(--font-mono)",
        fontSize: 11.5,
        textTransform: "uppercase",
        color: "var(--muted-foreground)",
      }}
    >
      <span
        style={{
          flex: 1,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {col}
      </span>
      <Badge tone="neutral" size="sm">
        {count}
      </Badge>
      {onCollapse && (
        <button
          aria-label={t("board.collapse")}
          title={t("board.collapse")}
          onClick={onCollapse}
          style={{
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--muted-foreground)",
            fontSize: 14,
            lineHeight: 1,
            padding: "2px 4px",
          }}
        >
          ⟨
        </button>
      )}
    </div>
  );
}

function EmptyHint({ t }) {
  return (
    <div
      style={{
        fontSize: 12,
        color: "var(--muted-foreground)",
        textAlign: "center",
        padding: "12px 0",
      }}
    >
      {t("board.no_cards")}
    </div>
  );
}

function MiniBtn({ label, ariaLabel, disabled, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      title={ariaLabel}
      style={{
        border: "1px solid var(--border)",
        background: "var(--background)",
        borderRadius: 8,
        width: 38,
        height: 34,
        cursor: disabled ? "default" : "pointer",
        color: disabled ? "var(--muted-foreground)" : "var(--foreground)",
        opacity: disabled ? 0.5 : 1,
        fontSize: 15,
        lineHeight: 1,
      }}
    >
      {label}
    </button>
  );
}
