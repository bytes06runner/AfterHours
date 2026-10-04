/**
 * The demo's scenes, each a real session on the site. Run one: `node scenes.mjs landing`, or all:
 * `node scenes.mjs all`. LIVE is the hosted site (Robinhood Chain mainnet reads, testnet vault);
 * LOCAL is `make up` served by `next start -p 3100` (the only place a visitor wallet can get
 * test USDG). Output: out/<scene>/frames + events.json, assembled by assemble.mjs.
 */
import { execFileSync, spawn } from "node:child_process";
import { randomBytes } from "node:crypto";

import { Session } from "./recorder.mjs";

const LIVE = process.env.DEMO_LIVE_URL || "https://after-hours-web-eta.vercel.app";
const LOCAL = process.env.DEMO_LOCAL_URL || "http://127.0.0.1:3100";
const RPC = process.env.DEMO_RPC_URL || "http://127.0.0.1:8545";
const EXPLORER_TX = process.env.DEMO_EXPLORER_TX; // the testnet allocate transaction page
const REPO = new URL("../../../", import.meta.url).pathname;

const nav = (s, name) => s.page.getByRole("banner").getByRole("link", { name, exact: true }).first();

/** The same test wallet the E2E suite uses: forwards to Anvil and impersonates an address. */
async function localWallet(s) {
  const from = `0x${randomBytes(20).toString("hex")}`;
  await s.ctx.addInitScript(
    ({ rpc, from }) => {
      let id = 0;
      const call = async (method, params = []) => {
        const r = await fetch(rpc, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: ++id, method, params }) });
        const b = await r.json();
        if (b.error) throw Object.assign(new Error(b.error.message), { code: b.error.code });
        return b.result;
      };
      const ls = {};
      const provider = {
        isMetaMask: true,
        request: async ({ method, params }) => {
          if (method === "eth_requestAccounts" || method === "eth_accounts") return [from];
          if (method === "eth_chainId") return "0x7a69";
          if (method === "wallet_switchEthereumChain" || method === "wallet_addEthereumChain") return null;
          if (method === "eth_sendTransaction") { await call("anvil_impersonateAccount", [from]); return call(method, params ?? []); }
          return call(method, params ?? []);
        },
        on: (e, fn) => (ls[e] ??= []).push(fn),
        removeListener: (e, fn) => { ls[e] = (ls[e] ?? []).filter((f) => f !== fn); },
      };
      Object.defineProperty(window, "ethereum", { value: provider, configurable: true });
    },
    { rpc: RPC, from },
  );
}

