// The named states of § 17 — the application of an account that is not the
// owner's, each on an INVENTED identity the state dials (DESIGN maquette-l18
// § 2.2). The resting maquette is the owner's: nothing here is readable until
// one of these states turns its dial, and the driver's reset turns it back.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state.
import { applyState, type NamedState } from "../drive";
import { openDrawer } from "../../app/frame-verbs";
import { WRITE_RIGHTS, type Right } from "../../lib/rights";

/**
 * Signs one invented account in, until the next state resets the layer.
 *
 * THE ACCOUNT IS READ AGAIN, and not as a courtesy: the driver's reset refills
 * the producers' reads — the account's among them — BEFORE the state runs, and
 * the layer answers synchronously, so the owner is already in the cache when
 * the dial turns. Dropping that answer is what a sign-in does (demand M).
 */
export function as(identity: string): void {
  window.__mocks?.setIdentity(identity);
  reread();
}

/**
 * Drops every answer the driver's reset already read, so the surfaces read the
 * layer again under the dials the state has just turned — the account, and the
 * lists whose requesters those dials change.
 */
function reread(): void {
  void window.__queries?.resetQueries();
}

/** Every WRITE right — what today's read-only instance forbids (ruling 23). */
export const EVERY_WRITE: Right[] = [...WRITE_RIGHTS];

// A title the library holds, whose sheet offers the library's writes.
const OWNED = "American Dad!";

// A follow four accounts asked for, each with its own settings in the seed.
const SHARED_FOLLOW = "Kyma, l'onde mystérieuse";

export function rightsStates(): NamedState[] {
  return [
    [
      "bar-household",
      "Droits — la barre d'un membre du foyer : Acquisition, Médiathèque, Découvrir",
      () => {
        as("household-member");
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
      },
    ],
    [
      "bar-guest",
      "Droits — la barre d'un invité Plex : Acquisition, Médiathèque, Découvrir",
      () => {
        as("guest");
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
      },
    ],
    [
      "bar-rightless",
      "Droits — un compte Plex sans droit : la Médiathèque seule, sans barre",
      () => {
        as("plex-without-rights");
        applyState({ page: "lib", phase: "ready" });
      },
    ],
    [
      "drawer-household",
      "Droits — le menu d'un membre du foyer : Trackers, Système, Maintenance et Réglages marqués « Réservé »",
      () => {
        as("household-member");
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        openDrawer();
      },
    ],
    [
      "place-reserved",
      "Droits — Système ouvert par un membre du foyer : la page dit le droit qui manque et qui le détient",
      () => {
        as("household-member");
        applyState({ page: "sys", phase: "ready" });
      },
    ],
    [
      "acq-household",
      "Droits — Acquisition d'un membre du foyer : ses seules demandes, « À traiter » vide",
      () => {
        as("household-member");
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
      },
    ],
    [
      "acq-household-sees-all",
      "Droits — Acquisition d'un membre qui voit tout : les demandes des autres en lecture seule, comptées nulle part",
      () => {
        as("household-member-sees-all");
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
      },
    ],
    [
      "acq-see-only",
      "Droits — un rôle qui voit sans demander : les onglets remplis, pas de « ＋ »",
      () => {
        as("see-only");
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
      },
    ],
    [
      "acq-guest",
      "Droits — Acquisition d'un invité Plex : sa carte « À traiter » sans les gestes du traitement",
      () => {
        as("guest");
        applyState({ page: "acq", acqTab: "todo", phase: "ready" });
      },
    ],
    [
      "acq-card-plural-requesters",
      "Droits — une carte demandée par plusieurs comptes : « demandé par izno et Noé »",
      () => {
        window.__mocks?.setInventedRequests(true);
        reread();
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
      },
    ],
    [
      "acq-card-read-only",
      "Droits — le parcours d'une carte d'un autre compte, lu sans ses gestes",
      () => {
        as("household-member-sees-all");
        applyState({ page: "acq", acqTab: "todo", phase: "ready" });
        window.__panel.produce("journey", "Lucky");
      },
    ],
    [
      "acq-reassign-chooser",
      "Droits — « Réaffecter… » : le choix ne propose que les comptes qui voient la carte",
      () => {
        window.__mocks?.setInventedRequests(true);
        reread();
        applyState({ page: "acq", acqTab: "todo", phase: "ready" });
        window.__panel.produce("reassign", "card|Star Trek: Strange New Worlds (2022)");
      },
    ],
    [
      "quality-own-offered",
      "Droits — le suivi d'un membre du foyer : sa qualité et sa pause, à lui, offertes",
      () => {
        as("household-member");
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__panel.produce("follow", SHARED_FOLLOW);
      },
    ],
    [
      "quality-own-absent",
      "Droits — le même suivi pour un invité Plex : ni qualité ni pause, son rôle ne les tient pas",
      () => {
        as("guest");
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__panel.produce("follow", SHARED_FOLLOW);
      },
    ],
    [
      "ceiling-operator",
      "Droits — l'instance en lecture seule : toute écriture absente, pour l'Admin aussi, et dite une fois",
      () => {
        window.__mocks?.setForbiddenWrites(EVERY_WRITE);
        reread();
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
      },
    ],
    [
      "ceiling-preprod",
      "Droits — la préproduction : seule la suppression de la médiathèque est interdite, et nommée",
      () => {
        window.__mocks?.setForbiddenWrites(["library.delete"]);
        reread();
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet(OWNED, window.__carriedFor(OWNED) ?? undefined);
      },
    ],
    [
      "no-access",
      "Droits — un rôle qui n'ouvre aucune page : la page dédiée, la déconnexion seule",
      () => {
        window.__mocks?.setRoleRights("default", []);
        as("plex-without-rights");
        applyState({ page: "no-access", phase: "ready" });
      },
    ],
  ];
}
