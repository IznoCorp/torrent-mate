// « Découvrir » — a page of the bottom bar.
//
// IT LEFT ACQUISITION'S TABS and kept its surface: what is proposed to follow
// is not what is being acquired, and a daily place deserves its own button.
// The surface is the one the tab drew, and its body is the page's own oracle
// region, as every page's is.
import type { ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { useStoreContent } from "../../lib/store-access";
import { DiscoverTab } from "./discover-tab";
import { suggestionsQuery } from "./queries";

/** The region the page's body is measured by. */
const REGION = "discover/body";

/**
 * The « Découvrir » page.
 *
 * @returns The page's body.
 */
export function DiscoverPage(): ReactElement {
  // Subscribed to the store's VERSION, as Acquisition's page is: the deck's
  // verbs mutate in place and signal with `touch()`.
  useStoreContent((content) => content.version);
  // THE PAGE OBSERVES WHAT IT SHOWS. The deck and the lists are drawn by the
  // fragment, which subscribes to nothing, so without this the page had no
  // active query and a pull to refresh re-read nothing at all — under
  // Acquisition's tabs it had borrowed the queue the tab bar observes.
  useQuery(suggestionsQuery);
  return <DiscoverTab region={REGION} />;
}
