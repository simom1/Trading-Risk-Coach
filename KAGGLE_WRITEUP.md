# Kaggle Capstone Project Writeup: Trading Risk Coach

**Track:** Agents for Business  
**Project Repository:** https://github.com/simom1/Trading-Risk-Coach

> Trading Risk Coach is a trading behavior risk-review and de-biasing system. It is not an investment advice product, a signal generator, or a market prediction tool.

## Data Sources

This project uses **real market data** from two sources:

| Data | File | Description |
| --- | --- | --- |
| Real trade history | `real_trades.csv` | 3,648 paired open/close trades from real MT5 account 8010234, covering XAUUSD, NAS100, XAGUSD, US30 (Nov 2025 – Jul 2026) |
| Real market prices | `XAUUSD_M1.csv` | 173,391 rows of XAUUSD 1-minute OHLCV candles (Jan – Jul 2026, price range 3942–5597) |

## 1. Product Background and Problem

Retail and small-account traders often lose money through repeated behavioral patterns rather than a lack of chart access. One common pattern is the Disposition Effect: taking small profits quickly while allowing losing trades to grow. Other high-risk patterns include trading without hard stop losses, concentrating risk in one symbol, and trying to recover losses through averaging down or Martingale-style sizing.

**Trading Risk Coach** addresses this as a post-trade review and active risk-control workflow. It analyzes historical XAUUSD trade records, quantifies behavior risk, applies explicit business rules from an Agent Skill, simulates protective broker actions through MCP tools, and uses deterministic guardrails to block unsafe recovery-trading advice.

## 2. Architecture Diagram

```text
User risk-review request
  -> ADK root_agent
  -> analysis_agent
       -> MCP read tools
       -> sample_trades.csv
  -> advisor_agent
       -> SKILL.md quantitative rules
       -> MCP write tool when mitigation is required
       -> safety_rules.py after_model_callback
  -> critic_agent
  -> final quantitative risk report
```

## 3. Rubric Mapping and Evidence

| Rubric Requirement | Implementation Evidence | Verification Evidence |
| --- | --- | --- |
| ADK Agent and Multi-Agent workflow | `trading_risk_coach/agent.py` defines a sequential ADK workflow: `analysis_agent -> advisor_agent -> critic_agent`. | `python test_runner.py` imports the workflow and prints the registered edges. |
| MCP Server over stdio | `trade_data_server.py` exposes FastMCP tools for trade reads and simulated risk actions. | `python test_sdd_specs.py` validates MCP JSON reads and mitigation writes. |
| Agent Skills | `SKILL.md` defines the Disposition Effect threshold, 2% risk limit, and Green/Yellow/Red risk logic. | The SDD test parses `SKILL.md` and asserts the threshold is used. |
| Security Features | `safety_rules.py` uses deterministic pattern checks to block averaging down, holding losses, all-in, and Martingale advice. | The SDD test confirms dangerous text is replaced and the unsafe original phrase does not leak. |
| Deployability | `Dockerfile` and pinned `requirements.txt` provide a container-ready runtime. | The Docker default command runs the same behavior verification suite. |

## 4. Core Code Files

- `trading_risk_coach/agent.py`: ADK root workflow.
- `trading_risk_coach/agents/analysis_agent.py`: MCP-backed trade metric analysis.
- `trading_risk_coach/agents/advisor_agent.py`: Skill-based risk diagnosis and active mitigation.
- `trading_risk_coach/agents/critic_agent.py`: quantitative report audit and formatting.
- `trading_risk_coach/mcp_server/trade_data_server.py`: FastMCP server with 5 tools:
  - `get_recent_trades` — recent trade records from real MT5 account
  - `get_account_stats` — full quantitative metrics (disposition ratio, SL rate, hold time)
  - `get_symbol_breakdown` — per-symbol PnL and win rate breakdown
  - `get_market_context` — real M1 price context around any trade timestamp (volatility, ATR)
  - `execute_risk_mitigation` — simulated broker risk actions with parameter validation
