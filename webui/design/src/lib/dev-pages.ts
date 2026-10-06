// Whether a build carries the development pages — the work's own pages, such as
// the lots progress.
//
// THEY EXIST WHERE THE DESIGN HOST'S INTERFACE IS BUILT, and nowhere else: in
// the design host's own build (`__DESIGN_HOST__`) and in the builds carrying the
// mock layer, which is that interface under its quality control — the harness
// and the unit suite. A build without the mock layer is a production one, and
// the development pages are not in it.

/**
 * Whether a build carries the development pages.
 *
 * @param designHost Whether this is the design host's own build.
 * @param mocksBuiltIn Whether the build carries the mock layer.
 * @returns True on the design host and under its quality control; false in production.
 */
export function carriesDevPages(designHost: boolean, mocksBuiltIn: boolean): boolean {
  return designHost || mocksBuiltIn;
}

/** This build's answer. */
export const DEV_PAGES_BUILT_IN = carriesDevPages(__DESIGN_HOST__, __MOCKS_BUILT_IN__);
