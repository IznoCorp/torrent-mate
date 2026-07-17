/**
 * LegacyRedirect — forwards a route change while preserving query-string parameters.
 *
 * react-router's {@link https://reactrouter.com/en/main/components/navigate | <Navigate>}
 * drops query strings on redirect: ``<Navigate to="/medias" />`` strips
 * ``?media=123`` from the URL, breaking deep-link preservation mandated by
 * {@link https://github.com/izno/PersonalScraper/blob/main/docs/reference/product-intent.md | DOIT-10}
 * ("l'URL encode l'état complet de la page").
 *
 * This component reads the current search params via {@link useSearchParams} and
 * appends them to the target path, so a legacy URL like
 * ``/scraping?media=tt0123456`` correctly resolves to
 * ``/medias?media=tt0123456``.
 *
 * Args:
 *   to: The destination path (without query string).
 *
 * Returns:
 *   A {@link Navigate} element with the forwarded query string, using ``replace``
 *   so the redirect does not create a history entry.
 */
import { Navigate, useSearchParams } from "react-router-dom";

export function LegacyRedirect({ to }: { to: string }) {
  const [searchParams] = useSearchParams();
  const suffix =
    [...searchParams].length > 0 ? `?${searchParams.toString()}` : "";
  return <Navigate to={`${to}${suffix}`} replace />;
}
