// design/src/screens/releases.tsx
// Legacy `openReleases(title)` (`refonte.html@60530dbd8`) — "choose another release" —
// reborn as a real route (`/releases/$title`) and a final component. Markup
// is TRANSPLANTED, not translated: every tag, class and data-attribute below
// is the one the legacy screen drew, so the same stylesheet applies
// unchanged. `data-key="releases:" + titre` is an identity this screen never
// had — the legacy `openScreen(html, undefined, () => openReleases(titre))`
// passed no `cle` at all — added here because a router-owned screen needs one
// to answer `.screen.open[data-key^="releases:"]` the way every other
// migrated screen already does (see `shell.tsx`'s dispatcher rewrite).
//
// The `.rel` rows are release CANDIDATES, not media cards — no poster, no
// `data-mediasheet`/`data-panel`. `data-pick-release` (pick this release) and
// `data-profile` (open the quality profile) carry NO onClick: the
// document-level click delegation the legacy engine still runs is the seam
// this screen leans on, exactly as `media.tsx` and `profile.tsx`.
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useReleases } from "./queries";
import { actionButton, backAction, body, chip, emptyNote, qualityHint, resultCount, screen, screenBar, scrollport, screenBarNote } from "../../ui/variants";
import { releaseName, releaseRow, releaseScore, releaseTags } from "../../features/releases/variants";
import { Icon } from "../../ui/icon";
import { bridge } from "../../lib/shell-doors";
import { baseTitle } from "../../lib/titles";
import { useAcquisitionQueue } from "../../lib/queue";
import { useStoreContent } from "../../lib/store-access";
import { acquisitionKey, liveCards, tabHolding } from "../../lib/arrival-slots";

// A release's name, where it names one episode: « Silo.S03E07.… ».
const EPISODE_IN_NAME = /(?:^|[.\s_-])S(\d{1,3})E\d{1,3}(?:[.\s_-]|$)/i;

/**
 * The whole-season recoveries live for one title — a series' alone: a film has
 * no season, and its release list is never refused.
 *
 * @param title The medium.
 * @returns Each season recovered, with the dial that lands on its card.
 */
function useSeasonsRecovered(title: string): Map<number, string> {
  const scenario = useStoreContent((content) => (content.state.scen === "loaded" ? "loaded" : ""));
  const { data: queue } = useAcquisitionQueue(scenario);
  const recovered = new Map<number, string>();
  if (queue === undefined) return recovered;
  for (const card of liveCards(queue)) {
    if (card.title !== title || card.season == null || card.episode != null) continue;
    const key = acquisitionKey(card);
    recovered.set(card.season, `${tabHolding(queue, key) ?? "now"}:${key}`);
  }
  return recovered;
}

/**
 * The season a release covers ONE episode of, when its name says so. The
 * release list is the one answer that carries no season field — its name is
 * the release, and the demand register asks the engine for the fields.
 *
 * @param name The release's name.
 * @returns The season, or null for a pack, a film, or a name naming none.
 */
function episodeSeason(name: string): number | null {
  const found = EPISODE_IN_NAME.exec(name);
  return found ? Number(found[1]) : null;
}

