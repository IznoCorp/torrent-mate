// Minimal i18n for bridge (DESIGN §13 operator feedback). Translations live in en.yaml / fr.yaml
// (imported as objects via the vite yaml plugin). English is the default and the fallback: a key
// missing from the active language falls back to English, then to the key itself. The chosen
// language is persisted in localStorage ("bridge.lang"). `t("a.b.c", {n: 3})` does a dotted lookup
// and interpolates {placeholders}.
import React from "react";
import en from "./en.yaml";
import fr from "./fr.yaml";

const BUNDLES = { en, fr };
export const LANGUAGES = [
  { code: "en", label: "EN" },
  { code: "fr", label: "FR" },
];
const STORAGE_KEY = "bridge.lang";

function lookup(bundle, key) {
  return key
    .split(".")
    .reduce((node, part) => (node == null ? undefined : node[part]), bundle);
}

function interpolate(str, vars) {
  // Only an OBJECT is a valid vars map. Guarding the type avoids `k in vars` throwing a TypeError
  // when a caller accidentally passes a string here (e.g. a fallback) — which blanked the whole app.
  if (!vars || typeof vars !== "object") return str;
  return str.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
}

const I18nContext = React.createContext({
  lang: "en",
  setLang: () => {},
  t: (k) => k,
});

export function I18nProvider({ children }) {
  const [lang, setLangState] = React.useState(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && BUNDLES[saved]) return saved;
    } catch (_) {
      /* localStorage unavailable — fall through to default */
    }
    return "en";
  });

  const setLang = React.useCallback((next) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch (_) {
      /* ignore persistence failure */
    }
  }, []);

  const t = React.useCallback(
    (key, fallbackOrVars, maybeVars) => {
      const hit = lookup(BUNDLES[lang], key);
      const enHit = hit !== undefined ? hit : lookup(BUNDLES.en, key);
      // Forms supported: t(key), t(key, vars), t(key, fallback), t(key, fallback, vars). A STRING
      // 2nd arg is an English fallback (used only when the key is absent from BOTH bundles); an
      // OBJECT 2nd arg is the interpolation vars. The whole UI uses inline fallbacks, so this must
      // not treat the fallback as vars (which crashed on any translation containing {placeholder}).
      const fallback =
        typeof fallbackOrVars === "string" ? fallbackOrVars : undefined;
      const vars =
        typeof fallbackOrVars === "string" ? maybeVars : fallbackOrVars;
      const str =
        enHit !== undefined ? enHit : fallback !== undefined ? fallback : key;
      return interpolate(str, vars);
    },
    [lang],
  );

  const value = React.useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useT() {
  return React.useContext(I18nContext);
}

// Language switcher (SegmentedControl). Placed in the shell header. Each segment carries a themed
// DS Tooltip naming the language it selects, so the terse "EN"/"FR" codes get a legible hint on
// hover/tap. SegmentedControl renders the label node verbatim, so the Tooltip wraps the code text.
export function LangSwitcher() {
  const { lang, setLang, t } = useT();
  const { SegmentedControl, Tooltip } = window.KanbanMateDesignSystem_2463ad;
  return (
    <SegmentedControl
      options={LANGUAGES.map((l) => ({
        value: l.code,
        label: (
          <Tooltip label={t(`lang.${l.code}`)}>
            <span>{l.label}</span>
          </Tooltip>
        ),
      }))}
      value={lang}
      onChange={setLang}
    />
  );
}
