/**
 * SecretsTab — masked write-only editor for ``.env`` secrets.
 *
 * Lists every secret key from the catalog (``GET /api/config/secrets``) alongside
 * a masked password input.  The user never sees the current value — only whether
 * a key is set (``is_set``).  On save only keys the user actually typed into are
 * sent, so the backend never sees a pre-filled value and accidentally clears
 * existing secrets.
 */

import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useConfigSecrets, usePutConfigSecrets } from "@/hooks/useConfig";

/** Props for {@link SecretsTab}. */
export interface SecretsTabProps {
  /** When ``true`` all inputs and the save button are disabled (staging mode). */
  readonly readOnly?: boolean;
}

/**
 * SecretsTab — masked per-key editor with ``is_set`` chips.
 *
 * Args:
 *   props: {@link SecretsTabProps}.
 *
 * Returns:
 *   The secrets editor element.
 */
export function SecretsTab({
  readOnly = false,
}: SecretsTabProps): ReactElement {
  const secrets = useConfigSecrets();
  const putSecrets = usePutConfigSecrets();

  // Local edited values: Map<key, typed_value>.  Only keys present here are
  // sent on save — we never pre-fill the map from the server.
  const [edited, setEdited] = useState<Map<string, string>>(new Map());
  // Inline success state for the last save.
  const [saved, setSaved] = useState(false);

  if (secrets.isLoading) {
    return (
      <p className="text-sm text-muted-foreground py-4">
        Chargement des secrets…
      </p>
    );
  }

  if (secrets.isError) {
    return (
      <p className="text-sm text-danger py-4" role="alert">
        Erreur lors du chargement des secrets.
      </p>
    );
  }

  const entries = secrets.data?.secrets ?? [];

  /** Read the current local draft for a key. */
  function draft(key: string): string {
    return edited.get(key) ?? "";
  }

  /** Update the local draft for a single key. */
  function setDraft(key: string, value: string): void {
    setEdited((prev) => {
      const next = new Map(prev);
      if (value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      return next;
    });
  }

  /** Persist only the keys with a typed value. */
  async function handleSave(): Promise<void> {
    if (edited.size === 0) return;

    // Build {KEY: value} from the locally edited keys only.
    const body: Record<string, string> = {};
    for (const [k, v] of edited.entries()) {
      if (v !== "") body[k] = v;
    }
    if (Object.keys(body).length === 0) return;

    try {
      await putSecrets.mutateAsync(body);
      setEdited(new Map());
      setSaved(true);
      toast.success("Secrets enregistrés.");
    } catch (err: unknown) {
      toast.error(
        err instanceof ApiError
          ? err.detail
          : "Échec de l’enregistrement des secrets.",
      );
    }
  }

  const hasEdits = edited.size > 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Secrets</h2>
      </div>

      {entries.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Aucun secret déclaré dans le catalogue.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {entries.map((entry) => (
          <div
            key={entry.key}
            className="flex flex-col gap-1.5 rounded-md border border-border p-3"
          >
            {/* Long env-var keys + the badge must wrap at 390px (the row was
                the /config mobile horizontal-overflow offender). */}
            <div className="flex flex-wrap items-center gap-2">
              <Label className="min-w-0 break-all text-sm font-medium">
                {entry.key}
              </Label>
              <Badge tone={entry.is_set ? "success" : "neutral"} mono>
                {entry.is_set ? "défini" : "non défini"}
              </Badge>
            </div>

            {entry.description && (
              <p className="text-xs break-words text-muted-foreground">
                {entry.description}
              </p>
            )}

            <Input
              type="password"
              autoComplete="off"
              placeholder={entry.is_set ? "•••• (défini)" : "non défini"}
              disabled={readOnly}
              value={draft(entry.key)}
              onChange={(e) => {
                setDraft(entry.key, e.target.value);
              }}
            />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <Button
          type="button"
          disabled={readOnly || !hasEdits || putSecrets.isPending}
          onClick={() => {
            void handleSave();
          }}
        >
          {putSecrets.isPending ? "Enregistrement…" : "Enregistrer les secrets"}
        </Button>

        {saved && (
          <span className="text-sm text-success">
            ✓ Secrets enregistrés — un redémarrage peut être requis.
          </span>
        )}
      </div>
    </div>
  );
}
