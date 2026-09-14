// THE ARRIVAL — what happens once, when the document opens on an address.
//
// The shell creates the store and the bridge FIRST and only then calls this, so
// no write ever needs recording and replaying. It adopts the opening state,
// registers the ladder's handler, reads the address it arrived at, writes the
// entries a Back will walk, lets the startup screen come off, and reopens a
// panel the address names — in that order, and every step says why it cannot
// move.
import type { Store } from "./store";
import { addressSeam } from "../lib/addresses";
import { navigationState } from "../lib/navigation-entry";
import { bridge } from "../lib/shell-doors";
import { reopenAddressedPanel } from "./addressed-panels";
import { entry, loadingDone } from "./entry";
import { onEngineBack } from "./layers";
import { walk } from "./page-switch";

/* The interface's opening state, before the address has said anything. */
const INITIAL_STATE = {
  page: "acq",
  acqTab: "now",
  libLens: "cat",
  libCat: "all",
  libMode: "grid",
  scen: "real",
  /* The pipeline's state, as the pilot's bar shows it — idle, running, or a run
     asked for while one is running, which DOIT-4 requires be QUEUED visibly
     rather than refused. */
  pipe: "idle",
  /* Maintenance: which rubric is open, and whether the blank run is on. A
     command that DELETES ignores the second — it is on until the dry run has
     named what would go. */
  maintTopic: null,
  /* Shows the SIMULATED fault on Système. Everything on this machine is green,
     and a screen that can only be green cannot be judged. */
  fault: false,
  maintBlanc: true,
  addMode: "follow",
  relatedTitle: null,
  /* The backend defaults: permissive everywhere EXCEPT exclude_3d. */
  profile: {
    min_resolution: "1080p",
    required_audio: ["VF"],
    require_known_resolution: false,
    exclude_3d: true,
  },
  addKind: "Tout",
  idProv: "TMDB",
  sortKey: "recent",
  sortReversed: false,
  resolveTarget: null,
  phase: "ready",
  tmdb: true,
  q: "",
  filter: "",
  addQ: "star wars",
  added: new Set(),
  recent: ["star wars", "silo", "the bear"],
  followMode: "list",
  pill: "tout",
  notes: false,
  selMode: false,
  selected: new Set(),
  sugCount: 30,
  sugGone: new Set(),
  sugMode: "list",
  sugOrder: null,
  sugLoading: false,
};

/**
 * Boots the interface onto the address the document opened at.
 *
 * Args:
 *     store: The interface's store, already created by the shell.
 */
