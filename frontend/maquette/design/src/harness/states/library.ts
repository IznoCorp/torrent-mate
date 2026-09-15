// The named states of the library page, « Médiathèque ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { redraw } from "../../lib/shell-doors";
import { openDeleteDialog } from "../../features/library/delete-dialog";

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
        // THE TITLES, because the selection is keyed by title — the three
        // rows drawn at ranks 0, 2 and 5 of the unfiltered listing, which is
        // the source's own order. french-ok: media titles, which are data.
        store.write({
          selected: new Set([
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
          selected: new Set([
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
        openDeleteDialog("Les Animaniacs");
      },
    ],
    [
      "lib-delete-multiple",
      "Médiathèque — suppression multiple",
      () => {
        applyState({ page: "lib", phase: "ready" });
        openDeleteDialog(null, ["Les Animaniacs", "La cour de récré", "Earl"]);
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
