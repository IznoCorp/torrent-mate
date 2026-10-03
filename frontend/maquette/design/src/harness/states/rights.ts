// The named states of § 17 — the application of an account that is not the
// owner's, each on an INVENTED identity the state dials (DESIGN maquette-l18
// § 2.2). The resting maquette is the owner's: nothing here is readable until
// one of these states turns its dial, and the driver's reset turns it back.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state.
import { applyState, onLeave, type NamedState } from "../drive";
import { openDrawer } from "../../app/frame-verbs";
import { WRITE_RIGHTS, type Right } from "../../lib/rights";
import { owed } from "../owed";

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

/** Raises the gate without writing history, as a driven state does. */
function showGate(): void {
  window.__entry?.showSignIn(false, true);
}

/**
 * Ends the gate's played wait as soon as it rises.
 *
 * A sign-in that walks through covers its landing with the startup screen for
 * the five seconds a real load is budgeted (`coverLoading`). A state whose
 * subject is the account's FIRST FRAME is the landing, not that wait: it rises
 * after the drive — the landing is asynchronous — so it is watched for, and
 * the watch stops when the next state is driven.
 */
function endStartupCover(): void {
  const splash = document.querySelector<HTMLElement>("#splash");
  if (!splash) return;
  const watch = new MutationObserver(() => {
    if (splash.hidden) return;
    watch.disconnect();
    window.__loadingDone?.();
  });
  watch.observe(splash, { attributes: true, attributeFilter: ["hidden"] });
  onLeave(() => watch.disconnect());
}

/** Taps one control of the gate. */
function tap(selector: string): void {
  document.querySelector<HTMLElement>(selector)?.click();
}

// A manager who is not Admin: the spectator's role, given accounts.manage.
const MANAGER_RIGHTS: Right[] = ["library.read", "acquisition.see.others", "accounts.manage", "acquisition.request"];

// How long the creation form waits for the roster before it is submitted empty.
const CREATE_AFTER = 400;

// A title the library holds, whose sheet offers the library's writes.
const OWNED = "American Dad!";

// Membre du foyer's rights (O-K1-4), and the quality an Admin may add to them.
const HOUSEHOLD_WITH_QUALITY: Right[] = [
  "library.read", "acquisition.request", "acquisition.follow", "acquisition.todo.view",
  "acquisition.pilot.own", "acquisition.pause.own", "acquisition.quality.own",
];

