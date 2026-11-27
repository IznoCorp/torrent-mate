// How the « Trackers » page writes its dates (its figures and sizes are
// `lib/byte-size.ts`'s, shared with the acquisition card).
//
// THE DAY IS THE FRAME'S (`lib/clock.ts`): Suivis says a follow's date the same way, and the
// two features may not import each other.
export { dayOf } from "../../lib/clock";
