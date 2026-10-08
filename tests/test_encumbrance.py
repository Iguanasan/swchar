"""Unit tests for encumbrance calculations, minimum strength checks, and weapon damage caps (Slice 3)."""

import pytest

from swchar.core.dice import DieType
from swchar.models.ancestry import get_ancestry
from swchar.models.character import Character
from swchar.models.items import InventoryItem
from swchar.rules.derived_stats import DerivedStatsCalculator
from swchar.rules.encumbrance import (
    EncumbranceCalculator,
    EncumbranceResult,
    MinStrResult,
)


class TestCalculateCarriedWeight:
    """Tests for calculating total carried weight from inventory items."""

    def test_empty_inventory_weight_is_zero(self) -> None:
        """Carried weight of an empty inventory is exactly 0.0 lbs."""
        items: list[InventoryItem] = []
        weight = EncumbranceCalculator.calculate_carried_weight(items)
        assert weight == 0.0

    def test_single_item_default_quantity(self) -> None:
        """Carried weight of a single item with quantity 1."""
        items = [
            InventoryItem(name="Backpack", category="Adventuring Gear", cost=50.0, weight=2.0, quantity=1)
        ]
        assert EncumbranceCalculator.calculate_carried_weight(items) == 2.0

    def test_item_with_multiple_quantity(self) -> None:
        """Carried weight multiplies individual item weight by quantity."""
        items = [
            InventoryItem(name="Trail Rations", category="Adventuring Gear", cost=10.0, weight=1.0, quantity=5)
        ]
        assert EncumbranceCalculator.calculate_carried_weight(items) == 5.0

    def test_fractional_weight_with_quantity(self) -> None:
        """Carried weight correctly aggregates fractional weights."""
        items = [
            InventoryItem(name="9mm Ammo", category="Ammo", cost=0.5, weight=0.05, quantity=50),
            InventoryItem(name="Arrows", category="Ammo", cost=0.5, weight=0.1, quantity=20),
        ]
        # (0.05 * 50) + (0.1 * 20) = 2.5 + 2.0 = 4.5
        assert pytest.approx(EncumbranceCalculator.calculate_carried_weight(items), 0.01) == 4.5

    def test_multiple_mixed_items(self) -> None:
        """Carried weight aggregates a realistic multi-item inventory."""
        items = [
            InventoryItem(name="Glock 9mm", category="Ranged Weapon", cost=200.0, weight=3.0, quantity=1),
            InventoryItem(name="Leather Jacket", category="Armor", cost=80.0, weight=5.0, quantity=1),
            InventoryItem(name="Rope", category="Adventuring Gear", cost=10.0, weight=10.0, quantity=1),
            InventoryItem(name="Dagger", category="Melee Weapon", cost=25.0, weight=1.0, quantity=2),
        ]
        # 3.0 + 5.0 + 10.0 + (1.0 * 2) = 20.0 lbs
        assert EncumbranceCalculator.calculate_carried_weight(items) == 20.0

    def test_zero_weight_items(self) -> None:
        """Weightless items contribute 0 to the carried weight."""
        items = [
            InventoryItem(name="Paper Money", category="Adventuring Gear", cost=0.0, weight=0.0, quantity=100),
            InventoryItem(name="Dagger", category="Melee Weapon", cost=25.0, weight=1.0, quantity=1),
        ]
        assert EncumbranceCalculator.calculate_carried_weight(items) == 1.0


