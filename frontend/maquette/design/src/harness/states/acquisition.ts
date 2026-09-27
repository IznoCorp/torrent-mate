// The named states of Acquisition — its three views, the add screen, the sheets it raises and the screens it opens.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { redraw } from "../../lib/shell-doors";

// How long after the list is drawn the paused fold is opened, as a finger would.
const OPEN_AFTER = 300;

export function acquisitionStates(): NamedState[] {
  // The store the shell creates and publishes, read when the table is built.
  const store = window.__store;
  return [
    [
      "acq-now-idle",
      "Acquisition · En cours — état réel (repos)",
      () =>
        applyState({
          page: "acq",
          acqTab: "now",
          scen: "real",
          phase: "ready",
        }),
    ],
    [
      "acq-now-loaded",
      "Acquisition · En cours — chargé",
      () =>
        applyState({
          page: "acq",
          acqTab: "now",
          scen: "loaded",
          phase: "ready",
        }),
    ],
    [
      "acq-now-loading",
      "Acquisition · En cours — chargement",
      () =>
        applyState({ page: "acq", acqTab: "now", phase: "loading" }),
    ],
    [
      "acq-now-error",
      "Acquisition · En cours — erreur",
      () => applyState({ page: "acq", acqTab: "now", phase: "error" }),
    ],
    [
      "acq-follows-list",
      "Acquisition · Suivis — liste",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "list",
          pill: "tout",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-group",
      "Acquisition · Suivis — groupé",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "group",
          pill: "tout",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-grid",
      "Acquisition · Suivis — grille",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "grid",
          pill: "tout",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-filter-empty",
      "Acquisition · Suivis — filtre sans résultat",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "list",
          filter: "zzz",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-paused",
      "Acquisition · Suivis — « En pause » déplié en fin de liste",
      () => {
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "list",
          pill: "tout",
          filter: "",
          phase: "ready",
        });
        // THE FOLD OPENED THE WAY A FINGER OPENS IT, once the list is drawn.
        window.setTimeout(() => {
          document.querySelector<HTMLElement>('[data-part="section/paused"] summary')?.click();
        }, OPEN_AFTER);
      },
    ],
    [
      "acq-follows-error",
      "Acquisition · Suivis — erreur",
      () => applyState({ page: "acq", acqTab: "follows", phase: "error" }),
    ],
    [
      "discover-full",
      "Découvrir — réserve pleine",
      () =>
        applyState({
          page: "discover",
          tmdb: true,
          phase: "ready",
          sugCount: 30,
        }),
    ],
    [
      "discover-posters",
      "Découvrir · affiches",
      () => {
        applyState({ page: "discover", phase: "ready" });
        store.write({ sugMode: "poster" });
        redraw();
      },
    ],
    [
      "discover-deck",
      "Découvrir · slide cards",
      () => {
        applyState({ page: "discover", phase: "ready" });
        store.write({ sugMode: "deck" });
        redraw();
      },
    ],
    [
      "discover-degraded",
      "Découvrir — sans compte TMDB",
      () =>
        applyState({
          page: "discover",
          tmdb: false,
          phase: "ready",
        }),
    ],
    [
      "discover-exhausted",
      "Découvrir — réserve épuisée",
      () =>
        applyState({
          page: "discover",
          tmdb: true,
          phase: "ready",
          sugCount: 999,
        }),
    ],
    [
      "discover-loading",
      "Découvrir — chargement",
      () =>
        applyState({ page: "discover", phase: "loading" }),
    ],
    [
      "acq-add-empty",
      "Écran d'ajout — au repos",
      () => {
        // THE TAB BENEATH IS PINNED: the driver's reset leaves `acqTab`.
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__screens.add("");
      },
    ],
    [
      "acq-add-results",
      "Écran d'ajout — résultats réels",
      () => {
        // THE TAB BENEATH IS PINNED: the driver's reset leaves `acqTab`.
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__screens.add("star wars");
      },
    ],
    [
      "followsheet-complete",
      "Feuille de suivi — gros catalogue complet",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__panel.produce("follow", "American Dad!");
      },
    ],
    [
      "followsheet-gaps",
      "Feuille de suivi — matrice à trous",
      () => {
        applyState({ page: "lib", libLens: "inc", phase: "ready" });
        window.__panel.produce("follow", "Les aventures de Tintin");
      },
    ],
    [
      "acq-identify",
      "Recherche en mode IDENTIFIER (depuis une résolution)",
      () => {
        applyState({ page: "arr", phase: "ready", pipe: "idle" });
        store.write({
          resolveTarget: "Backrooms.2026.MULTi.2160p.WEB-DL",
        });
        window.__screens.add("Backrooms 2026", "identify");
      },
    ],
    [
      "screen-releases",
      "Écran — choisir une autre release",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__screens.releases("Silo");
      },
    ],
    [
      "screen-profile",
      "Écran — profil de qualité",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__screens.profile("Silo");
      },
    ],
    [
      "sheet-journey",
      "Feuille de parcours",
      () => {
        applyState({ page: "acq", phase: "ready" });
        window.__panel.produce("journey", "Furious");
      },
    ],
    [
      "sheet-more",
      "Feuille « ⋮ » — veille et obligations",
      () => {
        applyState({ page: "acq", phase: "ready" });
        window.__panel.produce("more");
      },
    ],
    [
      "sheet-user",
      "Menu utilisateur — profil et déconnexion",
      () => {
        applyState({ page: "acq", phase: "ready" });
        window.__panel.produce("account");
      },
    ],
  ];
}
