# Hosting Afterhours for free

This guide puts Afterhours on the internet at no cost, step by step. You create every account
yourself; nothing here shares a key with anyone, and no key ever goes into git.

Free-tier facts below were checked in each provider's own documentation on 2026-09-27. Free
tiers change, so each section names its source page; check it again if something differs.

## What runs where

| Part | Where | Why there |
| --- | --- | --- |
| Web app (`web/`) | Vercel Hobby | Free Next.js hosting. |
| API: risk board, position checker, Telegram webhook | Render free web service (`render.free.yaml`) | Free Python web service. |
| Pre-close bot cycle (testnet vault) and pre-close Telegram alerts | GitHub Actions (`.github/workflows/pre-close.yml`) | Free for public repositories; runs hourly on weekdays. |
| Bot history and Telegram subscriptions | Upstash Redis | Free, reached over HTTPS, so the API and the Actions job share it. |
| Keeping the API awake | UptimeRobot | Free; calls `/v1/health` every 5 minutes. |
| Page counts | GoatCounter | Free, no cookies, keeps aggregate counts only. |

Everything else (price cache, borrower scan, market registry) is rebuilt when the API starts,
in the background, in about 20 seconds (measured locally from an empty cache).

**Keys.** The hosted pieces get only what they use:
- Render gets the Telegram bot token, the webhook secret and the Upstash URL and token. It
  signs nothing, so it has no private key.
- GitHub Actions gets `ALLOCATOR_PK` for the bot step only, the Telegram bot token for the alerts
  step only, and the Upstash URL and token.
- `DEPLOYER_PK`, `CURATOR_PK` and `GUARDIAN_PK` never leave your `.env`.
  `engine/tests/test_shared_state.py` fails if the workflow or `render.free.yaml` ever asks for
  them.

## What we checked, and what changed from the first plan

| Assumption | Verdict (source) |
| --- | --- |
| Hugging Face Spaces free CPU with Docker | **Wrong.** Docker and Gradio Spaces now need a paid plan (PRO) to create; free accounts get Static Spaces and ZeroGPU Gradio only (huggingface.co/docs/hub/spaces-overview, huggingface.co/pricing). The API uses Render free instead, the named fallback. |
| Render free web service | Right. 512 MB RAM and 0.1 CPU; 750 free instance hours per workspace per month, then free services are suspended until the next month; sleeps after 15 minutes without inbound traffic and wakes on the next HTTP request in about a minute; no disk, files lost on restart (render.com/docs/free; RAM from render.com/blog/free-tier). |
| The API fits in free RAM | Right, measured. From an empty cache, the API fetched all 35 Stock Tokens' prices, built the board and scanned borrowers with a peak of 366 MB (macOS, `time -l`), plus about 17 MB for the `uv` wrapper. Linux differs a little. |
| Telegram webhook with a secret | Right. `setWebhook` takes `secret_token` (1 to 256 characters, `A-Z a-z 0-9 _ -`), sent back in the `X-Telegram-Bot-Api-Secret-Token` header; webhooks use ports 443, 80, 88 or 8443; `getUpdates` stops working while a webhook is set (core.telegram.org/bots/api#setwebhook). |
| GitHub Actions hourly on weekdays | Right, with limits. Free for public repositories (this one is public); private repositories on GitHub Free get 2,000 minutes a month. Scheduled runs can be delayed or dropped under load, "especially the start of every hour", so the job runs at minute 23; they run only on the default branch and are disabled after 60 days without repository activity (docs.github.com, events that trigger workflows; billing for GitHub Actions). |
| A free database | Upstash Redis free: 256 MB data, 500,000 commands a month, 10 GB bandwidth, REST API included (upstash.com/docs/redis/overall/pricing). Free databases are archived after at least 30 days of inactivity, with warning emails and a backup you can restore (upstash.com/docs/redis/help/faq). |
| Vercel Hobby | Right, with one condition: free, but "non-commercial, personal use only" (vercel.com/docs/plans/hobby). A hackathon demo fits; a business would need Pro. |
| Free analytics | GoatCounter: free "for reasonable public usage", including a personal site or a small-to-medium business; stores aggregate data and no IP addresses (goatcounter.com, goatcounter.com/help/gdpr). |
| Uptime pinger | UptimeRobot free: 50 monitors, checks every 5 minutes (uptimerobot.com/pricing). Render's free docs do not forbid keeping a service awake. |

**Why Upstash Redis and not Neon Postgres.** Both have free tiers that fit. Upstash wins here
because it is reached over plain HTTPS with a token, so:
- the engine needs no database driver (it already uses `httpx`), which matters on a 512 MB
  instance;
- short GitHub Actions jobs do not open and close database connections;
- the data is keys, lists and small JSON documents, which is what Redis stores.

Neon's free compute also sleeps after 5 minutes idle and cannot be kept on (neon.com/docs,
plans), which would add a cold start to every Telegram command.

