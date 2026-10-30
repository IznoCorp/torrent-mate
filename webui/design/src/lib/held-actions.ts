// A send held back for the undo window of the message that announced it.
//
// WHY A SEND WAITS AT ALL. A gesture can be wrong, and the message answering it
// offers « Annuler » for a few seconds. When the layer has no operation that
// puts an act back — a resolve has none today — an undo is honest only while
// the act has not left. So the act is drawn at once, in the cache, and its send
// is held until the window closes; the undo puts the drawing back, and the send
// never leaves.
//
// IT KNOWS NO SUBJECT. What is held is a key, a scope and three verbs the caller
// writes: send the act, put its drawing back, draw it again. Which lists an act
// touches is the caller's knowledge, never this module's.
//
// WHAT A RELOAD DOES, said once: nothing was sent, so the act is lost and its
// subject is as it was before the gesture. That is the safe side, and it is why
// a cleared cache CANCELS a held send rather than flushing it.

/** One act drawn at once, whose send waits. */
export type HeldAction = {
  /** What the act is about. A second act on the same key replaces the first. */
  key: string;
  /** The world it was drawn in. A cleared world cancels what it holds. */
  scope: string;
  /** Sends the act, once the window has closed with no undo. */
  send: () => void;
  /** Puts back what the act drew, when it is undone. */
  putBack: () => void;
  /** Draws the act again over a fresher answer that no longer shows it. */
  drawAgain: () => void;
};

/** The held sends of one caller. */
export type HeldActions = {
  /** Holds an act's send for the window, and answers its undo. */
  hold: (act: HeldAction) => () => void;
  /** Draws every act held in a scope again, over a fresh answer. */
  drawAgain: (scope: string) => void;
  /** Forgets every act held in a scope, sending none of them. */
  cancel: (scope: string) => void;
};

/**
 * Creates the held acts of one caller, and the window their sends wait for.
 *
 * @param windowMilliseconds How long a send waits. At least the life of the
 *   message that offers the undo, or the undo outlives what it can undo.
 * @returns The three verbs.
 */
export function createHeldActions(windowMilliseconds: number): HeldActions {
  const held = new Map<string, { act: HeldAction; timer: number }>();
  const release = (key: string) => {
    const entry = held.get(key);
    if (entry !== undefined) window.clearTimeout(entry.timer);
    held.delete(key);
  };
  return {
    hold: (act) => {
      release(act.key);
      const timer = window.setTimeout(() => {
        held.delete(act.key);
        act.send();
      }, windowMilliseconds);
      held.set(act.key, { act, timer });
      // AN UNDO THAT COMES LATE DOES NOTHING. Once the send has left, or once a
      // second act on the same key has replaced this one, putting the drawing
      // back would draw a state the layer no longer holds.
      return () => {
        if (held.get(act.key)?.timer !== timer) return;
        release(act.key);
        act.putBack();
      };
    },
    drawAgain: (scope) => {
      for (const { act } of held.values()) {
        if (act.scope === scope) act.drawAgain();
      }
    },
    cancel: (scope) => {
      for (const [key, { act }] of held) {
        if (act.scope === scope) release(key);
      }
    },
  };
}
