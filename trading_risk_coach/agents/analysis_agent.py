"""
Analysis Agent (数据分析师智能体)
----------------------------------
[Design Intent / 设计意图]
This agent serves as Phase 1 of our multi-agent pipeline. Its sole responsibility is 
to ingest and analyze trade data. By limiting its scope to data aggregation and calculation 
(without generating trade advice), we satisfy the "Separation of Concerns" (关注点分离) software design principle.

[Implementation / 实现细节]
- Built using the Google Agent Development Kit (ADK) `Agent` class.
- Tool Ingestion via Model Context Protocol (MCP): The agent does NOT access the filesystem 
  directly. Instead, it interacts with an out-of-process MCP server (`trade_data_server.py`) 
  over stdio using `MCPToolset` and `StdioConnectionParams`.
- Decoupling logic: Replacing CSV storage with a production live database requires zero 
  changes to this agent; only the MCP server needs to be updated.

[Behavior / 行为规范]
- Expected behavior: Actively calls `get_recent_trades` or other available tools.
- Expected output: Outputs key risk metrics (win-rate, reward-to-risk ratio, max drawdown, concentration).
- Strict bounds: Prohibited from suggesting trading size or entries (delegated to the Advisor Agent).
"""

import os
import sys
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Resolve absolute path to the out-of-process MCP Server script
_SERVER_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mcp_server",
    "trade_data_server.py",
)

# Connect to the MCP Server over standard I/O (stdio) connection
trade_data_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[_SERVER_SCRIPT],
        ),
        timeout=30,  # 30 seconds connection timeout
    ),
)

# Define the Analysis Agent
analysis_agent = Agent(
    name="analysis_agent",
    model="gemini-2.5-flash",
    description="读取交易记录并计算关键风控指标（胜率、盈亏比、止损合理性等）。",
    instruction="""你是一名量化交易复盘分析师。

你的任务：
1. 必须调用工具获取最近的交易记录（按需调用 get_recent_trades / get_symbol_history / get_platform_summary）。
2. 基于返回的交易记录，精确计算以下量化指标：
   - 总胜率
   - 平均盈利 vs 平均亏损（盈亏比）
   - 单笔最大亏损
   - 止损设置是否普遍偏大（导致"赢小亏大"结构）
   - 品种/平台集中度风险
3. 用简洁、结构化的中文输出分析结果。
4. 【🚨 核心限制】：不要给出任何仓位建议或改进建议，只做客观的数据指标计算与趋势判断。仓位建议和风控措施交给下一个阶段的 agent（advisor_agent）处理。

输出格式要求：先给出关键指标摘要，再给出 1-2 句模式判断（例如是否存在赢小亏大）。
""",
    tools=[trade_data_toolset],  # Wrapped in a list to satisfy Pydantic type specifications
)

