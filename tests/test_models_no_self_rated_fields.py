"""DATA-06 schema-wide audit — no LLM self-rated metric fields anywhere.

Scans every BaseModel subclass declared in ``seers_harness.domain.models``
(excluding ``BaseModel`` itself). The forbidden field names are
``strength``, ``confidence``, ``uncertainty``, ``probability``, ``score``
per Principle 10. A single offending field anywhere fails this test.
"""

from __future__ import annotations

import inspect

from pydantic import BaseModel

from seers_harness.domain import models as _models

_FORBIDDEN_SELF_RATED = frozenset(
    {"strength", "confidence", "uncertainty", "probability", "score"}
)


def test_no_self_rated_fields_anywhere() -> None:
    offenders: list[tuple[str, set[str]]] = []
    for name, cls in inspect.getmembers(_models):
        if not inspect.isclass(cls):
            continue
        if cls is BaseModel:
            continue
        if not issubclass(cls, BaseModel):
            continue
        # Some BaseModel subclasses might be re-exported from pydantic; skip those.
        if cls.__module__ != _models.__name__:
            continue
        bad = set(cls.model_fields) & _FORBIDDEN_SELF_RATED
        if bad:
            offenders.append((name, bad))
    assert not offenders, (
        "models declare LLM self-rated metric fields (forbidden by Principle 10): "
        f"{offenders}"
    )