export function installArrival(store: Store): void {
  store.adoptState(INITIAL_STATE);

  /* The bridge announces a back the way `popstate` did. Registered HERE: the
     real bridge exists from the shell's boot on, and nothing upstream queues
     it. */
  bridge.onBack(onEngineBack);

  /* The opening state comes from the ADDRESS, before the first paint: a reload
     that lands on the opening page rather than where one was is the defect
     DOIT-10 names, and it is fixed here rather than corrected after a frame the
     operator would see. The page travels in the PATH, so this reads both
     halves. */
  /* Read ONCE, and kept: the writes below settle the address, so by the time
     the panel is asked for at the end of this boot `location.search` no longer
     carries what was typed. */
  const arrivalSearch = location.search;
  const arrival = addressSeam.parse(location.pathname, arrivalSearch);
  const state = store.read().state;
  Object.assign(state, { page: arrival.page }, arrival.dials);
  /* The address as asked, PANEL PARAMETER EXCEPTED — and it is taken off for
     exactly the reason the arrival address below takes it off: a panel the
     interface declined is not part of the address one is left on. This field
     is what every later write of this state COMPOSES, so a parameter left in it
     comes back into the bar on the first Back. Read off what the model parsed
     rather than off `location` a second time: two readings of one address are
     two answers waiting to differ. */
  if (arrival.notFound) {
    const queryAt = arrival.notFound.indexOf("?");
    state.notFound =
      queryAt < 0
        ? arrival.notFound
        : arrival.notFound.slice(0, queryAt) +
          addressSeam.withoutPanel(arrival.notFound.slice(queryAt));
  }
  /* Kept from BEFORE the first render, because rendering an unknown id moves the
     state onto the not-found surface — and rewriting the address to match would
     make a mistyped link quietly become a different one. A browser answering 404
     leaves the address alone; so does this.

     THE BARE ROOT IS THE ONE EXCEPTION, and it is a settlement rather than a
     correction: `/` is where a bookmark, a bare link and an installed app's
     scope all land, and it names no page. It settles onto the home page's own
     address, in a REPLACE, so the first Back still reaches the guard entry.

     THE PANEL PARAMETER IS THE ONE THING TAKEN OFF, whether the panel reopens
     or not. A panel that reopens pushes its OWN entry carrying its own address
     on top of this one; a panel that does NOT reopen was declined. Either way
     this entry is the page. */
  const arrivalAddress =
    location.pathname === "/"
      ? addressSeam.compose(store.read().state)
      : location.pathname + addressSeam.withoutPanel(arrivalSearch);
  /* TWO WAYS AN ADDRESSED PANEL IS DROPPED BEFORE ANYTHING CAN DECLINE IT: an
     EMPTY value names no panel at all, and a panel asked for over the SIGN-IN
     screen is never read — the gate covers everything. A parameter that
     disappears without a word is one nobody can account for from the outside.

     ENGLISH, and not in the i18n resources, like every other console message: a
     developer reads it, never a reader of the interface. */
  if (!arrival.panel && new URLSearchParams(arrivalSearch).has(addressSeam.panelParameter)) {
    console.warn(
      arrival.signIn
        ? "the sign-in screen covers everything, so the addressed panel is dropped:"
        : "the addressed panel carries no value, so nothing is opened:",
      location.pathname + arrivalSearch,
    );
  }
  window.__referentiel.render();
  /* A cold `/login` raises the gate over a frame that is already drawn, which is
     the whole reason its address resolves to a page underneath rather than to
     nothing. Driven, so the raise does not rewrite the address it was just read
     from. */
  if (arrival.signIn) {
    walk.driven = true;
    entry?.showSignIn(false, walk.driven);
    walk.driven = false;
  }
  /* The address is put back on the entry one arrives on, so a back from
     anywhere reaches the page the link named rather than a bare document.

     EVERY WRITE BELOW RAISES THE FLAG LIKE EVERY OTHER WRITER. There are four on
     an ordinary page arrival — the arrival address, the exit guard, the floor
     beneath the arrival and the arrival entry — and the count is the ARRIVAL's:
     the home page needs no floor and a screen address puts its parent down too.
     A refusal here leaves a drawn interface on an address nobody wrote, and the
     last of them is the entry the panel's own layer is stacked on: lose it and
     the first Back spends the guard instead. */
  try {
    bridge.replace(navigationState(), arrivalAddress);
  } catch (error) {
    console.error("boot: writing the arrival address failed", error);
    window.__navEchec = true;
  }
  /* The interface exists from here on, so the startup screen has nothing left
     to cover — but it comes off when the wait it covers RESOLVES, which is the
     only rule that serves both a prototype with nothing to fetch and an app
     with a real one. */
  loadingDone?.();
  /* The guard is the FIRST entry, and the opening page sits on top of it: nothing
     can be inserted below the entry a document opens on, so the guard has to BE
     that entry. */
  try {
    bridge.replace({ tm: "garde" }); // french-ok: the exit guard's entry marker, matched by the ladder and the harness
  } catch (error) {
    console.error("boot: writing the exit guard failed", error);
    window.__navEchec = true;
  }
  /* AND THE STACK UNDER IT IS SYNTHESISED FROM THE HIERARCHY. A link opened from
     a message, a bookmark or a restored tab has no stack to unwind, so what a
     Back finds under the arrival is built here — the page the arrival BELONGS
     TO, never the home page by default. The home page is the FLOOR every other
     page stands on, which is what makes one Back from any page land there and
     the exit guard reachable from one place only.

     The entries go on in hierarchy order and the arrival's own goes on LAST,
     because the router renders by URL. An address nobody serves gets no floor,
     and neither does the sign-in screen: it covers everything, so its own
     address is already the home page's entry. */
  const homePage = addressSeam.homePage;
  const beneath: string[] = [];
  if (!arrival.notFound && (arrival.screen || arrival.page !== homePage)) {
    beneath.push(homePage);
    if (arrival.screen && arrival.page !== homePage) beneath.push(arrival.page);
  }
  /* AND AN ARRIVAL WITH NO FLOOR UNDER IT IS RECORDED AS SUCH, because a Back can
     then go under the one a later switch lays. */
  if (arrival.notFound) walk.arrivalWithoutFloor = true;
  for (const under of beneath) {
    try {
      bridge.record(
        Object.assign(navigationState(), { page: under }),
        addressSeam.compose(Object.assign({}, store.read().state, { page: under })),
      );
      /* AND THE FLOOR FLAG FOLLOWS THE WRITE, not the plan: a push that was
         refused lays nothing. */
      if (under === homePage) walk.homeFloorExists = true;
    } catch (error) {
      console.error("boot: recording the entry beneath the arrival failed", error);
      window.__navEchec = true;
    }
  }
  /* Pushed with the address one ARRIVED at rather than with the one the state
     now implies: rendering an unknown id moves the state onto the not-found
     surface, and deriving the address from it would rewrite a mistyped link. */
  try {
    bridge.record(navigationState(), arrivalAddress);
    /* ARRIVING ON THE HOME PAGE, the entry just written IS the floor. */
    if (arrival.page === homePage) walk.homeFloorExists = true;
  } catch (error) {
    console.error("boot: recording the arrival entry failed", error);
    window.__navEchec = true;
  }
  /* AND THE PANEL LAST OF ALL, so its layer entry sits on top of the arrival
     entry exactly as one opened from inside the application does. It PUSHES
     that entry, which is what tells the reader apart from the Forward the same
     function serves.

     AND IT WAITS FOR WHAT IT VALIDATES AGAINST: every entry of the addressed
     table answers from the query cache, and on a COLD LOAD none of it has landed
     when this runs. A bounded wait over frames is the shape the scroll
     restoration and the listing's paging door already use. */
  let framesLeft = 60;
  const reopenWhenTheSubjectIsThere = () => {
    const answer = reopenAddressedPanel(arrivalSearch, false, framesLeft > 1);
    if (answer !== "not yet") return;
    framesLeft -= 1;
    requestAnimationFrame(reopenWhenTheSubjectIsThere);
  };
  reopenWhenTheSubjectIsThere();
}
