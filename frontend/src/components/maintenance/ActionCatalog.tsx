/**
 * ActionCatalog — the maintenance action registry browser.
 *
 * Fetches the static action registry once (``GET /api/maintenance/actions``,
 * ``staleTime: Infinity`` — the registry never changes at runtime) and renders
 * it grouped by category. Each group is a collapsible section (plain React
 * state) whose header shows the category label and its action count; each
 * action is a clickable card carrying a risk badge and a long-running
 * indicator. Selecting an action opens {@link ActionForm} in a shadcn
 * ``<Dialog>``.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Clock } from "lucide-react";
import { useState, type ReactElement } from "react";

import {
  getActions,
  type ActionsResponse,
  type MaintenanceAction,
} from "@/api/maintenance";
import { ActionForm } from "@/components/maintenance/ActionForm";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
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

  // Categories the user has collapsed (all expanded by default for discovery).
  const [collapsed, setCollapsed] = useState<ReadonlySet<Category>>(new Set());
  // The action whose form dialog is open, or null when closed.
  const [selected, setSelected] = useState<MaintenanceAction | null>(null);

  const actions = data?.actions ?? [];
  const counts = data?.category_counts ?? {};

  /** Toggle a category's collapsed state. */
  function toggleCategory(category: Category): void {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }

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
          <p className="text-sm text-muted-foreground">
            Chargement des actions…
          </p>
        )}
        {isError && (
          <p className="text-sm text-muted-foreground">
            Erreur lors du chargement.
          </p>
        )}

        {!isLoading &&
          !isError &&
          CATEGORY_ORDER.map((category) => {
            const items = actions.filter((a) => a.category === category);
            if (items.length === 0) return null;
            const count = counts[category] ?? items.length;
            const isCollapsed = collapsed.has(category);

            return (
              <section key={category} className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => {
                    toggleCategory(category);
                  }}
                  aria-expanded={!isCollapsed}
                  className="flex items-center gap-2 text-left text-sm font-semibold"
                >
                  {isCollapsed ? (
                    <ChevronRight
                      className="size-4 shrink-0"
                      aria-hidden="true"
                    />
                  ) : (
                    <ChevronDown
                      className="size-4 shrink-0"
                      aria-hidden="true"
                    />
                  )}
                  <span>{CATEGORY_LABELS[category]}</span>
                  <Badge tone="neutral">{count}</Badge>
                </button>

                {!isCollapsed && (
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {items.map((action) => {
                      const risk = RISK_BADGE[action.risk];
                      return (
                        <button
                          key={action.id}
                          type="button"
                          onClick={() => {
                            setSelected(action);
                          }}
                          className="flex flex-col gap-1.5 rounded-md border border-border bg-card p-3 text-left transition-colors hover:bg-accent"
                        >
                          <div className="flex items-start justify-between gap-2">
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
                          <span className="text-xs text-muted-foreground">
                            {action.description}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}

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
