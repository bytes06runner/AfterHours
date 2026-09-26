// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {SimOracle} from "../src/SimOracle.sol";
import {SimStockToken} from "../src/SimStockToken.sol";

contract SimContractsTest is Test {
    address internal owner = makeAddr("owner");

    function test_oracleScalingMatchesMorpho() public {
        // USDG has 6 decimals, the Stock Token 18. 1 token at $225.66 is worth 225.66 USDG.
        SimOracle oracle = new SimOracle(owner, "sNVDA (sim) / USDG", 6, 18, 225_66000000);
        // price() has 36 + 6 - 18 = 24 decimals: 225.66 * 1e24.
        assertEq(oracle.price(), 22566 * 1e22);
        // 1e18 collateral units * price / 1e36 = loan units: 225.66 USDG = 225_660_000.
        assertEq(uint256(1e18) * oracle.price() / 1e36, 225_660_000);
    }

    function test_oracleOwnerSetsPriceAndRounds() public {
        SimOracle oracle = new SimOracle(owner, "x", 6, 18, 100e8);
        vm.warp(1000);
        vm.prank(owner);
        oracle.setPrice(80e8);
        (uint80 round, int256 answer,, uint256 updated,) = oracle.latestRoundData();
        assertEq(round, 2);
        assertEq(answer, 80e8);
        assertEq(updated, 1000);
        assertEq(oracle.price(), 80e8 * oracle.SCALE());
    }

    function test_oracleGuards() public {
        SimOracle oracle = new SimOracle(owner, "x", 6, 18, 1e8);
        vm.expectRevert(
            abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, address(this))
        );
        oracle.setPrice(2e8);
        vm.prank(owner);
        vm.expectRevert(SimOracle.PriceZero.selector);
        oracle.setPrice(0);
        vm.expectRevert(SimOracle.BadDecimals.selector);
        new SimOracle(owner, "x", 0, 40, 1e8);
    }

    function test_simTokenIsLabelledAndOwnerMints() public {
        SimStockToken token = new SimStockToken(owner, "NVDA", 18);
        assertEq(token.name(), "NVDA Stock Token (sim)");
        assertEq(token.symbol(), "sNVDA (sim)");
        assertEq(token.decimals(), 18);
        vm.prank(owner);
        token.mint(address(this), 5e18);
        assertEq(token.balanceOf(address(this)), 5e18);
        vm.expectRevert(
            abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, address(this))
        );
        token.mint(address(this), 1);
    }
}
