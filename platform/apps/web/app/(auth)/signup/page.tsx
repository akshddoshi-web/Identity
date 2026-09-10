"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { trpc } from "@/lib/trpc/client";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const signup = trpc.auth.signup.useMutation({
    onSuccess: async () => {
      const result = await signIn("credentials", { email, password, redirect: false });
      if (result?.error) {
        setError("Account created, but sign-in failed. Try logging in.");
        return;
      }
      router.push("/dashboard");
    },
    onError: (err) => setError(err.message),
  });

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <form
        className="panel w-full max-w-sm space-y-4 p-8"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          signup.mutate({ email, password, name: name || undefined });
        }}
      >
        <h1 className="text-2xl">Create your account</h1>

        <div>
          <label className="label" htmlFor="name">
            Name
          </label>
          <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>

        <div>
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <p className="text-sm text-ember-400">{error}</p>}

        <button type="submit" className="btn-primary w-full" disabled={signup.isPending}>
          {signup.isPending ? "Creating account..." : "Create account"}
        </button>

        <p className="text-center text-sm text-ink-400">
          Already have an account?{" "}
          <Link href="/login" className="text-jade-400 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </main>
  );
}
