// The device side's registration (fcm-push DESIGN § 3.6), without a browser: the environment
// and the SDK are injected.
//
// WHAT MAKES THIS NON-VACUOUS. iOS in a Safari tab defines no push API at all, so a detection
// that tested the APIs first would call an iPhone « unsupported » forever — the iPhone case is
// asserted with the APIs ABSENT. The registration is asserted to reach the SDK with the
// application's OWN registration object (identity, not shape), and the permission request is
// asserted to happen before anything is awaited.
import { describe, expect, it, vi } from "vitest";
import {
  type FcmWebConfig,
  type PushDeps,
  type PushEnvironment,
  pushSupport,
  refreshPush,
  registerPush,
  unregisterPush,
} from "./push-registration";

const CONFIG: FcmWebConfig = {
  firebase: { apiKey: "k", projectId: "p", messagingSenderId: "1", appId: "a" },
  vapidKey: "vapid-public",
};

const ANDROID: PushEnvironment = {
  userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/129",
  platform: "Linux armv8l",
  maxTouchPoints: 5,
  standalone: true,
  hasNotification: true,
  hasPushManager: true,
  hasServiceWorker: true,
  permission: "default",
};
const IPHONE_TAB: PushEnvironment = {
  ...ANDROID,
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Safari/604.1",
  platform: "iPhone",
  standalone: false,
  hasNotification: false,
  hasPushManager: false,
};

describe("pushSupport", () => {
  it("says an iPhone in a Safari tab must be installed first, though it has no push API", () => {
    expect(pushSupport(IPHONE_TAB)).toEqual({ kind: "needs-install" });
  });

  it("says an iPad (a Mac with a touch screen) must be installed first", () => {
    expect(pushSupport({ ...IPHONE_TAB, userAgent: "Mozilla/5.0 (Macintosh)", platform: "MacIntel" }))
      .toEqual({ kind: "needs-install" });
  });

  it("offers push on the installed iPhone app", () => {
    expect(pushSupport({ ...IPHONE_TAB, standalone: true, hasNotification: true, hasPushManager: true }))
      .toEqual({ kind: "available", permission: "default" });
  });

  it.each(["hasNotification", "hasPushManager", "hasServiceWorker"] as const)(
    "says unsupported without %s",
    (missing) => {
      expect(pushSupport({ ...ANDROID, [missing]: false })).toEqual({ kind: "unsupported" });
    },
  );

  it.each(["default", "granted", "denied"] as const)("reports the permission %s", (permission) => {
    expect(pushSupport({ ...ANDROID, permission })).toEqual({ kind: "available", permission });
  });

  it("does not ask a desktop Mac without touch to install", () => {
    const mac = { ...ANDROID, userAgent: "Mozilla/5.0 (Macintosh)", platform: "MacIntel", maxTouchPoints: 0 };
    expect(pushSupport({ ...mac, standalone: false }).kind).toBe("available");
  });
});

// The push subscription models what the SDK does to it: `getToken` subscribes, `deleteToken`
// unsubscribes. It is what tells a device turned on from one turned off, whatever the permission reads.
function deps(
  permission: NotificationPermission,
  environment: PushEnvironment = ANDROID,
  subscribed = permission === "granted",
) {
  const state = { subscription: subscribed ? ({ endpoint: "https://push.example/1" } as PushSubscription) : null };
  const registration = {
    scope: "/",
    pushManager: { getSubscription: vi.fn(async () => state.subscription) },
  } as unknown as ServiceWorkerRegistration;
  const order: string[] = [];
  const sdk = {
    token: vi.fn(async (_config: FcmWebConfig, _registration: ServiceWorkerRegistration) => {
      order.push("token");
      state.subscription = { endpoint: "https://push.example/1" } as PushSubscription;
      return "fcm-token-1";
    }),
    forget: vi.fn(async () => {
      order.push("forget");
      state.subscription = null;
    }),
  };
  const value: PushDeps = {
    requestPermission: vi.fn(() => { order.push("ask"); return Promise.resolve(permission); }),
    registration: vi.fn(() => { order.push("registration"); return Promise.resolve(registration); }),
    sdk,
    permission: () => permission,
    environment: () => environment,
  };
  return { value, registration, sdk, order };
}

