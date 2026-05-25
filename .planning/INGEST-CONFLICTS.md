# Conflict Detection Report

## Result

- Blockers: 0
- Warnings: 0
- Informational notes: resolved into `intel/decisions.md`,
  `docs/memory.md`, and `docs/rubrics.md`

## Resolved Conflicts

| Topic | Resolution |
|---|---|
| Provider path | ADR-01-PRINCIPLE-09 wins: one `generate_with_tools` path. |
| Probe config | ADR-PROBE-7.1.1 supersedes ADR-PROBE-7.1: current config uses `deepseek-v4-pro` and `reasoning_effort="max"`. |
| Validation batch | ADR-RUNTIME-BATCH sets real validation to 20 requests. |
| BridgeLogic compatibility | C15 slots stay deleted; no compatibility baggage. |
| Handler vs rubric scope | Handlers enforce structural checks; rubric handles quality/domain judgment. |
| Chinese numeral regex | Allowed as structural number+measure detection, not a domain lexicon. |
| Old SKILL methodology | Keep/drop/defer mapping in `docs/methodology.md` is authoritative. |

## Rule For Future Conflicts

Prefer, in order:

1. Current `.planning/intel/decisions.md`
2. `docs/memory.md` and `docs/rubrics.md`
3. Current code/tests
4. `docs/history.md` provenance
