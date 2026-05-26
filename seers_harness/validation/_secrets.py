"""Redacted exception rendering — Phase 7 plan 07-04 (CR-03).

The runner and evolution_snapshot writers persist exception class name
+ message into ``index.json`` / ``evolution_snapshot.json`` as the
canonical failure scene. Some provider SDKs surface request headers or
body excerpts in the exception message — including ``Authorization``
headers carrying ``Bearer sk-...`` tokens. ``evidence_writer``
output is git-ignored, but git-ignored does not mean "safe to share";
the directory still gets synced, screenshot-shared, or zipped.

``_safe_exc(exc)`` is the single chokepoint that:

* renders the exception as ``"<ClassName>: <message>"``;
* substitutes any ``sk-...`` / ``Bearer ...`` / ``Authorization: ...``
  / ``api_key=...`` token with ``<redacted>``;
* caps the result at 512 characters so a runaway stack-text payload
  cannot inflate ``index.json``.

The pattern set is conservative — narrow enough that a legitimate
user-facing error string is not mangled, broad enough to cover the
common OpenAI / DeepSeek SDK shapes. Add new patterns here when a
future incident proves another shape needs redaction.
"""

from __future__ import annotations

import re

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]+"
    r"|Bearer\s+\S+"
    r"|Authorization\s*[:=]\s*\S+"
    r"|api[_-]?key\s*[:=]\s*\S+)",
    re.IGNORECASE,
)

_MAX_LEN = 512


def _safe_message(message: str) -> str:
    """Redact secrets from ``message`` and cap to ``_MAX_LEN`` chars."""
    redacted = _SECRET_RE.sub("<redacted>", message)
    if len(redacted) > _MAX_LEN:
        return redacted[:_MAX_LEN] + "…"
    return redacted


def safe_exc(exc: BaseException) -> str:
    """Render ``exc`` as ``"<ClassName>: <redacted message>"``."""
    return _safe_message(f"{type(exc).__name__}: {exc}")


def safe_exc_message(exc: BaseException) -> str:
    """Render ``exc`` message ONLY (no class prefix), redacted + capped.

    Use this when the caller separately records the exception class
    (e.g. ``trial_failed`` events store ``exception_class`` distinct
    from ``exception_message``).
    """
    return _safe_message(str(exc))
