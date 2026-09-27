// « Découvrir » — a page of the bottom bar.
//
// IT LEFT ACQUISITION'S TABS and kept its surface: what is proposed to follow
// is not what is being acquired, and a daily place deserves its own button.
// The surface is the one the tab drew, and its body is the page's own oracle
// region, as every page's is.
import type { ReactElement } from "react";
import { useStoreContent } from "../../lib/store-access";
import { DiscoverTab } from "./discover-tab";

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
  return <DiscoverTab region={REGION} />;
}
