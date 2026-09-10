import { createTRPCReact } from "@trpc/react-query";
import type { AppRouter } from "@identity/api";

export const trpc = createTRPCReact<AppRouter>();