- `trading_risk_coach/data/real_trades.csv`: 3,648 real MT5 trade records.
- `trading_risk_coach/data/XAUUSD_M1.csv`: 173,391 real 1-minute XAUUSD candles.
- `trading_risk_coach/skills/risk_pattern_detection/SKILL.md`: decoupled business rules.
- `trading_risk_coach/guardrails/safety_rules.py`: deterministic safety guardrails.
- `test_sdd_specs.py`: behavior-driven verification suite.

## 5. Complete Demo Input and Output

Demo input:

```text
Please review my recent XAUUSD trades. Tell me whether I am showing win-small-lose-big behavior, whether any active position needs risk mitigation, and produce a safe final risk report.
```

Expected system behavior:

1. `analysis_agent` calls MCP tools to load trade records.
2. It computes win rate, average win, average loss, loss/win ratio, and concentration risk.
3. `advisor_agent` compares those metrics against `SKILL.md`.
4. When active risk is detected, it calls `execute_risk_mitigation`, for example `set_hard_sl`.
5. `safety_rules.py` blocks unsafe recovery language.
6. `critic_agent` produces the final structured report.

Example MCP mitigation response:

```json
{
  "status": "success",
  "message": "风控指令执行成功：订单 T1001 已成功挂载硬止损，止损价格设置为 2350.0",
  "ticket_id": "T1001",
  "action": "SET_STOP_LOSS",
  "value": 2350.0
}
```

## 6. Security Mechanism

The project uses a zero-trust output safety layer. The model may reason about risk, but final user-facing text is still passed through deterministic Python checks. If text includes patterns such as `加仓.*回本`, `摊平成本`, `扛单`, `all-in`, `martingale`, or `马丁格尔`, the output is replaced with a safety warning.

This matters because the project domain is trading risk. The system should never encourage a user to recover losses by increasing exposure.

## 7. Test Results

```text
$ python test_sdd_specs.py
[Pass] Threshold calculation conforms to SKILL.md definition.
[Pass] Guardrail successfully intercepted the Averaging Down pattern.
[Pass] Guardrail successfully intercepted the Position Holding pattern.
[Pass] MCP read tools returned valid records and summaries.
[Pass] Advisor Agent successfully executed active Stop-Loss command on Mock Broker.
[Pass] MCP write tool rejects unknown mitigation actions safely.
All Spec-Driven Development behavior tests PASSED.

$ python test_runner.py
ADK workflow loaded successfully.
Workflow Edges:
  - START -> analysis_agent
  - analysis_agent -> advisor_agent
  - advisor_agent -> critic_agent
Agent Models:
  - analysis_agent: gemini-3.1-flash-lite
  - advisor_agent: gemini-3.1-flash-lite
  - critic_agent: gemini-3.1-flash-lite
Guardrail successfully intercepted unsafe recovery advice.
```

## 8. Reproducibility and Deployment

```bash
git clone https://github.com/simom1/Trading-Risk-Coach.git
cd Trading-Risk-Coach
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python test_sdd_specs.py
python test_runner.py
adk web trading_risk_coach
```

Container deployment is supported through `Dockerfile`. The default container command runs `python test_sdd_specs.py` as a health verification step and can be overridden to launch `adk web trading_risk_coach --host 0.0.0.0 --port 8080` for Cloud Run-style deployment.

## 9. Limitations and Future Work

- The broker execution layer is a simulation and does not place real orders.
- The sample data is local CSV data; production use would replace it with a broker API or database-backed MCP server.
- The current guardrail is intentionally conservative and keyword-based. Future versions could add policy versioning and structured safety audits.
- Future work could include portfolio-level exposure aggregation, richer drawdown analytics, and an operator dashboard.

## 10. Final Positioning

Trading Risk Coach is best understood as a **trading behavior risk-control and review assistant**. It does not predict markets, recommend entries, or provide investment advice. Its value is in making risk behavior measurable, auditable, and safer through ADK multi-agent orchestration, MCP tool boundaries, explicit Agent Skill rules, and deterministic safety guardrails.
