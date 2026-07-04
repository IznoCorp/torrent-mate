import { LogOut } from "lucide-react";
import type { ReactElement } from "react";

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
import { useLogout } from "@/hooks/useAuth";

/**
 * UserMenu — the account dropdown anchored to the right of the {@link TopBar}.
 *
 * The trigger is an avatar; sub-phase 5.3's `AuthProvider` will feed the real
 * username initial, so 5.2 shows a static "—" fallback. The single action logs
 * out via {@link useLogout} and hard-redirects to `/login` (5.3 refines this
 * into a router-aware navigation preserving the target path).
 *
 * @returns The user menu element.
 */
export function UserMenu(): ReactElement {
  const logout = useLogout();

  /** Fire the logout mutation, then leave for the login page. */
  function handleLogout(): void {
    logout.mutate();
    // 5.3 replaces this hard redirect with a router-aware navigation.
    window.location.assign("/login");
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
            <AvatarFallback className="text-xs">—</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        <DropdownMenuLabel>Compte</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          disabled={logout.isPending}
          onSelect={handleLogout}
        >
          <LogOut className="size-4" aria-hidden="true" />
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
