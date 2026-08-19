import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

afterEach(cleanup);

function renderItem(props?: {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  return render(
    <Accordion>
      <AccordionItem {...props}>
        <AccordionTrigger>Journal brut</AccordionTrigger>
        <AccordionContent>secret body</AccordionContent>
      </AccordionItem>
    </Accordion>,
  );
}

describe("Accordion", () => {
  it("is collapsed by default — content not in the DOM", () => {
    renderItem();
    expect(screen.queryByText("secret body")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Journal brut" }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("expands on trigger click and shows the content region", () => {
    renderItem();
    fireEvent.click(screen.getByRole("button", { name: "Journal brut" }));
    expect(screen.getByText("secret body")).toBeInTheDocument();
    expect(screen.getByRole("region")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Journal brut" }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("collapses again on a second click", () => {
    renderItem({ defaultOpen: true });
    expect(screen.getByText("secret body")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Journal brut" }));
    expect(screen.queryByText("secret body")).not.toBeInTheDocument();
  });

  it("wires aria-controls / aria-labelledby between trigger and region", () => {
    renderItem({ defaultOpen: true });
    const trigger = screen.getByRole("button", { name: "Journal brut" });
    const region = screen.getByRole("region");
    expect(trigger.getAttribute("aria-controls")).toBe(
      region.getAttribute("id"),
    );
    expect(region.getAttribute("aria-labelledby")).toBe(
      trigger.getAttribute("id"),
    );
  });

  it("supports controlled mode via open / onOpenChange", () => {
    const onOpenChange = vi.fn();
    renderItem({ open: false, onOpenChange });
    // Controlled + open=false → still collapsed after click, but callback fires.
    fireEvent.click(screen.getByRole("button", { name: "Journal brut" }));
    expect(onOpenChange).toHaveBeenCalledWith(true);
    expect(screen.queryByText("secret body")).not.toBeInTheDocument();
  });
});
