"""Inventory management and equipment catalog browser tab."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from swchar.models.items import ItemCategory

if TYPE_CHECKING:
    from swchar.app import CharacterState
    from swchar.db.repository import InventoryRepository


class InventoryTab(ttk.Frame):
    """Tab 5: SQLite equipment catalog browser, equip toggles, and encumbrance meter."""

    def __init__(
        self,
        parent: tk.Misc,
        state: "CharacterState",
        repo: "InventoryRepository | None" = None,
    ) -> None:
        super().__init__(parent, padding=15)
        self.state = state
        self.repo = repo or getattr(state, "db_repo", None)

        self._build_ui()
        self.state.add_listener(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the UI widgets."""
        # Header & Status Indicators
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=(0, 15))

        header = ttk.Label(top_frame, text="Inventory & Equipment", style="Title.TLabel")
        header.pack(side="left")

        stats_frame = ttk.Frame(top_frame)
        stats_frame.pack(side="right")

        self.cash_label = ttk.Label(stats_frame, text="Cash: $500.00", style="Badge.TLabel")
        self.cash_label.pack(side="left", padx=10)

        self.weight_label = ttk.Label(stats_frame, text="Weight: 0.0 / 20.0 lbs", style="Badge.TLabel")
        self.weight_label.pack(side="left", padx=10)

        self.encumb_label = ttk.Label(stats_frame, text="Penalty: 0", style="Badge.TLabel")
        self.encumb_label.pack(side="left", padx=10)

        # Split: Catalog (Left) and Character Inventory (Right)
        split = ttk.Frame(self)
        split.pack(fill="both", expand=True)

        # Left Column: Catalog Browser
        cat_card = ttk.LabelFrame(split, text="Master Catalog", padding=10)
        cat_card.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Filter bar
        filter_bar = ttk.Frame(cat_card)
        filter_bar.pack(fill="x", pady=(0, 8))

        ttk.Label(filter_bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(filter_bar, textvariable=self.search_var, width=14)
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self._search_catalog())

        self.cat_choice_var = tk.StringVar(value="All")
        cat_values = ["All"] + [c.value for c in ItemCategory]
        self.cat_combo = ttk.Combobox(
            filter_bar,
            textvariable=self.cat_choice_var,
            values=cat_values,
            width=14,
            state="readonly",
        )
        self.cat_combo.pack(side="left", padx=4)
        self.cat_combo.bind("<<ComboboxSelected>>", lambda e: self._search_catalog())

        ttk.Button(filter_bar, text="Filter", command=self._search_catalog).pack(side="left", padx=2)

        # Catalog Treeview
        cat_tree_frame = ttk.Frame(cat_card)
        cat_tree_frame.pack(fill="both", expand=True, pady=(0, 8))

        cat_cols = ("Name", "Category", "Cost", "Weight", "Notes")
        self.cat_tree = ttk.Treeview(cat_tree_frame, columns=cat_cols, show="headings", height=10)
        self.cat_tree.heading("Name", text="Item")
        self.cat_tree.heading("Category", text="Category")
        self.cat_tree.heading("Cost", text="Cost")
        self.cat_tree.heading("Weight", text="Wt (lbs)")
        self.cat_tree.heading("Notes", text="Notes")

        self.cat_tree.column("Name", width=120)
        self.cat_tree.column("Category", width=95)
        self.cat_tree.column("Cost", width=60, anchor="e")
        self.cat_tree.column("Weight", width=55, anchor="e")
        self.cat_tree.column("Notes", width=100)

        c_scroll = ttk.Scrollbar(cat_tree_frame, orient="vertical", command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=c_scroll.set)
        self.cat_tree.pack(side="left", fill="both", expand=True)
        c_scroll.pack(side="right", fill="y")

        # Purchase Button
        ttk.Button(cat_card, text="Purchase Selected Item", command=self._purchase_item).pack(
            anchor="e"
        )

        # Right Column: Character Inventory
        inv_card = ttk.LabelFrame(split, text="Carried Inventory", padding=10)
        inv_card.pack(side="right", fill="both", expand=True)

        inv_tree_frame = ttk.Frame(inv_card)
        inv_tree_frame.pack(fill="both", expand=True, pady=(0, 8))

        inv_cols = ("Name", "Category", "Qty", "Cost", "Weight", "Equipped")
        self.inv_tree = ttk.Treeview(inv_tree_frame, columns=inv_cols, show="headings", height=10)
        self.inv_tree.heading("Name", text="Item")
        self.inv_tree.heading("Category", text="Category")
        self.inv_tree.heading("Qty", text="Qty")
        self.inv_tree.heading("Cost", text="Cost")
        self.inv_tree.heading("Weight", text="Total Wt")
        self.inv_tree.heading("Equipped", text="Equipped")

        self.inv_tree.column("Name", width=120)
        self.inv_tree.column("Category", width=95)
        self.inv_tree.column("Qty", width=40, anchor="center")
        self.inv_tree.column("Cost", width=55, anchor="e")
        self.inv_tree.column("Weight", width=60, anchor="e")
        self.inv_tree.column("Equipped", width=65, anchor="center")

        i_scroll = ttk.Scrollbar(inv_tree_frame, orient="vertical", command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=i_scroll.set)
        self.inv_tree.pack(side="left", fill="both", expand=True)
        i_scroll.pack(side="right", fill="y")

        # Inventory Action Buttons
        inv_actions = ttk.Frame(inv_card)
        inv_actions.pack(fill="x")

        ttk.Button(inv_actions, text="Toggle Equip", command=self._toggle_equip).pack(
            side="left", padx=2
        )
        ttk.Button(inv_actions, text="Sell / Remove", command=self._remove_item).pack(
            side="right", padx=2
        )

        self._search_catalog()

    def _search_catalog(self) -> None:
        """Fetch filtered catalog items and populate catalog tree."""
        if not self.repo:
            return
        query = self.search_var.get().strip()
        cat_sel = self.cat_choice_var.get()
        category = None if cat_sel == "All" else cat_sel

        items = self.repo.list_catalog_items(category=category, query=query)
        self.cat_tree.delete(*self.cat_tree.get_children())
        for it in items:
            self.cat_tree.insert(
                "",
                "end",
                iid=str(it.id),
                values=(it.name, it.category, f"${it.cost:.2f}", f"{it.weight:.1f}", it.notes),
            )

    def _purchase_item(self) -> None:
        selected = self.cat_tree.selection()
        if not selected or not self.repo:
            return
        item_id = int(selected[0])
        catalog_item = self.repo.get_catalog_item(item_id)
        if not catalog_item:
            return

        success = self.state.add_item_from_catalog(catalog_item, quantity=1)
        if not success:
            messagebox.showwarning(
                "Insufficient Funds",
                f"You do not have enough cash (${self.state.get_cash():.2f}) to purchase {catalog_item.name} (${catalog_item.cost:.2f}).",
            )

    def _toggle_equip(self) -> None:
        selected = self.inv_tree.selection()
        if not selected:
            return
        idx = self.inv_tree.index(selected[0])
        if 0 <= idx < len(self.state.character.inventory):
            item = self.state.character.inventory[idx]
            self.state.toggle_equip_item(item)

    def _remove_item(self) -> None:
        selected = self.inv_tree.selection()
        if not selected:
            return
        idx = self.inv_tree.index(selected[0])
        if 0 <= idx < len(self.state.character.inventory):
            item = self.state.character.inventory[idx]
            self.state.remove_inventory_item(item)

    def _on_state_change(self, event: str = "") -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Update inventory view, cash, weight, and encumbrance indicators."""
        # Cash & Encumbrance Status
        cash = self.state.get_cash()
        self.cash_label.configure(text=f"Cash: ${cash:.2f}")

        carried = self.state.get_carried_weight()
        limit = self.state.get_load_limit()
        self.weight_label.configure(text=f"Weight: {carried:.1f} / {limit:.1f} lbs")

        penalty = self.state.get_encumbrance_penalty()
        self.encumb_label.configure(
            text=f"Penalty: {penalty}", foreground="red" if penalty < 0 else "black"
        )

        # Character Inventory Treeview
        self.inv_tree.delete(*self.inv_tree.get_children())
        for it in self.state.character.inventory:
            eq_str = "Yes" if it.is_equipped else "No"
            self.inv_tree.insert(
                "",
                "end",
                values=(
                    it.name,
                    it.category,
                    it.quantity,
                    f"${it.cost:.2f}",
                    f"{it.total_weight:.1f}",
                    eq_str,
                ),
            )
