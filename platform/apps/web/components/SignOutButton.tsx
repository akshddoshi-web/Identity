"use client";

import { signOut } from "next-auth/react";

export function SignOutButton() {
  return (
    <button
      className="text-sm text-ink-400 hover:text-ink-100"
      onClick={() => signOut({ callbackUrl: "/" })}
    >
      Sign out
    </button>
  );
}