// A Plex-linked account's e-mail, typed at the password door.
const PLEX_LINKED_EMAIL = "lea@example.invalid";

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
      "Droits — la barre d'un invité qui demande (rôle de test) : Acquisition, Médiathèque, Découvrir",
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
      "Droits — Acquisition d'un invité qui demande (rôle de test) : ni « À traiter » ni son compte, son rôle ne tient pas le droit de le voir",
      () => {
        as("guest");
        // THE DIAL ASKS FOR « À TRAITER », and the page draws the first tab the
        // role opens instead (round 9 Q13).
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
      "Droits — le suivi d'un membre du foyer à qui un Admin a donné la qualité : sa qualité et sa pause, à lui, offertes",
      () => {
        // MEMBRE DU FOYER HOLDS NO QUALITY (O-K1-4): an Admin gave it here, in « Comptes ».
        window.__mocks?.setRoleRights("household", HOUSEHOLD_WITH_QUALITY);
        as("household-member");
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__panel.produce("follow", SHARED_FOLLOW);
      },
    ],
    [
      "quality-own-absent",
      "Droits — le même suivi pour un invité qui demande (rôle de test) : ni qualité ni pause, son rôle ne les tient pas",
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
      "media-cross-seed",
      "Droits — la fiche d'un média en cross-seed : son bloc tracker par tracker, pour qui voit les trackers",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet(OWNED, window.__carriedFor(OWNED) ?? undefined);
      },
    ],
    [
      "media-cross-seed-hidden",
      "Droits — la même fiche pour un membre du foyer : sans le droit de voir les trackers, aucun bloc cross-seed",
      () => {
        as("household-member");
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet(OWNED, window.__carriedFor(OWNED) ?? undefined);
      },
    ],
    [
      "profile-household",
      "Droits — Profil d'un membre du foyer : son rôle, ce qu'il peut faire, et qui détient le reste",
      () => {
        as("household-member");
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-guest",
      "Droits — Profil d'un invité qui demande (rôle de test)",
      () => {
        as("guest");
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-ceiling",
      "Droits — Profil de l'Admin sur l'instance en lecture seule",
      () => {
        window.__mocks?.setForbiddenWrites(EVERY_WRITE);
        reread();
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-preprod",
      "Droits — Profil de l'Admin en préproduction : la suppression nommée, le reste permis",
      () => {
        window.__mocks?.setForbiddenWrites(["library.delete"]);
        reread();
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "signin-password-open",
      "Connexion — « Utiliser un mot de passe » ouvert sous « Se connecter avec Plex »",
      () => {
        showGate();
        tap('[data-part="login/password-disclosure"]');
      },
    ],
    [
      "signin-plex-unreachable-open",
      "Connexion — Plex ne répond pas : le mot de passe s'ouvre de lui-même",
      () => {
        window.__mocks?.setPlexReachable(false);
        showGate();
        tap('[data-part="login/plex-submit"]');
      },
    ],
    [
      "signin-password-refused",
      "Connexion — le mot de passe d'un compte lié à Plex, refusé comme tout autre échec",
      () => {
        showGate();
        tap('[data-part="login/password-disclosure"]');
        const form = document.querySelector<HTMLFormElement>("#loginform");
        if (!form) return;
        (form.elements.namedItem("username") as HTMLInputElement).value = PLEX_LINKED_EMAIL;
        (form.elements.namedItem("password") as HTMLInputElement).value = "secret";
        form.requestSubmit();
      },
    ],
    [
      "signin-plex-bare",
      "Connexion — un compte Plex sans droit entre par Plex et arrive sur la Médiathèque, sans barre",
      () => {
        window.__mocks?.setIdentity("plex-without-rights");
        endStartupCover();
        showGate();
        tap('[data-part="login/plex-submit"]');
      },
    ],
    [
      "accounts-roster",
      "Comptes — la liste : un compte par ligne, son rôle, comment il se connecte",
      () => {
        reread();
        applyState({ page: "accounts", phase: "ready" });
      },
    ],
    [
      "accounts-detail",
      "Comptes — un compte ouvert : son rôle, et les rôles qu'on peut lui donner",
      () => {
        applyState({ page: "accounts", phase: "ready" });
        window.__panel.produce("roster", "household-member");
      },
    ],
    [
      "accounts-roles",
      "Comptes — un rôle ouvert : chaque droit, donné ou retiré",
      () => {
        applyState({ page: "accounts", phase: "ready" });
        window.__panel.produce("role", "household");
      },
    ],
    [
      "accounts-escalation-greyed",
      "Comptes — un gestionnaire qui n'est pas Admin : ce qui dépasse ses droits est grisé, l'Admin absent",
      () => {
        window.__mocks?.setRoleRights("spectator", MANAGER_RIGHTS);
        as("see-only");
        applyState({ page: "accounts", phase: "ready" });
        window.__panel.produce("roster", "household-member");
      },
    ],
    [
      "accounts-create-refused",
      "Comptes — un nouveau compte sans adresse e-mail, refusé",
      () => {
        applyState({ page: "accounts", phase: "ready" });
        owed(() => {
          const form = document.querySelector<HTMLFormElement>('[data-part="accounts/create"]');
          (form?.elements.namedItem("name") as HTMLInputElement | null)?.setAttribute("value", "Maya");
          form?.requestSubmit();
        }, CREATE_AFTER);
      },
    ],
    [
      "accounts-forbidden",
      "Comptes — ouvert par un membre du foyer : la page dit le droit qui manque",
      () => {
        as("household-member");
        applyState({ page: "accounts", phase: "ready" });
      },
    ],
    [
      "no-access",
      "Droits — un rôle qui n'ouvre aucune page : la page dédiée, la déconnexion seule",
      () => {
        window.__mocks?.setRoleRights("plex-guest", []);
        as("plex-without-rights");
        applyState({ page: "no-access", phase: "ready" });
      },
    ],
  ];
}
