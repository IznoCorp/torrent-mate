// acquisitions — what is followed, and how it is chased
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { Schemas } from "../../lib/contract-schemas";

// A FOLLOW, as the world holds one: a title, its kind, its year, the status the
// acquisition engine last put it in, and — for a series — whether the show is
// still running (`showStatus`). `fresh` is what pushes a newly-added follow to the top.
export type Follow = Schemas["Follow"];

// What a follow's words and facts are drawn from: a served follow, or the
// subject a panel composes for a medium not followed yet (an incomplete show,
// a title) — its identity and status, and whatever else is known.
export type FollowSubject = Pick<Follow, "title" | "kind" | "year" | "status"> & Partial<Follow>;

// A search hit, exactly as the mock `SEARCH` constant shapes one. `k` is the
// French kind label used throughout the legacy templates ("Film" / "Série"),
// not the English "movie"/"show" token `cardHTML` itself expects for a
// poster's aspect ratio — the two are deliberately different vocabularies at
// two different seams, and a migrated screen converts between them exactly
// where `openAddScreen` used to.
export type SearchResult = Schemas["SearchResult"];

export type SearchResults = Schemas["SearchResults"];

// WHAT BECAME OF A CREATE, in the three answers a caller can draw differently.
// `added` — the layer took it. `held` — nothing answered, the outbox keeps it
// and the optimistic write stands, which is NOT a failure. `refused` — the
// layer answered a refusal, so the local write is undone and the operator is
// told. A boolean would fold the first two together or the last two, and both
// foldings are a sentence about the machine that is not true.
export type FollowOutcome = "added" | "held" | "refused";

// One TVDB/TMDB candidate offered for a decision still awaiting arbitration.
// `withoutPoster` marks a candidate with no poster at the provider (the
// placeholder is what says so on the card, never a truncating sentence);
// `overview` is the synopsis shown there.
export type DecisionCandidate = Schemas["DecisionCandidate"];

// The choice recorded once a decision resolves — the winning candidate's
// identity plus how it was reached (`via`): picked from the offered list, or
// found through a manual search override that bypassed that list.
export type DecisionChoice = Schemas["DecisionChoice"];

// A folder still waiting on an operator's call. `candidates` is empty when the
// provider returned no candidate at all — the other shape besides a populated
// list, never absent outright. `folder` is the staging folder's display name,
// never a medium title; `reason` keys the reason vocabulary.
export type PendingDecision = Schemas["PendingDecision"];

// A decision already settled. `state` keys the settled-state vocabulary.
// `choice` is present only for a resolved row — a superseded or dismissed row
// never recorded one, because no candidate was ever chosen.
export type SettledDecision = Schemas["SettledDecision"];
