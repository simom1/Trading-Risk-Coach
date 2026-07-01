import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_risk_coach.agent import root_agent
from google.adk.models import LlmResponse
from google.adk.agents.callback_context import CallbackContext
from trading_risk_coach.guardrails.safety_rules import sanitize_advice

print("ADK workflow loaded successfully!")
print(f"Workflow Name: {root_agent.name}")
print(f"Edges: {root_agent.edges}")

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
        print("\n❌ Guardrail failed to intercept the advice!")

if __name__ == "__main__":
    asyncio.run(test_guardrail())
