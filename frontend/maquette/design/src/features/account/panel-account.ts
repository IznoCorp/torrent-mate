// The account menu — what the avatar in the header raises.
//
// It lives with Compte because that is what makes it change: who is signed in,
// and the two things one can do about it. The panel that draws it is a `ui/`
// primitive and knows neither — so this file REGISTERS what produces the
// descriptor, exactly as `features/media/panel-seasons.tsx` registers what
// draws a season matrix. The panel stays domain-free; the domain stays here.
//
// A PRODUCER IS NOT A HOOK. It is called from the document-level click
// delegation, in the middle of a task that cannot await, so it reads the query
// cache synchronously (invariant 10: « a function from the cache to a
// descriptor ») and never the engine's accessors.
//
// Descriptor is the legacy `openUserSheet`'s, transplanted rather than
// translated: same fields, same order, same `data-*` targets, so the delegation
// keeps working unchanged and the oracle has nothing to report.
import i18next from "i18next";
import { icons } from "../../app/icons";
import { registerProducer, type PanelDescriptor } from "../../ui/panel/contract";
import { accountQuery, type Account } from "./queries";

/**
 * Builds the account menu's descriptor.
 *
 * ANSWERS NULL BEFORE THE ACCOUNT HAS LANDED, and that is the honest reply
 * rather than a defensive one: a panel drawn from an empty object would say the
 * server has no name, which is a statement about the data and not about the
 * fetch. The engine's producer had the fixture in hand and never faced the
 * case; a cache does.
 *
 * Args:
 *     _subject: Unused — the account menu has one subject and it is implicit.
 *     cache: What the query cache holds, read synchronously.
 *
 * Returns:
 *     The descriptor, or null while nothing has been fetched.
 */
function accountPanel(
  _subject: string,
  cache: { held: <Result>(key: readonly unknown[]) => Result | undefined },
): PanelDescriptor | null {
  const account = cache.held<Account>(accountQuery.queryKey);
  if (account === undefined) return null;
  const translate = i18next.t.bind(i18next);
  return {
    title: account.name,
    subtitle: account.mail,
    avatar: account.avatar,
    blocs: [
      {
        type: "actions",
        secondary: true,
        actions: [
          {
            // THE WORDS ARE THE ONES ALREADY WRITTEN. « Profil et préférences »
            // is the navigation table's name for that page and « Se déconnecter »
            // is the account screen's own button — one derivation per question
            // (§13). Retyping either into a new key would render correctly while
            // the two copies drifted, which is the defect a retyped string IS.
            text: translate("navigation.pages.profile"),
            icone: icons.user,
            target: { go: "profile" },
          },
          {
            text: translate("screens.accountPage.signOut"),
            icone: icons.logout,
            ton: "danger",
            target: { signout: "1" },
          },
        ],
      },
    ],
  };
}

// Declared to the registry as this module evaluates, WITH WHAT IT NEEDS TO HAVE
// LANDED. The menu is raised from the header on every page, and the account's
// query belongs to the account page — so without this the cache is empty
// everywhere but there, the producer answers `null`, and the menu opens
// nowhere. Measured, on `sheet-user`, by three rules at once.
registerProducer("account", { produce: accountPanel, needs: [accountQuery] });