**Upstash command budget** (estimate from config, not measured):
- The pinger reads the bot's plan once per health check: 12 an hour, about 9,000 a month.
- A browser tab left open on the site checks for new bot events once every 30 seconds
  (`state.event_poll_seconds`): at most about 89,000 a month, even if a tab stayed open all
  month.
- API reads are cached for 30 seconds (`state.read_cache_seconds`).
- Telegram commands and the pre-close job use a few hundred a month.

That is well under 500,000.

**Render hours.** One service awake all month uses up to 744 hours of the 750. Do not run a
second free Render service in the same workspace, or both will be suspended near the end of
the month.

## Before you start

You need a GitHub account with this repository, and accounts on:
- Render
- Vercel
- Upstash
- UptimeRobot
- GoatCounter
- Telegram (for the bot)
- Reown (for WalletConnect; you already have a project ID)

All are free. Sign in with GitHub where offered. None of these steps needs a payment card.

On your own machine you need the repository and `make setup` done, and a `.env` file (copy
`.env.example`). You will add a few values to `.env` as you go.

## Step 1. Upstash: the shared database

1. Open console.upstash.com and create a **Redis** database. Pick the region closest to your
   Render region.
2. Open the database and find the **REST API** section. Copy two values:
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`

   The token is a secret.

## Step 2. Telegram: the bot and its webhook secret

1. In Telegram, message **@BotFather**, send `/newbot`, and pick a name and a username ending in
   `bot`. BotFather replies with the token (`TELEGRAM_BOT_TOKEN`, a secret).
2. Make a webhook secret on your machine:

```bash
openssl rand -hex 32
```

3. Put both in your local `.env` as `TELEGRAM_BOT_TOKEN=...` and `TELEGRAM_WEBHOOK_SECRET=...`.
   You need them again in steps 3 and 7.

## Step 3. Render: the API

Source: render.com/docs/free, render.com/docs/blueprint-spec, render.com/docs/web-services.

1. Open dashboard.render.com, click **New > Blueprint**, and click **Connect** next to the
   `AfterHours` repository. Pick the `main` branch.
2. In **Blueprint Path**, type `render.free.yaml`. (The default `render.yaml` is the paid setup
   with a disk; see the end of this guide.)
3. Render asks for each value marked `sync: false`. Fill them in from the table in section
   "Environment variables". Leave the optional RPC URLs empty if you have none.
4. Click **Deploy Blueprint**. The first build takes a few minutes.
5. Copy the service URL (it ends in `onrender.com`) and open `<that URL>/v1/health`. You should
   see `"service":"ok"`.

What `render.free.yaml` sets:

| Setting | Value |
| --- | --- |
| Plan | `free` |
| Root directory | none (the repository root: Render adds uv when `uv.lock` is there, and the engine reads `config/`, `artifacts/`, `deployments/`) |
| Build command | `uv sync --frozen --no-dev` |
| Start command | `./scripts/serve.sh` |
| Health check path | `/v1/health` |
| Disk | none (free services cannot have one) |

**The port.** Render requires every web service to listen on host `0.0.0.0` and passes a `PORT`
variable (10000 by default). `scripts/serve.sh` sets `API_HOST=0.0.0.0` and `API_PORT=$PORT`,
so do not set either yourself. With no `ALLOCATOR_PK` and a webhook secret set, it starts the
API only.

## Step 4. Vercel: the web app

Source: vercel.com/docs/monorepos, vercel.com/docs/builds/configure-a-build,
vercel.com/docs/package-managers, vercel.com/docs/plans/hobby.

1. Open vercel.com, click **Add New… > Project**, and **Import** the `AfterHours` repository.
2. Next to **Root Directory**, click **Edit** and choose `web`. Leave **Include source files
   outside of the Root Directory** on (the default). The build needs three files at the
   repository root:
   - `pnpm-lock.yaml`: Vercel picks pnpm from it.
   - `pnpm-workspace.yaml`
   - `package.json`: its `pnpm.overrides` keeps the wallet QR code from crashing.
3. Leave the framework (Next.js), install command and build command at their defaults.
4. Under **Environment Variables**, add the three Vercel values from the table below. Set
   `NEXT_PUBLIC_API_BASE_URL` **before** the first build: `NEXT_PUBLIC_` values are baked in
   at build time, so after changing one you must redeploy. Checked locally: with it set, every
   page renders per request; without it, pages build as static pages with no live data.
5. Click **Deploy** and copy the site's URL (it ends in `vercel.app`).

## Step 5. Connect the web app and the API

1. **CORS.** In Render, open the service's **Environment** and set `CORS_ORIGINS` to the site's
   URL, for example `https://your-project.vercel.app` (no trailing slash). Render restarts the
   service.
