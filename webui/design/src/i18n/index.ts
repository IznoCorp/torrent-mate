// The i18n bootstrap. `publicDir: false` (vite.config.mjs) forbids fetching
// resource files at runtime, so `fr.json` and `en.json` are STATIC imports —
// bundled, not requested — which is also why `resolveJsonModule` had to be turned on
// (tsconfig.json). Imported once, for its side effect, before the shell
// mounts (`shell.tsx`'s first import): every component that calls
// `useTranslation()` after that point finds `i18next` already initialised.
//
// WHICH LANGUAGE (the operator, 2026-10-03, FG-1 B; 2026-10-04, OPEN-2 B): the
// SIGNED-IN ACCOUNT's — an account field, chosen in Profil, the same on every
// device (`lib/account.ts` follows it). Before anyone is signed in, the
// browser's, when it is French or English; English otherwise.
import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import fr from "./fr.json";

/** A language the interface speaks — the contract's `Language`. */
export type Language = "fr" | "en";

/** The languages the interface speaks, in no order. */
export const LANGUAGES: readonly Language[] = ["fr", "en"];

/** The language when nothing names one (OPEN-2 B). */
export const DEFAULT_LANGUAGE: Language = "en";

/**
 * The browser's language, as the interface speaks it.
 *
 * THE FIRST TAG THE INTERFACE SPEAKS, in the browser's order of preference —
 * the same reading the design host gives `Accept-Language`, so the sign-in
 * page it serves and the prototype's own agree.
 *
 * @param tags The browser's languages, most preferred first (`navigator.languages`).
 * @returns The first one whose primary subtag is French or English; English when none is.
 */
export function browserLanguage(
  tags: readonly string[] = globalThis.navigator?.languages ?? [],
): Language {
  for (const tag of tags) {
    const primary = tag.split("-")[0]?.toLowerCase();
    if (LANGUAGES.includes(primary as Language)) return primary as Language;
  }
  return DEFAULT_LANGUAGE;
}

/**
 * Words every element of the document that names its words by key.
 *
 * THE MARKUP THE JAVASCRIPT DOES NOT RENDER — the sign-in screen in
 * `index.html`, which the design host extracts and serves as its own page —
 * carries its French as the fallback a page without script shows, and the key
 * of its words beside it: `data-words` for the text, `data-words-label` for the
 * accessible name. React redraws its own words when the language changes; these
 * have to be told.
 *
 * @param root Where to look; the whole document by default.
 */
export function wordMarkup(
  root: ParentNode | undefined = globalThis.document,
): void {
  // A stand-in document (the unit suite's) may hold no query at all.
  if (typeof root?.querySelectorAll !== "function") return;
  for (const element of root.querySelectorAll<HTMLElement>("[data-words]")) {
    element.textContent = i18next.t(element.dataset.words!);
  }
  for (const element of root.querySelectorAll<HTMLElement>(
    "[data-words-label]",
  )) {
    element.setAttribute("aria-label", i18next.t(element.dataset.wordsLabel!));
  }
}

/**
 * Speaks one language from now on, everywhere at once and without a reload.
 *
 * @param language The language; anything the interface does not speak is English.
 */
export function speak(language: string | undefined): void {
  const chosen = LANGUAGES.includes(language as Language)
    ? (language as Language)
    : DEFAULT_LANGUAGE;
  if (i18next.language !== chosen) void i18next.changeLanguage(chosen);
}

// THE DOCUMENT FOLLOWS: its `lang` — what a screen reader pronounces and the
// browser hyphenates by — and the words of the markup no component draws.
i18next.on("languageChanged", (language) => {
  const root = globalThis.document?.documentElement;
  if (root) root.lang = language;
  wordMarkup();
});

void i18next.use(initReactI18next).init({
  lng: browserLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: [...LANGUAGES],
  resources: { fr: { translation: fr }, en: { translation: en } },
  // React already escapes interpolated values when it renders text nodes,
  // so i18next's own escaping would double-encode them.
  interpolation: { escapeValue: false },
});

export default i18next;
