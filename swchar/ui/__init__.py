"""Desktop graphical interface components for the Savage Worlds Character Builder."""

from swchar.ui.main_window import MainWindow
from swchar.ui.theme import (
    ThemeMode,
    ThemeName,
    ThemePalette,
    apply_theme,
    get_available_themes,
    get_current_theme,
    get_theme_palette,
    setup_theme,
)
from swchar.ui.controller import AppController, CharacterState
from swchar.ui.tabs.concept_tab import ConceptTab
from swchar.ui.tabs.traits_tab import TraitsTab
from swchar.ui.tabs.hindrances_edges_tab import HindrancesEdgesTab
from swchar.ui.tabs.arcana_tab import ArcanaTab
from swchar.ui.tabs.inventory_tab import InventoryTab
from swchar.ui.tabs.summary_tab import SummaryTab

__all__ = [
    "MainWindow",
    "ThemeName",
    "ThemeMode",
    "ThemePalette",
    "apply_theme",
    "get_available_themes",
    "get_current_theme",
    "get_theme_palette",
    "setup_theme",
    "AppController",
    "CharacterState",
    "ConceptTab",
    "TraitsTab",
    "HindrancesEdgesTab",
    "ArcanaTab",
    "InventoryTab",
    "SummaryTab",
]
