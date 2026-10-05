// « Langue », in Profil — the language the interface speaks to this account.
//
// The operator, 2026-10-03 (FG-1 B): the language is the ACCOUNT's, chosen here, the same on every
// device it signs in from — never the device's; and its pushes are worded in it (FG-2 A).
//
// THE HOUSE'S IN-PLACE PICKER: the segmented control that picks a value where it stands (the
// drawer's appearance), in a row of the section's panel — its label leading, its line muted under it.
//
// THE SWITCH FOLLOWS THE SERVER: the choice is sent now, and only once it is held does the whole
// interface speak it — at once, without a reload (`lib/account.ts` follows the account's entry).
// While it is asked, the control says so and takes no other choice; a refusal is said under it, and
// the language in force stays the one the server holds.
//
// A SESSION ACT, NO RIGHT (the account's own setting, like its notification switches): every account
// is offered the choice. The read-only instance's server still refuses the write; that is said.
import { useState, type ReactElement } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { LANGUAGES, type Language } from "../../i18n";
import { refusalWords } from "../../lib/refusal";
import { factsPanel, keyValueRow, qualityHint, sectionHeading, settingRow, surfaceError, viewSwitch, viewSwitchButton } from "../../ui/variants";
import { accountQuery, useAccount, type Account } from "./queries";
import { sendNow } from "./send-now";

/** Where the choice stands: at rest, asked of the server, or refused with its words. */
type Outcome = { kind: "rest" } | { kind: "saving"; language: Language } | { kind: "refused"; words: string };

/**
 * The « Langue » section.
 *
 * @returns The section, or nothing while the account has not been read.
 */
export function LanguageSection(): ReactElement | null {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data: account } = useAccount();
  const [outcome, setOutcome] = useState<Outcome>({ kind: "rest" });
  if (!account) return null;
  const current: Language = account.language;
  const saving = outcome.kind === "saving";
  const words = "screens.accountPage.language";

  async function choose(language: Language): Promise<void> {
    if (saving || language === current) return;
    setOutcome({ kind: "saving", language });
    const problem = await sendNow("PUT", "/api/v1/auth/language", { language });
    if (problem !== null) return setOutcome({ kind: "refused", words: refusalWords(problem, `${words}.refused`) });
    setOutcome({ kind: "rest" });
    // HELD: the account's entry moves, and the interface follows it.
    client.setQueryData<Account>(accountQuery.queryKey, (held) => held && { ...held, language });
  }

  return (
    <section data-part="profile/language" data-language={current} data-saving={saving || undefined}>
      <h2 className={sectionHeading()} data-part="heading">{t(`${words}.heading`)}</h2>
      <div className={factsPanel()} data-part="panel">
        <div className={`${keyValueRow()} ${settingRow()}`} data-part="key-value">
          <div className="min-w-0">
            <div className="font-semibold">{t(`${words}.label`)}</div>
            <div className={qualityHint()} role="status" data-part="profile/language-line">
              {t(saving ? `${words}.saving` : `${words}.line`)}
            </div>
          </div>
          <div className={viewSwitch()} data-part="profile/language-choice" role="group" aria-label={t(`${words}.label`)}>
            {LANGUAGES.map((language) => (
              <button
                key={language}
                type="button"
                className={viewSwitchButton({ size: "text" })}
                data-language-choice={language}
                // THE LANGUAGE ASKED FOR IS THE ONE PRESSED while it is asked: the tap is answered at once.
                aria-pressed={(outcome.kind === "saving" ? outcome.language : current) === language}
                disabled={saving}
                lang={language}
                onClick={() => void choose(language)}
              >
                {t(`${words}.names.${language}`)}
              </button>
            ))}
          </div>
        </div>
      </div>
      {outcome.kind === "refused" ? (
        <p className={surfaceError({ tone: "danger" })} role="status" data-part="profile/language-refusal">{outcome.words}</p>
      ) : null}
    </section>
  );
}
