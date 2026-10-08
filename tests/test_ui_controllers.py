"""Unit and component tests for Desktop GUI controllers, state manager, and UI widgets (Slice 5).

Verifies acceptance criteria defined in docs/feature-slices.md:
- Testing CharacterState / AppController:
  - Creating a new character initializes default Human and 5 core skills.
  - Setting ancestry updates ancestry traits, pace, running die, size, and bennies.
  - Modifying attributes recalculates attribute points remaining and validates caps.
  - Modifying skills recalculates skill points remaining based on linked attributes.
  - Adding/removing hindrances tracks points and redemptions (attributes, skills, edges, cash).
  - Adding/removing edges checks prerequisites via PrerequisiteChecker.
  - Inventory operations: adding item from catalog deducts cost from cash, adds to inventory;
    removing item refunds cash; toggling equip updates carried armor / parry / encumbrance.
  - Arcana tab state: switching arcane background updates power points and allowed powers.
- Headless Tkinter UI widget instantiation:
  - Instantiating MainWindow, ConceptTab, TraitsTab, HindrancesEdgesTab, ArcanaTab,
    InventoryTab, and SummaryTab headlessly with proper teardown and graceful handling.
"""

import os
import sqlite3
import tkinter as tk
from pathlib import Path
from typing import Any
import pytest

from swchar.core.constants import (
    BASE_ATTRIBUTE_POINTS,
    BASE_BENNIES,
    BASE_PACE,
    BASE_SKILL_POINTS,
    MAX_HINDRANCE_POINTS,
    STARTING_CASH,
)
from swchar.core.dice import DieType
from swchar.db.catalog_seed import seed_default_catalog
from swchar.db.connection import get_db_connection
from swchar.db.repository import InventoryRepository
from swchar.db.schema import init_schema
from swchar.models.ancestry import get_ancestry
from swchar.models.arcana import (
    ArcaneBackgroundType,
    ArcaneConfiguration,
    Power,
    get_arcane_background_defaults,
)
from swchar.models.attributes import AttributeName
from swchar.models.character import Character
from swchar.models.edges import Rank
from swchar.models.hindrances import Hindrance, HindranceEconomy, HindranceSeverity
from swchar.models.items import CatalogItem, InventoryItem, ItemCategory
from swchar.models.skills import CORE_SKILLS

# UI & Controller components under test (Slice 5)
# In accordance with architecture.md, swchar.app is the application launcher and controller,
# and swchar.ui holds the desktop GUI components.
try:
    from swchar.app import AppController, CharacterState
except ImportError:
    try:
        from swchar.ui.controller import AppController, CharacterState  # type: ignore
    except ImportError:
        # Fallback to swchar.app so pytest captures the missing module in the RED phase
        from swchar.app import AppController, CharacterState  # type: ignore

try:
    from swchar.ui.main_window import MainWindow
    from swchar.ui.tabs.concept_tab import ConceptTab
    from swchar.ui.tabs.traits_tab import TraitsTab
    from swchar.ui.tabs.hindrances_edges_tab import HindrancesEdgesTab
    from swchar.ui.tabs.arcana_tab import ArcanaTab
    from swchar.ui.tabs.inventory_tab import InventoryTab
    from swchar.ui.tabs.summary_tab import SummaryTab
except ImportError:
    # Will fail in RED phase when UI modules are not yet implemented
    pass


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def in_memory_db() -> sqlite3.Connection:
    """Provide an initialized in-memory SQLite database seeded with standard catalog items."""
    conn = get_db_connection(":memory:")
    init_schema(conn)
    seed_default_catalog(conn)
    yield conn
    conn.close()


@pytest.fixture
def inventory_repo(in_memory_db: sqlite3.Connection) -> InventoryRepository:
    """Provide an InventoryRepository connected to the seeded test database."""
    return InventoryRepository(in_memory_db)


@pytest.fixture
def character_state(inventory_repo: InventoryRepository) -> CharacterState:
    """Provide a fresh CharacterState instance configured with the test repository."""
    return CharacterState(db_repo=inventory_repo)


@pytest.fixture
def app_controller(in_memory_db: sqlite3.Connection) -> AppController:
    """Provide a fresh AppController instance configured with the test connection."""
    return AppController(conn=in_memory_db)


