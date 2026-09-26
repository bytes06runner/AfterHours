// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Script} from "forge-std/Script.sol";
import {stdJson} from "forge-std/StdJson.sol";
import {IMorpho, MarketParams, Id} from "morpho-blue/src/interfaces/IMorpho.sol";
import {MarketParamsLib} from "morpho-blue/src/libraries/MarketParamsLib.sol";
import {IVaultV2} from "vault-v2/src/interfaces/IVaultV2.sol";
import {VaultV2Factory} from "vault-v2/src/VaultV2Factory.sol";
import {
    MorphoMarketV1AdapterV2Factory
} from "vault-v2/src/adapters/MorphoMarketV1AdapterV2Factory.sol";
import {AfterhoursReasonRegistry} from "../src/AfterhoursReasonRegistry.sol";
import {SimOracle} from "../src/SimOracle.sol";
import {SimStockToken} from "../src/SimStockToken.sol";
import {SimUSDG} from "../src/SimUSDG.sol";

/// @dev Same ABI as morpho-blue-oracles v2.0.0 IMorphoChainlinkOracleV2Factory, declared here because
/// that interface imports the oracle contract, which is pinned to solc 0.8.21.
interface IChainlinkOracleV2Factory {
    function createMorphoChainlinkOracleV2(
        address baseVault,
        uint256 baseVaultConversionSample,
        address baseFeed1,
        address baseFeed2,
        uint256 baseTokenDecimals,
        address quoteVault,
        uint256 quoteVaultConversionSample,
        address quoteFeed1,
        address quoteFeed2,
        uint256 quoteTokenDecimals,
        bytes32 salt
    ) external returns (address oracle);
}

