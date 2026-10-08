"""Unit tests for Slice 2: Edge Model & Prerequisite Validation Engine.

Directly verifies acceptance criteria defined in docs/feature-slices.md:
- Edge domain model:
  - Name, Category (Background, Combat, Leadership, Power, Professional, Social, Weird),
    Rank (Novice, Seasoned, Veteran, Heroic, Legendary), Prerequisites, Description.
- Prerequisite validation engine (PrerequisiteChecker):
  - Trait requirements (minimum attribute ratings, minimum skill ratings).
  - Multiple trait prerequisites (e.g. Strength d6 AND Vigor d6).
  - Rank requirements (Novice at creation, Seasoned, Veteran).
  - Chained edge prerequisites (e.g. Frenzy required for Improved Frenzy).
  - Arcane Background requirements for Power edges (New Powers, Power Points).
  - Verification of standard SWADE Novice Edges:
    - Alertness, Ambidextrous, Arcane Background, Brawny, Quick,
      Fleet-Footed, Brawler, Command, Luck, etc.
  - Character-level edge validation (validate_character_edges).
"""

import pytest
from swchar.core.dice import DieType
from swchar.models.ancestry import get_ancestry
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.character import Character
from swchar.models.edges import Edge, EdgeCategory, Rank, get_edge, EDGES
from swchar.rules.prerequisites import PrerequisiteChecker


# ==============================================================================
# Domain Model Tests (Rank, EdgeCategory, Edge)
# ==============================================================================

class TestEdgeAndRankModels:
    """Tests for Rank enum, EdgeCategory enum, and Edge dataclass."""

    def test_rank_enum_progression_and_values(self):
        """Verify Rank enum contains all standard SWADE ranks with ordered progression."""
        assert Rank.NOVICE.value.lower() == "novice"
        assert Rank.SEASONED.value.lower() == "seasoned"
        assert Rank.VETERAN.value.lower() == "veteran"
        assert Rank.HEROIC.value.lower() == "heroic"
        assert Rank.LEGENDARY.value.lower() == "legendary"

        # Check ordering: Novice < Seasoned < Veteran < Heroic < Legendary
        assert Rank.NOVICE < Rank.SEASONED < Rank.VETERAN < Rank.HEROIC < Rank.LEGENDARY

    def test_edge_category_enum_values(self):
        """Verify EdgeCategory enum has all standard SWADE categories."""
        expected_categories = {
            "Background",
            "Combat",
            "Leadership",
            "Power",
            "Professional",
            "Social",
            "Weird",
        }
        actual_categories = {cat.value for cat in EdgeCategory}
        assert actual_categories == expected_categories

    def test_edge_initialization_defaults(self):
        """Verify Edge model attributes and default rank to Novice."""
        edge = Edge(
            name="Custom Edge",
            category=EdgeCategory.COMBAT,
            description="A combat edge.",
        )
        assert edge.name == "Custom Edge"
        assert edge.category == EdgeCategory.COMBAT
        assert edge.rank == Rank.NOVICE
        assert edge.description == "A combat edge."


# ==============================================================================
# Trait Prerequisite Tests
# ==============================================================================

