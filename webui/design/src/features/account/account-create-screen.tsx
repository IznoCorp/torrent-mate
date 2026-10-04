// « Nouveau compte » — an account's creation page, over « Comptes » (the
// operator, 2026-10-04: « Créer un nouveau compte devrait avoir sa propre page
// avec formulaire et validation aussi »).
//
// EVERY FIELD STARTS EMPTY, the role included: nothing is chosen for the
// manager. A name, a MANDATORY e-mail (§ 17) and a role are required, each said
// at its field once typed into — never on a mere blur, which moves nothing — and
// Create stays closed until they hold. The
// PROVISIONAL password (the operator, 2026-10-03: « A ») is a local account's:
// whether the e-mail is a user of the managed Plex server — linked, signing in
// by Plex, its password ignored — is the server's to know, so its rules are the
// server's refusals, said under the password field in `fr.json`'s words.
//
// SENT NOW OR NOT AT ALL (`send-now.ts`): the body carries a password.
import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { accountsQuery, roleLabel } from "../../lib/account";
import { refusalCode, refusalWords } from "../../lib/refusal";
import { bypassesRights } from "../../lib/rights";
import { bridge } from "../../lib/shell-doors";
import { CreationForm, CreationScreen, Field } from "../../ui/creation-form";
import { emptyNote, formControl, surfaceError } from "../../ui/variants";
import { useAccount, useRights } from "./queries";
import { withinReach } from "./roster-panels";
import { sendNow } from "./send-now";

/** The screen's key: its `data-key`, and its body's region. */
const KEY = "account-create";

/** The form's fields. */
type FieldName = "name" | "email" | "role" | "password";

/** Which field each refusal the server answers belongs to. */
const FIELD_OF: Readonly<Record<string, FieldName>> = {
  "account.email_invalid": "email",
  "account.email_taken": "email",
  "password.required": "password",
  "password.too_short": "password",
  "role.unknown": "role",
  "role.escalation": "role",
};

/**
 * Whether a typed e-mail reads as one: something, an at sign, something, no space.
 *
 * @param typed The e-mail typed.
 * @returns True when it does.
 */
export function readsAsEmail(typed: string): boolean {
  return /^[^\s@]+@[^\s@]+$/.test(typed.trim());
}

/**
 * « Nouveau compte »' screen: an account's creation form, every field empty.
 *
 * @returns The form, or the reserved note when the viewer lacks `accounts.manage`.
 */
