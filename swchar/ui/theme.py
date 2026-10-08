"""Tkinter and ttk theme, palette, and styling configuration."""

import tkinter as tk
from tkinter import ttk

# Palette definitions
COLOR_BG = "#f8fafc"
COLOR_SURFACE = "#ffffff"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_SECONDARY = "#64748b"
COLOR_TEXT_MAIN = "#0f172a"
COLOR_TEXT_MUTED = "#64748b"
COLOR_BORDER = "#cbd5e1"
COLOR_SUCCESS = "#16a34a"
COLOR_WARNING = "#d97706"
COLOR_DANGER = "#dc2626"
COLOR_CARD_BG = "#ffffff"

FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 14, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12, "bold")
FONT_HEADER = (FONT_FAMILY, 11, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_BODY_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_MONO = ("Consolas", 10)


def setup_theme(root: tk.Misc) -> ttk.Style:
    """Configure modern ttk styles and widget appearances.

    Args:
        root: The root window or parent widget.

    Returns:
        Configured ttk.Style instance.
    """
    style = ttk.Style(root)

    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")

    # General widget configurations
    style.configure(".", font=FONT_BODY, background=COLOR_BG, foreground=COLOR_TEXT_MAIN)
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Card.TFrame", background=COLOR_CARD_BG, relief="solid", borderwidth=1)

    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT_MAIN, font=FONT_BODY)
    style.configure("Title.TLabel", font=FONT_TITLE, foreground=COLOR_PRIMARY)
    style.configure("Header.TLabel", font=FONT_HEADER, foreground=COLOR_TEXT_MAIN)
    style.configure("Muted.TLabel", font=FONT_SMALL, foreground=COLOR_TEXT_MUTED)
    style.configure("Badge.TLabel", font=FONT_BODY_BOLD, foreground=COLOR_PRIMARY)
    style.configure("Stat.TLabel", font=FONT_SUBTITLE, foreground=COLOR_TEXT_MAIN)

    style.configure("TButton", font=FONT_BODY, borderwidth=1, relief="raised")
    style.configure("Primary.TButton", background=COLOR_PRIMARY, foreground="#ffffff", font=FONT_BODY_BOLD)
    style.map("Primary.TButton", background=[("active", COLOR_PRIMARY_HOVER)])

    style.configure("Danger.TButton", background=COLOR_DANGER, foreground="#ffffff")
    style.configure("TNotebook", background=COLOR_BG, tabmargins=[2, 5, 2, 0])
    style.configure("TNotebook.Tab", font=FONT_BODY_BOLD, padding=[10, 4])
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_SURFACE), ("", COLOR_BG)],
        foreground=[("selected", COLOR_PRIMARY), ("", COLOR_SECONDARY)],
    )

    style.configure("Treeview", font=FONT_BODY, rowheight=24, background=COLOR_SURFACE)
    style.configure("Treeview.Heading", font=FONT_HEADER, background=COLOR_BG)

    return style
