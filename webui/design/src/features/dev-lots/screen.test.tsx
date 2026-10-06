// The lots progress screen draws what the read answered: the lots with their states and links, or the notice.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import i18next from "../../i18n";
import { lotsKey, type LotsDocument } from "./queries";
import { DevLotsScreen } from "./screen";
import { SAMPLE_LOTS } from "../../harness/states/dev-lots-sample";

/**
 * Renders the screen over a read that already answered.
 *
 * @param document What the read answered.
 * @returns The markup.
 */
function drawn(document: LotsDocument): string {
  void i18next.changeLanguage("en");
  const client = new QueryClient();
  client.setQueryData(lotsKey, document);
  return renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(DevLotsScreen)));
}

describe("DevLotsScreen", () => {
  it("draws one card per lot and one row per phase, each with its state", () => {
    const html = drawn(SAMPLE_LOTS);
    expect(html.match(/data-part="lots\/lot"/g)).toHaveLength(2);
    expect(html.match(/data-part="lots\/phase"/g)).toHaveLength(7);
    for (const state of ["planned", "in-progress", "pr-open", "merged"]) {
      expect(html).toContain(`data-state="${state}"`);
    }
    expect(html).toContain("In progress");
    expect(html).toContain("in review");
  });

  it("links every pull request to its page, and says what blocks", () => {
    const html = drawn(SAMPLE_LOTS);
    expect(html).toContain('href="https://github.com/example/repository/pull/104"');
    expect(html.match(/data-part="lots\/pr"/g)).toHaveLength(4);
    expect(html).toContain("Blocked: Owed by hand");
  });

  it("says nothing is published when the host serves no progress", () => {
    const html = drawn({ available: false });
    expect(html).toContain('data-part="lots/unavailable"');
    expect(html).not.toContain('data-part="lots/lot"');
  });
});
