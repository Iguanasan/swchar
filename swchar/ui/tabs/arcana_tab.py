"""Arcana & supernatural powers configuration tab."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from swchar.models.arcana import ArcaneBackgroundType, Power

if TYPE_CHECKING:
    from swchar.app import CharacterState


class ArcanaTab(ttk.Frame):
    """Tab 4: Arcane Background and supernatural power configuration."""

    def __init__(self, parent: tk.Misc, state: "CharacterState") -> None:
        super().__init__(parent, padding=15)
        self.state = state

        self._build_ui()
        self.state.add_listener(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the UI widgets."""
        header = ttk.Label(self, text="Arcana & Powers", style="Title.TLabel")
        header.pack(anchor="w", pady=(0, 15))

        # Arcane Background Card
        bg_card = ttk.LabelFrame(self, text="Arcane Background Setup", padding=12)
        bg_card.pack(fill="x", pady=(0, 15))

        row1 = ttk.Frame(bg_card)
        row1.pack(fill="x", pady=5)

        ttk.Label(row1, text="Arcane Background:", width=18).pack(side="left")
        self.bg_var = tk.StringVar(value="None")
        bg_options = [b.value for b in ArcaneBackgroundType]
        self.bg_combo = ttk.Combobox(row1, textvariable=self.bg_var, values=bg_options, state="readonly", width=20)
        self.bg_combo.pack(side="left", padx=5)
        self.bg_combo.bind("<<ComboboxSelected>>", self._on_bg_selected)

        ttk.Label(row1, text="Power Points:", width=14).pack(side="left", padx=(15, 0))
        self.pp_var = tk.StringVar(value="0")
        self.pp_label = ttk.Label(row1, textvariable=self.pp_var, style="Badge.TLabel", width=8)
        self.pp_label.pack(side="left")

        # Powers Management Card
        powers_card = ttk.LabelFrame(self, text="Known Supernatural Powers", padding=12)
        powers_card.pack(fill="both", expand=True)

        # Powers Treeview
        tree_frame = ttk.Frame(powers_card)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("Name", "Points", "Trappings", "Range", "Damage")
        self.powers_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        self.powers_tree.heading("Name", text="Power Name")
        self.powers_tree.heading("Points", text="PP")
        self.powers_tree.heading("Trappings", text="Trappings")
        self.powers_tree.heading("Range", text="Range")
        self.powers_tree.heading("Damage", text="Damage")

        self.powers_tree.column("Name", width=130)
        self.powers_tree.column("Points", width=50, anchor="center")
        self.powers_tree.column("Trappings", width=150)
        self.powers_tree.column("Range", width=90)
        self.powers_tree.column("Damage", width=90)

        p_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.powers_tree.yview)
        self.powers_tree.configure(yscrollcommand=p_scroll.set)
        self.powers_tree.pack(side="left", fill="both", expand=True)
        p_scroll.pack(side="right", fill="y")

        # Add Power Form
        form_frame = ttk.LabelFrame(powers_card, text="Add Power", padding=8)
        form_frame.pack(fill="x", pady=5)

        f_row = ttk.Frame(form_frame)
        f_row.pack(fill="x", pady=2)

        ttk.Label(f_row, text="Name:").pack(side="left")
        self.p_name_var = tk.StringVar()
        ttk.Entry(f_row, textvariable=self.p_name_var, width=14).pack(side="left", padx=3)

        ttk.Label(f_row, text="PP:").pack(side="left", padx=(5, 0))
        self.p_pp_var = tk.StringVar(value="1")
        ttk.Entry(f_row, textvariable=self.p_pp_var, width=4).pack(side="left", padx=3)

        ttk.Label(f_row, text="Trappings:").pack(side="left", padx=(5, 0))
        self.p_trap_var = tk.StringVar()
        ttk.Entry(f_row, textvariable=self.p_trap_var, width=16).pack(side="left", padx=3)

        ttk.Label(f_row, text="Range:").pack(side="left", padx=(5, 0))
        self.p_range_var = tk.StringVar()
        ttk.Entry(f_row, textvariable=self.p_range_var, width=10).pack(side="left", padx=3)

        ttk.Label(f_row, text="Damage:").pack(side="left", padx=(5, 0))
        self.p_dmg_var = tk.StringVar()
        ttk.Entry(f_row, textvariable=self.p_dmg_var, width=8).pack(side="left", padx=3)

        ttk.Button(f_row, text="Add Power", command=self._add_power).pack(side="left", padx=8)
        ttk.Button(f_row, text="Remove Selected", command=self._remove_power).pack(side="right", padx=5)

    def _on_bg_selected(self, *args: object) -> None:
        val = self.bg_var.get()
        self.state.set_arcane_background(val)

    def _add_power(self) -> None:
        name = self.p_name_var.get().strip()
        if not name:
            return
        try:
            pp = int(self.p_pp_var.get().strip() or "1")
        except ValueError:
            pp = 1

        power = Power(
            name=name,
            power_points=pp,
            trappings=self.p_trap_var.get().strip(),
            range=self.p_range_var.get().strip(),
            damage=self.p_dmg_var.get().strip(),
        )
        self.state.add_power(power)
        self.p_name_var.set("")
        self.p_trap_var.set("")
        self.p_range_var.set("")
        self.p_dmg_var.set("")

    def _remove_power(self) -> None:
        selected = self.powers_tree.selection()
        if not selected:
            return
        vals = self.powers_tree.item(selected[0], "values")
        if vals:
            self.state.remove_power(str(vals[0]))

    def _on_state_change(self, event: str = "") -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Update Arcana and power lists."""
        arcana = self.state.character.arcana
        if arcana and arcana.background and arcana.background.lower() != "none":
            self.bg_var.set(arcana.background)
            self.pp_var.set(str(arcana.power_points))
        else:
            self.bg_var.set("None")
            self.pp_var.set("0")

        self.powers_tree.delete(*self.powers_tree.get_children())
        for p in self.state.get_powers():
            self.powers_tree.insert(
                "",
                "end",
                values=(p.name, p.power_points, p.trappings, p.range, p.damage),
            )
