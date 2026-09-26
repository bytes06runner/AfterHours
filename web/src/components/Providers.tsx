"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { PhaseProvider, type Phase } from "@/lib/phase";
import { useLiveStream } from "@/lib/queries";

function Live() {
  useLiveStream();
  return null;
}

export function Providers({
  initialPhase,
  children,
}: {
  initialPhase: Phase;
  children: React.ReactNode;
}) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <PhaseProvider initial={initialPhase}>
        <Live />
        {children}
      </PhaseProvider>
    </QueryClientProvider>
  );
}
