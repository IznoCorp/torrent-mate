// What a surface shows when it has nothing to show yet, or nothing at all.
//
// ONE DERIVATION PER QUESTION (§13 of the constitution). Eight surfaces are
// about to be wired to a query cache and every one of them needs a skeleton and
// an error surface; eight implementations of the same two is how two surfaces
// come to answer one question differently, and the operator sees two truths.
//
// IT KNOWS NO DOMAIN (invariants 7 and 10). It takes what it renders — how many
// placeholders, what could not be loaded, what to do about it — and it never
// asks which surface is asking.
//
// WHY THE ERROR SURFACE IS A COMPONENT AT ALL, and it is not tidiness. The
// library drew it by asking the ENGINE for a string and handing it to
// `dangerouslySetInnerHTML`: the markup, the French and the retry all lived in
// `legacy.js`'s `surfErrInner`. That is the engine reaching into a converted
// surface, and D5 says its share dies with the surface that stops needing it.
// The engine keeps `surfErr` for the surfaces IT still draws; what leaves is
// its last component reader.
//
// THE RETRY STAYS DELEGATED until a surface has a query to re-ask. See the
// note on `SurfaceError`: a callback was written here and taken back in the
// same phase, because it made a component write a server-state key.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { surfaceError } from "./variants";

/**
 * The placeholders a surface shows while its data is in flight.
 *
 * THE MARKUP IS THE ENGINE'S, kept to the character. `sk` carries the shimmer,
 * `data-skeleton` is what the harness counts, and `tile` against `skcard` is
 * the difference between a gallery cell and a list row. Re-deriving any of that
 * here would move a rectangle the oracle measures, for no reason at all.
 */
export function Skeletons({
  count,
  shape,
}: {
  /** How many placeholders. */
  count: number;
  /** Which shape: a gallery cell, or a list row. */
  shape: "tile" | "card";
}): ReactElement {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className={shape === "tile" ? "sk tile" : "sk skcard"}
          data-skeleton=""
          data-part={shape === "tile" ? "tile" : undefined}
        />
      ))}
    </>
  );
}

/**
 * What a surface shows when its data could not be loaded at all.
 *
 * IT OWNS ITS OUTER ELEMENT, which the six call sites drew themselves in two
 * different ways: five through the typed variant, and the library through the
 * raw `surferr` class inside a string the engine built. The two render
 * identically — they are one of R80's sixteen pairs, declaring the same terms —
 * so unifying them moves nothing, and the oracle is what says so rather than
 * this sentence.
 *
 * `role="alert"` is L03's and it stays: an error nobody is told about is
 * NE-DOIT-PAS-5 with extra steps.
 *
 * THE RETRY STAYS DELEGATED, and that is a decision rather than an omission. No
 * surface is wired to the query cache yet, so there is nothing here to re-ask:
 * the button keeps the `data-phase="ready"` the engine's document-level handler
 * already reads, which puts the surface back into its ready state.
 *
 * AN `onRetry` PROP WAS WRITTEN AND TAKEN BACK IN THE SAME PHASE. It made the
 * library's surface write `phase` — a SERVER-STATE key — from a component, and
 * `check-state-ownership.py --arm server-state` refused it: the component share
 * went 4 → 5 against a ceiling of 4. The arm was right. A retry that re-asks
 * belongs to the phase that gives this surface a query, and adding the prop
 * before its first caller would be machinery nobody could justify.
 *
 * B-031 IS THEREFORE NOT TOUCHED. Its entry reads « Réessayer on every error
 * surface is inert » and its status is the operator's to move.
 */
export function SurfaceError({ subject }: {
  /** What could not be loaded, in the interface's own words. */
  subject: string;
}): ReactElement {
  const { t } = useTranslation();
  return (
    <div className={surfaceError()} data-part="surface-error" role="alert">
      <b>{t("surfaces.error.lead", { subject })}</b>
      {t("surfaces.error.body")}
      <button data-part="surface-error/retry" data-phase="ready">
        {t("surfaces.error.retry")}
      </button>
    </div>
  );
}
