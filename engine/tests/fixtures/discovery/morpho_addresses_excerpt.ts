  [ChainId.RobinhoodMainnet]: {
    blue: "0x9D53d5E3bd5E8d4Cbfa6DB1ca238AEA02E651010",
    permit2: "0x000000000022D473030F116dDEE9F6B43aC78BA3",
    bundles: {
      vaultExitBundlesV1: "0xCE29862924756584BBD0D75CA1249d22007E2813",
      vaultBundlesV1: "0xcC108538f36242D6E0d6B9255f6D9Ccd137D70Fe",
      blueBundlesV1: "0x53A1eB6589861F686af7c531211E35Aefe30210f",
    },
    adaptiveCurveIrm: "0x2BD3d5965B26B51814AC95127B2b80dD6CcC0fa1",
    vaultV2BluePublicAllocator: "0xCe5c1aFa115fF8b1D6913509bfc79D9AE08CC857",
    vaultV2Factory: "0x0FBad98595b0186dA120E41f77C102beb49f803c",
    morphoMarketV1AdapterV2Factory:
      "0x79370Ed003CE325C088E530d5e8655c99c2993e1",
    morphoVaultV1AdapterFactory: "0x7a91222F3f7B927bB8fb624593Ca86e111C2F85e",
    registryList: "0xe785a2eFD384BA7B95BaEd3851BC76aeD67C676f",
    chainlinkOracleFactory: "0xB7c16F6F8cF531447Bf27Ca7220f981E79C9cdF2",
    /** @deprecated Pre-liquidation support is deprecated and will be removed in the next major. */
    preLiquidationFactory: "0x0B0cFa151c06d2342799267754b0a2c320C43D5B",
    midnight: "0x6120765Ba5336150BbdDdD0Cd9108B5bFD369632",
    midnightBundles: "0x71aa985ff80AbcE3b8b443845633674Ca9f7575C",
    midnightBlueBuyCallbackFactory:
      "0x53cbCd884CABA07762c72F43283D3fa72de42D4f",
    midnightMempool: "0xcEF685D4796FA80F71a97e803D2c0b6719F1b4E2",
    ecrecoverRatifier: "0x90B800999e4ACd1bD20283BD450bBd2e06D91F7C",
    ecrecoverAuthorizer: "0x75FCdD113fe33a8bEd3CD3C35955DE094Bd2bdf8",
    setterRatifier: "0x708d6Bf6F847202a0755bb5636bE663B174242ea",
    wNative: "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
  },
} as const;

/** Deployment block registry with the same shape as `ChainAddresses`. */
