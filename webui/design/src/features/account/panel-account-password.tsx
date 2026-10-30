// A LOCAL account's provisional password, as its panel in « Comptes » offers to
// set it again — a forgotten password replaced by an Admin, which the account
// then changes in Profil (the operator, 2026-10-03: « A »).
//
// DRAWN ON A LOCAL ACCOUNT'S PANEL ONLY (`roster-panels.ts`): the Plex owner's
// fallback password changes by a command on the server, and a Plex-linked
// account holds none.
//
// ITS OWN FORM, with its outcome said inside the panel rather than in a toast
// that leaves: the Admin must read that the password is set before telling it
// to the account's holder. Sent now or not at all (`send-now.ts`), and the
// refusal said from `fr.json` by its code (gap G-1). THE PASSWORD POLICY (the
// operator, 2026-10-04) is said under the field, and a password breaking it is
// said before anything is asked.
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { PASSWORD_MINIMUM, passwordShortfall } from "../../lib/password-policy";
import { refusalWords } from "../../lib/refusal";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { actionButton, guidance, surfaceError } from "../../ui/variants";
import { sendNow } from "./send-now";
import { accountField, accountForm } from "./variants";

declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    accountPassword: { account: string; name: string };
  }
}

/** Where the form stands: at rest, asking, set, or refused with its words. */
type Outcome = { kind: "rest" } | { kind: "sending" } | { kind: "set" } | { kind: "refused"; words: string };

/**
 * The field and the act that set a local account's provisional password.
 *
 * @param props The block: the account's id and its name.
 * @returns The form.
 */
function AccountPasswordBlock({ block }: { block: { type: "accountPassword" } & PanelBlockMap["accountPassword"] }) {
  const { t } = useTranslation();
  const [outcome, setOutcome] = useState<Outcome>({ kind: "rest" });

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    const password = String(new FormData(form).get("provisionalPassword") ?? "");
    const shortfall = password ? passwordShortfall(password) : undefined;
    if (shortfall !== undefined)
      return setOutcome({ kind: "refused", words: t(`refusals.${shortfall}`, { minimum: PASSWORD_MINIMUM }) });
    setOutcome({ kind: "sending" });
    const problem = await sendNow("POST", `/api/v1/accounts/${encodeURIComponent(block.account)}/password`, { password });
    if (problem === null) {
      form.reset();
      return setOutcome({ kind: "set" });
    }
    setOutcome({ kind: "refused", words: refusalWords(problem, "screens.accounts.reset.refused") });
  }

  return (
    <form
      className={accountForm()}
      data-part="accounts/password-reset"
      data-account={block.account}
      onSubmit={(event) => void submit(event)}
      noValidate
    >
      <label>
        {t("screens.accounts.reset.field")}
        <input className={accountField()} name="provisionalPassword" type="password" autoComplete="new-password" required />
      </label>
      <p className={guidance()} data-part="accounts/password-rule">{t("common.passwordRule", { minimum: PASSWORD_MINIMUM })}</p>
      <p className={guidance()}>{t("screens.accounts.reset.hint")}</p>
      {outcome.kind === "refused" ? (
        <p className={surfaceError({ tone: "danger" })} role="status" data-part="accounts/password-reset-refusal">{outcome.words}</p>
      ) : null}
      {outcome.kind === "set" ? (
        <p className={guidance()} role="status" data-part="accounts/password-reset-done">
          {t("screens.accounts.reset.done", { name: block.name })}
        </p>
      ) : null}
      <button
        className={actionButton({ kind: "cardFoot", tone: "solid" })}
        type="submit"
        data-part="accounts/password-reset-submit"
        disabled={outcome.kind === "sending"}
      >
        {t(outcome.kind === "sending" ? "screens.accounts.reset.sending" : "screens.accounts.reset.submit")}
      </button>
    </form>
  );
}

// KEYED BY THE ACCOUNT: the panel reuses its nodes from one account to the next,
// and a typed password or an outcome must never follow the reader.
registerBlock("accountPassword", (block) => <AccountPasswordBlock key={block.account} block={block} />);
