// What Compte asks the server for.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";

/** Who is signed in. */
export function useAccount() {
  return useQuery({
    queryKey: ["/api/auth/me"],
    queryFn: async () => toEngineShape<{ name: string; mail: string }>("ACCOUNT", await read("/api/auth/me")),
  });
}
