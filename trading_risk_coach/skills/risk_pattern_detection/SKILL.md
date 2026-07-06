# Skill Name: Risk Pattern Detection & Cognitive De-biasing
# Description: Quantitative rules for identifying Disposition Effect and executing three-value active risk mitigation.

## 📊 1. Quantitative Bias Thresholds
*   **Disposition Effect Index**:
    Ratio = (Average Loss Absolute Value) / (Average Win Value)
    *   **Rule**: If Ratio >= 1.5, trigger a **Disposition Effect Warning (Win-Small-Lose-Big Anti-Pattern)**.
*   **Position Sizing Risk Limit**:
    *   Single trade risk must not exceed **2.0% of total capital equity**.

---

## 🚦 2. Three-Value Risk Logic
To prevent flash crashes and reduce unnecessary transaction costs (slippage/spreads), the agent operates on three discrete risk assessment states instead of binary panic triggers:

| Risk Rating | Condition | Expected System Action |
| :--- | :--- | :--- |
| 🟢 **GREEN - SAFE** | All active trades have stop losses set; single-trade risk <= 1.0% of balance. | **Keep Watching**: Maintain current market observation. No orders needed. |
| 🟡 **YELLOW - WATCH** | Active trade missing stop loss, BUT market volatility (ATR) is currently low. | **Set Protective SL**: Call `execute_risk_mitigation` with `action_type='set_hard_sl'` to place a safe stop-loss. **Do not close the position** to save transaction costs. |
| 🔴 **RED - BREAKER** | Active trade missing stop-loss AND account drawdown > 5.0% OR market volatility spikes. | **Emergency Liquidation**: Call `execute_risk_mitigation` with `action_type='emergency_close'` to immediately exit positions and isolate the risk. |

---

## 🚫 3. Zero-Trust Security Callback Bounds
Any LLM recommendation matching patterns of "averaging down", "holding losses", or "doubling lots (Martingale)" must be intercepted and replaced with safety warnings before reaching the interface.
