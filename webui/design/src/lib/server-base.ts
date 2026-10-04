// WHERE THE SERVER IS ADDRESSED: the contract's `servers` URL, which every one
// of its paths is relative to, and the event stream is served beside them.
//
// ONE CONSTANT, in a module that imports nothing, because the client
// (`query-client.ts`) and the stream (`relay.ts`) both build on it and neither
// should reach the other for it. `server-base.test.ts` holds it equal to the
// contract's.

/** The base every operation of the contract is served under. */
export const SERVER_BASE = "/api/v1";
