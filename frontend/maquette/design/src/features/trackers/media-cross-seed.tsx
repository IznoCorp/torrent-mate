// The media sheet's cross-seed block (§ 19: « un bloc par tracker, réservé au
// profil administrateur »; L18 DESIGN § 3.6, F25): for each origin torrent of
// the medium still in the client, its state on every other tracker, in the
// operator's six words.
//
// THE TRACKERS FEATURE'S, composed into the sheet by its route: it reads the
// same pairs the « Torrents » tab marks (R-L17-b), and two features never import
// each other (invariant 7). GATED BY `trackers.view`, the right that opens the
// page it summarises (L18 § 1.2): absent — never greyed, never asked — for an
// account without it.
import type { ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useRights } from "../../lib/account";
import { read } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";
import { Chip } from "../../ui/chip";
import { factDetail, factList, factName, factRow, factRowBody, optionKind, sectionHeading, sheetFacts } from "../../ui/variants";
import { CROSS_SEED_TONE, familyWord, reasonSentence, stateWord, type CrossSeedPair } from "./cross-seed-state";
import { orderedPairs } from "./panel-cross-seed";

/**
 * The key the block is cached under — its own, so the stream's cross-seed
 * events refresh it (`live.ts`) and nothing else does.
 */
export const mediaCrossSeedKey = ["/api/v1/media/cross-seed"];

/**
 * One medium's cross-seed, read once per visit of its sheet (R-L17-k): no
 * interval, and only for an account that may see it.
 *
 * @param provider The provider the sheet is addressed by.
 * @param identifier The medium's identifier there.
 * @param enabled Whether the account holds the right to read it.
 * @returns The query.
 */
function useMediaCrossSeed(provider: string, identifier: string, enabled: boolean) {
  return useQuery({
    queryKey: [...mediaCrossSeedKey, provider, identifier],
    queryFn: async () => read<Schemas["MediaCrossSeed"]>(
      `/api/v1/media/${encodeURIComponent(provider)}/${encodeURIComponent(identifier)}/cross-seed`),
    enabled,
  });
}

/**
 * One pair's row: the tracker, its state, and why when the state is a refusal or a wait.
 *
 * @param props.pair The pair.
 * @param props.origin The origin torrent's hash.
 * @returns The row.
 */
function MediaPairRow({ pair, origin }: { pair: CrossSeedPair; origin: string }): ReactElement {
  const { t } = useTranslation();
  return (
    <li className={factRow()} data-part="media/cross-seed-pair" data-origin={origin} data-tracker={pair.tracker}
      data-state={pair.state}>
      <div className={factRowBody()}>
        <span className={factName()}>{pair.tracker}</span>
        <span data-part="media/cross-seed-state">
          <Chip tone={CROSS_SEED_TONE[pair.state]} label={stateWord(pair.state)} />
        </span>
        {pair.state === "error" && pair.reason !== null ? (
          <span className={factDetail()} data-part="media/cross-seed-reason" data-reason={pair.reason}>
            <b>{familyWord(pair.reason)}</b> — {reasonSentence(pair.reason)}
          </span>
        ) : null}
        {pair.state === "notSearched" && pair.waitReason !== null ? (
          <span className={factDetail()} data-part="media/cross-seed-wait">
            {t("screens.crossSeed.panel.wait", { reason: t(`screens.crossSeed.waits.${pair.waitReason}`) })}
          </span>
        ) : null}
      </div>
    </li>
  );
}

/**
 * The block, for the medium a sheet is addressed by — or nothing: for an
 * account without `trackers.view`, before the read lands, and for a medium no
 * torrent in the client carries.
 *
 * @param props.provider The provider the sheet is addressed by.
 * @param props.identifier The medium's identifier there.
 * @returns The block, or null.
 */
export function MediaCrossSeed({ provider, identifier }: { provider: string; identifier: string }): ReactElement | null {
  const { t } = useTranslation();
  const sees = useRights().holds("trackers.view");
  const { data } = useMediaCrossSeed(provider, identifier, sees);
  if (!sees || data === undefined || data.torrents.length === 0) return null;
  return (
    <section className={sheetFacts()} data-part="media/cross-seed" aria-label={t("screens.crossSeed.media.heading")}>
      <h2 className={sectionHeading()} data-part="heading">
        {t("screens.crossSeed.media.heading")}
      </h2>
      {data.torrents.map((origin) => (
        <div key={origin.infoHash} data-part="media/cross-seed-origin" data-origin={origin.infoHash}>
          <p className={optionKind()} data-part="media/cross-seed-origin-name">
            {t("screens.crossSeed.media.origin", { name: origin.name, tracker: origin.tracker })}
          </p>
          {origin.pairs.length === 0 ? (
            <p className={factDetail()}>{t("screens.crossSeed.panel.none")}</p>
          ) : (
            <ol className={factList()}>
              {orderedPairs(origin.pairs).map((pair) => (
                <MediaPairRow key={pair.tracker} pair={pair} origin={origin.infoHash} />
              ))}
            </ol>
          )}
          {origin.titleExcluded ? (
            <p className={factDetail()} data-part="media/cross-seed-title-excluded">
              {t("screens.crossSeed.panel.titleExcluded")}
            </p>
          ) : null}
        </div>
      ))}
    </section>
  );
}
