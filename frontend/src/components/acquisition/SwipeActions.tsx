/**
 * SwipeActions — reveal a card's actions by dragging it sideways.
 *
 * The action layer sits BEHIND the card and never moves; the card slides over
 * it. Moving the wrapper instead would drag the buttons out of view along with
 * the card, which is the bug that makes a swipe row feel broken.
 */

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";

import { EDGE_DEAD_ZONE_PX, lockAxis } from "@/components/acquisition/gestures";

/** One action revealed by a swipe. */
export interface SwipeAction {
  readonly key: string;
  readonly label: string;
  /** 17 px maquette icon — sized by the `.act svg` rule. */
  readonly icon: ReactNode;
  /** Maquette pane class — carries the tone (grab=primary, pause=muted,
   *  remove=danger) and the 84 px column layout. */
  readonly actClass: "grab" | "pause" | "remove";
  readonly onRun: () => void;
}

/** Props for {@link SwipeActions}. */
export interface SwipeActionsProps {
  /** Revealed by dragging right — the affirmative action. */
  readonly left?: SwipeAction;
  /** Revealed by dragging left — secondary and destructive actions. */
  readonly right?: readonly SwipeAction[];
  /** The card. */
  readonly children: ReactNode;
  /** Extra container class — e.g. maquette ``fresh`` for the add glow. */
  readonly className?: string;
}

/**
 * Fixed width of one action button, in CSS pixels.
 *
 * A basis rather than a content-driven width: labels differ in length
 * (« Récupérer » vs « Ne plus chercher »), and unequal buttons make the row read
 * as misaligned. The label wraps inside this width instead of widening it.
 */
const ACTION_WIDTH_PX = 84;

/** Distance a drag must cover before the actions stay open. */
const OPEN_THRESHOLD_PX = 40;

/**
 * Window, in ms, during which the click that FOLLOWS a swipe is absorbed.
 *
 * Mouse semantics fire a click after any press-move-release on one element,
 * so a desktop drag would double as a tap and open the detail sheet. The
 * maquette absorbs it (`justSwiped`, 400 ms); touch browsers already
 * suppress the click on long drags, so this only guards mouse drags.
 */
const CLICK_ABSORB_MS = 400;

/**
 * The one row allowed to stay open, and the rows listening for that to change.
 *
 * Operator, 2026-08-08: « une seule carte peut être ouverte à la fois — en
 * ouvrir une seconde referme la première ». A module-level registry rather than
 * lifted state: every list that renders these rows would otherwise have to
 * thread an "openId" through, and the rule belongs to the row, not to the list.
 */
const openListeners = new Map<string, (openId: string | null) => void>();

/** Declare `id` the open row and notify every other row to settle. */
function claimOpenRow(id: string | null): void {
  for (const [key, notify] of openListeners) {
    if (key !== id) notify(id);
  }
}

/**
 * Wrap a card so a sideways drag reveals its actions.
 *
 * Args:
 *   props: See {@link SwipeActionsProps}.
 *
 * Returns:
 *   The swipe container.
 */
