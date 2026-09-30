// The named states of Acquisition — its three views, the add screen, the sheets it raises and the screens it opens.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";

// How long after the list is drawn the paused fold is opened, as a finger would.
const OPEN_AFTER = 300;

// How far a finger throws a suggestion to commit its side, and how far it holds
// one mid-travel — past the uncovering, short of the commit.
const THROW = 170;
const HOLD = 70;
// How long the list's row takes to leave before the next gesture is read.
const SETTLE = 500;

/**
 * Lands on Découvrir in one view mode.
 *
 * @param mode The view: « list », « poster » or « deck ».
 */
function discoverIn(mode: string): void {
  applyState({ page: "discover", tmdb: true, phase: "ready" });
  store.write({ sugMode: mode });
  redraw();
}

/**
 * Drags the first element a selector names sideways, as a finger does, once it
 * is drawn — released past the threshold, or held mid-travel.
 *
 * @param selector What is dragged: the list's first row, or the deck's top card.
 * @param travel How far, negative to the left.
 * @param release Whether the finger lets go.
 * @param then What follows the gesture, once it has settled.
 */
function throwFirst(selector: string, travel: number, release: boolean, then?: () => void): void {
  window.setTimeout(() => {
    const held = document.querySelector<HTMLElement>(selector);
    if (held === null) return;
    const box = held.getBoundingClientRect();
    const x = box.left + box.width / 2;
    const y = box.top + box.height / 2;
    const at = (type: string, offset: number) =>
      held.dispatchEvent(new PointerEvent(type, { bubbles: true, isPrimary: true, pointerId: 1, pointerType: "touch", clientX: x + offset, clientY: y }));
    at("pointerdown", 0);
    for (let step = 1; step <= 6; step += 1) at("pointermove", (travel * step) / 6);
    if (release) window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, isPrimary: true, pointerId: 1, clientX: x + travel, clientY: y }));
    if (then) window.setTimeout(then, SETTLE);
  }, OPEN_AFTER);
}

/** Presses the notification's « Annuler », the way a finger does. */
function undo(): void {
  document.querySelector<HTMLElement>("#toastundo")?.click();
}

const LIST_ROW = '#view [data-part="suggestion/wrap"]';
const DECK_TOP = '[data-part="deck/card"][data-depth="0"]';

// A SETTLED DECISION ON THE JOURNEY SHEET (L24 S1): each medium's identification
// behind it — every rung before « vérifié dans Plex » done — so the block reads
// the decision the seed holds for it.
const DECISION_SUBJECTS = [
  ["sheet-journey-decision-operator", "President Curtis", "une correspondance choisie par vous"],
  ["sheet-journey-decision-engine", "Furious", "le moteur l'a identifié seul"],
  ["sheet-journey-decision-dismissed", "The Alabama Solution", "laissé tel quel"],
] as const;

/** The journey sheet over each kind of settled decision. */
function decisionStates(): NamedState[] {
  return DECISION_SUBJECTS.map(([id, subject, what]) => [
    id,
    `Feuille de parcours — l'identification réglée : ${what}`,
    () => {
      window.__mocks?.reset();
      window.__mocks?.placeAtPlexCheck(subject);
      applyState({ page: "acq", phase: "ready" });
      window.__panel.produce("journey", subject);
    },
  ]);
}

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
      "discover-header",
      "Découvrir — l'en-tête à côté des vues : « n séries et m films à découvrir », compté sur les suggestions lues",
      () => discoverIn("list"),
    ],
    [
      "discover-header-narrow",
      "Découvrir — l'en-tête coupé à la bascule de vue, et son toucher qui ouvre la phrase entière",
      () => {
        discoverIn("list");
        window.setTimeout(() => document.querySelector<HTMLElement>('#view [data-discover-header]')?.click(), OPEN_AFTER);
      },
    ],
    [
      "discover-header-loading",
      "Découvrir — l'en-tête pendant la lecture des suggestions",
      () => applyState({ page: "discover", tmdb: true, phase: "loading" }),
    ],
    [
      "discover-header-unavailable",
      "Découvrir — la lecture des suggestions a échoué : l'en-tête le dit, jamais vide",
      () => applyState({ page: "discover", tmdb: true, phase: "error" }),
    ],
    [
      "discover-list-travel-left",
      "Découvrir · liste — une ligne tenue à mi-course vers la gauche : « Passer » découvert",
      () => {
        discoverIn("list");
        throwFirst(LIST_ROW, -HOLD, false);
      },
    ],
    [
      "discover-list-travel-right",
      "Découvrir · liste — une ligne tenue à mi-course vers la droite : « Pas intéressé » découvert",
      () => {
        discoverIn("list");
        throwFirst(LIST_ROW, HOLD, false);
      },
    ],
    [
      "discover-list-passed",
      "Découvrir · liste — glissée à gauche : passée, partie de sa place, sans notification",
      () => {
        discoverIn("list");
        throwFirst(LIST_ROW, -THROW, true);
      },
    ],
    [
      "discover-list-passed-returns",
      "Découvrir · liste — la suggestion passée revient en bas de la liste, après toutes celles pas encore passées",
      () => {
        discoverIn("list");
        throwFirst(LIST_ROW, -THROW, true, () =>
          document.querySelector('#view [data-part="suggestion/wrap"]:last-of-type')?.scrollIntoView());
      },
    ],
    [
      "discover-list-rejected",
      "Découvrir · liste — glissée à droite : rejetée, la notification offre « Annuler »",
      () => {
        discoverIn("list");
        throwFirst(LIST_ROW, THROW, true);
      },
    ],
    [
      "discover-list-reject-undone",
      "Découvrir · liste — rejetée puis « Annuler » : la ligne revient à sa place",
      () => {
        discoverIn("list");
        throwFirst(LIST_ROW, THROW, true, undo);
      },
    ],
    [
      "discover-deck-passed",
      "Découvrir · deck — glissée à gauche : passée, la carte suivante monte, sans notification",
      () => {
        discoverIn("deck");
        throwFirst(DECK_TOP, -THROW, true);
      },
    ],
    [
      "discover-deck-rejected",
      "Découvrir · deck — glissée à droite : rejetée, la notification offre « Annuler »",
      () => {
        discoverIn("deck");
        throwFirst(DECK_TOP, THROW, true);
      },
    ],
    [
      "discover-deck-reject-undone",
      "Découvrir · deck — rejetée puis « Annuler » : la carte revient sur la pile",
      () => {
        discoverIn("deck");
        throwFirst(DECK_TOP, THROW, true, undo);
      },
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
        applyState({ page: "acq", acqTab: "todo", phase: "ready", pipe: "idle" });
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
    ...decisionStates(),
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