export function AccountCreateScreen(): ReactElement {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data: roster } = useQuery(accountsQuery);
  const { data: manager } = useAccount();
  const rights = useRights();
  const [values, setValues] = useState<Record<FieldName, string>>({ name: "", email: "", role: "", password: "" });
  const [touched, setTouched] = useState<Set<FieldName>>(new Set());
  const [sending, setSending] = useState(false);
  const [refusal, setRefusal] = useState<{ field: FieldName | null; words: string } | null>(null);

  const screen = (children: ReactElement) => (
    <CreationScreen screenKey={KEY} title={t("screens.accounts.accountCreate.title")} back={t("screens.accounts.back")}>
      {children}
    </CreationScreen>
  );
  if (!rights.holds("accounts.manage"))
    return screen(
      <p className={emptyNote()} data-part="access/reserved" data-right="accounts.manage">
        {t("access.reservedBody", { right: t("access.rights.accounts.manage") })}
      </p>,
    );

  // NEVER ADMIN HERE: an account is promoted from its panel, by an Admin.
  const roles = (roster?.roles ?? []).filter((role) => !bypassesRights(role));
  const typed = { name: values.name.trim(), email: values.email.trim(), role: values.role };
  // WHAT THE CLIENT KNOWS IS SAID BEFORE ANYTHING IS ASKED, once the field was touched.
  const own: Record<FieldName, string | null> = {
    name: typed.name ? null : t("screens.accounts.accountCreate.nameRequired"),
    email: !typed.email ? t("screens.accounts.emailRequired") : readsAsEmail(typed.email) ? null : t("refusals.account.email_invalid"),
    role: typed.role ? null : t("screens.accounts.accountCreate.roleRequired"),
    password: null,
  };
  const errorOf = (field: FieldName): string | null =>
    (touched.has(field) ? own[field] : null) ?? (refusal?.field === field ? refusal.words : null);
  const valid = own.name === null && own.email === null && own.role === null && roster !== undefined;

  /** Writes what was typed into one field, and forgets the refusal that field carried. */
  function type(field: FieldName, value: string): void {
    setValues((before) => ({ ...before, [field]: value }));
    setTouched((before) => new Set(before).add(field));
    if (refusal?.field === field) setRefusal(null);
  }

  async function create(): Promise<void> {
    setSending(true);
    setRefusal(null);
    const problem = await sendNow("POST", "/api/v1/accounts", { ...typed, password: values.password });
    setSending(false);
    if (problem === null) {
      await client.refetchQueries({ queryKey: accountsQuery.queryKey });
      bridge.back();
      return;
    }
    // A REFUSAL SAYS WHY, AT ITS FIELD, in `fr.json`'s words for its code (gap G-1).
    const code = refusalCode(problem);
    setRefusal({ field: code === undefined ? null : FIELD_OF[code] ?? null, words: refusalWords(problem, "screens.accounts.createRefused") });
  }

  /** The attributes every control carries: its name, its state, what describes it. */
  const control = (field: FieldName, required: boolean) => ({
    className: formControl({ invalid: errorOf(field) !== null }),
    id: `creation-${field}`,
    name: field,
    "data-part": `account-create/${field}`,
    value: values[field],
    "aria-required": required,
    "aria-invalid": errorOf(field) !== null,
    "aria-describedby": errorOf(field) !== null ? `creation-${field}-error` : undefined,
  });
  const required = t("screens.accounts.required");

  return screen(
    <CreationForm onSubmit={() => void create()} valid={valid} sending={sending}
      act={t("screens.accounts.create")} sendingAct={t("screens.accounts.creating")}>
      <Field name="name" label={t("screens.accounts.name")} required requiredWords={required} error={errorOf("name")}>
        <input {...control("name", true)} autoComplete="off" onChange={(event) => type("name", event.currentTarget.value)} />
      </Field>
      <Field name="email" label={t("screens.accounts.accountCreate.email")} required requiredWords={required}
        error={errorOf("email")}>
        <input {...control("email", true)} type="email" inputMode="email" autoComplete="off"
          onChange={(event) => type("email", event.currentTarget.value)} />
      </Field>
      <Field name="role" label={t("screens.accounts.initialRole")} required requiredWords={required} error={errorOf("role")}>
        <select {...control("role", true)} onChange={(event) => type("role", event.currentTarget.value)}>
          <option value="" disabled>{t("screens.accounts.accountCreate.chooseRole")}</option>
          {/* GREYED, NEVER OFFERED, where the manager may not give it — the
              account panel's own rule for the same choice (round 9 Q14 = A). */}
          {roles.map((role) => (
            <option key={role.id} value={role.id} disabled={!withinReach(role.rights, manager)}>{roleLabel(role)}</option>
          ))}
        </select>
      </Field>
      <Field name="password" label={t("screens.accounts.provisionalPassword")} required={false} requiredWords={required}
        error={errorOf("password")} hint={t("screens.accounts.plexHint")}>
        <input {...control("password", false)} type="password" autoComplete="new-password"
          onChange={(event) => type("password", event.currentTarget.value)} />
      </Field>
      {refusal !== null && refusal.field === null ? (
        <p className={surfaceError({ tone: "danger" })} role="alert" data-part="account-create/refusal">{refusal.words}</p>
      ) : null}
    </CreationForm>,
  );
}
