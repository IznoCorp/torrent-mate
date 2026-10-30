// THE ONE DOOR EVERY VARIANT IN THIS TREE COMES THROUGH.
//
// It re-exports `class-variance-authority` unchanged, and the reason it exists
// at all is a defect worth keeping: A VARIANT THAT OVERRIDES A BASE
// DECLARATION EMITS BOTH UTILITIES, and which one wins is decided by the
// generator's sort order rather than by the author. `panelField`'s `list`
// variant set `items-stretch` over a base `items-center` and `gap-3` over
// `gap-5`, and the list field came out 186px taller because the base won. The
// prototype had no such ambiguity: `.field.list` beat `.field` by specificity,
// always.
//
// `tailwind-merge` was tried here as the general answer — later wins, per
// property family — and it is NOT one: it also drops arbitrary variants and
// arbitrary properties it cannot classify, and the oracle read 389 divergences
// where there had been two. It is removed rather than tuned.
//
// SO THE RULE IS BY CONSTRUCTION, and it is the only one this file enforces
// by existing: A PROPERTY A VARIANT MAY CHANGE DOES NOT BELONG IN THE BASE.
// Put it in every branch instead — including the `false` one. There is then
// nothing to race.
export { cva, cx } from "class-variance-authority";
