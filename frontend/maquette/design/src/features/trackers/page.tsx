// « Trackers » — a page of the bottom bar: the ratio, tracker by tracker.
//
// Its body is the page's own oracle region, `trackers/body`, set by the page
// host from the navigation row. What the body holds — the two tabs, « Torrents »
// and « Trackers », and what each lists — is drawn inside this container.
import type { ReactElement } from "react";

/**
 * The « Trackers » page.
 *
 * @returns The page's body.
 */
export function TrackersPage(): ReactElement {
  return <div data-part="trackers" />;
}
