// The named states of the account page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, onLeave, type NamedState } from "../drive";
import { forgetOwed, owed } from "../owed";
import { as, EVERY_WRITE } from "./rights";
import { poseDevice, type PosedDevice } from "../../features/account/push-device";
import type { PushEnvironment } from "../../lib/push-registration";

// AN ANDROID PHONE with every push API — the operator's own device.
const ANDROID: PushEnvironment = {
  userAgent: "Mozilla/5.0 (Linux; Android 15; Pixel 9) Mobile",
  platform: "Linux armv8l",
  maxTouchPoints: 5,
  standalone: true,
  hasNotification: true,
  hasPushManager: true,
  hasServiceWorker: true,
  permission: "granted",
};

// AN IPHONE in a Safari tab: no push until the application is on the home screen.
const IPHONE_TAB: PushEnvironment = {
  ...ANDROID,
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148",
  platform: "iPhone",
  standalone: false,
  hasNotification: false,
  hasPushManager: false,
  permission: "default",
};

// A DESKTOP BROWSER with no Push API.
const NO_PUSH: PushEnvironment = {
  ...ANDROID,
  userAgent: "Mozilla/5.0 (X11; Linux x86_64)",
  platform: "Linux x86_64",
  maxTouchPoints: 0,
  standalone: false,
  hasPushManager: false,
  permission: "default",
};

/**
 * Opens Profil on a posed device, the pose lifted when the next state is driven.
 *
 * @param device The device the state shows.
 */
function profileOn(device: PosedDevice): void {
  poseDevice(device);
  onLeave(() => poseDevice(null));
  applyState({ page: "profile", phase: "ready" });
}

// How long Profil waits for its section to be drawn before the language is tapped.
const TAP_AFTER = 400;
// Long enough that a language asked for is still being asked when the state is read.
const HELD_FOR = 600_000;

/**
 * Opens Profil and taps one language of « Langue », the server answering as the state dialled.
 *
 * @param language The language tapped.
 */
function chooseLanguageInProfile(language: "fr" | "en"): void {
  applyState({ page: "profile", phase: "ready" });
  // THE TAP IS FORGOTTEN WHEN THE NEXT STATE IS DRIVEN: landing after it, it would switch the
  // language of a state that never asked.
  const tapping = owed(() => {
    document.querySelector<HTMLElement>(`[data-part="profile/language"] [data-language-choice="${language}"]`)?.click();
  }, TAP_AFTER);
  onLeave(() => forgetOwed(tapping));
}

// How long Profil waits before a session's « Mettre fin » is pressed, and before the confirmation's
// own button is pressed after it opened.
const PRESS_END_AFTER = 400;
const PRESS_CONFIRM_AFTER = 900;

/**
 * Opens Profil, presses « Mettre fin » on the first other session and confirms the dialog that names
 * it, the server answering as the state dialled.
 */
function endAnotherSession(): void {
  applyState({ page: "profile", phase: "ready" });
  // THE PRESSES ARE FORGOTTEN WHEN THE NEXT STATE IS DRIVEN: landing after it, they would end a
  // session in a state that never asked.
  const pressing = owed(() => {
    document.querySelector<HTMLElement>('[data-part="profile/session"]:not([data-current]) [data-part="profile/session-end"]')?.click();
  }, PRESS_END_AFTER);
  const confirming = owed(() => {
    document.querySelector<HTMLElement>('[data-part="dialog/button"][data-tone="danger"]')?.click();
  }, PRESS_CONFIRM_AFTER);
  onLeave(() => {
    forgetOwed(pressing);
    forgetOwed(confirming);
  });
}

