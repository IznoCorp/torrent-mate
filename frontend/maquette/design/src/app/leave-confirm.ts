// LEAVING A PAGE WITH EDITS WAITING — asked once, whichever way one leaves.
//
// The operator, 2026-09-29 (C1): « Si on veux quitter réglages un message de
// confirmation s'affiche, avec enregistrer, abandonné les modif, ou fermer
// rester sur réglages » — and on Trackers: « Oui ». A page that holds the
// settings' pending edits (`holdsEdits`, `app/navigation.ts`) is left by the
// bar, the menu, a link, or Retour; the first three are the frame's three page
// verbs (`app/frame-verbs.ts`), Retour is the ladder (`app/layers.ts`). Each asks
// HERE before it leaves, so the confirmation is one, and no emitter asks it.
//
// WHAT WAITS IS THE PENDING EDITS' OWN ANSWER (`lib/pending-edits-door.ts`), the
// table the save bar counts: there is no second dirty-tracker.
import i18next from "../i18n";
import { pendingEdits } from "../lib/pending-edits-door";
import { bridge, dialog } from "../lib/shell-doors";
import { store } from "../lib/store-access";
import { rowFor } from "./navigation";
import { walk } from "./page-switch";

/** The page drawn now. */
function currentPage(): string {
  return String(store.read().state.page ?? "");
}

/**
 * Whether leaving a page for another must ask first.
 *
 * @param from The page being left.
 * @param to The page the leave lands on.
 * @returns True when `from` holds edits, some wait, and `to` is another page.
 */
function askFirst(from: string, to: string): boolean {
  if (walk.driven || from === to || rowFor(from)?.holdsEdits !== true) return false;
  return (pendingEdits()?.waiting() ?? 0) > 0;
}

/**
 * Opens the three-choice confirmation over the page being left.
 *
 * « Enregistrer » writes, then leaves — and a write that failed keeps its edits
 * and stays, where the failure is drawn; « Abandonner les modifications » drops
 * them, then leaves; « Rester sur … » closes the confirmation AND the layer the
 * leave was asked from — the menu, the account sheet — so the page is given back
 * bare: the operator's « fermer, rester sur réglages » (C1's reader, 2026-09-30).
 *
 * THE LEAVE WAITS FOR THE CONFIRMATION'S OWN ENTRY TO BE GONE. Closing the
 * dialog pops the entry it pushed, and that pop is asynchronous: a leave written
 * in the same task would land first and the pop would undo it. So the leave is
 * handed to the ladder's latch (`walk.afterUnwind`), which fires it once the pop
 * has landed — the dialog's close issues the pop before the choice runs.
 *
 * @param from The page being left — its name is in the words.
 * @param leave What leaves, once the choice allows it.
 * @param stay What « Rester » closes besides the confirmation, if anything.
 */
export function askToLeave(from: string, leave: () => void, stay?: () => void): void {
  const edits = pendingEdits();
  if (edits === undefined || dialog === undefined) {
    leave();
    return;
  }
  const count = edits.waiting();
  const page = i18next.t(rowFor(from)?.labelKey ?? "navigation.pages.cfg");
  let entryLaid = false;
  const onceClosed = (act: () => void) => () => {
    if (!entryLaid) {
      act();
      return;
    }
    walk.afterUnwind = () => {
      act();
      return true;
    };
  };
  dialog.open({
    heading: i18next.t("screens.settings.leaveHeading"),
    body: [{
      type: "paragraph",
      runs: [{ text: i18next.t(count > 1 ? "screens.settings.leaveBodyMany" : "screens.settings.leaveBodyOne",
        { count, page }) }],
    }],
    actions: [
      {
        text: i18next.t("screens.settings.leaveSave"),
        tone: "primary",
        run: onceClosed(() => {
          void edits.save().then(() => {
            if (edits.waiting() === 0) leave();
          });
        }),
      },
      {
        text: i18next.t("screens.settings.leaveAbandon"),
        tone: "dangerOutline",
        run: onceClosed(() => {
          edits.drop();
          leave();
        }),
      },
      {
        text: i18next.t("screens.settings.leaveStay", { page }),
        tone: "ghost",
        dismiss: true,
        run: stay ? onceClosed(stay) : undefined,
      },
    ],
  });
  entryLaid = Boolean(history.state && history.state.layer === "dialog");
}

/**
 * Asks before a page verb leaves a page with edits waiting.
 *
 * @param to The page the verb lands on.
 * @param leave The verb's own leave, run as it would have run.
 * @param stay What « Rester » closes besides the confirmation: the layer the
 *     verb was pressed in.
 * @returns True when the confirmation holds the leave; the caller then does
 *     nothing more.
 */
export function heldLeave(to: string, leave: () => void, stay?: () => void): boolean {
  const from = currentPage();
  if (!askFirst(from, to)) return false;
  askToLeave(from, leave, stay);
  return true;
}

/**
 * Holds a Retour that would leave a page with edits waiting.
 *
 * The gesture has ALREADY stepped back onto the entry under the page, with the
 * page still drawn. The page's own entry is stepped forward onto again,
 * announced so the ladder does not read it, and the confirmation opens once it
 * has landed: « Rester » leaves the page exactly as it was — its entry on top,
 * so the next Retour asks again — and the two others leave by the Retour the
 * gesture asked for.
 *
 * @param to The page the Retour would give back.
 * @returns True when the Retour is held; the ladder then does nothing more.
 */
export function heldBack(to: string): boolean {
  const from = currentPage();
  if (!askFirst(from, to)) return false;
  try {
    bridge.forward();
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("heldBack: stepping back onto the page failed", error);
    window.__navEchec = true;
    return false;
  }
  walk.afterUnwind = () => {
    askToLeave(from, () => bridge.back());
    return true;
  };
  return true;
}
