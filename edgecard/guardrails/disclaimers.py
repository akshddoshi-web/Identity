"""Disclaimer module. Imported by the dashboard and by anything that renders
an ROI, CLV, or "edge" claim to a human. Not decorative — every function
here is designed to be called inline next to the number it qualifies, not
tucked away in a footer nobody reads.
"""
from __future__ import annotations

TOP_LEVEL_DISCLAIMER = """\
This system is a decision-support and research tool, not a source of \
guaranteed winning bets. It estimates probabilities from historical data and \
compares them to betting markets; both the estimates and the comparison are \
uncertain. Model outputs can be wrong, markets can be right even when this \
system disagrees with them, and past backtested performance does not \
guarantee future results. Sports betting carries real financial risk \
including the risk of losing your entire stake, and in many jurisdictions is \
regulated or restricted — know your local laws. Nothing produced by this \
system is financial advice. If gambling stops being fun or affects your \
finances, relationships, or well-being, contact the National Council on \
Problem Gambling (US): 1-800-522-4700 / ncpgambling.org.\
"""

SMALL_SAMPLE_WARNING_TEMPLATE = (
    "n={n} is below the {min_n}-bet threshold this system requires before treating a "
    "result as statistically meaningful. Below that threshold, win rate, ROI, and CLV "
    "can look arbitrarily good or bad purely from noise — a real 2-3% edge produces win "
    "rates and ROI figures over 50-100 bets that are dominated by variance, not skill. "
    "Treat this number as descriptive only."
)

VARIANCE_REALITY_CHECK = (
    "Even a genuinely durable edge is choppy in practice: a bettor with a true 55% win "
    "probability at standard -110 pricing (roughly a 2.4% expected ROI per bet, a very "
    "good real-world edge) will still go through extended losing stretches and can see "
    "double-digit percentage bankroll drawdowns over a few hundred bets, purely from "
    "variance. See the Monte Carlo simulation for what this actually looks like across "
    "thousands of simulated paths — one realized backtest curve is a single draw from "
    "that same distribution, not a promise of what happens next."
)

NO_PARLAY_POLICY = (
    "This system does not model, recommend, or size parlays or same-game parlays. "
    "Parlays combine independent vig on every leg into a much larger effective house "
    "edge than any single-game bet, and same-game parlay legs are often correlated in "
    "ways the posted price does not reflect — there is no real, durable edge on offer "
    "there for a retail bettor, so it's out of scope by design, not by oversight."
)

CLV_EXPLAINER = (
    "Closing Line Value (CLV) compares the price you got against the market's final, "
    "most-informed price at closing. Positive average CLV over a large sample is the "
    "best available evidence of genuine predictive skill — better than short-run win "
    "rate, which is dominated by variance. A positive win rate with negative CLV is a "
    "warning sign that you've been getting lucky, not that you have an edge."
)


def small_sample_warning(n: int, min_n: int) -> str | None:
    """Returns a warning string if n < min_n, else None. Callers should
    render this warning whenever they show a metric derived from n."""
    if n < min_n:
        return SMALL_SAMPLE_WARNING_TEMPLATE.format(n=n, min_n=min_n)
    return None


def confidence_caveat(ci_low: float, ci_high: float, n: int) -> str:
    """A one-line caveat to render next to any point-estimate 'edge' number."""
    return (
        f"95% CI (n={n}): [{ci_low:+.2%}, {ci_high:+.2%}]. Read the interval, not the "
        "point estimate — a wide interval crossing zero means this could plausibly be no "
        "edge at all."
    )


def full_disclaimer_block() -> str:
    return "\n\n".join(
        [TOP_LEVEL_DISCLAIMER, VARIANCE_REALITY_CHECK, NO_PARLAY_POLICY, CLV_EXPLAINER]
    )
