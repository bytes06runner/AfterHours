# Afterhours: how to start Claude Code and keep it building

## 1. What is in this kit

| File | Purpose |
| --- | --- |
| `CLAUDE.md` | The rules Claude Code loads every session: operating mode, no hardcoding, verification, secrets, compute, quality bar |
| `docs/SPEC.md` | Full product and technical spec, 13 milestones with acceptance criteria, fallbacks |
| `docs/DESIGN.md` | The design system: concept, tokens, closing bell sequence, illustration system, pages, QA loop |
| `.claude/agents/*.md` | Four subagents: contracts, ML, frontend design, QA review |
| `.claude/settings.json` | Permissions (broad allow, secrets denied) and Mac notifications when Claude stops |
| `.mcp.json` | MCP servers: Playwright (screenshots and browser testing), Context7 (current library docs), shadcn |
| `.gitignore` | Keeps secrets and caches out of git |

## 2. One-time setup on the MacBook

```bash
xcode-select --install                      # if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"   # if no Homebrew
brew install node@22 pnpm uv libomp jq gh
curl -L https://foundry.paradigm.xyz | bash && foundryup
npm install -g @anthropic-ai/claude-code
# optional, only if a Kaggle job is ever needed:
uv tool install kaggle                      # then put kaggle.json in ~/.kaggle/
```

Create the repo and drop the kit in:

```bash
mkdir afterhours && cd afterhours
git init
# copy everything from this kit into this folder (including the hidden .claude, .mcp.json, .gitignore)
git add . && git commit -m "chore: add Claude Code build kit"
gh repo create afterhours --public --source=. --push     # public repo helps judging
```

## 3. Keys and accounts you prepare (Claude Code cannot do these for you)

Claude Code writes `.env.example` in M0. Copy it to `.env` and fill it yourself. Claude Code is blocked from reading `.env`.

| What | Where to get it | `.env` name (Claude Code will confirm) |
| --- | --- | --- |
| RPC URLs for Robinhood Chain mainnet and testnet, Arbitrum One and Sepolia | Alchemy dashboard (create one app per network) | `RH_MAINNET_RPC_URL`, `RH_TESTNET_RPC_URL`, `ARB_ONE_RPC_URL`, `ARB_SEPOLIA_RPC_URL` |
| WalletConnect project id | Reown cloud dashboard | `NEXT_PUBLIC_WC_PROJECT_ID` |
| Four throwaway keys: deployer, curator, allocator, guardian | Run `cast wallet new` four times | `DEPLOYER_PK`, `CURATOR_PK`, `ALLOCATOR_PK`, `GUARDIAN_PK` |
| Testnet ETH for those addresses | The faucets Claude Code finds in M1 | none |
| Admin token for demo endpoints | `openssl rand -hex 32` | `ADMIN_TOKEN` |
| Optional backup data keys | Finnhub, Alpha Vantage free tiers | `FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY` |
| Optional alerts | A Discord channel webhook | `ALERT_WEBHOOK_URL` |

Never put a key that holds real money in `.env`.

## 4. Launch

```bash
cd afterhours
claude --permission-mode auto
```

Auto mode lets Claude Code run almost everything without asking while a safety classifier still blocks clearly dangerous actions. If you want zero prompts, run Claude Code inside a dev container and use `claude --dangerously-skip-permissions` there, not directly on your Mac.

Inside Claude Code, check the setup:

- `/mcp` should list playwright, context7 and shadcn as connected. If one fails, ask Claude Code to fix `.mcp.json` using that server's current docs.
- `/agents` should list the four subagents.

## 5. The first prompt (paste this)

```
You are the lead engineer and design lead for Afterhours, our entry to Colosseum's Crypto World's Fair (Robinhood Chain and Arbitrum tracks).

Read CLAUDE.md, docs/SPEC.md and docs/DESIGN.md completely before writing any code.

Then:
1. Create PROGRESS.md with the milestone checklist from SPEC.md section 10, a BLOCKED section at the top, and a log section.
2. Start M0 now. Run M1 (onchain discovery and verification) in parallel through the contracts-engineer subagent, and start the M2 data work through the ml-engineer subagent as soon as M0's config loaders exist.
3. Keep going milestone after milestone without waiting for me, exactly as the operating mode in CLAUDE.md says. After every result: update PROGRESS.md with evidence, commit, write a builder update draft in updates/, print a short summary, and continue.
4. Run the qa-reviewer subagent at the end of each milestone. Must-fix findings block the next milestone.
5. Stop only for the three blocker cases in CLAUDE.md. When blocked, write the question under BLOCKED, finish everything else that is unblocked, then stop.
6. Never invent an address, parameter or number. Verify, record evidence, or use the documented fallback and label it.

Begin with M0.
```

## 6. Prompts for later

**Resume after a break or a new session**

```
Read PROGRESS.md, CLAUDE.md and the SPEC.md section for the current milestone. Resolve anything under BLOCKED that I answered below, then continue building from the next unchecked item without waiting for me.
My answers to BLOCKED: <write them here, or "none">
```

**Quick status**

```
Give me a 10-line status: milestones done, the latest measured numbers (gap study, model coverage, backtest), what is running, what is blocked, and what you are doing next. Then keep going.
```

**UI polish pass (run once pages exist)**

```
Run a full design critique with the frontend-designer subagent. For every page, run the screenshot QA loop from DESIGN.md at all widths, day, night and mid-bell. Compare against DESIGN.md and the anti-pattern list. Pick the 10 highest-impact fixes, make them, re-screenshot, and log before and after images in PROGRESS.md. The closing bell sequence must be the most memorable thing in the product; if it is not, fix that first.
```

**Pre-submission audit (run on Oct 10)**

```
Act as a skeptical Colosseum judge and a security reviewer. Run make demo from a clean clone in a temp folder. Check every number in the README, the UI and the pitch shot list against artifacts/. Check every simulated element is labelled. Check the testnet deployments and links. List everything a judge could poke a hole in, fix what can be fixed today, and write the rest as honest limitations in the README.
```

## 7. What you do while it builds

- Answer anything under BLOCKED quickly; that is the only thing that stalls the build.
- Post the drafts in `updates/` to your Colosseum project as builder updates (edit them in your own voice first).
- Book and record 3 calls with people who lend in DeFi or curate vaults. Their quotes go in the pitch.
- Learn the code as it lands: read each PROGRESS.md entry and ask Claude Code to explain anything you could not defend in a 15-minute judges' interview.
- Record the pitch video and the demo video from the shot list in M12.
