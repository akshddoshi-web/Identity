"use client";

import { useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { trpc } from "@/lib/trpc/client";

export function PlaidConnectButton() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const utils = trpc.useUtils();

  const createLinkToken = trpc.finance.createPlaidLinkToken.useMutation({
    onSuccess: (data) => setLinkToken(data.linkToken),
  });

  const exchangeToken = trpc.finance.exchangePlaidPublicToken.useMutation({
    onSuccess: () => {
      utils.finance.listAccounts.invalidate();
      utils.finance.netWorth.invalidate();
    },
  });

  const { open, ready } = usePlaidLink({
    token: linkToken ?? "",
    onSuccess: (publicToken) => exchangeToken.mutate({ publicToken }),
  });

  if (linkToken && ready) {
    return (
      <button className="btn-primary" onClick={() => open()}>
        Continue connecting bank
      </button>
    );
  }

  return (
    <button
      className="btn-primary"
      onClick={() => createLinkToken.mutate()}
      disabled={createLinkToken.isPending}
    >
      {createLinkToken.isPending ? "Preparing..." : "Connect a bank (Plaid sandbox)"}
    </button>
  );
}