export function ReleasesScreen() {
  const { title: raw } = useParams({ from: "/releases/$title" });
  // Defensive: `__screens.releases` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const title = raw.normalize("NFC");
  const {
    icons,
  } = useEngineDrawing();
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4).
  const { data: RELEASES = [] } = useReleases(baseTitle(title));
  // WHILE A WHOLE SEASON IS RECOVERED, its episodes are not taken alone (17:36:
  // « aucun téléchargement d'épisode de la saison … en parallèle »): each release
  // of one of them keeps its row, and says why it cannot be taken — VISIBLE, never
  // quietly left out (DOIT-2, DOIT-12). A pack keeps its act.
  const recovered = useSeasonsRecovered(baseTitle(title));
  const coveredBy = (name: string) => {
    const season = episodeSeason(name);
    return season !== null && recovered.has(season) ? season : null;
  };
  const covered = RELEASES.map((release) => coveredBy(release.name));
  const allCovered = RELEASES.length > 0 && covered.every((season) => season !== null && season === covered[0]);

  return (
    <section
      className={screen({ open: true })}
      data-part="screen"
      data-open=""
      data-key={`releases:${title}`}
      aria-label={title}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.releases.back")}
        </button>{" "}
        <span className={screenBarNote()}>
          {baseTitle(title)}
        </span>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="surface/body" data-region="screen-releases/body">
          <div className="note" data-part="note">
            <b>{t("screens.releases.noteTitle")}</b>{" "}
            {t("screens.releases.noteBeforePourquoi")}{" "}
            <em>{t("screens.releases.notePourquoi")}</em>{" "}
            {t("screens.releases.noteAfterPourquoi")}
          </div>
          <p className={resultCount({ flush: true })} data-part="result/count">
            <b>{RELEASES.length}</b>{" "}
            {/* THE COUNT'S OWN FORM: « 1 candidat retenu », never « 1 candidats ». */}
            {allCovered
              ? t("screens.releases.allCovered", { season: covered[0], count: RELEASES.length })
              : t("screens.releases.rescount", { count: RELEASES.length })}
          </p>
          {RELEASES.map((release, index) => (
            <article
              className={releaseRow({ best: index === 0 })}
              data-part="release"
              key={release.name}
            >
              <span className={releaseName()}>{release.name}</span>{" "}
              <span className={releaseTags()}>
                <span
                  className={chip({
                    tone:
                      release.resolution === "2160p"
                        ? "success"
                        : release.resolution === "1080p"
                          ? "info"
                          : "neutral",
                  })}
                >
                  {release.resolution}
                </span>{" "}
                <span className={chip()} data-part="chip">{release.source}</span>{" "}
                <span className={chip()} data-part="chip">{release.language}</span>{" "}
                <span className={chip()} data-part="chip">
                  {release.seeders} {t("screens.releases.sourcesUnit")}
                </span>{" "}
                <span className={chip()} data-part="chip">
                  {String(release.sizeGigabytes).replace(".", ",")}{" "}
                  {t("screens.releases.goUnit")}
                </span>{" "}
                <span className={releaseScore()}>
                  {t("screens.releases.scoreLabel")} {release.score}
                </span>
              </span>{" "}
              {/* « Retenue » is never said of a release the recovery covers. */}
              {index === 0 && covered[index] === null ? (
                <p className={qualityHint()}>{t("screens.releases.qhint")}</p>
              ) : (
                ""
              )}
              {covered[index] !== null ? (
                <>
                  <span className={releaseTags()}>
                    <span className={chip({ tone: "info" })} data-tone="info" data-part="release/covered">
                      {t("screens.releases.coveredBySeason", { season: covered[index] })}
                    </span>
                  </span>{" "}
                  <button
                    className={actionButton({ kind: "cardFoot" })}
                    data-part="card/foot"
                    data-go="acq"
                    data-dial={recovered.get(covered[index] ?? 0)}
                  >
                    {t("panels.journey.seeSeasonCard")}
                  </button>
                </>
              ) : <button
                className={actionButton({ kind: "cardFoot", tone: index === 0 ? "solid" : "plain" })}
                data-solid={index === 0 || undefined}
                data-part="card/foot"
                data-pick-release={index}
              >
                {index === 0
                  ? t("screens.releases.pickCurrent")
                  : t("screens.releases.pickAlternative")}
              </button>}
            </article>
          ))}
          <div className={emptyNote()} data-part="empty-state">
            <b>{t("screens.releases.emptyTitle")}</b>
            {t("screens.releases.emptyBody")}
            <button
              className={`${actionButton({ kind: "cardFoot" })} mt-5`}
              data-part="card/foot"
              data-profile={title}
            >
              {t("screens.releases.openProfile")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
