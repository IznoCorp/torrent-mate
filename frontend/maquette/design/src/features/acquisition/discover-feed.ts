// THE DÉCOUVRIR FEED — the reserve, the pile, and the gesture that spends them.
//
// The last feature surface the dying engine still DREW once the frame had gone,
// and the only one where the conversion is not « React owns the markup ».
// `advanceDeck` mutates the deck's own DOM in place — it inserts a card at the
// back, decrements every `data-depth`, writes an inline transform on the card
// and removes it 440 ms later — and **a replaced node cannot animate**. React
// owning that markup would restore the string it last rendered on the next
// repaint and undo the gesture four rules measure.
//
// SO WHAT MOVED IS OWNERSHIP, NOT THE TECHNIQUE. The containers stay React's,
// their content stays imperative, and both halves are now the FEATURE's — which
// is the whole of the move. `discover-tab.tsx` already draws the containers and
// renders zero children into them, so neither world removes the other's nodes.
//
// THE ENGINE IMPORTS THESE BACK, the way it imports `app/icons.ts` and
// `features/settings/catalog.ts`: its `render()`, its `mountLoaders()`, its
// click delegation and its swipe handlers all still call them by name, and the
// day it goes this file loses an importer rather than a subject.
import i18next from "i18next";
import { deckCard, deckHints, suggestionRow, suggestionTile, type Suggestion } from "./discover-cards";

/** How many more the footer asks for at a time. */
const BATCH = 30;

/** How long a card takes to fly out, in milliseconds. */
const FLIGHT = 440;

/** How far a dismissed row travels before it is removed, in milliseconds. */
const COLLAPSE = 320;

// THE SENTINEL that asks for more when it comes into view. Module state, as it
// was engine state: one observer, disconnected before each re-arm, because two
// observers on one footer ask twice for the same batch.
let sentinel: IntersectionObserver | null = null;

// WHAT WAS LAST WRITTEN INTO EACH CONTAINER — B-247's producer half, and it was
// found by the hold written for it rather than reasoned about.
//
// `discover-tab.tsx`'s effect runs on EVERY commit and asks for the feed to be
// filled; the deck branch already refused to rewrite a pile that was there
// (« rewriting it destroys the gesture in flight »), and the list and poster
// branches rewrote unconditionally. Measured: on `acq-discover-posters`, all
// SIXTY tiles were new nodes after any store write — so a tap landing between
// `pointerdown` and `click` was lost, silently, on the one surface built to be
// browsed with a thumb.
//
// The repair is `ui/markup.tsx`'s, one layer down: write only when the string
// CHANGES. The DOM ends identical either way; what differs is whether the nodes
// are the same ones.
let lastList = "";
let lastFooter = "";

const drawing = () => window.__referentiel;
const say = (key: string, values?: Record<string, unknown>) =>
  i18next.t(`discover.${key}`, values ?? {});
const reserve = (): Suggestion[] => (window.__suggestions?.() ?? []) as Suggestion[];
const uiState = () => window.__store.read().state;

/**
 * The order the pile is spent in, minus what has been dismissed.
 *
 * THE ORDER IS DERIVED FROM THE LIST, and it is re-derived while the two
 * disagree in LENGTH. It used to be computed once, on the first draw — safe
 * while the list was a fixture that existed before anything ran. It is a query
 * now: the first draw happens before the cards land, so an order computed then
 * is empty and stays empty, and the deck draws nothing for ever. Re-deriving on
 * a length mismatch keeps what a shuffle or a dismissal put there, and fills it
 * the moment the cards arrive.
 *
 * Returns:
 *     The positions still to be shown, in the order they will be.
 */
export function deckOrder(): number[] {
  const state = uiState();
  if (!state.sugOrder || (state.sugOrder as number[]).length !== reserve().length)
    window.__store.write({ sugOrder: reserve().map((one, index) => index) });
  const gone = uiState().sugGone as Set<number>;
  return (uiState().sugOrder as number[]).filter((one) => !gone.has(one));
}

/**
 * « Passer » — sends a card to the back, so it comes round again.
 *
 * It decides NOTHING, which is the difference between it and « Pas intéressé ».
 *
 * Args:
 *     position: The card's index into the reserve.
 */
export function passerSug(position: number): void {
  const rest = deckOrder().filter((one) => one !== position);
  window.__store.write({ sugOrder: [...rest, position] });
}

/**
 * The pile, as markup — or the end mark when it has been spent.
 *
 * Returns:
 *     The deck's markup.
 */
