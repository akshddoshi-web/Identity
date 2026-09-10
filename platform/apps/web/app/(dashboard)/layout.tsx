import { getServerSession } from "next-auth";
import Link from "next/link";
import { redirect } from "next/navigation";
import { SignOutButton } from "@/components/SignOutButton";
import { authOptions } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/finance", label: "Finance" },
  { href: "/nutrition", label: "Nutrition" },
  { href: "/training", label: "Training" },
  { href: "/planner", label: "Planner" },
  { href: "/investing", label: "Investing" },
];

// Auth is enforced here (server component) rather than in edge middleware —
// simpler, and avoids bundling next-auth's middleware into the Edge runtime.
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession(authOptions);
  if (!session) redirect("/login");

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-ink-800 bg-ink-900 p-4">
        <div className="mb-8 px-2 text-lg font-semibold text-ink-50">Identity</div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-lg px-3 py-2 text-sm text-ink-300 transition-colors hover:bg-ink-800 hover:text-ink-50"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 px-2">
          <SignOutButton />
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
