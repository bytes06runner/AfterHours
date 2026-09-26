"use client";

import { createContext, useContext } from "react";

/** True inside the wagmi and RainbowKit providers; wagmi hooks are safe only then. */
export const WalletReady = createContext(false);
export const useWalletReady = () => useContext(WalletReady);
