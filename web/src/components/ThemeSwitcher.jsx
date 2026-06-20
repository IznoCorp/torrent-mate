// Theme switcher (light / dark / system). Mirrors LangSwitcher's SegmentedControl styling so the two
// sit together in the header / drawer footer / login. Icons keep it compact; titles carry the label.
import React from "react";
import useTheme from "../useTheme.js";
import { useT } from "../i18n/index.jsx";

const { SegmentedControl } = window.KanbanMateDesignSystem_2463ad;

// Icon + accessible title (SegmentedControl renders the label node verbatim, so a titled span gives
// a native tooltip on hover and an accessible name).
const Glyph = ({ icon, label }) => (
  <span title={label} aria-label={label} role="img">
    {icon}
  </span>
);

export default function ThemeSwitcher() {
  const { mode, setMode } = useTheme();
  const { t } = useT();
  return (
    <SegmentedControl
      value={mode}
      onChange={setMode}
      options={[
        { value: "light", label: <Glyph icon="☀️" label={t("theme.light")} /> },
        { value: "dark", label: <Glyph icon="🌙" label={t("theme.dark")} /> },
        {
          value: "system",
          label: <Glyph icon="💻" label={t("theme.system")} />,
        },
      ]}
    />
  );
}
