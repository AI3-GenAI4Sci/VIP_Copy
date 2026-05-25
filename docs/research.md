# Research

## DeepSeek Tool-Use Probe

Date: 2026-05-25.

Result: DeepSeek `deepseek-v4-pro` at `/beta` supports strict tool calls with
thinking enabled and `reasoning_effort="max"`.

Locked runtime shape:

- `model = "deepseek-v4-pro"`
- `base_url = "https://api.deepseek.com/beta"`
- `reasoning_effort = "max"`
- `extra_body = {"thinking": {"type": "enabled"}}`
- `tool_choice = "auto"`
- no `temperature`

Cost signal from the probe:

| Effort | Input | Output | Reasoning |
|---|---:|---:|---:|
| max | 385 | 74 | 30 |
| high | 306 | 66 | 22 |

`max` stayed inside the accepted cost envelope for the batch-20 validation plan.

## Tool-Loop Note

Multi-turn DeepSeek tool conversations must echo prior `reasoning_content` back
in later requests. The current Phase 3 tool loop accounts for this behavior.
