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
import { forgetLadder } from "./handlers/ladder";
import { scenario } from "./scenario";
import type { components } from "../contract/types";

type Schemas = components["schemas"];

/** The trackers' subject, as the layer holds it. */
export type TrackersHeld = {
  trackers: Schemas["Tracker"][];
  downloads: Schemas["Download"][];
  obligations: Schemas["Obligation"][];
  /** Every removal asked for, in order: what a rule reads the request by. */
  removals: { infoHash: string; deleteFiles: boolean }[];
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
      trackers: structuredClone(TRACKERS) as unknown as Schemas["Tracker"][],
      downloads: structuredClone(DOWNLOADS) as Schemas["Download"][],
      obligations: structuredClone(OBLIGATIONS) as Schemas["Obligation"][],
      removals: [],
    };
    held.set(owner, subject);
  }
  return subject;
}

/** The dials a named state turns to reach a trackers' state no verb produces. */
export type TrackerDials = {
  setTrackersEmpty: (empty: boolean) => void;
  setDownloadsEmpty: (empty: boolean) => void;
  setTrackerIdle: (tracker: string) => void;
  setObligationSatisfied: (infoHash: string) => void;
  poseArrived: (title: string) => void;
  poseExternalRemoval: (infoHash: string) => void;
  poseAlertThreshold: (tracker: string, threshold: number) => void;
  poseIdentifierRefused: (tracker: string) => void;
  poseRecovered: (tracker: string) => void;
  poseOneTracker: (tracker: string) => void;
  setObligationBreached: (infoHash: string) => void;
  poseBrokenObligation: (infoHash: string) => void;
  poseTrackerRatio: (tracker: string, ratio: number) => void;
  poseEntry: (infoHash: string, fields: Partial<Schemas["Download"]>) => void;
  poseOneEntry: (infoHash: string) => void;
  trackerRemovals: () => TrackersHeld["removals"];
};

// WHERE A TRACKER'S ALERT THRESHOLD IS SET: its own key in the tracker's
// economy block, beside the floor and the target, written through the same
// settings write as they are.
const SETTING_PREFIX = "tracker.providers.";
const ALERT_THRESHOLD_SUFFIX = ".economy.alert_threshold";
const ENABLED_SUFFIX = ".enabled";

/**
 * The settings key of one tracker's alert threshold.
 *
 * @param tracker The tracker's configured name.
 * @returns The key.
 */
export function alertThresholdKey(tracker: string): string {
  return SETTING_PREFIX + tracker + ALERT_THRESHOLD_SUFFIX;
}
// The engine's words for a refused identifier — the sentence the switch's refusal
// says — read off the seeded tracker that refuses one, never retyped here.
const IDENTIFIER_REFUSED = (TRACKERS as { disabled: { reason: string | null; message: string | null } | null }[])
  .find((tracker) => tracker.disabled?.reason === "identifierRefused")?.disabled?.message ?? null;

/**
 * The settings key of one tracker's activation — the one the roster's switch
 * and Réglages both write.
 *
 * @param tracker The tracker's configured name.
 * @returns The key.
 */
export function enabledKey(tracker: string): string {
  return SETTING_PREFIX + tracker + ENABLED_SUFFIX;
}

/**
 * Turns one tracker's activation setting on or off, where the settings write puts it.
 *
 * @param tracker The tracker's configured name.
 * @param enabled Whether it is on.
 */
function setEnabled(tracker: string, enabled: boolean): void {
  const key = enabledKey(tracker);
  for (const setting of mockState().settings.flatMap((topic) => topic.settings)) {
    if (setting.key !== key) continue;
    setting.raw = enabled;
  }
}

// The milliseconds in a second: the layer dates in Unix-epoch seconds.
const MILLISECONDS_PER_SECOND = 1000;

// A download complete: its files are all there, and the client seeds it.
const DOWNLOAD_DONE = "seeding";
const COMPLETE = 1;

