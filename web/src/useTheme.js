// Theme controller (light / dark / system, default system). The design system ships a full dark
// palette under `[data-theme="dark"]` (ds/tokens/colors.css), so theming = setting that attribute
// on <html>. "system" follows the OS via prefers-color-scheme and reacts live to OS changes.
// The pre-paint apply lives inline in index.html (no flash); this hook keeps it in sync at runtime.
import React from "react";

const KEY = "bridge.theme";
export const THEME_MODES = ["light", "dark", "system"];

const prefersDark = () =>
  typeof window !== "undefined" &&
  window.matchMedia &&
  window.matchMedia("(prefers-color-scheme: dark)").matches;

export function getStoredMode() {
  try {
    const m = localStorage.getItem(KEY);
    return THEME_MODES.includes(m) ? m : "system";
  } catch (_) {
    return "system";
  }
}

// The concrete theme ("light" | "dark") a mode resolves to right now.
export function resolveTheme(mode) {
  if (mode === "system") return prefersDark() ? "dark" : "light";
  return mode;
}

// Apply a mode to <html> (data-theme drives the CSS; color-scheme styles native controls/scrollbars).
export function applyTheme(mode) {
  const resolved = resolveTheme(mode);
  const el = document.documentElement;
  el.setAttribute("data-theme", resolved);
  el.style.colorScheme = resolved;
  return resolved;
}

export default function useTheme() {
  const [mode, setModeState] = React.useState(getStoredMode);

  const setMode = (m) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch (_) {
      /* non-fatal (private mode) */
    }
    applyTheme(m);
  };

  // Keep <html> in sync if the stored mode is changed elsewhere / on mount.
  React.useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  // In "system" mode, follow live OS theme changes.
  React.useEffect(() => {
    if (mode !== "system") return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [mode]);

  return { mode, setMode, resolved: resolveTheme(mode) };
}
