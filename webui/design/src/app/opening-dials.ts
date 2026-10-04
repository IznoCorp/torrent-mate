// THE DIALS THE INTERFACE OPENS ON — which page, which tab of Acquisition and of
// Trackers, and how the Médiathèque lists. One table, read by the arrival for the
// opening state and by the harness driver's reset (B-548, B-554): a dial the
// reset left was inherited by the next named state, so a state that did not pin
// its page, its tab or its lens drew whatever the state before it had left.

/** The opening value of every navigation dial. */
export const OPENING_DIALS = {
  page: "acq",
  acqTab: "now",
  libLens: "cat",
  libCat: "all",
  libMode: "grid",
  /* « Trackers »: its open tab, and the tracker « Torrents » is filtered to. */
  trackersTab: "torrents",
  trackersFilter: "",
} as const;
