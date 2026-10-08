"""Concept & Ancestry selection tab."""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from swchar.models.ancestry import ANCESTRIES

if TYPE_CHECKING:
    from swchar.app import CharacterState


class ConceptTab(ttk.Frame):
    """Tab 1: Character identity, archetype concept, and ancestry selection."""

    def __init__(self, parent: tk.Misc, state: "CharacterState") -> None:
        super().__init__(parent, padding=15)
        self.state = state

        self._updating = False
        self._build_ui()
        self.state.add_listener(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the UI widgets."""
        # Header
        header = ttk.Label(self, text="Character Concept & Ancestry", style="Title.TLabel")
        header.pack(anchor="w", pady=(0, 15))

        # Identity Card
        card = ttk.LabelFrame(self, text="Identity & Archetype", padding=12)
        card.pack(fill="x", pady=(0, 15))

        # Name field
        row1 = ttk.Frame(card)
        row1.pack(fill="x", pady=5)
        ttk.Label(row1, text="Character Name:", width=18).pack(side="left")
        self.name_var = tk.StringVar(value=self.state.character.name)
        self.name_var.trace_add("write", self._on_name_change)
        self.name_entry = ttk.Entry(row1, textvariable=self.name_var, width=35)
        self.name_entry.pack(side="left", fill="x", expand=True)

        # Concept field
        row2 = ttk.Frame(card)
        row2.pack(fill="x", pady=5)
        ttk.Label(row2, text="Concept / Archetype:", width=18).pack(side="left")
        self.concept_var = tk.StringVar(value=self.state.character.concept)
        self.concept_var.trace_add("write", self._on_concept_change)
        self.concept_entry = ttk.Entry(row2, textvariable=self.concept_var, width=35)
        self.concept_entry.pack(side="left", fill="x", expand=True)

        # Ancestry Card
        anc_card = ttk.LabelFrame(self, text="Ancestry & Racial Traits", padding=12)
        anc_card.pack(fill="both", expand=True)

        row3 = ttk.Frame(anc_card)
        row3.pack(fill="x", pady=5)
        ttk.Label(row3, text="Select Ancestry:", width=18).pack(side="left")
        self.ancestry_var = tk.StringVar(
            value=self.state.character.ancestry.name if self.state.character.ancestry else "Human"
        )
        self.ancestry_combo = ttk.Combobox(
            row3,
            textvariable=self.ancestry_var,
            values=list(ANCESTRIES.keys()),
            state="readonly",
            width=33,
        )
        self.ancestry_combo.pack(side="left")
        self.ancestry_combo.bind("<<ComboboxSelected>>", self._on_ancestry_selected)

        # Racial Traits Display
        ttk.Label(anc_card, text="Ancestral Traits & Modifiers:", style="Header.TLabel").pack(
            anchor="w", pady=(15, 5)
        )

        self.traits_text = tk.Text(anc_card, height=12, wrap="word", relief="solid", borderwidth=1)
        self.traits_text.pack(fill="both", expand=True, pady=5)
        self.traits_text.configure(state="disabled")

    def _on_name_change(self, *args: object) -> None:
        if not self._updating:
            self.state.set_name(self.name_var.get())

    def _on_concept_change(self, *args: object) -> None:
        if not self._updating:
            self.state.set_concept(self.concept_var.get())

    def _on_ancestry_selected(self, *args: object) -> None:
        selected = self.ancestry_var.get()
        if selected:
            self.state.set_ancestry(selected)

    def _on_state_change(self, event: str = "") -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Synchronize UI with character state."""
        self._updating = True
        try:
            char = self.state.character
            if self.name_var.get() != char.name:
                self.name_var.set(char.name)
            if self.concept_var.get() != char.concept:
                self.concept_var.set(char.concept)
            if char.ancestry and self.ancestry_var.get() != char.ancestry.name:
                self.ancestry_var.set(char.ancestry.name)

            # Format traits
            anc = char.ancestry
            lines: list[str] = []
            if anc:
                lines.append(f"Ancestry: {anc.name}")
                lines.append(f"Base Pace: {anc.pace} | Running Die: {anc.running_die} | Size: {anc.size}")
                if anc.free_edge_count > 0:
                    lines.append(f"Free Edges at Creation: {anc.free_edge_count}")
                if anc.armor_bonus > 0:
                    lines.append(f"Natural Armor: +{anc.armor_bonus}")
                if anc.bennies_bonus > 0:
                    lines.append(f"Bonus Bennies: +{anc.bennies_bonus}")
                lines.append("-" * 50)
                lines.append("Traits:")
                for trait in getattr(anc, "traits", []):
                    desc = f": {trait.description}" if trait.description else ""
                    lines.append(f" * {trait.name}{desc}")

            self.traits_text.configure(state="normal")
            self.traits_text.delete("1.0", "end")
            self.traits_text.insert("1.0", "\n".join(lines))
            self.traits_text.configure(state="disabled")
        finally:
            self._updating = False
