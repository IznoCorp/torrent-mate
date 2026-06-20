import React from "react";
import { createRoot } from "react-dom/client";
import "./ds/react-global.js"; // sets window.React — MUST precede the bundle import
import "./ds/_ds_bundle.js"; // exposes window.KanbanMateDesignSystem_2463ad (side effect)
import "./ds/bridge.css"; // bridge placeholder + diff-row classes
import App from "./App.jsx";
import { I18nProvider } from "./i18n/index.jsx";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </React.StrictMode>,
);
