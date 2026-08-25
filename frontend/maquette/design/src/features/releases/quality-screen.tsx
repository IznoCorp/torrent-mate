// design/src/screens/profile.tsx
// The pilot screen: legacy `openProfil(titre)` (the per-title quality-profile
// screen — resolution floor, required audio, two locks; NOT the account page
// at `?page=profil`, which stays legacy) reborn as a real route and a final
// component. Markup is TRANSPLANTED, not translated: every tag and class
// below is the one `refonte.html`'s BLOCK 2 CSS already targets
// (`.screen`, `.screen.open`, `.screen .port`, `.qgroup`, `.opt`, …), so the
// same stylesheet applies unchanged and the rule harness measures the same
// geometry it measured on the legacy `#screen`.
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Icon } from "../../ui/icon";
import { useReleasesReference, type Release, type Resolution } from "../../features/releases/reference";
import { useUiState, writeUiState } from "../../lib/store-access";
import { actionButton, backAction, body, factsPanel, keyValueRow, option, optionKind, optionLabel, optionList, optionMark, qualityHint, ruleNote, screen, screenBar, sectionHeading, settingRow, sheetActions, toggleSwitch } from "../../ui/variants";
import { qualityGroup } from "../../features/releases/variants";

// The field names are the legacy state's own — `state.profil` is written and
// read by the engine under these exact keys.
type QualityProfile = {
  min_resolution: Resolution | null;
  required_audio: string[];
  exclude_3d: boolean;
  require_known_resolution: boolean;
};

// `retenus`: transplanted verbatim from `openProfil` — the SAME filter over
// the SAME mock release list, so the count on screen matches what the
// legacy screen showed for the same profile.
function countKept(profile: QualityProfile, releases: Release[]): number {
  const order: Record<string, number> = { "720p": 0, "1080p": 1, "2160p": 2 };
  return releases.filter((release) => {
    if (
      profile.min_resolution &&
      order[release.res] < order[profile.min_resolution]
    )
      return false;
    if (profile.required_audio.length) {
      const tier =
        release.lang === "VOSTFR"
          ? "VOSTFR"
          : release.lang === "VO"
            ? "VO"
            : "VF";
      if (!profile.required_audio.includes(tier)) return false;
    }
    return true;
  }).length;
}

