// A persistent "Install" affordance for the PWA. Chrome shows its own install mini-infobar only
// once (and never if dismissed/already-installed), so we capture the `beforeinstallprompt` event
// (in main.jsx) and expose an explicit button that re-offers it on demand. The button only renders
// when the app is actually installable (event captured, not yet installed); on browsers that don't
// fire the event (e.g. iOS Safari) it stays hidden — there, install is Share → Add to Home Screen.
import React from "react";
import { useT } from "../i18n/index.jsx";
import { Download } from "lucide-react";

const { Button, Tooltip } = window.KanbanMateDesignSystem_2463ad;

export default function PwaInstallButton({ size = "sm" }) {
  const { t } = useT();
  const [available, setAvailable] = React.useState(
    typeof window !== "undefined" && !!window.__pwaPrompt,
  );

  React.useEffect(() => {
    const onAvail = () => setAvailable(!!window.__pwaPrompt);
    const onInstalled = () => setAvailable(false);
    window.addEventListener("pwa-installable", onAvail);
    window.addEventListener("pwa-installed", onInstalled);
    return () => {
      window.removeEventListener("pwa-installable", onAvail);
      window.removeEventListener("pwa-installed", onInstalled);
    };
  }, []);

  if (!available) return null;

  const install = async () => {
    const evt = window.__pwaPrompt;
    if (!evt) return;
    evt.prompt();
    try {
      await evt.userChoice;
    } catch (_) {
      /* user dismissed — ignore */
    }
    // A given prompt event can only be used once.
    window.__pwaPrompt = null;
    setAvailable(false);
  };

  return (
    <Tooltip
      label={t("tip.install", "Install KanbanMate as an app")}
      placement="bottom"
    >
      <Button
        variant="secondary"
        size={size}
        leadingIcon={<Download size={14} strokeWidth={2} />}
        onClick={install}
      >
        {t("common.install", "Install")}
      </Button>
    </Tooltip>
  );
}
