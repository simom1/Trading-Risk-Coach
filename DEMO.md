# End-to-End Demo

This demo shows how Trading Risk Coach handles one complete risk-review request.

For video recording, open `replay_demo.html` and click **开始演示**. The page automatically animates the data load, ADK workflow, MCP historical replay, guardrail check, and final report.

## Demo Input

```text
Please review my recent XAUUSD trades. Tell me whether I am showing win-small-lose-big behavior, whether any active position needs risk mitigation, and produce a safe final risk report.
```

## Expected Execution Flow

1. The ADK runtime loads `root_agent` from `trading_risk_coach/agent.py`.
2. `analysis_agent` calls MCP read tools from `trade_data_server.py`.
3. The MCP server reads `trading_risk_coach/data/real_trades.csv` and, when needed, `trading_risk_coach/data/XAUUSD_M1.csv`.
4. `analysis_agent` computes metrics such as win rate, average win, average loss, loss/win ratio, stop-loss rate, holding time, and symbol concentration.
5. `advisor_agent` loads `SKILL.md` and compares the metrics against the Disposition Effect threshold.
6. If the user asks for active-risk evidence, `advisor_agent` can call `simulate_historical_risk_replay` to replay prior trades with real M1 candles and classify what the risk controls would have done.
7. For explicitly provided mock active orders, `advisor_agent` can call `execute_risk_mitigation`.
8. `safety_rules.py` sanitizes unsafe recovery-trading language.
9. `critic_agent` produces the final structured risk diagnosis.

## Tool Evidence

The MCP server exposes:

```text
get_recent_trades(days=7)
get_symbol_history(symbol="XAUUSD")
get_account_stats(symbol="XAUUSD", days=90)
get_symbol_breakdown()
get_market_context(trade_time="2026-01-06 01:35:00", window_minutes=30)
simulate_historical_risk_replay(limit=30, hard_stop_points=3.0, emergency_points=6.0)
execute_risk_mitigation(action_type="set_hard_sl", ticket_id="T1001", parameter=2350.0)
```

Example mitigation response:

```json
{
  "status": "success",
  "message": "Wind control execution successful: Order T1001 stop loss successfully set at 2350.0",
  "ticket_id": "T1001",
  "action": "SET_STOP_LOSS",
  "value": 2350.0
}
```

## Expected Final Report Shape

```markdown
# Quantitative Risk Audit Report

## Current Account Risk Rating: YELLOW WATCH

The account exhibits a disposition effect tendency. According to SKILL.md, the Disposition Ratio = (Avg Loss Absolute Value) / (Avg Win Value); a risk alert is triggered when this ratio is >= 1.5.

## Core Metrics

- Win Rate: Computed by analysis_agent based on MCP trade history.
- Average Win: Average PnL of profitable trades.
- Average Loss: Average PnL of losing trades.
- Disposition Ratio: Absolute average loss divided by average win.
- Concentration Risk: Determined by symbol/platform distribution.

## Active Mitigation Execution Logs

- Called `simulate_historical_risk_replay`
- Mode: historical replay / what-if simulation
- Action Distribution: `keep_watching` / `set_hard_sl` / `emergency_close`
- Note: The current version does not connect to a live broker; it uses historical trades and M1 candles to backtest decisions.

## De-biasing Recommendations

1. Enforce stop-losses pre-entry rather than making decisions under emotional distress.
2. If the Disposition Ratio exceeds 1.5, pause expanding risk exposure and review stop distances.
3. Never average down, hold onto losses, or apply Martingale compounding.
```

## Guardrail Demonstration

Unsafe model text:

```text
Your losses are heavy, you should average down to recover.
```

Sanitized output:

```text
[Security Guardrail Intercepted Original Suggestion] Detected that this recommendation may contain high-risk position management logic (e.g., averaging down, holding onto losses). The system does not output such recommendations. Recommended alternative: Review whether the stop-loss placement is reasonable, reduce single-trade risk exposure, or consult a licensed advisor.
```

## Local Verification

Run:

```bash
python test_sdd_specs.py
python test_runner.py
```

The first command verifies the business rules, MCP tool behavior, and guardrails. The second command verifies that the ADK workflow imports correctly and that the sanitizer works independently of a live LLM call.
