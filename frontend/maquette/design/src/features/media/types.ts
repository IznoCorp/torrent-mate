// the media catalogue — what a work IS, and what we own of it
//
// The shapes this feature's reads answer, declared where the subject lives.

// A media sheet, exactly as the served read shapes one in the engine's names — a
// movie and a show share most fields but not all (a show carries `seasons`
// and `eps`, a movie carries `duree`), and the source stays untyped JS. A
// loose index type is the honest shape here rather than a speculative
// closed one: a component narrows the fields it actually reads.
export type MediaSheet = Record<string, unknown>;

// One YouTube trailer reference, as a sheet's `trailerVideo` carries it.
export type Trailer = {
  key: string;
  name: string;
  language: string;
};
