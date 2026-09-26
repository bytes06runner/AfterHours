# Afterhours design system

Source of truth for every pixel. Read it fully before M8 and before any UI change.

## 1. Concept: the exchange after dark

The subject is the gap between two clocks: the stock exchange that closes, and the chain that never does. The whole interface is built around that. It looks like a grand 1920s exchange building rendered as crafted, illustrated, animated art, and it changes with the real market: daylight while the exchange is open, night once the closing bell rings. The product name becomes something you can see.

### What we borrow from Colosseum, and what we make ours

The brief asks for Colosseum-level craft. We borrow the DNA, not the assets.

| Colosseum DNA we borrow | How Afterhours does it differently |
| --- | --- |
| A large illustrated hero inside an ornamental frame | Our own code-drawn art deco exchange facade, inside a stepped-corner deco frame |
| A classical serif display face | Bodoni Moda, a high-contrast Didone that reads as old financial print |
| A live countdown under the hero | A closing-bell or opening-bell countdown driven by the real NYSE calendar |
| Warm, rich, non-minimal surfaces | A limestone day palette and a midnight-and-lamplight night palette |
| Ornamental dividers | Art deco sunburst and stepped-rule dividers |

Never use Colosseum's logo, wordmark, illustrations, banner frame, world's fair imagery or colours. If a screen could be mistaken for Colosseum's site, change it.

## 2. The signature moment: the closing bell

Spend the boldness here; keep everything around it disciplined.

When the market closes (at the real time, when the demo triggers a close-out, or when a visitor presses "Preview the close"), one orchestrated sequence plays, about 2.4 seconds:

1. The bell in the facade's pediment swings once.
2. The sky shifts from day to dusk to night; the limestone palette crossfades to midnight.
3. Facade windows light up in a stepped wave from the ground floor up.
4. Stars fade in behind the skyline.
5. On the allocation board, brass bars slide from the weekday slots into the weekend slots, stock by stock, matching the real (or simulated) plan.
6. A reason telegram prints into the ledger rail.

The opening bell plays the reverse, shorter. With `prefers-reduced-motion`, the whole thing becomes a 300 ms crossfade and the board updates without sliding.

The sequence is driven by real state from `/v1/status` and `/v1/stream`, never by a timer that fakes it.

## 3. Tokens

### Colour

Define as CSS variables under `[data-phase="day"]` and `[data-phase="night"]`; interpolate between them with a `--phase` value from 0 to 1 during transitions.

| Role | Day | Night |
| --- | --- | --- |
| Background | Limestone `#E4E0D5` | Midnight `#0E1430` |
| Surface | Stone `#D6D0C0` | Dusk `#1B2450` |
| Text | Ink `#1D1F33` | Moonlight `#E7E3D8` |
| Primary action, highlights | Brass `#9C7431` | Lamplight `#F1C76B` |
| Safe, allowed tier | Verdigris `#2E6B62` | Verdigris light `#62AD9F` |
| Risk, blocked tier | Signal `#A23B2D` | Signal light `#E2705F` |
| Rules and hairlines | `#B9B19C` | `#34407A` |

Brass buttons carry Ink text in day and Midnight text in night. Signal colour is reserved for risk; never for a call to action.

### Type

- Display: **Bodoni Moda** (Google Fonts, variable, optical sizes). Headlines and big numerals in the hero.
- Everything else: **Hanken Grotesk** (Google Fonts, variable). Body, UI, tables, charts. Use `font-variant-numeric: tabular-nums lining-nums` for all figures.
- Load both with `next/font`. No third family.

Scale (px): 12, 14, 16, 18, 21, 24, 36, 48, 64, 88. Body 16/1.55 in Hanken; hero display 88 desktop, 48 mobile, tracking -1%. Line length under 72 characters. Sentence case everywhere. No all-caps labels, no letter-spaced eyebrow labels.

### Shape, space and surface

