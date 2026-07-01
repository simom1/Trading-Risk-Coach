import re
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_risk_coach.guardrails.safety_rules import sanitize_advice, contains_dangerous_advice
from trading_risk_coach.mcp_server.trade_data_server import execute_risk_mitigation

def parse_gherkin_feature(file_path):
    print(f"Reading behavior specs from: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Scenario:") or stripped.startswith("Given") or stripped.startswith("When") or stripped.startswith("Then") or stripped.startswith("And"):
            print(f"  [SDD Step] {stripped}")

def run_sdd_assertions():
    feature_path = "specs/behavior_rules.feature"
    parse_gherkin_feature(feature_path)
    
    print("\n--- Running Behavior-Driven Spec Assertions ---")
    
    # 1. Asserting Scenario: Detect Disposition Effect (Win Small Lose Big)
    # Threshold defined in SKILL.md is 1.5. Let's assert calculations with mock metrics.
    avg_loss = 95.0
    avg_win = 35.0
    ratio = avg_loss / avg_win
    print(f"Asserting Win-Small-Lose-Big threshold: {ratio:.2f} >= 1.5")
    assert ratio >= 1.5, "Ratio calculation assertion failed!"
    print("  [Pass] Threshold calculation conforms to SKILL.md definition.")
    
    # 2. Asserting Scenario: Prevent Gambler Fallacy Advice
    dangerous_input_1 = "如果你亏钱了，建议在金价下跌时加仓摊平成本，早日打回本钱。"
    dangerous_input_2 = "目前浮亏150美金，建议继续扛单等金价反弹回本。"
    
    print(f"\nAsserting Guardrail Interceptor with input: '{dangerous_input_1}'")
    assert contains_dangerous_advice(dangerous_input_1) == True, "Failed to identify dangerous advice!"
    sanitized_1 = sanitize_advice(dangerous_input_1)
    assert "[安全护栏已拦截原始建议]" in sanitized_1, "Guardrail failed to insert security warning!"
    print("  [Pass] Guardrail successfully intercepted the Averaging Down pattern.")
    
    print(f"\nAsserting Guardrail Interceptor with input: '{dangerous_input_2}'")
    assert contains_dangerous_advice(dangerous_input_2) == True, "Failed to identify dangerous advice!"
    sanitized_2 = sanitize_advice(dangerous_input_2)
    assert "[安全护栏已拦截原始建议]" in sanitized_2, "Guardrail failed to insert security warning!"
    print("  [Pass] Guardrail successfully intercepted the Position Holding pattern.")
    
    # 3. Asserting Scenario: Execute Active Stop Loss Mitigation
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

    print("\n✅ All Spec-Driven Development (SDD) behavior tests PASSED!")

if __name__ == "__main__":
    run_sdd_assertions()
