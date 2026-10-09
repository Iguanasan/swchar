"""Tkinter and ttk theme, palette, and styling configuration."""

from dataclasses import dataclass
import enum
import tkinter as tk
from tkinter import ttk


class ThemeName(str, enum.Enum):
    """Enumeration of supported application themes."""

    DEFAULT = "Default"
    DARK = "Dark"
    HIGH_CONTRAST_LIGHT = "High Contrast (Light)"
    HIGH_CONTRAST_DARK = "High Contrast (Dark)"
    COLORBLIND_HIGH_CONTRAST = "Colorblind High Contrast"


ThemeMode = ThemeName


@dataclass(frozen=True)
class ThemePalette:
    """Foundational UI color palette specification."""

    bg: str
    surface: str
    primary: str
    primary_hover: str
    secondary: str
    text_main: str
    text_muted: str
    border: str
    success: str
    warning: str
    danger: str
    card_bg: str


# Comprehensive theme color palette definitions
PALETTES: dict[ThemeName, ThemePalette] = {
    ThemeName.DEFAULT: ThemePalette(
        bg="#f8fafc",
        surface="#ffffff",
        primary="#2563eb",
        primary_hover="#1d4ed8",
        secondary="#64748b",
        text_main="#0f172a",
        text_muted="#64748b",
        border="#cbd5e1",
        success="#16a34a",
        warning="#d97706",
        danger="#dc2626",
        card_bg="#ffffff",
    ),
    ThemeName.DARK: ThemePalette(
        bg="#0f172a",
        surface="#1e293b",
        primary="#3b82f6",
        primary_hover="#60a5fa",
        secondary="#94a3b8",
        text_main="#f8fafc",
        text_muted="#94a3b8",
        border="#334155",
        success="#22c55e",
        warning="#f59e0b",
        danger="#ef4444",
        card_bg="#1e293b",
    ),
    ThemeName.HIGH_CONTRAST_LIGHT: ThemePalette(
        bg="#ffffff",
        surface="#ffffff",
        primary="#0000cc",
        primary_hover="#000088",
        secondary="#000000",
        text_main="#000000",
        text_muted="#333333",
        border="#000000",
        success="#005500",
        warning="#885500",
        danger="#bb0000",
        card_bg="#ffffff",
    ),
    ThemeName.HIGH_CONTRAST_DARK: ThemePalette(
        bg="#000000",
        surface="#000000",
        primary="#ffff00",
        primary_hover="#ffff66",
        secondary="#ffffff",
        text_main="#ffffff",
        text_muted="#cccccc",
        border="#ffffff",
        success="#00ff66",
        warning="#ffaa00",
        danger="#ff3333",
        card_bg="#000000",
    ),
    ThemeName.COLORBLIND_HIGH_CONTRAST: ThemePalette(
        bg="#ffffff",
        surface="#f0f4f8",
        primary="#0072b2",
        primary_hover="#005080",
        secondary="#56b4e9",
        text_main="#000000",
        text_muted="#333333",
        border="#000000",
        success="#009e73",
        warning="#b87000",
        danger="#d55e00",
        card_bg="#ffffff",
    ),
}

# Legacy default palette constants for backwards compatibility
COLOR_BG = PALETTES[ThemeName.DEFAULT].bg
COLOR_SURFACE = PALETTES[ThemeName.DEFAULT].surface
COLOR_PRIMARY = PALETTES[ThemeName.DEFAULT].primary
COLOR_PRIMARY_HOVER = PALETTES[ThemeName.DEFAULT].primary_hover
COLOR_SECONDARY = PALETTES[ThemeName.DEFAULT].secondary
COLOR_TEXT_MAIN = PALETTES[ThemeName.DEFAULT].text_main
COLOR_TEXT_MUTED = PALETTES[ThemeName.DEFAULT].text_muted
COLOR_BORDER = PALETTES[ThemeName.DEFAULT].border
COLOR_SUCCESS = PALETTES[ThemeName.DEFAULT].success
COLOR_WARNING = PALETTES[ThemeName.DEFAULT].warning
COLOR_DANGER = PALETTES[ThemeName.DEFAULT].danger
COLOR_CARD_BG = PALETTES[ThemeName.DEFAULT].card_bg

