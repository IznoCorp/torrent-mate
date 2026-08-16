// The i18n bootstrap. `publicDir: false` (vite.config.mjs) forbids fetching
// resource files at runtime, so `fr.json` is a STATIC import — bundled, not
// requested — which is also why `resolveJsonModule` had to be turned on
// (tsconfig.json). Imported once, for its side effect, before the shell
// mounts (`shell.tsx`'s first import): every component that calls
// `useTranslation()` after that point finds `i18next` already initialised.
import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import fr from "./fr.json";

void i18next.use(initReactI18next).init({
  lng: "fr",
  fallbackLng: "fr",
  resources: { fr: { translation: fr } },
  // React already escapes interpolated values when it renders text nodes,
  // so i18next's own escaping would double-encode them.
  interpolation: { escapeValue: false },
});

export default i18next;