- Spacing on an 8 px grid.
- Radius follows hierarchy: deco frames use stepped corners, not radius; interactive panels 12; inputs and buttons 10; badges fully rounded. Never one radius on everything.
- No drop shadows. Depth comes from double rules, inset frames, and the illustration layers.
- Texture: faint paper grain by day, film grain and stars by night. Grain via an SVG `feTurbulence` filter or a tiny `ogl` shader; it must cost under 2 ms per frame.

## 4. Illustration system

All art is code: React SVG components in `web/src/art/`, parameterised by `phase` (0 day, 1 night) and live data. No stock images, no AI-generated bitmaps.

| Piece | Description | Live data it shows |
| --- | --- | --- |
| `ExchangeFacade` | Art deco exchange: stepped setbacks, fluted columns, sunburst fan over the doors, pediment with a bell, central clock | Clock hands show real New York time; window glow follows `phase` |
| `Skyline` | Two parallax layers of stepped towers behind the facade | Lit windows at night scale with vault activity |
| `TickerRibbon` | A brass band across the facade with scrolling Stock Token prices | Live prices from the API; pauses on hover; static with reduced motion |
| `Bell` | Pediment bell used by the closing bell sequence | Swings on session change |
| `SunburstDivider` | Section divider built from rays and a stepped rule | None |
| `DecoFrame` | Double-rule frame with stepped corners, for the hero and at most one key panel per page | None |
| `AlmanacPage` | Paper page texture with ruled lines for the calendar | Closed periods and earnings |
| `Telegram` | Reason card styled as a printed telegram slip with a torn edge | Reason card content |

Draw with care: consistent stroke widths (1.25 and 2), geometry on the 8 px grid, the palette above only. Review each piece by screenshot at 2x.

## 5. Motion

| Library | Used for |
| --- | --- |
| GSAP (timelines, ScrollTrigger, SplitText) | The closing bell sequence, landing scroll story, hero entrance |
| Motion (motion/react) | UI state changes: panels opening, board bars, split-flap digits, toasts |
| Lenis | Smooth scrolling on the landing page only |

Rules:

