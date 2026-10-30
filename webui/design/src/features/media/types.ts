// the media catalogue — what a work IS, and what we own of it
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { Schemas } from "../../lib/contract-schemas";

// A media sheet, exactly as the served read answers one, in the contract's
// names. A movie and a show share most fields but not all (a show carries
// `seasons` and `episodes`, a movie a `runtime`); the contract says which are
// optional.
export type MediaSheet = Schemas["MediaSheet"];

// One YouTube trailer reference, as a sheet's `trailerVideo` carries it.
export type Trailer = {
  key: string;
  name: string;
  language: string;
};
