"""Attributes & Skills point-buy allocation tab."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName

if TYPE_CHECKING:
    from swchar.app import CharacterState


class TraitsTab(ttk.Frame):
    """Tab 2: Point-buy trait progression with live budget accounting."""

    def __init__(self, parent: tk.Misc, state: "CharacterState") -> None:
        super().__init__(parent, padding=15)
        self.state = state

        self.attr_labels: dict[AttributeName, ttk.Label] = {}
        self._build_ui()
        self.state.add_listener(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the UI widgets."""
        # Header & Live Budgets Banner
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=(0, 15))

        header = ttk.Label(top_frame, text="Traits: Attributes & Skills", style="Title.TLabel")
        header.pack(side="left")

        # Budget labels
        budgets_frame = ttk.Frame(top_frame)
        budgets_frame.pack(side="right")

        self.attr_budget_label = ttk.Label(
            budgets_frame, text="Attr Points: 0 / 5 (5 remaining)", style="Badge.TLabel"
        )
        self.attr_budget_label.pack(side="left", padx=10)

        self.skill_budget_label = ttk.Label(
            budgets_frame, text="Skill Points: 0 / 12 (12 remaining)", style="Badge.TLabel"
        )
        self.skill_budget_label.pack(side="left", padx=10)

        # Split pane for Attributes and Skills
        split_frame = ttk.Frame(self)
        split_frame.pack(fill="both", expand=True)

        # Left Column: Attributes
        attr_card = ttk.LabelFrame(split_frame, text="Attributes (5 Base Points)", padding=12)
        attr_card.pack(side="left", fill="both", expand=False, padx=(0, 10))

        for attr in [
            AttributeName.AGILITY,
            AttributeName.SMARTS,
            AttributeName.SPIRIT,
            AttributeName.STRENGTH,
            AttributeName.VIGOR,
        ]:
            row = ttk.Frame(attr_card)
            row.pack(fill="x", pady=8)

            lbl = ttk.Label(row, text=f"{attr.value}:", width=12, style="Header.TLabel")
            lbl.pack(side="left")

            btn_down = ttk.Button(row, text="-", width=3, command=lambda a=attr: self._step_attr(a, -1))
            btn_down.pack(side="left", padx=3)

            val_lbl = ttk.Label(row, text="d4", width=5, anchor="center", style="Stat.TLabel")
            val_lbl.pack(side="left", padx=5)
            self.attr_labels[attr] = val_lbl

            btn_up = ttk.Button(row, text="+", width=3, command=lambda a=attr: self._step_attr(a, 1))
            btn_up.pack(side="left", padx=3)

        # Right Column: Skills
        skill_card = ttk.LabelFrame(split_frame, text="Skills (12 Base Points)", padding=12)
        skill_card.pack(side="right", fill="both", expand=True)

        # Skills Treeview
        tree_frame = ttk.Frame(skill_card)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))

        columns = ("Name", "Attribute", "Die", "Core")
        self.skills_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        self.skills_tree.heading("Name", text="Skill Name")
        self.skills_tree.heading("Attribute", text="Linked Attribute")
        self.skills_tree.heading("Die", text="Current Die")
        self.skills_tree.heading("Core", text="Core Skill")

        self.skills_tree.column("Name", width=140)
        self.skills_tree.column("Attribute", width=110)
        self.skills_tree.column("Die", width=80, anchor="center")
        self.skills_tree.column("Core", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.skills_tree.yview)
        self.skills_tree.configure(yscrollcommand=scrollbar.set)
        self.skills_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Controls under treeview
        ctrl_frame = ttk.Frame(skill_card)
        ctrl_frame.pack(fill="x")

        ttk.Button(ctrl_frame, text="Step -", command=lambda: self._step_selected_skill(-1)).pack(
            side="left", padx=3
        )
        ttk.Button(ctrl_frame, text="Step +", command=lambda: self._step_selected_skill(1)).pack(
            side="left", padx=3
        )

        ttk.Separator(ctrl_frame, orient="vertical").pack(side="left", fill="y", padx=10)

        # Add custom skill inline
        ttk.Label(ctrl_frame, text="New Skill:").pack(side="left", padx=(5, 2))
        self.new_skill_var = tk.StringVar()
        self.new_skill_entry = ttk.Entry(ctrl_frame, textvariable=self.new_skill_var, width=14)
        self.new_skill_entry.pack(side="left", padx=3)

        self.new_skill_attr_var = tk.StringVar(value="Agility")
        self.new_skill_attr_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.new_skill_attr_var,
            values=[a.value for a in AttributeName],
            width=9,
            state="readonly",
        )
        self.new_skill_attr_combo.pack(side="left", padx=3)

        ttk.Button(ctrl_frame, text="Add", command=self._add_custom_skill).pack(side="left", padx=3)
        ttk.Button(ctrl_frame, text="Remove", command=self._remove_selected_skill).pack(
            side="right", padx=3
        )

    def _step_attr(self, attr: AttributeName, delta: int) -> None:
        self.state.step_attribute(attr, delta)

    def _step_selected_skill(self, delta: int) -> None:
        selected = self.skills_tree.selection()
        if not selected:
            return
        item_values = self.skills_tree.item(selected[0], "values")
        if item_values:
            skill_name = str(item_values[0])
            self.state.step_skill(skill_name, delta)

    def _add_custom_skill(self) -> None:
        name = self.new_skill_var.get().strip()
        if not name:
            return
        attr_name = self.new_skill_attr_var.get().strip()
        attr_enum = next((a for a in AttributeName if a.value.lower() == attr_name.lower()), AttributeName.AGILITY)
        self.state.set_skill(name, DieType.D4, attribute=attr_enum, core=False)
        self.new_skill_var.set("")

    def _remove_selected_skill(self) -> None:
        selected = self.skills_tree.selection()
        if not selected:
            return
        item_values = self.skills_tree.item(selected[0], "values")
        if item_values:
            skill_name = str(item_values[0])
            skill = self.state.character.get_skill(skill_name)
            if skill and skill.core:
                messagebox.showwarning("Core Skill", "Core skills cannot be removed.")
                return
            self.state.remove_skill(skill_name)

    def _on_state_change(self, event: str = "") -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Update live budget counters, attribute values, and skill list."""
        # 1. Update Attributes
        for attr, lbl in self.attr_labels.items():
            die = self.state.character.attributes[attr]
            lbl.configure(text=str(die))

        # 2. Update Budgets
        attr_spent = self.state.get_attribute_points_spent()
        attr_avail = self.state.get_attribute_points_available()
        attr_rem = self.state.get_attribute_points_remaining()
        self.attr_budget_label.configure(
            text=f"Attr Points: {attr_spent} / {attr_avail} ({attr_rem} remaining)"
        )

        skill_spent = self.state.get_skill_points_spent()
        skill_avail = self.state.get_skill_points_available()
        skill_rem = self.state.get_skill_points_remaining()
        self.skill_budget_label.configure(
            text=f"Skill Points: {skill_spent} / {skill_avail} ({skill_rem} remaining)"
        )

        # 3. Update Skills Treeview
        selected_id = self.skills_tree.selection()
        selected_name = None
        if selected_id:
            vals = self.skills_tree.item(selected_id[0], "values")
            if vals:
                selected_name = vals[0]

        self.skills_tree.delete(*self.skills_tree.get_children())
        for skill in self.state.character.skills.values():
            core_str = "Yes" if skill.core else "No"
            attr_str = skill.attribute.value if hasattr(skill.attribute, "value") else str(skill.attribute)
            iid = self.skills_tree.insert(
                "",
                "end",
                values=(skill.name, attr_str, str(skill.die), core_str),
            )
            if selected_name and skill.name == selected_name:
                self.skills_tree.selection_set(iid)
