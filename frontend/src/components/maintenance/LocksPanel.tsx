/**
 * LocksPanel — pipeline lock and orphan monitoring (5.1 placeholder).
 *
 * Replaced with real implementation in a follow-up commit.
 */

import type { ReactElement } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function LocksPanel(): ReactElement {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Verrous</CardTitle>
        <CardDescription>Locks, sentinelles, orphelins</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Chargement des verrous…
        </p>
      </CardContent>
    </Card>
  );
}
