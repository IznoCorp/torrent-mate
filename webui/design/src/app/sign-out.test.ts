// Signing out ends the session where it lives: v1's.
//
// WHAT MAKES THIS NON-VACUOUS. The design host's door is v1's session, and the
// host no longer has a `/logout` of its own: a sign-out that still asked for it
// would answer on screen and leave the real session open — the next reload would
// walk straight back in. The act is driven as a person drives it, over a
// recording `fetch`, and reads what left: v1's `POST /api/v1/auth/logout`, and
// nothing at `/logout`.
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

  it("goes on to the sign-in screen when v1 does not answer", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("network down");
    });
    const { signOut } = await import("./entry");
    await expect(signOut()).resolves.toBeUndefined();
  });
});
