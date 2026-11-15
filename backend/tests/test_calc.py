import pytest

from app.services.calc import (
    Definition,
    InvalidDefinition,
    KRKind,
    Status,
    percent,
    status_for,
    weighted_mean,
)


def num(b, t):
    return Definition(KRKind.NUMERIC, baseline=b, target=t)


def test_ascending():
    assert percent(num(50, 70), 61) == pytest.approx(55)  # example from the KR detail screen


def test_descending():
    assert percent(num(48, 24), 36) == pytest.approx(50)


def test_clamped():
    assert percent(num(0, 10), 25) == 100
    assert percent(num(0, 10), -5) == 0
    assert percent(num(48, 24), 60) == 0


def test_negative_values_allowed():
    assert percent(num(-10, 10), 0) == pytest.approx(50)


def test_none_is_not_zero():
    assert percent(num(0, 10), None) is None
    assert percent(num(0, 10), 0) == 0


def test_equal_baseline_target_rejected():
    with pytest.raises(InvalidDefinition):
        percent(num(5, 5), 5)


def test_milestone_and_boolean():
    assert percent(Definition(KRKind.MILESTONE), 40) == 40
    assert percent(Definition(KRKind.MILESTONE), 140) == 100
    assert percent(Definition(KRKind.BOOLEAN), 1) == 100
    assert percent(Definition(KRKind.BOOLEAN), 0) == 0


def test_maintain():
    d = Definition(KRKind.MAINTAIN, range_min=90, range_max=100)
    assert percent(d, 95) == 100
    assert percent(d, 85) == pytest.approx(50)
    assert percent(d, 50) == 0


@pytest.mark.parametrize(
    "p,expected",
    [(None, Status.NOT_RECORDED), (70, Status.ON_TRACK), (69.9, Status.AT_RISK), (40, Status.AT_RISK), (39, Status.BEHIND)],
)
def test_status(p, expected):
    assert status_for(p) is expected


def test_weighted_mean():
    assert weighted_mean([(100, 1), (None, 1)]) == 50
    assert weighted_mean([(100, 3), (0, 1)]) == 75
    assert weighted_mean([]) is None
