// What the device's line says, from what the device can do.
import { describe, expect, it } from "vitest";
import { deviceSupport, platformOf } from "./push-device";
import type { PushEnvironment } from "../../lib/push-registration";

const ANDROID: PushEnvironment = {
  userAgent: "Mozilla/5.0 (Linux; Android 15; Pixel 9) Mobile",
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
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
  platform: "iPhone",
  standalone: false,
};

describe("deviceSupport", () => {
  it("says the permission where push is available", () => {
    expect(deviceSupport({ ...ANDROID, permission: "granted" })).toBe("granted");
    expect(deviceSupport(ANDROID)).toBe("unasked");
    expect(deviceSupport({ ...ANDROID, permission: "denied" })).toBe("denied");
  });

  it("tells an iPhone tab to install before telling it anything is unsupported", () => {
    expect(deviceSupport({ ...IPHONE_TAB, hasPushManager: false })).toBe("needs-install");
  });

  it("says unsupported where an API is missing", () => {
    expect(deviceSupport({ ...ANDROID, hasPushManager: false })).toBe("unsupported");
  });
});

describe("platformOf", () => {
  it("names the device's family", () => {
    expect(platformOf(ANDROID)).toBe("android");
    expect(platformOf(IPHONE_TAB)).toBe("ios");
    expect(platformOf({ ...ANDROID, userAgent: "Mozilla/5.0 (Macintosh)", platform: "MacIntel", maxTouchPoints: 5 }))
      .toBe("ios");
    expect(platformOf({ ...ANDROID, userAgent: "Mozilla/5.0 (X11; Linux x86_64)", maxTouchPoints: 0 })).toBe("desktop");
  });
});
