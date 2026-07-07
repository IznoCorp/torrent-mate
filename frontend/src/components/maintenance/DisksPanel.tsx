/**
 * DisksPanel — storage disk monitoring (5.1 placeholder).
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

export function DisksPanel(): ReactElement {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Disques</CardTitle>
        <CardDescription>Espace et statut de montage</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Chargement des disques…
        </p>
      </CardContent>
    </Card>
  );
}
