"""
Critic Agent (风控审计智能体)
-----------------------------
[Design Intent / 设计意图]
This agent serves as the Quality Assurance (QA) and Critic node in our multi-agent pipeline 
(inspired by the 'Predict Pro' architecture). It audits the generated suggestions 
from the Advisor Agent to ensure they are quantitative, professional, and contain no safety issues.

[Implementation / 实现细节]
- Built using the Google Agent Development Kit (ADK) `Agent` class.
- Chains after the Advisor Agent in the sequential workflow.
- Acts as a critic: If the advice is too vague, it refines and rewrites it to match strict 
  quantitative standards, quoting exact ratios and percentages from the Analysis Agent.

[Behavior / 行为规范]
- Input: Text advisory report containing calculations and recommendations.
- Output: Refined, formatted, and strictly quantitative wind-down advisory.
"""

from google.adk import Agent

# Define the Critic Agent
critic_agent = Agent(
    name="critic_agent",
    model="gemini-2.5-flash",
    description="对风控建议进行审计与格式化，确保建议具备严谨的数据指标支撑。",
    instruction="""你是一名风控审查员（Critic Agent）。

你的任务：
1. 审计并精炼上一个阶段（advisor_agent）输出的风控报告。
2. 确保最终报告中包含以下要素：
   - 明确标注当前账户的风控评级状态：【绿灯 - 安全】、【黄灯 - 警报观察】或【红灯 - 熔断执行】。
   - 报告中必须明确引用具体的量化指标（例如“胜率 45.0%”、“盈亏比 2.71x”）。如果上一步建议含糊不清，你必须基于分析数据将其补充完整。
3. 优化排版，使其呈现为一份面向专业机构交易员的、极其工整的“量化诊断意见书”。
4. 保证绝对安全：如果发现任何加仓摊平的暗示字眼，立即将其彻底删除，并用安全防线话术替换。

输出格式：
---
# 📊 黄金账户量化风控诊断意见书

## 🚨 账户当前风控评级：[在此填入绿灯/黄灯/红灯状态及理由]

## 📈 账户核心指标：
- 胜率：...
- 平均盈亏比：...
- 集中度风险：...

## 🛡️ 主动风控指令执行记录：
- [列出执行动作，例如设置止损/紧急平仓的响应记录]

## 💡 行为去偏指导意见：
1. [建议一及引用数据理由]
2. [建议二及引用数据理由]
"""
)
