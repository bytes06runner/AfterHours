"use client";

import "@rainbow-me/rainbowkit/styles.css";

import {
  type DisclaimerComponent,
  RainbowKitProvider,
  connectorsForWallets,
  darkTheme,
  lightTheme,
  useConnectModal,
} from "@rainbow-me/rainbowkit";
import {
  braveWallet,
  coinbaseWallet,
  injectedWallet,
  metaMaskWallet,
  okxWallet,
  phantomWallet,
  rabbyWallet,
  rainbowWallet,
  walletConnectWallet,
} from "@rainbow-me/rainbowkit/wallets";
import { useEffect, useMemo, useState } from "react";
import { defineChain } from "viem";
import { WagmiProvider, createConfig, http, useAccount } from "wagmi";

import { usePhase } from "@/lib/phase";

import { WalletReady } from "./ready";
import { useConfig } from "@/lib/queries";

/** If a wallet has not answered a connection request after a while, say what to do. */
function ConnectWatch() {
  const { status } = useAccount();
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    if (status !== "connecting") {
      const t = window.setTimeout(() => setStuck(false), 0);
      return () => window.clearTimeout(t);
    }
    const t = window.setTimeout(() => setStuck(true), 15_000);
    return () => window.clearTimeout(t);
  }, [status]);
  if (!stuck) return null;
  return (
    <div
      role="alert"
      className="fixed inset-x-4 top-4 z-[2147483647] mx-auto max-w-[520px] rounded-[12px] border-[1.25px] border-rule bg-bg p-4 text-[16px] font-semibold"
    >
      Your wallet has not answered yet. Open it from the browser toolbar and approve the request, or
      close the window and pick another wallet by name.
    </div>
  );
}

function OpenOnMount({ open }: { open: boolean }) {
  const { openConnectModal } = useConnectModal();
  useEffect(() => {
    if (open) openConnectModal?.();
  }, [open, openConnectModal]);
  return null;
}

/** Shown under the wallet list: what to do when a wallet does not open. */
const Help: DisclaimerComponent = ({ Text }) => (
  <Text>
    Nothing happens after you pick a wallet? Open the wallet from your browser toolbar and approve
    the request there (in Brave, the wallet icon at the top right). If your browser has more than
    one wallet, pick it by name above rather than &quot;Browser Wallet&quot;.
  </Text>
);

/** wagmi and RainbowKit, built from /v1/config/public (chain id, name, gas currency, RPC). */
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
      name: pub.chain.name,
      nativeCurrency: pub.chain.native_currency,
      rpcUrls: { default: { http: [pub.chain.rpc_url] } },
      blockExplorers: pub.chain.explorer_url
        ? { default: { name: "Explorer", url: pub.chain.explorer_url } }
        : undefined,
    });
    // Extension wallets that need no WalletConnect project are always listed; any other wallet
    // that announces itself (EIP-6963) is added by wagmi's provider discovery. Phone wallets and
    // QR codes need a WalletConnect project id (NEXT_PUBLIC_WC_PROJECT_ID).
    const projectId = process.env.NEXT_PUBLIC_WC_PROJECT_ID ?? "";
    const groups = [
      {
        groupName: "Browser wallets",
        wallets: [braveWallet, rabbyWallet, phantomWallet, coinbaseWallet, injectedWallet],
      },
      ...(projectId
        ? [
            {
              groupName: "More wallets",
              wallets: [metaMaskWallet, rainbowWallet, okxWallet, walletConnectWallet],
            },
          ]
        : []),
    ];
    const connectors = connectorsForWallets(groups, {
      appName: "Afterhours",
      projectId: projectId || "not-configured",
    });
    return createConfig({
      chains: [chain],
      connectors,
      transports: { [chain.id]: http() },
      // ssr: true makes wagmi reconnect in an effect; with false it reconnects during render,
      // which updates RainbowKit's modal mid-render (a React error on the vault page).
      ssr: true,
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
      <RainbowKitProvider
        theme={theme}
        modalSize="compact"
        appInfo={{ appName: "Afterhours", disclaimer: Help }}
      >
        <OpenOnMount open={openModal} />
        <ConnectWatch />
        <WalletReady.Provider value={true}>{children}</WalletReady.Provider>
      </RainbowKitProvider>
    </WagmiProvider>
  );
}
