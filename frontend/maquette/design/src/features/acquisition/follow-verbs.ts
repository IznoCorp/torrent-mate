// THE FOLLOWS' VERBS, answered here rather than by the dying engine.
//
// « Ajouter » / « Suivre la série » is the acquisition's act: it puts a medium
// into what the operator is waiting for. Its EMITTERS were React already — a
// suggestion's panel and a medium's own sheet — and what moves here is the
// READER. The engine's branch and its body are deleted in the same commit; the
// engine dies by SUBTRACTION (D5) and the size ledger refuses it upward.
//
// TWO EMITTERS, ONE ACT, AND THEY DIFFER BY WHAT THEY CARRY BESIDE THE NAME.
// A suggestion carries `sugidx`, its POSITION in the reserve; a sheet carries
// `fkind`, the medium's KIND — spelled here as the emitters spell them, since
// the prefixed form is a name and this file is not where either is coined. The position is what lets the deck
// know the card is spent — following something is answering the question the
// deck asked — and the kind is what decides which sentence the act says, since
// §5 has a film ADDED and a series FOLLOWED: the one has an end and the other
// does not.
//
// THE BUMP IS EXPLICIT, twice, and it was the engine's reason as much as ours.
// `add` writes the follows cache IN PLACE and no re-render follows on this
// path: the sheet's button becomes « done » only if React is told, and the
// dismissed suggestion leaves the deck only if it is told again. A `write`
// would have given both for free; a Set mutated in place does not.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";

/** A suggestion as the reserve holds it — the two fields this act reads. */
type Suggestion = { t: string; k: string };

/** How long a dismissed row takes to collapse, in milliseconds. */
const COLLAPSE = 320;

/**
 * Whether this medium is already followed, under any spelling of its title.
 *
 * THROUGH `baseTitle` ON BOTH SIDES, which is the engine's own test and not a
 * refinement of it: a follow recorded as « Silo (2023) » and a sheet titled
 * « Silo » are one medium, and adding the second would leave the operator with
 * two rows for one thing and no way to tell them apart.
 *
 * Args:
 *     title: The medium's title, as the emitter carries it.
 *
 * Returns:
 *     True when the follows already hold it.
 */
function alreadyFollowed(title: string): boolean {
  const base = window.__referentiel.baseTitle;
  return (window.__followActions?.all() ?? []).some(
    (follow) => base(follow.t) === base(title));
}

/**
 * Takes a suggestion out of the deck, with the collapse the row is drawn for.
 *
 * `sugGone` is a Set of POSITIONS mutated in place, so the store is touched
 * rather than written — and the row is collapsed by hand because the pile is
 * not rebuilt on this path: a replaced node cannot animate, which is why the
 * engine did it this way and why moving the reader does not change it.
 *
 * Args:
 *     position: The suggestion's index into the reserve.
 */
function takeSuggestionOutOfTheDeck(position: number): void {
  (window.__store.read().state.sugGone as Set<number>).add(position);
  window.__store.touch();
  const row = document.querySelector<HTMLElement>(
    `[data-dismissable="${position}"]`);
  if (!row) return;
  row.style.height = `${row.getBoundingClientRect().height}px`;
  requestAnimationFrame(() => row.classList.add("gone"));
  setTimeout(() => row.remove(), COLLAPSE);
}

/**
 * Follows a medium, and says which of the two things it did.
 *
 * IT RETURNS EARLY ON A MEDIUM ALREADY FOLLOWED, and says nothing: the act has
 * already happened, and a second message about it would report an event that
 * did not occur.
 *
 * Args:
 *     title: The medium's title.
 *     kind: What the emitter said it is — the suggestion's `k`, or the sheet's
 *         `fkind`. ANYTHING THAT IS NOT A FILM IS A SERIES, which is the
 *         engine's own default and the safe one: a series is followed
 *         indefinitely and a film is not, so a kind nobody supplied errs
 *         towards the state that keeps looking.
 */
function follow(title: string, kind: string): void {
  if (alreadyFollowed(title)) return;
  // french-ok: an attribute VALUE, frozen with the DOM contract `media-details.tsx`
  // emits and the reserve carries — the same literal, compared where it arrives
  const film = kind === "Film";
  window.__followActions?.add({
    t: title,
    k: film ? "movie" : "show",
    st: "unverified",
    fresh: true,
  });
  window.__toast?.show({
    message: i18next.t(film ? "verbs.follows.added" : "verbs.follows.followed",
                       { title }),
  });
}

/**
 * Stops looking for a medium, or starts again — the same act, both ways.
 *
 * IT TOGGLES, and that is why nothing here names a destination. The row and
 * the panel both offer one button whose meaning is « change this », so a
 * caller that passed a status would be deciding what the operator can only
 * have meant by pressing it once.
 *
 * WHAT A LIFTED PAUSE GOES BACK TO DEPENDS ON THE KIND, and it is §5 again: a
 * film is still being looked for, so it returns to `pending`; a series has no
 * end, so it returns to `up_to_date` and resumes watching for what comes next.
 * There is no third answer, and a status this function invented would be a
 * fact about the medium that nothing measured.
 *
 * Args:
 *     title: The medium's title, which is the only key the follows are held
 *         by — the row reads it off its own heading and the panel carries it
 *         in the attribute, so both arrive here spelled the same way.
 */
