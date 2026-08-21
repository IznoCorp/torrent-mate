// design/src/pages/not-found.tsx
// An address that leads nowhere, answered honestly: what was asked for is
// NAMED, nothing is claimed to be broken, and two ways out are offered — the
// page one would have gone to anyway, and the menu that lists every page.
//
// The address is printed exactly as it was typed. Rewriting it to something
// that exists would quietly turn a mistyped link into a different one.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useReference, useUiState } from "../data";

export function NotFoundPage(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { emptyInner, escapeHtml } = useReference();
  const asked = (state.notFound as string) || t("screens.notFound.bodyFallback");
  return (
    <>
      <div
        className="empty" data-part="empty-state"
        dangerouslySetInnerHTML={{
          __html: emptyInner(
            t("screens.notFound.title"),
            `${t("screens.notFound.bodyBefore")}<code>${escapeHtml(asked)}</code>${t("screens.notFound.bodyAfter")}`,
          ),
        }}
      />
      <button className="cfoot solid" data-part="card/foot" data-go="acq">
        {t("screens.notFound.toAcquisition")}
      </button>
      <button className="crossref" data-drawer="1">
        {t("screens.notFound.allPages")}
        <span>{t("screens.notFound.menuLink")}</span>
      </button>
    </>
  );
}
