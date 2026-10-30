// « Notifications », in Profil — the account's switches, one per type, under this device's line.
//
// The operator, 2026-10-03: « il faudra une gestion des canaux, des canaux de notification, de
// façon à pouvoir couper les notifications FCM de certains types tout en gardant les autres. »
// His rulings the same day: the switches are the ACCOUNT'S, on all its devices (Q1 A), and they
// live here, under the device's line, for every account that receives pushes (Q2 A).
//
// THE TYPES ARE THE SERVER'S ANSWER: it offers only those the account's rights receive, so the
// section draws what it reads and holds no table of rights — and an account offered none is
// shown no section at all.
//
// A ROW'S LABEL LEADS AND ITS LINE FOLLOWS, MUTED — the weight of « Votre session »'s rows, not
// the key-value row's own, which mutes its first span.
//
// THE WRITES CARRY NO RIGHT (the operator, 2026-10-03: « tout le monde à le droit de changer les
// notifications de son propre compte, ça n'a pas de sens de mettre ça sous un droit »): every
// account offered a type has pressable switches and « Activer ». The read-only instance's server
// still refuses a write; a refusal is SAID, and the switch returns to the server's truth.
//
// THE DEVICE'S LINE COMES FIRST because it says whether the switches below reach THIS device;
// they are drawn whatever it says, since a choice holds on the account's other devices.
import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { read, send } from "../../lib/query-client";
import { toast } from "../../lib/shell-doors";
import { Switch } from "../../ui/switch";
import { actionButton, factsPanel, guidance, keyValueRow, qualityHint, section, sectionHeading, settingRow } from "../../ui/variants";
import { chipTone } from "../../ui/fact-rows";
import { Chip } from "../../ui/chip";
import { deviceSupport, enablePush, poseGeneration, type DeviceSupport } from "./push-device";
import type { components } from "../../contract/types";

type Preferences = components["schemas"]["NotificationPreferences"];
type NotificationType = components["schemas"]["NotificationType"];

const PREFERENCES_KEY = ["/api/v1/notifications/preferences"];

/**
 * The account's switches, read from the server.
 *
 * @returns The query.
 */
function usePreferences() {
  return useQuery({
    queryKey: PREFERENCES_KEY,
    queryFn: () => read<Preferences>("/api/v1/notifications/preferences"),
  });
}

/**
 * The words key of one type, under `notifications.types`.
 *
 * @param type The type's id, `area.name`.
 * @returns The key of its words.
 */
function typeKey(type: NotificationType): string {
  return `notifications.types.${type}`;
}

/**
 * This device's line: what it can do, and « Activer » where it can still be asked.
 *
 * @returns The line.
 */
function DeviceLine(): ReactElement {
  const { t } = useTranslation();
  const [support, setSupport] = useState<DeviceSupport>(() => deviceSupport());
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const words = `screens.accountPage.notifications.device`;

  function enable(): void {
    setPending(true);
    setFailed(false);
    // CALLED FROM THE PRESS, before any await: iOS grants the permission only inside the gesture.
    enablePush()
      .then(setSupport)
      .catch(() => setFailed(true))
      .finally(() => setPending(false));
  }

  return (
    <div className={`${keyValueRow()} ${settingRow()}`} data-part="profile/push-device" data-support={support}>
      <div className="min-w-0">
        <div className="font-semibold">{t(`${words}.label`)}</div>
        {/* THE SUPPORT UNDER THE LABEL, never beside it: its words are longer than a chip's
            room beside a phone's row, and the row's right side is the action's. */}
        {support === "unasked" ? null : (
          <div className="my-1 flex">
            <Chip tone={chipTone(support === "granted" ? "success" : "neutral")} label={t(`${words}.${support}.value`)} />
          </div>
        )}
        <div className={qualityHint()}>{t(failed ? `${words}.failed` : `${words}.${support}.line`)}</div>
      </div>
      {support === "unasked" ? (
        <button className={actionButton({ kind: "panelAction" })} data-part="profile/push-enable" disabled={pending}
          onClick={enable}>
          {t(pending ? `${words}.enabling` : `${words}.enable`)}
        </button>
      ) : null}
    </div>
  );
}

/**
 * The « Notifications » section, or nothing for an account offered no type.
 *
 * @returns The section.
 */
export function NotificationsSection(): ReactElement | null {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data } = usePreferences();
  if (!data || data.preferences.length === 0) return null;

  function toggle(type: NotificationType, enabled: boolean): void {
    // OPTIMISTIC, and on a refusal SAID refused, then rolled back by a fresh read.
    client.setQueryData<Preferences>(PREFERENCES_KEY, (held) =>
      held && { preferences: held.preferences.map((one) => (one.type === type ? { ...one, enabled } : one)) });
    send("PUT", `/api/v1/notifications/preferences/${encodeURIComponent(type)}`, { enabled })
      .catch(() => {
        toast?.show({ message: t("screens.accountPage.notifications.refused", { type: t(`${typeKey(type)}.label`) }) });
        return client.invalidateQueries({ queryKey: PREFERENCES_KEY });
      });
  }

  return (
    <section className={section()} data-part="profile/notifications">
      <h2 className={sectionHeading()} data-part="heading">{t("screens.accountPage.notifications.heading")}</h2>
      <p className={guidance()} data-part="profile/notifications-guidance">
        {t("screens.accountPage.notifications.intro")}
      </p>
      <div className={factsPanel()} data-part="panel">
        <DeviceLine key={poseGeneration()} />
        {data.preferences.map((one) => (
          <div key={one.type} className={`${keyValueRow()} ${settingRow()}`} data-part="key-value"
            data-notification-type={one.type}>
            <div className="min-w-0">
              <div className="font-semibold">{t(`${typeKey(one.type)}.label`)}</div>
              <div className={qualityHint()}>{t(`${typeKey(one.type)}.description`)}</div>
            </div>
            <Switch checked={one.enabled} label={t(`${typeKey(one.type)}.label`)} data-part="switch"
              onClick={() => toggle(one.type, !one.enabled)} />
          </div>
        ))}
      </div>
    </section>
  );
}
