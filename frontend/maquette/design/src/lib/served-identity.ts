// WHAT THE HOST IS SERVING, put into words — the answer to « is what I am
// looking at what is on `main`? », which the screen could not answer at all.
//
// THE DEFECT THIS REPLACES WAS NOT SILENCE. The drawer stated a version and a
// build as literals — `0.98.23`, `build 58d0d4fd · à jour` — while the
// repository stood nineteen patch versions further on, and « à jour » asserted a
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
  /** The branch checked out, or "" when HEAD is detached. */
  branch: string;
  /** Whether HEAD is detached — no branch, only a commit. */
  detached: boolean;
  /** The commit, abbreviated. */
  commit: string;
  /** Whether the tree the host serves from carries changes that commit does not. */
  dirty: boolean;
}

declare global {
  interface Window {
    __servedIdentity?: ServedIdentity | null;
  }
}

/** The three lines the drawer shows, already worded. */
export interface IdentityLines {
  /** What the block is. */
  label: string;
  /** The branch, the detached statement, or the unavailable one. */
  primary: string;
  /** The commit and its dirty mark, or why nothing could be named. */
  secondary: string;
  /** Whether a real identity was published — read by the rule, not by a style. */
  known: boolean;
}

/** The resource keys this block words itself from, in one place. */
const WORDS = "common.servedIdentity";
const KEYS = ["label", "dirty", "detached", "unavailable", "unavailableReason"] as const;

/**
 * Reads the interface's words for this block, and never renders `undefined`.
 *
 * `i18next.t(key, { returnObjects: true })` answers the KEY AS A STRING when
 * the key is missing, so an unchecked cast to an object yields `undefined` for
 * every field — and `undefined` on screen reads as a value, which is the whole
 * defect this block was written to end. A missing resource therefore shows its
 * own key path: unmistakably broken, in no language, and holdable by a rule.
 *
 * @returns One entry per key, each a non-empty string.
 */
function words(): Record<string, string> {
  const read = i18next.t(WORDS, { returnObjects: true });
  const found = (typeof read === "object" && read !== null ? read : {}) as Record<string, unknown>;
  const wording: Record<string, string> = {};
  for (const key of KEYS) {
    const value = found[key];
    wording[key] = typeof value === "string" && value !== "" ? value : `${WORDS}.${key}`;
  }
  return wording;
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
  const wording = words();
  const served = typeof window === "undefined" ? undefined : window.__servedIdentity;
  // `!= null` and not `!== undefined`: a published `null` would pass the
  // stricter test and then throw on the first field read, from inside the
  // drawer's own render — so the whole drawer would fail, not merely its
  // footer.
  //
  // Every field is checked, not merely the object: a partial payload renders
  // « undefined » on screen, which reads as a value rather than as a hole. A
  // host that cannot name all of them names none. A DETACHED head carries no
  // branch, so `branch` is empty there by construction and is required only
  // when `detached` is false.
  const usable =
    served != null &&
    typeof served.detached === "boolean" &&
    typeof served.branch === "string" &&
    (served.detached || served.branch !== "") &&
    typeof served.commit === "string" && served.commit !== "" &&
    typeof served.dirty === "boolean";
  if (!usable) {
    return {
      label: wording.label,
      primary: wording.unavailable,
      secondary: wording.unavailableReason,
      known: false,
    };
  }
  const identity = served as ServedIdentity;
  return {
    label: wording.label,
    // A detached checkout is NOT a branch called « HEAD », and saying so is the
    // point: the incident that opened this defect was a detached checkout two
    // commits behind, read as a branch.
    primary: identity.detached ? wording.detached : identity.branch,
    secondary: identity.dirty ? `${identity.commit} · ${wording.dirty}` : identity.commit,
    known: true,
  };
}
