"""
Advisor Agent (风控顾问智能体)
----------------------------------
[Design Intent / 设计意图]
This agent evaluates calculations and executes active risk mitigation actions. 
By binding the trade database toolset, the agent can call `execute_risk_mitigation` 
to protect the client account.

[Implementation / 实现细节]
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
    skill_content = "指标阈值警报：平均亏损绝对值 / 平均盈利 >= 1.5 判定为赢小亏大反模式。"

# Output interception callback (Guardrail hook)
async def safety_guardrail_callback(callback_context: CallbackContext, llm_response: LlmResponse, **kwargs) -> LlmResponse:
    """Intercepts the LLM response to verify and sanitize safety issues before output."""
    llm_response.text = sanitize_advice(llm_response.text)
    return llm_response

# Define the Advisor Agent
advisor_agent = Agent(
    name="advisor_agent",
    model="gemini-2.5-flash",
    description="基于分析结果生成并执行风控建议，保护账户安全。",
    tools=[trade_data_toolset],  # ✨ Bind MCP toolset to enable active execution actions
    after_model_callback=safety_guardrail_callback,  # ✨ Wire output interceptor hook
    instruction=f"""你是一名风控顾问。

输入：上一个 agent（analysis_agent）给出的交易指标分析结果。

=== 依据以下技能规范进行量化判定 (Agent Skill) ===
{skill_content}

你的任务：
1. 针对分析结果中暴露的问题（如赢小亏大、止损过宽、品种过度集中），
   结合上述 Skill 规范中定义的定量阈值标准进行对比诊断。
2. 给出具体、可执行的改进建议。建议必须聚焦在「事后复盘与流程优化」层面。
3. 【🚨 核心升级 - 主动执行】：
   如果分析报告或输入指出存在“未设置止损的高危活跃订单”（例如订单号 T1001 浮亏严重且无止损），
   你必须立即调用工具 `execute_risk_mitigation` 进行干预：
   - 动作：使用 `action_type='set_hard_sl'`，填入订单号 `ticket_id`，并计算出一个合理的硬止损价格作为 `parameter` 传入。
   - 如果风险超过账户承受能力，可直接调用 `action_type='emergency_close'` 进行紧急平仓。
   在生成最终建议前，请先执行该工具，并在输出中展示执行结果。
4. 【🚨 核心安全底线】：
   严禁给出或执行任何形式的"加仓摊平成本"、"扛单等回本"等建议或动作。
   这类高危仓位决策会被系统安全护栏物理截断。

输出格式：用 2-4 条编号建议呈现，包含风控操作执行结果（如订单设置止损的响应），并附一句引用判定标准的数字作为理由。
"""
)