export function deckHTML(): string {
  const remaining = deckOrder().map((position) => [reserve()[position], position] as const);
  if (!remaining.length) {
    const reference = drawing();
    return `<div class="empty" data-part="empty-state"><b>${say("allSeenLead")}</b>
        <p>${say("allSeenRest", { count: reserve().length })}</p>
        <button class="btnprimary" data-sugmore="1">${reference.svgIcon(reference.icons.refresh)}${say("loadThirtyMore")}</button></div>`;
  }
  const pile = remaining
    .slice(0, 3)
    .map(([suggestion, position], depth) => deckCard(suggestion, position, depth))
    .reverse()
    .join("");
  return `<div class="deck" data-part="deck">${pile}</div>`;
}

/**
 * Advances the pile WITHOUT rebuilding it.
 *
 * The top card flies out, the ones behind change depth — and their CSS
 * transition carries them forward — and a new card is inserted at the back,
 * rising from under the deck. Rebuilding the markup would replace every node,
 * and a replaced node cannot animate: that is what made the pile look like it
 * was cutting rather than moving.
 *
 * Args:
 *     position: The card's index into the reserve.
 *     direction: Positive to the right, negative to the left.
 */
export function advanceDeck(position: number, direction: number): void {
  const deck = document.querySelector(".deck");
  const outgoing = deck?.querySelector<HTMLElement>('.dcard[data-depth="0"]');
  if (!deck || !outgoing) return;

  outgoing.classList.add("out");
  outgoing.style.transform =
    `translateX(${direction > 0 ? 460 : -460}px) rotate(${direction > 0 ? 20 : -20}deg)`;
  outgoing.dataset.depth = "sortie";

  for (const card of deck.querySelectorAll<HTMLElement>(".dcard[data-depth]")) {
    const depth = Number(card.dataset.depth);
    if (!Number.isNaN(depth) && depth > 0) card.dataset.depth = String(depth - 1);
  }

  // The card that takes the place of the top one becomes the swipeable one, and
  // needs the gesture labels the outgoing card carried.
  const newHead = deck.querySelector('.dcard[data-depth="0"]');
  if (newHead && !newHead.querySelector(".dhint"))
    newHead.insertAdjacentHTML("beforeend", deckHints());

  // Feed the back of the pile from the order, skipping what is already shown.
  const shown = new Set(
    [...deck.querySelectorAll<HTMLElement>(".dcard")].map((card) => Number(card.dataset.deck)),
  );
  const next = deckOrder().find((one) => !shown.has(one));
  if (next != null) {
    deck.insertAdjacentHTML("afterbegin", deckCard(reserve()[next], next, 3));
    const incoming = deck.querySelector<HTMLElement>('.dcard[data-depth="3"]');
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        if (incoming) incoming.dataset.depth = "2";
      }),
    );
  }

  window.setTimeout(() => {
    outgoing.remove();
    if (!deck.querySelector(".dcard")) refreshDeck();
  }, FLIGHT);
}

/**
 * Forgets what was last written, so the next fill really writes.
 *
 * The memo above is what keeps the tiles' identity across a store write. A
 * dismissal, a mode change and a reset all mean to rewrite, and they say so
 * here rather than by defeating the memo with a flag nobody can find.
 */
export function forgetDrawnFeed(): void {
  lastList = "";
  lastFooter = "";
}

/** Rebuilds a spent pile, which is the one case rebuilding is right. */
export function refreshDeck(): void {
  const body = document.querySelector(".deckbody");
  if (!body) return;
  body.innerHTML = deckHTML();
  mountDeck();
}

/**
 * Gives the deck the height actually left in the scrollport.
 *
 * Re-run on every render and on resize, because a rotated phone is a different
 * height. Self-correcting: whatever still overflows is taken back, once — a
 * deck that makes the page scroll is a deck that is not full-screen.
 */
export function mountDeck(): void {
  const deck = document.querySelector<HTMLElement>(".deck");
  const port = document.querySelector("#port");
  if (!deck || !port) return;
  const top = deck.getBoundingClientRect().top - port.getBoundingClientRect().top;
  const height = Math.max(340, Math.round(port.clientHeight - top - 12));
  deck.style.height = height + "px";
  const overflow = port.scrollHeight - port.clientHeight;
  if (overflow > 0) deck.style.height = Math.max(340, height - overflow) + "px";
}

window.addEventListener("resize", mountDeck, { passive: true });

