// What the application offers to install, to whom, and when — and what it offers once it is installed.
//
// WHAT MAKES THIS NON-VACUOUS. The decisions are read through stand-in globals the way a browser
// presents them: `display-mode: standalone`, an iPhone's user agent, a captured
// `beforeinstallprompt`, a storage that works, one that is empty and one that THROWS (a private
// window, blocked site data). Each leg drives the module as the entry does and reads what it
// answers — never a flag the module keeps for the test.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
const CHROME = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36";

type Install = typeof import("./install-state");
let install: Install;
let store: Record<string, string>;
let session: Record<string, string>;

/** Stands up the globals one browser presents. */
function browser(options: { standalone?: boolean; agent?: string; storage?: "works" | "throws" } = {}): void {
  const { standalone = false, agent = CHROME, storage = "works" } = options;
  const area = (data: Record<string, string>): Storage =>
    (storage === "throws"
      ? new Proxy({}, { get: () => () => { throw new Error("storage blocked"); } })
      : {
          getItem: (key: string) => (key in data ? data[key] : null),
          setItem: (key: string, value: string) => { data[key] = String(value); },
          removeItem: (key: string) => { delete data[key]; },
        }) as Storage;
  vi.stubGlobal("window", { matchMedia: () => ({ matches: standalone }), location: { reload: vi.fn() } });
  vi.stubGlobal("navigator", { userAgent: agent, platform: "iPhone", maxTouchPoints: 5 });
  vi.stubGlobal("localStorage", area(store));
  vi.stubGlobal("sessionStorage", area(session));
}

/** A `beforeinstallprompt` as Chrome dispatches it, with the two members a page may use. */
function promptEvent(outcome: "accepted" | "dismissed" = "accepted") {
  return {
    preventDefault: vi.fn(),
    prompt: vi.fn(),
    userChoice: Promise.resolve({ outcome }),
  } as unknown as import("./install-state").InstallPrompt & { prompt: ReturnType<typeof vi.fn> };
}

beforeEach(async () => {
  store = {};
  session = {};
  vi.resetModules();
  browser();
  install = await import("./install-state");
});

afterEach(() => vi.unstubAllGlobals());

describe("who is offered the install, and when", () => {
  it("offers the captured prompt on Android and desktop, once", () => {
    install.captureInstallEvent(promptEvent());
    expect(install.proposalFor()).toBe("android");
    install.markOffered();
    expect(install.proposalFor()).toBeNull();
  });

  it("offers the guide on iOS Safari, where nothing fires", async () => {
    browser({ agent: IPHONE });
    expect(install.proposalFor()).toBe("ios");
  });

  it("offers nothing where there is nothing to offer: no prompt, not iOS", () => {
    expect(install.proposalFor()).toBeNull();
  });

  it("offers nothing to an application already installed", () => {
    browser({ standalone: true, agent: IPHONE });
    install.captureInstallEvent(promptEvent());
    expect(install.proposalFor()).toBeNull();
  });

  it("proposes right after the first sign-in, shows once, and never again when it was shown", () => {
    install.captureInstallEvent(promptEvent());
    const show = vi.fn();
    install.proposeAfterSignIn(show);
    install.proposeAfterSignIn(show);
    expect(show).toHaveBeenCalledTimes(1);
    expect(show).toHaveBeenCalledWith("android");
    expect(store["tm-install-offered"]).toBeDefined();
  });

  it("waits for the prompt a browser fires after the sign-in, then shows it once", () => {
    const show = vi.fn();
    install.proposeAfterSignIn(show);
    expect(show).not.toHaveBeenCalled();
    install.captureInstallEvent(promptEvent());
    expect(show).toHaveBeenCalledTimes(1);
    install.captureInstallEvent(promptEvent());
    expect(show).toHaveBeenCalledTimes(1);
  });

  it("proposes nothing more once refused — the mark is the browser's, and survives a new page", async () => {
    install.captureInstallEvent(promptEvent());
    install.proposeAfterSignIn(vi.fn());
    vi.resetModules();
    install = await import("./install-state");
    install.captureInstallEvent(promptEvent());
    const show = vi.fn();
    install.proposeAfterSignIn(show);
    expect(show).not.toHaveBeenCalled();
  });

  it("proposes again when the site data was cleared", async () => {
    install.captureInstallEvent(promptEvent());
    install.proposeAfterSignIn(vi.fn());
    store = {};
    browser();
    vi.resetModules();
    install = await import("./install-state");
    install.captureInstallEvent(promptEvent());
    const show = vi.fn();
    install.proposeAfterSignIn(show);
    expect(show).toHaveBeenCalledTimes(1);
  });

  it("works with a storage that throws: it proposes, and never fails", () => {
    browser({ storage: "throws" });
    install.captureInstallEvent(promptEvent());
    const show = vi.fn();
    expect(() => install.proposeAfterSignIn(show)).not.toThrow();
    expect(show).toHaveBeenCalledTimes(1);
    expect(install.wasOffered()).toBe(false);
  });

  it("reads the sign-in mark once: the host's page leaves it, the first boot takes it", () => {
    expect(install.takeSignedIn()).toBe(false);
    session["tm-signed-in"] = "1";
    expect(install.takeSignedIn()).toBe(true);
    expect(install.takeSignedIn()).toBe(false);
  });
});

describe("what the Profil button offers", () => {
  it("is the install, on a captured prompt, while the app runs in a browser", () => {
    install.captureInstallEvent(promptEvent());
    expect(install.installFace()).toBe("install");
  });

  it("is the iOS guide on iOS Safari", () => {
    browser({ agent: IPHONE });
    expect(install.installFace()).toBe("ios");
  });

  it("is nothing where the browser offers no install", () => {
    expect(install.installFace()).toBe("none");
  });

  it("is hidden when the app already runs installed", () => {
    browser({ standalone: true });
    install.captureInstallEvent(promptEvent());
    expect(install.installFace()).toBe("none");
  });

  it("offers the update when the app is installed and a newer version waits", () => {
    browser({ standalone: true });
    install.setUpdateWaiting(() => {});
    expect(install.installFace()).toBe("update");
  });

  it("does not offer the update in a browser tab, which reloads itself", () => {
    install.setUpdateWaiting(() => {});
    expect(install.installFace()).toBe("none");
  });

  it("applies the waiting update on demand, once, and says nothing waits after", () => {
    browser({ standalone: true });
    const apply = vi.fn();
    install.setUpdateWaiting(apply);
    install.applyUpdate();
    expect(apply).toHaveBeenCalledTimes(1);
  });

  it("notifies a subscriber when the face moves", () => {
    const heard = vi.fn();
    install.subscribeInstall(heard);
    install.captureInstallEvent(promptEvent());
    expect(heard).toHaveBeenCalled();
  });

  it("fires the captured prompt on demand and reports the choice", async () => {
    const event = promptEvent("dismissed");
    install.captureInstallEvent(event);
    expect(await install.promptInstall()).toBe("dismissed");
    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(await install.promptInstall()).toBe("unavailable");
  });
});
