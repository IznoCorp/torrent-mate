// Who is signed in, and the doors in (the operator, 2026-10-03).
//
// EVERY LOGIN IS AN E-MAIL. HOW AN ACCOUNT SIGNS IN IS A FACT OF THE ACCOUNT,
// not of its role: the Plex server's owner by Plex and a fallback password; a
// Plex-linked account by Plex only; a local account by its password only.
import ACCOUNTS from "../seeds/accounts.json";
import { GET, POST, PUT, field, route, text } from "./shared";
import { policyRefusal } from "./accounts";
import { answeredWith, refused, type MockRoute } from "../router";
import {
  heldAccounts,
  openSession,
  plexClaim,
  plexReachable,
  signedIn,
  signedInId,
  signInAllowed,
  passwordAccepted,
} from "../identity";

const UNAVAILABLE = 503;
const INVALID = 400;
const UNAUTHORIZED = 401;
const FORBIDDEN = 403;
const CONFLICT = 409;
// A CUT ACCOUNT'S REFUSAL (the operator, 2026-10-04), answered only once its
// credentials or its Plex identity are proven: it tells nothing to whoever
// does not hold them, so it sits after the one anti-enumeration refusal.
const DISABLED = () => refused(FORBIDDEN, "this account's access is cut", "auth.access_disabled");
// The answer of a PIN nobody has claimed yet: ask again.
const PENDING = 202;

/** The PINs started since the layer was installed — each sign-in its own. */
let pins = 0;

/** Every route this subject answers. */
export function authenticationRoutes(): MockRoute[] {
  return [
    route("readAccount", GET, "/auth/me", () => signedIn()),
    // The prototype holds NO credentials: a password written into a page is
    // readable by everyone the page reaches. The gate exists to be judged as a
    // surface, and who may see it is decided by the server that serves it.
    route("signIn", POST, "/auth/login", (request) => {
      // AN E-MAIL THE ROSTER KNOWS signs that account in — when it holds a
      // password: the owner's fallback, or a local account's. A Plex-linked
      // account is refused with THE ONE refusal every failed attempt gets, so
      // no attempt tells which e-mails the server knows (O-K1-4). Any other
      // e-mail walks through as the account dialled, because the screen, not
      // the check, is what this surface shows — save while that account is
      // cut: an unknown e-mail proves no credentials, so it gets the one
      // refusal, never the cut account's.
      const asked = text(request.body, "email").toLowerCase();
      const account = heldAccounts().find(
        (one) => one.email.toLowerCase() === asked,
      );
      if (account?.signInKind === "plex")
        return refused(UNAUTHORIZED, "refused", "auth.refused");
      if (account === undefined && !signInAllowed(signedInId()))
        return refused(UNAUTHORIZED, "refused", "auth.refused");
      if (!openSession(account?.id ?? signedInId())) return DISABLED();
      return signedIn();
    }),
    route("signOut", POST, "/auth/logout", () => ({ ok: true })),
    route("startPlexSignIn", POST, "/auth/plex/start", () => {
      if (!plexReachable())
        return refused(
          UNAVAILABLE,
          "plex.tv does not answer",
          "plex.unreachable",
        );
      pins += 1;
      return { pinId: pins, signInUrl: ACCOUNTS.plexSignInUrl };
    }),
    // THE CLAIM IS THE DIAL'S: the identity dialled signs in, after the
    // pending answers dialled; or Plex refuses an identity with no access to
    // the server, or the PIN expires unclaimed.
    route("signInWithPlex", POST, "/auth/plex", (request) => {
      if (typeof field(request.body, "pinId") !== "number")
        return refused(
          INVALID,
          "no PIN this server started",
          "plex.pin_unknown",
        );
      if (!plexReachable())
        return refused(
          UNAVAILABLE,
          "plex.tv does not answer",
          "plex.unreachable",
        );
      const claim = plexClaim();
      if (claim === "pending") return answeredWith(PENDING, { pending: true });
      if (claim === "no-access")
        return refused(UNAUTHORIZED, "refused", "auth.refused");
      if (claim === "expired")
        return refused(
          CONFLICT,
          "the PIN expired unclaimed",
          "plex.pin_expired",
        );
      if (!openSession(signedInId())) return DISABLED();
      return signedIn();
    }),
    route("changeOwnPassword", PUT, "/auth/password", (request) => {
      const account = heldAccounts().find((one) => one.id === signedInId())!;
      if (account.signInKind === "owner")
        return refused(
          FORBIDDEN,
          "the owner's fallback password is replaced on the server only",
          "password.held_by_cli",
        );
      if (account.signInKind === "plex")
        return refused(
          FORBIDDEN,
          "this account signs in with Plex",
          "auth.plex_only",
        );
      if (!passwordAccepted())
        return refused(
          INVALID,
          "the current password does not match",
          "password.current_wrong",
        );
      return policyRefusal(text(request.body, "newPassword")) ?? { ok: true };
    }),
  ];
}
