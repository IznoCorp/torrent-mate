/**
 * Réglages tab (#18) — the acquisition RANKING editor with live preview.
 *
 * Lets the operator tune how tracker releases are ranked before a grab: the
 * per-criterion weights, the categorical value scores (resolution / codec /
 * language / source / provider…), the seeders/size thresholds' weight, the
 * freeleech/silverleech bonuses and the minimum-seeders floor. Loading and
 * saving reuse the S4 config write-path verbatim (``useConfigFile`` /
 * ``usePutConfigFile`` on ``ranking.json5``) — a single write mechanism, with
 * the SHA-256 precondition (412 conflict) it already enforces. Every edit is
 * scored live against a representative sample set via
 * ``POST /api/acquisition/ranking/preview`` so the effect of a change is
 * visible immediately, without running a real search.
 *
 * Serves product-intent §1 (compréhensible sans être ingénieur) and §3
 * (l'opérateur garde la main sur ce qui est récupéré).
 */

import { useEffect, useMemo, useState, type ReactElement } from "react";
import { toast } from "sonner";

import {
  previewRanking,
  type RankingConfig,
  type RankingCriterion,
  type RankingPreviewResponse,
} from "@/api/acquisition";
import { ApiError } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfigFile, usePutConfigFile } from "@/hooks/useConfig";

/** French label for each scored field the ranking can carry. */
const FIELD_LABEL: Record<string, string> = {
  resolution: "Résolution",
  codec: "Codec vidéo",
  format: "Conteneur",
  audio: "Codec audio",
  language: "Langue / piste audio",
  source: "Source",
  seeders: "Sources (seeders)",
  size: "Taille",
  provider: "Tracker",
};

