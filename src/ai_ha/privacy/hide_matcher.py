"""Privacy hide-pattern matcher.

Compiles user-supplied regex list, rejects patterns with high catastrophic-backtracking
risk (nested quantifiers over groups). v0.1.0 uses a heuristic; v0.6+ may swap to re2.

Trade-off note: the ReDoS guard is intentionally conservative. It rejects any pattern
matching the form (X+)+ / (X*)* / (.*)* by structural heuristic, before attempting
to compile or run the pattern. This will produce false positives (some safe patterns
that happen to look structurally similar will also be rejected). The contract for
callers is: if you need a pattern the guard rejects, simplify it or wait for the
re2-backed v0.6+ implementation.
"""
from __future__ import annotations

import re


class PatternComplexityError(ValueError):
    """Pattern looks ReDoS-prone — reject before it can be matched."""


_REDOS_RE = re.compile(
    r"\([^)]*[+*][^)]*\)\s*[+*]"   # (X+)+ / (X*)* / (.X)*+ etc
    r"|"
    r"\(\.\*\)\s*[+*]"             # (.*)*
)


def _complexity_guard(pattern: str) -> None:
    if _REDOS_RE.search(pattern):
        raise PatternComplexityError(
            f"pattern {pattern!r} contains nested-quantifier construct "
            "(catastrophic backtracking risk); reject"
        )


class HideMatcher:
    def __init__(self, patterns: list[str]) -> None:
        self._compiled: list[re.Pattern[str]] = []
        for p in patterns:
            _complexity_guard(p)
            self._compiled.append(re.compile(p))

    def matches(self, entity_id: str) -> bool:
        return any(c.fullmatch(entity_id) for c in self._compiled)
