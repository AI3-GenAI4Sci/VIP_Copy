# SEERS Harness Workspace

This is the development version of SEERS Harness v3.

`harness-runtime/` is the publishable runtime. Work here first, prove the change
with tests and GSD phase artifacts, then promote reviewed code into runtime.

## Daily Entry

1. Read `.planning/PROJECT.md`.
2. Read `.planning/STATE.md`.
3. Read `docs/meta/memory.md` and `docs/meta/rubrics.md`.
4. Continue with the next GSD phase or plan under `.planning/phases/`.
5. Edit `seers_harness/`, `tests/`, and future workflow assets directly in this
   workspace.

## Layout

```text
workspace/
├── .planning/       # GSD project, requirements, roadmap, state, phase plans
├── .scratch/        # local PRDs, issue drafts, and temporary planning notes
├── docs/            # flat durable design, history, methodology, research notes
├── docs/meta/       # compact cross-iteration memory and operating rubrics
├── seers_harness/   # development package
├── tests/           # development tests
└── pyproject.toml   # install/test configuration
```

## Rules

- Keep one development line in `workspace/`; do not create parallel development
  lanes.
- Keep historical context distilled in `docs/`, not scattered across live code.
- Keep generated caches, local virtualenvs, private traces, and one-off run
  output out of the active workspace.
- Treat `docs/history.md` as history only.
