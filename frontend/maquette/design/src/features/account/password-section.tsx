// « Mot de passe », in Profil — a LOCAL account changes its own password (the
// operator, 2026-10-03: « Le mot de passe d'un compte local … peut se changer
// sur le profil de l'utilisateur »).
//
// DRAWN FOR A LOCAL ACCOUNT ONLY: the Plex owner's fallback password changes by
// a command on the server, never here, and a Plex-linked account holds none —
// Profil's « Connexion » line says so for both.
//
// NOT THROUGH THE OUTBOX (`send-now.ts`): a password is sent now or not at all.
//
// A REFUSAL IS SAID FROM `fr.json` BY ITS CODE (gap G-1): the current password
// wrong, the new one too short — its minimum the server's, carried in the
// refusal's parameters.
import { useState, type FormEvent, type ReactElement } from "react";
import { useTranslation } from "react-i18next";

import { refusalWords } from "../../lib/refusal";
import { actionButton, guidance, sectionHeading, surfaceError } from "../../ui/variants";
import { sendNow } from "./send-now";
import { accountField, accountForm } from "./variants";

/** Where the form stands: at rest, asking, changed, or refused with its words. */
type Outcome = { kind: "rest" } | { kind: "sending" } | { kind: "changed" } | { kind: "refused"; words: string };

export function PasswordSection(): ReactElement {
  const { t } = useTranslation();
  const [outcome, setOutcome] = useState<Outcome>({ kind: "rest" });

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const current = String(fields.get("currentPassword") ?? "");
    const next = String(fields.get("newPassword") ?? "");
    const again = String(fields.get("confirmPassword") ?? "");
    // SAID BEFORE ANYTHING IS ASKED: a field left empty, or two new passwords
    // that differ — the one mistake that would lock a local account out.
    if (!current || !next || !again) return setOutcome({ kind: "refused", words: t("screens.accountPage.password.missing") });
    if (next !== again) return setOutcome({ kind: "refused", words: t("screens.accountPage.password.mismatch") });
    setOutcome({ kind: "sending" });
    const problem = await sendNow("PUT", "/api/v1/auth/password", { currentPassword: current, newPassword: next });
    if (problem === null) {
      form.reset();
      return setOutcome({ kind: "changed" });
    }
    setOutcome({ kind: "refused", words: refusalWords(problem, "screens.accountPage.password.refused") });
  }

  return (
    <form className={accountForm()} data-part="profile/password" onSubmit={(event) => void submit(event)} noValidate>
      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.password.heading")}</h2>
      <label>
        {t("screens.accountPage.password.current")}
        <input className={accountField()} name="currentPassword" type="password" autoComplete="current-password" required />
      </label>
      <label>
        {t("screens.accountPage.password.new")}
        <input className={accountField()} name="newPassword" type="password" autoComplete="new-password" required />
      </label>
      <label>
        {t("screens.accountPage.password.confirm")}
        <input className={accountField()} name="confirmPassword" type="password" autoComplete="new-password" required />
      </label>
      {outcome.kind === "refused" ? (
        <p className={surfaceError({ tone: "danger" })} role="status" data-part="profile/password-refusal">{outcome.words}</p>
      ) : null}
      {outcome.kind === "changed" ? (
        <p className={guidance()} role="status" data-part="profile/password-changed">{t("screens.accountPage.password.changed")}</p>
      ) : null}
      <button
        className={actionButton({ kind: "cardFoot", tone: "solid" })}
        type="submit"
        data-part="profile/password-submit"
        disabled={outcome.kind === "sending"}
      >
        {t(outcome.kind === "sending" ? "screens.accountPage.password.sending" : "screens.accountPage.password.submit")}
      </button>
    </form>
  );
}
