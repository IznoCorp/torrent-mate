// The « Trackers » page's live rules: which events refresh which of its reads.
//
// THE RATIO AND THE OBLIGATIONS HAVE A PAGE NOW, so the events that move them
// are claimed here, each refreshing the reads it moves and nothing else — the
// bar's badge moves with them, without the page open, because the frame
// observes the same reads for it. THE CROSS-SEED'S EVENTS TOO (L17): an
// injection, a refusal and a search's outcome move a torrent's pairs and its
// tracker's counts — never a media-sheet key, which is L18's.
import type { LiveRule } from "../../lib/live-rule";

const TRACKERS_KEY = ["/api/trackers"];

const DOWNLOADS_KEY = ["/api/acquisition/downloads"];

const OBLIGATIONS_KEY = ["/api/acquisition/obligations"];

/** Every rule this feature contributes to the relay. */
export const trackersLiveRules: readonly LiveRule[] = [
  {
    types: ["RatioMeasured"],
    keys: [TRACKERS_KEY],
    because:
      "a ratio measured anew is the tracker's summary moving: its ratio, its "
      + "volumes, and whether it has crossed its own alert threshold",
  },
  {
    types: ["SeedObligationRecorded", "SeedObligationSatisfied"],
    keys: [OBLIGATIONS_KEY],
    because:
      "an obligation recorded or met changes the mark a torrent's row wears, "
      + "and nothing the tracker's summary carries",
  },
  {
    types: ["SeedObligationBreached"],
    keys: [OBLIGATIONS_KEY, TRACKERS_KEY],
    because:
      "a broken obligation is marked on its row while the torrent is still "
      + "active, and kept on its tracker's summary once the torrent is gone — "
      + "both are the alert, so both are refreshed",
  },
  {
    types: ["DownloadStarted", "DownloadProgressed", "DownloadCompleted"],
    keys: [DOWNLOADS_KEY],
    because:
      "an entry added, advanced or finished is the download client's list "
      + "moving — the « Torrents » tab's rows, and which breach is still on an "
      + "active entry",
  },
  {
    types: ["CrossSeedInjected"],
    keys: [TRACKERS_KEY, DOWNLOADS_KEY, OBLIGATIONS_KEY],
    because:
      "an injection is a pair turning « actif » on its origin's row, a new "
      + "entry in the client, its tracker's count, and the obligation the "
      + "engine persists before it emits",
  },
  {
    types: ["CrossSeedRejected", "CrossSeedSearched"],
    keys: [TRACKERS_KEY, DOWNLOADS_KEY],
    because:
      "a refusal, or a search's outcome, is a pair's state moving on its "
      + "origin's row — and a failure is its tracker's count and the badge's "
      + "term; a queued search is seen to end in the same visit",
  },
];
