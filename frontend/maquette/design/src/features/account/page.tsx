// design/src/pages/account.tsx
// « Profil et préférences » — the account surface the user menu points at. It
// draws what EXISTS: one identity, one session, and the way that session ends.
//
// THE CONNECTED ACCOUNT AND ITS PREFERENCES, for everyone (ruling 14): its
// role's NAME — shown, never compared (ruling 20) — what it can do and why not
// the rest, and its Plex link. The other accounts left for « Comptes ».
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import { useAccount, useRights } from "./queries";
import { RIGHTS, bypassesRights } from "../../lib/rights";
import type { ReactElement } from "react";
import { FactRows, type FactRow } from "../../ui/fact-rows";
import { actionButton, factList, guidance, sectionHeading } from "../../ui/variants";

export function AccountPage(): ReactElement | null {
  const { t } = useTranslation();
  // FROM THE CACHE (invariant 4).
  const { data: ACCOUNT } = useAccount();
  const rights = useRights();
  if (!ACCOUNT) return null;
  // WHAT THIS ACCOUNT CAN DO, from the model (R-L18-z): the rights held, then,
  // for each one lacking, the reason and who holds it by default — the same
  // sentences a reserved page says.
  const held = RIGHTS.filter((right) => rights.holds(right));
  const lacking = RIGHTS.filter((right) => !rights.holds(right));
  // THE CONFIGURATION'S ACCOUNT IS THE ADMIN'S: its name comes from
  // `web.username` and its address only notifies. Any other account is the
  // roster's — named in « Comptes », its address the one that links Plex — and
  // those two lines would be false for it (the reader's L18 round).
  const fromConfiguration = bypassesRights(ACCOUNT.role);
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
          ...(fromConfiguration ? { k: "web.username", secondaryLine: t("screens.accountPage.identifierSub") } : {}),
        },
        {
          label: t("screens.accountPage.address"),
          value: ACCOUNT.email,
          secondaryLine: fromConfiguration
            ? t("screens.accountPage.addressSub")
            : ACCOUNT.plexLinked ? t("screens.accountPage.addressPlexSub") : undefined,
        },
        {
          label: t("screens.accountPage.role"),
          value: ACCOUNT.role.name,
          secondaryLine: t("screens.accountPage.roleSub"),
          part: "profile/role",
        },
        {
          label: t("screens.accountPage.plex"),
          value: t(ACCOUNT.plexLinked ? "screens.accountPage.plexLinked" : "screens.accountPage.plexNotLinked"),
          part: "profile/plex",
        },
      ])}

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.can")}</h2>
      {/* A HELD RIGHT SAYS SO in its chip — never an empty « — » — and a
          role that holds none says « aucun » rather than an empty frame. */}
      {held.length ? facts(held.map((right) => ({
        label: t(`access.rights.${right}`),
        value: t("screens.accountPage.held"),
        tone: "success",
        part: "profile/right-held",
      }))) : <p className={guidance()} data-part="profile/no-right">{t("screens.accountPage.noRight")}</p>}
      {lacking.length ? (
        <>
          <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.cannot")}</h2>
          {facts(lacking.map((right) => ({
            label: t(`access.rights.${right}`),
            secondaryLine: rights.forbidden.includes(right)
              ? t("screens.accountPage.forbiddenHere")
              : t(`access.holders.${right}`),
            part: "profile/right-lacking",
          })))}
        </>
      ) : null}

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

    </>
  );
}
