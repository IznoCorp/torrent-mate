// A landing that names ONE acquisition card — « Voir la carte de la saison »,
// the pointer an absorbed episode's journey and a covered release carry
// (DESIGN maquette-season-recovery § 1.4, DECIDED 2): the tab that holds the
// card, that card scrolled into view, focused and highlighted.
//
// THE TRACKERS DOOR'S SHAPE, ADAPTED: `data-dial="<tab>:<acquisition>"`, the tab
// first, the acquisition's key after the first separator (a key holds none of
// its own: « Silo|S03 »).

// Between the tab and the acquisition, in a dial.
const DIAL_SEPARATOR = ":";
// How long the card is looked for once the tab is drawn — the queue may still
// be answering — and how often.
const LOOK_FOR = 3000;
const LOOK_EVERY = 100;

/**
 * Splits a landing's dial into the tab and the acquisition it names.
 *
 * @param dial The dial, as the control carries it.
 * @returns The tab, and the acquisition's key when one is named.
 */
export function dialParts(dial: string | undefined): { tab?: string; acquisition?: string } {
  if (dial === undefined) return {};
  const at = dial.indexOf(DIAL_SEPARATOR);
  return at === -1 ? { tab: dial } : { tab: dial.slice(0, at), acquisition: dial.slice(at + 1) };
}

/**
 * Brings the card of one acquisition into view once the tab has drawn it,
 * focuses it and marks it landed — the card's own variant draws the ring.
 *
 * @param acquisition The acquisition's key.
 */
export function landOnCard(acquisition: string): void {
  const started = Date.now();
  const look = () => {
    const card = [...document.querySelectorAll<HTMLElement>('#view [data-part="card"][data-acquisition]')]
      .find((one) => one.dataset.acquisition === acquisition);
    if (card === undefined) {
      if (Date.now() - started < LOOK_FOR) window.setTimeout(look, LOOK_EVERY);
      return;
    }
    card.dataset.landed = "";
    card.tabIndex = -1;
    card.scrollIntoView({ block: "center" });
    card.focus({ preventScroll: true });
  };
  window.setTimeout(look, 0);
}
