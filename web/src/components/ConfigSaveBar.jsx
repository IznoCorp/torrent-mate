// Save / validate action bar for config-editing panels (columns, transitions). On mobile it is
// FIXED to the viewport bottom (not `sticky` — sticky only pins while the container scrolls past it,
// so on a short form it floated mid-page) and spans the screen edge-to-edge with an iOS safe-area
// inset, keeping the save action under the thumb. On desktop it sits inline at the foot of the panel.
// Saves the WHOLE config draft (shared dirty flag drives the label). `onValidate` is optional.
import React from "react";
import { useT } from "../i18n/index.jsx";
import useIsMobile from "../useIsMobile.js";

const { Button } = window.KanbanMateDesignSystem_2463ad;

export default function ConfigSaveBar({
  onSave,
  onValidate,
  saving = false,
  dirty = false,
}) {
  const { t } = useT();
  const isMobile = useIsMobile();

  const buttons = (
    <>
      {onValidate && (
        <Button
          variant="outline"
          onClick={onValidate}
          disabled={saving}
          style={isMobile ? { flex: 1 } : undefined}
        >
          {t("transitions.validate_btn", "Validate")}
        </Button>
      )}
      <Button
        variant="primary"
        onClick={onSave}
        loading={saving}
        disabled={saving || !dirty}
        style={isMobile ? { flex: 2 } : undefined}
      >
        {dirty
          ? t("transitions.save_btn", "Save changes")
          : t("transitions.saved", "Saved ✓")}
      </Button>
    </>
  );

  if (isMobile) {
    // Fixed to the screen bottom, full-width. A spacer reserves the bar's height in normal flow so
    // the last form fields are never hidden behind it.
    return (
      <>
        <div style={{ height: 74 }} aria-hidden />
        <div
          style={{
            position: "fixed",
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 30,
            display: "flex",
            gap: 10,
            padding:
              "10px 14px calc(10px + env(safe-area-inset-bottom, 0px)) 14px",
            borderTop: "1px solid var(--border)",
            background: "var(--card)",
            boxShadow: "0 -6px 18px rgba(0,0,0,.22)",
          }}
        >
          {buttons}
        </div>
      </>
    );
  }

  return (
    <div
      style={{
        position: "sticky",
        bottom: 0,
        zIndex: 2,
        display: "flex",
        gap: 10,
        flexWrap: "wrap",
        justifyContent: "flex-end",
        marginTop: 16,
        padding: "12px 0",
        borderTop: "1px solid var(--border)",
        background: "var(--background)",
      }}
    >
      {buttons}
    </div>
  );
}
