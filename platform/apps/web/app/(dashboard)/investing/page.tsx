"use client";

import { DEFAULT_FACTOR_WEIGHTS } from "@identity/shared";
import { useState } from "react";
import { trpc } from "@/lib/trpc/client";

export default function InvestingPage() {
  const utils = trpc.useUtils();
  const [weights, setWeights] = useState(DEFAULT_FACTOR_WEIGHTS);
  const screener = trpc.investing.screener.useQuery({ weights });
  const refresh = trpc.investing.refreshFactorCache.useMutation({
    onSuccess: () => utils.investing.screener.invalidate(),
  });

  const riskProfile = trpc.riskProfile.getProfile.useQuery();
  const allocation = trpc.riskProfile.allocationSuggestion.useQuery(undefined, {
    enabled: Boolean(riskProfile.data),
  });
  const [questionnaire, setQuestionnaire] = useState({ timeHorizonYears: "10", drawdownComfort: "3", hasEmergencyFund: true });
  const submitQuestionnaire = trpc.riskProfile.submitQuestionnaire.useMutation({
    onSuccess: () => {
      utils.riskProfile.getProfile.invalidate();
      utils.riskProfile.allocationSuggestion.invalidate();
    },
  });

  return (
    <div className="space-y-8">
      <h1 className="text-2xl">Investing — Factor Screener</h1>

      <div className="panel border-gold-500/40 bg-gold-500/5 p-4 text-sm text-gold-400">
        <strong>Educational and informational only — not licensed financial advice.</strong> Scores are
        a transparent weighted composite of factors from a small local/dev universe, not a
        recommendation to buy or sell any security. Data sourced from Alpha Vantage's free dev
        tier and refreshed on demand below.
      </div>

      <section className="panel space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg">Ranked screener{screener.data?.asOfDate ? ` — as of ${new Date(screener.data.asOfDate).toLocaleDateString()}` : ""}</h2>
          <button className="btn-secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            {refresh.isPending ? "Refreshing (rate-limited)..." : "Refresh factor data"}
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {(Object.keys(weights) as (keyof typeof weights)[]).map((key) => (
            <div key={key}>
              <label className="label capitalize">{key}</label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={weights[key]}
                onChange={(e) => setWeights((w) => ({ ...w, [key]: Number(e.target.value) }))}
                className="w-full"
              />
              <p className="text-xs text-ink-400">{weights[key].toFixed(2)}</p>
            </div>
          ))}
        </div>

        {screener.data?.ranked.length === 0 && (
          <p className="text-sm text-ink-400">
            No factor data yet — set MARKET_DATA_API_KEY and click "Refresh factor data" (the free
            Alpha Vantage tier is rate-limited to 5 requests/minute, so this can take a minute for
            the default 10-symbol dev universe).
          </p>
        )}

        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-500">
              <th className="pb-2">Symbol</th>
              <th className="pb-2">Sector</th>
              <th className="pb-2">Composite score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-800">
            {screener.data?.ranked.map((stock) => (
              <tr key={stock.symbol}>
                <td className="py-2 font-mono">{stock.symbol}</td>
                <td className="py-2 text-ink-400">{stock.sector}</td>
                <td className={`py-2 font-mono ${stock.compositeScore >= 0 ? "text-jade-400" : "text-ember-400"}`}>
                  {stock.compositeScore.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel space-y-4 p-5">
        <h2 className="text-lg">Tier 2 — Personalized allocation (experimental)</h2>
        <p className="text-xs text-ink-500">
          Built on top of the Tier 1 screener above. A simple, transparent weighting — not
          mean-variance optimization or proprietary alpha generation.
        </p>

        {!riskProfile.data && (
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label">Time horizon (years)</label>
              <input
                className="input w-28"
                type="number"
                value={questionnaire.timeHorizonYears}
                onChange={(e) => setQuestionnaire((q) => ({ ...q, timeHorizonYears: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Drawdown comfort (1-5)</label>
              <input
                className="input w-28"
                type="number"
                min={1}
                max={5}
                value={questionnaire.drawdownComfort}
                onChange={(e) => setQuestionnaire((q) => ({ ...q, drawdownComfort: e.target.value }))}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-ink-300">
              <input
                type="checkbox"
                checked={questionnaire.hasEmergencyFund}
                onChange={(e) => setQuestionnaire((q) => ({ ...q, hasEmergencyFund: e.target.checked }))}
              />
              I have an emergency fund outside this portfolio
            </label>
            <button
              className="btn-primary"
              onClick={() =>
                submitQuestionnaire.mutate({
                  timeHorizonYears: Number(questionnaire.timeHorizonYears),
                  drawdownComfort: Number(questionnaire.drawdownComfort),
                  hasEmergencyFund: questionnaire.hasEmergencyFund,
                })
              }
            >
              Get my allocation
            </button>
          </div>
        )}

        {riskProfile.data && allocation.data && (
          <div className="space-y-3">
            <p className="text-sm text-ink-400">Risk tolerance: {riskProfile.data.riskTolerance} / 5</p>
            <div className="space-y-1">
              {allocation.data.allocation.map((position) => (
                <div key={position.symbol} className="flex items-center justify-between text-sm">
                  <span className="font-mono">{position.symbol}</span>
                  <span className="text-ink-300">{position.weightPercent}%</span>
                </div>
              ))}
            </div>
            {allocation.data.backtest && (
              <div className="rounded-lg bg-ink-800 p-3 text-sm">
                <p className={allocation.data.backtest.weightedReturnPercent >= 0 ? "text-jade-400" : "text-ember-400"}>
                  Illustrative trailing-12mo blended return: {allocation.data.backtest.weightedReturnPercent}%
                </p>
                <p className="mt-1 text-xs text-ink-500">{allocation.data.backtest.disclaimer}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
