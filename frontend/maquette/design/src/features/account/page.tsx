// design/src/pages/account.tsx
// « Profil et préférences » — the account surface the user menu points at. It
// draws what EXISTS: one identity, one session, and the way that session ends.
//
// The place of other accounts is marked and EMPTY. Filling it with invented
// colleagues would teach a reader to distrust the rest of the interface, and
// the shape is settled here so the feature does not have to teach its own form
// twice when it arrives.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useAccountReference } from "../../features/account/reference";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { actionButton, emptyNote, sectionHeading } from "../../ui/variants";

export function AccountPage(): ReactElement {
  const { t } = useTranslation();
  const { ACCOUNT } = useAccountReference();
  const { factRowsHTML, emptyInner } = useEngineDrawing();
  const facts = (rows: Parameters<typeof factRowsHTML>[0]) => (
    <ol
      className="flux" data-part="flux"
      dangerouslySetInnerHTML={{ __html: factRowsHTML(rows) }}
    />
  );
  return (
    <>
      <div className="note" data-part="note">
        <b>{t("screens.accountPage.noteLead")}</b>
        {t("screens.accountPage.noteRest")}
      </div>

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.you")}</h2>
      {facts([
        {
          l: t("screens.accountPage.identifier"),
          v: ACCOUNT.name,
          k: "web.username",
          s: t("screens.accountPage.identifierSub"),
        },
        {
          l: t("screens.accountPage.address"),
          v: ACCOUNT.mail,
          s: t("screens.accountPage.addressSub"),
        },
      ])}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.session")}</h2>
      {facts([
        {
          l: t("screens.accountPage.duration"),
          v: t("screens.accountPage.durationValue"),
          k: "web.session_ttl_hours",
          s: t("screens.accountPage.durationSub"),
        },
        {
          l: t("screens.accountPage.transport"),
          v: t("screens.accountPage.transportValue"),
          k: "web.cookie_secure",
          s: t("screens.accountPage.transportSub"),
        },
        {
          l: t("screens.accountPage.where"),
          v: t("screens.accountPage.whereValue"),
          s: t("screens.accountPage.whereSub"),
        },
      ])}
      <button className={`cfoot ${actionButton()}`} data-part="card/foot" data-signout="1">
        {t("screens.accountPage.signOut")}
      </button>

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.others")}</h2>
      <div
        className={emptyNote()} data-part="empty-state"
        dangerouslySetInnerHTML={{
          __html: emptyInner(
            t("screens.accountPage.othersEmptyTitle"),
            t("screens.accountPage.othersEmptyBody"),
          ),
        }}
      />
    </>
  );
}
