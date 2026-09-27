# Hosting Afterhours

This guide puts Afterhours on the internet in two parts:

- **The engine** (API, allocator bot and Telegram alerts) runs on **Render** as one web service
  with one persistent disk.
- **The web app** (`web/`) runs on **Vercel**.

You need accounts on both, created by you. Nothing in this guide asks you to share a key with
anyone, and no key ever goes into git.

Platform facts below were checked in Render's and Vercel's documentation on 2026-09-27; each
section names its source page.

## The order, at a glance

1. Optional but recommended first: deploy the testnet vault from your machine (section 6). The
   site works without it, but the vault pages say "No deployment for this profile yet" until
   then. The risk board, position checker and Telegram alerts work either way.
2. Render: create the engine from `render.yaml` (section 1). Copy its URL.
3. Vercel: create the web app with that URL (section 3). Copy the site's URL.
4. Render: set `CORS_ORIGINS` to the site's URL (section 4). The engine restarts.
5. Reown and Plausible: add the site's domain (section 4).
6. Check it (section 7).

## 1. Render: the engine

Source: render.com/docs/blueprint-spec, render.com/docs/web-services,
render.com/docs/python-version, render.com/docs/uv-version, render.com/docs/infrastructure-as-code.

`render.yaml` at the repository root describes the service, so Render fills in most settings
for you.

| Setting | Value | Why |
| --- | --- | --- |
| Root directory | none (the repository root) | Render adds uv only when `uv.lock` is in the service's root directory, and the engine reads `config/`, `artifacts/` and `deployments/` from the root. |
| Runtime | Python | Version 3.12, from `.python-version` at the root. |
| Build command | `uv sync --frozen --no-dev` | Installs exactly what `uv.lock` pins, without test tools. |
| Start command | `./scripts/serve.sh` | Starts the API, then the bot and the alerts in the background. |
| Health check path | `/v1/health` | Answers 200 when the API is up. |
| Plan | `1c-2g` | Measured locally: the API uses about 240 MB of memory and the bot about 150 MB, so the 512 MB plan is too small for all three. Check Render's pricing page for the cost. |
| Disk | `afterhours-data`, mounted at `/var/data`, 1 GB | See section 2. Disks need a paid plan. |

**The port.** Render requires every web service to listen on host `0.0.0.0` and gives it a
`PORT` environment variable (10000 unless you change it). `scripts/serve.sh` sets
`API_HOST=0.0.0.0` and `API_PORT=$PORT` before starting the API, so you do not set either on
Render. Tested locally: with `PORT=8123`, the API listened on `*:8123` and `/v1/health`
answered 200.

**What `serve.sh` starts.**

- The API, in the foreground. If it stops, Render restarts the service.
- In the background: first a refresh of every Stock Token's prices (into the disk cache), then:
  - the allocator bot, only when `ALLOCATOR_PK` is set and `deployments/<profile>.json` exists;
  - the Telegram alerts, only when `TELEGRAM_BOT_TOKEN` is set.

  Each one restarts 30 seconds after it exits. When one is skipped, the log says why.

**Steps.**

1. Open dashboard.render.com and click **New > Blueprint**.
2. Click **Connect** next to the `AfterHours` repository. Pick the `main` branch. Render finds
   `render.yaml` at the root.
3. Render asks for every variable marked `sync: false`. Fill them in from section 5. Leave
   optional ones empty if you do not have them.
4. Click **Deploy Blueprint**. The first build takes a few minutes.
5. When it is live, copy the service URL (it ends in `onrender.com`). Check it: open
   `<that URL>/v1/health` in a browser. You should see `"service":"ok"`.

Later pushes to `main` that change `render.yaml` update the service automatically. Pushes
that change code redeploy it if auto-deploy is on in the service settings.

