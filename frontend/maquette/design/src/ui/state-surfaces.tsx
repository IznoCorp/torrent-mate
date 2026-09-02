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
import { skeletonLine, surfaceError } from "./variants";

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
 * One line of placeholder where a sentence will go, while its read is in flight.
 *
 * A PART, NEVER A BLOCK: it stands inside the element that will carry the
 * answer, so the screen's blocks are the same blocks at every instant and a
 * read that lands replaces a line, not a layout. `data-skeleton` is what the
 * harness counts; `aria-hidden` because a placeholder says nothing a reader
 * should hear.
 */
export function SkeletonLine({
  width,
}: {
  /** Roughly how long the sentence will be. */
  width?: "full" | "wide" | "half" | "short";
}): ReactElement {
  return <span className={`sk ${skeletonLine({ width })}`} data-skeleton="" aria-hidden="true" />;
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
 * THE RETRY RE-ASKS WHERE A CALLER GIVES IT SOMETHING TO ASK, and is delegated
 * everywhere else. The button carried `data-phase="ready"` alone: the engine's
 * document-level handler writes a PAGE's UI phase and re-asks nothing, so on a
 * surface that owns a query the control said « Réessayer » and did something
 * else. A caller holding a read passes `onRetry`; the delegation attribute is
 * emitted only when none does, so the surfaces the engine still draws keep the
 * behaviour they had.
 *
 * AND A FAILURE CARRIES ITS OWN REASON. `detail` is what the server said — data,
 * never copy — and it stands where the body sentence would. That sentence
 * asserts a TIMEOUT, and it was printed over a 502 that had answered with its
 * reason in hand: a constant that cannot change when the reality does is the
 * first thing §13 forbids, and an error surface is not exempt.
 *
 * AN `onRetry` PROP WAS WRITTEN AND TAKEN BACK ONCE BEFORE. It made the
 * library's surface write `phase` — a SERVER-STATE key — from a component, and
 * `check-state-ownership.py --arm server-state` refused it: the component share
 * went 4 → 5 against the ceiling in force that day, which is what a component
 * ceiling exists to see — the union alone stays put when the engine already
 * writes the key. (Both numbers moved after that phase: the ceiling is 0 now
 * and so is the share. This paragraph records the measurement that refused the
 * prop, not a threshold in force.) The arm was right about what it refused: a
 * component writing a SERVER-STATE key. `onRetry` re-asks a query and writes
 * nothing, and that paragraph's own last sentence — « a retry that re-asks
 * belongs to the phase that gives this surface a query » — names the phase this
 * is.
 *
 * B-031 SHRINKS BY ONE SURFACE and is not closed: « Réessayer on every error
 * surface is inert » stays true of every surface without a read to re-ask.
 */
export function SurfaceError({ subject, detail, onRetry }: {
  /** What could not be loaded, in the interface's own words. */
  subject: string;
  /** What the server said, if it said anything. Data, never copy. */
  detail?: string;
  /** Re-asks the caller's own read. Without one, the retry stays delegated. */
  onRetry?: () => void;
}): ReactElement {
  const { t } = useTranslation();
  return (
    <div className={surfaceError()} data-part="surface-error" role="alert">
      <b>{t("surfaces.error.lead", { subject })}</b>
      {/* PRESENCE, NOT TRUTHINESS. A failure whose reason is an empty string is
          still a failure that ANSWERED, and falling back on the timeout sentence
          there says the opposite of what happened. */}
      {detail !== undefined ? (
        <span data-part="surface-error/detail">{detail}</span>
      ) : (
        t("surfaces.error.body")
      )}
      {/* TWO LITERAL ELEMENTS, not one with a spread. The markup guard SKIPS an
          element whose props are spread, so the contract this button carries —
          its part name, and the delegation attribute it wears only when no
          caller re-asks — sat outside the guard that exists to read exactly
          that. */}
      {onRetry ? (
        <button data-part="surface-error/retry" onClick={onRetry}>
          {t("surfaces.error.retry")}
        </button>
      ) : (
        <button data-part="surface-error/retry" data-phase="ready">
          {t("surfaces.error.retry")}
        </button>
      )}
    </div>
  );
}
