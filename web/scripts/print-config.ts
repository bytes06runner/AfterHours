/**
 * Reads a public config document on stdin, parses it with the web loader and prints one
 * dotted key. Used by scripts/config-roundtrip.sh to prove YAML changes reach the web.
 */
import { parsePublicConfig } from "../src/lib/config";

async function main(): Promise<void> {
  const key = process.argv[2];
  if (!key) throw new Error("usage: print-config.ts <dotted.key>");
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  let node: unknown = parsePublicConfig(JSON.parse(Buffer.concat(chunks).toString("utf8")));
  for (const part of key.split(".")) {
    node = (node as Record<string, unknown>)[part];
  }
  process.stdout.write(`${JSON.stringify(node)}\n`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
