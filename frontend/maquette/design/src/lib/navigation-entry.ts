// THE SHAPE OF A NAVIGATION ENTRY — what a page's entry carries in history.
//
// EVERY dial the address model declares travels on the entry, and that is the
// whole of the list: a dial left off is one a back cannot put back, so the
// address loses it while the interface keeps showing it — measured on
// `maintTopic`, which was the one missing.
//
// A pure read of the store, and it lives here rather than beside the page
// switch because four parties write an entry of this shape — the page switch,
// the boot, the sign-in gate and the rubric verbs — and one shape written from
// four places is the seam, not any one of them.
import { store } from "./store-access";

/* The dials an entry carries beside its page, in the order it writes them —
   written ONCE, because the entry is written in one place and read back in
   another, and two lists of one fact are one list waiting to lose a member. */
const ENTRY_DIALS = ["acqTab", "libLens", "libMode", "libCat", "maintTopic", "trackersTab", "trackersFilter"] as const;

/* WHAT A TAP KNEW about the item it opened, and nothing else: its title, its
   poster and its provider identity. The screen it opens reads them while its own
   read is out, so the first frame draws what the finger was on.

   THREE FIELDS AND NEVER A BODY. An entry's state lives in the browser's
   history, which has a size ceiling of its own — a whole sheet written there is
   an entry a browser may refuse. So the writer below copies exactly these three,
   whatever the object handed to it carries, and a rule reads that it did.

   Carried under ONE key, so a pop that reads the page's dials never mistakes
   them for a dial, and so the three travel or go missing together. */
export const CARRIED_KEY = "carried";
const CARRIED_FIELDS = ["title", "poster", "ids"] as const;

/** What a tap knew: a title, a poster address or null, and the provider identifiers. */
export type CarriedIdentity = {
  title: string;
  poster: string | null;
  ids: Record<string, number | string>;
};

/**
 * The state an entry carries for an arrival that knows what it opened.
 *
 * Args:
 *     known: What the tap knew. Only its three carried fields are copied.
 *
 * Returns:
 *     The state to write on the entry.
 */
export function carryingState(known: CarriedIdentity): Record<string, unknown> {
  return {
    [CARRIED_KEY]: Object.fromEntries(
      CARRIED_FIELDS.map((field) => [field, known[field] ?? null]),
    ),
  };
}

/**
 * What an entry carries about the item it was opened on, if anything.
 *
 * Args:
 *     state: An entry's state, as the history holds it.
 *
 * Returns:
 *     The carried fields, or undefined for an entry no tap wrote — an address
 *     typed, pasted or restored from a bookmark.
 */
export function carriedBy(state: unknown): Record<string, unknown> | undefined {
  const held = (state as Record<string, unknown> | null | undefined)?.[CARRIED_KEY];
  return held !== null && typeof held === "object" ? (held as Record<string, unknown>) : undefined;
}

/**
 * The page and the dials an entry carries, read off any object that holds them.
 *
 * Args:
 *     holder: The store's state when an entry is written, or the entry itself
 *         when a Back restores the page it names.
 *
 * Returns:
 *     The page, then every dial, each present even when it holds nothing.
 */
export function entryPatch(holder: Record<string, unknown>): Record<string, unknown> {
  return {
    page: holder.page,
    ...Object.fromEntries(ENTRY_DIALS.map((dial) => [dial, holder[dial]])),
  };
}

/**
 * The state a navigation entry carries, read from the store now.
 *
 * Returns:
 *     The entry's marker and every dial the address model declares.
 */
export function navigationState(): Record<string, unknown> {
  return { tm: "nav", ...entryPatch(store.read().state) };
}

/* THE TRAIL — the pages under the one an entry stands for, from the floor up,
   each with the history index of its own entry (§ 16 as amended: the menu's
   pages and the links inside a page STACK, so Retour replays the arrival path).
   It answers the one question no verb could: how far down the floor is from
   here, and where a page already walked lies — a page revisited moves to the
   top of the trail and is never on it twice (DECIDED 1, 2026-09-30).

   A few ids and numbers, never a body, and it survives a reload because the
   history does. EVERY entry carries the trail of the page it stands on — a
   screen's, a layer's and a rubric's included — so a switch made from any of
   them reads it off the entry it is on. */
export const TRAIL_KEY = "trail";

/** One page of the trail: its id, and the history index of its entry. */
export type TrailStop = { page: string; at: number };

/* The router's own index on every entry, which is what `at` counts. */
const INDEX_KEY = "__TSR_index";

/**
 * The history index an entry carries.
 *
 * Args:
 *     state: An entry's state, as the history holds it.
 *
 * Returns:
 *     Its index, 0 for an entry the router never stamped.
 */
export function entryIndex(state: unknown): number {
  const index = (state as Record<string, unknown> | null | undefined)?.[INDEX_KEY];
  return typeof index === "number" ? index : 0;
}

/**
 * The trail an entry stands on.
 *
 * Args:
 *     state: An entry's state, as the history holds it.
 *     homePage: The entry page — the floor every trail starts on.
 *     page: The page drawn, read when the entry names none.
 *
 * Returns:
 *     The stops from the floor up. An entry written before trails existed
 *     reads as the floor under its page (no backward compatibility, 09-29).
 */
export function trailOf(state: unknown, homePage: string, page: string): TrailStop[] {
  const held = (state as Record<string, unknown> | null | undefined)?.[TRAIL_KEY];
  if (Array.isArray(held) && held.length > 0) return held as TrailStop[];
  const at = entryIndex(state);
  return page === homePage ? [{ page, at }] : [{ page: homePage, at: at - 1 }, { page, at }];
}

/* WHAT A LAYER'S ENTRY RECORDS, so a Back onto it can put the layer back. A
   layer left for an arrival keeps its entry, and the entry is all that is left
   of it once the arrival has closed it: the kind and the subject it was
   produced from, and the page it was opened on — which is what tells an entry
   left by an arrival from the leftover a page switch buries under a layer. */
export type LayerRecord = { kind: string; subject: string; openedOn: string };

/**
 * The state a layer's entry carries — its name, and what reopens it.
 *
 * Args:
 *     layer: The rung's name.
 *     record: What reopens it, for a layer produced from a kind and a subject;
 *         none for a layer nothing can produce again.
 *
 * Returns:
 *     The entry's state.
 */
export function layerEntry(layer: string, record?: LayerRecord): Record<string, unknown> {
  return record ? { layer, ...record } : { layer };
}

/**
 * The record a panel's entry carries, read on the page as it stands now.
 *
 * Args:
 *     kind: The panel's kind.
 *     subject: What it was produced for.
 *
 * Returns:
 *     The record, its page read from the store.
 */
export function panelRecord(kind: string, subject: string): LayerRecord {
  return { kind, subject, openedOn: String(store.read().state.page ?? "") };
}

/**
 * What a layer's entry records, if it records anything.
 *
 * Args:
 *     state: An entry's state, as the history holds it.
 *     layer: The rung the entry must belong to.
 *
 * Returns:
 *     The record, or undefined for an entry of another rung or one that
 *     records nothing.
 */
export function layerRecordOf(state: unknown, layer: string): LayerRecord | undefined {
  const entry = state as Record<string, unknown> | null | undefined;
  if (!entry || entry.layer !== layer || typeof entry.kind !== "string") return undefined;
  return {
    kind: entry.kind,
    subject: String(entry.subject ?? ""),
    openedOn: String(entry.openedOn ?? ""),
  };
}
