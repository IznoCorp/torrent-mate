// What Acquisitions contributes to the bottom panel, in one import.
//
// `app/panel-contributions.ts` names ONE line per feature and never one per
// producer, so this feature gathers its own siblings here. Each import runs a
// module for its SIDE EFFECT: it registers what produces a descriptor.
import "./panel-journey";
import "./panel-more";
import "./panel-suggestion";
import "./panel-discover-header";
import "./panel-add";
import "./panel-follow";
// And the settled decision's block, which the journey sheet and the media screen
// draw: it registers the « decision » kind, so it is named here like every other
// block module rather than reached through whichever file imports its helpers.
import "./decision-block";
