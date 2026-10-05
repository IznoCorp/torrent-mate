// Signing out ends the session where it lives: v1's.
//
// WHAT MAKES THIS NON-VACUOUS. The design host's door is v1's session, and the
// host no longer has a `/logout` of its own: a sign-out that still asked for it
// would answer on screen and leave the real session open — the next reload would
// walk straight back in. The act is driven as a person drives it, over a
// recording `fetch`, and reads what left: v1's `POST /api/v1/auth/logout`, and
// nothing at `/logout`. And the sign-in page it lands on speaks the browser's
// language, not the last account's (before sign-in, the browser's), and keeps it
// while the frame behind the gate goes on reading the same account — or a late
// answer of it arrives. A session LOST under the interface (a read answered 401)
// lands the gate in that language too.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// THE OUTBOX'S STORAGE IS NOT WHAT IS READ HERE: forgetting it needs a database
// the stand-in document does not hold.
// THE FRAME IS NOT WHAT IS READ HERE: the gate the entry installs lands pages the
// stand-in document does not hold, and loading the frame loads every surface.
vi.mock("./frame-verbs", () => ({ landSignedIn: () => {} }));
vi.mock("./navigation", () => ({ entryPageFor: () => "" }));
vi.mock("./outbox", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./outbox")>()),
  forgetOutbox: async () => {},
}));

let sent: { path: string; method: string }[];

beforeEach(async () => {
  sent = [];
  // THE PANEL DOOR a sign-out closes first, filled the way the frame fills it.
  const doors = await import("../lib/shell-doors");
  doors.fillPanelDoor({ close: () => {} } as never);
  vi.stubGlobal("document", { querySelector: () => null });
  vi.stubGlobal("window", { addEventListener: () => {}, matchMedia: () => ({ matches: false }) });
  vi.stubGlobal("location", { pathname: "/media", search: "" });
  vi.stubGlobal("fetch", async (path: string, options: RequestInit = {}) => {
    sent.push({ path, method: options.method ?? "GET" });
    return new Response("{}", { status: 200 });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("signOut", () => {
  it("asks v1 to end the session, and the host for no route of its own", async () => {
    const { signOut } = await import("./entry");
    await signOut();
    expect(sent).toEqual([{ path: "/api/v1/auth/logout", method: "POST" }]);
  });

  it("gives the sign-in page the browser's language, and a surface reading the account again does not take it back", async () => {
    vi.stubGlobal("navigator", { languages: ["en-US"] });
    const { QueryClient, QueryObserver } = await import("@tanstack/react-query");
    const { accountQuery, followAccountLanguage } = await import("../lib/account");
    const { default: i18next } = await import("../i18n");
    const client = new QueryClient();
    followAccountLanguage(client);
    client.setQueryData(accountQuery.queryKey, { language: "fr" });
    expect(i18next.language).toBe("fr");

    const { signOut } = await import("./entry");
    await signOut();
    expect(i18next.language).toBe("en");

    // A SURFACE MOUNTING behind the gate over the same, unchanged answer.
    new QueryObserver(client, { queryKey: accountQuery.queryKey, enabled: false }).subscribe(() => {});
    expect(i18next.language).toBe("en");
  });

  it("keeps the browser's language when a late answer of the account arrives after it", async () => {
    vi.stubGlobal("navigator", { languages: ["en-US"] });
    const { QueryClient } = await import("@tanstack/react-query");
    const { accountQuery, followAccountLanguage } = await import("../lib/account");
    const { default: i18next } = await import("../i18n");
    const client = new QueryClient();
    followAccountLanguage(client);
    client.setQueryData(accountQuery.queryKey, { id: 1, language: "fr" });

    const { signOut } = await import("./entry");
    await signOut();
    // A `/auth/me` asked before the sign-out, answered after it — a DIFFERENT
    // object, so the follower sees the entry move.
    client.setQueryData(accountQuery.queryKey, { id: 1, language: "fr", name: "late" });
    expect(i18next.language).toBe("en");
  });

  it("follows the next account once its sign-in lands", async () => {
    vi.stubGlobal("navigator", { languages: ["en-US"] });
    const { QueryClient } = await import("@tanstack/react-query");
    const { accountQuery, followAccountLanguage, followTheSignedIn } = await import("../lib/account");
    const { default: i18next } = await import("../i18n");
    const client = new QueryClient();
    followAccountLanguage(client);
    const { signOut } = await import("./entry");
    await signOut();
    expect(i18next.language).toBe("en");

    followTheSignedIn();
    client.setQueryData(accountQuery.queryKey, { id: 2, language: "fr" });
    expect(i18next.language).toBe("fr");
  });

  it("goes on to the sign-in screen when v1 does not answer", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("network down");
    });
    const { signOut } = await import("./entry");
    await expect(signOut()).resolves.toBeUndefined();
  });
});

describe("a session lost under the interface", () => {
  it("lands the gate in the browser's language, and a late answer of the account does not take it back", async () => {
    vi.stubGlobal("navigator", { languages: ["en-US"] });
    const { QueryClient } = await import("@tanstack/react-query");
    const { accountQuery, followAccountLanguage } = await import("../lib/account");
    const { read } = await import("../lib/query-client");
    const { default: i18next } = await import("../i18n");
    const client = new QueryClient();
    followAccountLanguage(client);
    client.setQueryData(accountQuery.queryKey, { id: 1, language: "fr" });
    expect(i18next.language).toBe("fr");

    // THE ENTRY INSTALLS WHAT LANDING IS, as the frame does; then a read answers
    // 401 — an expiry, an Admin's cut, a sign-out in another tab.
    const { installEntry } = await import("./entry");
    installEntry();
    vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ code: "auth.required" }), { status: 401 }));
    await read("/api/v1/library").catch(() => undefined);
    expect(i18next.language).toBe("en");

    client.setQueryData(accountQuery.queryKey, { id: 1, language: "fr", name: "late" });
    expect(i18next.language).toBe("en");
  });
});
