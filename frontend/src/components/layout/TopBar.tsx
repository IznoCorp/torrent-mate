import { Menu } from "lucide-react";
import type { ReactElement } from "react";
import { Link } from "react-router-dom";

import { BRAND_ICON } from "@/lib/env";
import { StatusDot, type PipelineStatus } from "@/components/ds/StatusDot";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { UserMenu } from "@/components/layout/UserMenu";
import type { ConnectionState } from "@/hooks/useEventStream";

/** Props for {@link TopBar}. */
interface TopBarProps {
  /** Opens the mobile navigation Sheet (fired by the hamburger, < md only). */
  readonly onOpenNav: () => void;
}

/**
 * How each live-stream connection state renders in the header StatusDot.
 *
 * The DS signal palette maps through {@link StatusDot}'s ``status`` prop:
 * ``done`` → success (green), ``running`` → warning (amber, animated), ``error``
 * → danger (red). "connecting" and "reconnecting" are both in-flight → warning.
 */
const CONNECTION_DISPLAY: Record<
  ConnectionState,
  {
    readonly status: PipelineStatus;
    readonly label: string;
    readonly title: string;
  }
> = {
  connecting: {
    status: "running",
    label: "Connexion…",
    title: "Connexion au flux temps réel…",
  },
  connected: {
    status: "done",
    label: "En ligne",
    title: "Flux temps réel connecté",
  },
  reconnecting: {
    status: "running",
    label: "Reconnexion…",
    title: "Reconnexion au flux temps réel…",
  },
  disconnected: {
    status: "error",
    label: "Hors ligne",
    title: "Flux temps réel interrompu",
  },
};

/**
 * TopBar — the shell's sticky header.
 *
 * Left: a hamburger button (< md only) opening the mobile navigation Sheet,
 * then the TorrentMate logo mark + wordmark (a link home). Right: a
 * {@link StatusDot} reporting the real-time (WebSocket) connection state — read
 * from the shared {@link useEventStreamContext} — and the {@link UserMenu}. The
 * dot is wrapped in a `title`-bearing span (a French tooltip) because
 * `StatusDot`'s prop whitelist doesn't accept `title` directly.
 *
 * The top padding folds in `env(safe-area-inset-top)` so the bar clears the
 * status bar / notch when the PWA runs standalone.
 *
 * Args:
 *   onOpenNav: Opens the mobile navigation Sheet (owned by {@link AppShell}).
 *
 * @returns The top bar element.
 */
export function TopBar({ onOpenNav }: TopBarProps): ReactElement {
  const { connectionState } = useEventStreamContext();
  const display = CONNECTION_DISPLAY[connectionState];

  return (
    <header className="sticky top-0 z-40 flex items-center gap-4 border-b border-border bg-background/85 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] backdrop-blur-sm md:px-6">
      <button
        type="button"
        onClick={onOpenNav}
        aria-label="Ouvrir le menu de navigation"
        className="-ml-1 inline-flex size-11 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
      >
        <Menu className="size-5" aria-hidden="true" />
      </button>
      {/* Wordmark is redundant with the sidebar brand on desktop → mobile only. */}
      <Link to="/" className="flex items-center gap-2 md:hidden">
        <img src={BRAND_ICON} alt="" className="size-7" />
        <span className="text-sm font-semibold tracking-tight">
          Torrent<span className="text-primary">Mate</span>
        </span>
      </Link>
      <div className="ml-auto flex items-center gap-3">
        {/* Hide the connection label under sm so the longest state
            ("Reconnexion…") can't overflow the 375px header — the coloured dot
            and the title tooltip still carry the state. */}
        <span
          title={display.title}
          className="[&_.ps-dot__label]:hidden sm:[&_.ps-dot__label]:inline"
        >
          <StatusDot status={display.status} label={display.label} />
        </span>
        <UserMenu />
      </div>
    </header>
  );
}
