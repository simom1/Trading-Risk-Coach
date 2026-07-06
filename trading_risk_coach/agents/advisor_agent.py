"""
Advisor Agent
----------------------------------
[Design Intent]
This agent evaluates calculations and executes active risk mitigation actions. 
By binding the trade database toolset, the agent can call `execute_risk_mitigation` 
to protect the client account.

[Implementation]
- Bind `trade_data_toolset` from `analysis_agent`.
- Implement `after_model_callback` for deterministic safety filter.
- Updates instructions to actively call tools when critical risk boundaries are crossed.
"""

import os
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from trading_risk_coach.guardrails.safety_rules import sanitize_advice
from trading_risk_coach.agents.analysis_agent import trade_data_toolset

# Resolve path to the Skill markdown specification
_SKILL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "risk_pattern_detection", "SKILL.md"
)

# Load Skill content dynamically at startup
if os.path.exists(_SKILL_PATH):
    with open(_SKILL_PATH, "r", encoding="utf-8") as f:
        skill_content = f.read()
else:
    skill_content = "Disposition Ratio alert: Avg Loss / Avg Win >= 1.5 is flagged as win-small-lose-big anti-pattern."

# Output interception callback (Guardrail hook)
async def safety_guardrail_callback(callback_context: CallbackContext, llm_response: LlmResponse, **kwargs) -> LlmResponse:
    """Intercepts the LLM response to verify and sanitize safety issues before output."""
    if hasattr(llm_response, "text") and llm_response.text is not None:
        llm_response.text = sanitize_advice(llm_response.text)
    elif llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.text:
                part.text = sanitize_advice(part.text)
    return llm_response

# Define the Advisor Agent
advisor_agent = Agent(
    name="advisor_agent",
    model="gemini-3.1-flash-lite",
    description="Generates and executes risk mitigation actions based on diagnostic metrics to protect account equity.",
    tools=[trade_data_toolset],  # ✨ Bind MCP toolset to enable active execution actions
    after_model_callback=safety_guardrail_callback,  # ✨ Wire output interceptor hook
    instruction=f"""You are a quantitative risk advisor.

Input: Quantitative trading metrics analysis from the previous agent (analysis_agent).

=== Refer to the following Skill Specification for Risk Thresholds ===
{skill_content}

Your tasks:
1. Compare the analysis metrics against the quantitative thresholds defined in the Skill specification (e.g., win-small-lose-big behavior, wide stop-losses, symbol concentration).
2. Provide concrete, actionable improvement recommendations. These suggestions must focus strictly on "performance review and risk-control process optimization".
3. 【🚨 HISTORICAL RISK REPLAY SIMULATION】:
   If the user requests to see active risk control capabilities, call `simulate_historical_risk_replay` first to replay prior trades with real M1 candles and simulate how the system would have set stop losses or triggered breakers.
   You must explicitly state in the output: "This is a historical replay / what-if simulation, not a live execution on a real broker."
4. 【🚨 ACTIVE MITIGATION EXECUTION BOUNDARY】:
   If the input explicitly provides a mock active trade (e.g., ticket T1001 with severe drawdown and no stop loss), you can call `execute_risk_mitigation` to perform mock intervention:
   - Action: Call `execute_risk_mitigation` with `action_type='set_hard_sl'`, providing `ticket_id` and a calculated stop-loss price as `parameter`.
   - If the risk exceeds account limits, call `action_type='emergency_close'`.
   Always execute the tool first and present the execution outcome in your response.
5. 【🚨 CORE SAFETY BOUNDARY】:
   Strictly forbid recommending or executing "averaging down", "holding onto losses to hope for a rebound", or "doubling lot sizes (Martingale)". Any such suggestions will be intercepted by the safety guardrail.

Output format: Provide 2-4 numbered recommendations, including the outcomes of any risk mitigation tool calls, citing the numeric thresholds as justification.
"""
)
