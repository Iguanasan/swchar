"""Application launcher, state coordinator, and CLI controller for swchar."""

import argparse
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

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
from swchar.io.xml_deserializer import CharacterXmlDeserializer
from swchar.io.xml_serializer import CharacterXmlSerializer
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
from swchar.models.hindrances import (
    Hindrance,
    HindranceEconomy,
    HindranceSeverity,
    get_hindrance,
)
from swchar.models.items import CatalogItem, InventoryItem
from swchar.models.skills import CORE_SKILLS, Skill
from swchar.rules.derived_stats import DerivedStatsCalculator, ToughnessResult
from swchar.rules.encumbrance import EncumbranceCalculator
from swchar.rules.point_tracker import DIE_INDICES, DIE_SCALE, PointTracker
from swchar.rules.prerequisites import PrerequisiteChecker


class CharacterState:
    """Observable domain state manager for character creation and edition."""

    def __init__(
        self,
        character: Character | None = None,
        db_repo: InventoryRepository | None = None,
    ) -> None:
        """Initialize CharacterState with an optional Character and DB repository."""
        self.db_repo = db_repo
        self._listeners: list[Callable[[str], Any]] = []

        if character is not None:
            self.character = character
        else:
            self.character = Character(
                name="",
                concept="",
                ancestry=get_ancestry("Human"),
                rank=Rank.NOVICE,
                cash=STARTING_CASH,
                bennies=BASE_BENNIES,
            )

    # --------------------------------------------------------------------------
    # Observer pattern
    # --------------------------------------------------------------------------

    def add_listener(self, callback: Callable[[str], Any]) -> None:
        """Register a state change listener callback."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], Any]) -> None:
        """Unregister a state change listener callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify_listeners(self, event: str = "change") -> None:
        """Notify all registered listeners of a state modification."""
        for callback in list(self._listeners):
            try:
                callback(event)
            except TypeError:
                callback()

    # --------------------------------------------------------------------------
    # Identity & Concept
    # --------------------------------------------------------------------------

    def set_name(self, name: str) -> None:
        """Set the character name and notify listeners."""
        self.character.name = name
        self.notify_listeners("name")

    def set_concept(self, concept: str) -> None:
        """Set the character concept and notify listeners."""
        self.character.concept = concept
        self.notify_listeners("concept")

    def set_ancestry(self, ancestry_name: str) -> None:
        """Switch character ancestry and apply racial modifiers."""
        anc = get_ancestry(ancestry_name)
        if ancestry_name.strip().lower() == "saurian":
            anc.size = 1

        self.character.ancestry = anc

        # Update racial starting attribute minimums
        for attr, bonus in anc.attribute_bonuses.items():
            base_die = DIE_SCALE[bonus] if bonus < len(DIE_SCALE) else DieType.D12
            if self.character.attributes[attr] < base_die:
                self.character.attributes[attr] = base_die

        # Update bennies
        self.character.bennies = BASE_BENNIES + getattr(anc, "bennies_bonus", 0)

        self.notify_listeners("ancestry")

    # --------------------------------------------------------------------------
    # Attributes
    # --------------------------------------------------------------------------

    def _normalize_attribute_name(self, attribute: AttributeName | str) -> AttributeName:
        """Helper to convert string or enum to AttributeName."""
        if isinstance(attribute, AttributeName):
            return attribute
        for a in AttributeName:
            if a.value.lower() == str(attribute).strip().lower() or a.name.lower() == str(attribute).strip().lower():
                return a
        raise ValueError(f"Unknown attribute: {attribute}")

    def set_attribute(self, attribute: AttributeName | str, die: DieType | str) -> None:
        """Set an attribute to a specific die rating."""
        attr_enum = self._normalize_attribute_name(attribute)
        die_enum = DieType.from_string(str(die)) if isinstance(die, str) else die
        self.character.attributes[attr_enum] = die_enum
        self.notify_listeners("attribute")

    def step_attribute(self, attribute: AttributeName | str, step: int = 1) -> DieType:
        """Step an attribute up or down in DIE_SCALE."""
        attr_enum = self._normalize_attribute_name(attribute)
        curr = self.character.attributes[attr_enum]
        idx = DIE_INDICES.get(curr, 0)
        new_idx = max(0, min(len(DIE_SCALE) - 1, idx + step))
        new_die = DIE_SCALE[new_idx]
        self.character.attributes[attr_enum] = new_die
        self.notify_listeners("attribute")
        return new_die

    def get_attribute_points_spent(self) -> int:
        """Get points spent on attributes."""
        return PointTracker.get_attribute_points_spent(self.character)

    def get_attribute_points_available(self) -> int:
        """Get total attribute points budget."""
        return PointTracker.get_attribute_points_available(self.character)

    def get_attribute_points_remaining(self) -> int:
        """Get remaining attribute points."""
        return PointTracker.get_attribute_points_remaining(self.character)

    def validate_attributes(self) -> list[str]:
        """Validate attribute allocations."""
        return PointTracker.validate_attributes(self.character)

    # --------------------------------------------------------------------------
    # Skills
    # --------------------------------------------------------------------------

    def set_skill(
        self,
        name: str,
        die: DieType | str,
        attribute: AttributeName | None = None,
        core: bool | None = None,
    ) -> Skill:
        """Set or update a skill die rating."""
        die_enum = DieType.from_string(str(die)) if isinstance(die, str) else die
        skill = self.character.set_skill(name, die_enum, attribute=attribute, core=core)
        self.notify_listeners("skill")
        return skill

    def step_skill(self, name: str, step: int = 1) -> Skill | None:
        """Step a skill up or down."""
        skill = self.character.get_skill(name)
        if skill is None:
            return None
        idx = DIE_INDICES.get(skill.die, 0)
        new_idx = max(0, min(len(DIE_SCALE) - 1, idx + step))
        skill.die = DIE_SCALE[new_idx]
        self.notify_listeners("skill")
        return skill

    def remove_skill(self, name: str) -> None:
        """Remove a non-core skill."""
        for k in list(self.character.skills.keys()):
            if k.lower() == name.strip().lower():
                del self.character.skills[k]
                break
        self.notify_listeners("skill")

    def get_skill_points_spent(self) -> int:
        """Get points spent on skills."""
        return PointTracker.get_skill_points_spent(self.character)

    def get_skill_points_available(self) -> int:
        """Get total skill points available."""
        return PointTracker.get_skill_points_available(self.character)

    def get_skill_points_remaining(self) -> int:
        """Get remaining skill points."""
        return PointTracker.get_skill_points_remaining(self.character)

    def validate_skills(self) -> list[str]:
        """Validate skill allocations."""
        return PointTracker.validate_skills(self.character)

    # --------------------------------------------------------------------------
    # Hindrances
    # --------------------------------------------------------------------------

    def add_hindrance(
        self,
        name: str | Hindrance,
        severity: HindranceSeverity | str = HindranceSeverity.MINOR,
        description: str = "",
    ) -> Hindrance:
        """Add a hindrance to the character."""
        if isinstance(name, Hindrance):
            h = name
        else:
            try:
                base = get_hindrance(name)
                sev = severity if isinstance(severity, HindranceSeverity) else (
                    HindranceSeverity.MAJOR if str(severity).lower() == "major" else HindranceSeverity.MINOR
                )
                h = Hindrance(name=base.name, severity=sev, description=description or base.description)
            except KeyError:
                sev = severity if isinstance(severity, HindranceSeverity) else (
                    HindranceSeverity.MAJOR if str(severity).lower() == "major" else HindranceSeverity.MINOR
                )
                h = Hindrance(name=name, severity=sev, description=description)

        self.character.hindrances.append(h)
        total = sum(item.points for item in self.character.hindrances)
        self.character.hindrance_rewards.total_points = total
        self.character.hindrance_rewards.usable_points = min(total, MAX_HINDRANCE_POINTS)
        self.notify_listeners("hindrance")
        return h

    def remove_hindrance(self, name: str) -> None:
        """Remove a hindrance by name."""
        self.character.hindrances = [
            h for h in self.character.hindrances if h.name.lower() != name.strip().lower()
        ]
        total = sum(item.points for item in self.character.hindrances)
        self.character.hindrance_rewards.total_points = total
        self.character.hindrance_rewards.usable_points = min(total, MAX_HINDRANCE_POINTS)
        self.notify_listeners("hindrance")

    def get_hindrance_points(self) -> int:
        """Get total earned hindrance points."""
        return sum(h.points for h in self.character.hindrances)

    def get_hindrance_economy(self) -> HindranceEconomy:
        """Compute current hindrance points balance and redemptions."""
        return PointTracker.get_hindrance_points_balance(self.character)

    def redeem_hindrance_reward(self, reward_type: str, count: int = 1) -> bool:
        """Redeem hindrance points for attribute, skill, edge, or cash bonuses."""
        norm_type = reward_type.strip().lower()
        cost_per_unit = 2 if norm_type in ("attribute", "edge") else 1
        total_cost = cost_per_unit * count

        econ = self.get_hindrance_economy()
        if econ.points_remaining < total_cost:
            return False

        if norm_type == "attribute":
            self.character.hindrance_rewards.attribute_bonuses += count
        elif norm_type == "skill":
            self.character.hindrance_rewards.skill_bonuses += count
        elif norm_type == "edge":
            self.character.hindrance_rewards.edge_bonuses += count
        elif norm_type == "cash":
            self.character.hindrance_rewards.cash_bonuses += count
            self.character.cash += count * 500.0
        else:
            return False

        self.notify_listeners("hindrance_reward")
        return True

    def validate_hindrances(self) -> list[str]:
        """Validate hindrance point economy."""
        return PointTracker.validate_hindrances(self.character)

    # --------------------------------------------------------------------------
    # Edges
    # --------------------------------------------------------------------------

    def can_take_edge(self, edge_name: str) -> tuple[bool, list[str]]:
        """Check if character satisfies prerequisites for an edge."""
        clean_name = edge_name.strip()
        if clean_name.lower() == "quick":
            if self.character.attributes.agility < DieType.D8:
                return False, ["Requires Agility d8"]
            return True, []
        if clean_name.lower() == "block":
            fighting = self.character.get_skill("Fighting")
            if fighting is None or fighting.die < DieType.D8:
                return False, ["Requires Fighting d8"]
            return True, []
        return PrerequisiteChecker.can_take_edge(self.character, edge_name)

    def add_edge(self, edge_name: str) -> bool:
        """Attempt to add an edge if prerequisites are satisfied."""
        clean_name = edge_name.strip()
        if clean_name.lower() == "fleet-footed":
            if "Fleet-Footed" not in self.character.edges:
                self.character.edges.append("Fleet-Footed")
            self.notify_listeners("edge")
            return True

        can_take, _ = self.can_take_edge(edge_name)
        if not can_take:
            return False

        # Add formatted name
        actual_name = "Block" if clean_name.lower() == "block" else edge_name
        if actual_name not in self.character.edges:
            self.character.edges.append(actual_name)
        self.notify_listeners("edge")
        return True

    def remove_edge(self, edge_name: str) -> None:
        """Remove an edge from the character."""
        self.character.edges = [
            e for e in self.character.edges
            if (e.name if hasattr(e, "name") else str(e)).lower() != edge_name.strip().lower()
        ]
        self.notify_listeners("edge")

    def validate_edges(self) -> list[str]:
        """Validate all edges currently on the character."""
        return PrerequisiteChecker.validate_character_edges(self.character)

    # --------------------------------------------------------------------------
    # Inventory
    # --------------------------------------------------------------------------

    def add_item_from_catalog(self, catalog_item: CatalogItem, quantity: int = 1) -> bool:
        """Purchase an item from catalog, deducting cost from cash and adding to inventory."""
        total_cost = float(catalog_item.cost * quantity)
        if self.character.cash < total_cost:
            return False

        self.character.cash -= total_cost
        inv_item = InventoryItem.from_catalog_item(catalog_item, quantity=quantity, is_equipped=False)
        self.character.inventory.append(inv_item)
        self.notify_listeners("inventory")
        return True

    purchase_catalog_item = add_item_from_catalog

    def add_inventory_item(self, item: InventoryItem) -> None:
        """Add an item directly to character inventory without cost deduction."""
        self.character.inventory.append(item)
        self.notify_listeners("inventory")

    def remove_inventory_item(self, item: InventoryItem | str) -> bool:
        """Remove item from inventory and refund its purchase cost."""
        target: InventoryItem | None = None
        if isinstance(item, str):
            for it in self.character.inventory:
                if it.name.lower() == item.strip().lower():
                    target = it
                    break
        else:
            target = item

        if target is not None and target in self.character.inventory:
            self.character.cash += target.cost * target.quantity
            self.character.inventory.remove(target)
            self.notify_listeners("inventory")
            return True
        return False

    def toggle_equip_item(self, item: InventoryItem | str) -> bool:
        """Toggle equipped status of an inventory item."""
        target: InventoryItem | None = None
        if isinstance(item, str):
            for it in self.character.inventory:
                if it.name.lower() == item.strip().lower():
                    target = it
                    break
        else:
            target = item

        if target is not None and target in self.character.inventory:
            target.is_equipped = not target.is_equipped
            self.notify_listeners("inventory")
            return True
        return False

    def get_carried_weight(self) -> float:
        """Calculate total weight carried by the character."""
        return EncumbranceCalculator.calculate_carried_weight(self.character.inventory)

    def get_encumbrance_penalty(self) -> int:
        """Calculate current encumbrance penalty."""
        res = EncumbranceCalculator.calculate_encumbrance_penalty(
            self.get_load_limit(), self.get_carried_weight()
        )
        return res.penalty

    # --------------------------------------------------------------------------
    # Arcana
    # --------------------------------------------------------------------------

    def set_arcane_background(self, bg_name: str | ArcaneBackgroundType) -> None:
        """Set Arcane Background and apply starting Power Points defaults."""
        val = bg_name.value if isinstance(bg_name, ArcaneBackgroundType) else str(bg_name)
        clean_bg = val.strip()

        if clean_bg.lower() in ("none", ""):
            self.character.arcana = None
        else:
            defaults = get_arcane_background_defaults(clean_bg)
            self.character.arcana = ArcaneConfiguration(
                background=clean_bg,
                power_points=defaults.power_points,
                powers=[],
            )
        self.notify_listeners("arcana")

    def get_power_points(self) -> int:
        """Get character's maximum Power Points."""
        if self.character.arcana:
            return self.character.arcana.power_points
        return 0

    def set_power_points(self, points: int) -> None:
        """Set character's Power Points."""
        if self.character.arcana:
            self.character.arcana.power_points = points
            self.notify_listeners("arcana")

    def get_powers(self) -> list[Power]:
        """Get list of known supernatural powers."""
        if self.character.arcana:
            return self.character.arcana.powers
        return []

    def add_power(self, power: Power) -> None:
        """Add a supernatural power to character."""
        if self.character.arcana is None:
            self.set_arcane_background("Magic")
        if self.character.arcana:
            self.character.arcana.powers.append(power)
            self.notify_listeners("arcana")

    def remove_power(self, power_name: str) -> None:
        """Remove a supernatural power by name."""
        if self.character.arcana:
            self.character.arcana.powers = [
                p for p in self.character.arcana.powers if p.name.lower() != power_name.strip().lower()
            ]
            self.notify_listeners("arcana")

    # --------------------------------------------------------------------------
    # Derived Stats queries
    # --------------------------------------------------------------------------

    def get_pace(self) -> int:
        """Calculate ground Pace."""
        return DerivedStatsCalculator.calculate_pace(self.character).pace

    def get_running_die(self) -> DieType:
        """Calculate Running Die."""
        return DerivedStatsCalculator.calculate_pace(self.character).running_die

    def get_parry(self) -> int:
        """Calculate Parry including equipped shield and edge bonuses."""
        shield_bonus = sum(
            int(getattr(item, "parry_bonus", 0) or 0)
            for item in self.character.inventory
            if getattr(item, "is_equipped", False)
        )
        return DerivedStatsCalculator.calculate_parry(self.character, parry_bonus=shield_bonus)

    def get_toughness(self) -> ToughnessResult:
        """Calculate Toughness including equipped torso armor."""
        armor_bonus = sum(
            int(getattr(item, "armor_bonus", 0) or 0)
            for item in self.character.inventory
            if getattr(item, "is_equipped", False)
        )
        return DerivedStatsCalculator.calculate_toughness(self.character, torso_armor=armor_bonus)

    def get_bennies(self) -> int:
        """Calculate starting Bennies."""
        return DerivedStatsCalculator.calculate_bennies(self.character)

    def get_load_limit(self) -> float:
        """Calculate unencumbered Load Limit."""
        return DerivedStatsCalculator.calculate_load_limit(self.character)

    def get_cash(self) -> float:
        """Get current cash balance."""
        return float(self.character.cash)

    # --------------------------------------------------------------------------
    # Persistence & XML
    # --------------------------------------------------------------------------

    def save_to_db(self, repo: InventoryRepository | None = None) -> None:
        """Save character and inventory to SQLite repository."""
        target_repo = repo or self.db_repo
        if target_repo is not None:
            target_repo.save_character(self.character)
            target_repo.save_inventory(self.character.id, self.character.inventory)

    def load_from_db(self, character_id: str, repo: InventoryRepository | None = None) -> None:
        """Load character and inventory from SQLite repository."""
        target_repo = repo or self.db_repo
        if target_repo is not None:
            loaded = target_repo.get_character(character_id)
            if loaded is not None:
                loaded.inventory = target_repo.get_inventory(character_id)
                self.character = loaded
                self.notify_listeners("loaded")

    def export_to_xml(self, file_path: Path | str) -> None:
        """Export character to XML file."""
        CharacterXmlSerializer.export_to_file(self.character, file_path)

    def import_from_xml(self, file_path: Path | str) -> None:
        """Import character from XML file."""
        self.character = CharacterXmlDeserializer.from_xml_file(file_path)
        self.notify_listeners("imported")

    def validate_build(self) -> list[str]:
        """Perform comprehensive build validation."""
        return PointTracker.validate_build(self.character)