@pytest.fixture
def tk_root():
    """Provide a withdrawn (headless) Tkinter root window with guaranteed teardown.

    Skips tests gracefully if no graphical display is available in the environment.
    """
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as err:
        pytest.skip(f"Tkinter display not available: {err}")
    yield root
    try:
        root.destroy()
    except Exception:
        pass


# ==============================================================================
# 1. Character State Initialization & Core Defaults
# ==============================================================================


class TestCharacterStateInitialization:
    """Acceptance tests for CharacterState / AppController initialization defaults."""

    def test_new_character_initializes_default_human(self, character_state: CharacterState) -> None:
        """Creating a new character initializes default Human ancestry, 5 core skills, and baseline cash."""
        char = character_state.character
        assert char is not None
        assert char.ancestry.name == "Human"
        assert char.cash == STARTING_CASH
        assert char.bennies == BASE_BENNIES
        assert char.rank == Rank.NOVICE
        assert char.name == ""
        assert char.concept == ""

    def test_new_character_initializes_five_core_skills_at_d4(
        self, character_state: CharacterState
    ) -> None:
        """New character automatically has the 5 SWADE core skills at d4 at zero point cost."""
        char = character_state.character
        for skill_name, attr_name in CORE_SKILLS.items():
            skill = char.get_skill(skill_name)
            assert skill is not None, f"Expected core skill '{skill_name}' to be present"
            assert skill.die == DieType.D4
            assert skill.attribute == attr_name
            assert skill.core is True

    def test_new_character_point_budgets_are_fresh(
        self, character_state: CharacterState
    ) -> None:
        """Attribute points remaining is 5, skill points remaining is 12, hindrance points is 0."""
        assert character_state.get_attribute_points_spent() == 0
        assert character_state.get_attribute_points_remaining() == BASE_ATTRIBUTE_POINTS
        assert character_state.get_skill_points_spent() == 0
        assert character_state.get_skill_points_remaining() == BASE_SKILL_POINTS
        assert character_state.get_hindrance_points() == 0

    def test_new_character_initial_derived_stats(
        self, character_state: CharacterState
    ) -> None:
        """Base Human character has Pace 6, Running die d6, Parry 2 (untrained), Toughness 4, Load Limit 20 lbs."""
        assert character_state.get_pace() == BASE_PACE
        assert character_state.get_running_die() == DieType.D6
        assert character_state.get_parry() == 2  # Untrained in Fighting
        # Toughness = 2 + (Vigor d4 // 2) = 4
        toughness = character_state.get_toughness()
        total_toughness = toughness.total if hasattr(toughness, "total") else toughness
        assert total_toughness == 4
        # Load limit = Str d4 (4) * 5 = 20 lbs
        assert character_state.get_load_limit() == 20.0

    def test_state_change_listeners_notified(
        self, character_state: CharacterState
    ) -> None:
        """Listeners subscribed to CharacterState receive notification events on mutations."""
        notifications: list[str] = []

        def on_change(event: str = "change") -> None:
            notifications.append(event)

        character_state.add_listener(on_change)
        character_state.set_name("Valen Thorne")
        assert len(notifications) >= 1
        assert character_state.character.name == "Valen Thorne"


# ==============================================================================
# 2. Ancestry State Transitions & Racial Modifiers
# ==============================================================================


