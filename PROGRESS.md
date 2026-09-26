# Afterhours progress

## BLOCKED

Nothing yet.

## Milestones

- [ ] M0 Bootstrap
- [ ] M1 Discovery
- [ ] M2 Data and gap study
- [ ] M3 Model
- [ ] M4 Policy and backtest
- [ ] M5 Contracts
- [ ] M6 Bot and API
- [ ] M7 Simulation harness
- [ ] M8 Frontend foundation
- [ ] M9 Frontend pages
- [ ] M10 End-to-end hardening
- [ ] M11 Live deployments
- [ ] M12 Submission assets

## Log

### 2026-09-26 Session start

- Kit found in `~/Desktop/afterhours-kit`, no git repo yet. Initialised git on `main` and committed the kit as-is (`44a6fb7`).
- Toolchain on this Mac (arm64, 16 GB RAM): no Homebrew, so installed without sudo into the home folder:
  - uv 0.12.19 (`~/.local/bin`), CPython 3.12.14 through `uv python install 3.12`;
  - Foundry 1.8.3 through foundryup (`~/.foundry/bin`);
  - pnpm 9.15.9 through `npm install -g` into the nvm Node 20.20.2 prefix.
- Not installed: Homebrew, `libomp` (LightGBM needs it; handled in M3), `gh`, Docker.
- Next: M0.
