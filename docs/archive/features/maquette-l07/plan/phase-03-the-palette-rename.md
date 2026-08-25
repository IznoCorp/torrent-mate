# Phase 3 — The palette takes Tailwind's name

**Converts nothing. Renames only.** D-L07-2, arbitrated by the operator on 2026-08-24.

## What moves

**30 colour tokens** `--background` → `--color-background`, `--card` → `--color-card`, and so on
across both theme blocks, through `scripts/rename-identifiers.py`.

**The 8 `--mq-shadow-*` do not move** (D-L07-4): Tailwind's `shadow-*` utilities rewrite the
computed `box-shadow` into a five-part composite, and `box-shadow` is one of the 19 properties the
oracle measures. They keep their name and are used through the arbitrary-property form, whose
compiled output is `box-shadow: var(--mq-shadow-card)` — byte-identical to today.

<sub>38 tokens declared between the `login:palette` markers; 462 `var()` call sites in `refonte.html`.</sub>

## The three ends that move together

1. the two `:root` blocks that declare them;
2. the 462 `var()` call sites, plus the 23 in `design/src`;
3. **`serve.py`'s `extract(styles_source, "palette")`** — the sign-in gate borrows this block
   verbatim, and `login:style` reads the same names.

## The proof is outside the tool

`rename-identifiers.py` skips its read-back check for `--values` runs, and two corruptions in this
repository were found by reading the diff after the tool reported success. So this phase closes on
three things and not on the tool's own count:

- the diff read line by line, not the « N file(s) touched » summary;
- **the oracle at zero divergence** — a token rename changes no computed style, so any divergence
  here is a rename that lost a call site;
- `python3 scripts/check-css-tokens.py` green, and the sign-in gate loaded and looked at.

## Gates

ACC-01, ACC-02 (**zero divergence, no exception**), ACC-03, ACC-10, ACC-11.