describe("registerPush", () => {
  it("asks first, then hands the token obtained through the application's own registration", async () => {
    const d = deps("granted");
    const submit = vi.fn(async (_token: string) => undefined);
    await expect(registerPush(CONFIG, submit, d.value)).resolves.toBe("on");
    expect(d.order[0]).toBe("ask");
    expect(d.sdk.token).toHaveBeenCalledWith(CONFIG, d.registration);
    expect(d.sdk.token.mock.calls[0]![1]).toBe(d.registration);
    expect(submit).toHaveBeenCalledWith("fcm-token-1");
  });

  it("asks synchronously, inside the caller's gesture", () => {
    const d = deps("granted");
    void registerPush(CONFIG, async () => undefined, d.value);
    expect(d.value.requestPermission).toHaveBeenCalledTimes(1);
  });

  it.each(["denied", "default"] as const)("stops at a %s permission, nothing obtained or sent", async (answer) => {
    const d = deps(answer);
    const submit = vi.fn(async () => undefined);
    await expect(registerPush(CONFIG, submit, d.value)).resolves.toBe("denied");
    expect(d.sdk.token).not.toHaveBeenCalled();
    expect(submit).not.toHaveBeenCalled();
  });
});

describe("refreshPush", () => {
  it("re-sends the token at a start when granted, without asking", async () => {
    const d = deps("granted");
    const submit = vi.fn(async () => undefined);
    await refreshPush(CONFIG, submit, d.value);
    expect(d.value.requestPermission).not.toHaveBeenCalled();
    expect(submit).toHaveBeenCalledWith("fcm-token-1");
  });

  it("re-sends the token when iOS reads the permission as default but the device is subscribed (#8269)", async () => {
    const d = deps("default", ANDROID, true);
    const submit = vi.fn(async () => undefined);
    await refreshPush(CONFIG, submit, d.value);
    expect(d.value.requestPermission).not.toHaveBeenCalled();
    expect(submit).toHaveBeenCalledWith("fcm-token-1");
  });

  it("submits nothing once the device was turned off, though the permission still reads granted", async () => {
    const d = deps("granted");
    await unregisterPush(CONFIG, async () => undefined, d.value);
    d.sdk.token.mockClear();
    const submit = vi.fn(async () => undefined);
    await refreshPush(CONFIG, submit, d.value);
    expect(submit).not.toHaveBeenCalled();
    expect(d.sdk.token).not.toHaveBeenCalled();
  });

  it("does nothing on a device never subscribed, nor on an iPhone tab", async () => {
    for (const d of [deps("default"), deps("granted", ANDROID, false), deps("granted", IPHONE_TAB)]) {
      const submit = vi.fn(async () => undefined);
      await refreshPush(CONFIG, submit, d.value);
      expect(submit).not.toHaveBeenCalled();
      expect(d.sdk.token).not.toHaveBeenCalled();
    }
  });
});

describe("unregisterPush", () => {
  it("has the server forget the token before the SDK deletes it", async () => {
    const d = deps("granted");
    const revoke = vi.fn(async (_token: string) => { d.order.push("revoke"); });
    await unregisterPush(CONFIG, revoke, d.value);
    expect(revoke).toHaveBeenCalledWith("fcm-token-1");
    expect(d.order.slice(-3)).toEqual(["token", "revoke", "forget"]);
  });
});

describe("firebaseSdk.forget", () => {
  it("deletes the token through the application's registration, never firebase's default worker", async () => {
    vi.resetModules();
    const sdkState: { swRegistration?: ServiceWorkerRegistration } = {};
    const registerDefaultWorker = vi.fn();
    vi.doMock("firebase/app", () => ({
      getApps: () => [],
      initializeApp: (_options: unknown, name: string) => ({ name }),
    }));
    // What the pinned SDK does: `getToken` binds the registration it is given; `deleteToken`
    // registers `firebase-messaging-sw.js` when no registration is bound yet.
    vi.doMock("firebase/messaging", () => ({
      getMessaging: () => sdkState,
      getToken: vi.fn(async (_m: unknown, options: { serviceWorkerRegistration: ServiceWorkerRegistration }) => {
        sdkState.swRegistration = options.serviceWorkerRegistration;
        return "fcm-token-1";
      }),
      deleteToken: vi.fn(async () => {
        if (!sdkState.swRegistration) registerDefaultWorker();
        return true;
      }),
    }));
    const { firebaseSdk } = await import("./push-registration");
    const registration = { scope: "/" } as ServiceWorkerRegistration;
    await firebaseSdk.forget(CONFIG, registration);
    expect(registerDefaultWorker).not.toHaveBeenCalled();
    expect(sdkState.swRegistration).toBe(registration);
    vi.doUnmock("firebase/app");
    vi.doUnmock("firebase/messaging");
  });
});
