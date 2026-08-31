// THE FANART FADES IN WHEN ITS FILE IS ACTUALLY THERE — « A généralisé »
// (operator, 2026-08-31): an arrival animates its pieces when they arrive.
//
// THE POP THIS REMOVES, measured by the steward's bench: the data and the
// element's style were both in place at 93ms, so the snap the operator kept
// seeing was not the screen and not the query — it was the PAINT of the
// `background-image` when the JPEG landed from the network, after the
// transition, with no rule animating it at all. « L'arrivée sur la page média
// reste un peu trop brute, peu importe d'où on vient. »
//
// A BACKGROUND IMAGE HAS NO LOAD EVENT, which is why this needs a module at
// all: nothing in CSS can key on « the file is here ». The URL is read off the
// element, decoded through an `Image`, and the element is marked when the decode
// resolves — which is also where the lot's « images are decoded before they are
// needed » contract finally has a subject. Decode, then fade. Never snap.
//
// WHY IT INSTALLS FROM `app/` AGAINST THE NODE AS IT STANDS: the hero is drawn
// by `features/media/media-screen.tsx`, one of L14's four grandfathered files
// this lot may not extend. The posture is `drawer-gesture.ts`'s and
// `focus.ts`'s — watch what the markup already emits, add nothing to it.
//
// ─────────────────────────────────────────────────────────────────────────────
// ONE ENTRY, ONE OWNER — the trap this wave has already paid for once.
//
// A CSS animation or transition on a tree mounted under `startViewTransition`
// does not START until the transition ENDS. For a file arriving from the
// network that is exactly right: it lands afterwards anyway, and the fade is
// its own entry.
//
// But a CACHED file decodes immediately — possibly while the transition is
// still running — and a fade queued then would replay AFTER it, over a snapshot
// that already showed the picture. That is precisely the `heroin` flash:
// appear, flash, reappear.
//
// So the module distinguishes the two and says which happened, and it reads
// `image.complete` SYNCHRONOUSLY to do it: a file the cache already holds is
// complete in the same statement, and anything else has to come over the
// network. A cached hero is marked `immediate` and the transition draws it; a
// fetched one is marked `faded` and owns its own entry. The stylesheet fades
// only the second.
import { ARTWORK_ARRIVAL, HERO_BACKGROUND } from "../lib/arrival-contract";

/** Pulls the URL out of a `background-image` value, or `null`. */
function urlWithin(backgroundImage: string): string | null {
  const found = /url\(["']?(.+?)["']?\)/.exec(backgroundImage);
  return found ? found[1] : null;
}

/**
 * Marks one hero background once its file has been decoded.
 *
 * Args:
 *     node: The element carrying the `background-image`.
 */
function follow(node: HTMLElement): void {
  if (node.dataset.arrival) return;
  const source = urlWithin(getComputedStyle(node).backgroundImage);
  if (!source) return;

  const image = new Image();
  image.src = source;

  // WHETHER THE FILE IS ALREADY HERE IS READ SYNCHRONOUSLY, and that is the
  // whole discriminator. `complete` is true in the same statement for a file the
  // cache already holds; anything else has to come over the network.
  //
  // A FIRST VERSION RACED A `requestAnimationFrame` AGAINST `decode()` and
  // marked whichever won. It marked `faded` in BOTH cases — measured, with the
  // artwork delayed half a second and without — because `decode()` is
  // asynchronous even for a cached file and always lost. A discriminator that
  // answers the same way on both sides of the distinction it exists to make is
  // not a discriminator.
  if (image.complete) {
    node.dataset.arrival = ARTWORK_ARRIVAL.immediate;
    return;
  }

  const settle = () => {
    node.dataset.arrival = ARTWORK_ARRIVAL.faded;
  };
  // `decode()` is the contract the lot's Done-when asks for; `onload` is the
  // fallback for a browser that refuses to decode a cross-origin file, and a
  // failure still has to mark the element or the hero would stay invisible.
  image.decode().then(settle, settle);
}

/**
 * Watches for hero backgrounds and follows each one's file.
 *
 * Installed once at boot. It is a subtree observer rather than a per-screen
 * call because the hero is mounted by a route this module may not touch, and
 * because the same treatment is wanted from EVERY origin — list, panel, tab —
 * which is what the symptom's independence from the origin already said.
 */
export function installArtworkArrival(): void {
  const follow_all = () => {
    document.querySelectorAll<HTMLElement>(HERO_BACKGROUND).forEach(follow);
  };
  follow_all();
  new MutationObserver(follow_all).observe(document.documentElement, {
    subtree: true,
    childList: true,
  });
}