/** Those dials, over the trackers' subject. */
export const trackerDials: TrackerDials = {
  setTrackersEmpty: (empty: boolean) => {
    // NO TRACKER CONFIGURED, which a configuration can hold: a real answer, empty.
    trackersState().trackers = empty ? [] : (structuredClone(TRACKERS) as unknown as Schemas["Tracker"][]);
  },
  setDownloadsEmpty: (empty: boolean) => {
    // NOTHING ACTIVE ANYWHERE, the client reachable: a real answer, empty.
    trackersState().downloads = empty ? [] : (structuredClone(DOWNLOADS) as Schemas["Download"][]);
  },
  setTrackerIdle: (tracker: string) => {
    // ONE TRACKER WITH NOTHING ACTIVE, the others unchanged.
    const held = trackersState();
    held.downloads = held.downloads.filter((entry) => entry.tracker !== tracker);
  },
  // NOT A DIAL — a reading: the removals the layer was asked for, and whether
  // each took its files with it.
  trackerRemovals: () => structuredClone(trackersState().removals),
  poseArrived: (title: string) => {
    // A DERIVATION, SHOWN AS ONE: the medium a direct add is still downloading
    // ARRIVES — its download completes, so the staging area serves its card; the
    // card loses the chip that said the download's progress. No seed holds an
    // arrived direct add of a series nobody follows.
    for (const entry of trackersState().downloads) {
      if (entry.title === title) Object.assign(entry, { state: DOWNLOAD_DONE, progress: COMPLETE, etaSeconds: null });
    }
    const state = mockState();
    state.moving = state.moving.map((card) => {
      if (card.title !== title) return card;
      const { chip, ...arrived } = card;
      void chip;
      return arrived;
    });
    forgetLadder(title);
  },
  poseExternalRemoval: (infoHash: string) => {
    // A DERIVATION, SHOWN AS ONE: the entry is removed BY HAND in the download
    // client, and the engine releases its obligation cleanly on its next read —
    // no removal asked by the interface. No real obligation has been released.
    const subject = trackersState();
    subject.downloads = subject.downloads.filter((entry) => entry.infoHash !== infoHash);
    for (const obligation of subject.obligations) {
      if (obligation.infoHash === infoHash) obligation.releasedAt = obligation.addedAt;
    }
  },
  poseAlertThreshold: (tracker: string, threshold: number) => {
    // THE OPERATOR'S OWN SETTING, posed where the settings write puts it: the
    // summary reads it there, never from a copy.
    const key = alertThresholdKey(tracker);
    for (const setting of mockState().settings.flatMap((topic) => topic.settings)) {
      if (setting.key !== key) continue;
      setting.raw = threshold;
      setting.displayedValue = String(threshold);
    }
  },
  poseIdentifierRefused: (tracker: string) => {
    // A DERIVATION, SHOWN AS ONE: the tracker refuses the configured identifier
    // since the layer's frozen now, and the engine switches it off for it — its
    // setting turned off where the settings write puts it. No real tracker refuses it.
    const since = Math.floor(Date.parse(scenario().now) / MILLISECONDS_PER_SECOND);
    for (const held of trackersState().trackers) {
      if (held.name !== tracker) continue;
      held.disabled = { by: "failure", reason: "identifierRefused", message: IDENTIFIER_REFUSED, since };
    }
    setEnabled(tracker, false);
  },
  poseOneTracker: (tracker: string) => {
    // ONE TRACKER LEFT IN THE CONFIGURATION, a seeded one: the roster at its smallest.
    const held = trackersState();
    held.trackers = held.trackers.filter((one) => one.name === tracker);
  },
  poseRecovered: (tracker: string) => {
    // A DERIVATION, SHOWN AS ONE: the failure that switched the tracker off is
    // over — it answers again — so switching it back on is accepted. Its setting
    // stays off until the operator turns it on.
    for (const held of trackersState().trackers) {
      if (held.name === tracker) held.disabled = null;
    }
  },
  setObligationBreached: (infoHash: string) => {
    // A DERIVATION, SHOWN AS ONE: an obligation BROKEN at its own deadline, its
    // torrent still active. No real obligation has been broken.
    for (const obligation of trackersState().obligations) {
      if (obligation.infoHash === infoHash) {
        obligation.breachedAt = obligation.addedAt + obligation.minimumSeedTimeSeconds;
      }
    }
  },
  poseBrokenObligation: (infoHash: string) => {
    // A DERIVATION, SHOWN AS ONE: the engine BROKE the obligation at its own
    // deadline, then its torrent left the client — kept on its tracker, unseen.
    // No real obligation has been broken.
    const subject = trackersState();
    for (const obligation of subject.obligations) {
      if (obligation.infoHash !== infoHash) continue;
      const brokenAt = obligation.addedAt + obligation.minimumSeedTimeSeconds;
      obligation.breachedAt = brokenAt;
      const tracker = subject.trackers.find((one) => one.name === obligation.sourceTracker);
      tracker?.brokenObligations.push({ infoHash, title: obligation.title ?? "", brokenAt, seen: false });
    }
    subject.downloads = subject.downloads.filter((entry) => entry.infoHash !== infoHash);
  },
  poseTrackerRatio: (tracker: string, ratio: number) => {
    // THE RATIO MEASURED ANEW on the server, before the event announcing it: a
    // rule then delivers `RatioMeasured` and reads what the page makes of it.
    for (const held of trackersState().trackers) {
      if (held.name === tracker) held.ratio = ratio;
    }
  },
  poseEntry: (infoHash: string, fields: Partial<Schemas["Download"]>) => {
    // A DERIVATION, SHOWN AS ONE: a real entry given what no seed holds — the
    // client's figures (its one read was never taken), another engine state, a
    // long real name, no medium. The named state that calls it says what it poses.
    for (const entry of trackersState().downloads) {
      if (entry.infoHash === infoHash) Object.assign(entry, fields);
    }
  },
  poseOneEntry: (infoHash: string) => {
    // ONE ENTRY LEFT IN THE CLIENT, a real one: the list at its smallest.
    const held = trackersState();
    held.downloads = held.downloads.filter((entry) => entry.infoHash === infoHash).slice(0, 1);
  },
  setObligationSatisfied: (infoHash: string) => {
    // A DERIVATION, SHOWN AS ONE: an obligation MET at its seed time, the
    // torrent still seeding. No real obligation is met — `acquire.db`'s
    // `seed_obligation` holds no satisfied row; the backend reads `satisfied_at`.
    for (const obligation of trackersState().obligations) {
      if (obligation.infoHash === infoHash) {
        obligation.satisfiedAt = obligation.addedAt + obligation.minimumSeedTimeSeconds;
      }
    }
  },
};
