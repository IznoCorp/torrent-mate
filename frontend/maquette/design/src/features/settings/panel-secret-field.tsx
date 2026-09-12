// Where a new key is TYPED, inside the secret's own panel.
//
// A secret's value travels one way: the layer answers which keys exist and
// whether each is defined, never what one holds (`panel-secret.ts`). So the
// panel could SAY « Remplacer la valeur » and had nowhere to put one — which is
// half of why that action was a sentence and not an act (B-334).
//
// IT IS A BLOCK, not a field of the producer's descriptor, for the same reason
// the setting's field is one: `ui/panel` is a primitive and does not know what
// a secret is. The block is declared here, beside what draws it, so the two
// halves of the contract cannot drift apart.
//
// THE VALUE NEVER LEAVES THIS ELEMENT except through the act that writes it.
// It is not held in React state, not put in the descriptor, and not read back:
// the verb reads the input at the moment of the tap and sends it. A value that
// lived anywhere else would be a second copy of a secret.
import { useTranslation } from "react-i18next";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { fieldInput, panelField } from "./variants";

declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    secretKey: { key: string };
  }
}

function SecretKeyBlock({
  block,
}: {
  block: { type: "secretKey" } & PanelBlockMap["secretKey"];
}) {
  const { t } = useTranslation();
  return (
    <div className={panelField()} data-part="secret/field">
      <input
        className={fieldInput({ mono: true })}
        data-part="secret/input"
        data-secret-key={block.key}
        // `password`, so a key is not read over a shoulder while it is typed,
        // and `off` on every assistance a browser offers: a secret in an
        // autofill store is a secret in one more place.
        type="password"
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        aria-label={t("panels.secret.newKeyLabel")}
        placeholder={t("panels.secret.newKeyPlaceholder")}
      />
    </div>
  );
}

registerBlock("secretKey", (block) => <SecretKeyBlock block={block} />);