class TestAncestryStateChanges:
    """Acceptance tests for switching ancestries and updating traits, pace, running die, size, and bennies."""

    def test_switch_ancestry_to_dwarf(self, character_state: CharacterState) -> None:
        """Switching to Dwarf updates Pace to 5, Running die to d4, Vigor baseline to d6, and traits."""
        character_state.set_ancestry("Dwarf")
        char = character_state.character

        assert char.ancestry.name == "Dwarf"
        assert character_state.get_pace() == 5
        assert character_state.get_running_die() == DieType.D4
        # Dwarf starts with Vigor d6 for free
        assert char.attributes.vigor >= DieType.D6
        # Toughness with Vigor d6 = 2 + (6 // 2) = 5
        toughness = character_state.get_toughness()
        total_toughness = toughness.total if hasattr(toughness, "total") else toughness
        assert total_toughness == 5
        # Traits check
        trait_names = [t.name for t in char.ancestry.traits]
        assert "Reduced Pace" in trait_names
        assert "Tough" in trait_names

    def test_switch_ancestry_to_half_folk(self, character_state: CharacterState) -> None:
        """Switching to Half-Folk updates Pace to 5, Running die to d4, Size to -1, and Bennies to 4 (Luck)."""
        character_state.set_ancestry("Half-Folk")
        char = character_state.character

        assert char.ancestry.name == "Half-Folk"
        assert character_state.get_pace() == 5
        assert character_state.get_running_die() == DieType.D4
        assert char.ancestry.size == -1
        assert character_state.get_bennies() == BASE_BENNIES + 1  # 4 Bennies from Luck

    def test_switch_ancestry_to_avion(self, character_state: CharacterState) -> None:
        """Switching to Avion updates ground Pace to 5, running die to d4, and flying pace to 12."""
        character_state.set_ancestry("Avion")
        char = character_state.character

        assert char.ancestry.name == "Avion"
        assert character_state.get_pace() == 5
        assert character_state.get_running_die() == DieType.D4
        assert getattr(char.ancestry, "flying_pace", 0) == 12

    def test_switch_ancestry_to_saurian(self, character_state: CharacterState) -> None:
        """Switching to Saurian grants Size +1 and natural armor +2, increasing total Toughness."""
        character_state.set_ancestry("Saurian")
        char = character_state.character

        assert char.ancestry.name == "Saurian"
        assert char.ancestry.size == 1
        assert char.ancestry.armor_bonus == 2
        # Base Toughness: 2 + (Vigor d4 // 2) + Size 1 = 5, plus 2 natural armor = 7
        toughness = character_state.get_toughness()
        total_toughness = toughness.total if hasattr(toughness, "total") else toughness
        assert total_toughness == 7

    def test_switch_ancestry_back_to_human(self, character_state: CharacterState) -> None:
        """Switching back to Human restores Pace 6, Running die d6, Bennies 3, and 1 free Edge."""
        character_state.set_ancestry("Dwarf")
        character_state.set_ancestry("Human")
        char = character_state.character

        assert char.ancestry.name == "Human"
        assert character_state.get_pace() == 6
        assert character_state.get_running_die() == DieType.D6
        assert character_state.get_bennies() == BASE_BENNIES
        assert char.ancestry.free_edge_count == 1


# ==============================================================================
# 3. Attribute Point-Buy & Validation
# ==============================================================================


class TestAttributeStateManagement:
    """Acceptance tests for modifying attributes, point budget accounting, caps, and derived recalculations."""

    def test_raising_attributes_deducts_points(self, character_state: CharacterState) -> None:
        """Raising attributes from d4 to d6/d8 spends 1 point per die step."""
        # Baseline: 5 available
        character_state.set_attribute(AttributeName.AGILITY, DieType.D8)  # 2 steps
        assert character_state.get_attribute_points_spent() == 2
        assert character_state.get_attribute_points_remaining() == 3

        character_state.set_attribute(AttributeName.SMARTS, DieType.D6)  # 1 step
        assert character_state.get_attribute_points_spent() == 3
        assert character_state.get_attribute_points_remaining() == 2

    def test_exact_budget_exhaustion(self, character_state: CharacterState) -> None:
        """Spending exactly 5 attribute points leaves 0 points remaining and no overspent errors."""
        character_state.set_attribute(AttributeName.AGILITY, DieType.D6)  # 1 pt
        character_state.set_attribute(AttributeName.SMARTS, DieType.D6)   # 1 pt
        character_state.set_attribute(AttributeName.SPIRIT, DieType.D6)   # 1 pt
        character_state.set_attribute(AttributeName.STRENGTH, DieType.D6) # 1 pt
        character_state.set_attribute(AttributeName.VIGOR, DieType.D6)    # 1 pt

        assert character_state.get_attribute_points_spent() == 5
        assert character_state.get_attribute_points_remaining() == 0
        errors = character_state.validate_attributes()
        assert not any("overspent" in err.lower() for err in errors)

    def test_overspending_attribute_budget_reported(self, character_state: CharacterState) -> None:
        """Spending more than 5 attribute points yields negative remaining and validation errors."""
        character_state.set_attribute(AttributeName.AGILITY, DieType.D10) # 3 pts
        character_state.set_attribute(AttributeName.STRENGTH, DieType.D10) # 3 pts
        # Total spent = 6 (over 5 budget)
        assert character_state.get_attribute_points_spent() == 6
        assert character_state.get_attribute_points_remaining() == -1
        errors = character_state.validate_attributes()
        assert any("overspent" in err.lower() for err in errors)

    def test_attribute_cap_validation(self, character_state: CharacterState) -> None:
        """Standard human character cannot exceed d12 at character creation."""
        with pytest.raises(ValueError) if hasattr(character_state, "strict_mode") else pytest.MonkeyPatch.context():
            # Should either raise ValueError or flag validation error on d12+
            character_state.set_attribute(AttributeName.AGILITY, DieType.D12_PLUS)
            errors = character_state.validate_attributes()
            assert any("cap" in err.lower() or "exceeds" in err.lower() for err in errors)

    def test_increasing_strength_updates_load_limit(self, character_state: CharacterState) -> None:
        """Increasing Strength increases character load limit dynamically (Strength die * 5 lbs)."""
        assert character_state.get_load_limit() == 20.0  # d4 * 5
        character_state.set_attribute(AttributeName.STRENGTH, DieType.D8)
        assert character_state.get_load_limit() == 40.0  # d8 * 5

    def test_increasing_vigor_updates_toughness(self, character_state: CharacterState) -> None:
        """Increasing Vigor increases Toughness dynamically (2 + half Vigor die)."""
        character_state.set_attribute(AttributeName.VIGOR, DieType.D8)
        toughness = character_state.get_toughness()
        total_toughness = toughness.total if hasattr(toughness, "total") else toughness
        assert total_toughness == 6  # 2 + (8 // 2)