export function QualityScreen() {
  const { name: raw } = useParams({ from: "/quality/$name" });
  // Defensive: `__screens.profil` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const title = raw.normalize("NFC");
  const state = useUiState();
  const profile = state.profile as QualityProfile;
  const {
    RELEASES,
    RESOLUTIONS,
    AUDIOS,
    icons,
    baseTitle,
  } = useReleasesReference();
  const { t } = useTranslation();
  const kept = countKept(profile, RELEASES);

  function writeProfile(patch: Partial<QualityProfile>): void {
    writeUiState({ profile: { ...profile, ...patch } });
  }

  function pickResolution(reso: Resolution | null): void {
    writeProfile({ min_resolution: reso });
  }

  function toggleAudio(key: string): void {
    const required = profile.required_audio.includes(key)
      ? profile.required_audio.filter((value) => value !== key)
      : [...profile.required_audio, key];
    writeProfile({ required_audio: required });
  }

  function toggleLock(key: "exclude_3d" | "require_known_resolution"): void {
    writeProfile({ [key]: !profile[key] });
  }

  return (
    <section
      className={`${screen()} open`}
      data-part="screen"
      data-open=""
      data-key={`profile:${title}`}
      aria-label={title}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.profile.back")}
        </button>
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--color-muted-foreground)",
          }}
        >
          {title ? baseTitle(title) : t("screens.profile.defaultProfile")}
        </span>
      </div>
      <div className="port" data-part="viewport">
        <div className={body()} data-part="surface/body" data-region="screen-profile/body">
          <div className="note" data-part="note">
            <b>{t("screens.profile.noteTitle")}</b>{" "}
            {t("screens.profile.noteBefore")}{" "}
            <em>{t("screens.profile.noteEmphasis")}</em>{" "}
            {t("screens.profile.noteAfterEmphasis")} <code>QualityProfile</code>{" "}
            {t("screens.profile.noteAfterCode")}{" "}
            <code>/config ?tab=classement</code>.
          </div>

          <p className={qualityHint()}>
            {t("screens.profile.leadBefore")}{" "}
            <b>{t("screens.profile.leadEmphasis")}</b>{" "}
            {t("screens.profile.leadAfter")}
          </p>

          <div className={qualityGroup()}>
            <h2 className={sectionHeading()} data-part="heading">{t("screens.profile.minResolution")}</h2>
            <p className={qualityHint()}>{t("screens.profile.minResolutionHint")}</p>
            <p className={optionKind()}>{t("screens.profile.singleChoice")}</p>
            <div
              className={optionList()}
              data-part="option/list"
              role="radiogroup"
              aria-label={t("screens.profile.minResolution")}
            >
              <button
                className={`${option()} radio`}
                data-part="option"
                role="radio"
                aria-checked={profile.min_resolution === null}
                data-qres=""
                onClick={() => pickResolution(null)}
              >
                <span className={optionMark({ kind: "radio" })} />
                <span className={optionLabel()}>
                  {t("screens.profile.noFloor")}
                  <small>{t("screens.profile.noFloorHint")}</small>
                </span>
              </button>
              {RESOLUTIONS.map((reso) => (
                <button
                  key={reso}
                  className={`${option()} radio`}
                  data-part="option"
                  role="radio"
                  aria-checked={profile.min_resolution === reso}
                  data-qres={reso}
                  onClick={() => pickResolution(reso)}
                >
                  <span className={optionMark({ kind: "radio" })} />
                  <span className={optionLabel()}>
                    {reso} {t("screens.profile.orBetter")}
                    <small>
                      {reso === "720p"
                        ? t("screens.profile.hint720")
                        : reso === "1080p"
                          ? t("screens.profile.hint1080")
                          : t("screens.profile.hint2160")}
                    </small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className={qualityGroup()}>
            <h2 className={sectionHeading()} data-part="heading">{t("screens.profile.audioTracks")}</h2>
            <p className={qualityHint()}>
              {t("screens.profile.audioHintBefore")}{" "}
              <b>{t("screens.profile.audioHintEmphasis")}</b>{" "}
              {t("screens.profile.audioHintAfter")}
            </p>
            <p className={optionKind()}>
              {t("screens.profile.multiChoice")}
              {profile.required_audio.length === 0
                ? ` — ${t("screens.profile.noneChecked")}`
                : ""}
            </p>
            <div className={optionList()} data-part="option/list">
              {AUDIOS.map(([key, label]) => (
                <button
                  key={key}
                  className={`${option()} check`}
                  data-part="option"
                  role="checkbox"
                  aria-checked={profile.required_audio.includes(key)}
                  data-qaud={key}
                  onClick={() => toggleAudio(key)}
                >
                  <span className={optionMark({ kind: "check" })} />
                  <span className={optionLabel()}>
                    {key}
                    <small>{label}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className={qualityGroup()}>
            <h2 className={sectionHeading()} data-part="heading">{t("screens.profile.twoLocks")}</h2>
            <div className={factsPanel()} data-part="panel">
              <div className={`${keyValueRow()} ${settingRow()}`} data-part="key-value">
                <span>
                  {t("screens.profile.exclude3d")}
                  <br />
                  <span className={qualityHint()}>
                    {t("screens.profile.exclude3dHint")}
                  </span>
                </span>
                <button
                  className={toggleSwitch()}
                  data-part="switch"
                  role="switch"
                  aria-checked={profile.exclude_3d}
                  aria-label={t("screens.profile.exclude3d")}
                  data-qflag="exclude_3d"
                  onClick={() => toggleLock("exclude_3d")}
                />
              </div>
              <div className={`${keyValueRow()} ${settingRow()}`} data-part="key-value">
                <span>
                  {t("screens.profile.requireKnownResolution")}
                  <br />
                  <span className={qualityHint()}>
                    {t("screens.profile.requireKnownResolutionHint")}
                  </span>
                </span>
                <button
                  className={toggleSwitch()}
                  data-part="switch"
                  role="switch"
                  aria-checked={profile.require_known_resolution}
                  aria-label={t("screens.profile.requireKnownResolution")}
                  data-qflag="require_known_resolution"
                  onClick={() => toggleLock("require_known_resolution")}
                />
              </div>
            </div>
          </div>

          <div className={factsPanel()} data-part="panel">
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.profile.candidatesKept")}</span>
              <span>
                {kept} {t("screens.profile.outOf")} {RELEASES.length}
              </span>
            </div>
            <div className={keyValueRow()} data-part="key-value">
              <span>{t("screens.profile.scope")}</span>
              <span>
                {title
                  ? t("screens.profile.scopeThisFollow")
                  : t("screens.profile.scopeAllFollows")}
              </span>
            </div>
          </div>

          <button
            className={`cfoot ${actionButton()}`}
            data-part="card/foot"
            data-toast={t("screens.profile.rankingToast")}
          >
            <Icon paths={icons.sort} />
            {t("screens.profile.rankingWeights")}
          </button>

          <p className={ruleNote()}>{t("screens.profile.rulenote")}</p>

          <div className={sheetActions()} data-part="sheet/actions">
            <button
              className={`sact primary ${actionButton()}`}
              data-part="sheet/action"
              data-tone="primary"
              data-toast={t("screens.profile.saveToast")}
            >
              <Icon paths={icons.check} />
              {t("screens.profile.save")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
