"""
Trading Risk Coach — Root Agent Orchestration (根节点工作流编排)
-----------------------------------------------------------------
[Design Intent / 设计意图]
This module defines the entry point and structural workflow execution path of the project. 
It chains the specialized sub-agents in a sequential logic graph. 
Upgraded to a 3-agent orchestration (Analysis -> Advisor -> Critic) inspired by the 'Predict Pro' architecture.

[Implementation / 实现细节]
- Built using the Google Agent Development Kit (ADK) `Workflow` class.
- Defines sequential edges representing transition boundaries:
  `START` -> `analysis_agent` -> `advisor_agent` -> `critic_agent` -> `END`.
- When users invoke the TUI CLI via `adk run` or start the interactive client via `adk web`, 
  the ADK runtime targets and instantiates the `root_agent` workflow in this module.

[Behavior / 行为规范]
- Workflow Entry: Start input contains the prompt and/or targets.
- Transitions: Flow proceeds from Analysis (Observe) to Advisor (Think & Act) to Critic (Audit/QA).
- Exit: Outputs the safe, audited, de-biased, and sanitized final advisory text block.
"""

from trading_risk_coach import config  # noqa: F401 - load local .env before agents start
from google.adk import Workflow
from trading_risk_coach.agents.analysis_agent import analysis_agent
from trading_risk_coach.agents.advisor_agent import advisor_agent
from trading_risk_coach.agents.critic_agent import critic_agent

# Orchestrate workflow graph matching Kaggle ADK multi-stage specifications
root_agent = Workflow(
    name="trading_risk_coach",
    edges=[
        ("START", analysis_agent),       # Edge 1: Start entry transitions to Analysis Agent
        (analysis_agent, advisor_agent), # Edge 2: Analysis output transitions to Advisor Agent
        (advisor_agent, critic_agent)    # Edge 3: Advisor output transitions to Critic Agent for audit
    ],
)
