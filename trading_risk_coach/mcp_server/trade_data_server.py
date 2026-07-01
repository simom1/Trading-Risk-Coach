"""
Trade Data & Active Mitigation MCP Server (数据与主动风控执行 MCP 服务端)
-----------------------------------------------------------------------
[Design Intent / 设计意图]
This server handles both READ operations (fetching real historical trade logs) 
and WRITE operations (simulating active risk mitigation actions like setting stop losses or emergency closes). 
This demonstrates the complete "Observe-Think-Act" loop in agent engineering.

[Implementation / 实现细节]
- FastMCP tool registry.
- Standard historical data tools: `get_recent_trades`, `get_symbol_history`, `get_platform_summary`.
- New Active execution tool: `execute_risk_mitigation`. It modifies simulated orders or executes 
  emergency position closures, logging the operations to prove the agent can interact with broker environments.
"""

import json
import pandas as pd
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DATA_PATH = Path(__file__).parent.parent / "data" / "sample_trades.csv"
mcp = FastMCP("trade-data-server")


def _load_trades() -> pd.DataFrame:
    """Helper method to load and parse trade records from CSV file."""
    df = pd.read_csv(DATA_PATH)
    df["close_time"] = pd.to_datetime(df["close_time"])
    return df


@mcp.tool()
def get_recent_trades(days: int = 7) -> str:
    """获取最近 N 天的交易记录。

    Args:
        days: 回溯天数，默认 7 天
    """
    df = _load_trades()
    cutoff = df["close_time"].max() - pd.Timedelta(days=days)
    recent = df[df["close_time"] >= cutoff]
    return recent.to_json(orient="records", date_format="iso")


@mcp.tool()
def get_symbol_history(symbol: str) -> str:
    """获取某个交易品种的历史交易记录。

    Args:
        symbol: 品种代码，例如 'XAUUSD'
    """
    df = _load_trades()
    filtered = df[df["symbol"].str.upper() == symbol.upper()]
    return filtered.to_json(orient="records", date_format="iso")


@mcp.tool()
def get_platform_summary(platform: str) -> str:
    """获取某个交易平台的汇总统计（总盈亏、交易数、胜率）。

    Args:
        platform: 平台名称，例如 'ANZO' 或 'INFINOX'
    """
    df = _load_trades()
    filtered = df[df["platform"].str.upper() == platform.upper()]
    if filtered.empty:
        return json.dumps({"error": f"No trades found for platform {platform}"})

    win_rate = (filtered["pnl"] > 0).mean() * 100
    summary = {
        "platform": platform,
        "total_trades": int(len(filtered)),
        "total_pnl": round(float(filtered["pnl"].sum()), 2),
        "win_rate_pct": round(float(win_rate), 1),
        "avg_win": round(float(filtered.loc[filtered["pnl"] > 0, "pnl"].mean() or 0), 2),
        "avg_loss": round(float(filtered.loc[filtered["pnl"] < 0, "pnl"].mean() or 0), 2),
    }
    return json.dumps(summary)


@mcp.tool()
def execute_risk_mitigation(action_type: str, ticket_id: str, parameter: float = None) -> str:
    """执行主动风控干预动作（如修改止损、紧急平仓等模拟操作）。

    Args:
        action_type: 动作类型，可选：'set_hard_sl' (设置硬止损) 或 'emergency_close' (紧急平仓)
        ticket_id: 订单识别码 (例如 'T1001')
        parameter: 动作参数，设置硬止损时传入价格，例如 2345.50

    Returns:
        执行结果 JSON 字符串
    """
    # 模拟经纪商/交易所接收风控指令的执行响应
    action_type = action_type.lower()
    if action_type == "set_hard_sl":
        response = {
            "status": "success",
            "message": f"风控指令执行成功：订单 {ticket_id} 已成功挂载硬止损，止损价格设置为 {parameter}",
            "ticket_id": ticket_id,
            "action": "SET_STOP_LOSS",
            "value": parameter
        }
    elif action_type == "emergency_close":
        response = {
            "status": "success",
            "message": f"风控指令执行成功：由于回撤或风控违规，订单 {ticket_id} 已被强制市价平仓！",
            "ticket_id": ticket_id,
            "action": "EMERGENCY_CLOSE",
        }
    else:
        response = {
            "status": "error",
            "message": f"未知的风控指令类型: {action_type}"
        }
    return json.dumps(response)


if __name__ == "__main__":
    mcp.run()
