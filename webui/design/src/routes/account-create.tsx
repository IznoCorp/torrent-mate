// One address, one file: an account's creation page, a screen over « Comptes »
// (the operator, 2026-10-04: « Créer un nouveau compte devrait avoir sa propre
// page avec formulaire et validation aussi »).
import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";
import { AccountCreateScreen } from "../features/account/account-create-screen";

export const accountCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/accounts/new",
  component: AccountCreateScreen,
});
