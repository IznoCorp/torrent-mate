// The one signal this application has that a session may exist again.
//
// `refused` IS TERMINAL BY DESIGN, and that is right: a 4401 is not a
// connection problem, and retrying an expired session is a loop that produces
// nothing. What was missing is the way OUT. The notice offers « Se reconnecter »
// and navigates to the sign-in; the operator signs in, the gate hides — and the
// relay was still refused, the notice still on screen, its button still leading
// back to a sign-in already passed. An infinite loop whose only exit was a page
// reload, with every query frozen at the moment the session ended.
//
// WHY THE ADDRESS RATHER THAN THE SIGN-IN ITSELF. The maquette's sign-in
// authenticates nothing — it demonstrates the screen — so there is no success
// to subscribe to. What there IS, in both the maquette and the application it
// becomes, is a navigation: leaving the sign-in is the only observable that
// means « something changed about the session ». It is a weaker signal than a
// real sign-in and it errs the safe way: at worst the relay tries once, is
// refused again, and says so.
//
// IT LIVES IN `app/` BECAUSE IT WIRES TWO THINGS THE FRAME OWNS — the address
// model and the transport — and neither may know the other. `lib/relay.ts` must
// not know what a route is; `lib/addresses.ts` must not know what a socket is.
import { SIGN_IN_PATH } from "../lib/addresses";
import { readCondition, subscribeToCondition } from "../lib/relay-condition";
import { reconnectNow } from "../lib/relay";
import { history } from "./history-bridge";

/**
 * Reconnects when the operator leaves the sign-in with a refused session.
 *
 * Called once, from the boot. It subscribes for the document's lifetime.
 */
export function installRelayRecovery(): void {
  let wasSigningIn = history.location.pathname === SIGN_IN_PATH;
  // A SIGN-IN THE RELAY HAS NOT SPENT YET. The edge alone is not enough: the
  // server ACCEPTS and only then reads the cookie, so a refusal is a round trip
  // away — an operator who signs in and navigates on can leave the sign-in
  // while the socket still reads « connecting », and the 4401 that lands a
  // moment later then has no trigger left at all. The visit is remembered until
  // it is used.
  let signedInSince = false;

  const takeTheChance = (): void => {
    if (!signedInSince) return;
    if (readCondition().condition !== "refused") return;
    signedInSince = false;
    reconnectNow();
  };

  history.subscribe(({ location }) => {
    const isSigningIn = location.pathname === SIGN_IN_PATH;
    if (wasSigningIn && !isSigningIn) signedInSince = true;
    wasSigningIn = isSigningIn;
    takeTheChance();
  });
  // AND WHEN THE REFUSAL ITSELF ARRIVES, for the ordering above.
  subscribeToCondition(takeTheChance);
}
