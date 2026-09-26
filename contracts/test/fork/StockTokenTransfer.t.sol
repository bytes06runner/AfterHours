// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "forge-std/interfaces/IERC20.sol";
import {IMorpho, MarketParams, Id} from "morpho-blue/src/interfaces/IMorpho.sol";

/// Holds tokens; stands in for "an arbitrary contract" in deciding fact 2.
contract Sink {}

/// Deciding fact 2 (SPEC 6.1): can Stock Tokens move between accounts, into an arbitrary
/// contract, and into Morpho as collateral? Addresses come from the discovered file.
/// Run with a fork: FORK_RPC_URL (and optionally FORK_BLOCK) set; skipped otherwise.
contract StockTokenTransferForkTest is Test {
    string internal doc;
    IERC20 internal token;
    IMorpho internal morpho;
    address internal holder;
    bytes32 internal marketId;
    string internal symbol;

    function setUp() public {
        string memory rpc = vm.envOr("FORK_RPC_URL", string(""));
        if (bytes(rpc).length == 0) {
            vm.skip(true);
            return;
        }
        uint256 forkBlock = vm.envOr("FORK_BLOCK", uint256(0));
        if (forkBlock == 0) vm.createSelectFork(rpc);
        else vm.createSelectFork(rpc, forkBlock);

        doc = vm.readFile(string.concat(vm.projectRoot(), "/../deployments/fork.discovered.json"));
        symbol = vm.envOr("STOCK_SYMBOL", abi.decode(vm.parseJson(doc, ".selected[0]"), (string)));
        string memory base = string.concat(".stock_tokens.", symbol);
        token = IERC20(vm.parseJsonAddress(doc, string.concat(base, ".address")));
        morpho = IMorpho(vm.parseJsonAddress(doc, ".core.morpho_blue.address"));
        // A Uniswap v3 pool is a real holder of the token; pools[] is sorted by depth.
        holder = vm.parseJsonAddress(doc, string.concat(base, ".pools[0].address_or_id"));
        marketId = vm.parseJsonBytes32(doc, string.concat(base, ".morpho_markets[0].market_id"));
    }

    function test_transfersBetweenFreshAccountsAndIntoAContract() public {
        uint256 amount = 1e18;
        address alice = makeAddr("alice");
        address bob = makeAddr("bob");
        Sink sink = new Sink();

        vm.prank(holder);
        assertTrue(token.transfer(alice, amount), "holder -> alice");
        assertEq(token.balanceOf(alice), amount);

        vm.prank(alice);
        assertTrue(token.transfer(bob, amount / 2), "alice -> bob");
        assertEq(token.balanceOf(bob), amount / 2);

        vm.prank(bob);
        assertTrue(token.transfer(address(sink), amount / 2), "bob -> contract");
        assertEq(token.balanceOf(address(sink)), amount / 2);
    }

    function test_suppliesAndWithdrawsCollateralInMorpho() public {
        uint256 amount = 1e18;
        address alice = makeAddr("alice");
        MarketParams memory params = morpho.idToMarketParams(Id.wrap(marketId));
        assertEq(params.collateralToken, address(token), "market collateral is the token");

        vm.prank(holder);
        token.transfer(alice, amount);

        vm.startPrank(alice);
        token.approve(address(morpho), amount);
        morpho.supplyCollateral(params, amount, alice, "");
        uint128 collateral = morpho.position(Id.wrap(marketId), alice).collateral;
        assertEq(collateral, amount, "collateral recorded");
        morpho.withdrawCollateral(params, amount, alice, alice);
        vm.stopPrank();
        assertEq(token.balanceOf(alice), amount, "collateral returned");
    }
}
