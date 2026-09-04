// What Acquisitions contributes to the bottom panel, in one import.
//
// `app/panel-contributions.ts` names ONE line per feature and never one per
// producer, so this feature gathers its own siblings here. Each import runs a
// module for its SIDE EFFECT: it registers what produces a descriptor.
import "./panel-journey";
import "./panel-more";
import "./panel-suggestion";
import "./panel-add";