export function accountStates(): NamedState[] {
  return [
    [
      "profile",
      "Profil et préférences",
      () => applyState({ page: "profile", phase: "ready" }),
    ],
    [
      "profile-language-english",
      "Profil — un compte dont la langue est l'anglais : toute l'interface est en anglais",
      () => {
        window.__mocks?.setLanguage("en");
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-language-saving",
      "Profil — « Langue » : l'anglais est demandé, le serveur n'a pas encore répondu",
      () => {
        window.__mocks?.setOperationOutcome("setOwnLanguage", { latencyMilliseconds: HELD_FOR });
        chooseLanguageInProfile("en");
      },
    ],
    [
      "profile-language-refused",
      "Profil — « Langue » : le serveur refuse le changement, la langue reste celle qu'il tient",
      () => {
        window.__mocks?.setOperationOutcome("setOwnLanguage", { status: 403 });
        chooseLanguageInProfile("en");
      },
    ],
    [
      "profile-sessions",
      "Profil — « Appareils connectés » : la session en cours nommée, deux autres révocables, une connexion à lire",
      () => applyState({ page: "profile", phase: "ready" }),
    ],
    [
      "profile-sessions-loading",
      "Profil — « Appareils connectés » : le serveur n'a pas encore répondu",
      () => {
        window.__mocks?.setOperationOutcome("readOwnSessions", { latencyMilliseconds: HELD_FOR });
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-sessions-only-current",
      "Profil — « Appareils connectés » : aucune autre session que celle en cours",
      () => {
        window.__mocks?.poseOnlyCurrentSession();
        window.__mocks?.poseNoNotices();
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-sessions-load-failed",
      "Profil — « Appareils connectés » : les sessions ne se lisent pas, un bouton pour réessayer",
      () => {
        window.__mocks?.setOperationOutcome("readOwnSessions", { status: 500 });
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-sessions-revoking",
      "Profil — « Appareils connectés » : la fin d'une session est confirmée, le serveur n'a pas encore répondu",
      () => {
        window.__mocks?.setOperationOutcome("revokeOwnSession", { latencyMilliseconds: HELD_FOR });
        endAnotherSession();
      },
    ],
    [
      "profile-sessions-revoke-failed",
      "Profil — « Appareils connectés » : le serveur refuse de fermer la session, elle reste ouverte et le dit",
      () => {
        window.__mocks?.setOperationOutcome("revokeOwnSession", { status: 404 });
        endAnotherSession();
      },
    ],
    [
      "profile-sessions-offline",
      "Profil — « Appareils connectés » : hors connexion, la fin de la session est retenue et dite comme telle",
      () => {
        endAnotherSession();
        // THE NETWORK GOES DOWN AFTER THE LIST IS READ: the end is then held, not refused.
        const down = owed(() => window.__mocks?.setOffline(true), PRESS_END_AFTER / 2);
        onLeave(() => {
          forgetOwed(down);
          window.__mocks?.setOffline(false);
        });
      },
    ],
    [
      "profile-notices-read",
      "Profil — « Connexions récentes » : toutes lues, plus de bouton pour les marquer",
      () => {
        window.__mocks?.poseNoticesRead();
        applyState({ page: "profile", phase: "ready" });
      },
    ],
    [
      "profile-notifications",
      "Profil — « Notifications » : cet appareil les reçoit, un interrupteur par type",
      () => profileOn({ environment: ANDROID, answer: "granted" }),
    ],
    [
      "profile-notifications-unasked",
      "Profil — « Notifications » : cet appareil n'a pas encore été autorisé, « Activer sur cet appareil »",
      () => profileOn({ environment: { ...ANDROID, permission: "default" }, answer: "granted" }),
    ],
    [
      "profile-notifications-denied",
      "Profil — « Notifications » : la permission refusée par le navigateur",
      () => profileOn({ environment: { ...ANDROID, permission: "denied" }, answer: "denied" }),
    ],
    [
      "profile-notifications-needs-install",
      "Profil — « Notifications » : un iPhone dans Safari, l'application à installer",
      () => profileOn({ environment: IPHONE_TAB, answer: "default" }),
    ],
    [
      "profile-notifications-unsupported",
      "Profil — « Notifications » : un navigateur sans notifications",
      () => profileOn({ environment: NO_PUSH, answer: "default" }),
    ],
    [
      "profile-notifications-ceiling",
      "Profil — « Notifications » sur l'instance en lecture seule : les interrupteurs se pressent, le serveur refuse et le dit",
      () => {
        window.__mocks?.setForbiddenWrites(EVERY_WRITE);
        // THE SERVER'S OWN REFUSAL (`require_not_staging`): no right is subtracted, the write is answered 403.
        window.__mocks?.setOperationOutcome("updateNotificationPreference", { status: 403 });
        window.__mocks?.setOperationOutcome("registerPushDevice", { status: 403 });
        void window.__queries?.resetQueries();
        profileOn({ environment: { ...ANDROID, permission: "default" }, answer: "granted" });
      },
    ],
    [
      "profile-notifications-household",
      "Profil — « Notifications » d'un membre du foyer : seuls les types de ses droits",
      () => {
        as("household-member");
        profileOn({ environment: ANDROID, answer: "granted" });
      },
    ],
    [
      "profile-notifications-none",
      "Profil d'un compte qui ne reçoit aucun type : pas de section « Notifications »",
      () => {
        as("plex-without-rights");
        profileOn({ environment: ANDROID, answer: "granted" });
      },
    ],
    // B-695: THE ACCOUNT MENU OF EACH PICTURE THE SERVER RESOLVES — a Plex
    // picture, a Gravatar, neither, and one whose picture fails to load, which
    // must read as neither: the initial in the bar, no picture in the panel.
    ...(
      [
        ["sheet-user-plex-picture", "Menu utilisateur d'un compte lié à Plex : sa photo Plex", "just-linked"],
        ["sheet-user-gravatar", "Menu utilisateur d'un compte local : son Gravatar", "local-guest"],
        ["sheet-user-initials", "Menu utilisateur d'un compte sans photo Plex ni Gravatar : son initiale", "local-account"],
        ["sheet-user-picture-fails", "Menu utilisateur d'un compte dont la photo ne se charge pas : son initiale", "guest-with-quality"],
      ] as const
    ).map(([id, label, account]): NamedState => [
      id,
      label,
      () => {
        as(account);
        // PROFIL, which every account sees — a guest's role may not see Acquisition.
        applyState({ page: "profile", phase: "ready" });
        window.__panel.produce("account");
      },
    ]),
  ];
}
