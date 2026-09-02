// design/src/components/icon.tsx
// The exact shape `svgIcon(paths, strokeWidth)` produces as an HTML string
// (`refonte.html`), rebuilt as a real element so it composes with JSX.
//
// Extracted on its THIRD user, which is what `add.tsx`'s own comment said would
// be the signal: two copies are a coincidence, three are a component. The two
// that existed were byte-identical, checked before this file replaced them, and
// the panel adopted it as the fourth. Three screens migrated by earlier waves
// (`media.tsx`, `releases.tsx`, `resolution.tsx`) still carry their own private
// copy — adopting them is a change to surfaces this one does not touch.
import type { ReactElement } from "react";
import { useMarkup } from "./markup";

export function Icon({
  paths,
  strokeWidth,
  className,
}: {
  paths: string;
  strokeWidth?: number;
  // The SIZE and anything else the drawing's context decides. The legacy
  // stylesheet said it with a descendant selector — `.bottombar svg { width:
  // 20px }` — which a converted component has no way to wear. It arrives as a
  // class from the caller's own variant instead, which is D3: a component's
  // styling lives in the component.
  className?: string;
}): ReactElement {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth || 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      // THE PATHS ARE MARKUP AND THEY ARE MEMOISED, like every other markup
      // this interface hands React. Written inline, the object was new on every
      // render, so React re-set `innerHTML` and every icon's `<path>` children
      // were replaced whenever a parent redrew. That is not cosmetic: the
      // browser delivers no `click` at all when the `pointerdown` target has
      // left the document, and a surviving ancestor does not rescue it — so a
      // press landing on an icon's STROKE, and the box is `fill="none"`, was
      // lost on any store write, on every icon-only control there is.
      dangerouslySetInnerHTML={useMarkup(paths)}
    />
  );
}
