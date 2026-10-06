// The lots progress the named states pose, apart from the states themselves so a
// unit test can read it without loading the driver.
import type { LotsDocument } from "../../features/dev-lots/queries";

// When the sample was generated: an instant of the layer's frozen day.
export const GENERATED_AT = 1790856000;
// A pull request's page on the repository.
const PR = (number: number) => `https://github.com/example/repository/pull/${number}`;

// THE SAMPLE: a lot done, a lot under way in every state, and a lot not begun
// whose name and blocker are long enough to wrap at the phone's width.
export const SAMPLE_LOTS: LotsDocument = {
  available: true,
  generatedAt: GENERATED_AT,
  lots: [
    {
      id: "queue",
      name: "The run queue",
      blockedBy: null,
      phases: [
        { id: "P1", title: "the steps become callables", state: "merged", dispatch: null, blockedBy: null,
          prs: [{ number: 101, url: PR(101), state: "merged" }] },
        { id: "P2", title: "the queue, stored", state: "merged", dispatch: null,
          blockedBy: null, prs: [{ number: 102, url: PR(102), state: "merged" }] },
        { id: "P3", title: "one service asks for a run", state: "pr-open", dispatch: null, blockedBy: null,
          prs: [{ number: 103, url: PR(103), state: "merged" }, { number: 104, url: PR(104), state: "open" }] },
        { id: "P4", title: "the worker takes the queue", state: "in-progress", dispatch: "in-review",
          blockedBy: null, prs: [] },
        { id: "P5", title: "the interface asks through the queue", state: "planned", dispatch: null,
          blockedBy: null, prs: [] },
      ],
    },
    {
      id: "sandbox",
      name: "A sandbox of its own for the development environment, and a smoke check after every redeploy of it",
      blockedBy: "Waits for a key the development configuration does not hold yet, owed before the first phase",
      phases: [
        { id: "S1", title: "one guard for every sandboxed environment", state: "planned", dispatch: null,
          blockedBy: null, prs: [] },
        { id: "OP-1", title: "the development key", state: "planned", dispatch: null,
          blockedBy: "Owed by hand", prs: [] },
      ],
    },
  ],
};
