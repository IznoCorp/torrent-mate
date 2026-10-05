// Which language the interface speaks (the operator: FG-1 B, OPEN-2 B) — the browser's before
// sign-in, then the signed-in account's, at once and without a reload.
//
// WHAT MAKES THIS NON-VACUOUS. The browser's tags are read in order and only French or English
// is taken; the account's language is read off the SAME cache entry every surface reads, and
// emptying that entry — a sign-out — gives the browser's back. Every leg reads `i18next.language`
// and a word the catalogue really holds, not the function's return alone.
import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import i18next, { browserLanguage, speak } from ".";
import { accountQuery, followAccountLanguage } from "../lib/account";
import EN from "./en.json";
import FR from "./fr.json";

describe("the browser's language", () => {
  it.each([
    [["fr-FR", "en-US"], "fr"],
    [["en-GB", "fr"], "en"],
    [["de-DE", "fr-CH"], "fr"],
    [["de-DE", "es"], "en"],
    [[], "en"],
  ] as const)("reads %j as %s — the first tag the interface speaks, else English", (tags, language) => {
    expect(browserLanguage(tags)).toBe(language);
  });
});

describe("the account's language", () => {
  let client: QueryClient;
  beforeEach(() => {
    client = new QueryClient();
    followAccountLanguage(client);
    speak("fr");
  });

  it("switches the whole catalogue when the account's entry says English", () => {
    client.setQueryData(accountQuery.queryKey, { language: "en" });
    expect(i18next.language).toBe("en");
    expect(i18next.t("screens.gate.submit")).toBe(EN.screens.gate.submit);
  });

  it("switches back when the account chooses French", () => {
    client.setQueryData(accountQuery.queryKey, { language: "en" });
    client.setQueryData(accountQuery.queryKey, { language: "fr" });
    expect(i18next.t("screens.gate.submit")).toBe(FR.screens.gate.submit);
  });

  it("gives the browser's language back once nobody is signed in", () => {
    client.setQueryData(accountQuery.queryKey, { language: "fr" });
    client.clear();
    expect(i18next.language).toBe(browserLanguage());
  });

  it("speaks English for a language it does not speak", () => {
    speak("de");
    expect(i18next.language).toBe("en");
  });
});