/// @title DeployAfterhours
/// @notice Deploys Afterhours for one profile from a plan file written by `afterhours deploy plan`
/// (addresses and parameters come from config and the discovered file, never from literals).
/// Steps: Morpho (reuse or self-deploy), loan token and collateral (real or simulated), one oracle
/// and two markets (weekday, weekend tiers) per Stock Token, a Vault V2 with a Market V1 adapter,
/// roles, caps and timelocks, and the reason registry. Writes the deployment JSON.
contract DeployAfterhours is Script {
    using stdJson for string;
    using MarketParamsLib for MarketParams;

    uint256 internal constant WAD = 1e18;

    struct Keys {
        uint256 deployer;
        uint256 curator;
        uint256 allocator;
        uint256 guardian;
    }

    struct Plan {
        bool selfDeployMorpho;
        bool simOracle;
        bool simCollateral;
        address morpho;
        address irm;
        address vaultFactory;
        address adapterFactory;
        address oracleFactory;
        address loanToken;
        uint8 loanDecimals;
        uint256 weekdayLltv;
        uint256 weekendLltv;
        string[] symbols;
        address[] tokens;
        address[] feeds;
        uint256[] tokenDecimals;
        uint256[] initialPrices8;
        string vaultName;
        string vaultSymbol;
        uint256 performanceFee;
        uint256 timelockSeconds;
        uint256 marketCap;
        uint256 collateralRelativeCap;
        bytes32 salt;
    }

    struct Result {
        address morpho;
        address irm;
        address vaultFactory;
        address adapterFactory;
        address loanToken;
        address vault;
        address adapter;
        address registry;
        address owner;
        address curator;
        address allocator;
        address guardian;
        string[] marketSymbols;
        string[] marketTiers;
        bytes32[] marketIds;
        address[] marketCollateral;
        address[] marketOracles;
        uint256[] marketLltvs;
    }

    function run() external {
        Plan memory p = readPlan(vm.readFile(vm.envString("PLAN_PATH")));
        Keys memory k = Keys(
            vm.envUint("DEPLOYER_PK"),
            vm.envUint("CURATOR_PK"),
            vm.envUint("ALLOCATOR_PK"),
            vm.envUint("GUARDIAN_PK")
        );
        Result memory r = deploy(p, k);
        write(r, vm.envString("DEPLOYMENT_PATH"));
    }

    function readPlan(string memory json) public pure returns (Plan memory p) {
        p.selfDeployMorpho = json.readBool(".self_deploy_morpho");
        p.simOracle = json.readBool(".sim_oracle");
        p.simCollateral = json.readBool(".sim_collateral");
        p.morpho = json.readAddress(".morpho.blue");
        p.irm = json.readAddress(".morpho.irm");
        p.vaultFactory = json.readAddress(".morpho.vault_v2_factory");
        p.adapterFactory = json.readAddress(".morpho.adapter_factory");
        p.oracleFactory = json.readAddress(".morpho.oracle_factory");
        p.loanToken = json.readAddress(".loan_token.address");
        p.loanDecimals = uint8(json.readUint(".loan_token.decimals"));
        p.weekdayLltv = json.readUint(".tiers.weekday_wad");
        p.weekendLltv = json.readUint(".tiers.weekend_wad");
        p.symbols = json.readStringArray(".tokens.symbols");
        p.tokens = json.readAddressArray(".tokens.addresses");
        p.feeds = json.readAddressArray(".tokens.feeds");
        p.tokenDecimals = json.readUintArray(".tokens.decimals");
        p.initialPrices8 = json.readUintArray(".tokens.initial_prices_8");
        p.vaultName = json.readString(".vault.name");
        p.vaultSymbol = json.readString(".vault.symbol");
        p.performanceFee = json.readUint(".vault.performance_fee_wad");
        p.timelockSeconds = json.readUint(".vault.timelock_seconds");
        p.marketCap = json.readUint(".vault.market_cap_assets");
        p.collateralRelativeCap = json.readUint(".vault.collateral_relative_cap_wad");
        p.salt = json.readBytes32(".salt");
    }

    function deploy(Plan memory p, Keys memory k) public returns (Result memory r) {
        r.owner = vm.addr(k.deployer);
        r.curator = vm.addr(k.curator);
        r.allocator = vm.addr(k.allocator);
        r.guardian = vm.addr(k.guardian);

        vm.startBroadcast(k.deployer);
        _morpho(p, r);
        r.loanToken = p.loanToken == address(0) ? address(new SimUSDG(r.owner)) : p.loanToken;
        _markets(p, r);
        r.vault = VaultV2Factory(r.vaultFactory).createVaultV2(r.owner, r.loanToken, p.salt);
        IVaultV2 vault = IVaultV2(r.vault);
        vault.setCurator(r.curator);
        vault.setIsSentinel(r.guardian, true);
        vault.setName(p.vaultName);
        vault.setSymbol(p.vaultSymbol);
        r.adapter =
            MorphoMarketV1AdapterV2Factory(r.adapterFactory).createMorphoMarketV1AdapterV2(r.vault);
        r.registry = address(new AfterhoursReasonRegistry(r.owner, r.allocator));
        vm.stopBroadcast();

        vm.startBroadcast(k.curator);
        _curate(p, r);
        vm.stopBroadcast();
    }

    function _morpho(Plan memory p, Result memory r) internal {
        if (!p.selfDeployMorpho) {
            (r.morpho, r.irm, r.vaultFactory, r.adapterFactory) =
            (p.morpho, p.irm, p.vaultFactory, p.adapterFactory);
            return;
        }
        r.morpho = vm.deployCode("Morpho.sol:Morpho", abi.encode(r.owner));
        r.irm = vm.deployCode("AdaptiveCurveIrm.sol:AdaptiveCurveIrm", abi.encode(r.morpho));
        IMorpho(r.morpho).enableIrm(r.irm);
        IMorpho(r.morpho).enableLltv(p.weekdayLltv);
        IMorpho(r.morpho).enableLltv(p.weekendLltv);
        r.vaultFactory = address(new VaultV2Factory());
        r.adapterFactory = address(new MorphoMarketV1AdapterV2Factory(r.morpho, r.irm));
    }

    function _markets(Plan memory p, Result memory r) internal {
        uint256 n = p.symbols.length;
        r.marketSymbols = new string[](2 * n);
        r.marketTiers = new string[](2 * n);
        r.marketIds = new bytes32[](2 * n);
        r.marketCollateral = new address[](2 * n);
        r.marketOracles = new address[](2 * n);
        r.marketLltvs = new uint256[](2 * n);
        for (uint256 i; i < n; ++i) {
            address collateral = p.simCollateral
                ? address(new SimStockToken(r.owner, p.symbols[i], uint8(p.tokenDecimals[i])))
                : p.tokens[i];
            address oracle = _oracle(p, r, i);
            for (uint256 t; t < 2; ++t) {
                uint256 lltv = t == 0 ? p.weekdayLltv : p.weekendLltv;
                MarketParams memory mp = MarketParams(r.loanToken, collateral, oracle, r.irm, lltv);
                if (IMorpho(r.morpho).market(mp.id()).lastUpdate == 0) {
                    IMorpho(r.morpho).createMarket(mp);
                }
                uint256 j = 2 * i + t;
                r.marketSymbols[j] = p.symbols[i];
                r.marketTiers[j] = t == 0 ? "weekday" : "weekend";
                r.marketIds[j] = Id.unwrap(mp.id());
                r.marketCollateral[j] = collateral;
                r.marketOracles[j] = oracle;
                r.marketLltvs[j] = lltv;
            }
        }
    }

    function _oracle(Plan memory p, Result memory r, uint256 i) internal returns (address) {
        if (p.simOracle) {
            string memory name = string.concat("s", p.symbols[i], " (sim) / USDG");
            return address(
                new SimOracle(
                    r.owner, name, p.loanDecimals, uint8(p.tokenDecimals[i]), p.initialPrices8[i]
                )
            );
        }
        // Same shape as the existing Stock Token markets on Robinhood Chain (M1): the token's
        // Chainlink feed as base, no quote feed (USDG treated as 1 USD), no vaults.
        bytes32 salt = keccak256(abi.encode(p.salt, p.symbols[i]));
        return
            _chainlinkOracle(p.oracleFactory, p.feeds[i], p.tokenDecimals[i], p.loanDecimals, salt);
    }

    function _chainlinkOracle(
        address factory,
        address feed,
        uint256 baseDecimals,
        uint256 quoteDecimals,
        bytes32 salt
    ) internal returns (address) {
        return IChainlinkOracleV2Factory(factory)
            .createMorphoChainlinkOracleV2(
                address(0),
                1,
                feed,
                address(0),
                baseDecimals,
                address(0),
                1,
                address(0),
                address(0),
                quoteDecimals,
                salt
            );
    }

    /// Curator actions are timelocked in Vault V2: submit, then execute. Timelocks start at 0,
    /// so everything executes at once; the last step raises the timelocks.
    function _curate(Plan memory p, Result memory r) internal {
        IVaultV2 vault = IVaultV2(r.vault);
        _exec(vault, abi.encodeCall(IVaultV2.addAdapter, (r.adapter)));
        _exec(vault, abi.encodeCall(IVaultV2.setIsAllocator, (r.allocator, true)));
        bytes memory adapterId = abi.encode("this", r.adapter);
        _exec(vault, abi.encodeCall(IVaultV2.increaseAbsoluteCap, (adapterId, type(uint128).max)));
        _exec(vault, abi.encodeCall(IVaultV2.increaseRelativeCap, (adapterId, WAD)));
        for (uint256 j; j < r.marketIds.length; ++j) {
            if (j % 2 == 0) {
                bytes memory collateralId = abi.encode("collateralToken", r.marketCollateral[j]);
                _exec(
                    vault,
                    abi.encodeCall(IVaultV2.increaseAbsoluteCap, (collateralId, type(uint128).max))
                );
                _exec(
                    vault,
                    abi.encodeCall(
                        IVaultV2.increaseRelativeCap, (collateralId, p.collateralRelativeCap)
                    )
                );
            }
            MarketParams memory mp = MarketParams(
                r.loanToken, r.marketCollateral[j], r.marketOracles[j], r.irm, r.marketLltvs[j]
            );
            bytes memory marketId = abi.encode("this/marketParams", r.adapter, mp);
            _exec(vault, abi.encodeCall(IVaultV2.increaseAbsoluteCap, (marketId, p.marketCap)));
            _exec(vault, abi.encodeCall(IVaultV2.increaseRelativeCap, (marketId, WAD)));
        }
        _exec(vault, abi.encodeCall(IVaultV2.setPerformanceFeeRecipient, (r.curator)));
        _exec(vault, abi.encodeCall(IVaultV2.setPerformanceFee, (p.performanceFee)));
        bytes4[5] memory guarded = [
            IVaultV2.addAdapter.selector,
            IVaultV2.increaseAbsoluteCap.selector,
            IVaultV2.increaseRelativeCap.selector,
            IVaultV2.setIsAllocator.selector,
            IVaultV2.setPerformanceFee.selector
        ];
        for (uint256 s; s < guarded.length; ++s) {
            _exec(vault, abi.encodeCall(IVaultV2.increaseTimelock, (guarded[s], p.timelockSeconds)));
        }
    }

    function _exec(IVaultV2 vault, bytes memory data) internal {
        vault.submit(data);
        (bool ok, bytes memory ret) = address(vault).call(data);
        if (!ok) {
            assembly {
                revert(add(ret, 32), mload(ret))
            }
        }
    }

    function write(Result memory r, string memory path) public {
        string memory o = "deployment";
        vm.serializeUint(o, "chain_id", block.chainid);
        vm.serializeUint(o, "block", block.number);
        vm.serializeAddress(o, "morpho", r.morpho);
        vm.serializeAddress(o, "irm", r.irm);
        vm.serializeAddress(o, "vault_v2_factory", r.vaultFactory);
        vm.serializeAddress(o, "adapter_factory", r.adapterFactory);
        vm.serializeAddress(o, "loan_token", r.loanToken);
        vm.serializeAddress(o, "vault", r.vault);
        vm.serializeAddress(o, "adapter", r.adapter);
        vm.serializeAddress(o, "registry", r.registry);
        vm.serializeAddress(o, "owner", r.owner);
        vm.serializeAddress(o, "curator", r.curator);
        vm.serializeAddress(o, "allocator", r.allocator);
        vm.serializeAddress(o, "guardian", r.guardian);
        vm.serializeString(o, "market_symbols", r.marketSymbols);
        vm.serializeString(o, "market_tiers", r.marketTiers);
        vm.serializeBytes32(o, "market_ids", r.marketIds);
        vm.serializeAddress(o, "market_collateral", r.marketCollateral);
        vm.serializeAddress(o, "market_oracles", r.marketOracles);
        string memory json = vm.serializeUint(o, "market_lltvs", r.marketLltvs);
        vm.writeJson(json, path);
    }
}
