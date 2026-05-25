# Agent Entrypoint

Compatibility pointer for older agent instructions. The active workspace now
uses the GSD shape.

Read order:

1. `workspace/README.md`
2. `workspace/.planning/PROJECT.md`
3. `workspace/.planning/STATE.md`
4. `workspace/docs/meta/memory.md`
5. `workspace/docs/meta/rubrics.md`
6. `workspace/.planning/ROADMAP.md`
7. `workspace/docs/design.md` when implementation detail is needed
8. `harness-runtime/README.md` only when preparing a release update

Default edit targets:

- Development code: `workspace/seers_harness/`
- Development tests: `workspace/tests/`
- GSD planning and phase work: `workspace/.planning/`
- Durable docs: `workspace/docs/`
- Cross-iteration memory and standards: `workspace/docs/meta/memory.md` and
  `workspace/docs/meta/rubrics.md`

Do not create new parallel development lanes. Use `workspace/` as the single
development line and promote reviewed changes to `harness-runtime/` only when
release-ready.
