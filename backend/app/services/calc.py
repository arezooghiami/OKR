"""Pure progress calculations (PRD section 3). No database access here."""

from dataclasses import dataclass
from enum import StrEnum


class KRKind(StrEnum):
    NUMERIC = "numeric"  # direction is derived from baseline vs target
    MILESTONE = "milestone"
    BOOLEAN = "boolean"
    MAINTAIN = "maintain"


class Status(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BEHIND = "behind"
    NOT_RECORDED = "not_recorded"


@dataclass(frozen=True)
class Definition:
    kind: KRKind
    baseline: float | None = None
    target: float | None = None
    range_min: float | None = None
    range_max: float | None = None


@dataclass(frozen=True)
class Thresholds:
    on_track: float = 70
    at_risk: float = 40


class InvalidDefinition(ValueError):
    pass


def validate_definition(d: Definition) -> None:
    if d.kind is KRKind.NUMERIC:
        if d.baseline is None or d.target is None:
            raise InvalidDefinition("مبنا و هدف الزامی است")
        if d.baseline == d.target:
            raise InvalidDefinition("مبنا و هدف نباید برابر باشند")
    elif d.kind is KRKind.MAINTAIN:
        if d.range_min is None or d.range_max is None or d.range_min > d.range_max:
            raise InvalidDefinition("بازه مجاز نامعتبر است")


def _clamp(x: float) -> float:
    return round(max(0.0, min(100.0, x)), 2)


def percent(d: Definition, value: float | None) -> float | None:
    """Progress 0..100, or None when no value was recorded (distinct from a real 0)."""
    if value is None:
        return None
    if d.kind is KRKind.NUMERIC:
        validate_definition(d)
        b, t = d.baseline, d.target
        assert b is not None and t is not None
        ratio = (value - b) / (t - b)  # works for both ascending and descending
        return _clamp(ratio * 100)
    if d.kind is KRKind.MILESTONE:
        return _clamp(value)
    if d.kind is KRKind.BOOLEAN:
        return 100.0 if value else 0.0
    if d.kind is KRKind.MAINTAIN:
        validate_definition(d)
        lo, hi = d.range_min, d.range_max
        assert lo is not None and hi is not None
        if lo <= value <= hi:
            return 100.0
        dist = lo - value if value < lo else value - hi
        width = (hi - lo) or max(abs(hi), 1.0)
        return _clamp(100 - dist / width * 100)
    raise InvalidDefinition(f"نوع نامعتبر: {d.kind}")


def status_for(p: float | None, th: Thresholds = Thresholds()) -> Status:
    if p is None:
        return Status.NOT_RECORDED
    if p >= th.on_track:
        return Status.ON_TRACK
    if p >= th.at_risk:
        return Status.AT_RISK
    return Status.BEHIND


def weighted_mean(items: list[tuple[float | None, float]]) -> float | None:
    """Mean of (percent, weight) pairs. Unrecorded KRs that exist count as 0;
    callers must leave out KRs that did not exist yet (PRD section 3, mid-cycle rule)."""
    if not items:
        return None
    total_w = sum(w for _, w in items)
    if total_w <= 0:
        return None
    return sum((p or 0.0) * w for p, w in items) / total_w
