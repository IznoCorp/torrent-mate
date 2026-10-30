// THE ONE PLACE A GESTURE IS ACKNOWLEDGED.
//
// Every gesture in the interface passes through `feedback()`. It is VISUAL
// today, and that is the whole point of it existing now rather than later: D9
// refuses the haptic capability and builds the seam.
//
//     Haptics — refuse the capability, build the seam. The target platform
//     exposes no public API; the workarounds ride an implementation detail that
//     has already been tightened once. One `feedback()` call site all gestures
//     pass through, visual today — so adopting it later changes one file.
//
// EXACTLY ONE IMPLEMENTATION, AND THAT IS A COUNT SOMETHING READS. A second
// acknowledgement written into a surface is the defect this seam exists to
// prevent: the day haptics become possible, a second implementation is a
// gesture that stays silent and nobody knows why.
//
// WHY IT WRITES AN ATTRIBUTE RATHER THAN ANIMATING. Rule 1 — what is
// declarative lives in the stylesheet, therefore in the design reference,
// therefore under the oracle. This module decides WHEN a gesture is
// acknowledged; `styles/base.css` decides what that looks like, and reduced
// motion is a designed state there rather than a branch here (invariant 14).
// Motion written in JavaScript leaves the field of measurement.

/**
 * What a gesture did, as far as the acknowledgement is concerned.
 *
 * The kind describes the GESTURE's outcome rather than the surface it happened
 * on: a seam that needed a new kind per surface would be a seam in name only.
 * `commit` is a gesture that completed and changed something.
 *
 * IT SHIPPED WITH A SECOND KIND, `refuse`, THAT NOTHING EMITTED. No gesture in
 * the interface declines one today, and the stylesheet reads `[data-feedback]`
 * without looking at its value — so the kind was a name with one end, and a
 * union of two where one is unreachable reads as a choice somebody makes. It
 * comes back the day a gesture is actually refused, which is when its drawing
 * has to be decided anyway.
 */
export type FeedbackKind = "commit";

/** How long the acknowledgement stays marked, in milliseconds. */
const FEEDBACK_MILLISECONDS = 200;

/** The mark's attribute — read by `styles/base.css`, and by the rule. */
const FEEDBACK_ATTRIBUTE = "data-feedback";

/** Timers in flight, per element, so a repeated gesture restarts cleanly. */
const pending = new WeakMap<Element, number>();

/**
 * Acknowledges a gesture.
 *
 * The single call site every gesture passes through. Today it marks the element
 * so the stylesheet can answer; the day the platform exposes haptics, this
 * function is the one file that changes.
 *
 * Args:
 *     kind: What the gesture did — it completed, or it was declined.
 *     element: What it happened on. When absent, nothing is marked: a gesture
 *         with no surface still passes through the seam, so the call site count
 *         stays honest and a later haptic answer reaches it.
 */
export function feedback(kind: FeedbackKind, element?: Element | null): void {
  if (!element) return;
  const running = pending.get(element);
  if (running !== undefined) window.clearTimeout(running);
  element.setAttribute(FEEDBACK_ATTRIBUTE, kind);
  pending.set(
    element,
    window.setTimeout(() => {
      element.removeAttribute(FEEDBACK_ATTRIBUTE);
      pending.delete(element);
    }, FEEDBACK_MILLISECONDS),
  );
}
