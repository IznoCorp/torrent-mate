/**
 * ActionCatalog — the maintenance action registry browser.
 *
 * Fetches the static action registry once (``GET /api/maintenance/actions``,
 * ``staleTime: Infinity`` — the registry never changes at runtime) and renders
 * it grouped by category. Each group is a collapsible DS {@link Accordion}
 * section (X6) whose header shows the category label and its action count;
 * each action is a clickable DS Button tile carrying a risk badge and a
 * long-running indicator. Selecting an action opens {@link ActionForm} in a
 * shadcn ``<Dialog>``.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Clock } from "lucide-react";
import { useState, type ReactElement } from "react";

import {
  getActions,
  type ActionsResponse,
  type MaintenanceAction,
} from "@/api/maintenance";
import { ErrorState } from "@/components/ds/ErrorState";
import { ActionForm } from "@/components/maintenance/ActionForm";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Category = MaintenanceAction["category"];
type Risk = MaintenanceAction["risk"];

// ---------------------------------------------------------------------------
// Static presentation maps
// ---------------------------------------------------------------------------

/** Category render order (matches the DESIGN §5 grouping). */
const CATEGORY_ORDER: readonly Category[] = [
  "query",
  "scan",
  "repair",
  "clean",
  "analyze",
  "fix",
];

/** French labels for each action category. */
const CATEGORY_LABELS: Record<Category, string> = {
  query: "Requêtes",
  scan: "Scans",
  repair: "Réparations",
  clean: "Nettoyage",
  analyze: "Analyses",
  fix: "Corrections",
};

/** Badge tone + French label for each risk level. */
const RISK_BADGE: Record<
  Risk,
  { tone: "neutral" | "warning" | "danger"; label: string }
> = {
  ro: { tone: "neutral", label: "Lecture seule" },
  write: { tone: "warning", label: "Écriture" },
  destructive: { tone: "danger", label: "Destructif" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ActionCatalog — a card listing every registered maintenance action, grouped
 * by category into collapsible sections. Clicking an action opens its form in a
 * modal dialog.
 *
 * Returns:
 *   The action-catalog card element.
 */
export function ActionCatalog(): ReactElement {
  const { data, isLoading, isError }: UseQueryResult<ActionsResponse> =
    useQuery({
      queryKey: maintenanceKeys.actions,
      queryFn: getActions,
      staleTime: Infinity,
      refetchOnWindowFocus: false,
    });

  // The action whose form dialog is open, or null when closed.
  const [selected, setSelected] = useState<MaintenanceAction | null>(null);

  const actions = data?.actions ?? [];
  const counts = data?.category_counts ?? {};

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions</CardTitle>
        <CardDescription>
          Catalogue des commandes de maintenance
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isLoading && (
          <div className="flex flex-col gap-3" aria-busy="true">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}
        {isError && (
          <ErrorState title="Impossible de charger le catalogue d'actions." />
        )}

        {/* X6: the DS Accordion owns aria-expanded/aria-controls and the
            chevron affordance; each action tile is a DS outline Button so
            radius / focus-ring come from the system. All categories stay
            expanded by default (discovery), collapsible per item. */}
        {!isLoading && !isError && (
          <Accordion>
            {CATEGORY_ORDER.map((category) => {
              const items = actions.filter((a) => a.category === category);
              if (items.length === 0) return null;
              const count = counts[category] ?? items.length;

              return (
                <AccordionItem key={category} defaultOpen>
                  <AccordionTrigger className="text-sm font-semibold">
                    <span className="flex items-center gap-2">
                      <span>{CATEGORY_LABELS[category]}</span>
                      <Badge tone="neutral">{count}</Badge>
                    </span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {items.map((action) => {
                        const risk = RISK_BADGE[action.risk];
                        return (
                          <Button
                            key={action.id}
                            type="button"
                            variant="outline"
                            className="h-auto min-h-11 flex-col items-start justify-start gap-1.5 whitespace-normal p-3 text-left"
                            onClick={() => {
                              setSelected(action);
                            }}
                          >
                            <div className="flex w-full items-start justify-between gap-2">
                              <span className="text-sm font-medium">
                                {action.title}
                              </span>
                              <div className="flex shrink-0 items-center gap-1">
                                <Badge tone={risk.tone}>{risk.label}</Badge>
                                {action.long_running && (
                                  <Badge tone="neutral">
                                    <Clock aria-hidden="true" />
                                    long
                                  </Badge>
                                )}
                              </div>
                            </div>
                            <span className="text-xs font-normal text-muted-foreground">
                              {action.description}
                            </span>
                          </Button>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        )}

        {!isLoading && !isError && actions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Aucune action disponible.
          </p>
        )}
      </CardContent>

      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent>
          {selected !== null && (
            <ActionForm
              action={selected}
              onClose={() => {
                setSelected(null);
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
