import type { ReactElement } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { BrandMark } from "@/components/ds/BrandMark";
import { useAuthContext } from "@/hooks/useAuthContext";
import { LoginForm } from "@/components/LoginForm";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Validate a `redirect` query param into a safe in-app destination.
 *
 * Only same-origin absolute paths (a single leading ``/``) are honoured, so a
 * hostile `?redirect=` can never bounce the freshly-authenticated user off-site
 * (open-redirect guard). Anything else collapses to the app root ``/``:
 *
 * - ``null`` / not a string starting with ``/`` → ``/``
 * - protocol-relative ``//evil.example`` → ``/``
 * - backslash trick ``/\evil.example`` (some browsers normalise ``\`` to ``/``)
 *   → ``/``
 *
 * Args:
 *   raw: The raw ``redirect`` search-param value (or ``null`` when absent).
 *
 * Returns:
 *   A safe in-app path — the validated ``raw`` value, or ``/``.
 */
function resolveRedirect(raw: string | null): string {
  if (raw === null) {
    return "/";
  }
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) {
    return "/";
  }
  return raw;
}

/**
 * Login — the unauthenticated entry screen for TorrentMate.
 *
 * A single centered card on the dark DS control-deck surface: the TorrentMate
 * logo mark + wordmark (Geist) above the credential form. No shell chrome (no
 * navigation, no top bar). Mobile-first: the card is full-width up to a small
 * max width and stays vertically centered on every viewport.
 *
 * When the session is already authenticated (a direct visit while logged in, or
 * the instant a successful login flips `me` to authenticated), the page
 * redirects to the validated `?redirect` destination — else the app root. That
 * single {@link Navigate} realises the post-login "return where you were" flow;
 * the form has no redirect logic of its own.
 *
 * @returns The login page element (or a redirect when already authenticated).
 */
export default function Login(): ReactElement {
  const { isAuthenticated } = useAuthContext();
  const [searchParams] = useSearchParams();

  if (isAuthenticated) {
    return (
      <Navigate to={resolveRedirect(searchParams.get("redirect"))} replace />
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-6 font-sans text-foreground">
      <div className="flex flex-col items-center gap-3">
        <BrandMark className="size-12" />
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