# Typography definitions
FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 14, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12, "bold")
FONT_HEADER = (FONT_FAMILY, 11, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_BODY_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_MONO = ("Consolas", 10)

# Global active theme tracking
_current_theme: ThemeName = ThemeName.DEFAULT


def get_available_themes() -> list[ThemeName]:
    """Return all available application themes."""
    return list(ThemeName)


def _resolve_theme(theme: ThemeName | str) -> ThemeName:
    """Resolve a theme enum or string to a canonical ThemeName member.

    Raises:
        ValueError: If the theme is unknown.
    """
    if isinstance(theme, ThemeName):
        return theme
    if isinstance(theme, str):
        # Exact match against enum value
        for member in ThemeName:
            if member.value == theme:
                return member
        # Case-insensitive match against enum name
        for member in ThemeName:
            if member.name.lower() == theme.lower():
                return member
        # Case-insensitive match against enum value
        for member in ThemeName:
            if member.value.lower() == theme.lower():
                return member
        # Normalized match (removing parentheses)
        normalized = theme.replace("(", "").replace(")", "").strip().lower()
        for member in ThemeName:
            norm_val = member.value.replace("(", "").replace(")", "").strip().lower()
            if norm_val == normalized:
                return member
        raise ValueError(f"Unknown theme: {theme!r}")
    raise ValueError(f"Invalid theme type: {type(theme)!r}")


def get_theme_palette(theme: ThemeName | str) -> ThemePalette:
    """Retrieve the color palette for a given theme enum or string name."""
    resolved = _resolve_theme(theme)
    return PALETTES[resolved]


get_palette = get_theme_palette


def get_current_theme() -> ThemeName:
    """Return the currently active ThemeName."""
    return _current_theme


def apply_theme(root: tk.Misc, theme: ThemeName | str) -> ttk.Style:
    """Apply the specified theme to the root window and configure ttk styles.

    Args:
        root: The root Tk window or widget.
        theme: The theme name (enum or string).

    Returns:
        Configured ttk.Style instance.
    """
    global _current_theme
    resolved = _resolve_theme(theme)
    _current_theme = resolved
    palette = get_theme_palette(resolved)

    if hasattr(root, "configure"):
        try:
            root.configure(bg=palette.bg)
        except Exception:
            try:
                root.configure(background=palette.bg)
            except Exception:
                pass

    style = ttk.Style(root)

    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")

    # General widget configurations
    style.configure(".", font=FONT_BODY, background=palette.bg, foreground=palette.text_main)
    style.configure("TFrame", background=palette.bg)
    style.configure("Card.TFrame", background=palette.card_bg, relief="solid", borderwidth=1)

    style.configure("TLabel", background=palette.bg, foreground=palette.text_main, font=FONT_BODY)
    style.configure("Title.TLabel", background=palette.bg, font=FONT_TITLE, foreground=palette.primary)
    style.configure("Header.TLabel", background=palette.bg, font=FONT_HEADER, foreground=palette.text_main)
    style.configure("Muted.TLabel", background=palette.bg, font=FONT_SMALL, foreground=palette.text_muted)
    style.configure("Badge.TLabel", background=palette.bg, font=FONT_BODY_BOLD, foreground=palette.primary)
    style.configure("Stat.TLabel", background=palette.bg, font=FONT_SUBTITLE, foreground=palette.text_main)

    style.configure("TButton", font=FONT_BODY, borderwidth=1, relief="raised")
    style.configure("Primary.TButton", background=palette.primary, foreground="#ffffff", font=FONT_BODY_BOLD)
    style.map("Primary.TButton", background=[("active", palette.primary_hover)])

    style.configure("Danger.TButton", background=palette.danger, foreground="#ffffff")
    style.configure("TNotebook", background=palette.bg, tabmargins=[2, 5, 2, 0])
    style.configure("TNotebook.Tab", font=FONT_BODY_BOLD, padding=[10, 4])
    style.map(
        "TNotebook.Tab",
        background=[("selected", palette.surface), ("", palette.bg)],
        foreground=[("selected", palette.primary), ("", palette.secondary)],
    )

    style.configure(
        "Treeview",
        font=FONT_BODY,
        rowheight=24,
        background=palette.surface,
        foreground=palette.text_main,
        fieldbackground=palette.surface,
    )
    style.configure(
        "Treeview.Heading",
        font=FONT_HEADER,
        background=palette.bg,
        foreground=palette.text_main,
    )

    return style


def setup_theme(root: tk.Misc) -> ttk.Style:
    """Configure modern ttk styles and widget appearances using current theme.

    Args:
        root: The root window or parent widget.

    Returns:
        Configured ttk.Style instance.
    """
    return apply_theme(root, _current_theme)
