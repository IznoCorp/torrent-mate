// WHAT THE HOST IS SERVING, put into words — the answer to « is what I am
// looking at what is on `main`? », which the screen could not answer at all.
//
// THE DEFECT THIS REPLACES WAS NOT SILENCE. The drawer stated a version and a
// build as literals — `0.98.23`, `build 58d0d4fd · à jour` — while the
// repository stood twenty patch versions further on, and « à jour » asserted a
// freshness nothing measured. A screen that says nothing sends its reader to
// look; a screen that states a plausible answer stops them looking, and the
// value was credible precisely because it had been a real version once.
//
// THE IDENTITY IS THE HOST'S, NOT THE BUILD'S. `serve.py` computes it per
// request and publishes it on the document it sends, for the same reason it
// rebuilds per request: a value cached at boot drifts away from the tree it
// claims to describe, and that drift is exactly what production's own R27
// post-check exists to catch on the other side. Baking it into the bundle
// would be worse still — a build is staler than a boot.
//
// AND WHEN NOBODY PUBLISHED ONE, IT SAYS SO. The rule suite reads a MANUAL copy
// served by a plain static host, which injects nothing; so does a `vite`
// preview. Neither is the design host, and neither can name a commit. The
// honest answer there is that the identity is unavailable, with the reason —
// never a plausible number, which is the defect being repaired.
import i18next from "../i18n";

/** What the host publishes about the tree it is serving. */
export interface ServedIdentity {
  /** The branch checked out, as `git rev-parse --abbrev-ref HEAD` gives it. */
  branch: string;
  /** The commit, abbreviated. */
  commit: string;
  /** Whether the working tree carries changes that commit does not. */
  dirty: boolean;
}

declare global {
  interface Window {
    __servedIdentity?: ServedIdentity;
  }
}

/** The three lines the drawer shows, already worded. */
export interface IdentityLines {
  /** What the block is: « Version déployée ». */
  label: string;
  /** The branch, or the unavailable statement. */
  primary: string;
  /** The commit and its dirty mark, or why nothing could be named. */
  secondary: string;
  /** Whether a real identity was published — read by the rule, not by a style. */
  known: boolean;
}

/**
 * Reads the identity the host published and words it for the drawer.
 *
 * Read on every call and never memoised: the host recomputes per request, and
 * a reader that cached the first answer would reintroduce the drift the host
 * goes to the trouble of avoiding.
 *
 * @returns The worded lines, whether or not a host published anything.
 */
export function servedIdentityLines(): IdentityLines {
  const words = i18next.t("common.servedIdentity", { returnObjects: true }) as Record<string, string>;
  const served = typeof window === "undefined" ? undefined : window.__servedIdentity;
  // Every field is checked, not merely the object: a partial payload would
  // render « undefined » on screen, which reads as a value rather than as a
  // hole. A host that cannot name all three names none.
  const usable =
    served !== undefined &&
    typeof served.branch === "string" && served.branch !== "" &&
    typeof served.commit === "string" && served.commit !== "" &&
    typeof served.dirty === "boolean";
  if (!usable) {
    return {
      label: words.label,
      primary: words.unavailable,
      secondary: words.unavailableReason,
      known: false,
    };
  }
  const identity = served as ServedIdentity;
  return {
    label: words.label,
    primary: identity.branch,
    secondary: identity.dirty ? `${identity.commit} · ${words.dirty}` : identity.commit,
    known: true,
  };
}
