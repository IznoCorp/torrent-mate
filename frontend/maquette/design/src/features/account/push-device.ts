// This device and the push channel, as Profil's « Notifications » section says it (F-3).
//
// THE DEVICE'S LINE NAMES ONE OF FIVE SUPPORTS, read off `pushSupport`: granted here, not yet
// asked (`unasked` — the browser's `default` permission, renamed so no source reads like a
// comparison with the Default role; the one support « Activer » is offered on, since a browser
// never asks twice),
// refused, an iPhone that must install the application first, a browser with no push at all.
//
// « ACTIVER » IS THE PERMISSION FLOW OF `lib/push-registration.ts`, unchanged: the permission is
// asked first, inside the press (iOS), then the token is obtained and handed to
// `registerPushDevice` (K5). The prototype has no Firebase project: the token comes from
// `PROTOTYPE_SDK`, and the switchover hands `registerPush` the real configuration and SDK.
//
// A NAMED STATE POSES THE DEVICE — its environment and the answer its permission prompt gives —
// because a headless browser has one device only, and the five supports are five devices.
import { send } from "../../lib/query-client";
import {
  currentEnvironment,
  pushSupport,
  registerPush,
  type FcmWebConfig,
  type MessagingSdk,
  type PushEnvironment,
} from "../../lib/push-registration";
import type { components } from "../../contract/types";

/** What the device's line says. */
export type DeviceSupport = "granted" | "unasked" | "denied" | "needs-install" | "unsupported";

type Platform = components["schemas"]["PushDevice"]["platform"];

/** A device a named state poses: its environment, and what its permission prompt answers. */
export type PosedDevice = { environment: PushEnvironment; answer: NotificationPermission };

/** The line's word for each permission the browser reports. */
const SUPPORT_OF_PERMISSION: Readonly<Record<NotificationPermission, DeviceSupport>> = {
  default: "unasked",
  granted: "granted",
  denied: "denied",
};

let posed: PosedDevice | null = null;
let generation = 0;

/**
 * Poses the device a named state shows, until the next state clears it.
 *
 * @param device The device, or null for the browser's own.
 */
export function poseDevice(device: PosedDevice | null): void {
  posed = device;
  generation += 1;
}

/**
 * Which device is posed, as a number that moves at every pose — the line is keyed by it, so a
 * page left mounted between two states draws the second device rather than the first's flow.
 *
 * @returns The pose's generation.
 */
export function poseGeneration(): number {
  return generation;
}

/**
 * This device's environment — the posed one, else the browser's.
 *
 * @returns The environment `pushSupport` reads.
 */
function environment(): PushEnvironment {
  return posed?.environment ?? currentEnvironment();
}

/**
 * What the device's line says, from what the device can do.
 *
 * @param env The device's environment.
 * @returns Its support, in the line's five words.
 */
export function deviceSupport(env: PushEnvironment = environment()): DeviceSupport {
  const support = pushSupport(env);
  if (support.kind !== "available") return support.kind;
  return SUPPORT_OF_PERMISSION[support.permission];
}

/**
 * The device's family, as the registration names it.
 *
 * @param env The device's environment.
 * @returns android, ios or desktop.
 */
export function platformOf(env: PushEnvironment): Platform {
  if (/iPhone|iPad|iPod/.test(env.userAgent) || (env.platform === "MacIntel" && env.maxTouchPoints > 1)) return "ios";
  if (/Android/.test(env.userAgent)) return "android";
  return "desktop";
}

// THE PROTOTYPE'S STAND-IN for the Firebase SDK: a token per device family, the same at every
// press, as the real SDK returns the token it already holds.
const PROTOTYPE_SDK: MessagingSdk = {
  token: async () => `prototype-token-${platformOf(environment())}`,
  forget: async () => undefined,
};

// The configuration the real SDK needs; the stand-in reads none of it.
const PROTOTYPE_CONFIG: FcmWebConfig = {
  firebase: { apiKey: "", projectId: "", messagingSenderId: "", appId: "" },
  vapidKey: "",
};

/**
 * « Activer sur cet appareil »: asks the permission — called from the press itself — and,
 * granted, registers the device's token for the account.
 *
 * @returns The device's support once the flow has ended.
 * @throws The registration's refusal, when the server does not take the token.
 */
export async function enablePush(): Promise<DeviceSupport> {
  const env = environment();
  const outcome = await registerPush(
    PROTOTYPE_CONFIG,
    async (token) => {
      await send("POST", "/api/v1/notifications/devices", { token, platform: platformOf(env) });
    },
    {
      requestPermission: () => (posed ? Promise.resolve(posed.answer) : Notification.requestPermission()),
      registration: async () => ({}) as ServiceWorkerRegistration,
      sdk: PROTOTYPE_SDK,
      permission: () => (posed ? posed.answer : Notification.permission),
      environment,
    },
  );
  return outcome === "on" ? "granted" : "denied";
}
