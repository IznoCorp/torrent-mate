// The device side of the push channel (fcm-push DESIGN § 3.6): detect, ask, obtain the FCM
// registration token, hand it over. NO UI — the opening offer and the Profil line that call
// it are drawn first (F-3), and the route the token is posted to is K5's: every function
// here takes the posting function as an argument.
//
// ONE WORKER. The Firebase SDK registers its own `firebase-messaging-sw.js` unless it is
// given a registration; it is always given the application's own (`navigator.serviceWorker.
// ready`), so the push and notificationclick listeners of `sw.js` receive the messages and
// no second worker ever exists.
//
// THE GESTURE. iOS grants the permission only from a direct user gesture, and an `await`
// before the request loses it: `registerPush` asks FIRST, synchronously from the caller's
// tap, and only then loads the SDK.
//
// THE TOKEN API, settled against the pinned SDK (firebase 12.19.0). `getToken` is marked
// deprecated there in favour of `register` + `onRegistered`, which deliver a Firebase
// Installation id. `getToken` is kept: it returns an FCM REGISTRATION TOKEN, the target
// `messages:send`'s `token` field is documented to accept; the SDK's note that « the backend
// send API supports FID as a target » is not in the HTTP v1 reference. The switch, when
// Firebase documents it, is confined to this file (`docs/reference/fcm-api.md`).
//
// The SDK is imported lazily: it is loaded on the device that turns notifications on, never
// in the bundle every page pays for.

/** The Web app's public configuration — not secrets (Firebase's own statement). */
export interface FcmWebConfig {
  firebase: {
    apiKey: string;
    authDomain?: string;
    projectId: string;
    messagingSenderId: string;
    appId: string;
  };
  /** The public half of the Web Push certificate (VAPID). */
  vapidKey: string;
}

export type PushSupport =
  | { kind: "unsupported" }
  | { kind: "needs-install" }
  | { kind: "available"; permission: NotificationPermission };

/** The named Firebase app the push channel uses, apart from any default app. */
const APP_NAME = "tm-push";

/** What `pushSupport` reads; the real globals by default, a fake one in tests. */
export interface PushEnvironment {
  userAgent: string;
  platform: string;
  maxTouchPoints: number;
  standalone: boolean;
  hasNotification: boolean;
  hasPushManager: boolean;
  hasServiceWorker: boolean;
  permission: NotificationPermission;
}

/** Reads the environment from the browser's globals. */
export function currentEnvironment(): PushEnvironment {
  const nav = navigator as Navigator & { standalone?: boolean };
  const hasNotification = typeof Notification !== "undefined";
  return {
    userAgent: nav.userAgent,
    platform: nav.platform,
    maxTouchPoints: nav.maxTouchPoints ?? 0,
    standalone: window.matchMedia?.("(display-mode: standalone)").matches === true || nav.standalone === true,
    hasNotification,
    hasPushManager: typeof PushManager !== "undefined",
    hasServiceWorker: "serviceWorker" in nav,
    permission: hasNotification ? Notification.permission : "default",
  };
}

/** iPhone, iPod, or an iPad — which reports itself as a Mac with a touch screen. */
function isAppleMobile(env: PushEnvironment): boolean {
  return /iPhone|iPad|iPod/.test(env.userAgent) || (env.platform === "MacIntel" && env.maxTouchPoints > 1);
}

/**
 * What this device can do. iOS / iPadOS exposes push ONLY to a web app launched from the home
 * screen, and a Safari tab does not even define the APIs — so « not installed » is told before
 * « unsupported », or an iPhone would be told it can never have notifications.
 */
export function pushSupport(env: PushEnvironment = currentEnvironment()): PushSupport {
  if (isAppleMobile(env) && !env.standalone) return { kind: "needs-install" };
  if (!env.hasNotification || !env.hasPushManager || !env.hasServiceWorker) return { kind: "unsupported" };
  return { kind: "available", permission: env.permission };
}

