import { z } from "zod";

export const identityThreadInputSchema = z.object({
  label: z.string().trim().min(3, "Give this thread a short identity statement").max(80),
  description: z.string().trim().max(280).optional(),
});
export type IdentityThreadInput = z.infer<typeof identityThreadInputSchema>;

export const onboardingSchema = z.object({
  threads: z
    .array(identityThreadInputSchema)
    .min(2, "Define at least 2 identity threads")
    .max(4, "Define at most 4 identity threads"),
});
export type OnboardingInput = z.infer<typeof onboardingSchema>;
