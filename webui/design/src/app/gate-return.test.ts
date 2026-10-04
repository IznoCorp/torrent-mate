// A sign-in through the in-app gate returns to the place the person was.
//
// WHAT MAKES THIS NON-VACUOUS. The gate used to land every sign-in on the account's entry page, so a session
// lost on `/media?cat=films` came back on Acquisition — the deep link dropped at the one moment the person
// asked for nothing but to go on. Each leg keeps a place the way the entry does when the gate comes up, signs
// in through the password door over a recording `fetch`, and reads where the frame was told to land: the
// place kept, or the entry page when the place is absent, foreign, or one the account does not open.
import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/** Every landing the gate asked the frame for. */
const landed: { page: string; dials: Record<string, string> | undefined }[] = [];

// THE FRAME IS NOT WHAT IS READ HERE: the landing is recorded, not drawn.
vi.mock("./frame-verbs", () => ({
  landSignedIn: (page: string, dials?: Record<string, string>) => landed.push({ page, dials }),
}));
// THE OUTBOX'S STORAGE is a database the stand-in document does not hold.
vi.mock("./outbox", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./outbox")>()),
  forgetOutbox: async () => {},
}));
// THE NAVIGATION TABLE loads every surface; the stand-in opens every page but `accounts`.
vi.mock("./navigation", () => ({
  entryPageFor: () => "acq",
  rowFor: (id: string) => ({ id }),
  opensFor: (row: { id: string }) => row.id !== "accounts",
}));

/** One element of the stand-in document. */
type FakeElement = {
  dataset: Record<string, string>;
  hidden: boolean;
  listeners: Record<string, (event: unknown) => void>;
  [key: string]: unknown;
};

/**
 * An element the gate can fill and listen on.
 *
 * @returns The element.
 */
function element(): FakeElement {
  const made: FakeElement = {
    dataset: {},
    hidden: false,
    listeners: {},
    addEventListener: (type: string, listener: (event: unknown) => void) => {
      made.listeners[type] = listener;
    },
  };
  return made;
}

let form: FakeElement;

/** Waits until every promise the gate chained has run. */
async function settle(): Promise<void> {
  for (let turn = 0; turn < 20; turn += 1) await new Promise((done) => setTimeout(done, 0));
}

/**
 * Signs in through the password door with v1 accepting, after keeping a place.
 *
 * @param place The address the gate came up over, or undefined for none.
 * @returns Where the frame was told to land.
 */
async function signInFrom(place: string | undefined): Promise<(typeof landed)[number] | undefined> {
  const { installSharedQueryClient } = await import("../lib/query-client");
  installSharedQueryClient(new QueryClient());
  const { installGate, keepPlace } = await import("./gate");
  installGate(() => {});
  if (place !== undefined) keepPlace(place);
  form.listeners.submit({ preventDefault: () => {}, currentTarget: form });
  await settle();
  return landed.at(-1);
}

beforeEach(() => {
  vi.resetModules();
  landed.length = 0;
  form = element();
  vi.stubGlobal("document", {
    createElement: element,
    querySelector: (selector: string) => (selector === "#loginform" ? form : null),
  });
  vi.stubGlobal("FormData", class {
    get(name: string): string {
      return name === "username" ? "owner@example.invalid" : "a password";
    }
  });
  vi.stubGlobal("window", { addEventListener: () => {}, removeEventListener: () => {} });
  vi.stubGlobal("fetch", async () =>
    new Response(JSON.stringify({ id: "1", forbiddenWrites: [], role: { kind: "admin", rights: [] } }), {
      status: 200,
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the gate's landing after a sign-in", () => {
  it("returns to the page and the dials of the place kept", async () => {
    expect(await signInFrom("/media?cat=films&mode=list")).toEqual({
      page: "lib",
      dials: { libCat: "films", libMode: "list" },
    });
  });

  it("lands on the entry page when no place was kept", async () => {
    expect((await signInFrom(undefined))?.page).toBe("acq");
  });

  it.each(["//elsewhere.invalid/media", "https://elsewhere.invalid/media", "/\\elsewhere.invalid", "media"])(
    "lands on the entry page for a place that is not a same-origin path (%s)",
    async (place) => {
      expect((await signInFrom(place))?.page).toBe("acq");
    },
  );

  it("lands on the entry page for a page the account does not open", async () => {
    expect((await signInFrom("/accounts"))?.page).toBe("acq");
  });

  it("lands on the entry page for the sign-in screen itself and for an address nobody serves", async () => {
    expect((await signInFrom("/login"))?.page).toBe("acq");
    expect((await signInFrom("/nowhere"))?.page).toBe("acq");
  });

  it("returns to a place only once", async () => {
    await signInFrom("/media");
    const { installGate } = await import("./gate");
    installGate(() => {});
    form.listeners.submit({ preventDefault: () => {}, currentTarget: form });
    await settle();
    expect(landed.map((one) => one.page)).toEqual(["lib", "acq"]);
  });

  it("keeps the place the entry's gate comes up over, and only when a person is there", async () => {
    vi.stubGlobal("location", { pathname: "/media", search: "?cat=films" });
    const { showSignIn } = await import("./entry");
    showSignIn(false);
    expect(await signInFrom(undefined)).toEqual({ page: "lib", dials: { libCat: "films" } });
  });

  it("keeps no place for a gate the harness drives", async () => {
    vi.stubGlobal("location", { pathname: "/media", search: "" });
    const { showSignIn } = await import("./entry");
    showSignIn(false, true);
    expect((await signInFrom(undefined))?.page).toBe("acq");
  });

  it("forgets the place on a sign-out: the next person starts at their own entry", async () => {
    vi.stubGlobal("location", { pathname: "/media", search: "" });
    const doors = await import("../lib/shell-doors");
    doors.fillPanelDoor({ close: () => {} } as never);
    const { signOut } = await import("./entry");
    await signOut();
    expect((await signInFrom(undefined))?.page).toBe("acq");
  });
});
