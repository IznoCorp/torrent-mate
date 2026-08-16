/**
 * MediaSheetPage — thin route host for the autonomous {@link MediaSheet} component.
 *
 * Reads ``provider`` and ``providerId`` from the route params and the optional
 * ``kind`` hint from the query string, then mounts the component. The page
 * itself carries no data logic — the component owns its fetch lifecycle so it
 * can later be mounted in a drawer or inline elsewhere without wiring changes
 * (DESIGN D7).
 */

import { ArrowLeft } from "lucide-react";
import type { ReactElement } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { MediaSheet } from "@/components/media/MediaSheet";
import { ErrorState } from "@/components/ds/ErrorState";

/**
 * MediaSheetPage — the route-level entry for ``/media/:provider/:providerId``.
 *
 * Returns:
 *   The media sheet element.
 */
export default function MediaSheetPage(): ReactElement {
  const { provider, providerId } = useParams<{
    provider: string;
    providerId: string;
  }>();
  const [searchParams] = useSearchParams();
  const kindParam = searchParams.get("kind");
  const navigate = useNavigate();

  /** Pop history when there is somewhere to go; a deep-linked fiche has no
   *  app history under it and would otherwise leave the app. */
  const back = (): void => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) {
      void navigate(-1);
    } else {
      void navigate("/acquisition");
    }
  };

  // Only accept known kind values — anything else falls through to no-hint.
  const kind: "movie" | "tv" | undefined =
    kindParam === "movie" || kindParam === "tv" ? kindParam : undefined;

  // Params are guaranteed present by the route pattern; this is a defensive
  // gate only — a malformed URL without provider or providerId cannot render
  // a meaningful sheet.
  if (provider === undefined || providerId === undefined) {
    return (
      <ErrorState
        title="URL incomplète"
        message="Les paramètres 'provider' et 'providerId' sont requis dans l'URL."
      />
    );
  }

  return (
    <>
      {/* Operator report: on iPhone the edge-swipe back is awkward — the
          fiche carries the same « ‹ Retour » bar as the add-media screen
          (.mq scope on the bar alone, for the exact same look). */}
      <div className="mq">
        <div className="screenbar">
          <button
            type="button"
            aria-label="Retour"
            className="fback"
            onClick={() => {
              back();
            }}
          >
            <ArrowLeft aria-hidden="true" />
            Retour
          </button>
        </div>
      </div>
      <MediaSheet
        provider={provider}
        providerId={providerId}
        {...(kind !== undefined ? { kind } : {})}
      />
    </>
  );
}
