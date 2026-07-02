# Scratch Utilities

This directory contains exploratory scripts and migration helpers used during project development.

These files are **not required** for the core Kaggle Capstone runtime path:

```text
ADK root_agent
-> analysis_agent
-> MCP trade_data_server
-> advisor_agent
-> safety_rules
-> critic_agent
```

## Contents

| File group | Purpose |
| --- | --- |
| `analyze_*.py` | Local exploratory analysis of trade statements and daily summaries. |
| `generate_*.py` | One-off HTML/chart generation helpers used for presentation assets. |
| `patch_*.py` | Experimental patch utilities for external platform integration. |
| `test_paramiko_ssh.py` | SSH connectivity experiment, not part of the ADK/MCP runtime. |

## Review Note

For rubric verification, use the main project files instead:

- `trading_risk_coach/agent.py`
- `trading_risk_coach/agents/`
- `trading_risk_coach/mcp_server/trade_data_server.py`
- `trading_risk_coach/guardrails/safety_rules.py`
- `trading_risk_coach/skills/risk_pattern_detection/SKILL.md`
- `test_sdd_specs.py`
