# Intel Requirements Map

This file records where the compact requirements came from. The actionable
requirement table is `.planning/REQUIREMENTS.md`.

## Source Mapping

| Requirement group | Source decision/spec | Current phase |
|---|---|---|
| DATA | Schema rewrite decisions, ADR-03 methodology mapping | Phase 1 complete |
| TOOL | Tool hand/mirror contract, handler structural checks | Phase 1 complete |
| PROV | One provider path, DeepSeek `/beta` tool/thinking probe | Phase 2 complete |
| LOOP | Tool loop, error routing, DAG integration | Phase 3 complete |
| SKILL | Matt-style SKILL rewrite, keep/drop/defer table | Phase 4 pending |
| CLEAN/TEST/REGRESS | Retired path cleanup and bypass-module sweep | Phase 5 pending |
| EVO/PROD/TERM/PROMOTE | Evolution alignment and production hardening | Phase 6 pending |
| VAL | Real-provider validation at batch 20 | Phase 7 pending |

## Precedence Notes

- ADR-PROBE-7.1.1 supersedes the earlier `high` probe. Current provider setting
  is `deepseek-v4-pro` with `reasoning_effort="max"`.
- ADR-03 decides which old skill methods are kept, dropped, moved to handlers, or
  represented by reflection tools.
- Phase summaries are evidence; `.planning/REQUIREMENTS.md` is the live status
  table.
