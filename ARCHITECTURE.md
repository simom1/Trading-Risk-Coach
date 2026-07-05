# Trading Risk Coach Architecture

This document describes the current production-facing architecture of Trading Risk Coach for Kaggle Capstone review.

## 1. System Goal

Trading Risk Coach is a behavior-driven risk review system for personal trading accounts. It focuses on post-trade analysis and active risk containment:

- Detect whether the trader is showing a "win small, lose big" pattern.
- Quantify risk through simple, auditable metrics.
- Apply rule-based risk thresholds from an Agent Skill file.
- Replay historical price paths to simulate protective risk-control actions through MCP tools.
- Block unsafe recovery-trading language through deterministic guardrails.

The system intentionally avoids market-entry recommendations and price prediction.

## 2. Runtime Flow

```text
User request
  -> ADK root_agent
  -> analysis_agent
  -> MCP read tools
  -> advisor_agent
  -> SKILL.md risk rules
  -> MCP write tool when mitigation is required
  -> safety guardrail callback
  -> critic_agent
  -> final quantitative risk report
```

## 3. Component Responsibilities

| Component | Location | Responsibility | Boundary |
| --- | --- | --- | --- |
| `root_agent` | `trading_risk_coach/agent.py` | Defines the ADK workflow graph and stage order. | Does not perform analysis itself. |
| `analysis_agent` | `trading_risk_coach/agents/analysis_agent.py` | Calls MCP tools and reports quantitative trade metrics. | Does not provide trading advice or position sizing. |
| `advisor_agent` | `trading_risk_coach/agents/advisor_agent.py` | Evaluates analysis output against `SKILL.md`; executes mitigation tools if needed. | Must not suggest averaging down, holding losses, or Martingale logic. |
| `critic_agent` | `trading_risk_coach/agents/critic_agent.py` | Audits and formats the final report with exact metrics and risk state. | Does not call external tools. |
| MCP server | `trading_risk_coach/mcp_server/trade_data_server.py` | Provides the tool boundary for real trade reads, market context, account stats, historical risk replay, and simulated broker writes. | Owns data access; agents do not read CSV directly. |
| Skill rules | `trading_risk_coach/skills/risk_pattern_detection/SKILL.md` | Defines quantitative risk thresholds and three-state action policy. | Business rules are separate from agent source code. |
| Safety guardrail | `trading_risk_coach/guardrails/safety_rules.py` | Deterministically sanitizes unsafe model output. | Runs after model generation and before user-facing output. |

## 4. Data and Tool Boundary

The project uses MCP to keep tool access separate from agent reasoning. The MCP server exposes seven tools:

| Tool | Type | Purpose |
| --- | --- | --- |
| `get_recent_trades(days)` | Read | Returns recent anonymized MT5 trade records from `real_trades.csv`. |
| `get_symbol_history(symbol, limit)` | Read | Returns trade history for one symbol such as `XAUUSD`. |
| `get_account_stats(symbol, days)` | Read | Returns win rate, average win/loss, disposition ratio, stop-loss rate, and holding-time metrics. |
| `get_symbol_breakdown()` | Read | Returns per-symbol PnL, win rate, and average win/loss breakdown. |
| `get_market_context(trade_time, window_minutes)` | Read | Returns real XAUUSD M1 price context and volatility around a trade timestamp. |
| `simulate_historical_risk_replay(limit, hard_stop_points, emergency_points)` | What-if replay | Replays historical trades with real M1 candle movement to simulate hard-stop and emergency-breaker actions. |
| `execute_risk_mitigation(action_type, ticket_id, parameter)` | Write simulation | Simulates setting a hard stop loss or emergency closing a trade. |

This design makes it possible to replace the CSV file with a real broker API or database while keeping the agents unchanged.

## 5. Skill Injection

The advisor loads:

```text
trading_risk_coach/skills/risk_pattern_detection/SKILL.md
```

Current rules include:

- Disposition Effect Index = absolute average loss / average win.
- If the ratio is at least `1.5`, flag a win-small-lose-big pattern.
- Single-trade risk must not exceed `2.0%` of account equity.
- Risk state is classified as Green, Yellow, or Red.
- Unsafe recovery logic must be intercepted.

Keeping these rules in Markdown makes the business policy readable and auditable.

## 6. Security Design

The security layer is intentionally deterministic. It does not rely only on model alignment.

`safety_rules.py` searches generated text for patterns including:

- `加仓.*回本`
- `摊平成本`
- `扛单`
- `all-in`
- `martingale`
- `马丁格尔`
- `梭哈`

If a match is found, the original text is replaced with a standard warning. This prevents unsafe recovery advice from leaking into the final interface.

## 7. Test Strategy

The test suite verifies behavior at the rule and tool level:

| Test area | Evidence |
| --- | --- |
| Skill threshold | Parses `SKILL.md` and checks the Disposition Effect threshold. |
| Guardrail | Confirms dangerous text is detected, replaced, and not leaked. |
| MCP reads | Confirms JSON records and platform summaries are valid. |
| Historical replay | Confirms M1 candle replay can classify keep-watch, hard-stop, and emergency-breaker scenarios without live broker access. |
| MCP writes | Confirms stop-loss mitigation succeeds and unknown actions fail safely. |
| ADK import | Confirms the workflow can be imported and inspected locally. |

Primary commands:

```bash
python test_sdd_specs.py
python test_runner.py
```

## 8. Deployment Shape

`Dockerfile` installs pinned dependencies and runs `python test_sdd_specs.py` as its default health command. The command can be overridden to launch the ADK web server for Cloud Run-style deployment:

```bash
adk web trading_risk_coach --host 0.0.0.0 --port 8080
```

## 9. Known Limits

- The broker execution tool is a simulation and does not place real orders.
- The current data layer uses anonymized local CSV exports; production use would replace it with a broker API or database-backed MCP server.
- The project is designed for risk review and behavior de-biasing, not financial advice.
- Live ADK model calls require a valid Gemini API key.
