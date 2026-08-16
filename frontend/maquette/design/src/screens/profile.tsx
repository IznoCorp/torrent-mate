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
import {
  writeUiState,
  useUiState,
  useReference,
  type Release,
  type Resolution,
} from "../data";

// The field names are the legacy state's own — `state.profil` is written and
// read by the engine under these exact keys.
type QualityProfile = {
  min_resolution: Resolution | null;
  required_audio: string[];
  exclude_3d: boolean;
  require_known_resolution: boolean;
};

// The exact shape `svgIcon(paths, strokeWidth)` produced as an HTML string —
// rebuilt as a real element so it composes with JSX, `paths` is still the
// SAME raw markup from `useReference().icons`, injected verbatim (trusted:
// it is a fixed set of `<path>`/`<circle>` primitives defined in
// refonte.html, never user input).
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

export function ProfileScreen() {
  const { titre: raw } = useParams({ from: "/profil/$titre" });
  // Defensive: `__ecrans.profil` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const title = raw.normalize("NFC");
  const state = useUiState();
  const profile = state.profil as QualityProfile;
  const { RELEASES, RESOS, AUDIOS, icons, baseTitle } = useReference();
  const { t } = useTranslation();
  const kept = countKept(profile, RELEASES);

  function writeProfile(patch: Partial<QualityProfile>): void {
    writeUiState({ profil: { ...profile, ...patch } });
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
    <section className="screen open" data-cle={`profil:${title}`}>
      <div className="fichebar">
        <button className="fback" onClick={() => window.__pont.retour()}>
          <Icon paths={icons.left} />
          {t("screens.profil.back")}
        </button>
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--muted-foreground)",
          }}
        >
          {title ? baseTitle(title) : t("screens.profil.defaultProfile")}
        </span>
      </div>
      <div className="port">
        <div className="body">
          <div className="note">
            <b>{t("screens.profil.noteTitle")}</b>{" "}
            {t("screens.profil.noteBefore")}{" "}
            <em>{t("screens.profil.noteEmphasis")}</em>{" "}
            {t("screens.profil.noteAfterEmphasis")} <code>QualityProfile</code>{" "}
            {t("screens.profil.noteAfterCode")}{" "}
            <code>/config ?tab=classement</code>.
          </div>

          <p className="qhint">
            {t("screens.profil.leadBefore")}{" "}
            <b>{t("screens.profil.leadEmphasis")}</b>{" "}
            {t("screens.profil.leadAfter")}
          </p>

          <div className="qgroup">
            <h2 className="h2">{t("screens.profil.minResolution")}</h2>
            <p className="qhint">{t("screens.profil.minResolutionHint")}</p>
            <p className="optkind">{t("screens.profil.singleChoice")}</p>
            <div
              className="optlist"
              role="radiogroup"
              aria-label={t("screens.profil.minResolution")}
            >
              <button
                className="opt radio"
                role="radio"
                aria-checked={profile.min_resolution === null}
                data-qres=""
                onClick={() => pickResolution(null)}
              >
                <span className="mark" />
                <span className="lb">
                  {t("screens.profil.noFloor")}
                  <small>{t("screens.profil.noFloorHint")}</small>
                </span>
              </button>
              {RESOS.map((reso) => (
                <button
                  key={reso}
                  className="opt radio"
                  role="radio"
                  aria-checked={profile.min_resolution === reso}
                  data-qres={reso}
                  onClick={() => pickResolution(reso)}
                >
                  <span className="mark" />
                  <span className="lb">
                    {reso} {t("screens.profil.orBetter")}
                    <small>
                      {reso === "720p"
                        ? t("screens.profil.hint720")
                        : reso === "1080p"
                          ? t("screens.profil.hint1080")
                          : t("screens.profil.hint2160")}
                    </small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="qgroup">
            <h2 className="h2">{t("screens.profil.audioTracks")}</h2>
            <p className="qhint">
              {t("screens.profil.audioHintBefore")}{" "}
              <b>{t("screens.profil.audioHintEmphasis")}</b>{" "}
              {t("screens.profil.audioHintAfter")}
            </p>
            <p className="optkind">
              {t("screens.profil.multiChoice")}
              {profile.required_audio.length === 0
                ? ` — ${t("screens.profil.noneChecked")}`
                : ""}
            </p>
            <div className="optlist">
              {AUDIOS.map(([key, label]) => (
                <button
                  key={key}
                  className="opt check"
                  role="checkbox"
                  aria-checked={profile.required_audio.includes(key)}
                  data-qaud={key}
                  onClick={() => toggleAudio(key)}
                >
                  <span className="mark" />
                  <span className="lb">
                    {key}
                    <small>{label}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="qgroup">
            <h2 className="h2">{t("screens.profil.twoLocks")}</h2>
            <div className="panel">
              <div className="kv reglage">
                <span>
                  {t("screens.profil.exclude3d")}
                  <br />
                  <span className="qhint">
                    {t("screens.profil.exclude3dHint")}
                  </span>
                </span>
                <button
                  className="switch"
                  role="switch"
                  aria-checked={profile.exclude_3d}
                  aria-label={t("screens.profil.exclude3d")}
                  data-qflag="exclude_3d"
                  onClick={() => toggleLock("exclude_3d")}
                />
              </div>
              <div className="kv reglage">
                <span>
                  {t("screens.profil.requireKnownResolution")}
                  <br />
                  <span className="qhint">
                    {t("screens.profil.requireKnownResolutionHint")}
                  </span>
                </span>
                <button
                  className="switch"
                  role="switch"
                  aria-checked={profile.require_known_resolution}
                  aria-label={t("screens.profil.requireKnownResolution")}
                  data-qflag="require_known_resolution"
                  onClick={() => toggleLock("require_known_resolution")}
                />
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="kv">
              <span>{t("screens.profil.candidatesKept")}</span>
              <span>
                {kept} {t("screens.profil.outOf")} {RELEASES.length}
              </span>
            </div>
            <div className="kv">
              <span>{t("screens.profil.scope")}</span>
              <span>
                {title
                  ? t("screens.profil.scopeThisFollow")
                  : t("screens.profil.scopeAllFollows")}
              </span>
            </div>
          </div>

          <button
            className="cfoot"
            data-toast={t("screens.profil.rankingToast")}
          >
            <Icon paths={icons.sort} />
            {t("screens.profil.rankingWeights")}
          </button>

          <p className="rulenote">{t("screens.profil.rulenote")}</p>

          <div className="sheetacts">
            <button
              className="sact primary"
              data-toast={t("screens.profil.saveToast")}
            >
              <Icon paths={icons.check} />
              {t("screens.profil.save")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