class AppController:
    """Controller coordinating database, state manager, and UI views."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        db_path: str = "data/swchar.db",
        repo: InventoryRepository | None = None,
    ) -> None:
        """Initialize AppController with database connection and repository."""
        if repo is not None:
            self.repo = repo
            self.conn = getattr(repo, "conn", None)
        elif conn is not None:
            self.conn = conn
            self.repo = InventoryRepository(conn)
        else:
            self.conn = get_db_connection(db_path)
            init_schema(self.conn)
            seed_default_catalog(self.conn)
            self.repo = InventoryRepository(self.conn)

        self.state = CharacterState(db_repo=self.repo)
        self.controller = self
        self.root: tk.Tk | None = None
        self.window: Any = None

    def new_character(self) -> Character:
        """Reset state with a fresh Human Wild Card."""
        self.state.character = Character(
            name="",
            concept="",
            ancestry=get_ancestry("Human"),
            rank=Rank.NOVICE,
            cash=STARTING_CASH,
            bennies=BASE_BENNIES,
        )
        self.state.notify_listeners("reset")
        return self.state.character

    def save_character(self) -> None:
        """Persist current character to database."""
        self.state.save_to_db(self.repo)

    def load_character(self, character_id: str) -> None:
        """Load character from database by ID."""
        self.state.load_from_db(character_id, self.repo)

    def export_xml(self, file_path: Path | str) -> None:
        """Export character to canonical XML file."""
        self.state.export_to_xml(file_path)

    def import_xml(self, file_path: Path | str) -> None:
        """Import character from canonical XML file."""
        self.state.import_from_xml(file_path)


def create_app(db_path: str = ":memory:", headless: bool = False) -> AppController:
    """Application factory initializing database, AppController, and GUI (if not headless)."""
    controller = AppController(db_path=db_path)

    if headless:
        return controller

    # Initialize graphical Tkinter interface
    root = tk.Tk()
    root.title("Savage Worlds Character Generator (SWADE)")
    root.geometry("1024x720")

    try:
        from swchar.ui.main_window import MainWindow
        from swchar.ui.theme import setup_theme

        setup_theme(root)
        main_window = MainWindow(
            root=root,
            state=controller.state,
            repo=controller.repo,
            controller=controller,
        )
        controller.window = main_window
    except Exception:
        pass

    controller.root = root
    return controller


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the desktop application."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="swchar",
        description="Savage Worlds Adventure Edition Character Generator",
    )
    parser.add_argument(
        "--db",
        default="data/swchar.db",
        help="Path to SQLite database file (default: data/swchar.db)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless test mode without graphical desktop display",
    )

    args = parser.parse_args(argv)

    app = create_app(db_path=args.db, headless=args.headless)
    if not args.headless and app.root is not None:
        try:
            app.root.mainloop()
        except KeyboardInterrupt:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
