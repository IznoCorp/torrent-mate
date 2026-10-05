// The named states of the library page, « Médiathèque ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { redraw } from "../../lib/shell-doors";
import { openDeleteDialog } from "../../features/library/delete-dialog";
import { librarySelection } from "../library-selection";
import type { Schemas } from "../../lib/contract-schemas";
import { libraryIncompleteQuery } from "../../features/library/queries";

/** When the kept states' seeding is owed until: 12 October 2026, 20:00 UTC, epoch seconds. */
const OWED_UNTIL = Date.UTC(2026, 9, 12, 20, 0) / 1000;

/**
 * Opens the delete dialog for some titles with some of them kept by the layer,
 * and confirms it as a reader would — the state is the dialog drawn AFTER.
 *
 * @param titles The titles the removal names.
 * @param keep The titles the layer keeps, each with its reason and the date its
 *     seeding is owed until (null when the store does not know it, or for
 *     another reason).
 */
function keptAfterConfirming(
  titles: string[],
  keep: Record<string, [NonNullable<Schemas["LibraryDeletion"]["reason"]>, number | null]>,
): void {
  // ONE TITLE IS SEARCHED FOR, as a reader finds the row they swipe: its row is
  // then drawn, and the state shows it still drawn once the layer kept it.
  applyState({ page: "lib", libLens: "cat", libMode: "list", q: titles.length === 1 ? titles[0] : "", phase: "ready" });
  const doomed = [...librarySelection(titles).values()];
  for (const one of doomed) {
    const kept = keep[one.title];
    if (kept !== undefined) window.__mocks?.setDeletionKept(one.ref, kept[0], kept[1]);
  }
  void openDeleteDialog(doomed).then(() => {
    let framesLeft = 60;
    const confirm = () => {
      const button = document.querySelector<HTMLElement>('[data-part="dialog/button"]');
      if (button !== null) button.click();
      else if (--framesLeft > 0) requestAnimationFrame(confirm);
    };
    confirm();
  });
}

