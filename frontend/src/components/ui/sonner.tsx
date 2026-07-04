import * as React from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

/**
 * App-wide toast host, themed to the PersonalScraper dark control deck.
 *
 * Patched from the stock shadcn `sonner` block: upstream reads the active theme
 * from `next-themes`, which this app does not use — the DS is dark-first
 * (`:root` = dark). We pin `theme="dark"` and map the toast surface onto DS
 * CSS variables so toasts inherit the brand palette.
 *
 * @param props Passthrough `sonner` Toaster props (position, richColors, …).
 * @returns The toast host element.
 */
function Toaster(props: ToasterProps): React.JSX.Element {
  // React's CSSProperties dropped its index signature (@types/react 19), so the
  // sonner theming CSS variables (`--normal-*`) need an assertion — this is the
  // documented csstype escape hatch for custom properties.
  const toasterStyle = {
    "--normal-bg": "var(--popover)",
    "--normal-text": "var(--popover-foreground)",
    "--normal-border": "var(--border)",
  } as React.CSSProperties;

  return (
    <Sonner
      theme="dark"
      className="toaster group"
      style={toasterStyle}
      {...props}
    />
  );
}

export { Toaster };