**One thing to know.** A service with a disk stops the old instance before starting the new
one on every deploy, so the API is down for a short moment each time (Render's disk docs).

## 2. What must survive a restart

Source: render.com/docs/disks and render.com/docs/free.

Everything on a Render service is wiped when it restarts or redeploys, except files under the
disk's mount path. Free services cannot have a disk, and they stop after 15 minutes without
traffic, which would also stop the Telegram bot. So the engine needs a paid plan and a disk.

Every file the engine writes while hosted:

| What | File | Config key | On Render |
| --- | --- | --- | --- |
| Telegram subscriptions and the last update read | `<state_dir>/alerts.json` | `paths.state_dir`, `alerts.store` | `/var/data/state/alerts.json` |
| Borrower scan for "Try a live borrower" | `<state_dir>/live-borrowers.json` | `paths.state_dir` | `/var/data/state/live-borrowers.json` |
| Morpho market registry (mainnet) | `<state_dir>/live-markets.json` | `paths.state_dir` | `/var/data/state/live-markets.json` |
| Bot state: plan, forecasts, reasons, event log (the Ledger page) | `<state_dir>/<profile>/` | `paths.state_dir` | `/var/data/state/rh-testnet/` |
| Prices and earnings cache | `<cache_dir>/prices/`, `earnings/`, `manifest.json` | `data.cache_dir` | `/var/data/cache/` |

Both folders are set by environment variables, which override `config/afterhours.yaml`:

- `AFTERHOURS_PATHS__STATE_DIR=/var/data/state`
- `AFTERHOURS_DATA__CACHE_DIR=/var/data/cache`

`render.yaml` sets both, so you do not type them. `engine/tests/test_hosting.py` checks that
they land under the disk's mount path. **Use mount path `/var/data`.** Render does not allow
`/`, `/opt`, `/opt/render`, `/home`, `/home/render`, `/etc` or `/etc/secrets` themselves.

What the engine only reads, from the repository:

- `deployments/`: written on your machine by `make deploy`, then committed. The hosted
  engine never deploys, so it needs no disk for these. (`AFTERHOURS_PATHS__DEPLOYMENTS_DIR`
  moves it if you ever need to.)
- `artifacts/` and `config/`.

If the disk is lost, nothing breaks for good:

- Prices are fetched again at start.
- The market registry and borrower scan are rebuilt (the first borrower scan takes about
  90 seconds).
- What would be lost: Telegram subscriptions and the bot's history.

## 3. Vercel: the web app

Source: vercel.com/docs/monorepos, vercel.com/docs/monorepos/monorepo-faq,
vercel.com/docs/builds/configure-a-build, vercel.com/docs/package-managers.

| Setting | Value |
| --- | --- |
| Framework preset | Next.js (detected) |
| Root directory | `web` |
| Include source files outside of the Root Directory | On (the default for new projects) |
| Install command | leave the default (`pnpm install`) |
| Build command | leave the default (`next build`, from `web/package.json`) |
| Output directory | leave the default |
| Node.js version | the default is fine (the app needs 20.9 or newer) |

**Files outside `web/` that the build needs**, all at the repository root:

- `pnpm-lock.yaml`: Vercel picks the package manager from the lockfile at the repository root.
  Ours is `lockfileVersion: '9.0'`, which Vercel installs with pnpm 9 or 10.
- `pnpm-workspace.yaml`: declares `web` as a workspace package.
- `package.json`: holds the `pnpm.overrides` entry that pins `qr` to 0.5.5. Without it the
  wallet QR code crashes the page ("invalid border=0").

That is why the setting above must stay on. The web app reads nothing else from outside
`web/` at build or run time; it gets the configuration from the engine's
`/v1/config/public`.

**Steps.**

1. Open vercel.com, click **Add New… > Project**, and **Import** the `AfterHours` repository.
2. Next to **Root Directory**, click **Edit** and choose `web`.
3. Open **Environment Variables** and add the three from section 5 (Vercel column). Set
   `NEXT_PUBLIC_API_BASE_URL` **before** the first build. Variables starting with
   `NEXT_PUBLIC_` are baked in when the site builds, so after changing one you must redeploy.
   Checked locally: with the API URL set, every page renders per request; without it, the
   pages build as static pages with no live data.
4. Click **Deploy**. Copy the site's URL (it ends in `vercel.app` unless you add a domain).

## 4. Connect the two

1. **CORS.** In Render, set `CORS_ORIGINS` to the site's URL, for example
   `https://your-project.vercel.app`. If you add your own domain, list both, separated by a
   comma. Without this, the browser blocks the site's calls to the engine.
2. **Reown (WalletConnect).** If your Reown project has a domain allowlist, add the site's
   domain. Otherwise phone wallets and the QR code will not connect.
3. **Plausible.** Add the site's domain at plausible.io, copy the script URL it gives you, set
   `NEXT_PUBLIC_PLAUSIBLE_SRC` in Vercel, and redeploy. It only loads in production and only
   from `https://plausible.io` (`web.analytics.script_host` in config). Visitors see nothing
   about it.

## 5. Environment variables

Never paste real values into a file in git, an issue or a chat. Put them in the host's
dashboard, or in `.env` on your own machine.

### Render (engine)

| Name | Secret? | Where the value comes from | Example format |
| --- | --- | --- | --- |
| `AFTERHOURS_PATHS__STATE_DIR` | no | set by `render.yaml` | `/var/data/state` |
| `AFTERHOURS_DATA__CACHE_DIR` | no | set by `render.yaml` | `/var/data/cache` |
| `AFTERHOURS_ACTIVE_PROFILE` | no | your choice: the testnet whose vault the site shows | `rh-testnet` or `arb-sepolia` |
| `CORS_ORIGINS` | no | your Vercel site's URL (section 4) | `https://your-project.vercel.app` |
| `ADMIN_TOKEN` | yes | Render generates it (`generateValue`) | 64 hex characters |
| `ALLOCATOR_PK` | yes | the allocator key you made with `cast wallet new` (section 6) | `0x` then 64 hex characters |
| `TELEGRAM_BOT_TOKEN` | yes | @BotFather in Telegram, `/newbot` | `<digits>:<letters and digits>` |
| `RH_MAINNET_RPC_URL` | yes (the URL holds your provider key) | optional; an RPC provider dashboard. Empty uses the public RPC. | `https://<provider host>/<your key>` |
| `RH_TESTNET_RPC_URL` | yes | optional, same as above | `https://<provider host>/<your key>` |
| `ARB_SEPOLIA_RPC_URL` | yes | optional, same as above | `https://<provider host>/<your key>` |
| `ALERT_WEBHOOK_URL` | yes | optional; a Discord channel's webhook | `https://discord.com/api/webhooks/<id>/<token>` |
| `FINNHUB_API_KEY` | yes | optional backup data provider (free tier) | letters and digits |
| `ALPHAVANTAGE_API_KEY` | yes | optional backup data provider (free tier) | letters and digits |
| `PORT` | no | Render sets it; do not add it | `10000` |

The hosted bot signs only as the allocator. It needs `ALLOCATOR_PK` and no other key.
`DEPLOYER_PK`, `CURATOR_PK` and `GUARDIAN_PK` stay in `.env` on your machine, and
`engine/tests/test_hosting.py` fails if `render.yaml` ever asks for them.

### Vercel (web)

| Name | Secret? | Where the value comes from | Example format |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | no | your Render service URL (section 1) | `https://afterhours-engine.onrender.com` |
| `NEXT_PUBLIC_WC_PROJECT_ID` | no (browsers see it), but keep it out of git | the Project ID in your Reown dashboard | the ID string Reown shows |
| `NEXT_PUBLIC_PLAUSIBLE_SRC` | no | your site's settings at plausible.io | `https://plausible.io/js/pa-XXXXXXXX.js` |

### Only on your machine (`.env`)

| Name | Secret? | Used for |
| --- | --- | --- |
| `DEPLOYER_PK`, `CURATOR_PK`, `ALLOCATOR_PK`, `GUARDIAN_PK` | yes | `make deploy`, `make seed`, `make fund-allocator` |
| `RH_TESTNET_RPC_URL`, `ARB_SEPOLIA_RPC_URL` | yes | optional, for deploys |
| `ETHERSCAN_API_KEY` | yes | optional, contract verification |

## 6. Testnets: faucets, RPCs and funding

From `config/afterhours.yaml` (`chains`):

| | Robinhood Chain Testnet | Arbitrum Sepolia |
| --- | --- | --- |
| Profile | `rh-testnet` | `arb-sepolia` |
| Chain id | 46630 | 421614 |
| Public RPC | https://rpc.testnet.chain.robinhood.com | https://sepolia-rollup.arbitrum.io/rpc |
| Explorer | https://explorer.testnet.chain.robinhood.com | https://sepolia.arbiscan.io |
| Faucet | https://faucet.testnet.chain.robinhood.com | https://arbitrum.faucet.dev |

**Which RPC variables you still need.** None is required: when a profile's variable is empty,
the engine uses the public RPC above (`rpc_url` in `engine/afterhours/config.py`). Public RPCs
are rate limited, so:

- `RH_MAINNET_RPC_URL`: recommended on Render. The risk board, position checker and alerts
  all read Robinhood Chain mainnet. It is also still needed as an archive endpoint for the
  fork runs (PROGRESS.md BLOCKED 1).
- `RH_TESTNET_RPC_URL`, `ARB_SEPOLIA_RPC_URL`: optional, for smoother deploys and bot runs.
- `ARB_ONE_RPC_URL`: not needed. Nothing hosted uses Arbitrum One.

**Fund one address, not four.** The deployer pays for the deploy and then sends the allocator
its gas.

1. Make four throwaway keys with `cast wallet new` and put them in `.env` as `DEPLOYER_PK`,
   `CURATOR_PK`, `ALLOCATOR_PK`, `GUARDIAN_PK`. Testnet only.
2. Send faucet ETH to the **deployer's** address on each testnet you use. How much, per chain:
   - The M11 rehearsal measured 0.0065 ETH for deploy, seed and a first bot cycle.
   - `funding.allocator_eth` sends the allocator 0.02 ETH.
   - `funding.keep_deployer_eth` keeps 0.005 ETH back on the deployer.
   - Total: about 0.0315 ETH, so ask the faucet for at least 0.035.
3. Deploy, seed and fund the allocator:

```bash
PROFILE=rh-testnet make deploy seed
```

```bash
make fund-allocator PROFILE=rh-testnet
```

`make fund-allocator` shows both balances and asks before sending. What it checks:

- It sends only on a testnet profile: the chain must have a faucet, need no mainnet go and use
  no local node. It refuses `rh-mainnet`, `arb-one`, `local` and `fork`.
- It checks the RPC answers with the expected chain id.
- It refuses if the deployer would be left below `funding.keep_deployer_eth`.

It signs with the engine's own signer, so keys stay in the environment and never appear on a
command line. Tested on a local fork of Robinhood Chain Testnet with throwaway keys and fork
ETH: it refused with too little ETH, then sent 0.02 ETH and the allocator's balance became
0.02.

The curator and guardian spent nothing in the rehearsal. They only need gas for emergency
actions, so send them a little later if you ever need them.

4. Commit and push the new `deployments/rh-testnet.json` (it holds public addresses only). Set
   `AFTERHOURS_ACTIVE_PROFILE=rh-testnet` and `ALLOCATOR_PK` on Render. The bot starts on the
   next deploy.

Repeat with `PROFILE=arb-sepolia` for Arbitrum Sepolia.

## 7. Check it

- `<Render URL>/v1/health` shows `"service":"ok"` and your profile.
- The site's `/live` page lists every Stock Token with "Live: Robinhood Chain mainnet,
  read-only".
- `/positions`: "Try a live borrower" shows a position card. Right after the first start it
  can take about 90 seconds to appear.
- Telegram: send your bot `/watch NVDA`; it answers "Following NVDA".
- Render's **Logs** tab shows `serve:` lines saying which background parts started or why not.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Render deploy fails the health check | The service is not listening on the port Render expects. Leave the start command as `./scripts/serve.sh` and do not set `PORT`. |
| The site loads but every panel says it can't reach the engine | `CORS_ORIGINS` on Render does not match the site's URL exactly (`https://`, no trailing slash), or `NEXT_PUBLIC_API_BASE_URL` was set after the build. Redeploy on Vercel. |
| Vault pages say "No deployment for this profile yet" | Section 6 is not done for the profile in `AFTERHOURS_ACTIVE_PROFILE`, or `deployments/<profile>.json` is not pushed. |
| Wallet QR code does not connect | Add the site's domain to the Reown project's allowlist. |
| Telegram bot does not answer | `TELEGRAM_BOT_TOKEN` is empty or wrong. The Logs tab says "alerts not started" when it is empty. |
| Subscriptions vanish after a deploy | The disk is not attached, or the state path does not start with `/var/data`. |
