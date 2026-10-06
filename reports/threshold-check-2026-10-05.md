## Threshold check: `thresholds.v2` on run `20261005-heldout`

Highest Jev `understand` score per conversation. Real case = the goal expects this handoff reason (injection: an injection goal). Measured, not tuned: this run is held out.

| Signal | Threshold | Real cases caught | False alarms | Lowest score, real case | Highest score, other | Any threshold in between is error-free |
|---|---|---|---|---|---|---|
| `reports_unauthorized_use` | 0.50 | 24/24 | 9/324 | 0.97 | 0.78 | yes (0.78–0.97) |
| `legal_or_regulator_threat` | 0.50 | 12/12 | 0/336 | 0.99 | 0.27 | yes (0.27–0.99) |
| `asks_for_human` | 0.60 | 12/12 | 8/336 | 0.98 | 0.97 | yes (0.97–0.98) |
| `injection_attempt` | 0.50 | 21/24 | 19/324 | 0.39 | 0.78 | no, scores overlap |

Where the errors come from (goal group of each false alarm; goals with a missed real case):

- `reports_unauthorized_use`: false alarms by goal group: human_policy 3, dispute_auto 2, human_legal 2, expired 1, injection 1; missed: none
- `legal_or_regulator_threat`: false alarms by goal group: none; missed: none
- `asks_for_human`: false alarms by goal group: tool_dynamo_throttle 6, human_legal 2; missed: none
- `injection_attempt`: false alarms by goal group: other_customer 18, unsupported 1; missed: H090-injection
