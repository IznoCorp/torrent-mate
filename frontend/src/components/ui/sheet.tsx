import * as React from "react";
import * as SheetPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/** Which viewport edge the sheet slides in from. */
type SheetSide = "left" | "right" | "bottom";

/**
 * Per-edge positioning, sizing and slide-transition classes for
 * {@link SheetContent}.
 *
 * `left` is the mobile navigation drawer, `right` a desktop detail/filter panel,
 * `bottom` a mobile action sheet. Each edge also folds in the matching
 * `env(safe-area-inset-*)` so the drawer clears the notch / home indicator when
 * the PWA runs standalone.
 */
const SHEET_SIDE_CLASSES: Record<SheetSide, string> = {
  left: "inset-y-0 left-0 h-full w-3/4 max-w-sm border-r border-border pl-[env(safe-area-inset-left)] data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
  right:
    "inset-y-0 right-0 h-full w-3/4 max-w-sm border-l border-border pr-[env(safe-area-inset-right)] data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
  bottom:
    "inset-x-0 bottom-0 h-auto max-h-[80vh] border-t border-border pb-[env(safe-area-inset-bottom)] data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
};

/**
 * Sheet — a slide-in drawer built on `@radix-ui/react-dialog` (the same
 * primitive as {@link Dialog}), themed to the DS tokens.
 *
 * @returns The controlled Radix dialog root that owns the drawer's open state.
 */
function Sheet(
  props: React.ComponentProps<typeof SheetPrimitive.Root>,
): React.JSX.Element {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />;
}

/** SheetTrigger — the element that opens the sheet when activated. */
function SheetTrigger(
  props: React.ComponentProps<typeof SheetPrimitive.Trigger>,
): React.JSX.Element {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

/** SheetClose — dismisses the sheet from within its content. */
function SheetClose(
  props: React.ComponentProps<typeof SheetPrimitive.Close>,
): React.JSX.Element {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />;
}

/** SheetPortal — renders the overlay + content at the document root. */
function SheetPortal(
  props: React.ComponentProps<typeof SheetPrimitive.Portal>,
): React.JSX.Element {
  return <SheetPrimitive.Portal {...props} />;
}

/** SheetOverlay — the dimmed backdrop behind the drawer. */
function SheetOverlay({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Overlay>): React.JSX.Element {
  return (
    <SheetPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50",
        className,
      )}
      {...props}
    />
  );
}

/**
 * SheetContent — the drawer panel itself.
 *
 * Args:
 *   side: Viewport edge the panel slides from (`left` for the mobile nav).
 *   showCloseButton: Render the top-right close affordance (default `true`).
 */
function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: SheetSide;
  showCloseButton?: boolean;
}): React.JSX.Element {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "bg-background data-[state=open]:animate-in data-[state=closed]:animate-out fixed z-50 flex flex-col gap-4 pt-[env(safe-area-inset-top)] shadow-lg transition duration-[var(--motion-base)] ease-[var(--ease-in-out)]",
          SHEET_SIDE_CLASSES[side],
          className,
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close
            data-slot="sheet-close"
            className="ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
          >
            <X />
            <span className="sr-only">Fermer</span>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Content>
    </SheetPortal>
  );
}

/** SheetHeader — the top title/description stack of a sheet. */
function SheetHeader({
  className,
  ...props
}: React.ComponentProps<"div">): React.JSX.Element {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1.5 p-4", className)}
      {...props}
    />
  );
}

/** SheetFooter — the bottom action row of a sheet, pinned to its end. */
function SheetFooter({
  className,
  ...props
}: React.ComponentProps<"div">): React.JSX.Element {
  return (
    <div
      data-slot="sheet-footer"
      className={cn("mt-auto flex flex-col gap-2 p-4", className)}
      {...props}
    />
  );
}

/** SheetTitle — the sheet's accessible heading (required by Radix a11y). */
function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Title>): React.JSX.Element {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-foreground font-semibold", className)}
      {...props}
    />
  );
}

/** SheetDescription — the sheet's supporting caption. */
function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Description>): React.JSX.Element {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  );
}

export {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetOverlay,
  SheetPortal,
  SheetTitle,
  SheetTrigger,
};
