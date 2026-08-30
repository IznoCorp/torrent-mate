// design/src/app/bar-height.ts
// THE BOTTOM BAR PUBLISHES ITS OWN HEIGHT, AND EVERYTHING ABOVE IT READS THAT.
//
// The height is a MEASUREMENT and not a design constant: it is the drawn bar
// plus whatever safe area the phone reserves under it, so it is known only once
// the bar is on screen. Writing it into `--tm-bottom-bar-h` is what lets a
// list, a sheet or a floating button clear the bar without any of them knowing
// a distance — the app's own rule, « nothing positions itself by a distance to
// an edge », which the magic numbers that used to sit here broke.
//
// WHY THE SHELL AND NOT THE ENGINE. This is an application-level DOM concern —
// measure a node, write a custom property on the document — and it is exactly
// what `app/focus.ts` beside it already is. It lived in the legacy engine only
// because the engine was once the whole page. The engine is being taken apart,
// and anything that must survive it has to be somewhere else BEFORE it goes;
// left where it was, the bar's height would have been one more thing to rescue
// on the last day.
//
// THERE IS ONE PUBLISHER, and the engine keeps no copy. Two writers of one
// property agree until they do not, and the disagreement does not surface as
// anything a stack trace names: it is a strip of content sliding under the bar.
//
// THE PROPERTY IS SPELLED OUT AT THE WRITE. Its uses in the stylesheet spell it
// out too — `var(--tm-bottom-bar-h, 0px)`, eight of them — so both ends of the
// contract carry the name, which is what lets a rule find the publisher by
// searching for the write rather than by trusting a list of files.

/**
 * Publishes the bottom bar's measured height, and keeps it current.
 *
 * The value is written on the document element only when it CHANGES: the
 * observer fires on every layout that touches the bar, and a write per fire
 * would invalidate style for the whole document each time.
 *
 * Called once from the TAB BAR's own layout effect, so the first value
 * published is a drawn bar's rather than an empty one's — and so that it is
 * published at all: the bar is a component since L15 and does not exist when
 * the boot runs, where this used to be called.
 */
export function publishBarHeight(): void {
  const bar = document.querySelector<HTMLElement>(".bottombar");
  if (!bar) return;
  const publish = () => {
    // Rounded UP, never down: half a pixel of bar left uncovered is half a
    // pixel of content the operator cannot reach.
    const ceil = Math.ceil(bar.getBoundingClientRect().height);
    const cur =
      document.documentElement.style.getPropertyValue("--tm-bottom-bar-h");
    if (cur !== ceil + "px")
      document.documentElement.style.setProperty(
        "--tm-bottom-bar-h",
        ceil + "px",
      );
  };
  publish();
  if (typeof ResizeObserver !== "undefined")
    new ResizeObserver(publish).observe(bar);
}
