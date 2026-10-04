// « Application », in Profil — the way to install the app by hand, and the way to update it once installed.
//
// The operator, 2026-10-04: the install is PROPOSED once, right after the first sign-in; this is the door
// for whoever dismissed the proposal or never saw it, and it is hidden when the app already runs installed.
// ONE BUTTON, THREE FACES (`app/install-state.ts` says which):
//   « Installer l'app » on a browser that fired its install prompt — it fires it;
//   « Installer l'app » on iOS Safari, which has no prompt to fire — it shows the way: Partager, then
//   Sur l'écran d'accueil;
//   « Mettre à jour » once the app is installed and a newer version waits — it applies it.
// Where there is nothing to do — a browser that offers no install, an app up to date — there is no
// section at all.
import { useState, useSyncExternalStore, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { applyUpdate, installFace, promptInstall, subscribeInstall } from "../../app/install-state";
import { toast } from "../../lib/shell-doors";
import { actionButton, factsPanel, guidance, keyValueRow, qualityHint, sectionHeading, settingRow } from "../../ui/variants";

/** The steps of the manual route, in order: the keys under `screens.accountPage.install.steps`. */
const STEPS = ["share", "addToHome", "confirm"] as const;

/**
 * The « Application » section, or nothing where there is nothing to install or update.
 *
 * @returns The section.
 */
export function InstallSection(): ReactElement | null {
  const { t } = useTranslation();
  const face = useSyncExternalStore(subscribeInstall, installFace, () => "none" as const);
  const [showSteps, setShowSteps] = useState(false);
  if (face === "none") return null;
  const words = "screens.accountPage.install";

  async function install(): Promise<void> {
    // FIRED FROM THE PRESS: a browser accepts its prompt on a gesture only, and once.
    const choice = await promptInstall();
    toast?.show({
      message: t(
        choice === "accepted" ? "message.installing" : choice === "dismissed" ? "message.installRefused" : "message.installRequested",
      ),
    });
  }

  const press = face === "install" ? () => void install() : face === "ios" ? () => setShowSteps((open) => !open) : applyUpdate;
  return (
    <section data-part="profile/install" data-face={face}>
      <h2 className={sectionHeading()} data-part="heading">{t(`${words}.heading`)}</h2>
      <div className={factsPanel()} data-part="panel">
        <div className={`${keyValueRow()} ${settingRow()}`} data-part="key-value">
          <div className="min-w-0">
            <div className="font-semibold">{t(`${words}.${face}.label`)}</div>
            <div className={qualityHint()}>{t(`${words}.${face}.line`)}</div>
          </div>
          <button className={actionButton({ kind: "panelAction" })} data-part="profile/install-action"
            aria-expanded={face === "ios" ? showSteps : undefined} onClick={press}>
            {t(`${words}.${face}.action`)}
          </button>
        </div>
      </div>
      {face === "ios" && showSteps ? (
        <ol className={guidance()} data-part="profile/install-steps">
          {STEPS.map((step) => <li key={step}>{t(`${words}.steps.${step}`)}</li>)}
        </ol>
      ) : null}
    </section>
  );
}
