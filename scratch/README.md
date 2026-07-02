# Scratch Utilities

This directory is intentionally kept as a placeholder for local-only exploratory scripts.

Exploratory scripts are **not required** for the core Kaggle Capstone runtime path:

```text
ADK root_agent
-> analysis_agent
-> MCP trade_data_server
-> advisor_agent
-> safety_rules
-> critic_agent
```

## Policy

Local scratch scripts often contain machine-specific paths, local report locations, or private integration experiments. They are intentionally ignored by Git through:

```text
scratch/*.py
```

Only this README is kept in the repository so reviewers understand that `scratch/` is outside the runtime and rubric verification path.

## Review Note

For rubric verification, use the main project files instead:

- `trading_risk_coach/agent.py`
- `trading_risk_coach/agents/`
- `trading_risk_coach/mcp_server/trade_data_server.py`
- `trading_risk_coach/guardrails/safety_rules.py`
- `trading_risk_coach/skills/risk_pattern_detection/SKILL.md`
- `test_sdd_specs.py`
