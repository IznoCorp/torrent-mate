import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "@/api/client";
import { router } from "@/router";

/**
 * App — the TorrentMateUI root.
 *
 * Wires the shared TanStack Query client (with its global 401 policy) around the
 * React Router provider. Sub-phase 5.3 layers an `AuthProvider` between these two
 * so the shell's auth guard can read the session; 5.2 mounts the router without
 * a guard (login stays public, the shell reachable at `/`).
 *
 * @returns The application root element.
 */
export default function App(): ReactElement {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
