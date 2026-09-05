// The bottom panel's verbs, and the address an addressed panel travels at.
//
// The store arrives as an ARGUMENT rather than being read off `window`: this
// module is what a producer's `open` runs through, so the thing it writes is
// the thing the boot handed it, and no reader has to work out which of the two
// doors was meant.
import { installArtworkArrival } from "./artwork-arrival";
import { flushSync } from "react-dom";
import {
  holderFor,
  needsFor,
  producerFor,
  producerNeeds,
  refuseBlock,
  refuseProducer,
  registeredProducers,
  type PanelDescriptor,
} from "../ui/panel/contract";
import type { QueryClient } from "@tanstack/react-query";
import { addressOf, isScreenPath, withPanel } from "../lib/addresses";
import type { Store } from "./store";

declare global {
  interface Window {
    // The probe R56 calls to prove the panel REFUSES a block nobody declared.
    // Published here because the constructor it exercises is a component now.
    __unknownPanel: () => void;
    // The same probe one level up: a panel KIND nobody produces must raise.
    __unknownProducer: () => void;
    /** Re-asks for what the moved producers read and no component observes. */
    __refillProducers?: () => void;
  }
}

/* The bottom panel, as the shell's verbs — what every legacy producer calls
   instead of the dead `openSheet(html)`. The descriptor of FACTS crosses
   untouched; the markup is `PanelContent`'s business.

   The store write is flushed SYNCHRONOUSLY, and that is the whole subtlety of
   moving this layer. React commits a frame later by default, while the legacy
   layer's callers were written against a DOM that was already updated when
   `openSheet`/`closeSheet` returned: `data-del` closes the sheet and opens a
   dialog on the next line, and the dialog raises the SAME shared `#scrim` — a
   commit landing after that line would clear the scrim out from under the
   dialog. Flushing keeps the ordering every caller already relies on, and the
   panel's own content changes in the same task as the class that reveals it,
   so the sheet never slides in showing the previous panel for a frame. */
/* The address an addressed panel travels at — D1 read literally. The query
   says how THIS surface is being looked at, and under a screen the surface IS
   the screen: the panel hangs off the path one is already on, with whatever
   else that address carries kept verbatim.

   Composing it from `state.page` instead is not a cosmetic difference. A
   screen is a ROUTE, mounted by the router, so pushing the page's own path
   stops the route matching and the screen the operator linked to unmounts
   behind the panel — measured on `/media/$provider/$id`. Off a screen, the
   page composes its address as it always did: the page IS the surface
   there. */
function panelAddress(address: string): string {
  if (isScreenPath(window.location.pathname))
    return (
      window.location.pathname + withPanel(window.location.search, address)
    );
  const { state } = window.__store.read();
  return addressOf(String(state.page ?? ""), state, address);
}

/* Raised while a panel is being put back onto the entry that ALREADY records
   it. It is the one case where a panel opens and history must not move: a
   Forward lands on the layer entry the first open pushed, and that entry is
   already there, already `{ layer: "sheet" }`, already carrying the panel's own
   address. Pushing a second one would leave a duplicate the next Back spends
   without taking the panel's address off. */
let onCurrentEntry = false;

/**
 * Runs a producer's open with the history write suppressed.
 *
 * The producer is called through this door rather than handed an argument,
 * because the argument would have to travel through every producer that opens
 * a panel — and they open it by describing FACTS, which is the whole of what
 * they are meant to know.
 *
 * Args:
 *     open: The producer call that opens the panel.
 */
function openPanelOnCurrentEntry(open: () => void): void {
  onCurrentEntry = true;
  try {
    open();
  } finally {
    onCurrentEntry = false;
  }
}

/**
 * Installs the panel's verbs onto the published seam.
 *
 * Called from the boot once the store exists and after the history bridge is
 * in place — `openPanel` below pushes a layer entry through it.
 *
 * Args:
 *     store: The single owner of the mutable state.
 *     queryClient: The cache a producer reads. It arrives as an ARGUMENT for
 *         the reason the store does — the thing a producer reads is the thing
 *         the boot handed this module, and no reader has to work out which of
 *         two doors was meant.
 */