# ==============================================================================
# 4. Skill Point-Buy & Linked Attribute Scaling
# ==============================================================================


class TestSkillStateManagement:
    """Acceptance tests for modifying skills, linked attribute thresholds, and derived Parry."""

    def test_advancing_core_skill_up_to_linked_attribute(
        self, character_state: CharacterState
    ) -> None:
        """Advancing a core skill up to its linked attribute costs 1 point per die step."""
        # Agility is d4 by default; raise Agility to d8
        character_state.set_attribute(AttributeName.AGILITY, DieType.D8)
        # Athletics is linked to Agility. Starts at d4 for 0 points.
        # Advancing d4 -> d6 costs 1 pt.
        character_state.set_skill("Athletics", DieType.D6)
        assert character_state.get_skill_points_spent() == 1
        assert character_state.get_skill_points_remaining() == 11

        # Advancing d6 -> d8 costs 1 more pt (total 2 pts).
        character_state.set_skill("Athletics", DieType.D8)
        assert character_state.get_skill_points_spent() == 2
        assert character_state.get_skill_points_remaining() == 10

    def test_advancing_skill_beyond_linked_attribute_costs_double(
        self, character_state: CharacterState
    ) -> None:
        """Advancing a skill beyond its linked attribute costs 2 points per step."""
        # Agility is d4. Athletics starts at d4 for 0 pts.
        # Advancing Athletics to d6 (above Agility d4) costs 2 points!
        character_state.set_skill("Athletics", DieType.D6)
        assert character_state.get_skill_points_spent() == 2
        assert character_state.get_skill_points_remaining() == 10

        # Advancing Athletics to d8 costs another 2 points (total 4 pts).
        character_state.set_skill("Athletics", DieType.D8)
        assert character_state.get_skill_points_spent() == 4
        assert character_state.get_skill_points_remaining() == 8

    def test_modifying_attribute_recalculates_linked_skill_costs(
        self, character_state: CharacterState
    ) -> None:
        """Raising an attribute reduces point cost for skills that were previously above it."""
        # Agility is d4. Set Athletics to d8 (costs 4 points).
        character_state.set_skill("Athletics", DieType.D8)
        assert character_state.get_skill_points_spent() == 4

        # Now raise Agility to d8. The steps d4->d6 and d6->d8 now cost 1 pt each (2 pts total).
        character_state.set_attribute(AttributeName.AGILITY, DieType.D8)
        assert character_state.get_skill_points_spent() == 2
        assert character_state.get_skill_points_remaining() == 10

    def test_non_core_skill_costs_one_point_for_d4(
        self, character_state: CharacterState
    ) -> None:
        """Non-core skill (e.g. Fighting) costs 1 point to purchase at d4 if linked attribute >= d4."""
        character_state.set_skill("Fighting", DieType.D4)
        assert character_state.get_skill_points_spent() == 1
        assert character_state.get_skill_points_remaining() == 11

    def test_fighting_skill_updates_parry(self, character_state: CharacterState) -> None:
        """Changing Fighting skill die immediately recalculates Parry (2 + half Fighting die)."""
        assert character_state.get_parry() == 2  # Untrained
        character_state.set_skill("Fighting", DieType.D6)
        assert character_state.get_parry() == 5  # 2 + 3
        character_state.set_skill("Fighting", DieType.D8)
        assert character_state.get_parry() == 6  # 2 + 4
        character_state.set_skill("Fighting", DieType.D10)
        assert character_state.get_parry() == 7  # 2 + 5

    def test_remove_non_core_skill_refunds_points(
        self, character_state: CharacterState
    ) -> None:
        """Removing a non-core skill refunds all spent points for that skill and resets Parry."""
        character_state.set_skill("Fighting", DieType.D8)
        assert character_state.get_skill_points_spent() > 0
        character_state.remove_skill("Fighting")
        assert character_state.get_skill_points_spent() == 0
        assert character_state.get_parry() == 2


