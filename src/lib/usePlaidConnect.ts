import { useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { useHomeStore } from "@/store/useHomeStore";
import type { Account, Transaction } from "@/types/domain";

type Status = "idle" | "connecting" | "exchanging" | "error";

/** Drives the Accounts view's "Link another account" button: fetches a
 *  Link token, opens Plaid Link once it's ready, exchanges the resulting
 *  public_token server-side, and merges the real (sandbox) accounts +
 *  transactions that come back into the store alongside seed data. */
export function usePlaidConnect() {
  const addPlaidData = useHomeStore((s) => s.addPlaidData);
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [wantsToOpen, setWantsToOpen] = useState(false);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: async (publicToken) => {
      setStatus("exchanging");
      try {
        const res = await fetch("/api/plaid/exchange-public-token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ public_token: publicToken }),
        });
        if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Exchange failed");
        const data: { accounts: Account[]; transactions: Transaction[] } = await res.json();
        addPlaidData(data.accounts, data.transactions);
        setStatus("idle");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong linking that account.");
        setStatus("error");
      }
    },
    onExit: (plaidError) => {
      setWantsToOpen(false);
      setStatus((prev) => (prev === "exchanging" ? prev : "idle"));
      if (plaidError) setError(plaidError.error_message ?? "Link was closed before finishing.");
    },
  });

  useEffect(() => {
    if (wantsToOpen && ready) {
      open();
      setWantsToOpen(false);
    }
  }, [wantsToOpen, ready, open]);

  async function connect() {
    setError(null);
    setStatus("connecting");
    try {
      if (!linkToken) {
        const res = await fetch("/api/plaid/create-link-token", { method: "POST" });
        if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Could not start Plaid Link");
        const data: { link_token: string } = await res.json();
        setLinkToken(data.link_token);
        setWantsToOpen(true);
      } else {
        setWantsToOpen(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Plaid Link.");
      setStatus("error");
    }
  }

  return { connect, status, error, isBusy: status === "connecting" || status === "exchanging" };
}
