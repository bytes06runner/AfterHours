// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Ownable2Step, Ownable} from "@openzeppelin/contracts/access/Ownable2Step.sol";

/// @title AfterhoursReasonRegistry
/// @notice Anchors the hash of every Afterhours reason card onchain.
/// @dev `reasonHash` is keccak256 of the reason card (without its `tx` block) serialised with
/// RFC 8785 JSON canonicalisation. `subject` is a Morpho market id, or a vault-level constant.
/// Anyone can recompute the hash from the card the API serves and compare it with the event.
interface IAfterhoursReasonRegistry {
    event ReasonLogged(
        uint256 indexed seq,
        bytes32 indexed subject,
        bytes32 reasonHash,
        string uri,
        uint64 timestamp
    );
    event AllocatorSet(address indexed allocator);

    function logReason(bytes32 subject, bytes32 reasonHash, string calldata uri) external;
    function setAllocator(address allocator) external;
    function seq() external view returns (uint256);
}

contract AfterhoursReasonRegistry is IAfterhoursReasonRegistry, Ownable2Step {
    error NotAllocator(address caller);
    error EmptyReasonHash();

    /// @notice The only address allowed to log reasons (the allocator bot).
    address public allocator;

    /// @notice Number of reasons logged. The first reason has seq 1.
    uint256 public seq;

    constructor(address owner_, address allocator_) Ownable(owner_) {
        _setAllocator(allocator_);
    }

    /// @inheritdoc IAfterhoursReasonRegistry
    function logReason(bytes32 subject, bytes32 reasonHash, string calldata uri) external {
        if (msg.sender != allocator) revert NotAllocator(msg.sender);
        if (reasonHash == bytes32(0)) revert EmptyReasonHash();
        uint256 next = ++seq;
        // Timestamps fit in 64 bits until the year 584942417355; the event type is in the SPEC.
        // forge-lint: disable-next-line(unsafe-typecast)
        emit ReasonLogged(next, subject, reasonHash, uri, uint64(block.timestamp));
    }

    /// @inheritdoc IAfterhoursReasonRegistry
    function setAllocator(address allocator_) external onlyOwner {
        _setAllocator(allocator_);
    }

    function _setAllocator(address allocator_) internal {
        allocator = allocator_;
        emit AllocatorSet(allocator_);
    }
}
