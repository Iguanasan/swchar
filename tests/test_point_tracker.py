"""Unit tests for Slice 2: Point-Buy Economy & Hindrance Accounting.

Directly verifies acceptance criteria defined in docs/feature-slices.md:
- Attribute points tracking:
  - Base starting: 5 points (BASE_ATTRIBUTE_POINTS).
  - Each step above d4 (or above ancestral base) costs 1 point.
  - Cap validation (d12 maximum, d12+ for ancestries with starting d6).
  - Minimum attribute validation (cannot be below d4, or below ancestral base).
  - Overspending and underspending detection.
- Skill points tracking:
  - Base allotment: 12 skill points (BASE_SKILL_POINTS).
  - 5 core skills (Athletics, Common Knowledge, Notice, Persuasion, Stealth) start at d4 at 0 cost.
  - Non-core skills start untrained at 0 cost.
  - Purchasing d4 in non-core skill costs 1 point.
  - Advancing up to linked attribute costs 1 point per die step.
  - Advancing beyond linked attribute costs 2 points per die step.
  - Skill cap validation (cannot exceed d12 at creation).
  - Overspending and underspending detection.
- Hindrance economy:
  - Hindrance model: Minor = 1 point, Major = 2 points.
  - Maximum mechanical benefit is capped at 4 points (MAX_HINDRANCE_POINTS).
  - Redemption tracking:
    - 2 hindrance points -> +1 attribute point OR +1 Novice Edge.
    - 1 hindrance point -> +1 skill point OR +$500 starting cash.
  - Validation of redemption balances, remaining unspent points, and invalid claims.
- Integrated character build validation (validate_build).
"""

import pytest
from swchar.core.constants import (
    BASE_ATTRIBUTE_POINTS,
    BASE_SKILL_POINTS,
    MAX_HINDRANCE_POINTS,
    STARTING_CASH,
)
from swchar.core.dice import DieType
from swchar.models.ancestry import get_ancestry
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.character import Character
from swchar.models.hindrances import Hindrance, HindranceSeverity
from swchar.models.skills import Skill
from swchar.rules.point_tracker import PointTracker, HindranceEconomy


# ==============================================================================
# Attribute Points Tracking Tests
# ==============================================================================