# ==============================================================================
# 5. Hindrances & Disadvantage Reward Economy
# ==============================================================================


class TestHindranceStateManagement:
    """Acceptance tests for adding/removing hindrances and tracking point redemptions."""

    def test_add_hindrances_accumulates_points(
        self, character_state: CharacterState
    ) -> None:
        """Minor hindrance adds 1 point, Major hindrance adds 2 points."""
        character_state.add_hindrance("Cautious", HindranceSeverity.MINOR)
        assert character_state.get_hindrance_points() == 1

        character_state.add_hindrance("Heroic", HindranceSeverity.MAJOR)
        assert character_state.get_hindrance_points() == 3

    def test_hindrance_points_capped_at_four(
        self, character_state: CharacterState
    ) -> None:
        """Taking hindrances worth more than 4 points caps usable mechanical points at 4."""
        character_state.add_hindrance("Heroic", HindranceSeverity.MAJOR)      # 2 pts
        character_state.add_hindrance("Bloodthirsty", HindranceSeverity.MAJOR) # 2 pts
        character_state.add_hindrance("Cautious", HindranceSeverity.MINOR)     # 1 pt
        # Total points earned = 5, usable capped at 4
        economy = character_state.get_hindrance_economy()
        assert economy.total_earned == 5
        assert economy.usable_points == MAX_HINDRANCE_POINTS

    def test_redeem_points_for_attribute_bonus(
        self, character_state: CharacterState
    ) -> None:
        """Redeeming 2 hindrance points grants +1 attribute point bonus."""
        character_state.add_hindrance("Heroic", HindranceSeverity.MAJOR)  # 2 pts
        character_state.redeem_hindrance_reward("attribute", count=1)  # 2 hindrance pts

        assert character_state.get_attribute_points_available() == BASE_ATTRIBUTE_POINTS + 1
        assert character_state.get_attribute_points_remaining() == BASE_ATTRIBUTE_POINTS + 1
        economy = character_state.get_hindrance_economy()
        assert economy.remaining_points == 0

    def test_redeem_points_for_skill_bonus(
        self, character_state: CharacterState
    ) -> None:
        """Redeeming 1 hindrance point grants +1 skill point bonus."""
        character_state.add_hindrance("Cautious", HindranceSeverity.MINOR)  # 1 pt
        character_state.redeem_hindrance_reward("skill", count=1)  # 1 hindrance pt

        assert character_state.get_skill_points_available() == BASE_SKILL_POINTS + 1
        assert character_state.get_skill_points_remaining() == BASE_SKILL_POINTS + 1

    def test_redeem_points_for_cash_bonus(
        self, character_state: CharacterState
    ) -> None:
        """Redeeming 1 hindrance point grants +$500 starting cash."""
        character_state.add_hindrance("Cautious", HindranceSeverity.MINOR)  # 1 pt
        initial_cash = character_state.get_cash()
        character_state.redeem_hindrance_reward("cash", count=1)

        assert character_state.get_cash() == initial_cash + 500.0

    def test_remove_hindrance_updates_available_balance(
        self, character_state: CharacterState
    ) -> None:
        """Removing a hindrance decreases total points earned and balance."""
        character_state.add_hindrance("Heroic", HindranceSeverity.MAJOR)
        assert character_state.get_hindrance_points() == 2
        character_state.remove_hindrance("Heroic")
        assert character_state.get_hindrance_points() == 0


