"""Hindrances & Edges selection and disadvantage reward redemption tab."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from swchar.models.edges import EDGES
from swchar.models.hindrances import HINDRANCES, HindranceSeverity

if TYPE_CHECKING:
    from swchar.app import CharacterState


class HindrancesEdgesTab(ttk.Frame):
    """Tab 3: Hindrance disadvantage economy and Edge prerequisite checking."""

    def __init__(self, parent: tk.Misc, state: "CharacterState") -> None:
        super().__init__(parent, padding=15)
        self.state = state

        self._build_ui()
        self.state.add_listener(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the UI widgets."""
        header = ttk.Label(self, text="Hindrances & Edges", style="Title.TLabel")
        header.pack(anchor="w", pady=(0, 15))

        split = ttk.Frame(self)
        split.pack(fill="both", expand=True)

        # Left Column: Hindrances & Economy
        hind_card = ttk.LabelFrame(split, text="Hindrances & Rewards", padding=12)
        hind_card.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Economy Banner
        self.economy_label = ttk.Label(
            hind_card, text="Hindrance Points: 0 earned | 0 usable | 0 remaining", style="Badge.TLabel"
        )
        self.economy_label.pack(anchor="w", pady=(0, 10))

        # Hindrances Treeview
        htree_frame = ttk.Frame(hind_card)
        htree_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.hind_tree = ttk.Treeview(htree_frame, columns=("Name", "Severity"), show="headings", height=6)
        self.hind_tree.heading("Name", text="Hindrance")
        self.hind_tree.heading("Severity", text="Severity")
        self.hind_tree.column("Name", width=140)
        self.hind_tree.column("Severity", width=80, anchor="center")

        h_scroll = ttk.Scrollbar(htree_frame, orient="vertical", command=self.hind_tree.yview)
        self.hind_tree.configure(yscrollcommand=h_scroll.set)
        self.hind_tree.pack(side="left", fill="both", expand=True)
        h_scroll.pack(side="right", fill="y")

        # Add / Remove Hindrance Picker
        h_ctrl = ttk.Frame(hind_card)
        h_ctrl.pack(fill="x", pady=5)

        self.hind_choice_var = tk.StringVar()
        self.hind_combo = ttk.Combobox(
            h_ctrl,
            textvariable=self.hind_choice_var,
            values=sorted(list(HINDRANCES.keys())),
            width=18,
            state="readonly",
        )
        self.hind_combo.pack(side="left", padx=2)

        self.hind_sev_var = tk.StringVar(value="Minor")
        self.hind_sev_combo = ttk.Combobox(
            h_ctrl,
            textvariable=self.hind_sev_var,
            values=["Minor", "Major"],
            width=7,
            state="readonly",
        )
        self.hind_sev_combo.pack(side="left", padx=2)

        ttk.Button(h_ctrl, text="Add", command=self._add_hindrance).pack(side="left", padx=2)
        ttk.Button(h_ctrl, text="Remove", command=self._remove_hindrance).pack(side="right", padx=2)

        # Rewards Redemptions
        ttk.Separator(hind_card, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(hind_card, text="Redeem Usable Points:", style="Header.TLabel").pack(anchor="w", pady=(0, 5))

        r_grid = ttk.Frame(hind_card)
        r_grid.pack(fill="x")

        ttk.Button(
            r_grid, text="+1 Attribute (2 pts)", command=lambda: self._redeem("attribute")
        ).grid(row=0, column=0, padx=3, pady=3, sticky="ew")
        ttk.Button(
            r_grid, text="+1 Skill (1 pt)", command=lambda: self._redeem("skill")
        ).grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        ttk.Button(
            r_grid, text="+1 Edge (2 pts)", command=lambda: self._redeem("edge")
        ).grid(row=1, column=0, padx=3, pady=3, sticky="ew")
        ttk.Button(
            r_grid, text="+$500 Cash (1 pt)", command=lambda: self._redeem("cash")
        ).grid(row=1, column=1, padx=3, pady=3, sticky="ew")
        r_grid.columnconfigure(0, weight=1)
        r_grid.columnconfigure(1, weight=1)

        # Right Column: Edges & Prerequisites
        edge_card = ttk.LabelFrame(split, text="Edges", padding=12)
        edge_card.pack(side="right", fill="both", expand=True)

        # Edges Treeview
        etree_frame = ttk.Frame(edge_card)
        etree_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.edge_tree = ttk.Treeview(etree_frame, columns=("Name", "Category"), show="headings", height=8)
        self.edge_tree.heading("Name", text="Edge Name")
        self.edge_tree.heading("Category", text="Category")
        self.edge_tree.column("Name", width=140)
        self.edge_tree.column("Category", width=100)

        e_scroll = ttk.Scrollbar(etree_frame, orient="vertical", command=self.edge_tree.yview)
        self.edge_tree.configure(yscrollcommand=e_scroll.set)
        self.edge_tree.pack(side="left", fill="both", expand=True)
        e_scroll.pack(side="right", fill="y")

        # Edge Picker
        e_ctrl = ttk.Frame(edge_card)
        e_ctrl.pack(fill="x", pady=5)

        self.edge_choice_var = tk.StringVar()
        self.edge_combo = ttk.Combobox(
            e_ctrl,
            textvariable=self.edge_choice_var,
            values=sorted(list(EDGES.keys())),
            width=22,
            state="readonly",
        )
        self.edge_combo.pack(side="left", padx=2)
        self.edge_combo.bind("<<ComboboxSelected>>", self._on_edge_selected)

        ttk.Button(e_ctrl, text="Add Edge", command=self._add_edge).pack(side="left", padx=2)
        ttk.Button(e_ctrl, text="Remove", command=self._remove_edge).pack(side="right", padx=2)

        # Prerequisite hint label
        self.edge_hint_label = ttk.Label(edge_card, text="", wraplength=350, style="Muted.TLabel")
        self.edge_hint_label.pack(fill="x", pady=5)

    def _add_hindrance(self) -> None:
        name = self.hind_choice_var.get().strip()
        if not name:
            return
        sev_str = self.hind_sev_var.get().strip()
        sev = HindranceSeverity.MAJOR if sev_str.lower() == "major" else HindranceSeverity.MINOR
        self.state.add_hindrance(name, severity=sev)

    def _remove_hindrance(self) -> None:
        selected = self.hind_tree.selection()
        if not selected:
            return
        vals = self.hind_tree.item(selected[0], "values")
        if vals:
            self.state.remove_hindrance(str(vals[0]))

    def _redeem(self, r_type: str) -> None:
        success = self.state.redeem_hindrance_reward(r_type, count=1)
        if not success:
            messagebox.showwarning(
                "Insufficient Points", "You do not have enough remaining usable hindrance points."
            )

    def _on_edge_selected(self, *args: object) -> None:
        selected = self.edge_choice_var.get().strip()
        if not selected:
            self.edge_hint_label.configure(text="")
            return
        can_take, reasons = self.state.can_take_edge(selected)
        if can_take:
            self.edge_hint_label.configure(
                text=f"Prerequisites satisfied for {selected}.", foreground="green"
            )
        else:
            reason_str = "; ".join(reasons)
            self.edge_hint_label.configure(
                text=f"Cannot take {selected}: {reason_str}", foreground="red"
            )

    def _add_edge(self) -> None:
        selected = self.edge_choice_var.get().strip()
        if not selected:
            return
        success = self.state.add_edge(selected)
        if not success:
            can_take, reasons = self.state.can_take_edge(selected)
            msg = "; ".join(reasons) if reasons else "Prerequisites not met."
            messagebox.showwarning("Prerequisites Unmet", f"Cannot add {selected}: {msg}")

    def _remove_edge(self) -> None:
        selected = self.edge_tree.selection()
        if not selected:
            return
        vals = self.edge_tree.item(selected[0], "values")
        if vals:
            self.state.remove_edge(str(vals[0]))

    def _on_state_change(self, event: str = "") -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Update Hindrance economy and Edge list."""
        # 1. Update Economy
        econ = self.state.get_hindrance_economy()
        self.economy_label.configure(
            text=(
                f"Hindrance Points: {econ.total_earned} earned | "
                f"{econ.usable_points} usable | {econ.remaining_points} remaining"
            )
        )

        # 2. Update Hindrances Tree
        self.hind_tree.delete(*self.hind_tree.get_children())
        for h in self.state.character.hindrances:
            hname = h.name if hasattr(h, "name") else str(h)
            sev = h.severity.value if hasattr(h, "severity") and hasattr(h.severity, "value") else str(getattr(h, "severity", "Minor"))
            self.hind_tree.insert("", "end", values=(hname, sev))

        # 3. Update Edges Tree
        self.edge_tree.delete(*self.edge_tree.get_children())
        for e in self.state.character.edges:
            ename = e.name if hasattr(e, "name") else str(e)
            cat = "General"
            if ename in EDGES:
                cat = EDGES[ename].category.value
            self.edge_tree.insert("", "end", values=(ename, cat))

        # Re-evaluate selected edge prerequisite label
        if self.edge_choice_var.get().strip():
            self._on_edge_selected()