const SCENES = {
  async landing() {
    const s = await Session.open({ welcomed: false });
    await s.start("01-landing");
    await s.goto(`${LIVE}/`);
    await s.wait(5200); // the welcome doors open
    await s.moveTo(620, 420);
    s.focus(720, 400, 1.35, 2.2); // the exchange and the ticker
    await s.wait(2400);
    await s.scroll(760, 1600);
    await s.wait(1800);
    await s.scroll(900, 1800);
    await s.wait(1800);
    await s.scroll(900, 1800);
    await s.wait(1600);
    await s.scroll(-2560, 1600);
    await s.wait(900);
    await s.click(s.page.getByRole("button", { name: "Preview the close" }), { zoom: 1.5, hold: 1.0 });
    await s.moveTo(1100, 300);
    await s.wait(7500); // the bell rings, night falls
    await s.stop();
    await s.close();
  },

  async riskboard() {
    const s = await Session.open();
    await s.goto(`${LIVE}/live`);
    await s.page.getByTestId("board-row").first().waitFor({ timeout: 120_000 });
    await s.goto(`${LIVE}/`);
    await s.wait(1500);
    await s.start("02-riskboard");
    await s.click(nav(s, "Risk board"), { zoom: 1.6 });
    await s.page.getByTestId("board-row").first().waitFor({ timeout: 120_000 });
    await s.wait(900);
    s.focus(360, 150, 1.5, 2.2); // "Live: Robinhood Chain mainnet, read-only"
    await s.hover(s.page.getByTestId("board-row").first(), 1600);
    await s.click(s.page.getByRole("button", { name: "Frozen now" }), { hold: 1.4 });
    await s.wait(900);
    await s.click(s.page.getByRole("button", { name: "Beyond a cushion tonight" }), { hold: 1.4 });
    await s.wait(900);
    await s.click(s.page.getByRole("button", { name: "All stocks" }), { hold: 1.0 });
    await s.scroll(520, 1500);
    await s.hover(s.page.getByTestId("board-row").nth(4), 1400);
    await s.scroll(-520, 1000);
    await s.stop();
    await s.close();
  },

  async checker() {
    const s = await Session.open();
    await s.goto(`${LIVE}/positions`);
    await s.page.getByText("Try a live borrower:").waitFor({ timeout: 120_000 });
    await s.start("03-checker");
    await s.wait(700);
    s.focus(560, 330, 1.45, 2.0); // the explanation and the address field
    await s.wait(1800);
    const borrowers = s.page.getByText("Try a live borrower:").getByRole("button");
    await s.click(borrowers.last(), { zoom: 1.8 });
    await s.page.getByTestId("position").first().waitFor({ timeout: 120_000 });
    await s.wait(900);
    await s.scroll(360, 1400);
    await s.wait(500);
    const tonight = s.page.getByTestId("tonight").first();
    const { x, y } = await s.hover(tonight, 300);
    s.focus(x, y, 1.7, 2.6);
    await s.wait(2800);
    await s.scroll(420, 1400);
    await s.wait(1500);
    await s.stop();
    await s.close();
  },

  async deposit() {
    const s = await Session.open();
    await localWallet(s);
    await s.goto(`${LOCAL}/vault`);
    await s.page.getByText("The vault").first().waitFor();
    await s.wait(1500);
    await s.start("04-deposit");
    s.focus(560, 250, 1.3, 1.8);
    await s.wait(1600);
    const faucet = s.page.getByRole("button", { name: "Get test USDG (sim)" });
    if (!(await faucet.isVisible().catch(() => false))) {
      await s.click(s.page.getByRole("button", { name: "Connect" }).first(), { zoom: 1.6 });
      await s.wait(700);
      await s.click(s.page.getByRole("button", { name: /MetaMask|Browser Wallet|Injected/ }).first(), { zoom: 1.5 });
      await s.wait(1500);
    }
    await s.click(faucet, { zoom: 1.7 });
    await s.page.getByText(/Received .* USDG \(sim\)/).waitFor({ timeout: 60_000 });
    await s.wait(1200);
    await s.click(s.page.getByLabel("Amount in USDG"), { zoom: 1.8, hold: 2.2, after: 200 });
    await s.type("1000", 140);
    await s.wait(500);
    await s.click(s.page.getByRole("button", { name: /deposit USDG/i }).last(), { zoom: 1.7, hold: 2.4 });
    await s.page.getByText(/Deposited 1,000\.00 USDG\./).waitFor({ timeout: 90_000 });
    const done = await s.centerOf(s.page.getByText(/Deposited 1,000\.00 USDG\./));
    s.focus(done.x, done.y, 1.7, 2.2);
    await s.wait(2600);
    await s.scroll(640, 1600);
    await s.wait(2200);
    await s.stop();
    await s.close();
  },

  async closingbell() {
    const s = await Session.open();
    await s.goto(`${LOCAL}/vault`);
    await s.page.getByText("Idle reservoir").first().waitFor({ timeout: 60_000 });
    await s.scroll(560, 10);
    await s.wait(1500);
    await s.start("05-closingbell", { top: false });
    const meta = s.page.getByText("META", { exact: true }).first();
    await s.hover(meta, 900).catch(() => {});
    s.log("mark", { label: "scenario-start" });
    // The scripted closing bell on the local chain: pre-close checks of 2025-04-22, 23 and 24.
    const run = spawn("bash", ["-c", ". scripts/env.sh; AFTERHOURS_ACTIVE_PROFILE=local uv run --quiet afterhours sim scenario closing_bell"], { cwd: REPO, stdio: "ignore" });
    const t0 = Date.now();
    while (run.exitCode === null && Date.now() - t0 < 240_000) await s.wait(1000);
    s.log("mark", { label: "scenario-end" });
    await s.wait(3000);
    const { x, y } = await s.centerOf(meta).catch(() => ({ x: 400, y: 400 }));
    s.focus(x + 300, y, 1.5, 2.6);
    await s.wait(3000);
    await s.stop();
    await s.close();
  },

  async ledger() {
    const s = await Session.open();
    await s.goto(`${LOCAL}/vault`);
    await s.wait(1200);
    await s.start("06-ledger");
    await s.click(nav(s, "Ledger"), { zoom: 1.6 });
    await s.page.getByRole("button", { name: "Verify on chain" }).first().waitFor({ timeout: 60_000 });
    await s.wait(900);
    // The card the closing bell just wrote: META's pullback.
    const card = s.page.locator("article").filter({ hasText: /META: [\d,]+ USDG from .* to idle/ }).first();
    const c = await s.centerOf(card);
    await s.moveTo(c.x, c.box.y + 90);
    s.focus(c.x, c.box.y + 170, 1.4, 3.4);
    await s.wait(3600);
    await s.click(card.getByRole("button", { name: "Verify on chain" }), { zoom: 1.8, hold: 1.2 });
    await s.page.getByText("Matched onchain").first().waitFor({ timeout: 60_000 });
    const m = await s.centerOf(s.page.getByText("Matched onchain").first());
    s.focus(m.x, m.y, 1.9, 2.4);
    await s.wait(2800);
    await s.stop();
    await s.close();
  },

  async testnet() {
    const s = await Session.open();
    await s.goto(`${LIVE}/ledger`);
    await s.page.getByRole("button", { name: "Verify on chain" }).first().waitFor({ timeout: 120_000 });
    await s.wait(1000);
    await s.start("07-testnet");
    s.focus(560, 260, 1.3, 1.8);
    await s.wait(1800);
    await s.click(s.page.getByRole("button", { name: "Verify on chain" }).first(), { zoom: 1.8, hold: 1.2 });
    await s.page.getByText("Matched onchain").first().waitFor({ timeout: 90_000 });
    const m = await s.centerOf(s.page.getByText("Matched onchain").first());
    s.focus(m.x, m.y, 1.9, 2.4);
    await s.wait(2800);
    if (EXPLORER_TX) {
      await s.goto(EXPLORER_TX);
      await s.wait(4500);
      s.focus(720, 330, 1.35, 3.2);
      await s.moveTo(700, 380);
      await s.wait(3600);
    }
    await s.stop();
    await s.close();
  },

  async replay() {
    const s = await Session.open();
    await s.goto(`${LIVE}/replay`);
    await s.page.getByRole("button", { name: "Replay this night" }).first().waitFor({ timeout: 120_000 });
    await s.wait(1000);
    await s.start("08-replay");
    const meta = s.page.getByRole("group", { name: "Scenarios" }).getByRole("button", { name: /META.*2022-10-26|2022-10-26.*META/ }).first();
    if (await meta.isVisible().catch(() => false)) await s.click(meta, { zoom: 1.6 });
    await s.wait(900);
    await s.click(s.page.getByRole("button", { name: "Replay this night" }).first(), { zoom: 1.6 });
    await s.moveTo(1150, 640);
    await s.wait(9000);
    await s.stop();
    await s.close();
  },

  async report() {
    const s = await Session.open();
    await s.goto(`${LIVE}/`);
    await s.page.getByText(/NVDA \d/).first().waitFor({ timeout: 90_000 }); // the ticker has prices
    await s.wait(1200);
    await s.start("09-report");
    await s.click(nav(s, "Report card"), { zoom: 1.6 });
    await s.page.getByRole("heading", { name: "Report card" }).waitFor({ timeout: 60_000 });
    await s.wait(900);
    s.focus(420, 260, 1.5, 2.4);
    await s.wait(2600);
    await s.scroll(700, 1700);
    await s.wait(2600);
    await s.scroll(620, 1500);
    await s.wait(2600);
    await s.stop();
    await s.close();
  },
};

const which = process.argv[2] || "all";
const order = which === "all" ? Object.keys(SCENES) : which.split(",");
for (const name of order) {
  if (!SCENES[name]) throw new Error(`no scene ${name}; have ${Object.keys(SCENES).join(", ")}`);
  await SCENES[name]();
}
void execFileSync;
