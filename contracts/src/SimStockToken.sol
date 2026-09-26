// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title SimStockToken (Simulation)
/// @notice Stand-in for a Robinhood Stock Token where the real one cannot be used (testnets).
/// @dev Name and symbol always end in "(sim)"; decimals match the real token (18, per
/// Robinhood's docs). Only the owner can mint.
contract SimStockToken is ERC20, Ownable {
    uint8 private immutable _decimals;

    constructor(address owner_, string memory ticker, uint8 decimals_)
        ERC20(string.concat(ticker, " Stock Token (sim)"), string.concat("s", ticker, " (sim)"))
        Ownable(owner_)
    {
        _decimals = decimals_;
    }

    function decimals() public view override returns (uint8) {
        return _decimals;
    }

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
