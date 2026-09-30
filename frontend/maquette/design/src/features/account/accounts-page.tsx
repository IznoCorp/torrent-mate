// « Comptes » — the accounts, their ONE role each, and the roles' rights
// (§ 17; ruling 14; round 8 Q9 = B: a first-level page of the menu, grouped
// with Réglages, opened by `accounts.manage`).
//
// EVERYTHING HERE IS THE ANSWER'S: one row per account the roster holds, its
// role by the name the server gives it — « sans droits » for the Default role,
// which opens the library alone — and one row per role. A tap opens the
// account's panel (its role) or the role's (its rights).
import { useState } from "react";
import type { FormEvent, ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { accountsQuery } from "../../lib/account";
import { bypassesRights, isDefaultRole } from "../../lib/rights";
import { send } from "../../lib/query-client";
import { FactRows } from "../../ui/fact-rows";
import { actionButton, factList, guidance, sectionHeading, surfaceError } from "../../ui/variants";
import type { Schemas } from "../../lib/contract-schemas";
import { accountField, accountForm } from "./variants";

export function AccountsPage(): ReactElement | null {
  const { t } = useTranslation();
  const { data: roster } = useQuery(accountsQuery);
  if (!roster) return null;
  return (
    <>
      <h2 className={sectionHeading()} data-part="heading">{t("screens.accounts.accounts")}</h2>
      <ol className={factList()} data-part="flux">
        <FactRows rows={roster.accounts.map((account) => ({
          label: account.name,
          value: isDefaultRole(account.role) ? t("screens.accounts.rightless") : account.role.name,
          secondaryLine: `${account.email} · ${t(account.plexLinked ? "screens.accounts.plexLinked" : "screens.accounts.plexNotLinked")}`,
          target: { panel: `roster:${account.id}` },
          part: "accounts/account",
        }))} />
      </ol>

      <h2 className={sectionHeading()} data-part="heading">{t("screens.accounts.roles")}</h2>
      <ol className={factList()} data-part="flux">
        <FactRows rows={roster.roles.map((role) => ({
          label: role.name,
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

/**
 * The creation form: a name, a MANDATORY e-mail, an initial role (demand G).
 *
 * @param roles The roles an account may be created on — never Admin here.
 */
function NewAccount({ roles }: { roles: Schemas["Role"][] }): ReactElement {
  const { t } = useTranslation();
  const client = useQueryClient();
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
    try {
      await send("POST", "/api/accounts", {
        name: String(fields.get("name") ?? "").trim(),
        email,
        role: String(fields.get("role") ?? ""),
      });
      setRefusal(null);
      form.reset();
      await client.refetchQueries({ queryKey: accountsQuery.queryKey });
    } catch {
      setRefusal(t("screens.accounts.createRefused"));
    }
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
        <select className={accountField()} name="role" defaultValue={roles.find(isDefaultRole)?.id}>
          {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
        </select>
      </label>
      <p className={guidance()}>{t("screens.accounts.plexHint")}</p>
      {refusal ? <p className={surfaceError({ tone: "danger" })} role="status" data-part="accounts/refusal">{refusal}</p> : null}
      <button className={actionButton({ kind: "cardFoot", tone: "solid" })} type="submit" data-part="accounts/create-submit">
        {t("screens.accounts.create")}
      </button>
    </form>
  );
}
