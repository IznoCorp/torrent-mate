// « La liste des épisodes n'est pas encore connue » on a season's row — ONE
// drawing, for the media sheet's season list and the follow panel's seasons.
//
// THE SERVER REFUSES a one-off season of a show whose episodes nothing lists
// (`acquisition.season_unknown`): it never answers « 0 missing » for what it
// cannot count. The message says it once and is gone; the row goes on saying why
// the ask took nothing, until the season is asked again.
//
// HELD IN THE CACHE, as `queued-seasons.ts` holds its mark: a client-only key,
// what this interface was told by an answer it already has.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { refusalKey } from "../../lib/refusal";
import { NoInfo } from "./no-info";

/** The cache key holding one medium's seasons refused as unknown. */
function keyFor(title: string): [string, string] {
  return ["unknown-seasons", title];
}

/**
 * Records that a season's ask was refused as unknown.
 *
 * @param client The cache the surfaces read.
 * @param title The medium.
 * @param season The season, 1-based.
 */
export function markSeasonUnknown(client: QueryClient, title: string, season: number): void {
  const held = (client.getQueryData(keyFor(title)) as number[] | undefined) ?? [];
  if (!held.includes(season)) client.setQueryData(keyFor(title), [...held, season]);
}

/**
 * Forgets a season's refusal, as it is asked again.
 *
 * @param client The cache the surfaces read.
 * @param title The medium.
 * @param season The season, 1-based.
 */
export function forgetUnknownSeason(client: QueryClient, title: string, season: number): void {
  const held = client.getQueryData(keyFor(title)) as number[] | undefined;
  if (held?.includes(season)) client.setQueryData(keyFor(title), held.filter((one) => one !== season));
}

/**
 * The refusal's words on one season's row, when its last ask was refused as unknown.
 *
 * @param props.title The medium.
 * @param props.season The season, 1-based.
 * @returns The note, or null.
 */
export function SeasonUnknown({ title, season }: { title: string; season: number }): ReactElement | null {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data } = useQuery({
    queryKey: keyFor(title),
    // IT ASKS NOBODY: no endpoint serves what an answer already said.
    queryFn: () => (client.getQueryData(keyFor(title)) as number[]) ?? [],
    enabled: false,
    initialData: [] as number[],
  });
  if (!data.includes(season)) return null;
  return (
    <div data-part="season/unknown">
      <NoInfo>{t(refusalKey("acquisition.season_unknown"))}</NoInfo>
    </div>
  );
}
