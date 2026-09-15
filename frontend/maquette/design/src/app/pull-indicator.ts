// THE PULL'S INDICATOR — what a completed pull MEANS, drawn by the frame.
//
// The GESTURE is `lib/pull-gesture.ts`'s: the axis decision, the edge dead zone,
// the damping and the arming distance are vocabulary, and vocabulary knows
// nothing of what refreshes. What is here is the other half — the indicator
// opening under the finger, the spinner while the refresh is in flight, and the
// message that says it happened. It is the FRAME's because the indicator is the
// frame's own affordance, sitting above every page and belonging to none.
//
// THE REFRESH IS A WAIT, NOT A READ, in this prototype: a fixed 1 100 ms, moved
// here exactly as it stood. Making it a real read is B-331's, and B-331 is a
// later lot's (c·5) — a conversion carries what it finds.
import i18next from "i18next";
import { installPullGesture } from "../lib/pull-gesture";
import { toast } from "../lib/shell-doors";

/** How long the prototype's refresh takes, in milliseconds. */
const REFRESH_MILLISECONDS = 1100;

/** How tall the indicator stands while the refresh is in flight. */
const LOADING_HEIGHT_PIXELS = 44;

/** The two states the indicator carries while a pull is being answered. */
const ARMED_MARK = "armed";
const LOADING_MARK = "loading";

let refreshing = false;
let refreshTimer: number | null = null;

/**
 * Puts the indicator back to rest, a refresh in flight included.
 *
 * A REFRESH OUTLIVES A CHANGE OF STATE, and the indicator's classes are not part
 * of the state object, so without this a measurement inherits the spinner of the
 * one before it — which is exactly how a first pass at this gesture reported it
 * working on half the surfaces and broken on the other half, in alternation.
 *
 * IT REMOVES THE TWO STATE CLASSES RATHER THAN THE CLASS LIST (ruling 59). The
 * engine wrote `ptr.className = "ptr"` here, which took every utility the
 * markup paints with it — which is why the indicator's own states had to be
 * read on the SPINNER inside it rather than on the indicator. Nothing is
 * erased now, so a utility written on the indicator survives a reset.
 *
 * @param indicator The indicator element, when the document has one.
 * @param reset What puts the gesture itself back.
 * @returns True, so a driver can await it like any other verb.
 */
function putBackToRest(indicator: HTMLElement | null, reset: () => void): boolean {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
  refreshing = false;
  reset();
  if (indicator) {
    indicator.classList.remove(LOADING_MARK, ARMED_MARK);
    indicator.style.height = "0px";
    indicator.style.transition = "";
  }
  return true;
}

/** Puts the indicator and the gesture back at rest — the harness driver's verb. */
export let resetPullIndicator: (() => boolean) | undefined;

/**
 * Draws the indicator for the pull gesture, on one scrollport.
 *
 * @param port The scrolling element the gesture is read on.
 * @param indicator The indicator drawn above it.
 */
export function installPullIndicator(port: HTMLElement, indicator: HTMLElement | null): void {
  const gesture = installPullGesture({
    port,
    /* THE SURFACES THAT OWN THEIR OWN HORIZONTAL GESTURE are excluded, or the
       pull fires beside them and the page navigates away mid-drag. They are
       named by the classes their own drawing paints, which is what the engine
       read too: these move with that drawing, not with this gesture. */
    isExcluded: (target) =>
      !!(
        target.closest?.(".swipe") ||
        target.closest?.(".sugwrap") ||
        target.closest?.(".deck") ||
        target.closest?.(".pillscroll")
      ),
    onPull: (pulled, armed) => {
      if (refreshing || !indicator) return;
      indicator.style.height = pulled + "px";
      indicator.style.transition = "none";
      indicator.classList.toggle(ARMED_MARK, armed);
    },
    onRelease: (armed) => {
      if (!indicator) return;
      indicator.style.transition = "";
      if (armed && !refreshing) {
        refreshing = true;
        indicator.classList.add(LOADING_MARK);
        indicator.style.height = `${LOADING_HEIGHT_PIXELS}px`;
        refreshTimer = window.setTimeout(() => {
          refreshTimer = null;
          refreshing = false;
          indicator.classList.remove(LOADING_MARK, ARMED_MARK);
          indicator.style.height = "0px";
          toast?.show({ message: i18next.t("message.refreshed") });
        }, REFRESH_MILLISECONDS);
      } else {
        indicator.style.height = "0px";
        indicator.classList.remove(ARMED_MARK);
      }
    },
  });
  resetPullIndicator = () => putBackToRest(indicator, () => gesture.reset());
}
