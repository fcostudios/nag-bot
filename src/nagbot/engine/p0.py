"""P0 detection — the configurable, safe rule evaluator (spine AD-5/AD-6).

The P0 rule is OR-of-AND groups of `P0Condition`s over GLPI `Ticket` fields.
A ticket is a P0 if ANY group matches (all conditions in that group true).
The evaluator is pure (no I/O, no `now`) so E7-S3/S4 reuse it verbatim as the
"verification gate", and it NEVER raises — a malformed rule degrades to no-match,
it must not crash the escalation loop.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nagbot.config import P0Condition
    from nagbot.glpi.models import Ticket

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

_MISSING = object()


def _condition_matches(cond: P0Condition, ticket: Ticket) -> bool:
    actual = getattr(ticket, cond.field, _MISSING)
    if actual is _MISSING:
        return False  # unknown field → never a match (never raise)
    if cond.op == "in":
        values = cond.value if isinstance(cond.value, list) else [cond.value]
        return actual in values
    fn = _OPS.get(cond.op)
    if fn is None:
        return False
    try:
        return bool(fn(actual, cond.value))
    except TypeError:
        return False  # e.g. ">=" between a str and an int


def is_p0(ticket: Ticket, rule: list[list[P0Condition]]) -> bool:
    """True iff any group matches (OR) and all conditions in it match (AND)."""
    return any(
        isinstance(group, list) and group and all(_condition_matches(c, ticket) for c in group)
        for group in rule
    )


def detect_p0s(tickets: list[Ticket], rule: list[list[P0Condition]]) -> list[Ticket]:
    return [t for t in tickets if is_p0(t, rule)]
