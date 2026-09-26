"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";

export default function ConnectLazy() {
  return <ConnectButton label="Connect" chainStatus="none" showBalance={false} />;
}
