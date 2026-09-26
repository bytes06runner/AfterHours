"use client";

/**
 * Loads wagmi and RainbowKit once, the first time anything asks (the Connect button or the
 * vault page), and wraps the whole app so the header and the deposit panel share one wallet.
 */
import dynamic from "next/dynamic";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

const WalletProviders = dynamic(() => import("./WalletProviders"), { ssr: false });

interface Gate {
  enabled: boolean;
  enable: (openModal?: boolean) => void;
}

const GateContext = createContext<Gate>({ enabled: false, enable: () => undefined });

export function WalletGate({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(false);
  const [openModal, setOpenModal] = useState(false);
  const enable = useCallback((open = false) => {
    setEnabled(true);
    if (open) setOpenModal(true);
  }, []);
  const value = useMemo(() => ({ enabled, enable }), [enabled, enable]);
  return (
    <GateContext.Provider value={value}>
      {enabled ? <WalletProviders openModal={openModal}>{children}</WalletProviders> : children}
    </GateContext.Provider>
  );
}

export const useWalletGate = () => useContext(GateContext);
