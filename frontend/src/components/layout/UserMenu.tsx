import { LogOut } from "lucide-react";
import { useState, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthContext } from "@/hooks/useAuthContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * UserMenu — the account dropdown anchored to the right of the {@link TopBar}.
 *
 * The trigger is an avatar showing the authenticated user's initial (from the
 * {@link useAuthContext} session). The single action logs out via the context
 * `logout` (which clears the query cache) and then navigates to `/login` with
 * the router — no full page reload.
 *
 * @returns The user menu element.
 */
export function UserMenu(): ReactElement {
  const { user, logout } = useAuthContext();
  const navigate = useNavigate();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const username = user?.username;
  const initial =
    username !== undefined && username.length > 0
      ? username.charAt(0).toUpperCase()
      : "—";

  /**
   * End the session then leave for the login page.
   *
   * Navigation runs in `finally` so a failed logout request (e.g. the cookie is
   * already gone) still lands the user on `/login` rather than stranding them in
   * the shell.
   */
  async function handleLogout(): Promise<void> {
    setIsLoggingOut(true);
    try {
      await logout();
    } finally {
      void navigate("/login", { replace: true });
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="rounded-full"
          aria-label="Menu utilisateur"
        >
          <Avatar className="size-8">
            <AvatarFallback className="text-xs">{initial}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        <DropdownMenuLabel>{username ?? "Compte"}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          disabled={isLoggingOut}
          onSelect={() => {
            void handleLogout();
          }}
        >
          <LogOut className="size-4" aria-hidden="true" />
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