- One orchestrated entrance on the landing page. Do not fade-and-slide every section.
- Motion answers state: a bar moves because money moved, a digit flips because a number changed.
- Durations 150 to 400 ms for UI, up to 2.4 s only for the closing bell. Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)` for UI.
- Everything has a reduced-motion path.

## 6. Components

| Component | Notes |
| --- | --- |
| `SessionBadge` | "Exchange open" or "Afterhours" with the time until the next bell |
| `BellCountdown` | Split-flap countdown to the next close or open |
| `SplitFlap` | Mechanical flip digits for TVL, APY, countdowns; tabular Hanken bold |
| `AllocationBoard` | One row per stock; weekday and weekend slots; brass bars sized by USDG; borrowed portion hatched; idle shown as a separate reservoir |
| `RiskGauge` | Semicircle gauge of bad-case drop vs each tier's cushion, with the allowed zone in verdigris |
| `ReasonTelegram` | Printed reason card with SHAP driver bars and a `Verify on chain` button |
| `VerifyBadge` | Recomputes the RFC 8785 hash in the browser, reads the registry event, shows matched or mismatched with the tx link |
| `ChartKit` | visx charts themed with tokens: gap histogram with the tail shaded signal, calibration plot with a diagonal, allocation over time by tier, replay dual timeline |
| `DepositPanel` | Deposit and withdraw USDG with clear previews of shares and available liquidity |
| `SimulationBanner` | Always visible when any data or contract on screen is simulated |

Base primitives come from shadcn/ui (Radix), fully restyled with our tokens; nothing should look like default shadcn.

## 7. Pages

### Landing `/`

```
+----------------------------------------------------------------------------+
| Afterhours     Vault   Almanac   Ledger   Replay   Report card  [Connect]  |
|                                                                            |
|  +--deco frame-----------------------------------------------------------+ |
|  |   sky . stars . skyline                                               | |
|  |            [ ExchangeFacade: bell, clock at NY time, lit windows ]    | |
|  |   ========== ticker ribbon: NVDA 182.40  TSLA 311.02  AAPL ... ====== | |
|  +------------------------------------------------------------------------+ |
|                                                                            |
|  The market is closed.                         Next opening bell           |
|  Stock Tokens aren't.                          [4][1]:[0][6]:[2][2]        |
|  Afterhours moved lender money to safer       [ Open the vault ]           |
|  markets before the bell. Here's why.         [ Preview the close ]        |
|                                                                            |
|  --- sunburst divider ---                                                  |
|  Scroll story (pinned, GSAP): the gap chart (real data from M2) ->         |
|  the two bad settings -> the closing bell on the board -> a telegram ->    |
|  the replay teaser -> the report card numbers                              |
+----------------------------------------------------------------------------+
```

The hero headline changes with the session: by day "The market is open. Lending runs at full speed." with sub "When the bell rings, Afterhours pulls back first." By night the version above.

### Vault `/vault`

```
+------------------------------+---------------------------------------------+
| Your position                |  Allocation board                           |
| Deposit USDG / Withdraw      |  NVDA  weekday [#####////   ] weekend [##  ] |
| Shares, value, APY (flap)    |  TSLA  weekday [##          ] weekend [####] |
|                              |  AAPL  ...                                   |
| Session badge + countdown    |  Idle reservoir [===]                        |
+------------------------------+---------------------------------------------+
| Latest telegrams (3) ................................. See the ledger      |
+----------------------------------------------------------------------------+
```

### Almanac `/almanac`

A paper almanac spread: one column per upcoming day, closed periods drawn as night bands across the week, earnings as small bell icons, and per stock the predicted bad-case drop as a band against each tier's cushion. Clicking a stock opens its `RiskGauge` and drivers.

### Ledger `/ledger`

A vertical rail of telegrams, newest first, filterable by stock and action. Each has `Verify on chain`. An empty ledger says when the next plan will run, using the real schedule.

### Replay `/replay`

A theatre: scenario picker on the left (scenarios come from the backtest, labelled with date, stock and segment); two stages side by side, "Ordinary vault" and "Afterhours", sharing one scrubbable timeline of the real historical price path; a bad debt counter under each; the Afterhours stage shows the telegram it would have printed. Labelled "historical stock prices, simulated vault".

### Report card `/report-card`

Plain, trustworthy, less ornament: calibration plot per segment, coverage table, pinball loss vs baselines, backtest results for all four strategies, and a short methods section. If the model fell back to a baseline, this page says so in the first sentence.

## 8. Copy voice

- Plain verbs, sentence case, no filler, no hype, no em dashes.
- Name things by what people understand: "Deposit USDG", "Withdraw", "Verify on chain", "Replay this night", "Preview the close", "Open the vault".
- An action keeps its name through the flow: the "Deposit USDG" button leads to a "Deposited" toast.
- Errors say what happened and what to do: "Can't reach Robinhood Chain. Retrying in 10 seconds."
- Every number shown comes from an artifact or the API. No placeholder numbers in production builds.

## 9. Wallet

RainbowKit with a custom theme built from our tokens (radius, fonts, colours per phase). Chains and RPCs come from `/v1/config/public`.

## 10. Anti-patterns (reject on sight)

- Identical rounded cards with the same soft shadow in a grid.
- Tracked-out all-caps eyebrow labels above headings.
- Gradient washes as decoration.
- Fade-and-slide-up on every section; hover animations on every card.
- Monospace for small labels; an arrow appended to every button.
- Meta strings joined with middle dots.
- One word in a headline set in a different colour or italic.
- Anything that looks like default shadcn or a generic dashboard template.

## 11. Screenshot QA loop (required after every UI change)

1. Run the app against the fork with seeded data.
2. With the Playwright MCP, capture 1440, 1024 and 390 px wide, in day and night, plus mid-transition at the bell.
3. Check: hierarchy reads in 3 seconds; one memorable element per page; contrast AA or better; nothing overflows at 390 px; focus rings visible; reduced motion works; no anti-pattern above.
4. Write three concrete critiques, fix them, capture again.
5. Save the final set to `artifacts/screens/<page>/` and link them in PROGRESS.md.
