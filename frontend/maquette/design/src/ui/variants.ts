// THE SHARED VOCABULARY, AS TYPED VARIANTS — D2 in force.
//
// A CLASS FACTORY RATHER THAN A COMPONENT, and the choice is not stylistic.
// Wrapping these primitives in React components would change the DOM: a
// `<Section>` adds nothing visible but every element it replaces would be
// re-created, and this wave's whole claim is that the rendering did not move.
// A factory returns a class string, so the markup is byte-identical and the
// oracle can still say so — while the utilities live in ONE place and the
// variants are checked by the compiler, which is what D2 asks for.
//
// THE ORIGINAL CLASS NAME IS KEPT AT THE FRONT of every string, emptied of
// style. The engine selects several of these by CSS class, and a name removed
// here would break a reader while the styling moved cleanly. It is an identity
// anchor now, which is what D4 wants an anchor to be.
import { cva } from "./cva";

// A BARREL, and it earns the exception. `ui/` is exempt from the module-hub
// rule (invariant 8) precisely because a shared vocabulary is meant to be
// imported widely — and re-exporting keeps 200-odd call sites reading one
// name each instead of hunting three files for it.
export * from "./variants/frame";
export * from "./variants/layout";
export * from "./variants/controls";
export * from "./variants/surfaces";
