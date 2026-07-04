import type { ReactElement } from "react";
import { Link } from "react-router-dom";

import logoIcon from "@/assets/logo-icon.svg";
import { StatusDot } from "@/components/ds/StatusDot";
import { UserMenu } from "@/components/layout/UserMenu";

/**
 * TopBar — the shell's sticky header.
 *
 * Left: the TorrentMate logo mark + wordmark (a link home). Right: a
 * {@link StatusDot} reporting the real-time (WebSocket) connection state and the
 * {@link UserMenu}. The WS transport arrives in phase 6, so 5.2 shows a neutral
 * "Hors ligne" placeholder (wrapped in a `title`-bearing span — `StatusDot`'s
 * prop whitelist doesn't accept `title` directly).
 *
 * The top padding folds in `env(safe-area-inset-top)` so the bar clears the
 * status bar / notch when the PWA runs standalone.
 *
 * @returns The top bar element.
 */
export function TopBar(): ReactElement {
  return (
    <header className="sticky top-0 z-40 flex items-center gap-4 border-b border-border bg-background/85 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] backdrop-blur-sm md:px-6">
      <Link to="/" className="flex items-center gap-2">
        <img src={logoIcon} alt="" className="size-7" />
        <span className="text-sm font-semibold tracking-tight">
          Torrent<span className="text-primary">Mate</span>
        </span>
      </Link>
      <div className="ml-auto flex items-center gap-3">
        <span title="Connexion temps réel — à venir (phase 6)">
          <StatusDot status="idle" label="Hors ligne" />
        </span>
        <UserMenu />
      </div>
    </header>
  );
}
