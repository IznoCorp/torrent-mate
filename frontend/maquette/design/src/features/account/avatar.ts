// The signed-in picture, placed in the top bar once the account is known.
//
// The server serves the account's picture with the rest of the account
// (`/api/auth/me`), so the bar shows what that read answered — the same answer
// the account page and its menu read, through the same query definition. The
// bar is the frame's; the feature hands the picture to its door
// (`lib/topbar-avatar.ts`).
import type { QueryClient } from "@tanstack/react-query";
import { showAvatar } from "../../lib/topbar-avatar";
import { accountQuery } from "./queries";

/**
 * Asks for the account and shows its picture in the top bar.
 *
 * A read that fails leaves the bar's avatar as the markup drew it: the bar has
 * nothing else to say about an account it could not read, and the account page
 * says the failure where it is asked for.
 *
 * @param queryClient The shared cache the boot created.
 */
export function installSignedInAvatar(queryClient: QueryClient): void {
  void queryClient.fetchQuery(accountQuery).then(
    (account) => {
      if (account.avatar) showAvatar(account.avatar);
    },
    () => undefined,
  );
}
