// THE INSTANCE'S CEILING, said once where the writes would have been (§ 17;
// ruling 23).
//
// A NAMED LIST, served with the account, never a boolean nor a guess from an
// address: today's read-only instance forbids every write, the future preprod
// forbids deleting from the library alone. The notice names what is forbidden —
// « lecture seule » only when the list covers every write.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { useRights } from "../lib/account";
import { WRITE_RIGHTS } from "../lib/rights";
import { SurfaceError } from "../ui/state-surfaces";

/** The ceiling's notice, or nothing on an instance that forbids no write. */
export function CeilingNotice(): ReactElement | null {
  const { t } = useTranslation();
  const { forbidden } = useRights();
  if (forbidden.length === 0) return null;
  const every = WRITE_RIGHTS.every((right) => forbidden.includes(right));
  const named = new Intl.ListFormat("fr", { type: "conjunction" })
    .format(forbidden.map((right) => t(`access.rights.${right}`)));
  return (
    <div data-part="access/ceiling" data-forbidden={forbidden.join(" ")}>
      <SurfaceError tone="info" part="notice">
        {every ? t("access.ceilingEvery") : t("access.ceilingSome", { rights: named })}
      </SurfaceError>
    </div>
  );
}