/** Fills the list container with whichever shape the reader chose. */
export function fillSug(): void {
  const box = document.querySelector<HTMLElement>("#sugitems");
  if (!box) return;
  const state = uiState();
  if (state.sugMode === "deck") {
    box.innerHTML = deckHTML();
    box.className = "";
    mountDeck();
    return;
  }
  const draw = state.sugMode === "poster" ? suggestionTile : suggestionRow;
  box.className = state.sugMode === "poster" ? "gallery" : "";
  const gone = state.sugGone as Set<number>;
  const markup = reserve()
    .slice(0, state.sugCount as number)
    .map((suggestion, position) => (gone.has(position) ? "" : draw(suggestion, position)))
    .join("");
  // ONLY WHEN IT CHANGES. See `lastList` above: rewriting identical markup
  // replaces every node, and a tap between press and click is then lost.
  if (markup === lastList && box.innerHTML !== "") return;
  lastList = markup;
  box.innerHTML = markup;
}

/**
 * « Pas intéressé » — reversible, because a quick gesture gets it wrong more
 * often than a pressing finger does.
 *
 * Args:
 *     position: The suggestion's index into the reserve.
 */
export function dismissSug(position: number): void {
  const gone = uiState().sugGone as Set<number>;
  const undo = () => {
    gone.delete(position);
    window.__store.touch();
  };
  const message = say("dismissed", { title: reserve()[position].t });
  if (uiState().sugMode === "deck") {
    // In the deck the whole pile changes, not one row: re-render, and the undo
    // restores both the suggestion and its place in the order. `sugGone` is a
    // Set mutated in place, so React needs the explicit bump a `write` would
    // otherwise have given it for free.
    gone.add(position);
    window.__store.touch();
    refreshDeck();
    window.__toast?.show({
      message,
      undo: () => {
        undo();
        refreshDeck();
      },
    });
    return;
  }
  const row = document.querySelector<HTMLElement>(`[data-dismissable="${position}"]`);
  if (!row) return;
  gone.add(position);
  window.__store.touch();
  forgetDrawnFeed();
  row.style.height = row.getBoundingClientRect().height + "px";
  requestAnimationFrame(() => row.classList.add("gone"));
  window.setTimeout(() => row.remove(), COLLAPSE);
  window.__toast?.show({
    message,
    undo: () => {
      undo();
      fillSug();
      sugFoot();
    },
  });
}

/** The footer: the end mark, or the sentinel that asks for more. */
export function sugFoot(): void {
  const foot = document.querySelector<HTMLElement>("#sugload");
  if (!foot) return;
  const state = uiState();
  if ((state.sugCount as number) >= reserve().length) {
    const end = `<p class="endmark">${say("endOfReserve", { loaded: reserve().length })}</p>`;
    if (end !== lastFooter || foot.innerHTML === "") {
      lastFooter = end;
      foot.innerHTML = end;
    }
    return;
  }
  const waiting =
    `<div style="display:flex;flex-direction:column;gap:14px">` +
    `${'<div class="sk row" data-skeleton="" style="height:104px"></div>'.repeat(2)}</div>`;
  if (waiting !== lastFooter || foot.innerHTML === "") {
    lastFooter = waiting;
    foot.innerHTML = waiting;
  }
  sentinel?.disconnect();
  sentinel = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadMoreSug();
    },
    { root: document.querySelector("#port"), rootMargin: "260px" },
  );
  sentinel.observe(foot);
}

/** Asks for the next batch, once. */
export function loadMoreSug(): void {
  const state = uiState();
  if (state.sugLoading || (state.sugCount as number) >= reserve().length) return;
  window.__store.write({ sugLoading: true });
  sentinel?.disconnect();
  window.setTimeout(() => {
    window.__store.write({
      sugLoading: false,
      sugCount: Math.min(reserve().length, (uiState().sugCount as number) + BATCH),
    });
    forgetDrawnFeed();
    fillSug();
    sugFoot();
  }, 420);
}

/** Re-arms the sentinel from scratch — the engine's own `mountLoaders`. */
export function remountSuggestionLoader(): void {
  sentinel?.disconnect();
  sentinel = null;
  forgetDrawnFeed();
  if (document.querySelector("#sugitems")) {
    fillSug();
    sugFoot();
  }
}

declare global {
  interface Window {
    /**
     * The feed's own driving seam, for the harness.
     *
     * These names were among the 254 the engine republished on `window` so the
     * rule suite could drive them; they left with the feed, and a rule reading
     * `deckOrder()` off the global stopped finding it. Published here rather
     * than left to the engine — `window.__sortWays` and `window.__settingLabels`
     * are the same arrangement: the feature owns the answer and the harness
     * reads it through one named door.
     */
    __discover?: {
      order: () => number[];
      pass: (position: number) => void;
      advance: (position: number, direction: number) => void;
      dismiss: (position: number) => void;
    };
  }
}

window.__discover = {
  order: deckOrder,
  pass: passerSug,
  advance: advanceDeck,
  dismiss: dismissSug,
};
