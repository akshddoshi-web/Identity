import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <h1 className="text-2xl">Page not found</h1>
      <Link href="/" className="btn-primary">
        Back home
      </Link>
    </main>
  );
}