/** Read a number input, keeping the previous value on an unparseable entry. */
function parseNum(raw: string, fallback: number): number {
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

/** The ranking sub-object read out of the loaded ranking.json5 file. */
function readRanking(values: Record<string, unknown> | undefined): RankingConfig | undefined {
  if (!values) return undefined;
  const ranking = (values as { ranking?: RankingConfig }).ranking;
  return ranking ?? undefined;
}

/**
 * Editor for one categorical criterion's ``values`` (token → score) map.
 *
 * Existing tokens are editable in place (score) and removable; a small add-row
 * appends a new token (e.g. a new language marker), so the operator can grow
 * the preference list without touching JSON.
 */
function ValuesEditor({
  values,
  onChange,
}: {
  values: Record<string, number>;
  onChange: (next: Record<string, number>) => void;
}): ReactElement {
  const [newKey, setNewKey] = useState("");
  const [newScore, setNewScore] = useState("");

  const entries = Object.entries(values);

  return (
    <div className="flex flex-col gap-1.5">
      {entries.map(([key, score]) => (
        <div key={key} className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-sm">{key}</span>
          <Input
            type="number"
            value={String(score)}
            aria-label={`Score ${key}`}
            className="h-8 w-20"
            onChange={(e) => {
              onChange({ ...values, [key]: parseNum(e.target.value, score) });
            }}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Retirer ${key}`}
            onClick={() => {
              onChange(Object.fromEntries(entries.filter(([k]) => k !== key)));
            }}
          >
            ✕
          </Button>
        </div>
      ))}
      <div className="flex items-center gap-2 pt-1">
        <Input
          value={newKey}
          placeholder="valeur (ex. MULTI)"
          aria-label="Nouvelle valeur"
          className="h-8 min-w-0 flex-1"
          onChange={(e) => {
            setNewKey(e.target.value);
          }}
        />
        <Input
          type="number"
          value={newScore}
          placeholder="score"
          aria-label="Score de la nouvelle valeur"
          className="h-8 w-20"
          onChange={(e) => {
            setNewScore(e.target.value);
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={newKey.trim() === "" || newScore.trim() === ""}
          onClick={() => {
            onChange({ ...values, [newKey.trim()]: parseNum(newScore, 0) });
            setNewKey("");
            setNewScore("");
          }}
        >
          Ajouter
        </Button>
      </div>
    </div>
  );
}

/** One criterion block: field label + weight, then values or read-only thresholds. */
function CriterionCard({
  criterion,
  onChange,
}: {
  criterion: RankingCriterion;
  onChange: (next: RankingCriterion) => void;
}): ReactElement {
  const label = FIELD_LABEL[criterion.field] ?? criterion.field;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          poids
          <Input
            type="number"
            step="0.5"
            value={String(criterion.weight)}
            aria-label={`Poids ${label}`}
            className="h-8 w-20"
            onChange={(e) => {
              onChange({ ...criterion, weight: parseNum(e.target.value, criterion.weight) });
            }}
          />
        </label>
      </div>
      {criterion.values != null ? (
        <ValuesEditor
          values={criterion.values}
          onChange={(next) => {
            onChange({ ...criterion, values: next });
          }}
        />
      ) : criterion.thresholds != null ? (
        <p className="text-xs text-muted-foreground">
          Paliers ({criterion.prefer === "lower" ? "plus petit = mieux" : "plus grand = mieux"}) :{" "}
          {criterion.thresholds.map((t) => `${String(t.at)}→${String(t.score)}`).join(", ")}
          <span className="italic"> — ajustez le poids ci-dessus.</span>
        </p>
      ) : null}
    </div>
  );
}

/** The live-preview column: the sample releases scored under the current draft. */
function PreviewColumn({
  preview,
  error,
}: {
  preview: RankingPreviewResponse | null;
  error: string | null;
}): ReactElement {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3 lg:sticky lg:top-4">
      <h3 className="text-sm font-semibold">Aperçu du classement</h3>
      <p className="text-xs text-muted-foreground">
        Un échantillon représentatif classé avec vos réglages — l'effet est visible
        immédiatement, sans lancer de recherche.
      </p>
      {error != null && <p className="text-xs text-danger">{error}</p>}
      <ol className="flex flex-col gap-1.5">
        {(preview?.ranked ?? []).map((r, i) => (
          <li
            key={`${r.provider}-${r.title}-${String(i)}`}
            className="flex items-center gap-2 rounded-md bg-background px-2 py-1.5"
          >
            <span className="w-8 shrink-0 text-right text-sm font-semibold tabular-nums">
              {String(r.score)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs">{r.title}</span>
              <span className="flex flex-wrap gap-1 pt-0.5">
                <Badge tone="neutral">{r.provider}</Badge>
                {r.language != null && <Badge tone="info">{r.language}</Badge>}
                {r.is_freeleech && <Badge tone="success">freeleech</Badge>}
                {r.excluded && <Badge tone="danger">exclu (seeders)</Badge>}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/**
 * ReglagesPanel — the acquisition ranking editor (#18).
 *
 * Returns:
 *   The Réglages tab content: a two-column editor (criteria on the left, live
 *   preview on the right) driven by ``ranking.json5`` through the S4 write-path.
 */
export function ReglagesPanel(): ReactElement {
  const fileQ = useConfigFile("ranking.json5");
  const putFile = usePutConfigFile("ranking.json5");

  const loaded = useMemo(() => readRanking(fileQ.data?.values), [fileQ.data]);
  const [draft, setDraft] = useState<RankingConfig | null>(null);
  const [preview, setPreview] = useState<RankingPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Seed the draft once the file loads (and reset it after a successful save /
  // a conflict reload, which re-fetches the file at a new sha).
  useEffect(() => {
    if (loaded && draft === null) {
      setDraft(structuredClone(loaded));
    }
  }, [loaded, draft]);

  // Debounced live preview: score the current draft against the sample set.
  useEffect(() => {
    if (draft == null) return;
    const handle = setTimeout(() => {
      previewRanking(draft)
        .then((res) => {
          setPreview(res);
          setPreviewError(null);
        })
        .catch((err: unknown) => {
          setPreviewError(
            err instanceof ApiError ? err.message : "Aperçu indisponible.",
          );
        });
    }, 300);
    return () => {
      clearTimeout(handle);
    };
  }, [draft]);

  const isDirty =
    draft != null && loaded != null && JSON.stringify(draft) !== JSON.stringify(loaded);

  function setCriterion(index: number, next: RankingCriterion): void {
    setDraft((d) => {
      if (d == null) return d;
      const criteria = [...(d.criteria ?? [])];
      criteria[index] = next;
      return { ...d, criteria };
    });
  }

  async function handleSave(): Promise<void> {
    if (draft == null || fileQ.data == null) return;
    const values = { ...fileQ.data.values, ranking: draft };
    try {
      const res = await putFile.mutateAsync({ values, base_sha256: fileQ.data.sha256 });
      if (res.warnings.length > 0) toast.warning(res.warnings.join("\n"));
      toast.success("Réglages enregistrés — pris en compte à la prochaine recherche.");
      // Await the fresh server snapshot — setDraft(null) + the stale
      // in-memory cache causes the form to snap back to pre-save values (#372).
      const fresh = await fileQ.refetch();
      const freshLoaded = readRanking(fresh.data?.values);
      setDraft(freshLoaded ? structuredClone(freshLoaded) : null);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 412) {
          toast.error("Le fichier a changé entre-temps — rechargement.");
          // Same treatment: await the refetch and seed from its result.
          const fresh = await fileQ.refetch();
          const freshLoaded = readRanking(fresh.data?.values);
          setDraft(freshLoaded ? structuredClone(freshLoaded) : null);
          return;
        }
        if (err.status === 422) {
          toast.error(`Valeurs invalides : ${err.detail}`);
          return;
        }
        toast.error(err.message);
        return;
      }
      toast.error("Échec de l'enregistrement.");
    }
  }

  if (fileQ.isLoading) {
    return <p className="text-sm text-muted-foreground">Chargement des réglages…</p>;
  }
  if (fileQ.isError || draft == null) {
    return (
      <p className="text-sm text-danger">
        Impossible de charger les réglages de récupération (ranking.json5).
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="max-w-prose text-sm text-muted-foreground">
          Réglez la façon dont les versions trouvées sur les trackers sont classées
          avant d'être récupérées. Les modifications s'appliquent à la prochaine
          recherche automatique — aucun redémarrage nécessaire.
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!isDirty || putFile.isPending}
            onClick={() => {
              setDraft(loaded ? structuredClone(loaded) : null);
            }}
          >
            Réinitialiser
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={!isDirty || putFile.isPending}
            onClick={() => {
              void handleSave();
            }}
          >
            {putFile.isPending ? "Enregistrement…" : "Enregistrer"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <span className="text-sm font-medium">Général</span>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                seeders minimum
                <Input
                  type="number"
                  value={String(draft.min_seeders)}
                  aria-label="Seeders minimum"
                  className="h-8 w-20"
                  onChange={(e) => {
                    setDraft((d) =>
                      d ? { ...d, min_seeders: parseNum(e.target.value, d.min_seeders) } : d,
                    );
                  }}
                />
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                bonus freeleech
                <Input
                  type="number"
                  value={String(draft.bonuses?.freeleech ?? 0)}
                  aria-label="Bonus freeleech"
                  className="h-8 w-20"
                  onChange={(e) => {
                    setDraft((d) =>
                      d
                        ? {
                            ...d,
                            bonuses: {
                              freeleech: parseNum(e.target.value, d.bonuses?.freeleech ?? 0),
                              silverleech: d.bonuses?.silverleech ?? 0,
                            },
                          }
                        : d,
                    );
                  }}
                />
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                bonus silverleech
                <Input
                  type="number"
                  value={String(draft.bonuses?.silverleech ?? 0)}
                  aria-label="Bonus silverleech"
                  className="h-8 w-20"
                  onChange={(e) => {
                    setDraft((d) =>
                      d
                        ? {
                            ...d,
                            bonuses: {
                              freeleech: d.bonuses?.freeleech ?? 0,
                              silverleech: parseNum(e.target.value, d.bonuses?.silverleech ?? 0),
                            },
                          }
                        : d,
                    );
                  }}
                />
              </label>
            </div>
          </div>

          {(draft.criteria ?? []).map((criterion, index) => (
            <CriterionCard
              key={`${criterion.field}-${String(index)}`}
              criterion={criterion}
              onChange={(next) => {
                setCriterion(index, next);
              }}
            />
          ))}
        </div>

        <PreviewColumn preview={preview} error={previewError} />
      </div>
    </div>
  );
}
