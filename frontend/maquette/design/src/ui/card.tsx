// The card — the row every list draws, in parts.
//
// IT KNOWS NO DOMAIN (invariant 10): it takes a title, lines, a strip of steps
// and the attributes its caller's delegation reads. Which panel a body
// addresses, and what a poster opens, are the caller's to say.
//
// PARTS, NOT ONE COMPONENT WITH FLAGS. Three shapes share these blocks: the
// list card, whose poster sits beside a column holding the top, the strip and
// the foot; the candidate that IS a button, its poster inside the top; and the
// decision, a folder on disk, its poster inside the top too. One component with
// a flag per difference is the « component with a dozen appearance flags » the
// card's descriptor exists to refuse. The parts compose each shape from the same
// blocks, and every block names itself with its `data-part`.
import { createElement, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from "react";
import { Icon } from "./icon";
import {
  card,
  cardBody,
  cardCaption,
  cardContent,
  cardFolder,
  cardFolderLabel,
  cardMeta,
  cardOverview,
  cardReason,
  cardStrip,
  cardSubtitle,
  cardTitle,
  cardTop,
  posterFrame,
  stripDot,
  stripLabel,
  stripStep,
} from "./variants";

/** What a part passes to its element: its attributes, `data-*` included. */
type Attributes = ButtonHTMLAttributes<HTMLElement> & {
  [attribute: `data-${string}`]: string | undefined;
  children?: ReactNode;
};

/** Where the journey stands at one step of the strip. */
export type StripState = "done" | "now" | "blocked" | "pending";

/**
 * Draws one part: the element, its classes, its name, and the rest as given.
 *
 * @param tag The element name.
 * @param classes The part's own classes.
 * @param name The part's `data-part`, or undefined where the part carries none.
 * @param attributes What the caller passed, a class of its own included.
 * @returns The element.
 */
function part(
  tag: "div" | "span" | "button",
  classes: string,
  name: string | undefined,
  { className, children, ...rest }: Attributes,
): ReactElement {
  return createElement(
    tag,
    { ...rest, className: className ? `${classes} ${className}` : classes, "data-part": name },
    children,
  );
}

/** The card's frame. A candidate that is picked by a tap anywhere is a `button`. */
export function Card({ as = "div", ...attributes }: Attributes & { as?: "div" | "button" }): ReactElement {
  return part(as, card(), "card", attributes);
}

/** The column beside a list card's poster. */
export function CardContent(attributes: Attributes): ReactElement {
  return part("div", cardContent(), undefined, attributes);
}

/** The top row. Inside a card that is a button it is a `span`: a button holds phrasing content only. */
export function CardTop({ as = "div", ...attributes }: Attributes & { as?: "div" | "span" }): ReactElement {
  return part(as, cardTop(), "card/top", attributes);
}

/** The poster's frame: a `button` when it leads somewhere, a `span` when it only shows. */
export function CardPoster({ as = "span", ...attributes }: Attributes & { as?: "span" | "button" }): ReactElement {
  return part(as, `poster ${posterFrame()}`, "card/poster", attributes);
}

/** The body: the `button` that opens the panel, or a `span` where the card is the control. */
export function CardBody({ as = "button", ...attributes }: Attributes & { as?: "button" | "span" }): ReactElement {
  return part(as, cardBody(), "card/body", attributes);
}

/** The title. */
export function CardTitle(attributes: Attributes): ReactElement {
  return part("span", cardTitle(), "card/title", attributes);
}

/** The sub-line. */
export function CardSubtitle(attributes: Attributes): ReactElement {
  return part("span", cardSubtitle(), "card/subtitle", attributes);
}

/** The reason, which wraps and never truncates. */
export function CardReason(attributes: Attributes): ReactElement {
  return part("span", cardReason(), "card/reason", attributes);
}

/** The synopsis, which clamps. */
export function CardOverview(attributes: Attributes): ReactElement {
  return part("span", cardOverview(), "card/overview", attributes);
}

/** The state line. A screen that draws one outside a card draws it as a `div`. */
export function CardMeta({ as = "span", ...attributes }: Attributes & { as?: "span" | "div" }): ReactElement {
  return part(as, cardMeta(), "card/meta", attributes);
}

/** A numeric aside. */
export function CardCaption(attributes: Attributes): ReactElement {
  return part("span", cardCaption(), "card/caption", attributes);
}

/**
 * The folder a card wears where no medium stands behind it: an icon and a word,
 * in a poster's footprint.
 *
 * @param properties The icon's paths, the word, and the attributes its control carries.
 * @returns The folder.
 */
export function CardFolder({
  icon,
  label,
  ...attributes
}: Attributes & { icon: string; label: string }): ReactElement {
  return part("button", cardFolder(), "card/folder", {
    ...attributes,
    children: (
      <>
        <Icon paths={icon} strokeWidth={1.6} />
        <span className={cardFolderLabel()}>{label}</span>
      </>
    ),
  });
}

/**
 * The progress strip: one step per stage, each saying where the journey stands.
 *
 * @param properties The steps, in order, each a state and a label.
 * @returns The strip.
 */
export function CardStrip({ steps }: { steps: { state: StripState; label: string }[] }): ReactElement {
  return (
    <div className={cardStrip()}>
      {steps.map((step, index) => (
        <div key={index} className={stripStep({ state: step.state })}>
          <span className={`d ${stripDot({ state: step.state })}`}></span>
          <span className={`l ${stripLabel()}`}>{step.label}</span>
        </div>
      ))}
    </div>
  );
}
