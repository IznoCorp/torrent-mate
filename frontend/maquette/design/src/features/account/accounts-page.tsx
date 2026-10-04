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
import { useState } from "react";
import type { FormEvent, ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { accountsQuery, roleLabel, useAccount } from "../../lib/account";
import { refusalWords } from "../../lib/refusal";
import { bypassesRights } from "../../lib/rights";
import { FactRows } from "../../ui/fact-rows";
import { Chip } from "../../ui/chip";
import { Switch } from "../../ui/switch";
import {
  actionButton, chip, factDetail, factList, factName, factRow, factRowBody, factValue, guidance, sectionHeading, surfaceError,
} from "../../ui/variants";
import type { Schemas } from "../../lib/contract-schemas";
import { sendNow } from "./send-now";
import { accountBody, accountField, accountForm } from "./variants";
import { PART, withinReach } from "./roster-panels";

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

      <NewAccount roles={roster.roles.filter((role) => !bypassesRights(role))} />
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

/**
 * The creation form: a name, a MANDATORY e-mail, an initial role (demand G),
 * and a local account's PROVISIONAL password (the operator, 2026-10-03: « A ») —
 * sent now or not at all (`send-now.ts`), ignored by the server for an e-mail
 * it links to Plex.
 *
 * @param roles The roles an account may be created on — never Admin here.
 */
function NewAccount({ roles }: { roles: Schemas["Role"][] }): ReactElement {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data: manager } = useAccount();
  const [refusal, setRefusal] = useState<string | null>(null);

  async function create(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const email = String(fields.get("email") ?? "").trim();
    // THE E-MAIL IS MANDATORY: said before anything is asked.
    if (!email.includes("@")) {
      setRefusal(t("screens.accounts.emailRequired"));
      return;
    }
    const problem = await sendNow("POST", "/api/v1/accounts", {
      name: String(fields.get("name") ?? "").trim(),
      email,
      role: String(fields.get("role") ?? ""),
      password: String(fields.get("password") ?? ""),
    });
    if (problem !== null) {
      // A REFUSAL SAYS WHY, in `fr.json`'s words for its code (gap G-1).
      setRefusal(refusalWords(problem, "screens.accounts.createRefused"));
      return;
    }
    setRefusal(null);
    form.reset();
    await client.refetchQueries({ queryKey: accountsQuery.queryKey });
  }

  return (
    <form className={accountForm()} data-part="accounts/create" onSubmit={(event) => void create(event)} noValidate>
      <h2 className={sectionHeading()} data-part="heading">{t("screens.accounts.newAccount")}</h2>
      <label>
        {t("screens.accounts.name")}
        <input className={accountField()} name="name" autoComplete="off" required />
      </label>
      <label>
        {t("screens.accounts.email")}
        <input className={accountField()} name="email" type="email" autoComplete="off" required />
      </label>
      <label>
        {t("screens.accounts.initialRole")}
        <select className={accountField()} name="role" defaultValue={roles.find((role) => role.defaultFor?.includes("local"))?.id}>
          {/* GREYED, NEVER HIDDEN, where the manager may not give it — the
              account sheet's own rule for the same choice (round 9 Q14 = A). */}
          {roles.map((role) => (
            <option key={role.id} value={role.id} disabled={!withinReach(role.rights, manager)}>{roleLabel(role)}</option>
          ))}
        </select>
      </label>
      <label>
        {t("screens.accounts.provisionalPassword")}
        <input className={accountField()} name="password" type="password" autoComplete="new-password" />
      </label>
      <p className={guidance()}>{t("screens.accounts.plexHint")}</p>
      {refusal ? <p className={surfaceError({ tone: "danger" })} role="status" data-part="accounts/refusal">{refusal}</p> : null}
      <button className={actionButton({ kind: "cardFoot", tone: "solid" })} type="submit" data-part="accounts/create-submit">
        {t("screens.accounts.create")}
      </button>
    </form>
  );
}
