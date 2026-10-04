// The named states of the account page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, onLeave, type NamedState } from "../drive";
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

export function accountStates(): NamedState[] {
  return [
    [
      "profile",
      "Profil et préférences",
      () => applyState({ page: "profile", phase: "ready" }),
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