2. **Reown.** If your Reown project has a domain allowlist, add the site's domain.

## Step 6. UptimeRobot: keep the API awake

A free Render service sleeps after 15 minutes without traffic, and the first request after that
waits about a minute.

1. In UptimeRobot, add a new **HTTP(s)** monitor.
2. Set the URL to `<Render URL>/v1/health` and the interval to 5 minutes.

The health check reads only cached data, so this costs almost nothing in Upstash commands.

If you skip this step, the site still works; the first visitor after a quiet spell waits about
a minute. A Telegram message that arrives while the API sleeps wakes it, and Telegram retries
the message if the first delivery fails.

## Step 7. Telegram: point the bot at the API

On your machine, with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` in `.env`:

```bash
make telegram-webhook URL=https://your-service.onrender.com
```

It calls Telegram's `setWebhook` with the secret and prints the URL Telegram now uses. Then
message your bot `/watch NVDA`; it should answer "Following NVDA".

- To go back to long polling on your machine (`make alerts`), run
  `uv run afterhours alerts delete-webhook` first.
- The two modes cannot run at once: Telegram disables `getUpdates` while a webhook is set.

## Step 8. GitHub Actions: the pre-close jobs

The workflow `.github/workflows/pre-close.yml` runs at minute 23 of every hour, Monday to
Friday (UTC). Each run:

1. installs the engine and asks it whether now is inside a pre-close window (the two hours
   before an exchange close, holidays and early closes included). If not, it stops;
2. refreshes every Stock Token's prices;
3. runs the bot's pre-close cycle for the testnet vault, once per close, if the vault is
   deployed;
4. sends the Telegram pre-close alerts, once per subscription per close.

Set it up:

1. In GitHub, open the repository's **Settings > Secrets and variables > Actions**.
2. Under **Secrets**, add:
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`
   - `TELEGRAM_BOT_TOKEN`
   - optional: `RH_MAINNET_RPC_URL`, `RH_TESTNET_RPC_URL`, `ARB_SEPOLIA_RPC_URL`
   - `ALLOCATOR_PK`, but only after step 9.
3. Under **Variables**, add `AFTERHOURS_ACTIVE_PROFILE` = `rh-testnet` (or `arb-sepolia`).
4. Check it: open the **Actions** tab, pick **Pre-close jobs**, and click **Run workflow**.
   Outside a pre-close window it installs, prints `false` for the window check, and stops. That
   is a pass.

Keep the repository public, or Actions minutes count against GitHub Free's 2,000 a month. Push
at least once every 60 days, or GitHub disables the schedule.

## Step 9 (optional, for the vault). Deploy the testnet vault

The site works without this; the vault pages say "No deployment for this profile yet" until
you do it. The risk board, position checker and alerts work either way.

From `config/afterhours.yaml` (`chains`):

| | Robinhood Chain Testnet | Arbitrum Sepolia |
| --- | --- | --- |
| Profile | `rh-testnet` | `arb-sepolia` |
| Chain id | 46630 | 421614 |
| Public RPC | https://rpc.testnet.chain.robinhood.com | https://sepolia-rollup.arbitrum.io/rpc |
| Explorer | https://explorer.testnet.chain.robinhood.com | https://sepolia.arbiscan.io |
| Faucet | https://faucet.testnet.chain.robinhood.com | https://arbitrum.faucet.dev |

