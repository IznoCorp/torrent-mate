// THE FRAME'S OWN VERBS, declared to the tap registry.
//
// Six names the document's delegation answered until this phase: the page a
// control names, the two landings — `go` from a layer, `navgo` from the drawer
// — the drawer itself, a message, and the panel an element addresses. None of
// them belongs to a feature: each is the frame deciding what the shell does, so
// they live beside the page switch and the ladder rather than in anybody's
// feature directory.
//
// TWO NAMES COULD NOT COME, and neither is an oversight: `pipe` and `phase` are
// SERVER STATE by `check-state-ownership.py`'s own table, and that arm refuses a
// component — `app/` included, which it reads as one — writing such a key at a
// ceiling of zero. They stay on the engine's last delegation branch until their
// conversion (b·12 for the pipeline's endpoint), and the listener with them.
//
// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`, like every other registration the boot names.
//
// THE PAGE IS REDRAWN THROUGH `window.__referentiel.render()`, the way every
// verb that still shares its page with the engine's drawing does
// (`features/acquisition/verbs.ts` is the precedent). It is not `store.touch()`
// here even though that is most of what it does: `render()` also settles a page
// id the navigation table does not carry, and a page write is the one place
// where that branch has a subject. It becomes a touch when the engine goes.
import { registerVerb } from "../lib/verbs";
import { store } from "../lib/store-access";
import {
  bridge,
  fillAddressedPanelDoor,
  resetLandingDial,
  panel,
  toast,
} from "../lib/shell-doors";
import { hideLayers, registeredLayers } from "./layers";
import { switchPage, switchPageFromLayer } from "./page-switch";

/** Redraws the page the engine still draws beside the components. */
function redraw(): void {
  window.__referentiel.render();
}

/** The page showing right now — what a switch is told it is leaving. */
function currentPage(): string {
  return String(store.read().state.page);
}

/* A LANDING STARTS THE PAGE AT THE TOP, and the scrolling element is the
   frame's own port rather than the document: a page that kept the previous
   one's offset opened halfway down a list nobody had scrolled. */
function scrollPortToTop(): void {
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
}

/**
 * Settles the history of a landing, from wherever it was asked.
 *
 * A landing asked from a LAYER settles the destination on the floor, so one
 * back from it reaches the page one entered from and not the layer one opened.
 * It is settled here rather than by letting the layer's close unwind and the
 * arrival push: a back is asynchronous, so its pop would land after the push
 * and overwrite it.
 *
 * @param fromLayer Whether the tap was made on a layer.
 * @param leaving The page being left.
 * @param name The verb's name, for the console when the write refuses.
 */
function settleLanding(fromLayer: boolean, leaving: string, name: string): void {
  try {
    if (fromLayer) switchPageFromLayer(leaving);
    else switchPage(leaving);
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error(`data-${name}: the navigation write refused`, error);
    window.__navEchec = true;
  }
}

/* THE PAGE A CONTROL NAMES. Navigating CLOSES whatever is open above it:
   without that, one changed page while staying stuck on the media sheet. */
registerVerb("page", (page) => {
  const leaving = currentPage();
  hideLayers();
  store.write({ page });
  scrollPortToTop();
  redraw();
  switchPage(leaving);
});

/* A LANDING THAT CAN BE ASKED FROM A LAYER — today only the user sheet's
   « Profil et préférences »: every other producer renders into the page body,
   which sits under every layer and is therefore untappable while one is open
   (walked control by control, B-024). Landing must LEAVE the layer. */
registerVerb("go", (page) => {
  const fromLayer = Boolean(history.state && history.state.layer);
  const leaving = currentPage();
  registeredLayers.close("drawer", true);
  panel?.close(true);
  store.write({ page });
  /* AND THE PAGE PUTS ITS OWN DIAL BACK, through the door its feature fills:
     arriving at the acquisition page from elsewhere has always opened its first
     tab. The frame does not name that dial — it is the page's, and the write is
     made where it is understood. */
  resetLandingDial?.(page);
  scrollPortToTop();
  redraw();
  settleLanding(fromLayer, leaving, "go");
});

/* A LANDING FROM THE DRAWER. The drawer is NOT a route, so its entry does not
   survive the destination — and neither does the entry of the page being left:
   a drawer entry is a top-level destination like any other. */
registerVerb("navgo", (page) => {
  const fromDrawer = Boolean(history.state && history.state.layer === "drawer");
  const leaving = currentPage();
  registeredLayers.close("drawer", true);
  store.write({ page });
  scrollPortToTop();
  redraw();
  settleLanding(fromDrawer, leaving, "navgo");
});

/* THE DRAWER. Its entry is pushed so a back closes it, and a refusal of the
   history write leaves the drawer open rather than the interface stuck.

   IT IS A FUNCTION AS WELL AS A VERB because the harness's named states open
   the drawer without a tap — `harness/states/frame.ts` composes the state where
   it is up — and a state driving the interface through a synthetic click would
   be measuring the registry rather than the drawer. */
export function openDrawer(): void {
  store.write({ drawerOpen: true });
  try {
    bridge?.pushLayer("drawer");
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("data-drawer: the layer entry refused", error);
  }
}

registerVerb("drawer", () => {
  openDrawer();
});

/* A MESSAGE A CONTROL CARRIES, said as it is written on the control. */
registerVerb("toast", (message) => {
  toast?.show({ message });
});

/* THE PANEL AN ELEMENT ADDRESSES. A card body opens its panel on a simple tap;
   a gallery reaches the same panel by a long press, timed where the press is.
   One entry point either way, so a surface states WHICH panel it wants and
   never how to build it. */
function openAddressedPanel(address: string): void {
  const separator = address.indexOf(":");
  const kind = address.slice(0, separator);
  const reference = address.slice(separator + 1);
  if (kind === "sug") panel?.produce("suggestion", reference);
  else if (kind === "add") panel?.produce("add", reference);
  else panel?.produce("follow", reference);
}

registerVerb("panel", (address) => {
  openAddressedPanel(address);
});

/* THE PRESS READS THE SAME OPENER THROUGH A DOOR, because the gesture is still
   the engine's: it decides WHICH element a press addresses — the walk widens
   from a poster to the card that knows the panel — and opening is this
   module's. The door goes when the gesture does. */
fillAddressedPanelDoor((element) => {
  const address = (element as HTMLElement).dataset.panel;
  if (address !== undefined) openAddressedPanel(address);
});
