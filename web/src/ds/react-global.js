// The design-system bundle (_ds_bundle.js) is a pre-compiled IIFE that references
// a FREE global `React` (React.createElement / React.useState — 252 call sites, no
// import). In the kit's HTML demo React was loaded as a UMD global before the bundle.
// Under Vite/ESM there is no implicit global, so we expose it here. This module MUST
// be imported BEFORE ./_ds_bundle.js so the global exists when the IIFE evaluates
// (ES modules evaluate dependencies in import order, depth-first).
import React from "react";

window.React = React;
