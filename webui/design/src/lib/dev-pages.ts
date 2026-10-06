// Whether a build carries the development pages — the work's own pages, such as
// the lots progress.
//
// THE ROUTE IS IN EVERY BUILD TODAY: `__MOCKS_BUILT_IN__` is true in every
// build until the switchover flips it, so this flag is true everywhere and the
// development pages are in any bundle built from this tree. WHAT KEEPS THE
// DATA SAFE IS THE DOOR, not the build: the design host serves the bytes only
// with `TM_DEV_LOTS_OUT` set and a v1 session, and a host without them answers
// 404 or 401. The build flag removes the route from a production bundle only
// once the switchover turns the mock layer off.

/**
 * Whether a build carries the development pages.
 *
 * @param designHost Whether this is the design host's own build.
 * @param mocksBuiltIn Whether the build carries the mock layer.
 * @returns True on the design host and wherever the mock layer is built in; false once the switchover removes it.
 */
export function carriesDevPages(designHost: boolean, mocksBuiltIn: boolean): boolean {
  return designHost || mocksBuiltIn;
}

/** This build's answer. */
export const DEV_PAGES_BUILT_IN = carriesDevPages(__DESIGN_HOST__, __MOCKS_BUILT_IN__);
