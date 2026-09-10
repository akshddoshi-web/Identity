"use client";

import { formatCents } from "@identity/shared";
import { useState } from "react";
import { PlaidConnectButton } from "@/components/PlaidConnectButton";
import { StatCard } from "@/components/StatCard";
import { trpc } from "@/lib/trpc/client";

function last30Days() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return { from, to };
}

export default function FinancePage() {
  const netWorth = trpc.finance.netWorth.useQuery();
  const accounts = trpc.finance.listAccounts.useQuery();
  const spending = trpc.finance.spendingByCategory.useQuery(last30Days());
  const recurring = trpc.finance.detectRecurring.useQuery();
  const budgets = trpc.finance.listBudgets.useQuery();
  const plannedExpenses = trpc.finance.listPlannedExpenses.useQuery();
  const utils = trpc.useUtils();

  const [budgetForm, setBudgetForm] = useState({ category: "", limitDollars: "" });
  const createBudget = trpc.finance.createBudget.useMutation({
    onSuccess: () => {
      utils.finance.listBudgets.invalidate();
      setBudgetForm({ category: "", limitDollars: "" });
    },
  });

  const [expenseForm, setExpenseForm] = useState({ description: "", amountDollars: "", category: "", dueDate: "" });
  const createPlannedExpense = trpc.finance.createPlannedExpense.useMutation({
    onSuccess: () => {
      utils.finance.listPlannedExpenses.invalidate();
      setExpenseForm({ description: "", amountDollars: "", category: "", dueDate: "" });
    },
  });

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl">Finance</h1>
        <PlaidConnectButton />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Net worth" value={netWorth.data ? formatCents(netWorth.data.netWorthCents) : "—"} />
        <StatCard label="Assets" value={netWorth.data ? formatCents(netWorth.data.assetsCents) : "—"} accent="jade" />
        <StatCard label="Liabilities" value={netWorth.data ? formatCents(netWorth.data.liabilitiesCents) : "—"} accent="ember" />
      </div>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg">Accounts</h2>
        {accounts.data?.length === 0 && (
          <p className="text-sm text-ink-400">
            No accounts yet. Connect a bank above — Plaid sandbox mode uses fake test institutions, so
            no real bank credentials are needed.
          </p>
        )}
        <div className="divide-y divide-ink-800">
          {accounts.data?.map((account) => (
            <div key={account.id} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm text-ink-100">{account.name}</p>
                <p className="text-xs text-ink-500">
                  {account.institutionName} · {account.type}
                </p>
              </div>
              <p className="font-mono text-sm">{formatCents(account.currentBalanceCents)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg">Spending by category (last 30 days)</h2>
        {spending.data?.length === 0 && <p className="text-sm text-ink-400">No transactions in this window yet.</p>}
        <div className="space-y-2">
          {spending.data
            ?.sort((a, b) => b.totalCents - a.totalCents)
            .map((row) => (
              <div key={row.category} className="flex items-center justify-between text-sm">
                <span className="text-ink-200">{row.category}</span>
                <span className="font-mono text-ink-100">{formatCents(row.totalCents)}</span>
              </div>
            ))}
        </div>
      </section>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg">Detected recurring charges</h2>
        {recurring.data?.length === 0 && <p className="text-sm text-ink-400">Nothing recurring detected yet.</p>}
        <div className="space-y-2">
          {recurring.data?.map((group) => (
            <div key={group.merchantName} className="flex items-center justify-between text-sm">
              <span className="capitalize text-ink-200">{group.merchantName}</span>
              <span className="text-ink-400">
                {group.cadence} · ~{formatCents(group.approxAmountCents)}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg">Budgets</h2>
        <div className="mb-4 space-y-3">
          {budgets.data?.map((budget) => (
            <div key={budget.id}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-ink-200">{budget.category}</span>
                <span className="text-ink-400">
                  {formatCents(budget.progress.spentCents)} / {formatCents(budget.progress.limitCents)}
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-ink-800">
                <div
                  className={`h-full ${
                    budget.progress.status === "over"
                      ? "bg-ember-500"
                      : budget.progress.status === "approaching"
                        ? "bg-gold-500"
                        : "bg-jade-500"
                  }`}
                  style={{ width: `${Math.min(100, budget.progress.percentUsed)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const now = new Date();
            const periodStart = new Date(now.getFullYear(), now.getMonth(), 1);
            const periodEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            createBudget.mutate({
              category: budgetForm.category,
              limitCents: Math.round(Number(budgetForm.limitDollars) * 100),
              periodStart,
              periodEnd,
            });
          }}
        >
          <input
            className="input max-w-[160px]"
            placeholder="Category"
            required
            value={budgetForm.category}
            onChange={(e) => setBudgetForm((f) => ({ ...f, category: e.target.value }))}
          />
          <input
            className="input max-w-[120px]"
            placeholder="Limit $"
            type="number"
            min="1"
            step="0.01"
            required
            value={budgetForm.limitDollars}
            onChange={(e) => setBudgetForm((f) => ({ ...f, limitDollars: e.target.value }))}
          />
          <button className="btn-secondary" type="submit" disabled={createBudget.isPending}>
            Add budget (this month)
          </button>
        </form>
      </section>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg">Planned expenses</h2>
        <div className="mb-4 space-y-2">
          {plannedExpenses.data?.map((expense) => (
            <div key={expense.id} className="flex items-center justify-between text-sm">
              <span className="text-ink-200">{expense.description}</span>
              <span className="text-ink-400">
                {formatCents(expense.amountCents)} · due {new Date(expense.dueDate).toLocaleDateString()}
                {expense.reconciledTransactionId ? " · reconciled" : ""}
              </span>
            </div>
          ))}
        </div>
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            createPlannedExpense.mutate({
              description: expenseForm.description,
              category: expenseForm.category || "Uncategorized",
              amountCents: Math.round(Number(expenseForm.amountDollars) * 100),
              dueDate: new Date(expenseForm.dueDate),
            });
          }}
        >
          <input
            className="input max-w-[180px]"
            placeholder="Description"
            required
            value={expenseForm.description}
            onChange={(e) => setExpenseForm((f) => ({ ...f, description: e.target.value }))}
          />
          <input
            className="input max-w-[120px]"
            placeholder="Amount $"
            type="number"
            step="0.01"
            required
            value={expenseForm.amountDollars}
            onChange={(e) => setExpenseForm((f) => ({ ...f, amountDollars: e.target.value }))}
          />
          <input
            className="input max-w-[140px]"
            type="date"
            required
            value={expenseForm.dueDate}
            onChange={(e) => setExpenseForm((f) => ({ ...f, dueDate: e.target.value }))}
          />
          <button className="btn-secondary" type="submit" disabled={createPlannedExpense.isPending}>
            Add planned expense
          </button>
        </form>
      </section>
    </div>
  );
}
