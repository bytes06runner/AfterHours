// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

// Compiles Morpho's 0.8.19 contracts so scripts and tests can deploy them from artifacts with
// vm.deployCode (a 0.8.28 file cannot import a file pinned to 0.8.19).
import {Morpho} from "morpho-blue/src/Morpho.sol";
import {AdaptiveCurveIrm} from "morpho-blue-irm/src/adaptive-curve-irm/AdaptiveCurveIrm.sol";
