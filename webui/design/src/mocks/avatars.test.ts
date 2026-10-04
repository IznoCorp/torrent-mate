// The mock's accounts each carry their own picture, as the server resolves it
// (B-695): a Plex picture, a Gravatar, or neither.
//
// WHAT MAKES THIS NON-VACUOUS. The account read is the one the bar and the
// account panel draw from, and before B-695 the layer gave the owner's picture
// to the owner alone: every other account read without one, so tm-design could
// show neither a Gravatar nor a Plex picture on anyone but him.
import { beforeEach, describe, expect, it } from "vitest";
import { resetMockState } from "./state";
import { identityDials, signedIn } from "./identity";

describe("signedIn's avatar", () => {
  beforeEach(() => resetMockState());

  it("is the owner's own picture at rest", () => {
    expect(signedIn().avatar).toBe("assets/avatar.webp");
  });

  it("is a Plex-linked account's Plex picture", () => {
    identityDials.setIdentity("just-linked");
    expect(signedIn().avatar).toBe("assets/avatar-plex-sample.svg");
  });

  it("is a local account's Gravatar", () => {
    identityDials.setIdentity("local-guest");
    expect(signedIn().avatar).toBe("assets/avatar-gravatar-sample.svg");
  });

  it("is absent on an account that has neither", () => {
    identityDials.setIdentity("local-account");
    expect("avatar" in signedIn()).toBe(false);
  });
});
