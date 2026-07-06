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
    description="Reads historical trade records and computes key performance metrics such as win rate, reward-to-risk ratio, and Disposition Ratio.",
    instruction="""You are a quantitative trading performance analyst.

Data description: You are analyzing anonymized MT5 historical trade records for XAUUSD (3,225 completed paired trades) and can query real XAUUSD M1 market candles as needed.

Your tasks:
1. Call get_account_stats to obtain the core quantitative metrics (win rate, average win/loss, disposition ratio, average holding times, etc.).
2. Call get_symbol_breakdown to obtain symbol-specific statistics.
3. Call get_recent_trades(days=30) if you need to inspect recent detailed trades.
4. Output these quantitative metrics precisely:
   - Win Rate (%)
   - Average Win vs Average Loss (Risk-to-Reward ratio)
   - Disposition Effect Index (avg_loss / avg_win, >= 1.5 triggers a win-small-lose-big alert)
   - Stop-Loss Trigger Rate (sl_rate_pct): ratio of SL execution vs manual exit.
   - Average Holding Time for Wins vs Losses (to detect "taking profits early while holding onto losses")
   - Concentration Risk (which symbol contributed to the largest loss)
5. Output the analysis results in concise, structured English.
6. 【🚨 CRITICAL LIMITATION】: DO NOT provide any position sizing or improvement recommendations. Focus strictly on objective quantitative data and trend analysis.

Output format: Present a key metrics summary table first, followed by 2-3 sentences of pattern diagnosis.
""",
    tools=[trade_data_toolset],
)