class TestAttributePointTracking:
    """Tests for attribute point calculation, budgets, caps, and validation."""

    def test_attribute_points_spent_baseline(self, sample_human_character):
        """Verify baseline character with all d4 attributes has spent 0 attribute points."""
        assert PointTracker.get_attribute_points_spent(sample_human_character) == 0

    def test_attribute_points_available_baseline(self, sample_human_character):
        """Verify baseline character has 5 attribute points available."""
        assert PointTracker.get_attribute_points_available(sample_human_character) == BASE_ATTRIBUTE_POINTS
        assert PointTracker.get_attribute_points_available(sample_human_character) == 5

    def test_attribute_points_remaining_baseline(self, sample_human_character):
        """Verify baseline character with 0 spent has 5 points remaining."""
        assert PointTracker.get_attribute_points_remaining(sample_human_character) == 5

    def test_attribute_points_cost_per_step(self, sample_human_character):
        """Verify each die step above d4 costs exactly 1 attribute point."""
        char = sample_human_character

        # d4 -> 0 points
        char.attributes.agility = DieType.D4
        assert PointTracker.get_attribute_points_spent(char) == 0

        # d6 -> 1 point
        char.attributes.agility = DieType.D6
        assert PointTracker.get_attribute_points_spent(char) == 1
        assert PointTracker.get_attribute_points_remaining(char) == 4

        # d8 -> 2 points
        char.attributes.agility = DieType.D8
        assert PointTracker.get_attribute_points_spent(char) == 2
        assert PointTracker.get_attribute_points_remaining(char) == 3

        # d10 -> 3 points
        char.attributes.agility = DieType.D10
        assert PointTracker.get_attribute_points_spent(char) == 3
        assert PointTracker.get_attribute_points_remaining(char) == 2

        # d12 -> 4 points
        char.attributes.agility = DieType.D12
        assert PointTracker.get_attribute_points_spent(char) == 4
        assert PointTracker.get_attribute_points_remaining(char) == 1

    def test_attribute_points_multi_attribute_spending(self, sample_human_character):
        """Verify multi-attribute allocation summing to exactly 5 points."""
        char = sample_human_character
        # Agility d8 (2), Smarts d6 (1), Spirit d6 (1), Strength d6 (1), Vigor d4 (0) = 5
        char.attributes.agility = DieType.D8
        char.attributes.smarts = DieType.D6
        char.attributes.spirit = DieType.D6
        char.attributes.strength = DieType.D6
        char.attributes.vigor = DieType.D4

        assert PointTracker.get_attribute_points_spent(char) == 5
        assert PointTracker.get_attribute_points_remaining(char) == 0
        errors = PointTracker.validate_attributes(char)
        assert len(errors) == 0

    def test_attribute_points_ancestral_bonus_dwarf(self, sample_dwarf_character):
        """Verify Dwarf starting Vigor d6 costs 0 attribute points, and higher steps scale from d6."""
        char = sample_dwarf_character
        # Dwarf starts with Vigor at d6 for free (0 pts spent)
        assert char.attributes.vigor == DieType.D6
        assert PointTracker.get_attribute_points_spent(char) == 0

        # Advancing Vigor to d8 costs 1 point
        char.attributes.vigor = DieType.D8
        assert PointTracker.get_attribute_points_spent(char) == 1

        # Advancing Vigor to d10 costs 2 points
        char.attributes.vigor = DieType.D10
        assert PointTracker.get_attribute_points_spent(char) == 2

        # Advancing Vigor to d12 costs 3 points
        char.attributes.vigor = DieType.D12
        assert PointTracker.get_attribute_points_spent(char) == 3

        # Advancing Vigor to d12+ costs 4 points
        char.attributes.vigor = DieType.D12_PLUS
        assert PointTracker.get_attribute_points_spent(char) == 4

    def test_attribute_points_ancestral_bonus_elf(self, sample_elf_character):
        """Verify Elf starting Agility d6 costs 0 attribute points."""
        char = sample_elf_character
        assert char.attributes.agility == DieType.D6
        assert PointTracker.get_attribute_points_spent(char) == 0

        char.attributes.agility = DieType.D8
        assert PointTracker.get_attribute_points_spent(char) == 1

    def test_attribute_points_ancestral_bonus_half_folk(self, sample_half_folk_character):
        """Verify Half-Folk starting Spirit d6 costs 0 attribute points."""
        char = sample_half_folk_character
        assert char.attributes.spirit == DieType.D6
        assert PointTracker.get_attribute_points_spent(char) == 0

        char.attributes.spirit = DieType.D8
        assert PointTracker.get_attribute_points_spent(char) == 1

    def test_attribute_points_ancestral_bonus_rakashan(self, sample_rakashan_character):
        """Verify Rakashan starting Agility d6 costs 0 attribute points."""
        char = sample_rakashan_character
        assert char.attributes.agility == DieType.D6
        assert PointTracker.get_attribute_points_spent(char) == 0

        char.attributes.agility = DieType.D8
        assert PointTracker.get_attribute_points_spent(char) == 1

    def test_attribute_cap_standard_ancestry_d12(self, sample_human_character):
        """Verify standard ancestries have a cap of d12 and exceed errors are reported."""
        char = sample_human_character
        char.attributes.agility = DieType.D12_PLUS

        errors = PointTracker.validate_attributes(char)
        assert any("cap" in e.lower() or "d12" in e.lower() or "exceed" in e.lower() for e in errors)

    def test_attribute_cap_boosted_ancestry_d12_plus(self, sample_dwarf_character):
        """Verify Dwarf Vigor can reach d12+ legally, but other Dwarf attributes cap at d12."""
        char = sample_dwarf_character
        # Dwarf Vigor capped at d12+ (valid)
        char.attributes.vigor = DieType.D12_PLUS
        errors = PointTracker.validate_attributes(char)
        vigor_cap_errors = [e for e in errors if "vigor" in e.lower() and "cap" in e.lower()]
        assert len(vigor_cap_errors) == 0

        # Dwarf Agility still capped at d12 (d12+ is invalid)
        char.attributes.agility = DieType.D12_PLUS
        errors = PointTracker.validate_attributes(char)
        agility_cap_errors = [e for e in errors if "agility" in e.lower()]
        assert len(agility_cap_errors) > 0

    def test_attribute_cannot_be_below_ancestral_minimum(self, sample_dwarf_character):
        """Verify Dwarf Vigor cannot be reduced below starting d6."""
        char = sample_dwarf_character
        char.attributes.vigor = DieType.D4
        errors = PointTracker.validate_attributes(char)
        assert any("minimum" in e.lower() or "d6" in e.lower() or "vigor" in e.lower() for e in errors)

    def test_attribute_overspending_detected(self, sample_human_character):
        """Verify spending 6 attribute points with 5 available is flagged as overspent."""
        char = sample_human_character
        # Agility d10 (3), Smarts d8 (2), Spirit d6 (1) = 6 points spent
        char.attributes.agility = DieType.D10
        char.attributes.smarts = DieType.D8
        char.attributes.spirit = DieType.D6

        assert PointTracker.get_attribute_points_spent(char) == 6
        assert PointTracker.get_attribute_points_remaining(char) == -1
        errors = PointTracker.validate_attributes(char)
        assert any("overspent" in e.lower() or "exceed" in e.lower() or "budget" in e.lower() for e in errors)

    def test_attribute_underspending_detected(self, sample_human_character):
        """Verify spending 4 attribute points with 5 available is flagged as unspent/incomplete."""
        char = sample_human_character
        # Agility d8 (2), Smarts d6 (1), Spirit d6 (1) = 4 points spent
        char.attributes.agility = DieType.D8
        char.attributes.smarts = DieType.D6
        char.attributes.spirit = DieType.D6

        assert PointTracker.get_attribute_points_spent(char) == 4
        assert PointTracker.get_attribute_points_remaining(char) == 1
        errors = PointTracker.validate_attributes(char)
        assert any("unspent" in e.lower() or "remaining" in e.lower() or "points" in e.lower() for e in errors)


