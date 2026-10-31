// One address, one file: the ranking editor, a screen under the settings page.
import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";
import { RankingScreen } from "../features/settings/ranking-screen";

export const rankingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/ranking",
  component: RankingScreen,
});
