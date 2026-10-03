// The named states of how an account signs in (the operator, 2026-10-03; O-K1-4) — the gate's
// Plex wait and its refusals, a local account changing its password in Profil, and « Comptes »
// saying how each account signs in, which one a Plex link demoted, and the provisional password
// an Admin gives a local account at creation and sets again on a reset (his « A »).
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

/**
 * Opens « Comptes » and submits its creation form for a local account.
 *
 * @param password The provisional password typed, empty for none.
 */
function createLocal(password: string): void {
  applyState({ page: "accounts", phase: "ready" });
  owed(() => {
    const form = document.querySelector<HTMLFormElement>('[data-part="accounts/create"]');
    if (!form) return;
    const fields: Record<string, string> = { name: "Nina", email: "nina@example.invalid", password };
    Object.entries(fields).forEach(([name, value]) => {
      (form.elements.namedItem(name) as HTMLInputElement).value = value;
    });
    form.requestSubmit();
  }, FILL_AFTER);
}

/**
 * Opens one account's panel in « Comptes ».
 *
 * @param account The account's id.
 */
function accountPanel(account: string): void {
  applyState({ page: "accounts", phase: "ready" });
  window.__panel.produce("roster", account);
}

/**
 * Opens a local account's panel and submits its provisional-password reset.
 *
 * @param password The new provisional password.
 */
function resetLocal(password: string): void {
  accountPanel("local-account");
  owed(() => {
    const form = document.querySelector<HTMLFormElement>('[data-part="accounts/password-reset"]');
    if (!form) return;
    (form.elements.namedItem("provisionalPassword") as HTMLInputElement).value = password;
    form.requestSubmit();
  }, FILL_AFTER);
}

// A manager who is not Admin, on a local account: Invité's rights, given accounts.manage (M7).
const LOCAL_MANAGER_RIGHTS = ["library.read", "accounts.manage"] as const;

/**
 * Signs in a local account whose role, not Admin's, manages accounts, and opens one panel.
 *
 * @param account The account whose panel is opened.
 */
function managerPanel(account: string): void {
  window.__mocks?.setRoleRights("local-guest", [...LOCAL_MANAGER_RIGHTS]);
  as("local-guest");
  accountPanel(account);
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
    [
      "accounts-create-provisional",
      "Comptes — un compte local créé avec son mot de passe provisoire, à changer dans son Profil",
      () => createLocal(LONG),
    ],
    [
      "accounts-create-password-missing",
      "Comptes — un compte local créé sans mot de passe provisoire : refusé, il est obligatoire",
      () => createLocal(""),
    ],
    [
      "accounts-reset-local",
      "Comptes — un compte local : son mot de passe provisoire se réinitialise ici",
      () => accountPanel("local-account"),
    ],
    [
      "accounts-reset-done",
      "Comptes — compte local : le mot de passe provisoire est enregistré, à lui communiquer",
      () => resetLocal(LONG),
    ],
    [
      "accounts-reset-too-short",
      "Comptes — compte local : le mot de passe provisoire est trop court, le minimum dit par le serveur",
      () => resetLocal(SHORT),
    ],
    [
      "accounts-owner-password",
      "Comptes — le propriétaire Plex : son mot de passe de secours ne se change que sur le serveur",
      () => accountPanel("izno"),
    ],
    [
      "accounts-plex-no-password",
      "Comptes — un compte lié à Plex : aucun mot de passe à réinitialiser",
      () => accountPanel("household-member"),
    ],
    [
      "accounts-reset-out-of-reach",
      "Comptes — un gestionnaire qui n'est pas Admin : le mot de passe d'un compte dont le rôle dépasse le sien ne se réinitialise pas",
      () => managerPanel("local-account"),
    ],
    [
      "accounts-reset-own",
      "Comptes — un gestionnaire qui n'est pas Admin, sur son propre compte : son mot de passe se change dans son Profil",
      () => managerPanel("local-guest"),
    ],
  ];
}
