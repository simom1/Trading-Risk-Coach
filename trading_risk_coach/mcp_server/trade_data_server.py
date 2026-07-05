"""
Trade Data & Active Mitigation MCP Server (数据与主动风控执行 MCP 服务端)
-----------------------------------------------------------------------
[Design Intent / 设计意图]
This server handles both READ operations (fetching anonymized real historical trade logs from
MT5 exports) and WRITE operations (simulating active risk mitigation
actions like setting stop losses or emergency closes).

[Data Source / 数据来源]
real_trades.csv: 3,225 paired open/close XAUUSD trade records from anonymized MT5 exports.
XAUUSD_M1.csv: 173,391 rows of real XAUUSD 1-minute OHLCV candles.
Fields include open_price, close_price, open_time, close_time, pnl, lot_size, symbol, etc.

[Implementation / 实现细节]
- FastMCP tool registry.
- Historical data tools: `get_recent_trades`, `get_symbol_history`, `get_account_stats`, `get_symbol_breakdown`, `get_market_context`.
- Active execution tool: `execute_risk_mitigation` simulates broker risk actions.
"""

import json
import pandas as pd
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DATA_PATH = Path(__file__).parent.parent / "data" / "real_trades.csv"
M1_PATH = Path(__file__).parent.parent / "data" / "XAUUSD_M1.csv"
mcp = FastMCP("trade-data-server")


def _load_trades() -> pd.DataFrame:
    """Helper: load and parse real trade records from CSV file."""
    df = pd.read_csv(DATA_PATH)
    df["open_time"] = pd.to_datetime(df["open_time"])
    df["close_time"] = pd.to_datetime(df["close_time"])
    return df


@mcp.tool()
def get_recent_trades(days: int = 30) -> str:
    """获取最近 N 天的已完成交易记录（开平仓配对）。

    Args:
        days: 回溯天数，默认 30 天
    """
    df = _load_trades()
    cutoff = df["close_time"].max() - pd.Timedelta(days=days)
    recent = df[df["close_time"] >= cutoff].copy()
    return recent.to_json(orient="records", date_format="iso")


@mcp.tool()
def get_symbol_history(symbol: str, limit: int = 100) -> str:
    """获取某个交易品种的历史交易记录。

    Args:
        symbol: 品种代码，例如 'XAUUSD'、'NAS100'
        limit: 最多返回记录数，默认 100
    """
    df = _load_trades()
    filtered = df[df["symbol"].str.upper() == symbol.upper()].tail(limit)
    return filtered.to_json(orient="records", date_format="iso")


@mcp.tool()
def get_account_stats(symbol: str = None, days: int = 90) -> str:
    """计算账户核心风控指标：胜率、平均盈亏、盈亏比、处置效应系数。

    Args:
        symbol: 可选，指定品种进行过滤（如 'XAUUSD'）；不填则统计全部品种
        days: 统计最近多少天，默认 90 天
    """
    df = _load_trades()
    cutoff = df["close_time"].max() - pd.Timedelta(days=days)
    df = df[df["close_time"] >= cutoff]

    if symbol:
        df = df[df["symbol"].str.upper() == symbol.upper()]

    if df.empty:
        return json.dumps({"error": "No trades found for given filters."})

    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] < 0]

    avg_win = float(wins["pnl"].mean()) if not wins.empty else 0.0
    avg_loss = float(losses["pnl"].mean()) if not losses.empty else 0.0
    avg_loss_abs = abs(avg_loss)

    # Disposition Effect Index: avg_loss_abs / avg_win >= 1.5 triggers warning
    disposition_ratio = round(avg_loss_abs / avg_win, 3) if avg_win > 0 else None

    # Average holding time
    df = df.copy()
    df["hold_minutes"] = (df["close_time"] - df["open_time"]).dt.total_seconds() / 60
    avg_hold_win = float(wins.assign(h=(wins["close_time"] - wins["open_time"]).dt.total_seconds() / 60)["h"].mean()) if not wins.empty else 0
    avg_hold_loss = float(losses.assign(h=(losses["close_time"] - losses["open_time"]).dt.total_seconds() / 60)["h"].mean()) if not losses.empty else 0

    stats = {
        "period_days": days,
        "symbol_filter": symbol or "ALL",
        "total_trades": int(len(df)),
        "win_trades": int(len(wins)),
        "loss_trades": int(len(losses)),
        "win_rate_pct": round(len(wins) / len(df) * 100, 1),
        "avg_win_usd": round(avg_win, 2),
        "avg_loss_usd": round(avg_loss, 2),
        "total_pnl_usd": round(float(df["pnl"].sum()), 2),
        "max_single_loss_usd": round(float(df["pnl"].min()), 2),
        "max_single_win_usd": round(float(df["pnl"].max()), 2),
        "disposition_effect_ratio": disposition_ratio,
        "disposition_warning": disposition_ratio is not None and disposition_ratio >= 1.5,
        "avg_hold_time_win_min": round(avg_hold_win, 1),
        "avg_hold_time_loss_min": round(avg_hold_loss, 1),
        "sl_hit_count": int((df["status"] == "closed_sl").sum()),
        "manual_close_count": int((df["status"] == "closed_manual").sum()),
        "sl_rate_pct": round((df["status"] == "closed_sl").mean() * 100, 1),
    }
    return json.dumps(stats, ensure_ascii=False)


