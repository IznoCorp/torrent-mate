// design/src/pages/account.tsx
// « Profil et préférences » — the account surface the user menu points at. It
// draws what EXISTS: one identity, one session, and the way that session ends.
//
// The place of other accounts is marked and EMPTY. Filling it with invented
// colleagues would teach a reader to distrust the rest of the interface, and
// the shape is settled here so the feature does not have to teach its own form
// twice when it arrives.
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import { useAccount } from "./queries";
import type { ReactElement } from "react";
import { FactRows, type FactRow } from "../../ui/fact-rows";
import { actionButton, emptyNote, factList, sectionHeading } from "../../ui/variants";
import { Markup, emptyNoteMarkup } from "../../ui/markup";

export function AccountPage(): ReactElement | null {
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4).
  const { data: ACCOUNT } = useAccount();
  if (!ACCOUNT) return null;
  const facts = (rows: FactRow[]) => (
    <ol className={factList()} data-part="flux">
      <FactRows rows={rows} />
    </ol>
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
          label: t("screens.accountPage.identifier"),
          value: ACCOUNT.name,
          k: "web.username",
          secondaryLine: t("screens.accountPage.identifierSub"),
        },
        {
          label: t("screens.accountPage.address"),
          value: ACCOUNT.email,
          secondaryLine: t("screens.accountPage.addressSub"),
        },
      ])}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.session")}</h2>
      {facts([
        {
          label: t("screens.accountPage.duration"),
          value: t("screens.accountPage.durationValue"),
          k: "web.session_ttl_hours",
          secondaryLine: t("screens.accountPage.durationSub"),
        },
        {
          label: t("screens.accountPage.transport"),
          value: t("screens.accountPage.transportValue"),
          k: "web.cookie_secure",
          secondaryLine: t("screens.accountPage.transportSub"),
        },
        {
          label: t("screens.accountPage.where"),
          value: t("screens.accountPage.whereValue"),
          secondaryLine: t("screens.accountPage.whereSub"),
        },
      ])}
      <button className={actionButton({ kind: "cardFoot" })} data-part="card/foot" data-signout="1">
        {t("screens.accountPage.signOut")}
      </button>

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.others")}</h2>
      <Markup
        className={emptyNote()} data-part="empty-state"
        html={emptyNoteMarkup(
            t("screens.accountPage.othersEmptyTitle"),
            t("screens.accountPage.othersEmptyBody"),
          )}
      />
    </>
  );
}
