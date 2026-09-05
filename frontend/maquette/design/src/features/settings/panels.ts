// What Configuration contributes to the bottom panel, in one import.
//
// `app/panel-contributions.ts` names ONE line per feature and never one per
// producer, so a feature that ends up with three panels appears there once and
// gathers its own siblings here. Each import runs a module for its SIDE EFFECT:
// the field BLOCK declares its kind and registers what draws it, the two
// PRODUCERS register what builds a descriptor.
import "./panel-field";
import "./panel-secret";
import "./panel-setting";
