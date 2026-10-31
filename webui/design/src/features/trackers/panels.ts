// What Trackers contributes to the bottom panel's block registry, in one import.
//
// `app/panel-contributions.ts` names ONE line per feature and never one per
// producer, so this feature gathers its own siblings here. The cross-seed
// block declares its two kinds — `crossSeed` and `crossSeedSwitch` — and
// registers what draws them, its own SIDE EFFECT at module evaluation. It was
// only reached through `panel-torrent.ts` and `panel-tracker.ts`, themselves
// imported by `verbs.ts` — one level further than the boot's reach follows, so
// R56 read it as never imported. A feature's own panel index is where a block
// module belongs, the same mechanism the other features' index files use.
// The obligation's outcome block (`obligationOutcome`) is reached the same
// way, so it is gathered here too.
import "./panel-cross-seed";
import "./panel-obligation-outcome";
