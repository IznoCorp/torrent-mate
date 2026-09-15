// The contract's schema types, as every layer that types a served answer reads them.
//
// A DOOR, and a type-only one. The generated contract (`contract/types.d.ts`)
// is one module every feature's reads are typed by; imported from each feature
// directly it would be the hub the fan-in ceiling refuses, so the features take
// the schemas from here, where the frame keeps what it shares.
import type { components } from "../contract/types";

/** Every schema the contract declares, by its name. */
export type Schemas = components["schemas"];
