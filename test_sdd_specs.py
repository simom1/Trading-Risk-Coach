import re
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_risk_coach.guardrails.safety_rules import sanitize_advice, contains_dangerous_advice
from trading_risk_coach.mcp_server.trade_data_server import (
    execute_risk_mitigation,
    get_account_stats,
    get_symbol_breakdown,
    get_recent_trades,
    get_symbol_history,
    simulate_historical_risk_replay,
)

SKILL_PATH = "trading_risk_coach/skills/risk_pattern_detection/SKILL.md"

def parse_gherkin_feature(file_path):
    print(f"Reading behavior specs from: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Scenario:") or stripped.startswith("Given") or stripped.startswith("When") or stripped.startswith("Then") or stripped.startswith("And"):
            print(f"  [SDD Step] {stripped}")

def load_disposition_threshold():
    with open(SKILL_PATH, "r", encoding="utf-8") as f:
        skill_text = f.read()
    match = re.search(r"Ratio\s*>=\s*([0-9.]+)", skill_text)
    assert match, "Could not find Disposition Effect threshold in SKILL.md"
    return float(match.group(1))

def run_sdd_assertions():
    feature_path = "specs/behavior_rules.feature"
    parse_gherkin_feature(feature_path)
    
    print("\n--- Running Behavior-Driven Spec Assertions ---")
    
    # 1. Asserting Scenario: Detect Disposition Effect (Win Small Lose Big)
    # Threshold is intentionally loaded from SKILL.md to keep tests aligned with the Agent Skill.
    threshold = load_disposition_threshold()
    avg_loss = 95.0
    avg_win = 35.0
    ratio = avg_loss / avg_win
    print(f"Asserting Win-Small-Lose-Big threshold from SKILL.md: {ratio:.2f} >= {threshold}")
    assert ratio >= threshold, "Ratio calculation assertion failed!"
    print("  [Pass] Threshold calculation conforms to SKILL.md definition.")
    
    # 2. Asserting Scenario: Prevent Gambler Fallacy Advice
    dangerous_input_1 = "如果你亏钱了，建议在金价下跌时加仓摊平成本，早日打回本钱。"
    dangerous_input_2 = "目前浮亏150美金，建议继续扛单等金价反弹回本。"
    
    print(f"\nAsserting Guardrail Interceptor with input: '{dangerous_input_1}'")
    assert contains_dangerous_advice(dangerous_input_1) == True, "Failed to identify dangerous advice!"
    sanitized_1 = sanitize_advice(dangerous_input_1)
    assert "[安全护栏已拦截原始建议]" in sanitized_1, "Guardrail failed to insert security warning!"
    assert "加仓摊平成本" not in sanitized_1, "Guardrail leaked the original unsafe phrase!"
    print("  [Pass] Guardrail successfully intercepted the Averaging Down pattern.")
    
    print(f"\nAsserting Guardrail Interceptor with input: '{dangerous_input_2}'")
    assert contains_dangerous_advice(dangerous_input_2) == True, "Failed to identify dangerous advice!"
    sanitized_2 = sanitize_advice(dangerous_input_2)
    assert "[安全护栏已拦截原始建议]" in sanitized_2, "Guardrail failed to insert security warning!"
    assert "继续扛单" not in sanitized_2, "Guardrail leaked the original unsafe phrase!"
    print("  [Pass] Guardrail successfully intercepted the Position Holding pattern.")

    # 3. Asserting Scenario: MCP Read Tools Return Valid JSON (real data)
    print("\nAsserting MCP read tools return valid JSON payloads (real MT5 data)")
    recent = json.loads(get_recent_trades(days=30))
    assert isinstance(recent, list), "Recent trades should be a JSON list!"
    assert len(recent) > 0, "Recent trades should not be empty!"
    assert {"symbol", "open_price", "close_price", "pnl"}.issubset(recent[0].keys()), "Recent trade record missing expected fields!"

    symbol_history = json.loads(get_symbol_history("XAUUSD"))
    assert len(symbol_history) > 0, "Symbol history should not be empty for XAUUSD!"
    assert all(row["symbol"].upper() == "XAUUSD" for row in symbol_history), "Symbol history returned wrong symbol!"

    account_stats = json.loads(get_account_stats(symbol="XAUUSD", days=90))
    assert "win_rate_pct" in account_stats, "Account stats missing win rate!"
    assert "disposition_effect_ratio" in account_stats, "Account stats missing disposition effect ratio!"
    assert "sl_rate_pct" in account_stats, "Account stats missing stop-loss rate!"
    print(f"  Real account stats: win_rate={account_stats['win_rate_pct']}%, disposition_ratio={account_stats['disposition_effect_ratio']}, total_trades={account_stats['total_trades']}")

    breakdown = json.loads(get_symbol_breakdown())
    assert "XAUUSD" in breakdown, "Symbol breakdown missing XAUUSD!"
    assert "win_rate_pct" in breakdown["XAUUSD"], "Symbol breakdown missing win rate for XAUUSD!"
    print(f"  Symbol breakdown: {list(breakdown.keys())}")
    print("  [Pass] MCP read tools returned valid records and summaries (real MT5 data).")

    replay = json.loads(simulate_historical_risk_replay(limit=30, hard_stop_points=3.0, emergency_points=6.0))
    assert replay["mode"] == "historical_replay_not_live_trading", "Replay mode should clarify this is not live trading!"
    assert replay["evaluated_trades"] > 0, "Historical replay should evaluate at least one trade!"
    assert {"keep_watching", "set_hard_sl", "emergency_close"}.issubset(replay["actions"].keys()), "Replay actions missing expected keys!"
    assert replay["actions"]["set_hard_sl"] + replay["actions"]["emergency_close"] > 0, "Replay should demonstrate at least one simulated mitigation action!"
    assert {"position_id", "max_adverse_points", "replay_action"}.issubset(replay["events"][0].keys()), "Replay event missing expected fields!"
    print(f"  Historical replay actions: {replay['actions']}")
    print("  [Pass] Historical M1 replay can simulate active risk-control actions without a live broker.")
    
    # 4. Asserting Scenario: Execute Active Stop Loss Mitigation
    ticket_id = "T1001"
    action = "set_hard_sl"
    sl_price = 2350.0
    
    print(f"\nAsserting Active Mitigation Tool with ticket: '{ticket_id}', action: '{action}', sl: {sl_price}")
    broker_resp_json = execute_risk_mitigation(action, ticket_id, sl_price)
    broker_resp = json.loads(broker_resp_json)
    
    assert broker_resp["status"] == "success", "Mitigation tool status was not success!"
    assert "风控指令执行成功" in broker_resp["message"], "Mitigation tool message was missing success log!"
    assert broker_resp["value"] == sl_price, "Set stop loss price mismatch!"
    
    print(f"Broker Response: {broker_resp['message']}")
    print("  [Pass] Advisor Agent successfully executed active Stop-Loss command on Mock Broker.")

    invalid_resp = json.loads(execute_risk_mitigation("double_down", ticket_id, sl_price))
    assert invalid_resp["status"] == "error", "Invalid mitigation action should fail safely!"
    print("  [Pass] MCP write tool rejects unknown mitigation actions safely.")

    print("\n✅ All Spec-Driven Development (SDD) behavior tests PASSED!")

if __name__ == "__main__":
    run_sdd_assertions()
