// The Système page over a read the server refused: it says why, in the reader's language.
//
// WHAT THIS HOLDS THAT `ui/state-surfaces.test.tsx` CANNOT: the wiring. The error surface words a failure it is
// handed; only the screen can hand it its read's `error`, and dropping `failure=` there silently brings back the
// timeout sentence over a server that answered (§ 13). Same pattern as `media/media-screen-failure.test.tsx`.
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import i18next from "../../i18n";

const UNAVAILABLE = {
  status: 503, title: "The library index cannot be read.", detail: "The library index cannot be read.",
  code: "library.unavailable", params: {},
};

/** A read that was refused, as the query hooks report it. */
const refused = { isError: true, isPending: false, isFetching: false, isPlaceholderData: false, data: undefined, error: UNAVAILABLE, refetch: vi.fn() };

/** A read that answered, with nothing to show. */
const answered = { isError: false, isPending: false, isFetching: false, isPlaceholderData: false, data: undefined, error: null, refetch: vi.fn() };

// BY DEFAULT EVERY READ BELOW THE SURFACE ANSWERS REFUSED; `onlyRefused` narrows that to one address, so a test can
// refuse the LAST read of a `??` chain alone.
// THE SIX READS THE PAGE REPORTS: the others (pipeline status, locks, account) stay unread, as they are here.
const SIX_LISTS = [
  "/api/v1/system/services", "/api/v1/maintenance/schedulers", "/api/v1/maintenance/disks",
  "/api/v1/maintenance/index-health", "/api/v1/system/dependencies",
];
const ERRORS = { total: 0, outOf: 0, latest: "", what: "", where: "" };
const reads = vi.hoisted(() => ({ onlyRefused: undefined as string | undefined, answeredExcept: undefined as string | undefined, holdsData: false }));
vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: (options: { queryKey: readonly unknown[] }) => {
    const address = options.queryKey[0];
    if (reads.answeredExcept !== undefined) return address === reads.answeredExcept ? answered : refused;
    if (reads.onlyRefused !== undefined && reads.onlyRefused !== address) return answered;
    return reads.holdsData ? { ...refused, data: address === "/api/v1/system/errors" ? ERRORS : SIX_LISTS.includes(String(address)) ? [] : undefined } : refused;
  },
}));
// THE SERVER-RENDERED PASS has no snapshot to subscribe to: the version stands still.
vi.mock("../../lib/query-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/query-client")>()),
  useServerStateVersion: () => 0,
}));
// THE PHASE IS THE TEST'S: "error" is what the harness names; "ready" is what a real refused read leaves, since
// nothing but the harness ever sets the error phase.
const screen = vi.hoisted(() => ({ phase: "error" }));
vi.mock("../../lib/store-access", () => ({
  useUiState: () => ({ phase: screen.phase, scen: "" }),
  useStoreContent: () => 0,
}));

/** The visible text of an element, whitespace folded. */
function textOf(element: ReactElement): string {
  void i18next.changeLanguage("fr");
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client: new QueryClient() }, element));
  return html.replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'").replace(/\s+/g, " ");
}

// THE TWO SENTENCES, WRITTEN OUT: reading them from the catalogue would make the test agree with whatever the code says.
const REFUSAL =
  "La médiathèque est indisponible : le serveur ne peut pas la lire pour le moment. Réessayez dans un instant."; // french-ok: the 503 refusal sentence the screen must show
const TIMEOUT = "Le serveur n'a pas répondu dans le temps imparti."; // french-ok: the timeout sentence a refused read must NOT show

describe("SystemPage in its error phase", () => {
  it("says why the reads were refused, not the timeout sentence", async () => {
    const { SystemPage } = await import("./page");
    const text = textOf(createElement(SystemPage));
    expect(text).toContain(REFUSAL);
    expect(text).not.toContain(TIMEOUT);
  });

  it("names the refusal when only the LAST read of its chain (the errors) is refused", async () => {
    reads.onlyRefused = "/api/v1/system/errors";
    try {
      const { SystemPage } = await import("./page");
      const text = textOf(createElement(SystemPage));
      expect(text).toContain(REFUSAL);
      expect(text).not.toContain(TIMEOUT);
    } finally {
      reads.onlyRefused = undefined;
    }
  });
});

describe("SystemPage over real refused reads (the phase is not \"error\")", () => {
  it("says why when all six reads are refused", async () => {
    screen.phase = "ready";
    try {
      const { SystemPage } = await import("./page");
      const text = textOf(createElement(SystemPage));
      expect(text).toContain(REFUSAL);
      expect(text).not.toContain(TIMEOUT);
    } finally {
      screen.phase = "error";
    }
  });

  it("leaves the page drawn when one section's read is refused (R400: its own row says so)", async () => {
    reads.onlyRefused = "/api/v1/system/errors";
    screen.phase = "ready";
    try {
      const { SystemPage } = await import("./page");
      const text = textOf(createElement(SystemPage));
      expect(text).not.toContain(REFUSAL);
      expect(text).not.toContain(TIMEOUT);
    } finally {
      reads.onlyRefused = undefined;
      screen.phase = "error";
    }
  });
});

describe("SystemPage at the boundary of \"all six\" and over a refused REFETCH", () => {
  it("leaves the page drawn when five of the six reads are refused", async () => {
    reads.answeredExcept = "/api/v1/system/errors";
    screen.phase = "ready";
    try {
      const { SystemPage } = await import("./page");
      const text = textOf(createElement(SystemPage));
      expect(text).not.toContain(REFUSAL);
      expect(text).not.toContain(TIMEOUT);
    } finally {
      reads.answeredExcept = undefined;
      screen.phase = "error";
    }
  });

  it("keeps the data drawn when a REFETCH is refused while the cache holds it", async () => {
    reads.holdsData = true;
    screen.phase = "ready";
    try {
      const { SystemPage } = await import("./page");
      expect(textOf(createElement(SystemPage))).not.toContain(REFUSAL);
    } finally {
      reads.holdsData = false;
      screen.phase = "error";
    }
  });
});
