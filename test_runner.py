import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_risk_coach.agent import root_agent
from trading_risk_coach.config import API_KEY_SOURCE, has_local_api_key
from trading_risk_coach.agents.analysis_agent import analysis_agent
from trading_risk_coach.agents.advisor_agent import advisor_agent
from trading_risk_coach.agents.critic_agent import critic_agent
from trading_risk_coach.guardrails.safety_rules import sanitize_advice

print("ADK workflow loaded successfully!")
print(f"Workflow Name: {root_agent.name}")
print(
    "Local API Key:"
    f" {'configured via ' + API_KEY_SOURCE if has_local_api_key() else 'not configured'}"
)

edge_names = []
for source, target in root_agent.edges:
    source_name = source if isinstance(source, str) else source.name
    target_name = target if isinstance(target, str) else target.name
    edge_names.append(f"{source_name} -> {target_name}")

print("Workflow Edges:")
for edge_name in edge_names:
    print(f"  - {edge_name}")

print("Agent Models:")
for agent in [analysis_agent, advisor_agent, critic_agent]:
    print(f"  - {agent.name}: {agent.model}")

assert advisor_agent.after_model_callback is not None, "Advisor guardrail callback is not registered!"
assert critic_agent.after_model_callback is not None, "Critic guardrail callback is not registered!"
print("Guardrail Callbacks:")
print("  - advisor_agent: registered")
print("  - critic_agent: registered")

# Create a mock response to test the guardrail callback directly
class MockResponse:
    def __init__(self, text):
        self.text = text

async def test_guardrail():
    print("\n--- Testing Guardrail Callback ---")
    # Test safe advice
    safe_resp = MockResponse("建议设置 ATR 止损，并分散投资到不同品种。")
    print(f"Original Safe: {safe_resp.text}")
    sanitized_safe = sanitize_advice(safe_resp.text)
    print(f"Sanitized Safe: {sanitized_safe}")
    
    # Test dangerous advice
    danger_resp = MockResponse("你亏损太严重了，应该加仓摊平成本以打回本钱。")
    print(f"\nOriginal Danger: {danger_resp.text}")
    sanitized_danger = sanitize_advice(danger_resp.text)
    print(f"Sanitized Danger: {sanitized_danger}")
    
    if "[安全护栏已拦截原始建议]" in sanitized_danger:
        print("\n✅ Guardrail successfully intercepted and blocked the gambler's fallacy advice!")
    else:
        raise AssertionError("Guardrail failed to intercept the advice!")

if __name__ == "__main__":
    asyncio.run(test_guardrail())