**RPC variables.** None is required: an empty `*_RPC_URL` means the public RPC above. Public
RPCs are rate limited:
- `RH_MAINNET_RPC_URL` is recommended, because the risk board, checker and alerts read mainnet.
  The public mainnet RPC answered "429 Too Many Requests" during our local tests. It is also
  the archive endpoint the fork runs still need (PROGRESS.md BLOCKED 1).
- `RH_TESTNET_RPC_URL` and `ARB_SEPOLIA_RPC_URL` are optional.
- `ARB_ONE_RPC_URL` is not used by anything hosted.

Then:

1. Make four throwaway keys with `cast wallet new` and put them in `.env` as `DEPLOYER_PK`,
   `CURATOR_PK`, `ALLOCATOR_PK`, `GUARDIAN_PK`. Testnet only.
2. Send faucet ETH to the **deployer** only. You need about 0.0315 ETH on each testnet you use:
   - 0.0065 for deploy, seed and a first cycle (measured in the M11 rehearsal);
   - 0.02 the deployer passes to the allocator (`funding.allocator_eth`);
   - 0.005 kept back (`funding.keep_deployer_eth`).

   Ask the faucet for at least 0.035.
3. Deploy, seed and fund the allocator:

```bash
PROFILE=rh-testnet make deploy seed
```

```bash
make fund-allocator PROFILE=rh-testnet
```

   `make fund-allocator`:
   - shows both balances and asks before sending;
   - sends only on a testnet profile, and checks the RPC's chain id;
   - keeps `funding.keep_deployer_eth` on the deployer;
   - signs with the engine's signer, so no key appears on a command line.

4. Commit and push `deployments/rh-testnet.json` (public addresses only).
5. Add `ALLOCATOR_PK` as a GitHub Actions secret (step 8). The next pre-close run cycles the
   bot, and the Ledger page on the site shows its history from Upstash.

The M11 rehearsal measured nothing spent by the curator and guardian; they only need gas for
emergency actions.

## Step 10. GoatCounter: page counts

1. Sign up at goatcounter.com and pick a code for the site.
2. Your count endpoint is `https://<your code>.goatcounter.com/count`.
3. In Vercel, set `NEXT_PUBLIC_GOATCOUNTER_URL` to it and redeploy.

