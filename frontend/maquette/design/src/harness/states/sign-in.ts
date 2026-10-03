// The named states of how an account signs in (the operator, 2026-10-03; O-K1-4) — the gate's
// Plex wait and its refusals, a local account changing its password in Profil, and « Comptes »
// saying how each account signs in and which one a Plex link demoted.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and what the oracle's
// reference names, the label says the state in words, and `run` builds the state.
import { applyState, type NamedState } from "../drive";
import { owed } from "../owed";
import { as } from "./rights";

// How long a form waits for its surface to be drawn before it is filled.
const FILL_AFTER = 400;

/** Raises the gate without writing history, as a driven state does. */
function showGate(): void {
  window.__entry?.showSignIn(false, true);
}

/** Taps one control of the gate. */
function tap(selector: string): void {
  document.querySelector<HTMLElement>(selector)?.click();
}

/** Starts a Plex sign-in at the gate, Plex answering as the dial says. */
function plexWith(claim: "pending" | "no-access" | "expired"): void {
  window.__mocks?.setPlexClaim(claim);
  showGate();
  tap('[data-part="login/plex-submit"]');
}

/**
 * Opens Profil as a local account and submits its password form.
 *
 * @param fields The three fields, in order: current, new, new again.
 */
function changePassword(fields: [string, string, string]): void {
  as("local-account");
  applyState({ page: "profile", phase: "ready" });
  owed(() => {
    const form = document.querySelector<HTMLFormElement>('[data-part="profile/password"]');
    if (!form) return;
    const names = ["currentPassword", "newPassword", "confirmPassword"];
    names.forEach((name, index) => {
      (form.elements.namedItem(name) as HTMLInputElement).value = fields[index];
    });
    form.requestSubmit();
  }, FILL_AFTER);
}

// A password long enough for the layer's minimum, and one that is not.
const LONG = "correct horse battery";
const SHORT = "court";

export function signInStates(): NamedState[] {
  return [
    [
      "signin-plex-pending",
      "Connexion — Plex ouvert, en attente de confirmation : rouvrir la page, ou annuler",
      () => plexWith("pending"),
    ],
    [
      "signin-plex-refused",
      "Connexion — un compte Plex sans accès au serveur : refusé comme tout autre échec",
      () => plexWith("no-access"),
    ],
    [
      "signin-plex-expired",
      "Connexion — la demande Plex a expiré avant d'être confirmée",
      () => plexWith("expired"),
    ],
    [
      "profile-local",
      "Profil — un compte local : sa connexion par mot de passe, et le formulaire pour le changer",
      () => {
        as("local-account");
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-password-current-wrong",
      "Profil — compte local : le mot de passe actuel est refusé",
      () => {
        window.__mocks?.setPasswordAccepted(false);
        changePassword([LONG, `${LONG}!`, `${LONG}!`]);
      },
    ],
    [
      "profile-password-too-short",
      "Profil — compte local : le nouveau mot de passe est trop court, le minimum dit par le serveur",
      () => changePassword([LONG, SHORT, SHORT]),
    ],
    [
      "profile-password-mismatch",
      "Profil — compte local : les deux nouveaux mots de passe diffèrent, dit sans rien demander",
      () => changePassword([LONG, `${LONG}!`, `${LONG}?`]),
    ],
    [
      "profile-password-changed",
      "Profil — compte local : le mot de passe est changé",
      () => changePassword([LONG, `${LONG}!`, `${LONG}!`]),
    ],
    [
      "profile-plex-linked",
      "Profil — un compte lié à Plex : Plex uniquement, pas de mot de passe ici",
      () => {
        as("household-member");
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "accounts-linked-demoted",
      "Comptes — un compte local devenu utilisateur du serveur Plex : lié, revenu au rôle de départ, à promouvoir",
      () => {
        applyState({ page: "accounts", phase: "ready" });
        window.__panel.produce("roster", "just-linked");
      },
    ],
  ];
}
