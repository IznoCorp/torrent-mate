// Markup composed elsewhere, put into an element WITHOUT recreating its
// children on every render.
//
// WHY THIS EXISTS, and it is a fact about React rather than a preference.
// React 18 compared the `__html` strings of `dangerouslySetInnerHTML` and left
// equal markup alone; React 19 assigns `innerHTML` whenever the prop is a NEW
// OBJECT — and `{ __html: … }` written inline is a new object on every render.
// Measured: a page subscribed to the store's version re-rendered on a bump
// with its section's markup byte-equal before and after, the `<section>` the
// same node, and every card inside it a NEW node. A tap between `pointerdown`
// and `click` on one of those cards is lost whenever anything bumps the store,
// with no event and no error.
//
// So the object is memoised on the STRING: as long as the markup is the same,
// the element keeps the children it has; when the markup changes, they are
// replaced, which is what a change is for. It is written once, here, so the
// day React changes again there is one line to change.
//
// IT KNOWS NO DOMAIN (invariant 10): it takes a string and an element name.
import { createElement, useMemo, type ReactElement } from "react";

/**
 * The `dangerouslySetInnerHTML` value for one string, stable while the string is.
 *
 * @param html The markup, composed by the caller.
 * @returns The same object for as long as `html` is unchanged.
 */
export function useMarkup(html: string): { __html: string } {
  return useMemo(() => ({ __html: html }), [html]);
}

/**
 * An element whose children are the given markup, kept across renders.
 *
 * Every attribute but `html` and `tag` goes onto the element as it is, so a
 * call site keeps its class, its naming attributes and its key.
 *
 * @param properties The element name (`div` by default), the markup, and the rest.
 * @returns The element.
 */
export function Markup({
  tag = "div",
  html,
  ...rest
}: {
  tag?: "div" | "section" | "span";
  html: string;
  className?: string;
  id?: string;
  hidden?: boolean;
  style?: React.CSSProperties;
  title?: string;
  [attribute: `data-${string}`]: string | undefined;
}): ReactElement {
  return createElement(tag, { ...rest, dangerouslySetInnerHTML: useMarkup(html) });
}
