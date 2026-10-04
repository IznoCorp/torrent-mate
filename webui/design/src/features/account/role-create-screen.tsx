// « Nouveau rôle » — a role's creation page, over « Comptes » (the operator,
// 2026-10-04: « je préférerais avoir une nouvelle page avec un formulaire de
// création avec validation. Pas de nom par défaut, saisie avec champs
// obligatoires »).
//
// NOTHING IS CREATED UNTIL CREATE IS PRESSED, and nothing is made up: the name
// starts EMPTY and is required, the rights start with none — what the role
// hands out is what the manager chose. A name another role already carries is
// said at the field before anything is asked; a refusal the server still
// answers lands at its field too.
//
// ESCALATION IS DRAWN AS WELL AS REFUSED (round 9 Q14 = A): a right the
// manager's own role does not hold is greyed, never offered.
import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { accountsQuery } from "../../lib/account";
import type { Schemas } from "../../lib/contract-schemas";
import { HELD, isRequestFailure, send } from "../../lib/query-client";
import { refusalCode, refusalWords } from "../../lib/refusal";
import { RIGHTS, type Right } from "../../lib/rights";
import { bridge } from "../../lib/shell-doors";
import { CreationForm, CreationScreen, Field } from "../../ui/creation-form";
import { Switch } from "../../ui/switch";
import {
  emptyNote, factList, factName, factRow, factRowBody, factDetail, formControl, sectionHeading, surfaceError,
} from "../../ui/variants";
import { useAccount, useRights } from "./queries";
import { withinReach } from "./roster-panels";

/** The screen's key: its `data-key`, and its body's region. */
const KEY = "role-create";

/** The refusals the server answers about the name — said at the name field. */
const NAME_CODES: ReadonlySet<string> = new Set(["role.name_required", "role.name_taken"]);

/**
 * Whether a typed name is one another role already carries in its `name` —
 * the contract's rule, the server's: trimmed, regardless of case. A seeded
 * role carries no name (its words are the interface's translation, which
 * change with the language and which the server cannot know), so its words
 * are never taken.
 *
 * @param typed The name typed.
 * @param roles The roles the roster holds.
 * @returns True when one carries it.
 */
export function nameTaken(typed: string, roles: readonly Pick<Schemas["Role"], "name">[]): boolean {
  const wanted = typed.trim().toLowerCase();
  return wanted !== "" && roles.some((role) => role.name?.trim().toLowerCase() === wanted);
}

/**
 * « Nouveau rôle »' screen: a role's creation form, its name empty, no right chosen.
 *
 * @returns The form, or the reserved note when the viewer lacks `accounts.manage`.
 */
export function RoleCreateScreen(): ReactElement {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data: roster } = useQuery(accountsQuery);
  const { data: manager } = useAccount();
  const rights = useRights();
  const [name, setName] = useState("");
  const [touched, setTouched] = useState(false);
  const [chosen, setChosen] = useState<Right[]>([]);
  const [sending, setSending] = useState(false);
  // A REFUSAL THE SERVER STILL ANSWERS, by the field it concerns — the name's,
  // or the form's as a whole when no field owns it.
  const [refusal, setRefusal] = useState<{ field: "name" | null; words: string } | null>(null);

  const screen = (children: ReactElement) => (
    <CreationScreen screenKey={KEY} title={t("screens.accounts.roleCreate.title")} back={t("screens.accounts.back")}
      lead={t("screens.accounts.roleCreate.lead")}>
      {children}
    </CreationScreen>
  );
  // A VIEWER WITHOUT THE RIGHT IS TOLD SO here, as « Comptes » tells it — never
  // a form it could not send.
  if (!rights.holds("accounts.manage"))
    return screen(
      <p className={emptyNote()} data-part="access/reserved" data-right="accounts.manage">
        {t("access.reservedBody", { right: t("access.rights.accounts.manage") })}
      </p>,
    );

  const trimmed = name.trim();
  const taken = nameTaken(trimmed, roster?.roles ?? []);
  const nameError = !touched ? null
    : !trimmed ? t("refusals.role.name_required")
    : taken ? t("refusals.role.name_taken")
    : refusal?.field === "name" ? refusal.words : null;
  const valid = trimmed !== "" && !taken && roster !== undefined;

  async function create(): Promise<void> {
    setSending(true);
    setRefusal(null);
    try {
      const answer = await send("POST", "/api/v1/roles", { name: trimmed, rights: chosen });
      // HELD offline, it departs with the outbox: the roster shows it then.
      if (answer !== HELD) await client.refetchQueries({ queryKey: accountsQuery.queryKey });
      bridge.back();
    } catch (failure) {
      const code = isRequestFailure(failure) ? refusalCode(failure) : undefined;
      setRefusal({
        field: code !== undefined && NAME_CODES.has(code) ? "name" : null,
        words: refusalWords(failure, "screens.accounts.roleCreate.refused"),
      });
    } finally {
      setSending(false);
    }
  }

  return screen(
    <CreationForm onSubmit={() => void create()} valid={valid} sending={sending}
      act={t("screens.accounts.roleCreate.act")} sendingAct={t("screens.accounts.creating")}>
      <Field name="name" label={t("screens.accounts.roleName")} required requiredWords={t("screens.accounts.required")}
        error={nameError}>
        <input className={formControl({ invalid: nameError !== null })} id="creation-name" name="name"
          data-part="role-create/name" value={name} autoComplete="off" aria-required="true"
          aria-invalid={nameError !== null}
          aria-describedby={nameError !== null ? "creation-name-error" : undefined}
          onChange={(event) => {
            setName(event.currentTarget.value);
            setTouched(true);
            if (refusal?.field === "name") setRefusal(null);
          }} />
      </Field>

      <div>
        <h2 className={sectionHeading()} data-part="heading">{t("screens.accounts.roleCreate.rights")}</h2>
        <ol className={factList()} data-part="role-create/rights">
          {RIGHTS.map((right) => {
            const on = chosen.includes(right);
            // GREYED, NEVER OFFERED, where the manager may not hand it out (Q14 = A).
            const reach = withinReach([right], manager);
            return (
              <li key={right} className={factRow({ withControl: true })} data-part="role-create/right" data-right={right}>
                <span className={factRowBody()}>
                  <span className={factName()}>{t(`access.rights.${right}`)}</span>
                  <span className={factDetail()}>{t(`access.holders.${right}`)}</span>
                </span>
                <Switch checked={on} label={t(`access.rights.${right}`)} disabled={!reach}
                  data-part="role-create/right-switch" data-role-create-right={right}
                  onClick={() => setChosen((before) => (on ? before.filter((one) => one !== right) : [...before, right]))} />
              </li>
            );
          })}
        </ol>
      </div>

      {refusal !== null && refusal.field === null ? (
        <p className={surfaceError({ tone: "danger" })} role="alert" data-part="role-create/refusal">{refusal.words}</p>
      ) : null}
    </CreationForm>,
  );
}