/** The SDK calls this module makes — the real ones, loaded lazily; fakes in tests. */
export interface MessagingSdk {
  token(config: FcmWebConfig, registration: ServiceWorkerRegistration): Promise<string>;
  forget(config: FcmWebConfig, registration: ServiceWorkerRegistration): Promise<void>;
}

async function messagingFor(config: FcmWebConfig) {
  const [{ getApps, initializeApp }, messaging] = await Promise.all([
    import("firebase/app"),
    import("firebase/messaging"),
  ]);
  const app = getApps().find((a) => a.name === APP_NAME) ?? initializeApp(config.firebase, APP_NAME);
  return { messaging: messaging.getMessaging(app), sdk: messaging };
}

export const firebaseSdk: MessagingSdk = {
  async token(config, registration) {
    const { messaging, sdk } = await messagingFor(config);
    return sdk.getToken(messaging, { vapidKey: config.vapidKey, serviceWorkerRegistration: registration });
  },
  // `deleteToken` takes no registration: on an instance none is bound to, it registers firebase's
  // default `firebase-messaging-sw.js` — a second worker. `getToken` with the application's
  // registration is the SDK's only public way to bind it; with a token already held it reads it
  // back from the SDK's store, nothing new is minted.
  async forget(config, registration) {
    const { messaging, sdk } = await messagingFor(config);
    await sdk.getToken(messaging, { vapidKey: config.vapidKey, serviceWorkerRegistration: registration });
    await sdk.deleteToken(messaging);
  },
};

/** The application's OWN worker registration — never a new one. */
function applicationRegistration(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.ready;
}

export interface PushDeps {
  requestPermission: () => Promise<NotificationPermission>;
  registration: () => Promise<ServiceWorkerRegistration>;
  sdk: MessagingSdk;
  permission: () => NotificationPermission;
  environment: () => PushEnvironment;
}

const browserDeps = (): PushDeps => ({
  requestPermission: () => Notification.requestPermission(),
  registration: applicationRegistration,
  sdk: firebaseSdk,
  permission: () => Notification.permission,
  environment: currentEnvironment,
});

/**
 * Asks the permission — MUST be called inside a user gesture (iOS) — and hands the FCM token,
 * obtained through the application's own worker registration, to `submit`.
 */
export async function registerPush(
  config: FcmWebConfig,
  submit: (token: string) => Promise<void>,
  deps: PushDeps = browserDeps(),
): Promise<"on" | "denied"> {
  // First, before any await: the gesture's grant does not survive one.
  const asked = deps.requestPermission();
  if ((await asked) !== "granted") return "denied";
  const token = await deps.sdk.token(config, await deps.registration());
  await submit(token);
  return "on";
}

/**
 * Re-sends the current token at every start when THIS DEVICE IS SUBSCRIBED — Firebase's monthly
 * refresh. The push subscription decides, not the permission: `unregisterPush` removes the
 * subscription (the SDK's `deleteToken`) and leaves the permission granted, so a device turned off
 * stays off; and iOS may read the permission as `default` after a reload while the subscription is
 * still there (firebase-js-sdk#8269), so the token is re-sent all the same. Never asks.
 */
export async function refreshPush(
  config: FcmWebConfig,
  submit: (token: string) => Promise<void>,
  deps: PushDeps = browserDeps(),
): Promise<void> {
  if (pushSupport(deps.environment()).kind !== "available") return;
  const registration = await deps.registration();
  if ((await registration.pushManager.getSubscription()) === null) return;
  await submit(await deps.sdk.token(config, registration));
}

/**
 * Turns notifications off on this device: the server forgets the token first (`revoke`), then the
 * SDK deletes it. The configuration is needed to reach the SDK's messaging instance.
 */
export async function unregisterPush(
  config: FcmWebConfig,
  revoke: (token: string) => Promise<void>,
  deps: PushDeps = browserDeps(),
): Promise<void> {
  if (deps.permission() !== "granted") return;
  const registration = await deps.registration();
  await revoke(await deps.sdk.token(config, registration));
  await deps.sdk.forget(config, registration);
}
