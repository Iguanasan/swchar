"""Main application window for the Savage Worlds Character Builder."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

from swchar.db.catalog_seed import seed_default_catalog
from swchar.ui.tabs.arcana_tab import ArcanaTab
from swchar.ui.tabs.concept_tab import ConceptTab
from swchar.ui.tabs.hindrances_edges_tab import HindrancesEdgesTab
from swchar.ui.tabs.inventory_tab import InventoryTab
from swchar.ui.tabs.summary_tab import SummaryTab
from swchar.ui.tabs.traits_tab import TraitsTab

if TYPE_CHECKING:
    from swchar.app import AppController, CharacterState
    from swchar.db.repository import InventoryRepository


class MainWindow:
    """Primary desktop interface unifying the character builder tabs and menus."""

    def __init__(
        self,
        root: tk.Tk | tk.Toplevel,
        state: "CharacterState",
        repo: "InventoryRepository | None" = None,
        controller: "AppController | None" = None,
    ) -> None:
        self.root = root
        self.state = state
        self.repo = repo or getattr(state, "db_repo", None)
        self.controller = controller

        self._build_menu()
        self._build_body()
        self._build_status_bar()

        self.state.add_listener(self._on_state_change)
        self._update_status()

    def _build_menu(self) -> None:
        """Create the top-level application menu bar."""
        menubar = tk.Menu(self.root)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Character", command=self._menu_new_character)
        file_menu.add_command(label="Open XML...", command=self._menu_open_xml)
        file_menu.add_command(label="Save XML...", command=self._menu_save_xml)
        file_menu.add_separator()
        file_menu.add_command(label="Save to Database", command=self._menu_save_to_db)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Catalog Menu
        catalog_menu = tk.Menu(menubar, tearoff=0)
        catalog_menu.add_command(label="Re-seed Default Catalog", command=self._menu_reseed_catalog)
        menubar.add_cascade(label="Catalog", menu=catalog_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._menu_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_body(self) -> None:
        """Create the notebook container and embed the 6 builder tabs."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        # Instantiate tabs
        self.concept_tab = ConceptTab(self.notebook, self.state)
        self.traits_tab = TraitsTab(self.notebook, self.state)
        self.hindrances_edges_tab = HindrancesEdgesTab(self.notebook, self.state)
        self.arcana_tab = ArcanaTab(self.notebook, self.state)
        self.inventory_tab = InventoryTab(self.notebook, self.state, repo=self.repo)
        self.summary_tab = SummaryTab(self.notebook, self.state, controller=self.controller)

        self.tabs = [
            self.concept_tab,
            self.traits_tab,
            self.hindrances_edges_tab,
            self.arcana_tab,
            self.inventory_tab,
            self.summary_tab,
        ]

        # Add tabs to notebook
        self.notebook.add(self.concept_tab, text="1. Concept")
        self.notebook.add(self.traits_tab, text="2. Traits")
        self.notebook.add(self.hindrances_edges_tab, text="3. Hindrances & Edges")
        self.notebook.add(self.arcana_tab, text="4. Arcana")
        self.notebook.add(self.inventory_tab, text="5. Inventory")
        self.notebook.add(self.summary_tab, text="6. Summary")

    def _build_status_bar(self) -> None:
        """Create the bottom status bar."""
        self.status_frame = ttk.Frame(self.root, relief="sunken", padding=4)
        self.status_frame.pack(fill="x", side="bottom")

        self.status_label = ttk.Label(self.status_frame, text="Ready", style="Muted.TLabel")
        self.status_label.pack(side="left")

    def _on_state_change(self, event: str = "") -> None:
        self._update_status()

    def _update_status(self) -> None:
        char = self.state.character
        char_name = char.name or "Unnamed"
        ancestry = char.ancestry.name if char.ancestry else "Human"
        errors = self.state.validate_build()

        if errors:
            status = f"{char_name} ({ancestry}) | Validation: {len(errors)} issues pending"
            self.status_label.configure(text=status, foreground="red")
        else:
            status = f"{char_name} ({ancestry}) | Build Valid"
            self.status_label.configure(text=status, foreground="green")

    # --------------------------------------------------------------------------
    # Menu callbacks
    # --------------------------------------------------------------------------

    def _menu_new_character(self) -> None:
        if self.controller:
            self.controller.new_character()
        else:
            from swchar.models.character import Character
            from swchar.models.ancestry import get_ancestry
            self.state.character = Character(ancestry=get_ancestry("Human"))
            self.state.notify_listeners("reset")

    def _menu_open_xml(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Open Character XML",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if file_path:
            try:
                self.state.import_from_xml(file_path)
                messagebox.showinfo("Loaded", f"Character loaded from:\n{file_path}")
            except Exception as err:
                messagebox.showerror("Error", f"Failed to load XML:\n{err}")

    def _menu_save_xml(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save Character XML",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if file_path:
            try:
                self.state.export_to_xml(file_path)
                messagebox.showinfo("Saved", f"Character saved to:\n{file_path}")
            except Exception as err:
                messagebox.showerror("Error", f"Failed to save XML:\n{err}")

    def _menu_save_to_db(self) -> None:
        if not self.repo:
            messagebox.showwarning("Database", "No database repository configured.")
            return
        try:
            self.state.save_to_db(self.repo)
            messagebox.showinfo("Saved", "Character and inventory persisted to database.")
        except Exception as err:
            messagebox.showerror("Error", f"Failed to save to database:\n{err}")

    def _menu_reseed_catalog(self) -> None:
        if self.repo and hasattr(self.repo, "conn"):
            seed_default_catalog(self.repo.conn)
            self.inventory_tab._search_catalog()
            messagebox.showinfo("Catalog", "Default equipment catalog re-seeded successfully.")

    def _menu_about(self) -> None:
        messagebox.showinfo(
            "About swchar",
            "Savage Worlds Character Generator (SWADE)\nVersion 1.0\nRule-enforcing Wild Card builder.",
        )
