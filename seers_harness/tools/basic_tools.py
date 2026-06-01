"""Basic workspace tool handlers for generic harness tasks."""

from __future__ import annotations

import glob as globlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from seers_harness.core.errors import ToolValidationError


_DEFAULT_READ_LIMIT = 2000
_MAX_READ_LIMIT = 20000
_MAX_BASH_TIMEOUT_SECONDS = 120
_MAX_OUTPUT_CHARS = 20000
_MAX_GLOB_LIMIT = 2000
_MAX_GREP_LIMIT = 2000


class _ReadArgs(BaseModel):
    path: str
    offset: int = Field(default=1, ge=1)
    limit: int = Field(default=_DEFAULT_READ_LIMIT, ge=1, le=_MAX_READ_LIMIT)
    model_config = {"extra": "forbid"}


class _BashArgs(BaseModel):
    command: str
    timeout_seconds: int = Field(default=30, ge=1, le=_MAX_BASH_TIMEOUT_SECONDS)
    model_config = {"extra": "forbid"}


class _GlobArgs(BaseModel):
    pattern: str
    limit: int = Field(default=200, ge=1, le=_MAX_GLOB_LIMIT)
    model_config = {"extra": "forbid"}


class _GrepArgs(BaseModel):
    pattern: str
    path: str = "."
    include: str = "*"
    limit: int = Field(default=200, ge=1, le=_MAX_GREP_LIMIT)
    model_config = {"extra": "forbid"}


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _workspace_root(state: dict) -> Path:
    raw = state.get("workspace_root") or state.get("cwd") or os.getcwd()
    return Path(raw).expanduser().resolve()


def _resolve_workspace_path(path: str, state: dict, tool_name: str) -> Path:
    root = _workspace_root(state)
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ToolValidationError(
            message=f"path {path!r} resolves outside workspace root {str(root)!r}",
            tool_name=tool_name,
            arg_path="path",
        )
    return resolved


def _parse_args(model: type[BaseModel], args: dict, tool_name: str) -> BaseModel:
    try:
        return model.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(
            message=f"{tool_name} args invalid: {exc.errors()[:3]}",
            tool_name=tool_name,
        ) from exc


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text, False
    return text[:_MAX_OUTPUT_CHARS], True


def read(args: dict, state: dict) -> str:
    """Read a UTF-8 text file from the workspace with 1-based line numbers."""
    parsed = _parse_args(_ReadArgs, args, "read")
    assert isinstance(parsed, _ReadArgs)
    path = _resolve_workspace_path(parsed.path, state, "read")
    if not path.is_file():
        raise ToolValidationError(
            message=f"path {parsed.path!r} is not a file",
            tool_name="read",
            arg_path="path",
        )
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ToolValidationError(
            message=f"path {parsed.path!r} is not valid UTF-8 text",
            tool_name="read",
            arg_path="path",
        ) from exc
    start = parsed.offset
    end = min(len(lines), start + parsed.limit - 1)
    return "\n".join(f"{line_no}: {lines[line_no - 1]}" for line_no in range(start, end + 1))


def bash(args: dict, state: dict) -> str:
    """Run a shell command in the workspace and return stdout/stderr JSON."""
    parsed = _parse_args(_BashArgs, args, "bash")
    assert isinstance(parsed, _BashArgs)
    root = _workspace_root(state)
    if not parsed.command.strip():
        raise ToolValidationError(
            message="bash requires a non-empty command",
            tool_name="bash",
            arg_path="command",
        )
    try:
        completed = subprocess.run(
            parsed.command,
            cwd=root,
            shell=True,
            executable="/bin/bash",
            text=True,
            capture_output=True,
            timeout=parsed.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolValidationError(
            message=f"bash command timed out after {parsed.timeout_seconds}s",
            tool_name="bash",
            arg_path="timeout_seconds",
        ) from exc
    stdout, stdout_truncated = _truncate(completed.stdout)
    stderr, stderr_truncated = _truncate(completed.stderr)
    return _json(
        {
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    )


def glob(args: dict, state: dict) -> str:
    """Return relative workspace paths matching a glob pattern."""
    parsed = _parse_args(_GlobArgs, args, "glob")
    assert isinstance(parsed, _GlobArgs)
    if Path(parsed.pattern).is_absolute() or ".." in Path(parsed.pattern).parts:
        raise ToolValidationError(
            message="glob pattern must be relative and stay inside the workspace",
            tool_name="glob",
            arg_path="pattern",
        )
    root = _workspace_root(state)
    matches = sorted(
        str(path.relative_to(root)).replace(os.sep, "/")
        for path in (Path(p).resolve() for p in globlib.glob(str(root / parsed.pattern), recursive=True))
        if path == root or root in path.parents
    )
    return _json({"matches": matches[: parsed.limit], "truncated": len(matches) > parsed.limit})


def grep(args: dict, state: dict) -> str:
    """Search UTF-8 text files under a workspace path for a literal pattern."""
    parsed = _parse_args(_GrepArgs, args, "grep")
    assert isinstance(parsed, _GrepArgs)
    root = _workspace_root(state)
    search_root = _resolve_workspace_path(parsed.path, state, "grep")
    if not parsed.pattern:
        raise ToolValidationError(
            message="grep requires a non-empty pattern",
            tool_name="grep",
            arg_path="pattern",
        )
    files = [search_root] if search_root.is_file() else sorted(search_root.rglob(parsed.include))
    matches: list[dict[str, Any]] = []
    for file_path in files:
        if not file_path.is_file() or not file_path.match(parsed.include):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, text in enumerate(lines, start=1):
            if parsed.pattern in text:
                matches.append(
                    {
                        "path": str(file_path.relative_to(root)).replace(os.sep, "/"),
                        "line": line_no,
                        "text": text,
                    }
                )
                if len(matches) >= parsed.limit:
                    return _json({"matches": matches, "truncated": True})
    return _json({"matches": matches, "truncated": False})


def _strict_spec(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": list(properties),
                "properties": properties,
            },
        },
    }


BASH_SPEC = _strict_spec(
    "bash",
    "Run a shell command in the workspace and return exit code, stdout, and stderr.",
    {
        "command": {"type": "string"},
        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": _MAX_BASH_TIMEOUT_SECONDS},
    },
)

READ_SPEC = _strict_spec(
    "read",
    "Read a UTF-8 text file from the workspace with 1-based line numbers.",
    {
        "path": {"type": "string"},
        "offset": {"type": "integer", "minimum": 1},
        "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_READ_LIMIT},
    },
)

GLOB_SPEC = _strict_spec(
    "glob",
    "List relative workspace paths matching a glob pattern.",
    {
        "pattern": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_GLOB_LIMIT},
    },
)

GREP_SPEC = _strict_spec(
    "grep",
    "Search UTF-8 text files for a literal pattern.",
    {
        "pattern": {"type": "string"},
        "path": {"type": "string"},
        "include": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_GREP_LIMIT},
    },
)

BASIC_TOOLS_SPEC: list[dict[str, Any]] = [BASH_SPEC, READ_SPEC, GLOB_SPEC, GREP_SPEC]

BASIC_TOOL_HANDLERS: dict[str, Callable[[dict, dict], str]] = {
    "bash": bash,
    "read": read,
    "glob": glob,
    "grep": grep,
}


__all__ = [
    "BASIC_TOOL_HANDLERS",
    "BASIC_TOOLS_SPEC",
    "BASH_SPEC",
    "GLOB_SPEC",
    "GREP_SPEC",
    "READ_SPEC",
    "bash",
    "glob",
    "grep",
    "read",
]
