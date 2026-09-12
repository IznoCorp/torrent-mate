// What the two acts on a secret DO — B-334 and B-335.
//
// Both carried `target: { toast: … }`. A panel action's `target` IS its `data-*`
// map (`ui/panel/contract.ts`) and `ui/panel` attaches no handler of its own, so
// what those two buttons emitted was a SENTENCE: nothing was written anywhere,
// and the operator's reading — « ne fait rien » — was exactly right. The worse
// half is the one that did not show: an interface that says a key was replaced
// over a replacement nobody made is NE-DOIT-PAS-1.
//
// A FILE OF ITS OWN beside the producer, on `journey-verbs.ts`'s pattern: a
// verb is behaviour, a producer is a function from the cache to a descriptor.
//
// AND THE VALUE IS READ AT THE MOMENT OF THE TAP. The input lives in the panel
// (`panel-secret-field.tsx`); nothing holds a copy of what was typed, so a
// secret exists in exactly one place between the keyboard and the layer.
import i18next from "i18next";
import { HELD } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";
import { configurationStatusQuery, secretsQuery, writeSecret } from "./queries";

/** What the layer is asked, and what each outcome is called. */
type Act = "replace" | "remove";

/**
 * Writes one secret's value — or clears it — and says what happened.
 *
 * THE MESSAGE COMES FROM WHAT CAME BACK, never from the tap. A write the outbox
 * HELD is not a write that landed, and saying « remplacée » over one would be
 * the defect this repairs, one layer down (P8's own discipline, `app/outbox.ts`).
 *
 * Args:
 *     act: Which of the two was asked for.
 *     key: The secret's key.
 *     value: What to write — the empty string clears the key.
 */
async function writeTheKey(act: Act, key: string, value: string): Promise<void> {
  const say = (outcome: string) => i18next.t(`verbs.secret.${act}${outcome}`);
  try {
    const answered = await writeSecret(key, value);
    if (answered === HELD) {
      window.__toast?.show({ message: say("Held") });
      return;
    }
    // THE SURFACES ARE RE-READ, because « posée » / « absente » is what the row
    // and the chip both draw and neither subscribes to a call. A refetch rather
    // than an invalidation for the panel's sake: a producer is a function from
    // the cache to a descriptor, so nothing is observing this key while the
    // panel is open (measured once already, `journey-verbs.ts`).
    await window.__queries?.refetchQueries({ queryKey: secretsQuery.queryKey });
    await window.__queries?.invalidateQueries({
      queryKey: configurationStatusQuery.queryKey });
    window.__panel?.close();
    window.__referentiel.render();
    window.__toast?.show({ message: say("Done") });
  } catch {
    window.__toast?.show({ message: say("Refused") });
  }
}

/** What the reader has typed into the secret's own field, or the empty string. */
function typedKey(key: string): string {
  const field = document.querySelector<HTMLInputElement>(
    `#sheetin [data-part="secret/input"][data-secret-key="${CSS.escape(key)}"]`);
  return field?.value ?? "";
}

/**
 * Asks before cutting a provider for the household (B-335, §17).
 *
 * THE SENTENCE SAYS WHAT THE CONFIRMATION IS FOR rather than « êtes-vous
 * sûr ? »: the key goes for every
 * account of the household, and the provider stops answering until a new one is
 * entered. Cancelling leaves the key exactly where it was and says nothing —
 * a confirmation one can only tap through is a delay.
 */
function askToRemove(key: string, label: string): void {
  const translate = i18next.t.bind(i18next);
  window.__dialog?.open({
    heading: translate("panels.secret.removeConfirmHeading", { provider: label }),
    body: [
      {
        type: "paragraph",
        runs: [{ text: translate("panels.secret.removeConfirmBody") }],
      },
    ],
    actions: [
      {
        text: translate("panels.secret.removeConfirmGo"),
        tone: "danger",
        target: { "data-confirm-remove-secret": key },
      },
      {
        text: translate("panels.secret.removeConfirmCancel"),
        tone: "ghost",
        dismiss: true,
      },
    ],
  });
}

/* THE THREE VERBS, declared at module evaluation and named once in
   `app/panel-contributions.ts`.

   THE CACHE IS REACHED THROUGH `window.__queries` rather than through a client
   handed in at boot, and that is this file's neighbour's own choice:
   `panel-setting.ts` invalidates through the same seam, one directory entry
   away, because a producer is called from a tap and has no hook to read a
   client from either. Taking one here would be a second door onto one cache
   inside one feature. */
registerVerb("replacesecret", (key) => {
  const typed = typedKey(key);
  // AN EMPTY FIELD IS NOT A REMOVAL. The layer clears a key on an empty value,
  // so sending one from here would turn « Remplacer » into « Retirer » with no
  // confirmation at all — the destructive act by the harmless door.
  if (!typed) {
    window.__toast?.show({ message: i18next.t("verbs.secret.replaceEmpty") });
    return;
  }
  void writeTheKey("replace", key, typed);
});

registerVerb("removesecret", (key) => {
  // THE PROVIDER IS NAMED FROM THE LAYER, never from the panel's own heading:
  // the question names what is about to stop answering, and reading it off the
  // screen would make the sentence depend on how the panel happens to be drawn
  // at that moment.
  const held = window.__queries?.getQueryData<{ k: string; l: string }[]>(
    secretsQuery.queryKey) ?? [];
  askToRemove(key, held.find((one) => one.k === key)?.l ?? key);
});

registerVerb("confirm-remove-secret", (key) => {
  window.__dialog?.close();
  void writeTheKey("remove", key, "");
});
