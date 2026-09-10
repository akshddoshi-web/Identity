import { z } from "zod";

export const accountTypeSchema = z.enum(["checking", "savings", "credit", "investment", "loan"]);
export type AccountType = z.infer<typeof accountTypeSchema>;

export const accountSchema = z.object({
  id: z.string(),
  userId: z.string(),
  plaidItemId: z.string().nullable(),
  plaidAccountId: z.string().nullable(),
  institutionName: z.string(),
  name: z.string(),
  type: accountTypeSchema,
  currentBalanceCents: z.number().int(),
  availableBalanceCents: z.number().int().nullable(),
  isLiability: z.boolean(),
  interestRateBps: z.number().int().nullable(),
  statementDueDate: z.coerce.date().nullable(),
  createdAt: z.coerce.date(),
});
export type Account = z.infer<typeof accountSchema>;

export const transactionSchema = z.object({
  id: z.string(),
  accountId: z.string(),
  plaidTransactionId: z.string().nullable(),
  merchantName: z.string(),
  amountCents: z.number().int(),
  category: z.string(),
  isUserOverridden: z.boolean(),
  postedAt: z.coerce.date(),
  isPending: z.boolean(),
});
export type Transaction = z.infer<typeof transactionSchema>;

export const budgetSchema = z.object({
  id: z.string(),
  userId: z.string(),
  category: z.string(),
  limitCents: z.number().int().positive(),
  periodStart: z.coerce.date(),
  periodEnd: z.coerce.date(),
});
export type Budget = z.infer<typeof budgetSchema>;

export const plannedExpenseSchema = z.object({
  id: z.string(),
  userId: z.string(),
  description: z.string().min(1),
  amountCents: z.number().int(),
  category: z.string(),
  dueDate: z.coerce.date(),
  reconciledTransactionId: z.string().nullable(),
});
export type PlannedExpense = z.infer<typeof plannedExpenseSchema>;

export const createBudgetInputSchema = budgetSchema.omit({ id: true, userId: true });
export const createPlannedExpenseInputSchema = plannedExpenseSchema.omit({
  id: true,
  userId: true,
  reconciledTransactionId: true,
});
