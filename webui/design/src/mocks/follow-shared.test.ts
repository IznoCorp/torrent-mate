// A follow other accounts asked for too is paused by each of them for itself (K3-G11).
//
// WHAT MAKES THIS NON-VACUOUS. `updateFollow` writes the status of the WHOLE follow, which is not
// the caller's to write while another account asked for it. The contract answers that with a 403
// whose code is `acquisition.follow_shared`, and an account that pilots every acquisition is the
// exception. Each leg calls the operation the way the interface does and reads the status AND the
// code: a handler that never refused, one that refused with another code, and one that refused a
// sole requester all fail here.
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import FOLLOWS from "./seeds/follows.json";
import { routes } from "./handlers";
import { resolve, settled } from "./router";
import { keyOfMedium } from "./follow-key";
import { adoptAccount, claimRequest } from "./identity";
import { resetMockState } from "./state";
import type { components } from "../contract/types";

type Account = components["schemas"]["Account"];

/** An ordinary account that pilots its own acquisitions and no one else's. */
const PILOT_OWN: Account = {
  id: "real-pilot-own",
  name: "pilot",
  email: "pilot@example.invalid",
  role: { id: "household", name: "Household", kind: "ordinary", rights: ["acquisition.request", "acquisition.pilot.own"] },
  signInKind: "plex",
  language: "fr",
  forbiddenWrites: [],
};

/** The same account with the right to pilot every acquisition. */
const PILOT_ANY: Account = {
  ...PILOT_OWN,
  id: "real-pilot-any",
  role: { ...PILOT_OWN.role, rights: [...PILOT_OWN.role.rights, "acquisition.pilot.any"] },
};

const follow = FOLLOWS.find((one) => one.kind === "show")!;
const PATH = `/acquisition/followed/${encodeURIComponent(keyOfMedium(follow) as string)}`;

/** Pauses the follow the way the interface does, and reads the answer as the wire carries it. */
function pause(): { status: number; payload: any } {
  const found = resolve(routes(), "PATCH", PATH);
  if (found === null) throw new Error(`no route PATCH ${PATH}`);
  const answer = found.route.handle({ path: PATH, parameters: found.parameters, query: new URLSearchParams(), body: { status: "disabled" } });
  return settled(200, answer as never) as { status: number; payload: any };
}

describe("pausing a follow other accounts asked for", () => {
  beforeEach(() => resetMockState());
  afterEach(() => adoptAccount(null));

  it("is refused 403 `acquisition.follow_shared` to an account that does not pilot every acquisition", () => {
    adoptAccount(PILOT_OWN);
    const answer = pause();
    expect(answer.status).toBe(403);
    expect(answer.payload.code).toBe("acquisition.follow_shared");
  });

  it("is allowed to an account that pilots every acquisition", () => {
    adoptAccount(PILOT_ANY);
    expect(pause().status).toBe(200);
  });

  it("is allowed to the one account that asked for the follow", () => {
    adoptAccount(PILOT_OWN);
    claimRequest(follow.title, false);
    expect(pause().status).toBe(200);
  });
});
