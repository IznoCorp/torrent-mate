// design/src/screens/releases.tsx
// Legacy `openReleases(title)` (`refonte.html`) — "choose another release" —
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
// `data-mediasheet`/`data-panel`. `data-take` (pick this release) and
// `data-profile` (open the quality profile) carry NO onClick: the
// document-level click delegation the legacy engine still runs is the seam
// this screen leans on, exactly as `media.tsx` and `profile.tsx`.
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useReference } from "../data";

// Same helper as `media.tsx`'s, `profile.tsx`'s and `add.tsx`'s, still not
// shared: the extraction those files' comments call for is a follow-up of
// its own, not a silent scope add here.
function Icon({ paths, strokeWidth }: { paths: string; strokeWidth?: number }) {
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

export function ReleasesScreen() {
  const { title: raw } = useParams({ from: "/releases/$title" });
  // Defensive: `__screens.releases` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const title = raw.normalize("NFC");
  const { icons, baseTitle, RELEASES } = useReference();
  const { t } = useTranslation();

  return (
    <section
      className="screen open"
      data-part="screen"
      data-open=""
      data-key={`releases:${title}`}
      aria-label={title}
    >
      <div className="screenbar" data-part="screen/bar">
        <button className="fback" data-part="screen/back" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.releases.back")}
        </button>{" "}
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--muted-foreground)",
          }}
        >
          {baseTitle(title)}
        </span>
      </div>
      <div className="port" data-part="viewport">
        <div className="body" data-part="surface/body" data-region="screen-releases/body">
          <div className="note" data-part="note">
            <b>{t("screens.releases.noteTitle")}</b>{" "}
            {t("screens.releases.noteBeforePourquoi")}{" "}
            <em>{t("screens.releases.notePourquoi")}</em>{" "}
            {t("screens.releases.noteAfterPourquoi")}
          </div>
          <p className="rescount" data-part="result/count" style={{ padding: 0 }}>
            <b>{RELEASES.length}</b> {t("screens.releases.rescount")}
          </p>
          {RELEASES.map((release, index) => (
            <article
              className={`rel${index === 0 ? " best" : ""}`}
              data-part="release"
              key={release.n}
            >
              <span className="rn">{release.n}</span>{" "}
              <span className="rt">
                <span
                  className={`chip ${
                    release.res === "2160p"
                      ? "success"
                      : release.res === "1080p"
                        ? "info"
                        : "neutral"
                  }`}
                >
                  {release.res}
                </span>{" "}
                <span className="chip" data-part="chip">{release.src}</span>{" "}
                <span className="chip" data-part="chip">{release.lang}</span>{" "}
                <span className="chip" data-part="chip">
                  {release.s} {t("screens.releases.sourcesUnit")}
                </span>{" "}
                <span className="chip" data-part="chip">
                  {String(release.go).replace(".", ",")}{" "}
                  {t("screens.releases.goUnit")}
                </span>{" "}
                <span className="sc">
                  {t("screens.releases.scoreLabel")} {release.sc}
                </span>
              </span>{" "}
              {index === 0 ? (
                <p className="qhint">{t("screens.releases.qhint")}</p>
              ) : (
                ""
              )}
              <button
                className={`cfoot${index === 0 ? " solid" : ""}`}
                data-solid={index === 0 || undefined}
                data-part="card/foot"
                data-take={index}
              >
                {index === 0
                  ? t("screens.releases.pickCurrent")
                  : t("screens.releases.pickAlternative")}
              </button>
            </article>
          ))}
          <div className="empty" data-part="empty-state">
            <b>{t("screens.releases.emptyTitle")}</b>
            {t("screens.releases.emptyBody")}
            <button
              className="cfoot"
              data-part="card/foot"
              style={{ marginTop: "10px" }}
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
