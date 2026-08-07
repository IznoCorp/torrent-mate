/**
 * SwipeActions — reveal a card's actions by dragging it sideways.
 *
 * The action layer sits BEHIND the card and never moves; the card slides over
 * it. Moving the wrapper instead would drag the buttons out of view along with
 * the card, which is the bug that makes a swipe row feel broken.
 */

import {
  useCallback,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";

import { EDGE_DEAD_ZONE_PX, lockAxis } from "@/components/acquisition/gestures";

/** One action revealed by a swipe. */
export interface SwipeAction {
  readonly key: string;
  readonly label: string;
  readonly icon: ReactNode;
  readonly tone: "primary" | "neutral" | "danger";
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

/** Tailwind classes per tone. */
const TONE_CLASS: Record<SwipeAction["tone"], string> = {
  primary: "bg-primary text-primary-foreground",
  neutral: "bg-muted text-foreground",
  danger: "bg-danger text-danger-foreground",
};

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
}: SwipeActionsProps): ReactElement {
  const [offset, setOffset] = useState(0);
  const dragRef = useRef<{ x: number; y: number; axis: "x" | "y" | null } | null>(
    null,
  );

  const rightWidth = (right?.length ?? 0) * ACTION_WIDTH_PX;
  const leftWidth = left != null ? ACTION_WIDTH_PX : 0;

  const close = useCallback(() => {
    setOffset(0);
  }, []);

  const onPointerDown = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    // Same edge band as the pager: iOS owns it, and competing there produces a
    // half-navigation nobody asked for.
    if (e.clientX < EDGE_DEAD_ZONE_PX) return;
    dragRef.current = { x: e.clientX, y: e.clientY, axis: null };
  }, []);

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (drag == null) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag.axis ??= lockAxis(dx, dy);
      if (drag.axis !== "x") return;
      // Clamp to what actually exists: dragging towards an empty side must not
      // open a gap onto nothing.
      setOffset(Math.max(-rightWidth, Math.min(leftWidth, dx)));
    },
    [leftWidth, rightWidth],
  );

  const onPointerUp = useCallback(() => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (drag?.axis !== "x") return;
    setOffset((current) => {
      if (current <= -OPEN_THRESHOLD_PX) return -rightWidth;
      if (current >= OPEN_THRESHOLD_PX) return leftWidth;
      return 0;
    });
  }, [leftWidth, rightWidth]);

  function renderAction(action: SwipeAction): ReactElement {
    return (
      <button
        key={action.key}
        type="button"
        data-testid="swipe-action"
        // `flex-none` with a fixed basis, and NEVER a class named `grab`: the
        // sheet handle already owns that name at the same specificity, and the
        // later declaration wins — which once painted an action as a 36x4 pill.
        className={`flex flex-none basis-[84px] flex-col items-center justify-center gap-1 px-1 text-center text-[length:var(--text-2xs)] leading-tight ${TONE_CLASS[action.tone]}`}
        onClick={() => {
          action.onRun();
          close();
        }}
      >
        <span aria-hidden="true">{action.icon}</span>
        <span>{action.label}</span>
      </button>
    );
  }

  return (
    <div
      data-swipe
      data-testid="swipe-container"
      className="relative overflow-hidden rounded-lg"
    >
      {/* Action layer — behind the card, never translated. */}
      <div className="absolute inset-y-0 left-0 flex" aria-hidden={offset <= 0}>
        {left != null && renderAction(left)}
      </div>
      <div className="absolute inset-y-0 right-0 flex" aria-hidden={offset >= 0}>
        {right?.map(renderAction)}
      </div>

      <div
        data-testid="swipe-card"
        className="relative touch-pan-y transition-transform"
        style={{ transform: `translateX(${String(offset)}px)` }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {children}
      </div>
    </div>
  );
}
