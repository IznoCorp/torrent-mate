// The network the PLATFORM gives, captured before anything replaces it.
//
// WHY IT EXISTS. The mock layer replaces `globalThis.fetch` and answers the
// maquette's CONTRACT, 404-ing every other same-origin path on purpose so that
// a call nobody meant to make is loud rather than silently satisfied. That is
// right for every request the application makes, and wrong for exactly one kind
// of call: the page asking the HOST what build it is serving. `/build.json` is
// not an operation and never will be — it is the server describing itself — so
// a poll through the mocked seam would read « no mock route » and the update
// discipline would conclude the host had gone away.
//
// WHY IT IS IN `lib/` AND NOT IN `mocks/` (invariant 10, invariant 7). Putting
// the getter beside the layer it bypasses would make `app/` import `mocks/`,
// which is the test layer — and the build can compile that layer out entirely
// (`__MOCKS_BUILT_IN__`), so the update discipline would lose its network on
// the very build that ships. What this module knows is « what the platform
// offered at load time », which is the application's SHAPE and knows no domain.
//
// THE CAPTURE IS AT MODULE EVALUATION, and that is what makes it correct. The
// mock layer installs from BOOT CODE — a function call — and every module in
// the graph is evaluated before the first line of boot runs. There is no order
// to arrange and none to get wrong.
const PLATFORM_CALL: typeof globalThis.fetch = globalThis.fetch.bind(globalThis);

/**
 * Reaches the host directly, past any layer standing in for the application's
 * network.
 *
 * It is a NAMED seam and not a convenience: anything reaching for it declares
 * that it is talking to the host rather than to the application, and that claim
 * is reviewable in one grep.
 *
 * @param address What to ask the host for.
 * @param options The request's options, if any.
 * @returns The host's answer, unmediated.
 */
export function askTheHost(
  address: string,
  options?: RequestInit,
): Promise<Response> {
  return PLATFORM_CALL(address, options);
}
