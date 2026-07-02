Feature: Trading Risk Coach Behavior Specs
  As a quantitative trader
  I want to receive behavioral de-biasing coaching and strict risk assessments
  So that I can fix my reward-to-risk structure without gambling advice

  Scenario: Detect Disposition Effect (Win Small Lose Big)
    Given a trade database with 45% win rate and average loss of 95 and average win of 35
    When the analysis agent processes the trades
    Then the ratio of average loss to average win should be greater than 1.5
    And the advisor agent must flag "Win-Small-Lose-Big" pattern presence

  Scenario: Prevent Gambler Fallacy Advice
    Given an LLM generated suggestion containing "加仓摊平成本" or "扛单"
    When the safety guardrail callback intercepts the output
    Then the response text must be sanitized to remove the dangerous advice
    And it must output the security warning "[安全护栏已拦截原始建议]"

  Scenario: Execute Active Stop Loss Mitigation
    Given an active trade with ticket "T1001" missing stop loss
    When the advisor agent executes "set_hard_sl" mitigation action with parameter 2350.0
    Then the mock broker response status should be "success"
    And it should log "风控指令执行成功"

  Scenario: Validate MCP Read Tools
    Given the sample trade database contains XAUUSD records
    When the MCP server returns recent trades, symbol history, and platform summary JSON
    Then the payloads should contain valid records and quantitative summary fields

  Scenario: Reject Unknown Risk Mitigation Action
    Given an invalid mitigation action "double_down"
    When the MCP server receives the action
    Then the response status should be "error"
