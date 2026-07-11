/**
 * Accordion — a lightweight collapsible section primitive.
 *
 * No ``@radix-ui/react-accordion`` dependency is installed (checked in
 * ``package.json``), so this is a self-contained controlled/uncontrolled
 * implementation with the shadcn-style compound API
 * (``Accordion`` / ``AccordionItem`` / ``AccordionTrigger`` /
 * ``AccordionContent``). Each item manages its own open state; the trigger is a
 * real ``<button>`` wired with ``aria-expanded`` + ``aria-controls`` and the
 * content region carries ``role="region"`` so the disclosure is accessible
 * (webui-ux Phase 2.3).
 */

import {
  createContext,
  useContext,
  useId,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

/** Internal per-item disclosure state shared by trigger + content. */
interface AccordionItemContextValue {
  /** Whether the item is currently expanded. */
  readonly open: boolean;
  /** Toggle the item's expanded state. */
  readonly toggle: () => void;
  /** Stable id linking the trigger (``aria-controls``) to the content region. */
  readonly contentId: string;
  /** Stable id linking the content region back to the trigger. */
  readonly triggerId: string;
}

const AccordionItemContext = createContext<AccordionItemContextValue | null>(
  null,
);

/**
 * Read the enclosing {@link AccordionItem} context.
 *
 * Args:
 *   part: The sub-component name, for a clear error when used out of context.
 *
 * Returns:
 *   The item context value.
 *
 * Throws:
 *   Error when rendered outside an {@link AccordionItem}.
 */
function useAccordionItem(part: string): AccordionItemContextValue {
  const ctx = useContext(AccordionItemContext);
  if (ctx === null) {
    throw new Error(`${part} must be used within an <AccordionItem>`);
  }
  return ctx;
}

/** Props for {@link Accordion}. */
export interface AccordionProps {
  /** The accordion items. */
  readonly children: ReactNode;
  /** Optional wrapper class. */
  readonly className?: string;
}

/**
 * Accordion — a thin vertical container for one or more {@link AccordionItem}s.
 *
 * Args:
 *   children: The accordion items.
 *   className: Optional wrapper class.
 *
 * Returns:
 *   The accordion container element.
 */
export function Accordion({
  children,
  className,
}: AccordionProps): ReactElement {
  return (
    <div data-slot="accordion" className={cn("flex flex-col", className)}>
      {children}
    </div>
  );
}

/** Props for {@link AccordionItem}. */
export interface AccordionItemProps {
  /** The trigger + content for this item. */
  readonly children: ReactNode;
  /** Uncontrolled initial open state. @default false */
  readonly defaultOpen?: boolean;
  /** Controlled open state (pairs with ``onOpenChange``). */
  readonly open?: boolean;
  /** Called with the next open state on toggle. */
  readonly onOpenChange?: (open: boolean) => void;
  /** Optional item wrapper class. */
  readonly className?: string;
}

/**
 * AccordionItem — one collapsible section (trigger + content).
 *
 * Controlled when ``open`` is provided (``onOpenChange`` receives every
 * toggle); otherwise uncontrolled, seeded by ``defaultOpen``.
 *
 * Args:
 *   children: The item's {@link AccordionTrigger} and {@link AccordionContent}.
 *   defaultOpen: Uncontrolled initial state.
 *   open: Controlled open state.
 *   onOpenChange: Toggle callback.
 *   className: Optional wrapper class.
 *
 * Returns:
 *   The accordion item element.
 */
export function AccordionItem({
  children,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  className,
}: AccordionItemProps): ReactElement {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const baseId = useId();
  const contentId = `${baseId}-content`;
  const triggerId = `${baseId}-trigger`;

  const toggle = (): void => {
    const next = !open;
    if (!isControlled) {
      setUncontrolledOpen(next);
    }
    onOpenChange?.(next);
  };

  return (
    <AccordionItemContext.Provider
      value={{ open, toggle, contentId, triggerId }}
    >
      <div
        data-slot="accordion-item"
        data-state={open ? "open" : "closed"}
        className={cn("border-b border-border last:border-b-0", className)}
      >
        {children}
      </div>
    </AccordionItemContext.Provider>
  );
}

/** Props for {@link AccordionTrigger}. */
export interface AccordionTriggerProps {
  /** The trigger label content. */
  readonly children: ReactNode;
  /** Optional trigger class. */
  readonly className?: string;
}

/**
 * AccordionTrigger — the clickable header that toggles its item.
 *
 * Args:
 *   children: The trigger label content.
 *   className: Optional class.
 *
 * Returns:
 *   The trigger button element.
 */
export function AccordionTrigger({
  children,
  className,
}: AccordionTriggerProps): ReactElement {
  const { open, toggle, contentId, triggerId } =
    useAccordionItem("AccordionTrigger");
  return (
    <button
      type="button"
      id={triggerId}
      aria-expanded={open}
      aria-controls={contentId}
      onClick={toggle}
      data-slot="accordion-trigger"
      className={cn(
        "flex w-full items-center justify-between gap-2 py-2 text-left text-sm font-medium text-foreground transition-colors hover:text-muted-foreground",
        className,
      )}
    >
      <span className="min-w-0 flex-1">{children}</span>
      <ChevronDown
        aria-hidden="true"
        className={cn(
          "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
          open && "rotate-180",
        )}
      />
    </button>
  );
}

/** Props for {@link AccordionContent}. */
export interface AccordionContentProps {
  /** The collapsible body content. */
  readonly children: ReactNode;
  /** Optional content class. */
  readonly className?: string;
}

/**
 * AccordionContent — the collapsible body region, rendered only when open.
 *
 * The content is unmounted while collapsed (rather than hidden) so its
 * subscriptions/effects do not run behind a closed panel — appropriate for the
 * raw-log feed which mounts a WS-driven auto-scroll.
 *
 * Args:
 *   children: The body content.
 *   className: Optional class.
 *
 * Returns:
 *   The content region element when open, else ``null``.
 */
export function AccordionContent({
  children,
  className,
}: AccordionContentProps): ReactElement | null {
  const { open, contentId, triggerId } = useAccordionItem("AccordionContent");
  if (!open) {
    return null;
  }
  return (
    <div
      id={contentId}
      role="region"
      aria-labelledby={triggerId}
      data-slot="accordion-content"
      className={cn("pb-2 pt-0 text-sm", className)}
    >
      {children}
    </div>
  );
}
