import re

import pytest

from ai_ha.privacy.hide_matcher import HideMatcher, PatternComplexityError


def test_empty_pattern_list_matches_nothing():
    m = HideMatcher([])
    assert m.matches("sensor.anything") is False


def test_exact_pattern_matches():
    m = HideMatcher([r"sensor\.bank_card_.*"])
    assert m.matches("sensor.bank_card_balance") is True
    assert m.matches("sensor.bank_card") is False
    assert m.matches("sensor.living_room_temp") is False


def test_multiple_patterns_or():
    m = HideMatcher([r"sensor\.bank_.*", r"person\.guest"])
    assert m.matches("sensor.bank_x") is True
    assert m.matches("person.guest") is True
    assert m.matches("light.x") is False


def test_invalid_regex_raises_at_construct():
    with pytest.raises(re.error):
        HideMatcher(["[unclosed"])


def test_catastrophic_backtracking_pattern_rejected():
    with pytest.raises(PatternComplexityError):
        HideMatcher([r"(a+)+b"])  # classic ReDoS
    with pytest.raises(PatternComplexityError):
        HideMatcher([r"(.*)*x"])
