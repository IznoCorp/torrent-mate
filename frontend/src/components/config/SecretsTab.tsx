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

// ---------------------------------------------------------------------------
// FR description override map — keyed by secret name.  The backend catalog
// parses the English comments from ``.env.example``; this map supplies the
// French translation.  When a secret key is absent from this map, the raw
// ``entry.description`` from the API is used as a fallback.
// ---------------------------------------------------------------------------

/** French description overrides keyed by secret env-var name. */
const FR_DESCRIPTIONS: Record<string, string> = {
  QBIT_USERNAME: "Nom d'utilisateur qBittorrent",
  QBIT_PASSWORD: "Mot de passe qBittorrent",
  TMDB_API_KEY: "Clé API TMDB",
  TVDB_API_KEY: "Clé API TVDB",
  TRAKT_CLIENT_ID: "Identifiant client Trakt (auth app-only)",
  TELEGRAM_BOT_TOKEN: "Jeton du bot Telegram",
  TELEGRAM_CHAT_ID: "Identifiant de discussion Telegram",
  HEALTHCHECK_URL: "URL du service Healthchecks.io",
  YOUTUBE_API_KEY: "Clé API YouTube Data v3",
  YOUTUBE_COOKIES_FILE: "Fichier cookies.txt YouTube (Netscape)",
  YOUTUBE_COOKIES_FROM_BROWSER: "Navigateur source pour cookies YouTube",
  OMDB_API_KEY: "Clé API OMDb",
  WEB_PASSWORD_HASH: "Hash du mot de passe web (scrypt)",
  WEB_JWT_SECRET: "Clé secrète pour les jetons JWT (HS256)",
  LACALE_PASSKEY: "Passkey LaCale",
  C411_PASSKEY: "Passkey C411",
};

/**
 * Resolve a French description for a secret key.
 *
 * Args:
 *   key: The env-var name (e.g. ``"TMDB_API_KEY"``).
 *   fallback: The raw description from the API catalog (English comments).
 *
 * Returns:
 *   The French description from {@link FR_DESCRIPTIONS}, or the fallback
 *   when the key is not mapped.
 */
function frDescription(key: string, fallback: string): string {
  return FR_DESCRIPTIONS[key] ?? fallback;
}

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
                {frDescription(entry.key, entry.description)}
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
