"""
Trade Data & Active Mitigation MCP Server
-----------------------------------------------------------------------
[Design Intent]
This server handles both READ operations (fetching anonymized real historical trade logs from
MT5 exports) and WRITE operations (simulating active risk mitigation
actions like setting stop losses or emergency closes).

[Data Source]
real_trades.csv: 3,225 paired open/close XAUUSD trade records from anonymized MT5 exports.
XAUUSD_M1.csv: 173,391 rows of real XAUUSD 1-minute OHLCV candles.
Fields include open_price, close_price, open_time, close_time, pnl, lot_size, symbol, etc.

[Implementation]
- FastMCP tool registry.
- Historical data tools: `get_recent_trades`, `get_symbol_history`, `get_account_stats`, `get_symbol_breakdown`, `get_market_context`, `simulate_historical_risk_replay`.
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
    """Fetch completed paired trade records for the last N days.

    Args:
        days: Lookback days, defaults to 30.
    """
    df = _load_trades()
    cutoff = df["close_time"].max() - pd.Timedelta(days=days)
    recent = df[df["close_time"] >= cutoff].copy()
    return recent.to_json(orient="records", date_format="iso")


@mcp.tool()
def get_symbol_history(symbol: str, limit: int = 100) -> str:
    """Fetch historical trade records for a specific symbol.

    Args:
        symbol: Symbol name, e.g., 'XAUUSD', 'NAS100'.
        limit: Maximum number of records, defaults to 100.
    """
    df = _load_trades()
    filtered = df[df["symbol"].str.upper() == symbol.upper()].tail(limit)
    return filtered.to_json(orient="records", date_format="iso")


@mcp.tool()
def get_account_stats(symbol: str = None, days: int = 90) -> str:
    """Calculate account core performance metrics: win rate, average win/loss, reward-risk ratio, and Disposition Ratio.

    Args:
        symbol: Optional symbol filter (e.g. 'XAUUSD'); defaults to all symbols.
        days: Number of days to include, defaults to 90.
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
    """Fetch summary statistics for each symbol (trade counts, win rate, net PnL)."""
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
    """Query XAUUSD M1 market candles around a specific trade execution timestamp.

    Args:
        trade_time: Execution time string in 'YYYY-MM-DD HH:MM:SS' format.
        window_minutes: Lookback/lookforward minutes, defaults to 30.
    """
    if not M1_PATH.exists():
        return json.dumps({"error": "M1 market data not available."})

    m1 = pd.read_csv(M1_PATH, parse_dates=["time"])
    try:
        center = pd.to_datetime(trade_time) - pd.Timedelta(hours=8)
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
def simulate_historical_risk_replay(
    limit: int = 20,
    hard_stop_points: float = 5.0,
    emergency_points: float = 10.0,
) -> str:
    """Backtest and simulate risk-control actions using historical trades and real M1 price paths.

    This is a historical what-if simulation, not live broker execution. It replays
    each historical trade as if it were an active position at the time, then checks
    whether a protective hard stop or emergency breaker would have been triggered.
    It uses relative M1 price movement inside the trade window rather than absolute
    price equality, because broker execution exports and market candles can have
    small source/timezone/quote-level differences.

    Args:
        limit: Max number of replayable trades, defaults to 20.
        hard_stop_points: Mock stop-loss distance, defaults to 5.0 XAUUSD points.
        emergency_points: Mock breaker distance, defaults to 10.0 XAUUSD points.
    """
    if not M1_PATH.exists():
        return json.dumps({"error": "M1 market data not available."})

    trades = _load_trades()
    # Convert trades times to Datetime objects and subtract 8 hours for UTC M1 matching
    trades["open_time_dt"] = pd.to_datetime(trades["open_time"])
    trades["close_time_dt"] = pd.to_datetime(trades["close_time"])
    trades["open_time_utc"] = trades["open_time_dt"] - pd.Timedelta(hours=8)
    trades["close_time_utc"] = trades["close_time_dt"] - pd.Timedelta(hours=8)

    m1 = pd.read_csv(M1_PATH, parse_dates=["time"])
    m1_start = m1["time"].min()
    m1_end = m1["time"].max()

    replayable = trades[
        (trades["symbol"].str.upper() == "XAUUSD")
        & (trades["open_time_utc"] >= m1_start)
        & (trades["close_time_utc"] <= m1_end)
    ].tail(limit)

    events = []
    for _, trade in replayable.iterrows():
        window = m1[
            (m1["time"] >= trade["open_time_utc"])
            & (m1["time"] <= trade["close_time_utc"])
        ]
        if window.empty:
            continue

        direction = str(trade["direction"]).upper()
        entry_price = float(trade["open_price"])
        lot_size = float(trade["lot_size"])
        point_value_usd = lot_size * 100.0

        reference_price = float(window.iloc[0]["close"])
        relative_low = window["low"] - reference_price
        relative_high = window["high"] - reference_price

        if direction == "B":
            max_adverse_points = max(0.0, -float(relative_low.min()))
            max_favorable_points = max(0.0, float(relative_high.max()))
            hard_stop_price = round(entry_price - hard_stop_points, 2)
            emergency_price = round(entry_price - emergency_points, 2)
            hard_stop_hit = max_adverse_points >= hard_stop_points
            emergency_hit = max_adverse_points >= emergency_points
        else:
            max_adverse_points = max(0.0, float(relative_high.max()))
            max_favorable_points = max(0.0, -float(relative_low.min()))
            hard_stop_price = round(entry_price + hard_stop_points, 2)
            emergency_price = round(entry_price + emergency_points, 2)
            hard_stop_hit = max_adverse_points >= hard_stop_points
            emergency_hit = max_adverse_points >= emergency_points

        actual_pnl = float(trade["pnl"])
        hard_stop_pnl = -hard_stop_points * point_value_usd
        emergency_pnl = -emergency_points * point_value_usd

        if emergency_hit:
            replay_action = "emergency_close"
            replay_state = "RED_BREAKER"
            replay_pnl = emergency_pnl
        elif hard_stop_hit:
            replay_action = "set_hard_sl"
            replay_state = "YELLOW_WATCH"
            replay_pnl = hard_stop_pnl
        else:
            replay_action = "keep_watching"
            replay_state = "GREEN_SAFE"
            replay_pnl = actual_pnl

        replay_delta = round(replay_pnl - actual_pnl, 2)
        events.append({
            "position_id": str(trade["position_id"]),
            "symbol": trade["symbol"],
            "direction": direction,
            "open_time": trade["open_time"].isoformat(),
            "close_time": trade["close_time"].isoformat(),
            "entry_price": round(entry_price, 2),
            "actual_close_price": round(float(trade["close_price"]), 2),
            "actual_pnl_usd": round(actual_pnl, 2),
            "market_reference_price": round(reference_price, 2),
            "max_adverse_points": round(max_adverse_points, 2),
            "max_favorable_points": round(max_favorable_points, 2),
            "hard_stop_price": hard_stop_price,
            "emergency_price": emergency_price,
            "replay_state": replay_state,
            "replay_action": replay_action,
            "replay_pnl_usd": round(replay_pnl, 2),
            "replay_delta_vs_actual_usd": replay_delta,
            "saved_loss_usd": max(0.0, replay_delta),
            "opportunity_cost_usd": max(0.0, -replay_delta),
        })

    summary = {
        "mode": "historical_replay_not_live_trading",
        "description": "Replays historical trades with real M1 candles to simulate what active risk controls would have done at the time.",
        "evaluated_trades": len(events),
        "hard_stop_points": hard_stop_points,
        "emergency_points": emergency_points,
        "actions": {
            "keep_watching": sum(1 for event in events if event["replay_action"] == "keep_watching"),
            "set_hard_sl": sum(1 for event in events if event["replay_action"] == "set_hard_sl"),
            "emergency_close": sum(1 for event in events if event["replay_action"] == "emergency_close"),
        },
        "total_replay_delta_vs_actual_usd": round(sum(event["replay_delta_vs_actual_usd"] for event in events), 2),
        "events": events,
    }
    return json.dumps(summary, ensure_ascii=False)


