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
// THE PAGE IS REDRAWN THROUGH THE `redraw` DOOR (`app/redraw.ts`). It is not
// `store.touch()` here even though that is most of what it does: the redraw
// also settles a page id the navigation table does not carry, and a page write
// is the one place where that branch has a subject.
import { sharedQueryClient } from "../lib/query-client";
import { registerVerb } from "../lib/verbs";
import { store } from "../lib/store-access";
import {
  bridge,
  fillAddressedPanelDoor,
  fillFollowLinkDoor,
  resetLandingDial,
  panel,
  toast,
  redraw,
} from "../lib/shell-doors";
import { hideLayers, registeredLayers } from "./layers";
import { rowFor } from "./navigation";
import { switchPage, switchPageFromLayer, type Landing } from "./page-switch";

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
 * @param landing How the tap lands (`landingOf`).
 */
function settleLanding(fromLayer: boolean, leaving: string, name: string, landing: Landing): void {
  try {
    if (fromLayer) switchPageFromLayer(leaving, landing);
    else switchPage(leaving, landing);
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error(`data-${name}: the navigation write refused`, error);
    window.__navEchec = true;
  }
}

/* WHAT CHOOSES A DESTINATION rather than follows a link: the bottom bar, and a
   menu's entry — the account menu's marks itself `data-destination`. */
const DESTINATION_MENU = '[data-part="shell/tab-bar"], [data-destination]';

/**
 * How a tap lands, read from WHERE it was made and WHAT it leads to (DESIGN § 3).
 *
 * The bar and the menus CHOOSE a destination: a bar page unwinds the trail
 * onto the floor (§ 16 rule 2, Q11), a menu page stacks on the page left (§ 16
 * as amended). A tap anywhere else — a page, a screen, a panel — is a LINK, and
 * a link stacks on what it was tapped on, the entry page included (Q12).
 *
 * @param page The destination.
 * @param chooser Whether the tap came from the bar or the menu.
 * @returns The landing.
 */
function landingOf(page: string, chooser: boolean): Landing {
  const barPage = rowFor(page)?.inBar === true;
  if (chooser) return barPage ? "unwind" : "stackOnPage";
  return "stack";
}

/* THE PAGE A CONTROL NAMES. Navigating CLOSES whatever is open above it:
   without that, one changed page while staying stuck on the media sheet. */
registerVerb("page", (page, element) => {
  const leaving = currentPage();
  const landing = landingOf(page, element.closest(DESTINATION_MENU) !== null);
  hideLayers();
  store.write({ page });
  scrollPortToTop();
  redraw();
  switchPage(leaving, landing);
});

/* A LANDING THAT CAN BE ASKED FROM A LAYER — the account menu's « Profil et
   préférences », and a panel's « Compléter » through the link door. Landing
   must LEAVE the layer: the menu's entry goes with it, a panel's is kept
   (D-L13-1) so Retour gives it back. */
/**
 * Lands on a page from a link, a layer included — the `go` verb, and the door a
 * feature's own verb follows a link through (« Compléter », `followLink`).
 *
 * @param page The destination.
 * @param dial The dial the link lands on, passed to the page unread.
 * @param chooser Whether the tap chose a destination (a menu's entry).
 */
function goTo(page: string, dial: string | undefined, chooser: boolean): void {
  const fromLayer = Boolean(history.state && history.state.layer);
  const leaving = currentPage();
  const landing = landingOf(page, chooser);
  registeredLayers.close("drawer", true);
  panel?.close(true);
  store.write({ page });
  /* AND THE PAGE PUTS ITS OWN DIAL BACK, through the door its feature fills:
     arriving at the acquisition page from elsewhere has always opened its first
     tab. The frame does not name that dial — it is the page's, and the write is
     made where it is understood. A control that names the dial it lands on
     (`data-dial`) has it passed along, unread. */
  resetLandingDial?.(page, dial);
  scrollPortToTop();
  redraw();
  settleLanding(fromLayer, leaving, "go", landing);
}

registerVerb("go", (page, element) => {
  goTo(page, element.dataset.dial, element.closest(DESTINATION_MENU) !== null);
});

fillFollowLinkDoor((page, dial) => goTo(page, dial, false));

/* A LANDING FROM THE DRAWER. The drawer is NOT a route, so its entry does not
   survive the destination. What the page left becomes depends on the
   destination (§ 16 as amended): a bar page unwinds the trail onto the floor, a
   menu page stacks on the page left, and the page one is on only closes the
   drawer. */
registerVerb("navgo", (page) => {
  const fromDrawer = Boolean(history.state && history.state.layer === "drawer");
  const leaving = currentPage();
  const landing = landingOf(page, true);
  registeredLayers.close("drawer", true);
  store.write({ page });
  scrollPortToTop();
  redraw();
  settleLanding(fromDrawer, leaving, "navgo", landing);
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

/* « RÉESSAYER » ON A SURFACE THAT HOLDS NO READ OF ITS OWN: every active read is
   asked again, which is what the word promises. */
registerVerb("retry", () => {
  void sharedQueryClient?.refetchQueries({ type: "active" });
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
  else if (kind === "torrent") panel?.produce("torrent", reference);
  else if (kind === "reassign") panel?.produce("reassign", reference);
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