# ==============================================================================
# 6. Edges & Prerequisite Checking
# ==============================================================================


class TestEdgeStateManagement:
    """Acceptance tests for selecting edges, prerequisite validation, and mechanical trait effects."""

    def test_can_take_edge_returns_true_when_prerequisites_met(
        self, character_state: CharacterState
    ) -> None:
        """Quick requires Agility d8; returns True when Agility is raised to d8."""
        character_state.set_attribute(AttributeName.AGILITY, DieType.D8)
        can_take, reasons = character_state.can_take_edge("Quick")
        assert can_take is True
        assert len(reasons) == 0

    def test_can_take_edge_returns_false_when_trait_insufficient(
        self, character_state: CharacterState
    ) -> None:
        """Quick requires Agility d8; returns False with reason when Agility is d4."""
        can_take, reasons = character_state.can_take_edge("Quick")
        assert can_take is False
        assert any("agility" in r.lower() for r in reasons)

    def test_add_edge_with_unsatisfied_prerequisites_rejected(
        self, character_state: CharacterState
    ) -> None:
        """Attempting to add an edge with unmet prerequisites fails or raises ValueError."""
        # Block requires Fighting d8
        result = character_state.add_edge("Block")
        # Should either return False or character.edges should not contain Block
        if result is not False:
            assert "Block" not in character_state.character.edges

    def test_add_edge_block_increases_parry(
        self, character_state: CharacterState
    ) -> None:
        """Adding Block (+1 Parry) when Fighting is d8 raises Parry from 6 to 7."""
        character_state.set_attribute(AttributeName.AGILITY, DieType.D8)
        character_state.set_skill("Fighting", DieType.D8)
        assert character_state.get_parry() == 6  # 2 + 4

        success = character_state.add_edge("Block")
        assert success is True or "Block" in character_state.character.edges
        assert character_state.get_parry() == 7  # 6 + 1

    def test_remove_edge_resets_bonus(self, character_state: CharacterState) -> None:
        """Removing Block resets Parry back to baseline 6."""
        character_state.set_attribute(AttributeName.AGILITY, DieType.D8)
        character_state.set_skill("Fighting", DieType.D8)
        character_state.add_edge("Block")
        assert character_state.get_parry() == 7

        character_state.remove_edge("Block")
        assert character_state.get_parry() == 6
        assert "Block" not in character_state.character.edges

    def test_fleet_footed_edge_increases_pace_and_running_die(
        self, character_state: CharacterState
    ) -> None:
        """Fleet-Footed grants +2 Pace and steps up Running die from d6 to d8."""
        assert character_state.get_pace() == 6
        assert character_state.get_running_die() == DieType.D6

        character_state.add_edge("Fleet-Footed")
        assert character_state.get_pace() == 8
        assert character_state.get_running_die() == DieType.D8


# ==============================================================================
# 7. Inventory Manager, Equip Toggles & Encumbrance
# ==============================================================================


