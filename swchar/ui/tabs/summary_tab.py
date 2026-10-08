"""Summary tab presenting the full combat profile, character sheet overview, and XML triggers."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from swchar.app import AppController, CharacterState


class SummaryTab(ttk.Frame):
    """Tab 6: Complete character sheet summary and XML export/import triggers."""

    def __init__(
        self,
        parent: tk.Misc,
        state: "CharacterState",
        controller: "AppController | None" = None,
    ) -> None:
        super().__init__(parent, padding=15)
        self.state = state
        self.controller = controller

        self._build_ui()
        self.state.add_listener(self._on_state_change)
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the UI widgets."""
        header = ttk.Label(self, text="Character Sheet Summary & Export", style="Title.TLabel")
        header.pack(anchor="w", pady=(0, 15))

        # Combat Profile Banner Card
        combat_card = ttk.LabelFrame(self, text="Combat Profile", padding=12)
        combat_card.pack(fill="x", pady=(0, 15))

        stats_row = ttk.Frame(combat_card)
        stats_row.pack(fill="x")

        self.pace_lbl = ttk.Label(stats_row, text="Pace: 6", font=("Segoe UI", 11, "bold"))
        self.pace_lbl.pack(side="left", padx=12)

        self.parry_lbl = ttk.Label(stats_row, text="Parry: 2", font=("Segoe UI", 11, "bold"))
        self.parry_lbl.pack(side="left", padx=12)

        self.tough_lbl = ttk.Label(stats_row, text="Toughness: 4", font=("Segoe UI", 11, "bold"))
        self.tough_lbl.pack(side="left", padx=12)

        self.bennies_lbl = ttk.Label(stats_row, text="Bennies: 3", font=("Segoe UI", 11, "bold"))
        self.bennies_lbl.pack(side="left", padx=12)

        self.load_lbl = ttk.Label(stats_row, text="Load Limit: 20 lbs", font=("Segoe UI", 11, "bold"))
        self.load_lbl.pack(side="left", padx=12)

        # Overview Sheet Card
        sheet_card = ttk.LabelFrame(self, text="Character Sheet Overview", padding=12)
        sheet_card.pack(fill="both", expand=True, pady=(0, 15))

        self.sheet_text = tk.Text(sheet_card, wrap="word", relief="solid", borderwidth=1, height=14)
        self.sheet_text.pack(fill="both", expand=True)
        self.sheet_text.configure(state="disabled")

        # Bottom Trigger Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Export XML...", command=self._export_xml, style="Primary.TButton").pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="Import XML...", command=self._import_xml).pack(side="left", padx=5)

    def _export_xml(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Export Character to XML",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if file_path:
            try:
                self.state.export_to_xml(file_path)
                messagebox.showinfo("Export Successful", f"Character exported cleanly to:\n{file_path}")
            except Exception as err:
                messagebox.showerror("Export Failed", f"Could not export character:\n{err}")

    def _import_xml(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Import Character from XML",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if file_path:
            try:
                self.state.import_from_xml(file_path)
                messagebox.showinfo("Import Successful", f"Character loaded cleanly from:\n{file_path}")
            except Exception as err:
                messagebox.showerror("Import Failed", f"Could not import character:\n{err}")

    def _on_state_change(self, event: str = "") -> None:
        self._refresh()

    def _refresh(self) -> None:
        """Update combat profile labels and formatted sheet overview."""
        char = self.state.character

        # Combat stats
        pace = self.state.get_pace()
        rdie = self.state.get_running_die()
        parry = self.state.get_parry()
        tough = self.state.get_toughness()
        tough_val = tough.total if hasattr(tough, "total") else tough
        bennies = self.state.get_bennies()
        load_limit = self.state.get_load_limit()

        self.pace_lbl.configure(text=f"Pace: {pace} (d{rdie.value})")
        self.parry_lbl.configure(text=f"Parry: {parry}")
        self.tough_lbl.configure(text=f"Toughness: {tough_val}")
        self.bennies_lbl.configure(text=f"Bennies: {bennies}")
        self.load_lbl.configure(text=f"Load Limit: {load_limit:.0f} lbs")

        # Overview Sheet
        lines: list[str] = [
            f"NAME: {char.name or '(Unnamed)'} | CONCEPT: {char.concept or '(None)'}",
            f"ANCESTRY: {char.ancestry.name if char.ancestry else 'Human'} | RANK: {char.rank.value} | CASH: ${char.cash:.2f}",
            "=" * 70,
            "ATTRIBUTES:",
            f"  Agility: {char.attributes.agility} | Smarts: {char.attributes.smarts} | Spirit: {char.attributes.spirit} | Strength: {char.attributes.strength} | Vigor: {char.attributes.vigor}",
            "-" * 70,
            "SKILLS:",
        ]

        for s in char.skills.values():
            core_flag = " (Core)" if s.core else ""
            lines.append(f"  * {s.name}: {s.die}{core_flag}")

        lines.append("-" * 70)
        lines.append(f"HINDRANCES: {', '.join(h.name if hasattr(h, 'name') else str(h) for h in char.hindrances) or 'None'}")
        lines.append(f"EDGES: {', '.join(e.name if hasattr(e, 'name') else str(e) for e in char.edges) or 'None'}")

        if char.arcana and char.arcana.background and char.arcana.background.lower() != "none":
            lines.append("-" * 70)
            lines.append(f"ARCANA: {char.arcana.background} (Power Points: {char.arcana.power_points})")
            for p in char.arcana.powers:
                trap = f" [{p.trappings}]" if p.trappings else ""
                lines.append(f"  * Power: {p.name}{trap}")

        lines.append("-" * 70)
        lines.append(f"INVENTORY ({len(char.inventory)} items):")
        for it in char.inventory:
            eq = " [EQUIPPED]" if it.is_equipped else ""
            lines.append(f"  * {it.name} x{it.quantity} (${it.cost:.2f}, {it.total_weight:.1f} lbs){eq}")

        # Build validation warnings
        errors = self.state.validate_build()
        if errors:
            lines.append("-" * 70)
            lines.append("VALIDATION ISSUES:")
            for err in errors:
                lines.append(f"  ! {err}")

        self.sheet_text.configure(state="normal")
        self.sheet_text.delete("1.0", "end")
        self.sheet_text.insert("1.0", "\n".join(lines))
        self.sheet_text.configure(state="disabled")
