"""Unit tests for the DieType polyhedral dice engine."""

import pytest
from swchar.core.dice import DieType


def test_die_type_values():
    """Verify that DieType members have exact SWADE integer values."""
    assert DieType.D4.value == 4
    assert DieType.D6.value == 6
    assert DieType.D8.value == 8
    assert DieType.D10.value == 10
    assert DieType.D12.value == 12
    assert DieType.D12_PLUS.value == 14


def test_die_type_comparison():
    """Verify that DieType enums are strictly ordered by their die scale."""
    assert DieType.D4 < DieType.D6
    assert DieType.D6 < DieType.D8
    assert DieType.D8 < DieType.D10
    assert DieType.D10 < DieType.D12
    assert DieType.D12 < DieType.D12_PLUS


def test_die_type_next_die_progression():
    """Verify next_die() steps up through the polyhedral scale."""
    assert DieType.D4.next_die() == DieType.D6
    assert DieType.D6.next_die() == DieType.D8
    assert DieType.D8.next_die() == DieType.D10
    assert DieType.D10.next_die() == DieType.D12
    assert DieType.D12.next_die() == DieType.D12_PLUS


def test_die_type_next_die_beyond_maximum():
    """Verify next_die() on maximum stepped die raises ValueError."""
    with pytest.raises(ValueError):
        DieType.D12_PLUS.next_die()


def test_die_type_prev_die_progression():
    """Verify prev_die() steps down through the polyhedral scale."""
    assert DieType.D12_PLUS.prev_die() == DieType.D12
    assert DieType.D12.prev_die() == DieType.D10
    assert DieType.D10.prev_die() == DieType.D8
    assert DieType.D8.prev_die() == DieType.D6
    assert DieType.D6.prev_die() == DieType.D4


def test_die_type_prev_die_below_minimum():
    """Verify prev_die() on minimum die (d4) raises ValueError."""
    with pytest.raises(ValueError):
        DieType.D4.prev_die()


def test_die_type_string_formatting():
    """Verify string representations match standard RPG dice notations."""
    assert str(DieType.D4) == "d4"
    assert str(DieType.D6) == "d6"
    assert str(DieType.D8) == "d8"
    assert str(DieType.D10) == "d10"
    assert str(DieType.D12) == "d12"
    assert str(DieType.D12_PLUS) in ("d12+", "d12_plus")


def test_die_type_from_string():
    """Verify parsing valid string representations into DieType."""
    assert DieType.from_string("d4") == DieType.D4
    assert DieType.from_string("D6") == DieType.D6
    assert DieType.from_string("d8") == DieType.D8
    assert DieType.from_string("D10") == DieType.D10
    assert DieType.from_string("d12") == DieType.D12
    assert DieType.from_string("d12+") == DieType.D12_PLUS
    assert DieType.from_string("d12_plus") == DieType.D12_PLUS


def test_die_type_from_string_invalid():
    """Verify invalid dice notation raises ValueError."""
    with pytest.raises(ValueError):
        DieType.from_string("d20")
    with pytest.raises(ValueError):
        DieType.from_string("d2")
    with pytest.raises(ValueError):
        DieType.from_string("invalid")


def test_die_type_from_int():
    """Verify DieType construction from integer value."""
    assert DieType(4) == DieType.D4
    assert DieType(6) == DieType.D6
    assert DieType(8) == DieType.D8
    assert DieType(10) == DieType.D10
    assert DieType(12) == DieType.D12
    assert DieType(14) == DieType.D12_PLUS


def test_die_type_from_int_invalid():
    """Verify non-standard integer values raise ValueError."""
    with pytest.raises(ValueError):
        DieType(5)
    with pytest.raises(ValueError):
        DieType(16)
