// The word a search result's act carries, composed once.
//
// The result's panel offers the act and the add screen's card wears the chip
// once it is done, and the two must say the same thing — the only way to be
// sure of that is for there to be one sentence to say it. « Associer » is not a
// synonym of « Ajouter »: identifying a stuck folder tells the pipeline WHICH
// medium the folder is, and creates no follow. The words are `screens.add.verb`.
import i18next from "i18next";
import { identifying, isAdded } from "./add-visit";
import type { SearchResult } from "./types";

/**
 * The label of a search result's act, before and after it is done.
 *
 * A film is added and a series followed; in the identify mode both are
 * associated. Once done the label says so with a check. A result the library
 * already holds carries an ellipsis before it is done: the act opens a question
 * — it will replace something held — rather than happening on the spot.
 *
 * @param result The search result.
 * @returns The label.
 */
export function addVerb(result: SearchResult): string {
  const identify = identifying();
  const film = result.kind === "Film";
  const say = (key: string) => i18next.t(`screens.add.verb.${key}`);
  if (isAdded(result)) {
    return say(identify ? "associated" : film ? "added" : "followed");
  }
  const label = say(identify ? "associate" : film ? "add" : "follow");
  return result.owned && !identify ? `${label}…` : label;
}