class TestInventoryStateOperations:
    """Acceptance tests for purchasing catalog items, cash deduction, equip toggling, and encumbrance."""

    def test_add_catalog_item_deducts_cash_and_adds_to_inventory(
        self, character_state: CharacterState, inventory_repo: InventoryRepository
    ) -> None:
        """Adding item from catalog deducts cost from cash and adds item to inventory."""
        items = inventory_repo.list_catalog_items(query="Dagger")
        assert len(items) > 0
        dagger = items[0]

        initial_cash = character_state.get_cash()
        character_state.add_item_from_catalog(dagger, quantity=1)

        assert character_state.get_cash() == initial_cash - dagger.cost
        inv = character_state.character.inventory
        assert len(inv) == 1
        assert inv[0].name == dagger.name
        assert inv[0].quantity == 1

    def test_insufficient_cash_prevents_purchase(
        self, character_state: CharacterState
    ) -> None:
        """Attempting to buy an item costing more than available cash fails."""
        expensive_item = CatalogItem(name="Sports Car", cost=50000.0, weight=2500.0)
        success = character_state.add_item_from_catalog(expensive_item, quantity=1)
        assert success is False or len(character_state.character.inventory) == 0
        assert character_state.get_cash() == STARTING_CASH

    def test_remove_item_refunds_cash(
        self, character_state: CharacterState, inventory_repo: InventoryRepository
    ) -> None:
        """Removing an inventory item refunds its purchase price to cash."""
        items = inventory_repo.list_catalog_items(query="Short Sword")
        assert len(items) > 0
        sword = items[0]

        character_state.add_item_from_catalog(sword, quantity=1)
        assert character_state.get_cash() == STARTING_CASH - sword.cost

        inv_item = character_state.character.inventory[0]
        character_state.remove_inventory_item(inv_item)

        assert character_state.get_cash() == STARTING_CASH
        assert len(character_state.character.inventory) == 0

    def test_equipping_armor_increases_toughness(
        self, character_state: CharacterState, inventory_repo: InventoryRepository
    ) -> None:
        """Equipping armor adds its armor bonus to character Toughness."""
        armors = inventory_repo.list_catalog_items(category=ItemCategory.ARMOR)
        assert len(armors) > 0
        armor = armors[0]  # e.g. Leather Jacket with armor_bonus 1 or Leather Armor with 2

        character_state.add_item_from_catalog(armor, quantity=1)
        item = character_state.character.inventory[0]
        assert item.is_equipped is False

        base_toughness = character_state.get_toughness()
        base_val = base_toughness.total if hasattr(base_toughness, "total") else base_toughness

        # Equip armor
        character_state.toggle_equip_item(item)
        assert item.is_equipped is True

        equipped_toughness = character_state.get_toughness()
        equipped_val = equipped_toughness.total if hasattr(equipped_toughness, "total") else equipped_toughness
        assert equipped_val == base_val + item.armor_bonus

        # Unequip armor
        character_state.toggle_equip_item(item)
        assert item.is_equipped is False
        unequipped_toughness = character_state.get_toughness()
        unequipped_val = unequipped_toughness.total if hasattr(unequipped_toughness, "total") else unequipped_toughness
        assert unequipped_val == base_val

    def test_equipping_shield_increases_parry(
        self, character_state: CharacterState, inventory_repo: InventoryRepository
    ) -> None:
        """Equipping a shield adds its parry bonus to Parry."""
        shields = inventory_repo.list_catalog_items(category=ItemCategory.SHIELD)
        assert len(shields) > 0
        shield = shields[0]  # e.g. Small Shield with parry_bonus 1

        character_state.add_item_from_catalog(shield, quantity=1)
        item = character_state.character.inventory[0]

        initial_parry = character_state.get_parry()
        character_state.toggle_equip_item(item)
        assert character_state.get_parry() == initial_parry + shield.parry_bonus

        character_state.toggle_equip_item(item)
        assert character_state.get_parry() == initial_parry

    def test_carried_weight_and_encumbrance_penalty_calculation(
        self, character_state: CharacterState
    ) -> None:
        """Carried weight exceeding Load Limit applies encumbrance penalties."""
        # Strength d4 -> Load Limit = 20 lbs
        assert character_state.get_load_limit() == 20.0
        assert character_state.get_encumbrance_penalty() == 0

        # Add heavy custom item: 25 lbs (over 20, <= 40 -> penalty -1)
        heavy_item = InventoryItem(name="Anvil", weight=25.0, cost=0.0, quantity=1)
        character_state.add_inventory_item(heavy_item)

        assert character_state.get_carried_weight() == 25.0
        assert character_state.get_encumbrance_penalty() == -1

        # Add second item: total 45 lbs (over 40, <= 60 -> penalty -2)
        heavy_item2 = InventoryItem(name="Iron Ore", weight=20.0, cost=0.0, quantity=1)
        character_state.add_inventory_item(heavy_item2)

        assert character_state.get_carried_weight() == 45.0
        assert character_state.get_encumbrance_penalty() == -2


# ==============================================================================
# 8. Arcana Tab State & Powers Configuration
# ==============================================================================


