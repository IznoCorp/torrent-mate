// the staging queue's card, as the contract answers it
//
// One card of every list the queue reads — stuck, moving, settled, takeable,
// blocked, in flight, not found, done today — in the contract's own names
// (`title`, `secondaryLine`, `reason`, `chip`, `withoutPoster`).
import type { components } from "../contract/types";

export type QueueCard = components["schemas"]["QueueCard"];
