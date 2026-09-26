"use client";

import "@rainbow-me/rainbowkit/styles.css";

import {
  RainbowKitProvider,
  connectorsForWallets,
  darkTheme,
  lightTheme,
  useConnectModal,
} from "@rainbow-me/rainbowkit";
import {
  injectedWallet,
  metaMaskWallet,
  rainbowWallet,
  walletConnectWallet,
} from "@rainbow-me/rainbowkit/wallets";
import { useEffect, useMemo } from "react";
import { defineChain } from "viem";
import { WagmiProvider, createConfig, http } from "wagmi";

import { usePhase } from "@/lib/phase";

import { WalletReady } from "./ready";
import { useConfig } from "@/lib/queries";

function OpenOnMount({ open }: { open: boolean }) {
  const { openConnectModal } = useConnectModal();
  useEffect(() => {
    if (open) openConnectModal?.();
  }, [open, openConnectModal]);
  return null;
}

/** wagmi and RainbowKit, built from /v1/config/public (chain id, name, browser-safe RPC). */
export default function WalletProviders({
  children,
  openModal,
}: {
  children: React.ReactNode;
  openModal: boolean;
}) {
  const { data: pub } = useConfig();
  const { live } = usePhase();
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
    // RainbowKit lists only wallets registered here. The browser wallet always works; the others
    // need a WalletConnect project id (NEXT_PUBLIC_WC_PROJECT_ID).
    const projectId = process.env.NEXT_PUBLIC_WC_PROJECT_ID ?? "";
    const wallets = projectId
      ? [injectedWallet, metaMaskWallet, rainbowWallet, walletConnectWallet]
      : [injectedWallet];
    const connectors = connectorsForWallets([{ groupName: "Wallets", wallets }], {
      appName: "Afterhours",
      projectId: projectId || "not-configured",
    });
    return createConfig({
      chains: [chain],
      connectors,
      transports: { [chain.id]: http() },
      ssr: false,
    });
  }, [pub]);
  const theme = useMemo(() => {
    const t = (live === "day" ? lightTheme : darkTheme)({
      borderRadius: "medium",
      fontStack: "system",
    });
    t.colors.accentColor = "var(--c-brass)";
    t.colors.accentColorForeground = "var(--c-on-brass)";
    t.colors.modalBackground = "var(--c-bg)";
    t.colors.modalText = "var(--c-text)";
    t.fonts.body = "var(--font-hanken), sans-serif";
    t.shadows.dialog = "none";
    return t;
  }, [live]);
  if (!config) return <>{children}</>;
  return (
    <WagmiProvider config={config}>
      <RainbowKitProvider theme={theme} modalSize="compact">
        <OpenOnMount open={openModal} />
        <WalletReady.Provider value={true}>{children}</WalletReady.Provider>
      </RainbowKitProvider>
    </WagmiProvider>
  );
}
