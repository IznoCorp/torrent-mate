// The layer's table of the right each notification type asks, held equal to the contract's.
//
// The contract's `x-rights` on `NotificationType` is what the backend follows when it filters the
// account's switches and its pushes; the layer answers the read through `NOTIFICATION_RIGHTS`.
// Two tables that may drift are one table read twice: this holds them equal.
import { describe, expect, it } from "vitest";
import contract from "../../../../../contract/openapi.json";
import { NOTIFICATION_RIGHTS } from "./notifications";

type TypeSchema = { enum: string[]; "x-rights": Record<string, string> };
const schema = (contract as unknown as { components: { schemas: Record<string, TypeSchema> } })
  .components.schemas.NotificationType;

describe("NOTIFICATION_RIGHTS", () => {
  it("names every type of the contract, in its order", () => {
    expect(Object.keys(NOTIFICATION_RIGHTS)).toEqual(schema.enum);
  });

  it("asks, for each type, the right the contract's x-rights names", () => {
    expect(NOTIFICATION_RIGHTS).toEqual(schema["x-rights"]);
  });
});