@mcp.tool()
def execute_risk_mitigation(action_type: str, ticket_id: str, parameter: float = None) -> str:
    """Execute active risk mitigation actions (simulating broker execution instructions).

    Args:
        action_type: Mitigation type: 'set_hard_sl' or 'emergency_close'.
        ticket_id: Position ticket identifier (e.g. 'T1001' or real database ID).
        parameter: Optional parameter (e.g., target stop loss price).

    Returns:
        JSON response from the mock broker execution endpoint.
    """
    action_type = action_type.lower().strip()

    if action_type == "set_hard_sl":
        # Validate stop loss price parameter
        if parameter is None or parameter <= 0:
            return json.dumps({
                "status": "error",
                "message": f"Invalid stop loss price parameter {parameter}; stop loss must be greater than 0.",
                "ticket_id": ticket_id,
            })
        response = {
            "status": "success",
            "message": f"Wind control execution successful: Order {ticket_id} stop loss successfully set at {parameter}",
            "ticket_id": ticket_id,
            "action": "SET_STOP_LOSS",
            "value": parameter,
        }
    elif action_type == "emergency_close":
        response = {
            "status": "success",
            "message": f"Wind control execution successful: Order {ticket_id} closed at market due to risk limit breach!",
            "ticket_id": ticket_id,
            "action": "EMERGENCY_CLOSE",
        }
    else:
        response = {
            "status": "error",
            "message": f"Unknown risk mitigation action: {action_type}. Supported actions: set_hard_sl, emergency_close",
        }
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
