// One address, one file: a role's creation page, a screen over « Comptes » (the
// operator, 2026-10-04: « une nouvelle page avec un formulaire de création avec
// validation »).
import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";
import { RoleCreateScreen } from "../features/account/role-create-screen";

export const roleCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/accounts/roles/new",
  component: RoleCreateScreen,
});
