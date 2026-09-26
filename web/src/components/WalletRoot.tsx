"use client";

import "@rainbow-me/rainbowkit/styles.css";

import {
  ConnectButton,
  RainbowKitProvider,
  lightTheme,
  darkTheme,
  useConnectModal,
} from "@rainbow-me/rainbowkit";
import { useEffect, useMemo } from "react";
import { WagmiProvider, createConfig, http } from "wagmi";
import { injected } from "wagmi/connectors";
import { defineChain } from "viem";

import { usePhase } from "@/lib/phase";
import { useConfig } from "@/lib/queries";

function OpenOnMount() {
  const { openConnectModal } = useConnectModal();
  useEffect(() => {
    openConnectModal?.();
  }, [openConnectModal]);
  return null;
}

/** Wallet providers built from /v1/config/public: chain id, name and a browser-safe RPC. */
export default function WalletRoot({ openOnMount = false }: { openOnMount?: boolean }) {
  const { data: pub } = useConfig();
  const { phase } = usePhase();
  const config = useMemo(() => {
    if (!pub?.chain.chain_id || !pub.chain.rpc_url) return null;
    const chain = defineChain({
      id: pub.chain.chain_id,
      name: pub.profile === "local" ? "Local chain (simulation)" : pub.chain.key,
      nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
      rpcUrls: { default: { http: [pub.chain.rpc_url] } },
      blockExplorers: pub.chain.explorer_url
        ? { default: { name: "Explorer", url: pub.chain.explorer_url } }
        : undefined,
    });
    return createConfig({
      chains: [chain],
      connectors: [injected()],
      transports: { [chain.id]: http() },
    });
  }, [pub]);
  const theme = useMemo(() => {
    const base = phase === "day" ? lightTheme : darkTheme;
    const t = base({ borderRadius: "medium", fontStack: "system" });
    t.colors.accentColor = "var(--c-brass)";
    t.colors.accentColorForeground = "var(--c-on-brass)";
    t.colors.modalBackground = "var(--c-bg)";
    t.colors.modalText = "var(--c-text)";
    t.fonts.body = "var(--font-hanken), sans-serif";
    t.shadows.dialog = "none";
    return t;
  }, [phase]);
  if (!config) {
    return <span className="badge">Wallet unavailable: the API has no chain RPC</span>;
  }
  return (
    <WagmiProvider config={config}>
      <RainbowKitProvider theme={theme} modalSize="compact">
        {openOnMount && <OpenOnMount />}
        <ConnectButton label="Connect" chainStatus="none" showBalance={false} />
      </RainbowKitProvider>
    </WagmiProvider>
  );
}