class TestTraitPrerequisites:
    """Tests for attribute and skill prerequisite enforcement."""

    def test_attribute_prerequisite_satisfied(self, sample_human_character):
        """Verify character with required attribute meets the prerequisite."""
        char = sample_human_character
        char.attributes.agility = DieType.D8

        ambidextrous = get_edge("Ambidextrous")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, ambidextrous)
        assert can_take is True
        assert len(reasons) == 0
        assert PrerequisiteChecker.is_eligible(char, ambidextrous) is True

    def test_attribute_prerequisite_unsatisfied(self, sample_human_character):
        """Verify character with attribute below requirement fails with explanation."""
        char = sample_human_character
        char.attributes.agility = DieType.D6  # Ambidextrous requires Agility d8

        ambidextrous = get_edge("Ambidextrous")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, ambidextrous)
        assert can_take is False
        assert len(reasons) > 0
        assert any("agility" in r.lower() and ("d8" in r.lower() or "d6" in r.lower()) for r in reasons)
        assert PrerequisiteChecker.is_eligible(char, ambidextrous) is False

    def test_multiple_attribute_prerequisites(self, sample_human_character):
        """Verify Edge with multiple attribute requirements (e.g. Brawny: Str d6, Vig d6)."""
        char = sample_human_character
        brawny = get_edge("Brawny")

        # Scenario 1: Both attributes satisfied (Str d6, Vig d6)
        char.attributes.strength = DieType.D6
        char.attributes.vigor = DieType.D6
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, brawny)
        assert can_take is True
        assert len(reasons) == 0

        # Scenario 2: Strength satisfied (d6), Vigor unsatisfied (d4)
        char.attributes.strength = DieType.D6
        char.attributes.vigor = DieType.D4
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, brawny)
        assert can_take is False
        assert any("vigor" in r.lower() for r in reasons)

        # Scenario 3: Strength unsatisfied (d4), Vigor satisfied (d6)
        char.attributes.strength = DieType.D4
        char.attributes.vigor = DieType.D6
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, brawny)
        assert can_take is False
        assert any("strength" in r.lower() for r in reasons)

        # Scenario 4: Neither satisfied (Str d4, Vig d4)
        char.attributes.strength = DieType.D4
        char.attributes.vigor = DieType.D4
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, brawny)
        assert can_take is False
        assert len(reasons) >= 2

    def test_skill_prerequisite_satisfied(self, sample_human_character):
        """Verify character with required skill die rating satisfies prerequisite."""
        char = sample_human_character
        char.rank = Rank.SEASONED
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)

        frenzy = get_edge("Frenzy")  # Requires Seasoned, Fighting d8
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, frenzy)
        assert can_take is True
        assert len(reasons) == 0

    def test_skill_prerequisite_untrained_fails(self, sample_human_character):
        """Verify character untrained in required skill fails with explanation."""
        char = sample_human_character
        char.rank = Rank.SEASONED

        frenzy = get_edge("Frenzy")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, frenzy)
        assert can_take is False
        assert any("fighting" in r.lower() for r in reasons)

    def test_skill_prerequisite_lower_die_fails(self, sample_human_character):
        """Verify character with skill die below requirement fails."""
        char = sample_human_character
        char.rank = Rank.SEASONED
        char.set_skill("Fighting", DieType.D6, AttributeName.AGILITY)  # Needs d8

        frenzy = get_edge("Frenzy")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, frenzy)
        assert can_take is False
        assert any("fighting" in r.lower() and "d8" in r.lower() for r in reasons)


# ==============================================================================
# Rank Prerequisite Tests
# ==============================================================================

class TestRankPrerequisites:
    """Tests for character rank vs edge required rank."""

    def test_rank_novice_character_can_take_novice_edge(self, sample_human_character):
        """Verify Novice character qualifies for Novice rank edges."""
        char = sample_human_character
        # At creation, character is Novice
        quick = get_edge("Quick")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, quick)
        assert can_take is True
        assert len(reasons) == 0

    def test_rank_novice_character_cannot_take_seasoned_edge(self, sample_human_character):
        """Verify Novice character is rejected for Seasoned edge even if trait is met."""
        char = sample_human_character
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)

        frenzy = get_edge("Frenzy")  # Requires Seasoned rank
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, frenzy)
        assert can_take is False
        assert any("rank" in r.lower() or "seasoned" in r.lower() for r in reasons)

    def test_rank_seasoned_character_accepted_for_seasoned_edge(self, sample_human_character):
        """Verify Seasoned character with required traits can take Seasoned edge."""
        char = sample_human_character
        char.rank = Rank.SEASONED
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)

        frenzy = get_edge("Frenzy")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, frenzy)
        assert can_take is True
        assert len(reasons) == 0

    def test_rank_seasoned_character_cannot_take_veteran_edge(self, sample_human_character):
        """Verify Seasoned character cannot take Veteran edge (e.g. Improved Frenzy)."""
        char = sample_human_character
        char.rank = Rank.SEASONED
        char.edges.append("Frenzy")

        improved_frenzy = get_edge("Improved Frenzy")  # Requires Veteran rank
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, improved_frenzy)
        assert can_take is False
        assert any("rank" in r.lower() or "veteran" in r.lower() for r in reasons)


