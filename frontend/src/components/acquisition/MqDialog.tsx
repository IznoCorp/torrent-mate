/**
 * MqDialog — the maquette's centered confirmation dialog (.dlgscrim/.dlg).
 *
 * One dialog grammar for every destructive/committing confirmation on the
 * Acquisition surface (§5 replace, §9 removal): title, one paragraph that
 * says what the action MEANS, cancel + one verb. Stays mounted so the
 * maquette's opacity/scale transitions play; `inert` while closed keeps the
 * hidden controls out of the tab order.
 */

import { useEffect, useRef, type ReactElement } from "react";

/** Props for {@link MqDialog}. */
export interface MqDialogProps {
  readonly open: boolean;
  readonly title: string;
  readonly text: string;
  readonly okLabel: string;
  /** Danger tone on the verb — the maquette's default. */
  readonly danger?: boolean;
  readonly okTestId?: string;
  readonly onOk: () => void;
  readonly onCancel: () => void;
}

/**
 * Render the maquette confirmation dialog.
 *
 * Args:
 *   props: See {@link MqDialogProps}.
 *
 * Returns:
 *   The scrim + dialog pair.
 */
export function MqDialog({
  open,
  title,
  text,
  okLabel,
  danger = true,
  okTestId,
  onOk,
  onCancel,
}: MqDialogProps): ReactElement {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    // Initial focus on the SAFE control: a destructive verb must be reached
    // deliberately, never by resting focus.
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onCancel]);

  return (
    <>
      <div
        className={`dlgscrim${open ? " open" : ""}`}
        aria-hidden="true"
        onClick={onCancel}
      />
      <div
        className={`dlg${open ? " open" : ""}`}
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        inert={!open}
      >
        <h3>{title}</h3>
        <p>{text}</p>
        <div className="dlgacts">
          <button
            ref={cancelRef}
            type="button"
            className="dlgbtn"
            onClick={onCancel}
          >
            Annuler
          </button>
          <button
            type="button"
            className={`dlgbtn${danger ? " danger" : ""}`}
            {...(okTestId != null ? { "data-testid": okTestId } : {})}
            onClick={onOk}
          >
            {okLabel}
          </button>
        </div>
      </div>
    </>
  );
}
