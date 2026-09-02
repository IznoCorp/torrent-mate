// The identifiers of a medium and the actions a sheet offers: rescrape and
// delete for what is owned, follow or add for what is not.
import { useTranslation } from "react-i18next";
import { Icon } from "../../ui/icon";
import { SkeletonLine } from "../../ui/state-surfaces";
import { useMediaReference } from "./reference";
import type { Follow } from "./sheet-fields";
import { actionButton, factsPanel, keyValueRow, sectionHeading, sheetActions } from "../../ui/variants";

export function MediaDetails({
  title,
  isFilm,
  owns,
  followed,
  follows,
  prov,
  inFlight,
  identified,
}: {
  title: string;
  /** True for a film, false for a series, null while the kind is in flight. */
  isFilm: boolean | null;
  owns: boolean;
  followed: boolean;
  follows: Follow[];
  prov: Record<string, string | number>;
  /** Whether the sheet's read is still out — identifiers not yet known are a skeleton row, never an absence. */
  inFlight: boolean;
  /** Whether a medium was identified at all. With none, ownership is unknown, not false. */
  identified: boolean;
}) {
  const { icons } = useMediaReference();
  const { t } = useTranslation();
  return (
    <>
      <div>
        <h2 className={sectionHeading()} data-part="heading" style={{ marginBottom: "6px" }}>
          {t("screens.media.information")}
        </h2>
        <div className={factsPanel()} data-part="panel">
          <div className={keyValueRow()} data-part="key-value">
            <span>{t("screens.media.follow")}</span>
            {/* The SECOND follow test, and the strict one: an exact title
                match, or an exact match on the title without its year
                suffix. The hero block above answers the same question
                through `baseTitle` on BOTH sides — a follow recorded
                under a different year suffix reads « actif » there and
                « non suivi » here. Transplanted as found. */}
            <span>
              {follows.some(
                (follow) =>
                  follow.t === title || follow.t === title.split(" (")[0],
              )
                ? t("screens.media.followActive")
                : t("screens.media.followInactive")}
            </span>
          </div>
          {inFlight && Object.keys(prov).length === 0 ? (
            <div className={keyValueRow()} data-part="key-value">
              <span><SkeletonLine width="short" /></span>
              <span><SkeletonLine width="half" /></span>
            </div>
          ) : null}
          {Object.entries(prov).map(([key, value]) => (
            <div className={keyValueRow()} data-part="key-value" key={key}>
              <span>{key.toUpperCase()}</span>
              <span
                style={{
                  fontFamily: "ui-monospace,Menlo,monospace",
                  fontSize: "11px",
                }}
              >
                {String(value)}
              </span>
            </div>
          ))}
          <div className={keyValueRow()} data-part="key-value">
            <span>{t("screens.media.metadataRefreshed")}</span>
            <span>{t("screens.media.metadataRefreshedValue")}</span>
          </div>
        </div>
      </div>

      <div className={sheetActions({ secondary: true })} data-part="sheet/actions">
        {!identified ? (
          // NOTHING IS OFFERED FOR A MEDIUM NOBODY HAS IDENTIFIED. Not the
          // destructive pair, which would act on an ownership nobody knows, and
          // not the follow, which would ask the machine to watch a title no
          // read has confirmed.
          inFlight ? <SkeletonLine width="half" /> : null
        ) : owns ? (
          <>
            <button
              className={`sact ${actionButton()}`}
              data-part="sheet/action"
              data-toast={t("screens.media.rescrapeToast")}
            >
              <Icon paths={icons.refresh} />
              {t("screens.media.rescrape")}
            </button>{" "}
            <button className={`sact danger ${actionButton()}`} data-part="sheet/action" data-tone="danger" data-del={title}>
              <Icon paths={icons.trash} />
              {t("screens.media.delete")}
            </button>
          </>
        ) : followed ? (
          <button className={`mediaadd done ${actionButton()}`} data-part="media/add" disabled>
            <Icon paths={icons.check} />
            {isFilm === false
              ? t("screens.media.followed")
              : isFilm
                ? t("screens.media.added")
                : t("screens.media.unknown")}
          </button>
        ) : (
          // No sheet-refresh attribute: the legacy button asked the sheet to
          // REOPEN itself so the label would flip under the finger. This
          // screen re-renders from the store instead — the follow act
          // bumps it, and the button becomes `mediaadd done` in place.
          <button
            className={`mediaadd ${actionButton()}`}
            data-part="media/add"
            data-follow={title}
            // french-ok: a data-* VALUE, frozen with the DOM contract
            data-fkind={isFilm ? "Film" : "Série"}
          >
            <Icon paths={icons.plus} />
            {isFilm === false
              ? t("screens.media.followVerb")
              : isFilm
                ? t("screens.media.add")
                : t("screens.media.unknown")}
          </button>
        )}
      </div>
    </>
  );
}
