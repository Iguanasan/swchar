"""Desktop graphical interface components for the Savage Worlds Character Builder."""

from swchar.ui.main_window import MainWindow
from swchar.ui.theme import setup_theme
from swchar.ui.controller import AppController, CharacterState
from swchar.ui.tabs.concept_tab import ConceptTab
from swchar.ui.tabs.traits_tab import TraitsTab
from swchar.ui.tabs.hindrances_edges_tab import HindrancesEdgesTab
from swchar.ui.tabs.arcana_tab import ArcanaTab
from swchar.ui.tabs.inventory_tab import InventoryTab
from swchar.ui.tabs.summary_tab import SummaryTab

__all__ = [
    "MainWindow",
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
