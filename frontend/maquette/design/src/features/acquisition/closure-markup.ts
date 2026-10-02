// What a CLOSED tunnel's card says and offers (Q8, Q9; maquette-blocked §
// 1.5, § 1.6) — the acquisition card's own reason line, chip and foot, fed by
// the closure the queue serves until the account has seen it. Nothing here is
// drawn: `card-markup.ts` draws it, as it draws every card.
//
// ITS OWN FILE on a SUBJECT — what a closure says — and because the card's
// module stands at the 400-line ceiling the acquisition feature respects.
import i18next from "i18next";
import { providerAddress } from "../../lib/held-identity";
import { escapeMarkup } from "../../ui/markup";
import type { MediumCard, MediumCardFoot } from "./card-markup";

// The tone of a closed tunnel's chip: it has ended, and nothing in it is his to judge.
export const CLOSED_TONE = "neutral";
// A superseded release: its torrent keeps seeding; any other closure reopens.
const SUPERSEDED = "superseded";

// Where a release line may break: after each of its dots. Its words are
// joined by dots, never spaces, and a line of fifty figures that breaks only at
// its last hyphen grows the card a line, and crops its poster past R47's bound.
const RELEASE_BREAK = /\./g;
// What stands for the winner while the sentence around it is escaped.
const WINNER_MARK = "\u2063";

/**
 * What a closed tunnel says (Q8, Q9; maquette-blocked § 1.5, § 1.6): why it
 * closed, then what follows — a return opens a new tunnel; a superseded
 * release's torrent keeps seeding. The winner's release line, named whole,
 * may break after each of its dots.
 *
 * @param closure The closure, as served.
 * @returns The two sentences, as markup.
 */
export function closureMarkup(closure: NonNullable<MediumCard["closure"]>): string {
  const why = i18next.t(`surfaces.card.closure.${closure.reason}`, { winner: WINNER_MARK });
  const then = i18next.t(closure.reason === SUPERSEDED ? "surfaces.card.closure.seeding" : "surfaces.card.closure.reopens");
  const winner = escapeMarkup(closure.winner ?? "").replace(RELEASE_BREAK, ".<wbr>");
  return escapeMarkup(`${why} ${then}`).replace(WINNER_MARK, winner);
}

/**
 * The foot of a closed tunnel's card: « Voir la fiche », where a sheet stands
 * behind it — addressed by the medium's identity, never its title alone
 * (B-616). « Marquer comme vu » is not a foot: it is in the card's panel
 * (DECIDED 2).
 *
 * @param medium The card's row.
 * @returns The foot, or undefined for a closure with no sheet behind it.
 */
export function closureFoot(medium: Pick<MediumCard, "title" | "ids">): MediumCardFoot | undefined {
  const address = providerAddress(medium.ids ?? null);
  if (address === null) return undefined;
  return {
    label: i18next.t("panels.journey.seeSheet"),
    attributes: { "data-mediasheet": medium.title, "data-provider": address.provider, "data-provider-id": address.id },
  };
}