export function SwipeActions({
  left,
  right,
  children,
  className,
}: SwipeActionsProps): ReactElement {
  const [offset, setOffset] = useState(0);
  const dragRef = useRef<{
    x: number;
    y: number;
    axis: "x" | "y" | null;
    captured: boolean;
  } | null>(null);
  const lastSwipeEndRef = useRef(0);
  const rowId = useId();

  const rightWidth = (right?.length ?? 0) * ACTION_WIDTH_PX;
  const leftWidth = left != null ? ACTION_WIDTH_PX : 0;

  const close = useCallback(() => {
    setOffset(0);
  }, []);

  // Another row opening closes this one — including mid-drag, so a second
  // finger cannot leave two rows half-open.
  useEffect(() => {
    openListeners.set(rowId, () => {
      dragRef.current = null;
      setOffset(0);
    });
    return () => {
      openListeners.delete(rowId);
    };
  }, [rowId]);

  const settle = useCallback(() => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (drag?.axis !== "x") return;
    lastSwipeEndRef.current = Date.now();
    setOffset((current) => {
      if (current <= -OPEN_THRESHOLD_PX) return -rightWidth;
      if (current >= OPEN_THRESHOLD_PX) return leftWidth;
      return 0;
    });
  }, [leftWidth, rightWidth]);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      // Same edge band as the pager: iOS owns it, and competing there produces
      // a half-navigation nobody asked for.
      if (e.clientX < EDGE_DEAD_ZONE_PX) return;
      // Touching THIS row settles every other one straight away, before the
      // drag even resolves: two rows open at once is the state the operator
      // reported, and it makes the second swipe look like it did nothing.
      claimOpenRow(rowId);
      dragRef.current = { x: e.clientX, y: e.clientY, axis: null, captured: false };
      // A window-level net for the end of the touch: a row LEFT MID-DRAG is
      // exactly what the operator saw on their phone (« seul pause visible
      // plus un bout de retirer ») — the card sitting wherever the finger let
      // go, half a pane wide. Which of pointerup / pointercancel / touchend
      // iOS delivers no longer decides whether the row settles.
      const end = (): void => {
        settle();
        window.removeEventListener("pointerup", end);
        window.removeEventListener("pointercancel", end);
        window.removeEventListener("touchend", end);
        window.removeEventListener("touchcancel", end);
      };
      window.addEventListener("pointerup", end);
      window.addEventListener("pointercancel", end);
      window.addEventListener("touchend", end);
      window.addEventListener("touchcancel", end);
    },
    [rowId, settle],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (drag == null) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag.axis ??= lockAxis(dx, dy);
      if (drag.axis !== "x") return;
      // Capture only once this is REALLY a horizontal drag, never on the
      // press: a captured pointer retargets the click that ends it to the
      // capturing element, so capturing on pointerdown swallowed every tap
      // on a control inside the card — the detail sheet stopped opening.
      if (!drag.captured) {
        drag.captured = true;
        const row = e.currentTarget;
        if (typeof row.setPointerCapture === "function") {
          row.setPointerCapture(e.pointerId);
        }
      }
      // Clamp to what actually exists: dragging towards an empty side must not
      // open a gap onto nothing.
      setOffset(Math.max(-rightWidth, Math.min(leftWidth, dx)));
    },
    [leftWidth, rightWidth],
  );

  const onPointerUp = useCallback(() => {
    settle();
  }, [settle]);

  const onClickCapture = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      if (Date.now() - lastSwipeEndRef.current < CLICK_ABSORB_MS) {
        // The synthetic click that ends the drag itself: swallowed WITHOUT
        // closing, or a mouse swipe would immediately undo its own opening.
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (offset === 0) return;
      // Maquette: a LATER tap on a swiped card settles it first — it is
      // never ALSO the tap that opens the sheet.
      e.preventDefault();
      e.stopPropagation();
      close();
    },
    [offset, close],
  );

  function renderAction(action: SwipeAction): ReactElement {
    return (
      <button
        key={action.key}
        type="button"
        data-testid="swipe-action"
        // Maquette pane grammar: 84 px column, 17 px icon, tone via the class.
        // `.act.grab` no longer collides with the sheet handle — it is
        // `sheetgrab`, named that way in the maquette for this exact reason.
        className={`act ${action.actClass}`}
        onClick={() => {
          action.onRun();
          close();
        }}
      >
        {action.icon}
        <span>{action.label}</span>
      </button>
    );
  }

  return (
    <div
      data-swipe
      data-testid="swipe-container"
      className={`relative overflow-hidden rounded-lg${className != null ? ` ${className}` : ""}`}
    >
      {/* Action layer — behind the card, never translated (maquette .actions). */}
      {/* inert: aria-hidden alone left the buttons keyboard-focusable — a
          hidden control that still takes focus is a trap. The kebab is the
          keyboard path to the same actions. */}
      <div className="actions">
        <div className="side left" aria-hidden={offset <= 0} inert={offset <= 0}>
          {left != null && renderAction(left)}
        </div>
        <div className="side right" aria-hidden={offset >= 0} inert={offset >= 0}>
          {right?.map(renderAction)}
        </div>
      </div>

      <div
        data-testid="swipe-card"
        className="relative touch-pan-y transition-transform"
        style={{ transform: `translateX(${String(offset)}px)` }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClickCapture={onClickCapture}
      >
        {children}
      </div>
    </div>
  );
}
