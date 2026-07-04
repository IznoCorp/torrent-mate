import type { ReactElement } from "react";

import logoIcon from "@/assets/logo-icon.svg";
import { LoginForm } from "@/components/LoginForm";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Login — the unauthenticated entry screen for TorrentMate.
 *
 * A single centered card on the dark DS control-deck surface: the TorrentMate
 * logo mark + wordmark (Geist) above the credential form. No shell chrome (no
 * navigation, no top bar) — the app shell and its route-level auth guard arrive
 * in sub-phases 5.2 and 5.3. Mobile-first: the card is full-width up to a small
 * max width and stays vertically centered on every viewport.
 *
 * @returns The login page element.
 */
export default function Login(): ReactElement {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-6 font-sans text-foreground">
      <div className="flex flex-col items-center gap-3">
        <img src={logoIcon} alt="" className="size-12" />
        <span className="text-2xl font-semibold tracking-tight">
          Torrent<span className="text-primary">Mate</span>
        </span>
      </div>

      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-lg">Connexion</CardTitle>
          <CardDescription>
            Identifiez-vous pour accéder à votre tableau de bord.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm />
        </CardContent>
      </Card>
    </main>
  );
}
