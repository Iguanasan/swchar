"""Item catalog and character inventory domain models for Savage Worlds Adventure Edition."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ItemCategory(str, Enum):
    """Canonical equipment categories in SWADE."""

    MELEE_WEAPON = "Melee Weapon"
    RANGED_WEAPON = "Ranged Weapon"
    ARMOR = "Armor"
    SHIELD = "Shield"
    ADVENTURING_GEAR = "Adventuring Gear"
    AMMO = "Ammo"


@dataclass
class CatalogItem:
    """Master catalog item definition for equipment and gear."""

    name: str = ""
    category: str | ItemCategory = ItemCategory.ADVENTURING_GEAR
    cost: float = 0.0
    weight: float = 0.0
    id: int | None = None
    min_str: str | None = None
    damage: str | None = None
    range: str | None = None
    armor_bonus: int = 0
    parry_bonus: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        """Normalize category string and min_str representation."""
        if isinstance(self.category, ItemCategory):
            self.category = self.category.value
        if self.min_str is not None and not isinstance(self.min_str, str):
            self.min_str = str(self.min_str)


@dataclass
class InventoryItem:
    """Personal inventory item attached to a character with quantity and equipment state."""

    name: str = ""
    category: str | ItemCategory = ItemCategory.ADVENTURING_GEAR
    cost: float = 0.0
    weight: float = 0.0
    quantity: int = 1
    is_equipped: bool = False
    id: int | None = None
    character_id: str | None = None
    catalog_item_id: int | None = None
    min_str: str | None = None
    damage: str | None = None
    range: str | None = None
    armor_bonus: int = 0
    parry_bonus: int = 0
    notes: str = ""
    custom_name: str = ""

    def __post_init__(self) -> None:
        """Synchronize name and custom_name, and normalize fields."""
        if self.custom_name and not self.name:
            self.name = self.custom_name
        elif self.name and not self.custom_name:
            self.custom_name = self.name
        if isinstance(self.category, ItemCategory):
            self.category = self.category.value
        if self.min_str is not None and not isinstance(self.min_str, str):
            self.min_str = str(self.min_str)
        self._initialized = True

    def __setattr__(self, key: str, value: Any) -> None:
        """Keep name and custom_name attributes synchronized."""
        super().__setattr__(key, value)
        if getattr(self, "_initialized", False):
            if key == "name":
                super().__setattr__("custom_name", value)
            elif key == "custom_name":
                super().__setattr__("name", value)

    @classmethod
    def from_catalog_item(
        cls,
        catalog_item: CatalogItem,
        quantity: int = 1,
        is_equipped: bool = False,
        character_id: str | None = None,
    ) -> "InventoryItem":
        """Instantiate an InventoryItem copied from a CatalogItem."""
        return cls(
            name=catalog_item.name,
            custom_name=catalog_item.name,
            category=catalog_item.category,
            cost=catalog_item.cost,
            weight=catalog_item.weight,
            quantity=quantity,
            is_equipped=is_equipped,
            catalog_item_id=catalog_item.id,
            character_id=character_id,
            min_str=catalog_item.min_str,
            damage=catalog_item.damage,
            range=catalog_item.range,
            armor_bonus=catalog_item.armor_bonus,
            parry_bonus=catalog_item.parry_bonus,
            notes=catalog_item.notes,
        )

    @property
    def total_weight(self) -> float:
        """Total weight of this inventory item slot."""
        return self.weight * self.quantity

    @property
    def total_cost(self) -> float:
        """Total cost value of this inventory item slot."""
        return self.cost * self.quantity
