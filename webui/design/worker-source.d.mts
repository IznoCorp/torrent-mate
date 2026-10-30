// Types of `worker-source.mjs`, for the maquette's suite.
export declare const PLACEHOLDERS: readonly string[];
export declare function pushTexts(catalogue: unknown, name?: string): Record<string, unknown>;
export declare function pushCatalogues(catalogues: { fr: unknown; en: unknown }): Record<"fr" | "en", Record<string, unknown>>;
export declare function substituteWorker(
  source: string,
  values: { build: string; shell: string[]; extras: string[]; push: Record<string, unknown> },
): string;
