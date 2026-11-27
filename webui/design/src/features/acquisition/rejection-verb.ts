// « Rejeter » and its « Annuler » (K3-G7): a rejection is the signed-in account's alone (O-9 A).
//
// THE CARD LEAVES IN THE TAP'S OWN TASK and the words wait for the answer: a rejection done, or held
// by the outbox, is said « écarté » with its « Annuler »; one the server refused puts the card back
// and says why. How the card leaves the view is the caller's: a row collapses, a deck card flies.
//
// A CARD IS TOLD BY ITS ID past the tap: the reserve may be read again while an answer is awaited,
// and the position it held then names another card.
import i18next from "i18next";
import { sharedQueryClient } from "../../lib/query-client";
import { refusalWords } from "../../lib/refusal";
import { toast } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { sendVerb, type VerbOutcome } from "./verb-outcome";
import { suggestions, suggestionsQuery } from "./queries";

const addressOf = (id: string) => `/api/v1/acquisition/suggestions/${encodeURIComponent(id)}/rejection`;

const positionOf = (id: string) => (suggestions?.() ?? []).findIndex((one) => one.id === id);

/**
 * Marks a card spent or not, where the deck consults it.
 *
 * `sugGone` is a Set mutated in place, so the store is touched for React to learn of it.
 *
 * @param id The card.
 * @param spent Whether the deck leaves it out.
 * @returns Whether the reserve holds the card.
 */
function spend(id: string, spent: boolean): boolean {
  const position = positionOf(id);
  if (position === -1) return false;
  const gone = store.read().state.sugGone as Set<number>;
  if (spent) gone.add(position);
  else gone.delete(position);
  store.touch();
  return true;
}

/**
 * Says why a write did not stand.
 *
 * @param sent How it ended: refused by the server, or never sent nor kept.
 * @param fallback The act's own words for a refusal that carries no code.
 */
function sayUnsent(sent: Extract<VerbOutcome<unknown>, { kind: "refused" | "failed" }>, fallback: string): void {
  toast?.show({
    message: sent.kind === "refused" ? refusalWords(sent.failure, fallback) : i18next.t("verbs.acquisition.failed"),
  });
}

/**
 * Undoes a rejection: the card is back at once, and leaves again if the server refuses.
 *
 * @param id The card.
 * @param redraw What draws the feed again.
 */
async function undoRejection(id: string, redraw: () => void): Promise<void> {
  if (spend(id, false)) redraw();
  const sent = await sendVerb("DELETE", addressOf(id));
  if (sent.kind === "refused" || sent.kind === "failed") {
    if (spend(id, true)) redraw();
    sayUnsent(sent, "verbs.deck.restoreRefused");
    return;
  }
  if (positionOf(id) !== -1) return;
  // THE RESERVE WAS READ AGAIN WITHOUT THE CARD, so only the server can hand it back.
  if (sent.kind === "held") return void toast?.show({ message: i18next.t("verbs.acquisition.held") });
  await sharedQueryClient?.invalidateQueries({ queryKey: suggestionsQuery.queryKey });
}

/**
 * Rejects one card of the reserve. The card is spent before this returns; the caller draws it
 * leaving.
 *
 * @param position The card's index into the reserve.
 * @param redraw What draws the feed again, when the card comes back.
 */
export async function rejectSuggestion(position: number, redraw: () => void): Promise<void> {
  const card = suggestions?.()?.[position];
  if (card === undefined) return;
  spend(card.id, true);
  const sent = await sendVerb("POST", addressOf(card.id));
  if (sent.kind === "refused" || sent.kind === "failed") {
    if (spend(card.id, false)) redraw();
    sayUnsent(sent, "verbs.deck.rejectRefused");
    return;
  }
  toast?.show({
    message: i18next.t("discover.dismissed", { title: card.title }),
    undo: () => void undoRejection(card.id, redraw),
  });
}