# ==============================================================================
# Edge Dependency & Chained Prerequisite Tests
# ==============================================================================

class TestEdgePrerequisites:
    """Tests for prerequisite edges required before taking advanced edges."""

    def test_edge_prerequisite_missing_parent_edge_fails(self, sample_human_character):
        """Verify taking Improved Frenzy without having Frenzy fails."""
        char = sample_human_character
        char.rank = Rank.VETERAN
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        # Does not have Frenzy

        improved_frenzy = get_edge("Improved Frenzy")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, improved_frenzy)
        assert can_take is False
        assert any("frenzy" in r.lower() for r in reasons)

    def test_edge_prerequisite_with_parent_edge_passes(self, sample_human_character):
        """Verify taking Improved Frenzy with Frenzy present passes."""
        char = sample_human_character
        char.rank = Rank.VETERAN
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        char.edges.append("Frenzy")

        improved_frenzy = get_edge("Improved Frenzy")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, improved_frenzy)
        assert can_take is True
        assert len(reasons) == 0


# ==============================================================================
# Arcane Background & Power Edge Tests
# ==============================================================================

class TestArcaneBackgroundPrerequisites:
    """Tests for Power edges requiring Arcane Background."""

    def test_power_edge_requires_arcane_background(self, sample_human_character):
        """Verify character without Arcane Background cannot take Power Edges."""
        char = sample_human_character

        power_points = get_edge("Power Points")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, power_points)
        assert can_take is False
        assert any("arcane" in r.lower() for r in reasons)

        new_powers = get_edge("New Powers")
        can_take2, reasons2 = PrerequisiteChecker.can_take_edge(char, new_powers)
        assert can_take2 is False
        assert any("arcane" in r.lower() for r in reasons2)

    def test_power_edge_satisfied_with_arcane_edge(self, sample_human_character):
        """Verify having Arcane Background in edges satisfies requirement."""
        char = sample_human_character
        char.edges.append("Arcane Background")

        power_points = get_edge("Power Points")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, power_points)
        assert can_take is True
        assert len(reasons) == 0

    def test_power_edge_satisfied_with_character_arcana(self, sample_human_character):
        """Verify having arcana attribute populated on character satisfies requirement."""
        char = sample_human_character
        char.arcana = "Magic"

        new_powers = get_edge("New Powers")
        can_take, reasons = PrerequisiteChecker.can_take_edge(char, new_powers)
        assert can_take is True
        assert len(reasons) == 0


# ==============================================================================
# Canonical SWADE Novice Edges Validation Tests
# ==============================================================================

