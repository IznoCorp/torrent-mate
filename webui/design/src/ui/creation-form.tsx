// A CREATION OPENS ITS OWN PAGE, WITH A VALIDATED FORM (the operator, 2026-10-04:
// « dès qu'on a des créations dans ce genre il faut préférer une page et un
// formulaire avec validation plutôt que tout mettre en vrac sur une page »).
//
// ONE DRAWING FOR EVERY CREATION, so the next one is not re-decided: the screen
// over the page the creation belongs to, its back, its heading; each field with
// its label, its REQUIRED mark, and what is wrong said UNDER IT; the act last,
// closed until the form is valid. What a field holds and when it is wrong is the
// feature's.
//
// IT KNOWS NO DOMAIN: no field, no word, no operation — the caller hands its
// words and its controls in.
import type { ReactElement, ReactNode } from "react";

import { useEngineDrawing } from "../lib/engine-drawing";
import { bridge } from "../lib/shell-doors";
import { Icon } from "./icon";
import {
  actionButton, backAction, body, creationForm, factName, fieldError, fieldHint, formField, guidance, requiredMark, screen,
  screenBar, scrollport,
} from "./variants";

/**
 * A creation's page: a screen over the page it belongs to, its way back, its heading.
 *
 * @param props.screenKey The screen's key — `data-key`, and its body's region.
 * @param props.title What is created, as a heading.
 * @param props.back The words of the way back: the page it returns to.
 * @param props.lead A sentence under the heading, when the creation needs one.
 * @param props.children The form.
 * @returns The screen.
 */
export function CreationScreen({ screenKey, title, back, lead, children }: {
  screenKey: string;
  title: string;
  back: string;
  lead?: string;
  children: ReactNode;
}): ReactElement {
  const { icons } = useEngineDrawing();
  return (
    <section className={screen({ open: true })} data-part="screen" data-open="" data-key={screenKey} aria-label={title}>
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => bridge.back()}>
          <Icon paths={icons.left} />
          {back}
        </button>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="surface/body" data-region={`screen-${screenKey}/body`}>
          <h1 className={factName()}>{title}</h1>
          {lead ? <p className={guidance()}>{lead}</p> : null}
          {children}
        </div>
      </div>
    </section>
  );
}

/**
 * One field: its label — marked when it is required —, its control, what is
 * wrong with it, and its guidance.
 *
 * @param props.name The field's name — the control's `name`, and the error's `data-field-error`.
 * @param props.label Its words.
 * @param props.required Whether the form is invalid without it.
 * @param props.requiredWords How the required mark is said to a screen reader.
 * @param props.error What is wrong with it, or null.
 * @param props.hint Its guidance, when it has some.
 * @param props.children The control.
 * @returns The field.
 */
export function Field({ name, label, required, requiredWords, error, hint, children }: {
  name: string;
  label: string;
  required: boolean;
  requiredWords: string;
  error: string | null;
  hint?: string;
  children: ReactNode;
}): ReactElement {
  return (
    <div className={formField()} data-part="creation/field" data-field={name}>
      <label htmlFor={`creation-${name}`}>
        {label}
        {required ? <span className={requiredMark()} aria-label={requiredWords}> *</span> : null}
      </label>
      {children}
      {error ? (
        <p className={fieldError()} id={`creation-${name}-error`} role="alert" data-field-error={name}>{error}</p>
      ) : null}
      {hint ? <p className={fieldHint()}>{hint}</p> : null}
    </div>
  );
}

/**
 * The form around the fields, and its act — closed until the form is valid.
 *
 * @param props.onSubmit What Create does, once the form is valid.
 * @param props.valid Whether every field holds what it must.
 * @param props.sending Whether the creation is under way.
 * @param props.act The act's words; `sendingAct` while it is under way.
 * @param props.children The fields.
 * @returns The form.
 */
export function CreationForm({ onSubmit, valid, sending, act, sendingAct, children }: {
  onSubmit: () => void;
  valid: boolean;
  sending: boolean;
  act: string;
  sendingAct: string;
  children: ReactNode;
}): ReactElement {
  return (
    <form className={creationForm()} data-part="creation/form" noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (valid && !sending) onSubmit();
      }}>
      {children}
      <button className={actionButton({ kind: "cardFoot", tone: "solid" })} type="submit" data-part="creation/submit"
        disabled={!valid || sending}>
        {sending ? sendingAct : act}
      </button>
    </form>
  );
}
