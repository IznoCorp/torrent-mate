// THE UNIT SUITE'S BROWSER SPEAKS FRENCH, whatever the machine running it speaks.
//
// Loaded before every test file (`test.setupFiles` in `vite.config.mjs`), so
// before `i18n/index.ts` reads `browserLanguage()` for its first language. The
// suite runs in Node, whose own `navigator.languages` is the HOST's locale
// (`LANG`, `LC_ALL`): left alone, a French workstation heard French and an
// English runner heard English, and the same assertions passed on one and
// failed on the other. French because the suite's words are the project's
// language's. A test that needs another browser stubs `navigator` itself
// (`vi.stubGlobal`); `vi.unstubAllGlobals()` brings back this one, not the
// host's, because it is defined here without the stub mechanism.
Object.defineProperty(globalThis, "navigator", {
  // Node's own navigator underneath, so what it answers besides the language
  // (`userAgent`, `hardwareConcurrency`, …) stays the host's.
  value: Object.create(globalThis.navigator, {
    language: { value: "fr-FR" },
    languages: { value: Object.freeze(["fr-FR"]) },
  }),
  configurable: true,
  writable: true,
});
