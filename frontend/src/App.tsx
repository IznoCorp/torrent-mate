import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "@/api/client";
import { AuthProvider } from "@/components/AuthProvider";
import { router } from "@/router";

/**
 * App — the TorrentMateUI root.
 *
 * Provider order (outer → inner): the shared TanStack Query client (with its
 * global 401 policy) → `AuthProvider` → `RouterProvider`. `AuthProvider` sits
 * **above** the router on purpose: its single `me` observer must survive route
 * changes and drive the shell's auth guard. Because it is above the router it
 * never navigates itself — the router-aware pieces (`RouterBridge`, the guard,
 * the login redirect, the user-menu logout) do that from inside the router tree.
 *
 * @returns The application root element.
 */
export default function App(): ReactElement {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  );
}