# ==============================================================================
# Skill Points Tracking Tests
# ==============================================================================

class TestSkillPointTracking:
    """Tests for skill point calculations, linked attributes, core skills, and budgets."""

    def test_skill_points_baseline_core_skills_free(self, sample_human_character):
        """Verify 5 core skills at d4 cost 0 skill points."""
        assert PointTracker.get_skill_points_spent(sample_human_character) == 0

    def test_skill_points_available_baseline(self, sample_human_character):
        """Verify baseline character has 12 skill points available."""
        assert PointTracker.get_skill_points_available(sample_human_character) == BASE_SKILL_POINTS
        assert PointTracker.get_skill_points_available(sample_human_character) == 12

    def test_skill_points_remaining_baseline(self, sample_human_character):
        """Verify baseline character with 0 spent has 12 skill points remaining."""
        assert PointTracker.get_skill_points_remaining(sample_human_character) == 12

    def test_skill_points_advance_core_up_to_linked_attribute(self, sample_human_character):
        """Verify advancing a core skill up to its linked attribute costs 1 point per die step."""
        char = sample_human_character
        char.attributes.smarts = DieType.D8  # Linked attribute for Notice is Smarts

        # Notice starts at d4 (0 pts)
        notice = char.get_skill("Notice")
        assert notice is not None
        assert notice.die == DieType.D4
        assert PointTracker.get_skill_points_spent(char) == 0

        # Advance Notice to d6 (at or below Smarts d8) -> 1 point
        char.set_skill("Notice", DieType.D6)
        assert PointTracker.get_skill_points_spent(char) == 1
        assert PointTracker.get_skill_points_remaining(char) == 11

        # Advance Notice to d8 (at Smarts d8) -> 2 points
        char.set_skill("Notice", DieType.D8)
        assert PointTracker.get_skill_points_spent(char) == 2
        assert PointTracker.get_skill_points_remaining(char) == 10

    def test_skill_points_advance_core_beyond_linked_attribute(self, sample_human_character):
        """Verify advancing a core skill beyond its linked attribute costs 2 points per die step."""
        char = sample_human_character
        char.attributes.smarts = DieType.D4  # Linked attribute for Notice is d4

        # Advancing Notice from d4 to d6 when Smarts is d4:
        # Step above linked attribute costs 2 points!
        char.set_skill("Notice", DieType.D6)
        assert PointTracker.get_skill_points_spent(char) == 2

        # Advancing Notice from d6 to d8 when Smarts is d4:
        # Another step above linked attribute costs +2 points (total 4 points)!
        char.set_skill("Notice", DieType.D8)
        assert PointTracker.get_skill_points_spent(char) == 4

    def test_skill_points_advance_core_partially_above_linked_attribute(self, sample_human_character):
        """Verify advancing core skill up to linked attribute (1 pt/step) and beyond (2 pts/step)."""
        char = sample_human_character
        char.attributes.spirit = DieType.D6  # Linked attribute for Persuasion is Spirit (d6)

        # Persuasion at d6 -> 1 point (up to Spirit d6)
        char.set_skill("Persuasion", DieType.D6)
        assert PointTracker.get_skill_points_spent(char) == 1

        # Persuasion at d8 -> 1 + 2 = 3 points (1 step above Spirit d6)
        char.set_skill("Persuasion", DieType.D8)
        assert PointTracker.get_skill_points_spent(char) == 3

        # Persuasion at d10 -> 1 + 2 + 2 = 5 points (2 steps above Spirit d6)
        char.set_skill("Persuasion", DieType.D10)
        assert PointTracker.get_skill_points_spent(char) == 5

    def test_skill_points_non_core_start_untrained(self, sample_human_character):
        """Verify non-core skills not taken have 0 cost."""
        assert PointTracker.get_skill_points_spent(sample_human_character) == 0

    def test_skill_points_non_core_purchase_at_d4(self, sample_human_character):
        """Verify purchasing a non-core skill at d4 costs 1 point (linked attr >= d4)."""
        char = sample_human_character
        char.attributes.agility = DieType.D6
        char.set_skill("Fighting", DieType.D4, AttributeName.AGILITY)

        assert PointTracker.get_skill_points_spent(char) == 1
        assert PointTracker.get_skill_points_remaining(char) == 11

    def test_skill_points_non_core_advance_up_to_linked_attribute(self, sample_human_character):
        """Verify purchasing and advancing non-core skill up to linked attribute."""
        char = sample_human_character
        char.attributes.agility = DieType.D8

        # d4 costs 1 pt
        char.set_skill("Fighting", DieType.D4, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 1

        # d6 costs 1(d4) + 1(d6) = 2 pts
        char.set_skill("Fighting", DieType.D6, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 2

        # d8 costs 1(d4) + 1(d6) + 1(d8) = 3 pts
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 3

    def test_skill_points_non_core_advance_beyond_linked_attribute(self, sample_human_character):
        """Verify advancing non-core skill beyond linked attribute costs 2 pts per die step."""
        char = sample_human_character
        char.attributes.agility = DieType.D6

        # Fighting at d6 (up to Agility d6) = 2 pts
        char.set_skill("Fighting", DieType.D6, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 2

        # Fighting at d8 (1 step beyond Agility d6) = 2 + 2 = 4 pts
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 4

        # Fighting at d10 (2 steps beyond Agility d6) = 4 + 2 = 6 pts
        char.set_skill("Fighting", DieType.D10, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 6

        # Fighting at d12 (3 steps beyond Agility d6) = 6 + 2 = 8 pts
        char.set_skill("Fighting", DieType.D12, AttributeName.AGILITY)
        assert PointTracker.get_skill_points_spent(char) == 8

    def test_skill_points_exact_budget_allocation(self, sample_human_character):
        """Verify valid character spending exactly 12 skill points."""
        char = sample_human_character
        char.attributes.agility = DieType.D8
        char.attributes.smarts = DieType.D6
        char.attributes.spirit = DieType.D6
        char.attributes.strength = DieType.D6
        char.attributes.vigor = DieType.D6

        # Core skills:
        # Athletics d6 (Agility d8) -> 1 pt
        char.set_skill("Athletics", DieType.D6)
        # Common Knowledge d4 (Smarts d6) -> 0 pt
        char.set_skill("Common Knowledge", DieType.D4)
        # Notice d6 (Smarts d6) -> 1 pt
        char.set_skill("Notice", DieType.D6)
        # Persuasion d6 (Spirit d6) -> 1 pt
        char.set_skill("Persuasion", DieType.D6)
        # Stealth d6 (Agility d8) -> 1 pt
        char.set_skill("Stealth", DieType.D6)

        # Non-core skills:
        # Fighting d8 (Agility d8) -> 3 pts (d4=1, d6=2, d8=3)
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        # Shooting d8 (Agility d8) -> 3 pts (d4=1, d6=2, d8=3)
        char.set_skill("Shooting", DieType.D8, AttributeName.AGILITY)
        # Healing d6 (Smarts d6) -> 2 pts (d4=1, d6=2)
        char.set_skill("Healing", DieType.D6, AttributeName.SMARTS)

        # Total = 1 + 0 + 1 + 1 + 1 + 3 + 3 + 2 = 12 points
        assert PointTracker.get_skill_points_spent(char) == 12
        assert PointTracker.get_skill_points_remaining(char) == 0
        errors = PointTracker.validate_skills(char)
        assert len(errors) == 0

    def test_skill_points_overspending_detected(self, sample_human_character):
        """Verify spending 13 skill points with 12 available is flagged as overspent."""
        char = sample_human_character
        char.attributes.agility = DieType.D8
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)  # 3 pts
        char.set_skill("Shooting", DieType.D8, AttributeName.AGILITY)  # 3 pts
        char.set_skill("Athletics", DieType.D8)  # 2 pts
        char.set_skill("Stealth", DieType.D8)  # 2 pts
        char.set_skill("Notice", DieType.D6)  # 2 pts (Smarts is d4)
        char.set_skill("Healing", DieType.D4, AttributeName.SMARTS)  # 1 pt
        # Total = 3 + 3 + 2 + 2 + 2 + 1 = 13 pts

        assert PointTracker.get_skill_points_spent(char) == 13
        assert PointTracker.get_skill_points_remaining(char) == -1
        errors = PointTracker.validate_skills(char)
        assert any("overspent" in e.lower() or "exceed" in e.lower() or "budget" in e.lower() for e in errors)

    def test_skill_points_underspending_detected(self, sample_human_character):
        """Verify spending 10 skill points with 12 available is flagged as unspent/incomplete."""
        char = sample_human_character
        char.attributes.agility = DieType.D8
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)  # 3 pts
        char.set_skill("Shooting", DieType.D8, AttributeName.AGILITY)  # 3 pts
        char.set_skill("Athletics", DieType.D6)  # 1 pt
        char.set_skill("Stealth", DieType.D6)  # 1 pt
        char.set_skill("Notice", DieType.D6)  # 2 pts (Smarts is d4)
        # Total = 10 pts

        assert PointTracker.get_skill_points_spent(char) == 10
        assert PointTracker.get_skill_points_remaining(char) == 2
        errors = PointTracker.validate_skills(char)
        assert any("unspent" in e.lower() or "remaining" in e.lower() or "points" in e.lower() for e in errors)

    def test_skill_cap_validation_d12(self, sample_human_character):
        """Verify skill die cannot exceed d12 at character creation."""
        char = sample_human_character
        char.set_skill("Fighting", DieType.D12_PLUS, AttributeName.AGILITY)

        errors = PointTracker.validate_skills(char)
        assert any("cap" in e.lower() or "d12" in e.lower() or "exceed" in e.lower() for e in errors)


# ==============================================================================
# Hindrance Economy Tests
# ==============================================================================

class TestHindranceEconomy:
    """Tests for Hindrance model, severity points, redemption, and 4-point cap."""

    def test_hindrance_model_severity_points(self):
        """Verify Minor hindrances yield 1 point and Major hindrances yield 2 points."""
        minor = Hindrance(name="Cautious", severity=HindranceSeverity.MINOR)
        assert minor.points == 1
        assert minor.severity == HindranceSeverity.MINOR

        major = Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR)
        assert major.points == 2
        assert major.severity == HindranceSeverity.MAJOR

    def test_hindrance_economy_points_calculation(self, sample_human_character):
        """Verify 1 Major + 2 Minor hindrances yield 4 total points."""
        char = sample_human_character
        char.hindrances = [
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR),
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR),
            Hindrance(name="Loyal", severity=HindranceSeverity.MINOR),
        ]

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.total_points == 4
        assert balance.usable_points == 4

    def test_hindrance_economy_max_benefit_cap_at_4(self, sample_human_character):
        """Verify that taking more than 4 points of hindrances caps usable points at 4."""
        char = sample_human_character
        # 2 Major + 1 Minor = 2 + 2 + 1 = 5 points
        char.hindrances = [
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR),
            Hindrance(name="Bloodthirsty", severity=HindranceSeverity.MAJOR),
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR),
        ]

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.total_points == 5
        assert balance.usable_points == MAX_HINDRANCE_POINTS
        assert balance.usable_points == 4

    def test_hindrance_redemption_attribute_bonus(self, sample_human_character):
        """Verify 2 hindrance points can be redeemed for +1 attribute point."""
        char = sample_human_character
        char.hindrances = [Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR)]  # 2 pts
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=1)

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.points_spent == 2
        assert balance.points_remaining == 0
        assert balance.is_valid is True

        # Attribute point available should increase by 1 (5 -> 6)
        assert PointTracker.get_attribute_points_available(char) == 6

    def test_hindrance_redemption_extra_edge(self, sample_human_character):
        """Verify 2 hindrance points can be redeemed for +1 Novice Edge."""
        char = sample_human_character
        char.hindrances = [Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR)]  # 2 pts
        char.hindrance_rewards = HindranceEconomy(edge_bonuses=1)

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.points_spent == 2
        assert balance.points_remaining == 0
        assert balance.is_valid is True

    def test_hindrance_redemption_skill_bonus(self, sample_human_character):
        """Verify 1 hindrance point can be redeemed for +1 skill point."""
        char = sample_human_character
        char.hindrances = [Hindrance(name="Cautious", severity=HindranceSeverity.MINOR)]  # 1 pt
        char.hindrance_rewards = HindranceEconomy(skill_bonuses=1)

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.points_spent == 1
        assert balance.points_remaining == 0
        assert balance.is_valid is True

        # Skill point available should increase by 1 (12 -> 13)
        assert PointTracker.get_skill_points_available(char) == 13

    def test_hindrance_redemption_cash_bonus(self, sample_human_character):
        """Verify 1 hindrance point can be redeemed for +$500 cash."""
        char = sample_human_character
        char.hindrances = [Hindrance(name="Cautious", severity=HindranceSeverity.MINOR)]  # 1 pt
        char.hindrance_rewards = HindranceEconomy(cash_bonuses=1)

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.points_spent == 1
        assert balance.points_remaining == 0
        assert balance.is_valid is True

    def test_hindrance_redemption_valid_combinations(self, sample_human_character):
        """Verify various valid combinations of spending 4 hindrance points."""
        char = sample_human_character
        char.hindrances = [
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR),
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR),
            Hindrance(name="Loyal", severity=HindranceSeverity.MINOR),
        ]  # 4 pts

        # Combo 1: 2 attribute bonuses (2 * 2 = 4 pts)
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=2)
        b1 = PointTracker.get_hindrance_points_balance(char)
        assert b1.points_spent == 4 and b1.points_remaining == 0 and b1.is_valid

        # Combo 2: 1 attribute (2 pts) + 1 edge (2 pts)
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=1, edge_bonuses=1)
        b2 = PointTracker.get_hindrance_points_balance(char)
        assert b2.points_spent == 4 and b2.points_remaining == 0 and b2.is_valid

        # Combo 3: 1 attribute (2 pts) + 1 skill (1 pt) + 1 cash (1 pt)
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=1, skill_bonuses=1, cash_bonuses=1)
        b3 = PointTracker.get_hindrance_points_balance(char)
        assert b3.points_spent == 4 and b3.points_remaining == 0 and b3.is_valid

        # Combo 4: 4 skill points (4 * 1 = 4 pts)
        char.hindrance_rewards = HindranceEconomy(skill_bonuses=4)
        b4 = PointTracker.get_hindrance_points_balance(char)
        assert b4.points_spent == 4 and b4.points_remaining == 0 and b4.is_valid

    def test_hindrance_redemption_overspending_invalid(self, sample_human_character):
        """Verify attempting to redeem more hindrance points than earned is invalid."""
        char = sample_human_character
        char.hindrances = [Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR)]  # 2 pts available
        # Attempt to spend 3 points (1 attr = 2 pts + 1 skill = 1 pt)
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=1, skill_bonuses=1)

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.points_spent == 3
        assert balance.points_remaining == -1
        assert balance.is_valid is False

        errors = PointTracker.validate_hindrances(char)
        assert any("overspend" in e.lower() or "exceed" in e.lower() or "hindrance" in e.lower() for e in errors)

    def test_hindrance_redemption_unspent_points_reported(self, sample_human_character):
        """Verify remaining unspent hindrance points are accurately tracked."""
        char = sample_human_character
        char.hindrances = [
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR),
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR),
        ]  # 3 pts available
        char.hindrance_rewards = HindranceEconomy(skill_bonuses=1)  # 1 pt spent

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.points_spent == 1
        assert balance.points_remaining == 2

    def test_hindrance_redemption_without_hindrances_invalid(self, sample_human_character):
        """Verify claiming hindrance rewards without taking hindrances is invalid."""
        char = sample_human_character
        char.hindrances = []
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=1)

        balance = PointTracker.get_hindrance_points_balance(char)
        assert balance.usable_points == 0
        assert balance.points_spent == 2
        assert balance.is_valid is False

        errors = PointTracker.validate_hindrances(char)
        assert len(errors) > 0


