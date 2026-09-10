import { getServerSession } from "next-auth";
import Link from "next/link";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";

export default async function HomePage() {
  const session = await getServerSession(authOptions);
  if (session) redirect("/dashboard");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <div className="space-y-3">
        <p className="text-sm font-medium uppercase tracking-widest text-jade-400">
          Finance &middot; Fitness &middot; Planning
        </p>
        <h1 className="text-4xl font-semibold text-ink-50 sm:text-5xl">
          One schedule for your lifts, your meals, and your money.
        </h1>
        <p className="mx-auto max-w-xl text-ink-300">
          Track spending and net worth, log macros down to the ingredient, and plan lifting,
          eating, and spending together on one calendar.
        </p>
      </div>
      <div className="flex gap-3">
        <Link href="/signup" className="btn-primary">
          Create an account
        </Link>
        <Link href="/login" className="btn-secondary">
          Sign in
        </Link>
      </div>
      <p className="max-w-md text-xs text-ink-500">
        Investment screener content is educational and informational only — not licensed
        financial advice. See disclaimers throughout the Investing section.
      </p>
    </main>
  );
}
