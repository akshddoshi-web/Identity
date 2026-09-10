import { router } from "./trpc";
import { authRouter } from "./routers/auth";
import { financeRouter } from "./routers/finance";
import { nutritionRouter } from "./routers/nutrition";
import { trainingRouter } from "./routers/training";
import { plannerRouter } from "./routers/planner";
import { investingRouter } from "./routers/investing";
import { riskProfileRouter } from "./routers/riskProfile";

export const appRouter = router({
  auth: authRouter,
  finance: financeRouter,
  nutrition: nutritionRouter,
  training: trainingRouter,
  planner: plannerRouter,
  investing: investingRouter,
  riskProfile: riskProfileRouter,
});

export type AppRouter = typeof appRouter;
