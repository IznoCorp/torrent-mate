// Who is signed in.
import ACCOUNT from "../seeds/ACCOUNT.json";
import { GET, POST, route } from "./shared";
import type { MockRoute } from "../router";

/** Every route this subject answers. */
export function authenticationRoutes(): MockRoute[] {
  return [
    route("readAccount", GET, "/api/auth/me", () => ACCOUNT),
    // The prototype holds NO credentials: a password written into a page is
    // readable by everyone the page reaches. The gate exists to be judged as a
    // surface, and who may see it is decided by the server that serves it.
    route("signIn", POST, "/api/auth/login", () => ACCOUNT),
    route("signOut", POST, "/api/auth/logout", () => ({ ok: true })),
  ];
}
