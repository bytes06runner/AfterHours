// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IOracle} from "morpho-blue/src/interfaces/IOracle.sol";

/// @title SimOracle (Simulation)
/// @notice Owner-set price for simulated markets: demo shocks and replays only.
/// @dev Implements Morpho's IOracle: price() is the price of 1 asset of collateral quoted in 1
/// asset of loan token, scaled by 1e36, i.e. with `36 + loanDecimals - collateralDecimals`
/// decimals (morpho-blue v1.0.0 src/interfaces/IOracle.sol). The owner sets the collateral
/// price in loan-token units with 8 decimals, like a Chainlink USD feed with USDG = 1 USD, and
/// the same value is exposed through `latestRoundData` so off-chain code reads one interface.
contract SimOracle is IOracle, Ownable {
    error PriceZero();
    error BadDecimals();

    event PriceSet(uint256 price8, uint80 roundId);

    uint8 public constant decimals = 8;
    string public description;
    /// @notice 10 ** (36 + loanDecimals - collateralDecimals - 8).
    uint256 public immutable SCALE;

    uint256 public price8;
    uint80 public roundId;
    uint256 public updatedAt;

    constructor(
        address owner_,
        string memory description_,
        uint8 loanDecimals,
        uint8 collateralDecimals,
        uint256 initialPrice8
    ) Ownable(owner_) {
        if (36 + uint256(loanDecimals) < uint256(collateralDecimals) + decimals) revert BadDecimals();
        SCALE = 10 ** (36 + uint256(loanDecimals) - uint256(collateralDecimals) - decimals);
        description = description_;
        _set(initialPrice8);
    }

    /// @notice Set the collateral price (8 decimals, in loan-token units).
    function setPrice(uint256 newPrice8) external onlyOwner {
        _set(newPrice8);
    }

    /// @inheritdoc IOracle
    function price() external view returns (uint256) {
        return price8 * SCALE;
    }

    /// @notice Chainlink AggregatorV3-compatible read of the same price.
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80) {
        // price8 is set by the owner and far below 2**255.
        // forge-lint: disable-next-line(unsafe-typecast)
        return (roundId, int256(price8), updatedAt, updatedAt, roundId);
    }

    function _set(uint256 newPrice8) internal {
        if (newPrice8 == 0) revert PriceZero();
        price8 = newPrice8;
        updatedAt = block.timestamp;
        roundId += 1;
        emit PriceSet(newPrice8, roundId);
    }
}