class TestCalculateEncumbrancePenalty:
    """Tests for computing encumbrance penalties and immobilization status based on load limits."""

    def test_unencumbered_below_load_limit(self) -> None:
        """Carried weight strictly below load limit results in no penalty and not immobilized."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=20.0)
        assert isinstance(res, EncumbranceResult)
        assert res.penalty == 0
        assert res.is_immobilized is False

    def test_unencumbered_at_exact_load_limit(self) -> None:
        """Carried weight exactly equal to load limit results in 0 penalty."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=30.0)
        assert res.penalty == 0
        assert res.is_immobilized is False

    def test_encumbered_tier_1_just_over_load_limit(self) -> None:
        """Carried weight just over load limit up to 2x load limit gives -1 penalty."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=30.1)
        assert res.penalty == -1
        assert res.is_immobilized is False

    def test_encumbered_tier_1_at_exact_2x_load_limit(self) -> None:
        """Carried weight at exactly 2x load limit is still in tier 1 (-1 penalty)."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=60.0)
        assert res.penalty == -1
        assert res.is_immobilized is False

    def test_encumbered_tier_2_just_over_2x_load_limit(self) -> None:
        """Carried weight just over 2x up to 3x load limit gives -2 penalty."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=60.1)
        assert res.penalty == -2
        assert res.is_immobilized is False

    def test_encumbered_tier_2_at_exact_3x_load_limit(self) -> None:
        """Carried weight at exactly 3x load limit is in tier 2 (-2 penalty)."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=90.0)
        assert res.penalty == -2
        assert res.is_immobilized is False

    def test_encumbered_tier_3_just_over_3x_load_limit(self) -> None:
        """Carried weight just over 3x up to 4x load limit gives -3 penalty."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=90.1)
        assert res.penalty == -3
        assert res.is_immobilized is False

    def test_encumbered_tier_3_at_exact_4x_load_limit(self) -> None:
        """Carried weight at exactly 4x load limit gives -3 penalty and not immobilized."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=120.0)
        assert res.penalty == -3
        assert res.is_immobilized is False

    def test_immobilized_over_4x_load_limit(self) -> None:
        """Carried weight greater than 4x load limit immobilizes the character."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=120.1)
        assert res.is_immobilized is True

    def test_immobilized_extreme_weight(self) -> None:
        """Carried weight far above 4x load limit is strictly immobilized."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=30.0, carried_weight=300.0)
        assert res.is_immobilized is True

    def test_zero_load_limit(self) -> None:
        """Zero load limit with positive weight causes immobilization."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit=0.0, carried_weight=5.0)
        assert res.is_immobilized is True


class TestCheckMinStrength:
    """Tests for checking character Strength against item Minimum Strength requirements."""

    def test_min_str_none_always_satisfies(self) -> None:
        """Items with no minimum strength requirement (None) are always satisfied without penalty."""
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str=None)
        assert isinstance(res, MinStrResult)
        assert res.satisfies is True
        assert res.deficiency == 0
        assert res.penalty == 0

    def test_min_str_exact_match(self) -> None:
        """Strength equal to Min Str satisfies requirement with 0 deficiency and 0 penalty."""
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D6, min_str=DieType.D6)
        assert res.satisfies is True
        assert res.deficiency == 0
        assert res.penalty == 0

    def test_min_str_exceeded(self) -> None:
        """Strength higher than Min Str satisfies requirement with 0 penalty."""
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D10, min_str=DieType.D6)
        assert res.satisfies is True
        assert res.deficiency == 0
        assert res.penalty == 0

    def test_min_str_deficient_by_one_step(self) -> None:
        """1 die step deficiency yields deficiency=1 and penalty=-1."""
        # D4 vs D6 (1 step)
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str=DieType.D6)
        assert res.satisfies is False
        assert res.deficiency == 1
        assert res.penalty == -1

        # D6 vs D8 (1 step)
        res2 = EncumbranceCalculator.check_min_strength(character_strength=DieType.D6, min_str=DieType.D8)
        assert res2.satisfies is False
        assert res2.deficiency == 1
        assert res2.penalty == -1

        # D8 vs D10 (1 step)
        res3 = EncumbranceCalculator.check_min_strength(character_strength=DieType.D8, min_str=DieType.D10)
        assert res3.satisfies is False
        assert res3.deficiency == 1
        assert res3.penalty == -1

        # D10 vs D12 (1 step)
        res4 = EncumbranceCalculator.check_min_strength(character_strength=DieType.D10, min_str=DieType.D12)
        assert res4.satisfies is False
        assert res4.deficiency == 1
        assert res4.penalty == -1

    def test_min_str_deficient_by_two_steps(self) -> None:
        """2 die steps deficiency yields deficiency=2 and penalty=-2."""
        # D4 vs D8 (2 steps: D4 -> D6 -> D8)
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str=DieType.D8)
        assert res.satisfies is False
        assert res.deficiency == 2
        assert res.penalty == -2

        # D6 vs D10 (2 steps: D6 -> D8 -> D10)
        res2 = EncumbranceCalculator.check_min_strength(character_strength=DieType.D6, min_str=DieType.D10)
        assert res2.satisfies is False
        assert res2.deficiency == 2
        assert res2.penalty == -2

    def test_min_str_deficient_by_three_steps(self) -> None:
        """3 die steps deficiency yields deficiency=3 and penalty=-3."""
        # D4 vs D10 (3 steps: D4 -> D6 -> D8 -> D10)
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str=DieType.D10)
        assert res.satisfies is False
        assert res.deficiency == 3
        assert res.penalty == -3

    def test_min_str_deficient_by_four_steps(self) -> None:
        """4 die steps deficiency yields deficiency=4 and penalty=-4."""
        # D4 vs D12 (4 steps: D4 -> D6 -> D8 -> D10 -> D12)
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str=DieType.D12)
        assert res.satisfies is False
        assert res.deficiency == 4
        assert res.penalty == -4

    def test_min_str_accepts_string_input(self) -> None:
        """check_min_strength gracefully accepts string representations like 'd6' or 'd8'."""
        res = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str="d6")
        assert res.satisfies is False
        assert res.deficiency == 1
        assert res.penalty == -1

        res_none = EncumbranceCalculator.check_min_strength(character_strength=DieType.D4, min_str="")
        assert res_none.satisfies is True


class TestEffectiveWeaponDamageCap:
    """Tests for SWADE core rule: weapon damage die cannot exceed wielder's Strength die when Min Str is not met."""

    def test_effective_damage_when_meeting_min_str(self) -> None:
        """When Strength meets or exceeds Min Str, weapon damage is uncapped."""
        # Long Sword (Str+d8), wielder Str d8 -> Str+d8
        dmg = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D8,
            min_str=DieType.D8,
            base_damage="Str+d8",
        )
        assert dmg.lower() == "str+d8"

        # Long Sword (Str+d8), wielder Str d10 -> Str+d8 (not increased beyond weapon die)
        dmg2 = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D10,
            min_str=DieType.D8,
            base_damage="Str+d8",
        )
        assert dmg2.lower() == "str+d8"

    def test_effective_damage_capped_when_lacking_min_str(self) -> None:
        """When Strength is lower than Min Str, weapon's bonus die is capped at wielder's Strength."""
        # Battle Axe (Str+d8), min str d8, wielder Str d6 -> capped at Str+d6
        dmg1 = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D6,
            min_str=DieType.D8,
            base_damage="Str+d8",
        )
        assert dmg1.lower() == "str+d6"

        # Greatsword (Str+d10), min str d10, wielder Str d6 -> capped at Str+d6
        dmg2 = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D6,
            min_str=DieType.D10,
            base_damage="Str+d10",
        )
        assert dmg2.lower() == "str+d6"

        # Long Sword (Str+d8), min str d8, wielder Str d4 -> capped at Str+d4
        dmg3 = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D4,
            min_str=DieType.D8,
            base_damage="Str+d8",
        )
        assert dmg3.lower() == "str+d4"

    def test_effective_damage_preserves_flat_bonuses(self) -> None:
        """Flat damage bonuses (+1, +2) are preserved when the die is capped."""
        dmg = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D6,
            min_str=DieType.D8,
            base_damage="Str+d8+1",
        )
        assert dmg.lower() == "str+d6+1"

    def test_effective_damage_without_min_str(self) -> None:
        """Items without minimum strength remain uncapped."""
        dmg = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D4,
            min_str=None,
            base_damage="Str+d4",
        )
        assert dmg.lower() == "str+d4"

    def test_effective_damage_from_inventory_item(self) -> None:
        """calculate_effective_weapon_damage can evaluate directly from an InventoryItem."""
        item = InventoryItem(
            name="Battle Axe",
            category="Melee Weapon",
            cost=300.0,
            weight=10.0,
            damage="Str+d8",
            min_str="d8",
        )
        # Using helper if item passed, or direct method
        dmg = EncumbranceCalculator.calculate_effective_weapon_damage(
            character_strength=DieType.D6,
            min_str=DieType.from_string(item.min_str) if item.min_str else None,
            base_damage=item.damage or "",
        )
        assert dmg.lower() == "str+d6"