# ==============================================================================
# Integrated Build Validation Tests
# ==============================================================================

class TestIntegratedBuildValidation:
    """Tests for aggregate validate_build function combining all economies."""

    def test_validate_build_valid_complete_character(self, sample_human_character):
        """Verify a fully specified, compliant character produces zero validation errors."""
        char = sample_human_character

        # 4 hindrance points earned:
        char.hindrances = [
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR),
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR),
            Hindrance(name="Loyal", severity=HindranceSeverity.MINOR),
        ]
        # Redeemed for +1 attribute (2 pts) and +2 skills (2 pts):
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=1, skill_bonuses=2)

        # Available attributes = 5 + 1 = 6. Allocate exactly 6 points:
        char.attributes.agility = DieType.D8  # 2 pts
        char.attributes.smarts = DieType.D6   # 1 pt
        char.attributes.spirit = DieType.D6   # 1 pt
        char.attributes.strength = DieType.D6 # 1 pt
        char.attributes.vigor = DieType.D6    # 1 pt
        # Total attribute spent = 6. Remaining = 0.

        # Available skills = 12 + 2 = 14. Allocate exactly 14 points:
        char.set_skill("Athletics", DieType.D6)  # 1 pt
        char.set_skill("Common Knowledge", DieType.D4)  # 0 pt
        char.set_skill("Notice", DieType.D6)  # 1 pt
        char.set_skill("Persuasion", DieType.D6)  # 1 pt
        char.set_skill("Stealth", DieType.D6)  # 1 pt
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)  # 3 pts
        char.set_skill("Shooting", DieType.D8, AttributeName.AGILITY)  # 3 pts
        char.set_skill("Healing", DieType.D6, AttributeName.SMARTS)    # 2 pts
        char.set_skill("Survival", DieType.D6, AttributeName.SMARTS)   # 2 pts
        # Total skill spent = 1 + 0 + 1 + 1 + 1 + 3 + 3 + 2 + 2 = 14. Remaining = 0.

        errors = PointTracker.validate_build(char)
        assert errors == []

    def test_validate_build_accumulates_all_errors(self, sample_human_character):
        """Verify validate_build collects errors across attributes, skills, and hindrances."""
        char = sample_human_character

        # Overspend attributes (all d10 without hindrance bonus -> 3*5 = 15 spent of 5)
        char.attributes.agility = DieType.D10
        char.attributes.smarts = DieType.D10
        char.attributes.spirit = DieType.D10
        char.attributes.strength = DieType.D10
        char.attributes.vigor = DieType.D10

        # Overspend skills (e.g. 20 spent of 12)
        char.set_skill("Fighting", DieType.D12, AttributeName.AGILITY)
        char.set_skill("Shooting", DieType.D12, AttributeName.AGILITY)

        # Invalid hindrance redemption
        char.hindrances = []
        char.hindrance_rewards = HindranceEconomy(attribute_bonuses=2)

        errors = PointTracker.validate_build(char)
        assert len(errors) >= 3
        # Should have attribute, skill, and hindrance errors represented
        assert any("attribute" in e.lower() for e in errors)
        assert any("skill" in e.lower() for e in errors)
        assert any("hindrance" in e.lower() for e in errors)
