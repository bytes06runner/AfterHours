// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "forge-std/interfaces/IERC20.sol";
import {IMorpho, MarketParams, Id} from "morpho-blue/src/interfaces/IMorpho.sol";
import {IOracle} from "morpho-blue/src/interfaces/IOracle.sol";
import {IVaultV2} from "vault-v2/src/interfaces/IVaultV2.sol";
import {DeployAfterhours} from "../../script/DeployAfterhours.s.sol";
import {AfterhoursReasonRegistry} from "../../src/AfterhoursReasonRegistry.sol";

interface IAggregator {
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}

/// Deploys Afterhours against Robinhood Chain's real Morpho, Chainlink oracle factory, Vault V2
/// factory, USDG and Stock Tokens (the fork profile plan), then runs the closing-bell move.
/// Needs FORK_RPC_URL; pins FORK_BLOCK when set (archive RPC), else forks the head.
contract DeployForkTest is Test {
    string internal plan;
    string internal discovered;
    DeployAfterhours internal script;
    DeployAfterhours.Result internal r;

    function setUp() public {
        string memory rpc = vm.envOr("FORK_RPC_URL", string(""));
        if (bytes(rpc).length == 0) {
            vm.skip(true);
            return;
        }
        uint256 forkBlock = vm.envOr("FORK_BLOCK", uint256(0));
        if (forkBlock == 0) vm.createSelectFork(rpc);
        else vm.createSelectFork(rpc, forkBlock);
        string memory root = string.concat(vm.projectRoot(), "/../deployments/");
        plan = vm.readFile(string.concat(root, "fork.plan.json"));
        discovered = vm.readFile(string.concat(root, "fork.discovered.json"));
        script = new DeployAfterhours();
        r = script.deploy(
            script.readPlan(plan), DeployAfterhours.Keys(0xA11CE, 0xC0FFEE, 0xB07, 0x6A4D)
        );
    }

    function _params(uint256 j) internal view returns (MarketParams memory) {
        return MarketParams(
            r.loanToken, r.marketCollateral[j], r.marketOracles[j], r.irm, r.marketLltvs[j]
        );
    }

    function test_marketsUseRealMorphoAndChainlink() public view {
        IMorpho morpho = IMorpho(r.morpho);
        for (uint256 j; j < r.marketIds.length; ++j) {
            assertGt(morpho.market(Id.wrap(r.marketIds[j])).lastUpdate, 0, "market exists");
        }
        // Oracle price equals the Chainlink answer scaled to Morpho's 1e36 convention.
        address feed = vm.parseJsonAddress(plan, ".tokens.feeds[0]");
        (, int256 answer,,,) = IAggregator(feed).latestRoundData();
        assertEq(IOracle(r.marketOracles[0]).price(), uint256(answer) * 1e16);
        assertEq(r.loanToken, vm.parseJsonAddress(discovered, ".core.usdg.address"));
        assertEq(IVaultV2(r.vault).timelock(IVaultV2.increaseAbsoluteCap.selector), 1 days);
    }

    function test_closingBellMoveOnRealMarkets() public {
        IVaultV2 vault = IVaultV2(r.vault);
        IMorpho morpho = IMorpho(r.morpho);
        // The deepest NVDA/USDG Uniswap v3 pool holds both tokens: a real source of balances.
        address pool = vm.parseJsonAddress(discovered, ".stock_tokens.NVDA.pools[0].address_or_id");
        address lender = makeAddr("lender");
        address borrower = makeAddr("borrower");
        vm.startPrank(pool);
        IERC20(r.loanToken).transfer(lender, 300_000e6);
        IERC20(r.marketCollateral[0]).transfer(borrower, 400e18);
        vm.stopPrank();

        vm.startPrank(lender);
        IERC20(r.loanToken).approve(r.vault, 300_000e6);
        vault.deposit(300_000e6, lender);
        vm.stopPrank();
        vm.prank(r.allocator);
        vault.allocate(r.adapter, abi.encode(_params(0)), 100_000e6);

        vm.startPrank(borrower);
        IERC20(r.marketCollateral[0]).approve(r.morpho, 400e18);
        morpho.supplyCollateral(_params(0), 400e18, borrower, "");
        morpho.borrow(_params(0), 60_000e6, 0, borrower, borrower);
        vm.stopPrank();

        vm.startPrank(r.allocator);
        vault.deallocate(r.adapter, abi.encode(_params(0)), 40_000e6);
        vault.allocate(r.adapter, abi.encode(_params(1)), 40_000e6);
        AfterhoursReasonRegistry(r.registry).logReason(r.marketIds[0], keccak256("card"), "");
        vm.stopPrank();

        bytes32 weekendId = keccak256(abi.encode("this/marketParams", r.adapter, _params(1)));
        assertApproxEqAbs(vault.allocation(weekendId), 40_000e6, 1);
        assertEq(AfterhoursReasonRegistry(r.registry).seq(), 1);
    }
}
