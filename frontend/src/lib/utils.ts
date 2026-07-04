import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge conditional class names, resolving Tailwind conflicts last-wins.
 *
 * The shadcn/ui convention: `clsx` flattens the conditional inputs, then
 * `tailwind-merge` deduplicates conflicting Tailwind utilities (e.g. two
 * `px-*` classes) keeping the last one.
 *
 * @param inputs Class values (strings, arrays, or conditional objects).
 * @returns The merged, conflict-resolved class string.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