How it loads:
- The script comes only from `web.analytics.script_src` in config (`gc.zgo.at`, from
  GoatCounter's docs).
- The endpoint must be on `web.analytics.endpoint_domain`.
- It loads in production builds only and shows nothing to visitors.
- Page changes inside the app are counted as GoatCounter's single-page-app guide describes.

## Environment variables

Never paste real values into a file in git, an issue or a chat.

### Render (API)

| Name | Secret? | Where the value comes from | Example format |
| --- | --- | --- | --- |
| `AFTERHOURS_ACTIVE_PROFILE` | no | your choice: which vault the site shows | `rh-testnet` |
| `CORS_ORIGINS` | no | your Vercel URL (step 5) | `https://your-project.vercel.app` |
| `ADMIN_TOKEN` | yes | Render generates it | 64 hex characters |
| `UPSTASH_REDIS_REST_URL` | yes | Upstash console, REST API | `https://<name>.upstash.io` |
| `UPSTASH_REDIS_REST_TOKEN` | yes | Upstash console, REST API | a long token string |
| `TELEGRAM_BOT_TOKEN` | yes | @BotFather | `<digits>:<letters and digits>` |
| `TELEGRAM_WEBHOOK_SECRET` | yes | `openssl rand -hex 32` (step 2) | 64 hex characters |
| `RH_MAINNET_RPC_URL` | yes (holds a provider key) | optional; an RPC provider | `https://<provider host>/<your key>` |
| `RH_TESTNET_RPC_URL` | yes | optional | same |
| `ARB_SEPOLIA_RPC_URL` | yes | optional | same |
| `PORT` | no | Render sets it; do not add it | `10000` |

### GitHub Actions (repository secrets and one variable)

| Name | Kind | Used by | Example format |
| --- | --- | --- | --- |
| `AFTERHOURS_ACTIVE_PROFILE` | variable | the whole job | `rh-testnet` |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | secret | the whole job | as above |
| `ALLOCATOR_PK` | secret | the bot step only | `0x` then 64 hex characters |
| `TELEGRAM_BOT_TOKEN` | secret | the alerts step only | as above |
| `RH_MAINNET_RPC_URL`, `RH_TESTNET_RPC_URL`, `ARB_SEPOLIA_RPC_URL` | secret, optional | the whole job | as above |

### Vercel (web)

| Name | Secret? | Where the value comes from | Example format |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | no | your Render URL (step 3) | `https://your-service.onrender.com` |
| `NEXT_PUBLIC_WC_PROJECT_ID` | no (browsers see it), keep it out of git | Reown dashboard | the ID string Reown shows |
| `NEXT_PUBLIC_GOATCOUNTER_URL` | no | GoatCounter (step 10) | `https://<code>.goatcounter.com/count` |

### Only on your machine (`.env`)

| Name | Used for |
| --- | --- |
| `DEPLOYER_PK`, `CURATOR_PK`, `ALLOCATOR_PK`, `GUARDIAN_PK` | `make deploy`, `make seed`, `make fund-allocator` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | `make telegram-webhook` |
| `ETHERSCAN_API_KEY` | optional, contract verification |

## What is stored where

| Data | Free setup | Rebuilt on restart? |
| --- | --- | --- |
| Telegram subscriptions | Upstash hash `afterhours:alerts:chats` | kept |
| Which subscriptions were checked for a close | Upstash key `afterhours:alerts:checked` (expires after `state.checked_ttl_days`) | kept |
| Bot history: plan, forecasts, reasons, event log | Upstash keys under `afterhours:<profile>:` | kept |
| Which close the bot already ran for | Upstash key `afterhours:<profile>:doc:pre_close_run` | kept |
| Prices and earnings | API's local cache; Actions cache in the workflow | yes, at start (about 20 s) |
| Borrower scan, market registry | API's local state folder | yes, at start |

The shared store is used whenever `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` are
set (`state` in config); without them everything stays in files under `data/state`, as on your
machine.

## Check it

- `<Render URL>/v1/health` shows `"service":"ok"`.
- The site's `/live` page lists every Stock Token with "Live: Robinhood Chain mainnet,
  read-only".
- `/positions`: "Try a live borrower" appears within a minute of a cold start.
- Telegram: `/watch NVDA` answers "Following NVDA"; `/list` shows it.
- GitHub **Actions** tab: hourly runs on weekdays; inside a pre-close window they show the bot
  and alerts steps.
- Render **Logs**: `serve:` lines say what started and why the rest did not.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Every panel says it can't reach the engine | `CORS_ORIGINS` does not match the site's URL exactly, or `NEXT_PUBLIC_API_BASE_URL` was set after the build (redeploy on Vercel). |
| The site is slow to answer the first time | Render woke the API (about a minute). Set up step 6. |
| The bot does not answer in Telegram | The webhook is not set (step 7), or the secret on Render differs from the one in `.env`, or `TELEGRAM_BOT_TOKEN` is missing on Render. Run `uv run afterhours alerts set-webhook <URL>` again; it prints what Telegram has. |
| No pre-close alerts arrive | The Actions secrets are missing, the schedule was disabled (60 days without activity), or a run was delayed past the window. Check the **Actions** tab. |
| Vault pages say "No deployment for this profile yet" | Step 9 is not done for the profile in `AFTERHOURS_ACTIVE_PROFILE`, or `deployments/<profile>.json` is not pushed. |
| Upstash says the database is archived | No activity for 30 days or more; restore it from the backup in the Upstash console. |

## Optional paid path: `render.yaml`

`render.yaml` (Render's default Blueprint file) runs the API, the bot and Telegram long polling
in one paid web service with a 1 GB disk at `/var/data`. There, state lives in files on the disk
(`AFTERHOURS_PATHS__STATE_DIR`, `AFTERHOURS_DATA__CACHE_DIR`), and GitHub Actions and Upstash are
not needed. Render keeps only files under the disk's mount path across restarts
(render.com/docs/disks), disks need a paid plan, and the plan is `1c-2g` because the API and the
bot together measured about 390 MB (240 plus 149). `serve.sh` starts:
- the bot when `ALLOCATOR_PK` is set and the profile is deployed;
- long polling when `TELEGRAM_BOT_TOKEN` is set and `TELEGRAM_WEBHOOK_SECRET` is not.
