// A secret's panel — what a row of the Secrets rubric raises.
//
// It lives with Configuration because that is what makes it change: which keys
// exist, and whether each is set. A secret's VALUE is never read back and never
// drawn — the panel says the key is posed, never what it is worth — and that is
// the whole sentence its note carries.
//
// A PRODUCER IS NOT A HOOK: it is called from the click delegation, so it reads
// the query cache synchronously (invariant 10).
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { secretsQuery } from "./queries";
import type { Secret } from "./reference";

// THE ICONS COME THROUGH THE ENGINE'S DRAWING SLICE, not by importing
// `app/icons.ts`, and it is invariant 8 that decides. `app/icons.ts` is outside
// `ui/` and `lib/`, so the fan-in ceiling applies to it — four features — and a
// producer per feature importing it directly walked it to five in one phase,
// which is « no god module » arriving exactly where the guard was aimed. Every
// other drawing helper in this tree comes through the same door
// (`lib/engine-drawing.ts`), it is the SAME object either way, and it dies with
// the engine — at which point `app/icons.ts` is the durable home and this line
// is the one that changes.
const icons = () => window.__referentiel.icons;

/**
 * Finds one secret among those the layer answered.
 *
 * Args:
 *     key: The secret's key, as the row spells it.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The secret, or null when the layer has not answered or does not carry it.
 */
function secretOf(key: string, cache: PanelCache): Secret | null {
  const secrets = cache.held<Secret[]>(secretsQuery.queryKey);
  return secrets?.find((secret) => secret.k === key) ?? null;
}

/**
 * Builds a secret's descriptor.
 *
 * Args:
 *     key: The secret's key.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null for a key the layer does not carry.
 */
function secretPanel(key: string, cache: PanelCache): PanelDescriptor | null {
  const secret = secretOf(key, cache);
  if (secret === null) return null;
  const translate = i18next.t.bind(i18next);
  // READ-ONLY IS THE ENGINE'S MUTABLE STATE, not server state and not this
  // feature's yet: it moves with the last delegation verb that writes it, and
  // that is the engine's last lot. Read through the same slice the page reads,
  // so the panel and the page cannot disagree about the instance's rights.
  const readOnly = Boolean(window.__referentiel.SETTINGS_STATE.readOnly);
  return {
    title: secret.l,
    meta: [{ m: secret.k }],
    puce: secret.def
      ? ["success", translate("panels.secret.set")]
      : ["warning", translate("panels.secret.absent")],
    blocs: [
      { type: "note", text: translate("panels.secret.neverReturned") },
      {
        type: "actions",
        actions: [
          readOnly
            ? {
                text: translate("panels.secret.readOnly"),
                icone: icons().x,
                desactive: true,
              }
            : {
                text: translate("panels.secret.replace"),
                icone: icons().wrench,
                ton: "primary",
                target: { toast: translate("panels.secret.replaceToast") },
              },
          secret.def
            ? {
                text: translate("panels.secret.removeKey"),
                icone: icons().trash,
                ton: "danger",
                target: { toast: translate("panels.secret.removeKeyToast") },
              }
            : null,
        ],
      },
    ],
  };
}

registerProducer("secret", {
  produce: secretPanel,
  needs: [secretsQuery],
  holds: (key, cache) => secretOf(key, cache) !== null,
});
