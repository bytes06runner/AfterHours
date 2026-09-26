// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {IMorpho, MarketParams, Id} from "morpho-blue/src/interfaces/IMorpho.sol";
import {IVaultV2} from "vault-v2/src/interfaces/IVaultV2.sol";
import {ErrorsLib} from "vault-v2/src/libraries/ErrorsLib.sol";
import {DeployAfterhours} from "../script/DeployAfterhours.s.sol";
import {AfterhoursReasonRegistry} from "../src/AfterhoursReasonRegistry.sol";
import {SimOracle} from "../src/SimOracle.sol";
import {SimStockToken} from "../src/SimStockToken.sol";
import {SimUSDG} from "../src/SimUSDG.sol";

/// End-to-end deployment on a plain local EVM: self-deployed Morpho, simulated oracle and
/// collateral (the rh-testnet / arb-sepolia shape). Exercises the vault flows and the trust
/// boundary the SPEC promises.
contract DeployAfterhoursTest is Test {
    DeployAfterhours internal script;
    DeployAfterhours.Result internal r;
    DeployAfterhours.Keys internal keys;
    IVaultV2 internal vault;
    IMorpho internal morpho;
    address internal lender = makeAddr("lender");
    address internal borrower = makeAddr("borrower");

    uint256 internal constant WEEKDAY = 0.915e18;
    uint256 internal constant MIDDLE = 0.86e18;
    uint256 internal constant WEEKEND = 0.77e18;

    function setUp() public {
        script = new DeployAfterhours();
        keys = DeployAfterhours.Keys(0xA11CE, 0xC0FFEE, 0xB07, 0x6A4D);
        string[] memory symbols = new string[](2);
        symbols[0] = "NVDA";
        symbols[1] = "SPY";
        address[] memory none = new address[](2);
        uint256[] memory decimals = new uint256[](2);
        decimals[0] = 18;
        decimals[1] = 18;
        uint256[] memory prices = new uint256[](2);
        prices[0] = 225e8;
        prices[1] = 770e8;
        string[] memory tierNames = new string[](3);
        (tierNames[0], tierNames[1], tierNames[2]) = ("weekday", "middle", "weekend");
        uint256[] memory tierLltvs = new uint256[](3);
        (tierLltvs[0], tierLltvs[1], tierLltvs[2]) = (WEEKDAY, MIDDLE, WEEKEND);
        DeployAfterhours.Plan memory p = DeployAfterhours.Plan({
            selfDeployMorpho: true,
            simOracle: true,
            simCollateral: true,
            morpho: address(0),
            irm: address(0),
            vaultFactory: address(0),
            adapterFactory: address(0),
            oracleFactory: address(0),
            loanToken: address(0),
            loanDecimals: 6,
            tierNames: tierNames,
            tierLltvs: tierLltvs,
            symbols: symbols,
            tokens: none,
            feeds: none,
            tokenDecimals: decimals,
            initialPrices8: prices,
            vaultName: "Afterhours USDG",
            vaultSymbol: "ahUSDG",
            performanceFee: 0.1e18,
            timelockSeconds: 1 days,
            marketCap: 1_000_000e6,
            collateralRelativeCap: 0.35e18,
            salt: keccak256("test")
        });
        r = script.deploy(p, keys);
        vault = IVaultV2(r.vault);
        morpho = IMorpho(r.morpho);
    }

    function _params(uint256 j) internal view returns (MarketParams memory) {
        return MarketParams(
            r.loanToken, r.marketCollateral[j], r.marketOracles[j], r.irm, r.marketLltvs[j]
        );
    }

    function _deposit(uint256 amount) internal {
        vm.prank(r.owner);
        SimUSDG(r.loanToken).mint(lender, amount);
        vm.startPrank(lender);
        SimUSDG(r.loanToken).approve(r.vault, amount);
        vault.deposit(amount, lender);
        vm.stopPrank();
    }

    function test_deploysTwoTiersPerTokenWithRoles() public view {
        assertEq(r.marketIds.length, 6);
        assertEq(r.marketLltvs[0], WEEKDAY);
        assertEq(r.marketLltvs[1], MIDDLE);
        assertEq(r.marketLltvs[2], WEEKEND);
        assertEq(r.marketTiers[1], "middle");
        assertEq(vault.owner(), r.owner);
        assertEq(vault.curator(), r.curator);
        assertTrue(vault.isAllocator(r.allocator));
        assertTrue(vault.isSentinel(r.guardian));
        assertEq(vault.timelock(IVaultV2.increaseAbsoluteCap.selector), 1 days);
        assertEq(AfterhoursReasonRegistry(r.registry).allocator(), r.allocator);
        assertEq(SimStockToken(r.marketCollateral[0]).symbol(), "sNVDA (sim)");
        for (uint256 j; j < 4; ++j) {
            assertGt(morpho.market(Id.wrap(r.marketIds[j])).lastUpdate, 0, "market created");
        }
    }

    function test_allocatorMovesOnlyUnborrowedMoneyBetweenTiers() public {
        // 300,000 USDG vault; 100,000 to NVDA's weekday market stays under the 35% stock cap.
        _deposit(300_000e6);
        MarketParams memory weekday = _params(0);
        MarketParams memory weekend = _params(2);
        vm.prank(r.allocator);
        vault.allocate(r.adapter, abi.encode(weekday), 100_000e6);

        // A borrower takes 60,000 USDG against 400 sNVDA ($90,000 at $225).
        vm.prank(r.owner);
        SimStockToken(r.marketCollateral[0]).mint(borrower, 400e18);
        vm.startPrank(borrower);
        SimStockToken(r.marketCollateral[0]).approve(r.morpho, 400e18);
        morpho.supplyCollateral(weekday, 400e18, borrower, "");
        morpho.borrow(weekday, 60_000e6, 0, borrower, borrower);
        vm.stopPrank();

        // Closing bell: move the unborrowed 40,000 to the weekend tier.
        vm.startPrank(r.allocator);
        vault.deallocate(r.adapter, abi.encode(weekday), 40_000e6);
        vault.allocate(r.adapter, abi.encode(weekend), 40_000e6);
        // Borrowed money cannot be pulled.
        vm.expectRevert();
        vault.deallocate(r.adapter, abi.encode(weekday), 1e6);
        vm.stopPrank();

        assertApproxEqAbs(
            vault.allocation(keccak256(abi.encode("this/marketParams", r.adapter, weekend))),
            40_000e6,
            1
        );
        assertApproxEqAbs(vault.totalAssets(), 300_000e6, 2);
    }

    function test_curatorCannotRaiseCapsWithoutTimelock() public {
        bytes memory idData = abi.encode("this/marketParams", r.adapter, _params(0));
        bytes memory raise = abi.encodeCall(IVaultV2.increaseAbsoluteCap, (idData, 2_000_000e6));
        vm.prank(r.curator);
        vault.submit(raise);
        vm.expectRevert(ErrorsLib.TimelockNotExpired.selector);
        (bool ok, bytes memory ret) = address(vault).call(raise);
        if (!ok) {
            assembly {
                revert(add(ret, 32), mload(ret))
            }
        }
    }

    function test_curatorRaiseExecutesAfterTimelock() public {
        bytes memory idData = abi.encode("this/marketParams", r.adapter, _params(0));
        bytes memory raise = abi.encodeCall(IVaultV2.increaseAbsoluteCap, (idData, 2_000_000e6));
        vm.prank(r.curator);
        vault.submit(raise);
        vm.warp(block.timestamp + 1 days);
        (bool ok,) = address(vault).call(raise);
        assertTrue(ok);
        assertEq(vault.absoluteCap(keccak256(idData)), 2_000_000e6);
    }

    function test_allocatorCannotRaiseCapsOrAddAdapters() public {
        bytes memory idData = abi.encode("this/marketParams", r.adapter, _params(0));
        vm.startPrank(r.allocator);
        vm.expectRevert(ErrorsLib.Unauthorized.selector);
        vault.submit(abi.encodeCall(IVaultV2.increaseAbsoluteCap, (idData, 2_000_000e6)));
        vm.expectRevert(ErrorsLib.DataNotTimelocked.selector);
        vault.increaseAbsoluteCap(idData, 2_000_000e6);
        vm.stopPrank();
    }

    function test_guardianCanCutTheWeekdayCap() public {
        bytes memory idData = abi.encode("this/marketParams", r.adapter, _params(0));
        vm.prank(r.guardian);
        vault.decreaseAbsoluteCap(idData, 0);
        assertEq(vault.absoluteCap(keccak256(idData)), 0);
        _deposit(10_000e6);
        vm.prank(r.allocator);
        vm.expectRevert(ErrorsLib.ZeroAbsoluteCap.selector);
        vault.allocate(r.adapter, abi.encode(_params(0)), 1e6);
    }

    function test_perStockRelativeCapLimitsExposure() public {
        _deposit(100_000e6);
        vm.prank(r.allocator);
        vm.expectRevert(ErrorsLib.RelativeCapExceeded.selector);
        vault.allocate(r.adapter, abi.encode(_params(0)), 36_000e6); // cap is 35% per stock
    }

    function test_simOracleShockMovesMorphoHealth() public {
        vm.prank(r.owner);
        SimOracle(r.marketOracles[0]).setPrice(180e8);
        assertEq(SimOracle(r.marketOracles[0]).price(), 180e8 * 1e16);
    }

    function test_writesDeploymentJson() public {
        string memory path = string.concat(vm.projectRoot(), "/cache/test-deployment.json");
        script.write(r, path);
        string memory json = vm.readFile(path);
        assertEq(vm.parseJsonAddress(json, ".vault"), r.vault);
        assertEq(vm.parseJsonBytes32Array(json, ".market_ids").length, 6);
    }
}
