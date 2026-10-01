// A role's NAME, as its panel offers it to change — the one field « Comptes »
// draws inside the bottom panel (round 9 Q14: « les droits et les rôles livrés
// sont … modifiables par l'interface »).
//
// DECLARED TO THE PANEL'S CONTRACT beside what draws it, as the settings'
// field is: the panel knows no role, this file adds the kind and registers its
// drawing. The act that files the name is an ordinary panel action
// (`role-rename`), which reads what was typed here — the secret field's
// arrangement.
import { useTranslation } from "react-i18next";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { accountField, accountForm } from "./variants";

declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    roleName: { role: string; name: string };
  }
}

/**
 * The field holding a role's name.
 *
 * @param props The block: the role's key and its current name.
 * @returns The labelled field.
 */
function RoleNameBlock({ block }: { block: { type: "roleName" } & PanelBlockMap["roleName"] }) {
  const { t } = useTranslation();
  return (
    <div className={accountForm()}>
      <label>
        {t("screens.accounts.roleName")}
        <input
          // KEYED BY THE ROLE: the panel reuses its nodes from one role to the
          // next, and a typed name must never follow the reader to another role.
          key={block.role}
          className={accountField()}
          data-part="accounts/role-name"
          data-role-name={block.role}
          defaultValue={block.name}
          autoComplete="off"
        />
      </label>
    </div>
  );
}

registerBlock("roleName", (block) => <RoleNameBlock block={block} />);

/**
 * What the reader has typed as a role's name.
 *
 * @param role The role's key.
 * @returns The name typed, trimmed, or the empty string.
 */
export function typedRoleName(role: string): string {
  const field = document.querySelector<HTMLInputElement>(
    `#sheetin [data-part="accounts/role-name"][data-role-name="${CSS.escape(role)}"]`);
  return field?.value.trim() ?? "";
}
