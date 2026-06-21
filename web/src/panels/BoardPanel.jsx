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
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const { Banner, Button, Badge } = window.KanbanMateDesignSystem_2463ad;

// One-shot <style> with the drag/hover effects (Item 2). Inline styles cannot express :hover or the
// .dragging class transition, so the board injects a scoped stylesheet once.
function BoardStyles() {
  return (
    <style>{`
      .km-card { transition: transform .12s ease, box-shadow .12s ease, opacity .12s ease; }
      .km-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
      .km-card.km-dragging { opacity: .4; transform: scale(.97); }
      .km-card.km-grab { cursor: grab; }
      .km-card.km-grab:active { cursor: grabbing; }
      .km-dropline { height: 3px; border-radius: 2px; background: var(--primary); margin: 1px 4px; }
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

  const load = React.useCallback(() => {
    setError(null);
    return api
      .boardState(project)
      .then((d) => {
        setData(d);
        setNotNative(false);
      })
      .catch((e) => {
        if (e.status === 409)
          setNotNative(true); // board_backend != native
        else setError(e.message);
      });
  }, [project]);

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
    const res = await mutate(() => api.boardImport({ dryRun: false }, project));
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
        }}
      >
        v{data.version}
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
      <Button
        variant="secondary"
        size="sm"
        disabled={busy}
        onClick={() => {
          setConfirmImport(false);
          load();
        }}
      >
        {t("board.refresh")}
      </Button>
      {/* Import re-seeds placement from GitHub (overwrites native order) → 2-step confirm. */}
      <Button
        variant={confirmImport ? "primary" : "secondary"}
        size="sm"
        disabled={busy}
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

  // Collapsed columns persist per project (Item 4 — visual-only hide).
  const storageKey = `km:board:collapsed:${project || "default"}`;
  const [collapsed, setCollapsed] = React.useState(() => {
    try {
      return new Set(
        JSON.parse(window.localStorage.getItem(storageKey) || "[]"),
      );
    } catch (_) {
      return new Set();
    }
  });
  const toggleCollapsed = (col) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(col)) next.delete(col);
      else next.add(col);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify([...next]));
      } catch (_) {
        /* ignore persistence failure */
      }
      return next;
    });
  };

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
        {columns.map((col) =>
          collapsed.has(col) ? (
            <CollapsedColumn
              key={col}
              col={col}
              count={(cardsByCol[col] || []).length}
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
          ),
        )}
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
              <CardFace card={card} t={t} rich />
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
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-xs)",
              padding: "12px 14px",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <CardFace card={card} t={t} rich />
            </div>
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

// A card face. `rich` adds a multi-line title + a body excerpt (Item 2 — more info on cards).
function CardFace({ card, t, rich }) {
  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {card.issue_number != null && (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--muted-foreground)",
              flex: "none",
            }}
          >
            #{card.issue_number}
          </span>
        )}
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 13.5,
            fontWeight: rich ? 600 : 500,
            lineHeight: 1.3,
            ...(rich ? clamp(2) : ONE_LINE),
            color: card.title ? "var(--foreground)" : "var(--muted-foreground)",
          }}
        >
          {card.title || t("board.untitled")}
        </span>
      </div>
      {rich && card.excerpt && (
        <div
          style={{
            fontSize: 12,
            lineHeight: 1.35,
            color: "var(--muted-foreground)",
            ...clamp(2),
          }}
        >
          {card.excerpt}
        </div>
      )}
    </div>
  );
}

const ONE_LINE = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

// Multi-line clamp helper (line-clamp via the webkit box model — supported in the Chromium target).
function clamp(lines) {
  return {
    display: "-webkit-box",
    WebkitLineClamp: lines,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  };
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
