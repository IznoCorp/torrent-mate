// Who is signed in.
import { GET, POST, route, text } from "./shared";
import { refused, type MockRoute } from "../router";
import { heldAccounts, identityDials, plexReachable, rightsOfAccount, signedIn } from "../identity";

// Why a Plex sign-in fails while the dial says Plex does not answer.
const PLEX_DOWN = "the Plex server does not answer";
const UNAVAILABLE = 503;
// Why a password is refused to an account whose role does not hold `auth.password`.
const PLEX_ONLY = "this account signs in with Plex";
const FORBIDDEN = 403;

/** Every route this subject answers. */
export function authenticationRoutes(): MockRoute[] {
  return [
    route("readAccount", GET, "/auth/me", () => signedIn()),
    // The prototype holds NO credentials: a password written into a page is
    // readable by everyone the page reaches. The gate exists to be judged as a
    // surface, and who may see it is decided by the server that serves it.
    route("signIn", POST, "/auth/login", (request) => {
      // A NAME THE ROSTER KNOWS signs that account in — when its role holds
      // `auth.password`; any other name walks through as the account dialled,
      // because the screen, not the check, is what this surface shows.
      const asked = text(request.body, "username").toLowerCase();
      const account = heldAccounts().find((one) => one.id === asked || one.name.toLowerCase() === asked);
      if (account === undefined) return signedIn();
      if (!rightsOfAccount(account.id).holds("auth.password")) return refused(FORBIDDEN, PLEX_ONLY);
      identityDials.setIdentity(account.id);
      return signedIn();
    }),
    route("signOut", POST, "/auth/logout", () => ({ ok: true })),
    route("signInWithPlex", POST, "/auth/plex", () =>
      plexReachable() ? signedIn() : refused(UNAVAILABLE, PLEX_DOWN)),
  ];
}
