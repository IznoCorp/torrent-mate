// « Comptes » — the accounts, their ONE role each, and the roles' rights
// (§ 17; ruling 14; round 8 Q9 = B: a first-level page of the menu, grouped
// with Réglages, opened by `accounts.manage`).
//
// EVERYTHING HERE IS THE ANSWER'S: one row per account the roster holds, its
// role by the name the server gives it — the Admin role named by its kind
// (gap G-10) — how it signs in, and one row per role. A tap opens the
// account's panel (its role) or the role's (its rights).
//
// A LINK THAT DEMOTED AN ACCOUNT IS SAID ON ITS ROW (the operator, 2026-10-03:
// « il perd son rôle et prend le rôle par défaut il devra être promu à nouveau
// par un Admin »; O-K1-4): the role it held before, until a role is given again.
//
// AN ADMIN CUTS AN ACCOUNT'S ACCESS FROM ITS ROW (the operator, 2026-10-04: « via
// un toggle qui par défaut est actif »): one switch per account, drawn for an
// Admin ONLY — « si on n'a pas le droit l'interface ne devrait pas permettre de
// le faire » — and greyed with its reason on the owner's row and the Admin's
// own (Q5 = A). A cut account is marked on its row, for whoever reads the roster.
//
// A CREATION OPENS ITS OWN PAGE (the operator, 2026-10-04: « dès qu'on a des
// créations dans ce genre il faut préférer une page et un formulaire avec
// validation plutôt que tout mettre en vrac sur une page »): « Nouveau compte »
// and « Nouveau rôle » are links to their pages, and create nothing here.
import type { ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { accountsQuery, roleLabel, useAccount } from "../../lib/account";
import { bypassesRights } from "../../lib/rights";
import { FactRows } from "../../ui/fact-rows";
import { Chip } from "../../ui/chip";
import { Switch } from "../../ui/switch";
import {
  actionButton, chip, factDetail, factList, factName, factRow, factRowBody, factValue, sectionHeading,
} from "../../ui/variants";
import type { Schemas } from "../../lib/contract-schemas";
import { accountBody } from "./variants";
import { PART } from "./roster-panels";

export function AccountsPage(): ReactElement | null {
  const { t } = useTranslation();
  const { data: roster } = useQuery(accountsQuery);
  const { data: viewer } = useAccount();
  if (!roster) return null;
  return (
    <>
      <h2 className={sectionHeading()} data-part="heading">{t("screens.accounts.accounts")}</h2>
      <ol className={factList()} data-part="flux">
        {roster.accounts.map((account) => <AccountRow key={account.id} account={account} viewer={viewer} />)}
      </ol>
      <button className={actionButton({ kind: "cardFoot" })} data-part="accounts/account-create" data-account-create="">
        {t("screens.accounts.newAccount")}
      </button>

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accounts.roles")}</h2>
      <ol className={factList()} data-part="flux">
        <FactRows rows={roster.roles.map((role) => ({
          label: roleLabel(role),
          value: bypassesRights(role) ? t("screens.accounts.bypass") : t("screens.accounts.roleCount", { count: role.rights.length }),
          target: { panel: `role:${role.id}` },
          part: "accounts/role",
        }))} />
      </ol>
      <button className={actionButton({ kind: "cardFoot" })} data-part="accounts/role-create" data-role-create="">
        {t("screens.accounts.newRole")}
      </button>
    </>
  );
}

/** Why an account's switch is greyed, if it is: the owner's door, or the Admin's own account. */
type Locked = "owner" | "own" | null;

/**
 * One account's row: its summary, which opens its panel, and — for an Admin —
 * the switch that allows or cuts its sign-in.
 *
 * @param props.account The account, as the roster answers it.
 * @param props.viewer The signed-in account, once read.
 * @returns The row.
 */
function AccountRow({ account, viewer }: {
  account: Schemas["AccountSummary"];
  viewer: Schemas["Account"] | undefined;
}): ReactElement {
  const { t } = useTranslation();
  const admin = viewer !== undefined && bypassesRights(viewer.role);
  const locked: Locked = account.signInKind === "owner" ? "owner" : account.id === viewer?.id ? "own" : null;
  const cut = !account.signInAllowed;
  const role = roleLabel(account.role);
  return (
    <li className={factRow({ withTarget: true, withControl: admin })} data-part="accounts/account"
      data-account={account.id} data-access={cut ? "off" : "on"}>
      <button className={`${factRowBody({ withTarget: true })} ${accountBody({ cut })}`} data-part="flux/row-body"
        data-panel={`roster:${account.id}`}>
        <span className={factName()} data-part="flux/name">{account.name}</span>
        <span className={factValue()} data-part="flux/value">
          {account.demotedFrom !== undefined ? <Chip tone="warning" label={role} /> : role}
        </span>
        <span className={factDetail()} data-part="flux/detail">
          {[
            account.email,
            t(`screens.accounts.signInKind.${account.signInKind}`),
            account.demotedFrom !== undefined ? t("screens.accounts.demotedShort") : null,
          ].filter(Boolean).join(" · ")}
        </span>
        {cut ? (
          <span className={factDetail()}>
            <span className={chip({ tone: "danger" })} data-part="accounts/cut" data-tone="danger">
              {t("screens.accounts.access.cut")}
            </span>
          </span>
        ) : null}
        {admin && locked !== null ? (
          <span className={factDetail()} data-part="accounts/access-locked" data-reason={locked}>
            {t(locked === "owner" ? "screens.accounts.access.lockedOwner" : "screens.accounts.access.lockedOwn")}
          </span>
        ) : null}
      </button>
      {/* ADMIN ONLY: a viewer without the right sees no switch at all, never one it cannot use. */}
      {admin ? (
        <Switch checked={!cut} label={t("screens.accounts.access.switch", { name: account.name })}
          disabled={locked !== null} data-part="accounts/access"
          data-account-access={[account.id, String(cut)].join(PART)} />
      ) : null}
    </li>
  );
}