export function installPanelHost(store: Store, queryClient: QueryClient): void {
  // INSTALLED FROM HERE FOR THE REASON THE CARRIED POSTER WAS: `app/shell.tsx`
  // stands at 398 of a 400-line hard ceiling and an import plus a call would put
  // it AT it. This is the nearest installer that boots once and owns no surface.
  installArtworkArrival();
function openPanel(descriptor: PanelDescriptor): void {
  // Same order as the legacy `openSheet`: the layer first, the history entry
  // second. This file is SHELL code — the seam itself — so it writes the store
  // directly rather than through data.ts's `writeUiState` component door.
  // THE PANEL OPENS BY ITS OWN SLIDE, and the view transition that briefly
  // wrapped this is GONE (operator, 2026-08-31). It existed to carry the
  // poster from the tile into the panel; the operator watched the real
  // slow-motion and withdrew the gesture — « la transition poster entre liste
  // et panneau n'est vraiment pas fluide du tout, elle est même très
  // dérangeante ». What replaced it is drawn and named: the panel keeps the
  // slide its own stylesheet gives it on the way IN, and on the way OUT — when
  // « Voir la fiche » leaves it for the media screen — it is captured leaving
  // by the navigation's own transition, under the name `leaving-panel`. Nothing
  // is wrapped HERE, and that is still the decision.
  //
  // Wrapping the opening WITHOUT the carry would have been worse than nothing:
  // the sheet already slides up in its own stylesheet, and a view transition
  // over it is the same two-systems-one-element defect the hero paid for.
  flushSync(() =>
    store.write({ panelDescriptor: descriptor, panelOpen: true }),
  );
  if (onCurrentEntry) return;
  try {
    // D1's second tier: a panel whose subject is stable travels in the query,
    // so a reload reopens it. One with no `address` is transient and keeps the
    // address it opened over.
    window.__bridge.pushLayer(
      "sheet",
      descriptor.address ? panelAddress(descriptor.address) : undefined,
    );
  } catch (error) {
    // B-026's own residual: `window.__bridge` is assigned synchronously at this
    // module's top level, before any producer can call `open` — so unlike
    // the legacy `openSheet` swallow this copies, there is no boot-time
    // window where the bridge is genuinely absent. A throw here means the
    // write itself failed, and the store above already flushed the panel
    // open: silence would leave the interface showing the panel with no
    // history entry recording it, the exact URL/UI disagreement DOIT-10
    // forbids. Same wiring as `recordPath`'s and `data-navgo`'s own
    // tails.
    // ENGLISH, and not in `fr.json`: a console message is a tool message,
    // read by a developer, never by a reader of the interface.
    console.error("openPanel: navigation write failed", error);
    window.__navEchec = true;
  }
}

function closePanel(pop?: boolean): void {
  // Guarded per LAYER, exactly as `closeSheet` was: closing an already-closed
  // sheet would consume a history entry that belongs to someone else.
  if (!isPanelOpen()) return;
  flushSync(() => store.write({ panelOpen: false }));
  // `pop` means the entry is already being popped by the gesture that got us
  // here; otherwise the layer unwinds its own, through the engine's latch.
  if (!pop) window.__derouler?.("sheet");
}

// The STORE answers, never the DOM: a legacy caller asks in the middle of its
// own task ("is a layer up before I open a screen?"), and the store is right
// at that instant whatever React has painted.
function isPanelOpen(): boolean {
  return store.read().state.panelOpen === true;
}

/* OPENS A PANEL BY KIND — the seam every moved producer arrives through, and
   the reason `app/` learns no domain in the process: `kind` and `subject` are
   opaque strings here. The dying engine's delegation asks for « the panel about
   this », and which feature answers is the registry's business.

   A producer that answers `null` opens nothing. That is not a failure to
   report: it is the honest reply for a subject the cache does not hold yet, and
   it is what the engine's own producers already did by returning early. A KIND
   nobody registered is the other case entirely, and it RAISES — the two look
   the same from outside and only one of them is a defect. */
function producePanel(kind: string, subject = ""): void {
  const produce = producerFor(kind);
  if (produce === null) refuseProducer(kind);
  const descriptor = produce(subject, { held });
  if (descriptor !== null) {
    openPanel(descriptor);
    return;
  }
  /* NOTHING IN THE CACHE YET — so it is asked for, and the panel opens when the
     answer lands. This is not a retry loop dressed up: it is the one case a
     producer reading a cache has that a producer reading a FIXTURE never had,
     and it was measured rather than foreseen. `window.__go(id)` clears the
     cache so no measurement inherits a previous one's pages, and a named state
     that opens a panel then produces it in the SAME tick — `sheet-user` does,
     and so will every panel state after it. The engine's producer had its
     fixture in hand and always opened; this one would have opened nothing, on
     the very path three rules walk.

     WHAT IT DOES NOT DO is draw anything new. Same descriptor, same rendering,
     one beat later on a cold cache and not at all different on a warm one — the
     oracle measures at rest and has nothing to report. A subject the layer
     genuinely does not have still opens nothing, which is where this stops. */
  /* AND THE SUPPRESSION TRAVELS WITH THE DEFERRED OPEN, which is the whole of
     the paragraph above read once more. `openPanelOnCurrentEntry` clears its
     flag in a `finally` around a SYNCHRONOUS call: an open that lands a beat
     later happens after that window has shut, so the addressed reopen pushed
     exactly the duplicate entry the flag exists to prevent — measured, not
     reasoned: inside the window `history.length` read 3 with the panel closed,
     and 4 with it open once the promise settled, where a warm producer read
     4 → 4 → 4.

     It is GUARANTEED rather than occasional for any kind whose `needs` is a
     function of the subject: those are excluded from the boot's prefill by
     construction, so the first ask for any subject is always cold. The flag is
     captured here and put back around the open, which is the only place that
     knows both that the open was deferred and that it was addressed. */
  const addressed = onCurrentEntry;
  void Promise.all(
    needsFor(kind, subject).map((required) => queryClient.prefetchQuery(required)),
  ).then(() => {
    const landed = produce(subject, { held });
    if (landed === null) {
      /* THE ANSWER CAME AND THE SUBJECT IS NOT IN IT. Before `panelHolds`
         learned to say « not yet », the engine's addressed table refused this
         case itself and said so in the console; now it reaches here instead,
         and a silent nothing would be a worse diagnosis than the refusal it
         replaces.

         ENGLISH, and not in the i18n resources: a console message is a tool
         message, read by a developer, never by a reader of the interface. */
      console.warn(
        "the panel's subject is not in what the layer answered, and nothing opens:",
        kind, subject);
      return;
    }
    if (addressed) openPanelOnCurrentEntry(() => openPanel(landed));
    else openPanel(landed);
  });
}

/* WHAT A PRODUCER SEES OF THE CACHE, and all it sees. `getQueryData` answers
   what has landed and `undefined` where nothing has — synchronously, which is
   the whole requirement: a producer is called from a click handler that cannot
   await. */
function held<Result>(key: readonly unknown[]): Result | undefined {
  return queryClient.getQueryData<Result>(key);
}

/* WHAT THE PRODUCERS NEED, ASKED FOR — and published rather than called once,
   for the reason `__refillSuggestions` is: a named state CLEARS the cache so no
   measurement inherits a previous one's pages, and a query with an OBSERVER is
   re-asked by that observer while one without is not. A producer has none: it
   is called from a click, not rendered. This is the door the reset re-asks
   through, and `app/engine-data.ts` — the engine's own list of what nothing
   observes — calls it beside its own. It dies when that file does.

   PUBLISHED HERE AND FIRST CALLED THERE, which is an ordering and was measured:
   this module is installed BEFORE `installMockNetwork()`, so a fetch started on
   this line leaves before there is a layer to answer it, and the cache stays
   empty in a way that reads exactly like a producer with nothing to say. The
   first fill is `installEngineData`'s, which runs after the mocks — the same
   position `installSuggestionsLookup` fills its own reserve from. */
window.__refillProducers = () => {
  for (const required of producerNeeds()) void queryClient.prefetchQuery(required);
};

/* DOES A FEATURE HOLD THIS SUBJECT — asked by the engine's addressed-panel
   table before it opens anything from a typed address. A kind that declares no
   answer answers FALSE rather than true: an address anyone can type is refused
   when nobody has said it is holdable, which is the table's own three-ways-to-
   refuse discipline and not a new one.

   AND A « NO » THE CACHE CANNOT YET MEAN IS NOT A NO. A holder reads the query
   cache, and before this wave the same question was answered from a FIXTURE the
   engine had in hand — so cold and warm could not differ. They can now, and the
   difference was measured rather than reasoned: on a build of `4c0e274a7` a
   Forward onto an evicted `setting:` entry reopens the panel (`open: true`,
   `history.length 5 → 5`, no warning); on this seam without the clause below it
   is refused with « the addressed panel names nothing this interface holds »,
   and the address stays in the bar naming a panel that never comes back —
   which is the URL and the interface disagreeing, DOIT-10's own subject.

   So a holder's `false` is taken at face value only when the cache could
   actually have told it. When one of the kind's own needs has not landed, the
   honest answer is « not yet », and « not yet » resolves: `producePanel` below
   asks for what the kind needs and opens when the answer lands, or opens
   nothing and says so. The decision moves to the one place that can wait for
   it, which is exactly what the deferred open does one layer along.

   WHAT IT COSTS, deliberately: while a need is unlanded this answers TRUE for
   ANY subject, so a typed address naming nothing real is refused a beat later
   by `producePanel` — after one asking of the layer — instead of at once. That
   is the price of not refusing the addresses that ARE served, and the refusal
   still says so on the console. */
function panelHolds(kind: string, subject: string): boolean {
  const holds = holderFor(kind);
  if (holds === null) return false;
  if (holds(subject, { held })) return true;
  return needsFor(kind, subject).some(
    (required) => held(required.queryKey) === undefined,
  );
}

window.__panel = {
  open: openPanel,
  close: closePanel,
  isOpen: isPanelOpen,
  openOnCurrentEntry: openPanelOnCurrentEntry,
  produce: producePanel,
  holds: panelHolds,
  /* WHICH KINDS HAVE A PRODUCER, for the rule that reads the seam from
     outside. It is a reading rather than an assertion: the rule compares it
     with what it expects to be moved, so a registration lost in a refactor is
     a fallen rule instead of a panel that silently stops opening. */
  producers: registeredProducers,
};

/* Lets the contract check prove the refusal rather than trust the comment on
   it: a block type nobody declared must raise, not draw nothing. Called as a
   plain function, not rendered — the dispatcher refuses before it reads
   anything else, which is what makes the refusal provable from outside. */
window.__unknownPanel = () => refuseBlock({ type: "ceci-n-existe-pas" });

/* And the same proof for the producer registry: a kind nobody registered must
   raise rather than open an empty panel. Called as a plain function, so the
   refusal is provable from outside without a tap, which would measure the
   delegation at the same time and leave two candidates for one failure. */
window.__unknownProducer = () => producePanel("ceci-n-existe-pas");
}