@mcp.tool()
def get_symbol_breakdown() -> str:
    """获取各交易品种的汇总统计（交易次数、胜率、总盈亏）。"""
    df = _load_trades()
    result = {}
    for sym, group in df.groupby("symbol"):
        wins = group[group["pnl"] > 0]
        result[sym] = {
            "total_trades": int(len(group)),
            "win_rate_pct": round(len(wins) / len(group) * 100, 1),
            "total_pnl_usd": round(float(group["pnl"].sum()), 2),
            "avg_win_usd": round(float(wins["pnl"].mean()), 2) if not wins.empty else 0,
            "avg_loss_usd": round(float(group[group["pnl"] < 0]["pnl"].mean()), 2) if len(group[group["pnl"] < 0]) > 0 else 0,
        }
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def get_market_context(trade_time: str, window_minutes: int = 30) -> str:
    """获取某笔交易时刻前后的 XAUUSD M1 市场行情（真实 K 线数据）。

    Args:
        trade_time: 交易时间字符串，格式 'YYYY-MM-DD HH:MM:SS'
        window_minutes: 前后各取多少分钟的 K 线，默认 30 分钟
    """
    if not M1_PATH.exists():
        return json.dumps({"error": "M1 market data not available."})

    m1 = pd.read_csv(M1_PATH, parse_dates=["time"])
    try:
        center = pd.to_datetime(trade_time)
    except Exception:
        return json.dumps({"error": f"Invalid time format: {trade_time}"})

    mask = (m1["time"] >= center - pd.Timedelta(minutes=window_minutes)) & \
           (m1["time"] <= center + pd.Timedelta(minutes=window_minutes))
    window = m1[mask].copy()

    if window.empty:
        return json.dumps({"error": f"No M1 data found around {trade_time}"})

    # Compute ATR-like volatility: mean of (high - low) over the window
    window["range"] = window["high"] - window["low"]
    summary = {
        "trade_time": trade_time,
        "window_minutes": window_minutes,
        "candles_found": int(len(window)),
        "price_at_trade": float(m1[m1["time"] <= center].iloc[-1]["close"]) if not m1[m1["time"] <= center].empty else None,
        "high_in_window": round(float(window["high"].max()), 2),
        "low_in_window": round(float(window["low"].min()), 2),
        "avg_candle_range_pts": round(float(window["range"].mean()), 2),
        "volatility_assessment": "HIGH" if window["range"].mean() > 3.0 else "NORMAL",
        "data_source": "XAUUSD_M1.csv (173K real candles, 2026-01 to 2026-07)",
    }
    return json.dumps(summary, ensure_ascii=False)


@mcp.tool()
def execute_risk_mitigation(action_type: str, ticket_id: str, parameter: float = None) -> str:
    """执行主动风控干预动作（模拟经纪商指令）。

    Args:
        action_type: 动作类型：'set_hard_sl'（设置硬止损）或 'emergency_close'（紧急平仓）
        ticket_id: 订单识别码（例如 'T1001' 或真实 position_id）
        parameter: 动作参数，设置硬止损时传入止损价格（必须 > 0）

    Returns:
        执行结果 JSON 字符串
    """
    action_type = action_type.lower().strip()

    if action_type == "set_hard_sl":
        # Validate stop loss price parameter
        if parameter is None or parameter <= 0:
            return json.dumps({
                "status": "error",
                "message": f"无效的止损价格参数 {parameter}，止损价必须大于 0。",
                "ticket_id": ticket_id,
            })
        response = {
            "status": "success",
            "message": f"风控指令执行成功：订单 {ticket_id} 已成功挂载硬止损，止损价格设置为 {parameter}",
            "ticket_id": ticket_id,
            "action": "SET_STOP_LOSS",
            "value": parameter,
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
            "message": f"未知的风控指令类型: {action_type}。支持的类型：set_hard_sl、emergency_close",
        }
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
