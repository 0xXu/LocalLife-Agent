# WeekendPilot Local Life Agent

WeekendPilot is a runnable hackathon demo for the Meituan local-life challenge. It demonstrates a local activity planning and execution agent: one natural-language goal becomes constraints, mock tool calls, an itinerary, confirmation receipts, and failure recovery.

## Run The Demo

Open [index.html](./index.html) in a browser.

No install step is required for the UI. The automated behavior tests use Node.js:

```powershell
npm.cmd test
```

PowerShell may block `npm` because it resolves to `npm.ps1`; use `npm.cmd` on Windows.

## Demo Script

1. Click **生成计划**.
2. Show the parsed constraints: family, 5-year-old child, low-fat diet, 5km radius.
3. Show the Agent trace: parse, search, rank, route, availability.
4. Show the itinerary and route overview.
5. Click **确认执行** and point out `TKT-*`, `RES-*`, and `MSG-*` receipts.
6. Click **触发餐厅无位恢复** and show the restaurant replacement diff.

## Mock Tools

The demo exposes the eight P0 tools promised in the submission:

- `parse_user_goal`
- `search_places`
- `search_restaurants`
- `rank_candidates`
- `optimize_route`
- `check_availability`
- `create_reservation`
- `send_plan_message`

All tools are deterministic mocks. They are designed to show the execution chain clearly and can be replaced by real Meituan, map, booking, order, and message adapters later.

## Project Map

- [index.html](./index.html): static demo shell.
- [src/agent.mjs](./src/agent.mjs): deterministic mock agent and tool contract.
- [src/app.mjs](./src/app.mjs): browser UI wiring.
- [src/styles.css](./src/styles.css): workbench styling.
- [data/poi.json](./data/poi.json): seed POI examples.
- [tests/agent.test.mjs](./tests/agent.test.mjs): behavior tests for plan generation, execution receipts, failure recovery, and tool list.
- [design_submission.md](./design_submission.md): concise two-page submission document.
- Existing Markdown files and images are retained as research and prototype material.

## Review Finding Coverage

| Finding | Fix |
|---|---|
| Missing runnable demo code | Added static Web demo, mock agent functions, POI data, and tests. |
| Submission doc too long | Added [design_submission.md](./design_submission.md) as the concise submission version. |
| Over-heavy tech stack | Submission now states P0 as deterministic state machine + mock tools + trace. |
| Prototype lacked receipts and recovery | Demo UI includes execution receipts and a restaurant-unavailable recovery diff. |

