// The account feature's tap verbs — the avatar that opens the account panel, and
// the sign-out both the panel and the account page offer.
//
// ONE REGISTRY ANSWERS THEM (`lib/verbs.ts`); this module is named once in
// `app/panel-contributions.ts`. Signing out is the entry's own act, so it is
// asked of `app/entry.ts` directly rather than of a window seam.
import { signOut } from "../../app/entry";
import { panel } from "../../lib/shell-doors";
import { registerVerb } from "../../lib/verbs";

// The avatar carries the account's own name, valueless: what it opens is a KIND,
// and `panel-account.ts` produces it.
registerVerb("account", () => panel.produce("account"));

registerVerb("signout", () => {
  void signOut();
});
