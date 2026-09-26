/**
 * Verify on chain, in the browser (docs/DESIGN.md VerifyBadge). Recompute the reason hash as
 * keccak256 of the RFC 8785 canonical card (without its `tx` block and stored hash), read the
 * registry's ReasonLogged event from the card's transaction, and compare. Nothing is trusted
 * from the API except the card itself.
 */
import canonicalize from "canonicalize";
import { keccak_256 } from "@noble/hashes/sha3.js";
import { bytesToHex, utf8ToBytes } from "@noble/hashes/utils.js";
import { createPublicClient, decodeEventLog, http, parseAbiItem, type Hex } from "viem";

import type { Card } from "./api";

const NOT_HASHED = new Set(["tx", "reason_hash"]);

export const REASON_LOGGED = parseAbiItem(
  "event ReasonLogged(uint256 indexed seq, bytes32 indexed subject, bytes32 reasonHash, string uri, uint64 timestamp)",
);

/** RFC 8785 canonical JSON of the hashed part of a card. */
export function canonicalCard(card: Record<string, unknown>): string {
  const body = Object.fromEntries(Object.entries(card).filter(([k]) => !NOT_HASHED.has(k)));
  const text = canonicalize(body);
  if (text === undefined) throw new Error("card could not be canonicalised");
  return text;
}

/** keccak256 of the canonical card, 0x-prefixed. */
export function reasonHash(card: Record<string, unknown>): Hex {
  return `0x${bytesToHex(keccak_256(utf8ToBytes(canonicalCard(card))))}`;
}

export type Verdict =
  | { status: "matched"; recomputed: Hex; onchain: Hex; seq: bigint; block: bigint; tx: Hex }
  | { status: "mismatched"; recomputed: Hex; onchain: Hex; seq: bigint; block: bigint; tx: Hex }
  | { status: "event_missing" | "no_tx"; recomputed: Hex; tx?: Hex }
  | { status: "unreachable"; recomputed: Hex; message: string };

/** Recompute the hash and check it against the registry event in the card's transaction. */
export async function verifyOnChain(
  card: Card,
  rpcUrl: string,
  registry: string,
): Promise<Verdict> {
  const recomputed = reasonHash(card as unknown as Record<string, unknown>);
  const tx = card.tx?.registry_tx as Hex | undefined;
  if (!tx) return { status: "no_tx", recomputed };
  let receipt;
  try {
    receipt = await createPublicClient({ transport: http(rpcUrl) }).getTransactionReceipt({
      hash: tx,
    });
  } catch (error) {
    return {
      status: "unreachable",
      recomputed,
      message: error instanceof Error ? error.message : String(error),
    };
  }
  for (const log of receipt.logs) {
    if (log.address.toLowerCase() !== registry.toLowerCase()) continue;
    try {
      const decoded = decodeEventLog({ abi: [REASON_LOGGED], data: log.data, topics: log.topics });
      const onchain = decoded.args.reasonHash as Hex;
      const subjectOk =
        (decoded.args.subject as string).toLowerCase() === card.subject.toLowerCase();
      const status =
        onchain.toLowerCase() === recomputed.toLowerCase() && subjectOk ? "matched" : "mismatched";
      return {
        status,
        recomputed,
        onchain,
        seq: decoded.args.seq as bigint,
        block: receipt.blockNumber,
        tx,
      };
    } catch {
      /* not a ReasonLogged log */
    }
  }
  return { status: "event_missing", recomputed, tx };
}
