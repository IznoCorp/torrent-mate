/**
 * IndexHealthPanel — library.db aggregate health (5.1 placeholder).
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

export function IndexHealthPanel(): ReactElement {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Santé de l'index</CardTitle>
        <CardDescription>Base library.db</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Chargement de l'index…
        </p>
      </CardContent>
    </Card>
  );
}