function pause(title: string): void {
  const found = (window.__followActions?.all() ?? []).find(
    (follow) => follow.t === title);
  if (!found) return;
  const before = found.st;
  const after = before === "disabled"
    ? (found.k === "movie" ? "pending" : "up_to_date")
    : "disabled";
  // THE BUMP IS EXPLICIT, and for the same reason it is in `follow`: the
  // status is written into the query cache, which moves what React observes
  // and moves nothing the engine still draws. The undo needs it just as much
  // as the act does, so both go through this one door.
  const put = (status: string) => {
    window.__followActions?.setStatus(title, status);
    window.__store.touch();
  };
  put(after);
  const resumed = after !== "disabled";
  window.__toast?.show({
    message: i18next.t(
      resumed
        ? "verbs.follows.resumed"
        // french-ok: an attribute VALUE frozen with the follows contract — the
        // same literal the layer answers with, compared where it arrives
        : found.k === "movie"
          ? "verbs.follows.searchStopped"
          : "verbs.follows.paused",
      { title: found.t }),
    // THE UNDO MOVES WITH THE VERB IT UNDOES. It restores what WAS rather
    // than toggling again: a second toggle is the same act repeated, and it
    // would land on the wrong side of anything that moved in between.
    undo: () => put(before),
  });
}

declare global {
  interface Window {
    /**
     * The follows' acts, for the callers the tap registry is not.
     *
     * TWO OF THEM NOW, and they are not the same kind of caller — the door was
     * opened for the first and this says why the second uses it, since a door
     * whose reason is stale is one nobody dares close.
     *
     * · The add screen follows a medium after a confirmation it draws itself,
     *   so it reaches the act without a `data-*` ever being tapped.
     * · A swiped-open ROW's revealed action is dispatched by CLASS — the
     *   engine reads `.act` then `.pause`, and takes the subject from the
     *   row's own heading text. There is no attribute on that button for a
     *   registry to answer, and giving it one is DRAWING, which is not this
     *   lot's. So the engine's branch keeps the gesture's bookkeeping — the
     *   drawer it must collapse — and calls the act through here.
     *
     * Both callers are the engine's and die with it; until then they call
     * through this door rather than keeping a second copy of an act, which is
     * how two truths about one follow start.
     */
    __followVerbs?: {
      follow: (title: string, kind: string) => void;
      pause: (title: string) => void;
    };
  }
}

// THE DECLARATION RUNS AT MODULE EVALUATION, exactly as a panel producer's
// does, and the boot names this module in `app/panel-contributions.ts` — the
// list whose job is to name what each feature contributes. It is not an
// `install…()` the shell calls: `app/shell.tsx` stood ONE LINE under a 400-line
// hard block, and two acts with an import and a call each took it over. That
// list exists so a feature's contribution costs the shell nothing.
//
// ONE VERB, TWO EMITTERS, and the element is what tells them apart — which is
// why the registry hands the element to the act rather than the value alone.
window.__followVerbs = { follow, pause };
registerVerb("follow", (title, element) => {
  const at = element.dataset.sugidx;
  const suggestion = at === undefined
    ? null
    : ((window.__suggestions?.() ?? [])[Number(at)] as Suggestion | undefined)
      ?? null;
  // THE PANEL LEAVES FIRST, in the tap's own commit. The act happens beside
  // it rather than after a wait: the 240 ms the engine spent here is B-249's
  // shape, and a panel that is still on screen while the follows move is a
  // reader watching two things happen in the wrong order.
  window.__panel.close();
  if (at !== undefined) takeSuggestionOutOfTheDeck(Number(at));
  // AN ABSENT KIND IS SPELLED AS ONE, not as the series' own word: the test
  // below asks whether it is a film, so the empty string answers « series »
  // without this file holding a second interface word to keep in step.
  follow(title, suggestion?.k ?? element.dataset.fkind ?? "");
  // AND THE STORE IS TOUCHED AGAIN, for the sheet's own button: `add` writes
  // the cache in place, so without this the button never learns the follow
  // happened and stays « Suivre » under the finger that pressed it.
  window.__store.touch();
});

// THE PANEL'S OWN ACT, whose target is `data-pause`. Only the panel emits it:
// the row's button carries a class instead, and is dispatched above through
// `__followVerbs`.
//
// THE PANEL LEAVES FIRST, in the tap's own commit, and the 240 ms the engine
// waited here goes with the branch (B-249). The panel leaves inside the
// navigation's own commit, so the wait bought nothing but a state that had
// already moved being announced late.
registerVerb("pause", (title) => {
  window.__panel.close();
  pause(title);
});