class TestStandardSWADENoviceEdges:
    """Tests verifying the standard SWADE Novice Edges list from feature slices."""

    @pytest.mark.parametrize(
        "edge_name",
        [
            "Alertness",
            "Ambidextrous",
            "Arcane Background",
            "Brawny",
            "Quick",
            "Fleet-Footed",
            "Brawler",
            "Command",
            "Luck",
        ],
    )
    def test_standard_novice_edges_exist_in_registry(self, edge_name):
        """Verify each standard Novice Edge exists and has Novice rank."""
        edge = get_edge(edge_name)
        assert edge is not None
        assert edge.name.lower() == edge_name.lower()
        assert edge.rank == Rank.NOVICE

    def test_alertness_prerequisites(self, sample_human_character):
        """Alertness: Novice rank, no trait requirements."""
        edge = get_edge("Alertness")
        assert edge.category == EdgeCategory.BACKGROUND
        assert edge.rank == Rank.NOVICE
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_ambidextrous_prerequisites(self, sample_human_character):
        """Ambidextrous: Novice rank, Agility d8."""
        edge = get_edge("Ambidextrous")
        sample_human_character.attributes.agility = DieType.D6
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is False

        sample_human_character.attributes.agility = DieType.D8
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_arcane_background_prerequisites(self, sample_human_character):
        """Arcane Background: Novice rank."""
        edge = get_edge("Arcane Background")
        assert edge.rank == Rank.NOVICE
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_brawny_prerequisites(self, sample_human_character):
        """Brawny: Novice rank, Strength d6, Vigor d6."""
        edge = get_edge("Brawny")
        sample_human_character.attributes.strength = DieType.D4
        sample_human_character.attributes.vigor = DieType.D6
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is False

        sample_human_character.attributes.strength = DieType.D6
        sample_human_character.attributes.vigor = DieType.D6
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_quick_prerequisites(self, sample_human_character):
        """Quick: Novice rank."""
        edge = get_edge("Quick")
        assert edge.rank == Rank.NOVICE
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_fleet_footed_prerequisites(self, sample_human_character):
        """Fleet-Footed: Novice rank, Agility d6."""
        edge = get_edge("Fleet-Footed")
        sample_human_character.attributes.agility = DieType.D4
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is False

        sample_human_character.attributes.agility = DieType.D6
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_brawler_prerequisites(self, sample_human_character):
        """Brawler: Novice rank, Strength d8, Vigor d8 (SWADE)."""
        edge = get_edge("Brawler")
        assert edge.category == EdgeCategory.COMBAT
        sample_human_character.attributes.strength = DieType.D4
        sample_human_character.attributes.vigor = DieType.D4
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is False

        sample_human_character.attributes.strength = DieType.D8
        sample_human_character.attributes.vigor = DieType.D8
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_command_prerequisites(self, sample_human_character):
        """Command: Novice rank, Smarts d6."""
        edge = get_edge("Command")
        assert edge.category == EdgeCategory.LEADERSHIP
        sample_human_character.attributes.smarts = DieType.D4
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is False

        sample_human_character.attributes.smarts = DieType.D6
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True

    def test_luck_prerequisites(self, sample_human_character):
        """Luck: Novice rank, no trait requirements."""
        edge = get_edge("Luck")
        assert edge.category == EdgeCategory.BACKGROUND
        assert edge.rank == Rank.NOVICE
        assert PrerequisiteChecker.is_eligible(sample_human_character, edge) is True


# ==============================================================================
# Character-Level Edge Validation Tests
# ==============================================================================

class TestCharacterEdgeValidation:
    """Tests for validating the full list of edges on a character."""

    def test_validate_character_edges_all_valid(self, sample_human_character):
        """Verify a character with valid edges passes with no errors."""
        char = sample_human_character
        char.attributes.agility = DieType.D8
        char.attributes.smarts = DieType.D6
        char.attributes.strength = DieType.D6
        char.attributes.vigor = DieType.D6

        char.edges = ["Alertness", "Ambidextrous", "Brawny", "Command", "Luck"]
        errors = PrerequisiteChecker.validate_character_edges(char)
        assert errors == []

    def test_validate_character_edges_detects_violations(self, sample_human_character):
        """Verify character with unfulfilled edges reports all violations."""
        char = sample_human_character
        # Baseline character: all traits d4, Novice rank
        char.edges = ["Ambidextrous", "Brawny", "Command", "Frenzy"]

        errors = PrerequisiteChecker.validate_character_edges(char)
        assert len(errors) == 4
        assert any("ambidextrous" in e.lower() for e in errors)
        assert any("brawny" in e.lower() for e in errors)
        assert any("command" in e.lower() for e in errors)
        assert any("frenzy" in e.lower() for e in errors)

    def test_can_take_edge_accepts_edge_name_string(self, sample_human_character):
        """Verify can_take_edge supports passing either an Edge object or edge name string."""
        can_take, _ = PrerequisiteChecker.can_take_edge(sample_human_character, "Alertness")
        assert can_take is True