class TestEncumbranceCharacterIntegration:
    """Integration tests combining Character traits, Load Limit calculation, and Encumbrance penalties."""

    def test_character_encumbrance_workflow(self) -> None:
        """Full character workflow verifying load limit vs carried weight penalties."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
        )
        char.attributes.strength = DieType.D6
        load_limit = DerivedStatsCalculator.calculate_load_limit(char)
        assert load_limit == 30.0  # D6 * 5 = 30 lbs

        # Add gear totaling 25 lbs (unencumbered)
        inv_under = [
            InventoryItem(name="Chainmail", category="Armor", cost=500.0, weight=25.0, quantity=1),
        ]
        carried_1 = EncumbranceCalculator.calculate_carried_weight(inv_under)
        assert carried_1 == 25.0
        res_1 = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried_1)
        assert res_1.penalty == 0
        assert res_1.is_immobilized is False

        # Add gear totaling 45 lbs (encumbered tier 1: 30.1 - 60 lbs)
        inv_tier_1 = inv_under + [
            InventoryItem(name="Rope and Gear", category="Adventuring Gear", cost=100.0, weight=20.0, quantity=1),
        ]
        carried_2 = EncumbranceCalculator.calculate_carried_weight(inv_tier_1)
        assert carried_2 == 45.0
        res_2 = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried_2)
        assert res_2.penalty == -1
        assert res_2.is_immobilized is False

        # Add gear totaling 75 lbs (encumbered tier 2: 60.1 - 90 lbs)
        inv_tier_2 = inv_tier_1 + [
            InventoryItem(name="Heavy Chest", category="Adventuring Gear", cost=50.0, weight=30.0, quantity=1),
        ]
        carried_3 = EncumbranceCalculator.calculate_carried_weight(inv_tier_2)
        assert carried_3 == 75.0
        res_3 = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried_3)
        assert res_3.penalty == -2
        assert res_3.is_immobilized is False

        # Add gear totaling 105 lbs (encumbered tier 3: 90.1 - 120 lbs)
        inv_tier_3 = inv_tier_2 + [
            InventoryItem(name="Iron Ore", category="Adventuring Gear", cost=20.0, weight=30.0, quantity=1),
        ]
        carried_4 = EncumbranceCalculator.calculate_carried_weight(inv_tier_3)
        assert carried_4 == 105.0
        res_4 = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried_4)
        assert res_4.penalty == -3
        assert res_4.is_immobilized is False

        # Add gear totaling 135 lbs (> 120 lbs = 4x load limit -> immobilized)
        inv_immob = inv_tier_3 + [
            InventoryItem(name="Anvil", category="Adventuring Gear", cost=200.0, weight=30.0, quantity=1),
        ]
        carried_5 = EncumbranceCalculator.calculate_carried_weight(inv_immob)
        assert carried_5 == 135.0
        res_5 = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried_5)
        assert res_5.is_immobilized is True

    def test_brawny_edge_increases_load_limit_and_reduces_encumbrance(self) -> None:
        """Brawny edge increases load limit to Strength * 8, mitigating encumbrance."""
        char = Character(
            name="Thorgar",
            concept="Dwarf Fighter",
            ancestry=get_ancestry("Dwarf"),
        )
        char.attributes.strength = DieType.D6
        char.edges.append("Brawny")

        load_limit = DerivedStatsCalculator.calculate_load_limit(char)
        assert load_limit == 48.0  # D6 * 8 = 48 lbs (vs 30 lbs standard)

        # Carrying 40 lbs would be encumbered (-1) for normal character, but unencumbered for Brawny
        inv = [
            InventoryItem(name="Plate", category="Armor", cost=700.0, weight=30.0, quantity=1),
            InventoryItem(name="Battle Axe", category="Melee Weapon", cost=300.0, weight=10.0, quantity=1),
        ]
        carried = EncumbranceCalculator.calculate_carried_weight(inv)
        assert carried == 40.0

        res = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried)
        assert res.penalty == 0
        assert res.is_immobilized is False
