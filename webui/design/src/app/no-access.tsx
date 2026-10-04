// WHERE A ROLE THAT OPENS NO PAGE LANDS (ruling 22, precision).
//
// A role emptied even of `library.read` is a configuration « Comptes » allows,
// and the interface must survive it rather than fail at sign-in: it says so, in
// one sentence, and offers the one act every account has — signing out. No
// bar, no menu: there is nowhere to go.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { actionButton, emptyNote } from "../ui/variants";
import { Markup, emptyNoteMarkup } from "../ui/markup";

export function NoAccessPage(): ReactElement {
  const { t } = useTranslation();
  return (
    <>
      <Markup
        className={emptyNote()} data-part="empty-state"
        html={emptyNoteMarkup(t("screens.noAccess.title"), t("screens.noAccess.body"))}
      />
      <button className={actionButton({ kind: "cardFoot" })} data-part="card/foot" data-signout="1">
        {t("screens.accountPage.signOut")}
      </button>
    </>
  );
}
