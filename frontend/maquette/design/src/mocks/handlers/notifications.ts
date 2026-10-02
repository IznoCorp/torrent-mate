// The account's notification switches and its devices' push tokens (the operator,
// 2026-10-03: « couper les notifications FCM de certains types tout en gardant les autres »).
//
// THE CHOICE IS THE ACCOUNT'S, on all its devices (ruling Q1 A): it is held here, by the
// layer, keyed by the signed-in account — never by the device that made it — so a fresh read
// from any device answers it.
//
// THE READ IS FILTERED BY RIGHTS, server side: a type is offered only to an account holding the
// right that type asks (`x-rights` on the contract's `NotificationType`, held equal to
// `NOTIFICATION_RIGHTS` by `notifications.test.ts`), so the page draws what it is answered and
// knows no table of its own.
import { POST, PUT, GET, field, route, text } from "./shared";
import { refused, type MockRoute } from "../router";
import { signedInId, signedInRights } from "../identity";
import { mockState } from "../state";
import type { components } from "../../contract/types";
import type { Right } from "../../lib/rights";

type NotificationType = components["schemas"]["NotificationType"];
type Platform = components["schemas"]["PushDevice"]["platform"];

const INVALID = 400;
const FORBIDDEN = 403;
const PLATFORMS: readonly Platform[] = ["android", "ios", "desktop"];

/** The right each type asks, in the contract's order — the contract's `x-rights`. */
export const NOTIFICATION_RIGHTS: Readonly<Record<NotificationType, Right>> = {
  "obligation.met": "trackers.view",
  "obligation.released": "trackers.view",
  "obligation.breached": "trackers.view",
  "tracker.ratio_low": "trackers.view",
  "tracker.disabled": "trackers.view",
  "crossseed.failed": "trackers.view",
  "acquisition.arrived": "acquisition.follow",
  "acquisition.to_handle": "acquisition.todo.view",
  "system.run_failed": "system.view",
  "system.disk_full": "system.view",
  "system.service_down": "system.view",
};

/**
 * The types the signed-in account may receive, in the contract's order.
 *
 * @returns The types whose right it holds.
 */
function receivable(): NotificationType[] {
  const rights = signedInRights();
  return (Object.keys(NOTIFICATION_RIGHTS) as NotificationType[]).filter((one) =>
    rights.holds(NOTIFICATION_RIGHTS[one]),
  );
}

/**
 * The types the signed-in account turned off.
 *
 * @returns Its list, created empty on first use.
 */
function turnedOff(): NotificationType[] {
  const held = mockState().notificationsOff;
  return (held[signedInId()] ??= []);
}

/**
 * One type's switch for the signed-in account.
 *
 * @param type The type.
 * @returns The switch as the contract shapes it.
 */
function preference(type: NotificationType) {
  return { type, enabled: !turnedOff().includes(type) };
}

export function notificationRoutes(): MockRoute[] {
  return [
    route("readNotificationPreferences", GET, "/api/notifications/preferences", () => ({
      preferences: receivable().map(preference),
    })),
    route("updateNotificationPreference", PUT, "/api/notifications/preferences/{type}", (request) => {
      const type = request.parameters.type as NotificationType;
      if (!(type in NOTIFICATION_RIGHTS)) return refused(INVALID, "no notification type carries that id");
      if (!receivable().includes(type)) return refused(FORBIDDEN, "the account does not hold the right this type asks");
      const enabled = field(request.body, "enabled");
      if (typeof enabled !== "boolean") return refused(INVALID, "enabled is a boolean");
      const off = turnedOff().filter((one) => one !== type);
      if (!enabled) off.push(type);
      mockState().notificationsOff[signedInId()] = off;
      return preference(type);
    }),
    route("registerPushDevice", POST, "/api/notifications/devices", (request) => {
      const token = text(request.body, "token");
      const platform = text(request.body, "platform") as Platform;
      if (!token || !PLATFORMS.includes(platform)) return refused(INVALID, "a device carries a token and a platform");
      const devices = mockState().pushDevices;
      // THE SAME TOKEN POSTED TWICE IS ONE DEVICE: the start-up refresh posts it again.
      if (!devices.some((one) => one.token === token)) devices.push({ token, platform });
      return { ok: true };
    }),
  ];
}