class TestArcanaStateOperations:
    """Acceptance tests for Arcane Background switching, power points, and known powers."""

    def test_switch_to_magic_background_configures_starting_defaults(
        self, character_state: CharacterState
    ) -> None:
        """Switching to Magic sets Power Points to 10 and allows 3 starting powers."""
        character_state.set_arcane_background("Magic")
        arcana = character_state.character.arcana
        assert arcana is not None
        assert arcana.background == "Magic"
        assert character_state.get_power_points() == 10
        defaults = get_arcane_background_defaults("Magic")
        assert defaults.power_points == 10
        assert defaults.starting_powers == 3

    def test_switch_to_gifted_background_configures_starting_defaults(
        self, character_state: CharacterState
    ) -> None:
        """Switching to Gifted sets Power Points to 15 and allows 1 starting power."""
        character_state.set_arcane_background("Gifted")
        assert character_state.get_power_points() == 15
        defaults = get_arcane_background_defaults("Gifted")
        assert defaults.power_points == 15
        assert defaults.starting_powers == 1

    def test_add_and_remove_supernatural_powers(
        self, character_state: CharacterState
    ) -> None:
        """Powers can be added with trappings and removed from Arcana tab state."""
        character_state.set_arcane_background("Magic")
        bolt = Power(
            name="Bolt",
            power_points=1,
            trappings="Fiery Missiles",
            range="12/24/48",
            damage="2d6",
        )
        character_state.add_power(bolt)

        powers = character_state.get_powers()
        assert len(powers) == 1
        assert powers[0].name == "Bolt"
        assert powers[0].trappings == "Fiery Missiles"

        character_state.remove_power("Bolt")
        assert len(character_state.get_powers()) == 0

    def test_switch_to_none_clears_arcana(
        self, character_state: CharacterState
    ) -> None:
        """Switching Arcane Background back to None clears powers and resets power points to 0."""
        character_state.set_arcane_background("Magic")
        character_state.add_power(Power(name="Healing", power_points=2))
        assert character_state.get_power_points() == 10

        character_state.set_arcane_background("None")
        assert character_state.get_power_points() == 0
        powers = character_state.get_powers()
        assert len(powers) == 0


# ==============================================================================
# 9. Headless Tkinter UI Widget Instantiation
# ==============================================================================


class TestHeadlessTkinterUIWidgets:
    """Acceptance tests verifying Tkinter UI widgets instantiate and teardown cleanly."""

    def test_main_window_instantiates_headlessly(
        self, tk_root: tk.Tk, character_state: CharacterState, inventory_repo: InventoryRepository
    ) -> None:
        """MainWindow instantiates cleanly with notebook and tab controllers."""
        window = MainWindow(root=tk_root, state=character_state, repo=inventory_repo)
        assert window is not None
        # Verify notebook or main container exists
        assert hasattr(window, "notebook") or hasattr(window, "tabs") or hasattr(window, "root")
        tk_root.update_idletasks()

    def test_concept_tab_instantiates_and_binds(
        self, tk_root: tk.Tk, character_state: CharacterState
    ) -> None:
        """ConceptTab instantiates and displays character name, concept, and ancestry."""
        tab = ConceptTab(parent=tk_root, state=character_state)
        assert tab is not None
        tk_root.update_idletasks()

    def test_traits_tab_instantiates_and_binds(
        self, tk_root: tk.Tk, character_state: CharacterState
    ) -> None:
        """TraitsTab instantiates with live attribute and skill counters."""
        tab = TraitsTab(parent=tk_root, state=character_state)
        assert tab is not None
        tk_root.update_idletasks()

    def test_hindrances_edges_tab_instantiates_and_binds(
        self, tk_root: tk.Tk, character_state: CharacterState
    ) -> None:
        """HindrancesEdgesTab instantiates with pickers and budget counters."""
        tab = HindrancesEdgesTab(parent=tk_root, state=character_state)
        assert tab is not None
        tk_root.update_idletasks()

    def test_arcana_tab_instantiates_and_binds(
        self, tk_root: tk.Tk, character_state: CharacterState
    ) -> None:
        """ArcanaTab instantiates with arcane background dropdown and power list."""
        tab = ArcanaTab(parent=tk_root, state=character_state)
        assert tab is not None
        tk_root.update_idletasks()

    def test_inventory_tab_instantiates_and_binds(
        self, tk_root: tk.Tk, character_state: CharacterState, inventory_repo: InventoryRepository
    ) -> None:
        """InventoryTab instantiates with catalog browser, inventory view, and cash tracker."""
        tab = InventoryTab(parent=tk_root, state=character_state, repo=inventory_repo)
        assert tab is not None
        tk_root.update_idletasks()

    def test_summary_tab_instantiates_and_binds(
        self, tk_root: tk.Tk, character_state: CharacterState
    ) -> None:
        """SummaryTab instantiates with combat sheet profile and export buttons."""
        tab = SummaryTab(parent=tk_root, state=character_state)
        assert tab is not None
        tk_root.update_idletasks()
