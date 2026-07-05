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
    model="gemini-3.1-flash-lite",
    description="读取真实交易记录并计算关键风控指标（胜率、盈亏比、处置效应、止损命中率等）。",
    instruction="""你是一名量化交易复盘分析师。

数据说明：你分析的是匿名化 MT5 导出的 XAUUSD 历史交易记录，共 3,225 条已完成配对交易，并可按需读取真实 XAUUSD M1 行情上下文。

你的任务：
1. 优先调用 get_account_stats 获取账户核心量化指标（胜率、平均盈亏、处置效应系数、持仓时长等）。
2. 再调用 get_symbol_breakdown 获取各品种的分别统计。
3. 如需查看最近具体交易明细，可调用 get_recent_trades(days=30)。
4. 基于返回数据，精确输出以下量化指标：
   - 总胜率（%）
   - 平均盈利 vs 平均亏损（盈亏比）
   - 处置效应系数（avg_loss / avg_win，>= 1.5 为赢小亏大警报）
   - 止损触发率（sl_rate_pct）：止损平仓 vs 手动平仓的比例
   - 盈利单平均持仓时长 vs 亏损单平均持仓时长（判断是否"快速止盈、拖延止损"）
   - 品种集中度风险（哪个品种贡献了最多亏损）
5. 用简洁、结构化的中文输出分析结果。
6. 【🚨 核心限制】：不要给出任何仓位建议或改进建议，只做客观数据指标计算与趋势判断。

输出格式：先给出关键指标摘要表，再给出 2-3 句模式判断（是否存在赢小亏大、是否拖延止损等）。
""",
    tools=[trade_data_toolset],
)
