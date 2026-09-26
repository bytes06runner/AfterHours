// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {
    AfterhoursReasonRegistry,
    IAfterhoursReasonRegistry
} from "../src/AfterhoursReasonRegistry.sol";

contract AfterhoursReasonRegistryTest is Test {
    AfterhoursReasonRegistry internal registry;
    address internal owner = makeAddr("owner");
    address internal allocator = makeAddr("allocator");
    address internal stranger = makeAddr("stranger");
    bytes32 internal constant SUBJECT = keccak256("market");
    bytes32 internal constant HASH = keccak256("card");

    event ReasonLogged(
        uint256 indexed seq,
        bytes32 indexed subject,
        bytes32 reasonHash,
        string uri,
        uint64 timestamp
    );
    event AllocatorSet(address indexed allocator);

    function setUp() public {
        registry = new AfterhoursReasonRegistry(owner, allocator);
    }

    function test_constructorSetsRoles() public view {
        assertEq(registry.owner(), owner);
        assertEq(registry.allocator(), allocator);
        assertEq(registry.seq(), 0);
    }

    function test_constructorEmitsAllocatorSet() public {
        vm.expectEmit(true, false, false, false);
        emit AllocatorSet(allocator);
        new AfterhoursReasonRegistry(owner, allocator);
    }

    function test_logReasonEmitsExactEventAndIncrementsSeq() public {
        vm.warp(1_790_355_600);
        vm.expectEmit(true, true, false, true, address(registry));
        emit ReasonLogged(1, SUBJECT, HASH, "ipfs://card-1", uint64(1_790_355_600));
        vm.prank(allocator);
        registry.logReason(SUBJECT, HASH, "ipfs://card-1");
        assertEq(registry.seq(), 1);

        vm.expectEmit(true, true, false, true, address(registry));
        emit ReasonLogged(2, SUBJECT, HASH, "", uint64(1_790_355_600));
        vm.prank(allocator);
        registry.logReason(SUBJECT, HASH, "");
        assertEq(registry.seq(), 2);
    }

    function test_logReasonRejectsNonAllocator() public {
        vm.expectRevert(
            abi.encodeWithSelector(AfterhoursReasonRegistry.NotAllocator.selector, stranger)
        );
        vm.prank(stranger);
        registry.logReason(SUBJECT, HASH, "");
        vm.expectRevert(
            abi.encodeWithSelector(AfterhoursReasonRegistry.NotAllocator.selector, owner)
        );
        vm.prank(owner);
        registry.logReason(SUBJECT, HASH, "");
    }

    function test_logReasonRejectsEmptyHash() public {
        vm.expectRevert(AfterhoursReasonRegistry.EmptyReasonHash.selector);
        vm.prank(allocator);
        registry.logReason(SUBJECT, bytes32(0), "");
    }

    function test_setAllocatorOnlyOwner() public {
        address next = makeAddr("next");
        vm.expectRevert(
            abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, stranger)
        );
        vm.prank(stranger);
        registry.setAllocator(next);

        vm.expectEmit(true, false, false, false, address(registry));
        emit AllocatorSet(next);
        vm.prank(owner);
        registry.setAllocator(next);
        assertEq(registry.allocator(), next);

        vm.expectRevert(
            abi.encodeWithSelector(AfterhoursReasonRegistry.NotAllocator.selector, allocator)
        );
        vm.prank(allocator);
        registry.logReason(SUBJECT, HASH, "");
    }

    function test_ownershipTransferIsTwoStep() public {
        address next = makeAddr("nextOwner");
        vm.prank(owner);
        registry.transferOwnership(next);
        assertEq(registry.owner(), owner);
        vm.prank(next);
        registry.acceptOwnership();
        assertEq(registry.owner(), next);
    }

    function testFuzz_seqCountsEveryLog(uint8 n) public {
        for (uint256 i; i < n; ++i) {
            vm.prank(allocator);
            registry.logReason(bytes32(i), keccak256(abi.encode(i)), "");
        }
        assertEq(registry.seq(), n);
    }

    function test_implementsInterface() public view {
        IAfterhoursReasonRegistry r = IAfterhoursReasonRegistry(address(registry));
        assertEq(r.seq(), 0);
    }
}
