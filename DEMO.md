# End-to-End Demo

This demo shows how Trading Risk Coach handles one complete risk-review request.

## Demo Input

```text
Please review my recent XAUUSD trades. Tell me whether I am showing win-small-lose-big behavior, whether any active position needs risk mitigation, and produce a safe final risk report.
```

## Expected Execution Flow

1. The ADK runtime loads `root_agent` from `trading_risk_coach/agent.py`.
2. `analysis_agent` calls MCP read tools from `trade_data_server.py`.
3. The MCP server reads `trading_risk_coach/data/sample_trades.csv`.
4. `analysis_agent` computes metrics such as win rate, average win, average loss, loss/win ratio, and platform concentration.
5. `advisor_agent` loads `SKILL.md` and compares the metrics against the Disposition Effect threshold.
6. If a high-risk active order is identified, `advisor_agent` calls `execute_risk_mitigation`.
7. `safety_rules.py` sanitizes unsafe recovery-trading language.
8. `critic_agent` produces the final structured risk diagnosis.

## Tool Evidence

The MCP server exposes:

```text
get_recent_trades(days=7)
get_symbol_history(symbol="XAUUSD")
get_platform_summary(platform="ANZO")
execute_risk_mitigation(action_type="set_hard_sl", ticket_id="T1001", parameter=2350.0)
```

Example mitigation response:

```json
{
  "status": "success",
  "message": "风控指令执行成功：订单 T1001 已成功挂载硬止损，止损价格设置为 2350.0",
  "ticket_id": "T1001",
  "action": "SET_STOP_LOSS",
  "value": 2350.0
}
```

## Expected Final Report Shape

```markdown
# 黄金账户量化风控诊断意见书

## 账户当前风控评级：黄灯 - 警报观察

当前账户存在赢小亏大倾向。根据 SKILL.md，处置效应系数 = 平均亏损绝对值 / 平均盈利；当该数值 >= 1.5 时触发风险预警。

## 账户核心指标

- 胜率：由 analysis_agent 基于 MCP 返回交易记录计算
- 平均盈利：由盈利交易均值计算
- 平均亏损：由亏损交易均值计算
- 处置效应系数：平均亏损绝对值 / 平均盈利
- 集中度风险：按 symbol/platform 分布判断

## 主动风控指令执行记录

- 已调用 `execute_risk_mitigation`
- 动作：`set_hard_sl`
- 订单：`T1001`
- 结果：风控指令执行成功

## 行为去偏指导意见

1. 将止损前置为开仓前规则，而不是浮亏后再决定。
2. 当处置效应系数超过 1.5 时，暂停扩大风险暴露，优先复盘止损距离和单笔风险。
3. 禁止使用加仓摊平、扛单等待回本或马丁格尔加倍策略。
```

## Guardrail Demonstration

Unsafe model text:

```text
你亏损太严重了，应该加仓摊平成本以打回本钱。
```

Sanitized output:

```text
[安全护栏已拦截原始建议] 检测到该建议可能包含高风险的仓位管理逻辑（例如加仓摊平、扛单等）。系统不会输出此类建议。建议改为：复盘止损位设置是否合理、降低单笔风险敞口、或咨询持牌财务顾问。
```

## Local Verification

Run:

```bash
python test_sdd_specs.py
python test_runner.py
```

The first command verifies the business rules, MCP tool behavior, and guardrails. The second command verifies that the ADK workflow imports correctly and that the sanitizer works independently of a live LLM call.
