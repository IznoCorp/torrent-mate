// Who is signed in.
import { GET, POST, route } from "./shared";
import { refused, type MockRoute } from "../router";
import { plexReachable, signedIn } from "../identity";

// Why a Plex sign-in fails while the dial says Plex does not answer.
const PLEX_DOWN = "the Plex server does not answer";
const UNAVAILABLE = 503;

/** Every route this subject answers. */
export function authenticationRoutes(): MockRoute[] {
  return [
    route("readAccount", GET, "/api/auth/me", () => signedIn()),
    // The prototype holds NO credentials: a password written into a page is
    // readable by everyone the page reaches. The gate exists to be judged as a
    // surface, and who may see it is decided by the server that serves it.
    route("signIn", POST, "/api/auth/login", () => signedIn()),
    route("signOut", POST, "/api/auth/logout", () => ({ ok: true })),
    route("signInWithPlex", POST, "/api/auth/plex", () =>
      plexReachable() ? signedIn() : refused(UNAVAILABLE, PLEX_DOWN)),
  ];
}