export function libraryStates(): NamedState[] {
  // The store the shell creates and publishes, read when the table is built.
  const store = window.__store;
  return [
    [
      "lib-grid",
      "Médiathèque · Médias — grille",
      () =>
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "grid",
          q: "",
          phase: "ready",
          selMode: false,
        }),
    ],
    [
      "lib-list",
      "Médiathèque · Médias — liste",
      () =>
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "list",
          q: "",
          phase: "ready",
          selMode: false,
        }),
    ],
    [
      "lib-film-panel",
      "Médiathèque · Médias — le panneau d'un film (sa variante FILM : ni saisons ni épisodes)",
      () => {
        applyState({ page: "lib", libLens: "cat", libMode: "grid", q: "", phase: "ready", selMode: false });
        // A FILM THE LIBRARY HOLDS AND NOBODY FOLLOWS: its panel is the one
        // whose kind is read from the library's own item, not from a follow.
        // french-ok: a media title, which is data.
        window.__panel.produce("follow", "On l'appelait Robin des Bois");
      },
    ],
    [
      "lib-search-empty",
      "Médiathèque — recherche sans résultat",
      () =>
        applyState({ page: "lib", libLens: "cat", q: "zzzz", phase: "ready" }),
    ],
    [
      "lib-incomplete",
      "Médiathèque · Incomplets",
      () => applyState({ page: "lib", libLens: "inc", phase: "ready" }),
    ],
    [
      "lib-recent",
      "Médiathèque · Récents",
      () => applyState({ page: "lib", libLens: "rec", phase: "ready" }),
    ],
    [
      "lib-recent-movies",
      "Médiathèque · Récents — Films",
      () => applyState({ page: "lib", libLens: "rec", libCat: "movies", phase: "ready" }),
    ],
    [
      "lib-incomplete-movies",
      "Médiathèque · Incomplets — Films (vide : que des séries)",
      () => applyState({ page: "lib", libLens: "inc", libCat: "movies", phase: "ready" }),
    ],
    [
      "lib-selection",
      "Médiathèque — mode sélection",
      () => {
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "grid",
          phase: "ready",
          selMode: true,
        });
        // THE TITLES the selection ticks, each taken to its row's identity —
        // the three rows drawn at ranks 0, 2 and 5 of the unfiltered listing,
        // which is the source's own order. french-ok: media titles, which are data.
        store.write({
          selected: librarySelection([
            "On l'appelait Robin des Bois",
            "Big Chicken Le complot de la malbouffe",
            "Marjorie Prime",
          ]),
        });
        redraw();
      },
    ],
    [
      "lib-selection-filtered",
      "Médiathèque — sélection gardée sous « Films »",
      () => {
        // THE SAME THREE TITLES, then the category a reader switches to: the
        // documentary is ticked and no longer drawn, and the bar still counts it.
        applyState({
          page: "lib",
          libLens: "cat",
          libCat: "movies",
          libMode: "grid",
          phase: "ready",
          selMode: true,
        });
        // french-ok: media titles, which are data.
        store.write({
          selected: librarySelection([
            "On l'appelait Robin des Bois",
            "Big Chicken Le complot de la malbouffe",
            "Marjorie Prime",
          ]),
        });
        redraw();
      },
    ],
    [
      "lib-delete",
      "Médiathèque — dialogue de suppression",
      () => {
        applyState({ page: "lib", phase: "ready" });
        openDeleteDialog([...librarySelection(["Les Animaniacs"]).values()]);
      },
    ],
    [
      "lib-delete-multiple",
      "Médiathèque — suppression multiple",
      () => {
        applyState({ page: "lib", phase: "ready" });
        openDeleteDialog([...librarySelection(["Les Animaniacs", "La cour de récré", "Earl"]).values()]);
      },
    ],
    /* O-5 B (2026-10-03): an identity two library rows hold is not deleted
       until the duplicate is settled. « Doctor Who » is the seed's own: two
       rows, one TVDB id. The dialog names it and offers nothing but to close. */
    [
      "lib-delete-ambiguous",
      "Médiathèque — suppression refusée : un doublon",
      () => {
        applyState({ page: "lib", phase: "ready" });
        openDeleteDialog([...librarySelection(["Doctor Who"]).values()]);
      },
    ],
    /* TWO MEDIA, ONE TITLE: « RoboCop » 1987 (TMDB 5548) and 2014 (TMDB
       97020) are two films, each held once under its own id. Every act on one
       of the two rows names that row's medium, never the other. */
    [
      "lib-same-title",
      "Médiathèque — deux médias sous un même titre",
      () => applyState({ page: "lib", libLens: "cat", libMode: "list", q: "RoboCop", phase: "ready", selMode: false }),
    ],
    /* THE PIPELINE HOLDS ITS LOCK, and the server refuses the deletion
       `library.locked`: the confirmed row comes back and the toast says why in
       the interface's words. The dial is set AFTER the state's reset. */
    [
      "lib-delete-locked",
      "Médiathèque — suppression refusée : le pipeline tourne",
      () => {
        applyState({ page: "lib", libLens: "cat", libMode: "list", phase: "ready" });
        window.__mocks?.setPipelineState("running");
        void openDeleteDialog([...librarySelection(["Les Animaniacs"]).values()]).then(() => {
          let framesLeft = 60;
          const confirm = () => {
            const button = document.querySelector<HTMLElement>('[data-part="dialog/button"]');
            if (button !== null) button.click();
            else if (--framesLeft > 0) requestAnimationFrame(confirm);
          };
          confirm();
        });
      },
    ],
    /* R2 (« Raison par médias », 2026-10-05): the deletion answers medium by
       medium, and a medium it KEPT stays in the library — its row is never
       taken off the screen — while the dialog that follows names it with its
       reason. What keeps it is what the machine IS, a dial turned AFTER the
       state's reset; the removal is confirmed as a reader would. */
    [
      "lib-delete-kept-seed",
      "Médiathèque — suppression : gardé, partage dû jusqu'à une date",
      () => keptAfterConfirming(["Les Animaniacs"], { "Les Animaniacs": ["seed_owed", OWED_UNTIL] }),
    ],
    [
      "lib-delete-kept-disk",
      "Médiathèque — suppression : gardé, disque débranché",
      () => keptAfterConfirming(["Les Animaniacs"], { "Les Animaniacs": ["disk_unreachable", null] }),
    ],
    [
      "lib-delete-kept-failed",
      "Médiathèque — suppression : gardé, un dossier n'a pas pu partir",
      () => keptAfterConfirming(["Les Animaniacs"], { "Les Animaniacs": ["failed", null] }),
    ],
    [
      "lib-delete-partly",
      "Médiathèque — suppression partielle : deux partis, un gardé",
      () =>
        keptAfterConfirming(["Les Animaniacs", "La cour de récré", "Earl"], {
          "La cour de récré": ["seed_owed", OWED_UNTIL],
        }),
    ],
    /* N1: a show whose year nothing states is served `year: null`, and its line
       says what it is missing and nothing else. */
    [
      "lib-incomplete-yearless",
      "Médiathèque · Incomplets — une série sans année",
      () => {
        window.__mocks?.reset();
        // french-ok: a media title, which is data.
        window.__mocks?.setIncompleteYearless("Les Animaniacs");
        applyState({ page: "lib", libLens: "inc", libMode: "list", phase: "ready" });
        // The page asks for the incomplete shows as soon as the reset redraws it,
        // before this dial is turned: the answer it holds is asked again.
        void window.__queries?.resetQueries({ queryKey: libraryIncompleteQuery.queryKey });
      },
    ],
    [
      "lib-loading",
      "Médiathèque — chargement",
      () => applyState({ page: "lib", libLens: "cat", phase: "loading" }),
    ],
    [
      "lib-error",
      "Médiathèque — erreur",
      () => applyState({ page: "lib", libLens: "cat", phase: "error" }),
    ],
    /* The OTHER error, and it is a different surface: the page loaded, and the
       NEXT page of the list did not. It has always existed — the infinite
       scroll fails once, on purpose, to show that path for real — but only a
       long scroll reached it, so nothing could drive it and nothing measured
       the sentence it prints or the control that retries. */
    [
      "lib-error-more",
      "Médiathèque — la suite ne charge plus",
      () => {
        /* ONE write, not two: the failure has to be in force at the FIRST
           draw. Setting it afterwards lets the sentinel mount for one render,
           and a sentinel in view starts a load — which then lands 620 ms
           later, over the state, with a second page of media whose sheets are
           hollow (B-030). A state exists to show ONE thing; racing its own
           loader makes a red run say something other than what it is for. */
        /* THE FAILURE IS THE LAYER'S NOW, not a flag in the store. « The list
           loaded and then the next page did not » cannot be asked for by a
           status alone — an operation set to fail fails its FIRST call, and the
           list would never appear at all. `afterCalls: 1` lets the first page
           through and refuses the second, which is the state this exists to
           show. The reset is what makes it independent of whatever was driven
           before it. */
        window.__mocks?.reset();
        window.__mocks?.setOperationOutcome("readLibraryItems", {
          status: 500,
          afterCalls: 1,
          /* ONCE. « The next page failed » is a state whose way out is a retry
             that WORKS; an operation that keeps failing is a different state
             and draws differently. The engine said this with a `libFailedOnce`
             flag in the interface's own store. */
          failingCalls: 1,
        });
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "list",
          phase: "ready",
        });
        /* And ASK for the page that fails. The layer only fails a page somebody
           asks for, so a scenario alone leaves the list whole and the error
           nowhere — the state has to reach what it names. The waiting is the
           door's, not this state's: it is the same wait for every surface, and
           written here it would be written again for the next one. */
        window.__libraryNextPage?.();
      },
    ],
  ];
}
