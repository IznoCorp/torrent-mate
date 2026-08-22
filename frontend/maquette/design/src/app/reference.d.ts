// The engine's published reference object, typed once as the intersection of
// every slice that reads it.
//
// `window.__referentiel` is ONE runtime object, so it has ONE declaration —
// but what it publishes is not one subject, and while a single 340-line type
// held all hundred and eight members, seventeen of twenty-five modules
// depended on all of them to read two. Each subject declares its own slice
// where it lives; this file only says that the global is all of them at once.
//
// THE IMPORTS BELOW ARE TYPE-ONLY, AND THAT IS WHAT MAKES THIS LEGAL. `app/`
// composes features — the router already imports every page — while `ui/` and
// `lib/` never may. A type-only edge creates no runtime dependency at all, so
// nothing here reaches a feature when the application runs, and a reader gets
// its slice's type from an ambient declaration without importing anything.
//
// A member no subject claims has nowhere to be written down. Ten of the
// original hundred and eight were in exactly that position — read by the
// engine alone, never by a component — and they are not here. They are not
// lost: the engine declares and publishes them, and `legacy.js` is what a
// later lot reads to build the mock layer, never this file.
import type { EngineDrawing } from "../lib/engine-drawing";
import type { EngineQueue } from "../lib/engine-queue";
import type { AccountReference } from "../features/account/reference";
import type { AcquisitionReference } from "../features/acquisition/reference";
import type { ArrivalsReference } from "../features/arrivals/reference";
import type { LibraryReference } from "../features/library/reference";
import type { MaintenanceReference } from "../features/maintenance/reference";
import type { MediaReference } from "../features/media/reference";
import type { ReleasesReference } from "../features/releases/reference";
import type { SettingsReference } from "../features/settings/reference";
import type { SystemReference } from "../features/system/reference";

declare global {
  interface Window {
    __referentiel: EngineDrawing &
      EngineQueue &
      AccountReference &
      AcquisitionReference &
      ArrivalsReference &
      LibraryReference &
      MaintenanceReference &
      MediaReference &
      ReleasesReference &
      SettingsReference &
      SystemReference;
    // The engine's own multi-layer closer, published by refonte.html: the
    // scrim covers the drawer, the dialog and the sheet alike, and a tap on it
    // closes whichever is up. Optional for the same reason `__startEngine`
    // is — a document served without the fragment must fail visibly, not here.
    __closeLayers?: () => void;
  }
}
