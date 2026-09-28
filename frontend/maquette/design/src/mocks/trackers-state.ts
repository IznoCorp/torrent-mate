// What the layer holds of the trackers: the roster, the download client's
// entries and the obligations they owe — mutable, so a gesture can move them.
//
// HELD BESIDE THE LAYER'S STATE, AND RENEWED WITH IT. It is keyed on the object
// `mockState()` answers, which `reset()` replaces: a reset therefore starts this
// subject again from its seeds without a line of its own in the reset.
import DOWNLOADS from "./seeds/downloads.json";
import OBLIGATIONS from "./seeds/obligations.json";
import TRACKERS from "./seeds/trackers.json";
import { mockState } from "./state";
import type { components } from "../contract/types";

type Schemas = components["schemas"];

/** The trackers' subject, as the layer holds it. */
export type TrackersHeld = {
  trackers: Schemas["Tracker"][];
  downloads: Schemas["Download"][];
  obligations: Schemas["Obligation"][];
};

const held = new WeakMap<object, TrackersHeld>();

/**
 * The trackers' subject for the layer's current state, seeded on first read.
 *
 * @returns What the layer holds.
 */
export function trackersState(): TrackersHeld {
  const owner = mockState();
  let subject = held.get(owner);
  if (subject === undefined) {
    subject = {
      trackers: structuredClone(TRACKERS) as Schemas["Tracker"][],
      downloads: structuredClone(DOWNLOADS) as Schemas["Download"][],
      obligations: structuredClone(OBLIGATIONS) as Schemas["Obligation"][],
    };
    held.set(owner, subject);
  }
  return subject;
}

/** The dials a named state turns to reach a trackers' state no verb produces. */
export type TrackerDials = {
  setTrackersEmpty: (empty: boolean) => void;
};

/** Those dials, over the trackers' subject. */
export const trackerDials: TrackerDials = {
  setTrackersEmpty: (empty: boolean) => {
    // NO TRACKER CONFIGURED, which a configuration can hold: a real answer, empty.
    trackersState().trackers = empty ? [] : (structuredClone(TRACKERS) as Schemas["Tracker"][]);
  },
};
