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

export function Icon({
  paths,
  strokeWidth,
}: {
  paths: string;
  strokeWidth?: number;
}): ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth || 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: paths }}
    />
  );
}
