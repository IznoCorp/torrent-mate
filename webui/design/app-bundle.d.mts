// Types of `app-bundle.mjs`, for the maquette's suite.
export declare const LEAKS: ReadonlyArray<{ needle: RegExp; what: string }>;
export declare function findLeaks(
  files: Array<{ name: string; text: string }>,
): Array<{ file: string; needle: string; what: string }>;
export declare function isLeftOut(id: string): boolean;
export declare function leftOutModules(modules: Record<string, { renderedLength: number }>): string[];
export declare function shellRoot(harnessCss: string): string;
export declare function readSources(root: string, names: string[]): Array<{ name: string; text: string }>;
export declare function readBuilt(dist: string): Array<{ name: string; text: string }>;
