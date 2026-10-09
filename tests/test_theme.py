"""Unit and integration tests for Theme and Colorblind High Contrast capabilities.

Verifies acceptance criteria:
1. ThemeName (or ThemeMode) Enum in swchar.ui.theme:
   - Contains: DEFAULT, DARK, HIGH_CONTRAST_LIGHT, HIGH_CONTRAST_DARK, COLORBLIND_HIGH_CONTRAST.
2. get_available_themes() returns all available theme names.
3. Palette attributes for themes:
   - Verifies COLORBLIND_HIGH_CONTRAST provides accessible contrast:
     - Primary / accent contrast against background.
     - Text colors have distinct contrast (WCAG AAA >= 7.0 for high contrast).
     - Accessible success / warning / danger palette (Okabe-Ito friendly, avoiding indistinguishable red/green).
   - Verifies contrast ratios across other themes (Default, Dark, High Contrast Light/Dark).
4. apply_theme(root, theme_name) function:
   - Takes a Tk root or widget and theme name/enum.
   - Successfully configures styles for all themes without error.
   - Updates root.configure(bg=...).
   - get_current_theme() returns the currently active theme.
5. In MainWindow:
   - Has a "View" or "Theme" menu enabling theme selection.
   - Allows switching theme dynamically via set_theme(theme_name).
   - Accessible status cues: _update_status outputs unambiguous text markers
     (e.g. [VALID] for valid builds, [!] or [ISSUES] for pending errors) so
     information is accessible without relying solely on red/green color perception.
"""

import enum
import tkinter as tk
from tkinter import ttk
from typing import Any
from unittest.mock import patch
import pytest

# Target imports under test
try:
    from swchar.ui.theme import ThemeName
except ImportError:
    try:
        from swchar.ui.theme import ThemeMode as ThemeName  # type: ignore
    except ImportError:
        ThemeName = None  # type: ignore

try:
    from swchar.ui.theme import get_available_themes
except ImportError:
    get_available_themes = None  # type: ignore

try:
    from swchar.ui.theme import get_theme_palette
except ImportError:
    try:
        from swchar.ui.theme import get_palette as get_theme_palette  # type: ignore
    except ImportError:
        get_theme_palette = None  # type: ignore

try:
    from swchar.ui.theme import apply_theme
except ImportError:
    apply_theme = None  # type: ignore

try:
    from swchar.ui.theme import get_current_theme
except ImportError:
    get_current_theme = None  # type: ignore

from swchar.app import CharacterState
from swchar.ui.main_window import MainWindow


# ==============================================================================
# WCAG Contrast & Color Science Utilities
# ==============================================================================


def hex_to_rgb(hex_code: str) -> tuple[float, float, float]:
    """Convert hex color string (e.g. '#ffffff' or '#fff') to normalized RGB floats in [0, 1]."""
    code = hex_code.strip().lstrip("#")
    if len(code) == 3:
        code = "".join(c * 2 for c in code)
    if len(code) != 6:
        raise ValueError(f"Invalid hex color string: {hex_code}")
    r = int(code[0:2], 16) / 255.0
    g = int(code[2:4], 16) / 255.0
    b = int(code[4:6], 16) / 255.0
    return r, g, b


def srgb_to_linear(c: float) -> float:
    """Convert sRGB component to linear luminance value per WCAG 2.1."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_code: str) -> float:
    """Calculate WCAG 2.1 relative luminance for a given hex color."""
    r, g, b = hex_to_rgb(hex_code)
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)


def wcag_contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate WCAG 2.1 contrast ratio between two hex colors (range: 1.0 to 21.0)."""
    l1 = relative_luminance(hex1)
    l2 = relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def get_palette_field(palette: Any, key: str) -> str:
    """Helper to retrieve a color hex code from a palette object or dictionary."""
    if isinstance(palette, dict):
        val = palette.get(key)
    else:
        val = getattr(palette, key, None)
    if val is None:
        raise AttributeError(f"Palette missing color field: '{key}'")
    return str(val)


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def shared_tk_root():
    """Provide a module-level withdrawn (headless) Tkinter root window."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as err:
        pytest.skip(f"Tkinter display not available: {err}")
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def tk_root(shared_tk_root: tk.Tk):
    """Provide a clean Tkinter root window with children reset between tests."""
    for child in shared_tk_root.winfo_children():
        try:
            child.destroy()
        except Exception:
            pass
    try:
        shared_tk_root.config(menu="")
    except Exception:
        pass
    yield shared_tk_root


@pytest.fixture
def fresh_state() -> CharacterState:
    """Provide a fresh CharacterState instance."""
    return CharacterState()


# ==============================================================================
# 1. ThemeName Enum Verification
# ==============================================================================


class TestThemeEnum:
    """Acceptance tests for ThemeName Enum definition and members."""

    def test_theme_enum_exists_and_is_enum(self) -> None:
        """ThemeName Enum is exported by swchar.ui.theme and subclasses enum.Enum."""
        assert ThemeName is not None, "ThemeName (or ThemeMode) must be exported from swchar.ui.theme"
        assert issubclass(ThemeName, enum.Enum), "ThemeName must be an Enum subclass"

    def test_theme_enum_contains_required_members(self) -> None:
        """ThemeName contains all required theme modes."""
        assert ThemeName is not None, "ThemeName must be defined"
        members = ThemeName.__members__
        expected_members = [
            "DEFAULT",
            "DARK",
            "HIGH_CONTRAST_LIGHT",
            "HIGH_CONTRAST_DARK",
            "COLORBLIND_HIGH_CONTRAST",
        ]
        for name in expected_members:
            assert name in members, f"ThemeName enum must contain member '{name}'"

    def test_theme_enum_member_values(self) -> None:
        """ThemeName enum members map to clear, user-facing descriptive strings."""
        assert ThemeName is not None, "ThemeName must be defined"
        assert ThemeName.DEFAULT.value in ("Default", "Default Light")
        assert ThemeName.DARK.value == "Dark"
        assert ThemeName.HIGH_CONTRAST_LIGHT.value in ("High Contrast (Light)", "High Contrast Light")
        assert ThemeName.HIGH_CONTRAST_DARK.value in ("High Contrast (Dark)", "High Contrast Dark")
        assert ThemeName.COLORBLIND_HIGH_CONTRAST.value == "Colorblind High Contrast"


# ==============================================================================
# 2. get_available_themes() Function Verification
# ==============================================================================


class TestAvailableThemes:
    """Acceptance tests for get_available_themes() function."""

    def test_get_available_themes_is_callable(self) -> None:
        """get_available_themes is exported and callable."""
        assert callable(get_available_themes), "get_available_themes must be callable in swchar.ui.theme"

    def test_get_available_themes_returns_all_themes(self) -> None:
        """get_available_themes() returns a collection containing at least 5 themes."""
        assert callable(get_available_themes), "get_available_themes must be defined"
        themes = get_available_themes()
        assert isinstance(themes, (list, tuple)), "get_available_themes must return a list or tuple"
        assert len(themes) >= 5, f"Expected at least 5 available themes, got {len(themes)}"

        # Convert themes to strings for inspection whether returned as enums or strings
        theme_names = [t.value if hasattr(t, "value") else str(t) for t in themes]
        expected_substrings = [
            "Default",
            "Dark",
            "High Contrast (Light)",
            "High Contrast (Dark)",
            "Colorblind High Contrast",
        ]
        for expected in expected_substrings:
            assert any(
                expected.lower() in name.lower() for name in theme_names
            ), f"Expected theme '{expected}' not found in available themes: {theme_names}"

    def test_get_available_themes_includes_colorblind_theme(self) -> None:
        """get_available_themes explicitly includes Colorblind High Contrast."""
        assert callable(get_available_themes), "get_available_themes must be defined"
        themes = get_available_themes()
        theme_names = [t.value if hasattr(t, "value") else str(t) for t in themes]
        assert "Colorblind High Contrast" in theme_names or any(
            "colorblind" in name.lower() for name in theme_names
        )


# ==============================================================================
# 3. Palette Contrast & Colorblind Accessibility Verification
# ==============================================================================


class TestThemePalettesAndContrast:
    """Acceptance tests verifying palette contrast and Okabe-Ito colorblind compliance."""

    def test_get_theme_palette_callable(self) -> None:
        """get_theme_palette is exported and callable."""
        assert callable(get_theme_palette), "get_theme_palette must be callable in swchar.ui.theme"

    def test_all_themes_provide_required_palette_attributes(self) -> None:
        """Each available theme returns a palette with all foundational UI color attributes."""
        assert callable(get_available_themes) and callable(get_theme_palette)
        required_fields = [
            "bg",
            "surface",
            "primary",
            "text_main",
            "text_muted",
            "border",
            "success",
            "warning",
            "danger",
        ]
        for theme in get_available_themes():
            palette = get_theme_palette(theme)
            assert palette is not None, f"Palette for {theme} must not be None"
            for field in required_fields:
                color = get_palette_field(palette, field)
                assert isinstance(color, str) and color.startswith("#"), (
                    f"Theme {theme} field '{field}' must be a hex color string, got {color!r}"
                )

    def test_colorblind_high_contrast_text_contrast(self) -> None:
        """Colorblind High Contrast theme provides WCAG AAA contrast (>= 7.0:1) for main text."""
        assert callable(get_theme_palette) and ThemeName is not None
        palette = get_theme_palette(ThemeName.COLORBLIND_HIGH_CONTRAST)
        bg = get_palette_field(palette, "bg")
        text_main = get_palette_field(palette, "text_main")
        text_muted = get_palette_field(palette, "text_muted")

        main_contrast = wcag_contrast_ratio(text_main, bg)
        assert main_contrast >= 7.0, (
            f"Colorblind High Contrast main text contrast ({main_contrast:.2f}:1) "
            f"must meet WCAG AAA high contrast (>= 7.0:1) against background {bg}"
        )

        muted_contrast = wcag_contrast_ratio(text_muted, bg)
        assert muted_contrast >= 4.5, (
            f"Colorblind High Contrast muted text contrast ({muted_contrast:.2f}:1) "
            f"must meet WCAG AA (>= 4.5:1) against background {bg}"
        )

    def test_colorblind_high_contrast_primary_accent_contrast(self) -> None:
        """Colorblind High Contrast primary accent provides high contrast (>= 4.5:1) against background."""
        assert callable(get_theme_palette) and ThemeName is not None
        palette = get_theme_palette(ThemeName.COLORBLIND_HIGH_CONTRAST)
        bg = get_palette_field(palette, "bg")
        primary = get_palette_field(palette, "primary")

        primary_contrast = wcag_contrast_ratio(primary, bg)
        assert primary_contrast >= 4.5, (
            f"Colorblind High Contrast primary accent contrast ({primary_contrast:.2f}:1) "
            f"must meet >= 4.5:1 against background {bg}"
        )

    def test_colorblind_accessible_status_indicators(self) -> None:
        """Colorblind High Contrast status palette avoids indistinguishable red/green.

        Conforms to Okabe-Ito / Color Universal Design (CUD):
        - Success and danger must not be standard confusable red (#dc2626) and green (#16a34a).
        - Success and danger must have distinct blue-channel components (|b1 - b2| >= 0.25)
          or significant contrast difference (>= 1.5:1), ensuring readability under protanopia/deuteranopia.
        - Status colors (success, warning, danger) have >= 3.0:1 contrast against theme background.
        """
        assert callable(get_theme_palette) and ThemeName is not None
        palette = get_theme_palette(ThemeName.COLORBLIND_HIGH_CONTRAST)
        bg = get_palette_field(palette, "bg")
        success = get_palette_field(palette, "success")
        warning = get_palette_field(palette, "warning")
        danger = get_palette_field(palette, "danger")

        # Background contrast checks
        assert wcag_contrast_ratio(success, bg) >= 3.0, "Success must have >= 3.0:1 contrast against bg"
        assert wcag_contrast_ratio(warning, bg) >= 3.0, "Warning must have >= 3.0:1 contrast against bg"
        assert wcag_contrast_ratio(danger, bg) >= 3.0, "Danger must have >= 3.0:1 contrast against bg"

        # Not standard red/green
        assert success.lower() != "#16a34a", (
            "Colorblind High Contrast must not use standard green (#16a34a) for success"
        )
        assert danger.lower() != "#dc2626", (
            "Colorblind High Contrast must not use standard red (#dc2626) for danger"
        )

        # Okabe-Ito / Color Universal Design differentiation:
        # Success and danger must be distinct from each other
        assert success.lower() != danger.lower(), "Success and danger colors must not be identical"

        _, _, b_success = hex_to_rgb(success)
        _, _, b_danger = hex_to_rgb(danger)
        blue_diff = abs(b_success - b_danger)
        contrast_diff = wcag_contrast_ratio(success, danger)

        assert (blue_diff >= 0.25) or (contrast_diff >= 1.5), (
            f"Colorblind success ({success}) and danger ({danger}) must provide distinguishable "
            f"chroma/luminance cues under red-green deficiency (blue diff: {blue_diff:.2f}, "
            f"contrast ratio: {contrast_diff:.2f}:1)"
        )

    def test_high_contrast_light_and_dark_contrast_ratios(self) -> None:
        """High Contrast Light and Dark modes provide strict WCAG AAA (>= 7.0:1) contrast."""
        assert callable(get_theme_palette) and ThemeName is not None

        # High Contrast Light
        hc_light = get_theme_palette(ThemeName.HIGH_CONTRAST_LIGHT)
        bg_light = get_palette_field(hc_light, "bg")
        text_light = get_palette_field(hc_light, "text_main")
        assert relative_luminance(bg_light) > 0.8, "High Contrast Light must have near-white background"
        assert wcag_contrast_ratio(text_light, bg_light) >= 7.0, (
            "High Contrast Light text must have >= 7.0:1 contrast"
        )

        # High Contrast Dark
        hc_dark = get_theme_palette(ThemeName.HIGH_CONTRAST_DARK)
        bg_dark = get_palette_field(hc_dark, "bg")
        text_dark = get_palette_field(hc_dark, "text_main")
        assert relative_luminance(bg_dark) < 0.1, "High Contrast Dark must have near-black background"
        assert wcag_contrast_ratio(text_dark, bg_dark) >= 7.0, (
            "High Contrast Dark text must have >= 7.0:1 contrast"
        )

    def test_dark_theme_contrast_ratios(self) -> None:
        """Dark theme provides dark background and WCAG AA (>= 4.5:1) main text contrast."""
        assert callable(get_theme_palette) and ThemeName is not None
        dark_palette = get_theme_palette(ThemeName.DARK)
        bg_dark = get_palette_field(dark_palette, "bg")
        text_dark = get_palette_field(dark_palette, "text_main")

        assert relative_luminance(bg_dark) < 0.25, "Dark theme background must be dark (luminance < 0.25)"
        assert wcag_contrast_ratio(text_dark, bg_dark) >= 4.5, "Dark theme text must have >= 4.5:1 contrast"


# ==============================================================================
# 4. apply_theme() & get_current_theme() Verification
# ==============================================================================


class TestApplyTheme:
    """Acceptance tests for apply_theme() and get_current_theme()."""

    def test_apply_theme_is_callable(self) -> None:
        """apply_theme and get_current_theme are exported and callable."""
        assert callable(apply_theme), "apply_theme must be callable in swchar.ui.theme"
        assert callable(get_current_theme), "get_current_theme must be callable in swchar.ui.theme"

    def test_apply_theme_configures_root_and_updates_current_theme(self, tk_root: tk.Tk) -> None:
        """apply_theme updates root background and get_current_theme() for all defined themes."""
        assert callable(apply_theme) and callable(get_current_theme) and callable(get_theme_palette)
        assert ThemeName is not None

        for theme in ThemeName:
            palette = get_theme_palette(theme)
            expected_bg = get_palette_field(palette, "bg").lower()

            apply_theme(tk_root, theme)
            active_theme = get_current_theme()

            assert active_theme in (theme, theme.value), (
                f"get_current_theme() returned {active_theme!r}, expected {theme!r} or {theme.value!r}"
            )
            actual_bg = tk_root.cget("bg").lower()
            assert actual_bg == expected_bg, (
                f"Root background for {theme} was {actual_bg}, expected {expected_bg}"
            )

    def test_apply_theme_accepts_string_names(self, tk_root: tk.Tk) -> None:
        """apply_theme accepts theme names as plain string arguments."""
        assert callable(apply_theme) and callable(get_current_theme) and ThemeName is not None

        apply_theme(tk_root, "Dark")
        assert get_current_theme() in (ThemeName.DARK, "Dark")

        apply_theme(tk_root, "Colorblind High Contrast")
        assert get_current_theme() in (
            ThemeName.COLORBLIND_HIGH_CONTRAST,
            "Colorblind High Contrast",
        )

    def test_apply_theme_invalid_name_raises_error(self, tk_root: tk.Tk) -> None:
        """apply_theme raises ValueError when passed an unknown theme name."""
        assert callable(apply_theme)
        with pytest.raises((ValueError, KeyError)):
            apply_theme(tk_root, "Nonexistent Invalid Theme")

    def test_apply_theme_configures_ttk_styles(self, tk_root: tk.Tk) -> None:
        """apply_theme configures standard ttk styles for the target theme."""
        assert callable(apply_theme) and callable(get_theme_palette) and ThemeName is not None

        dark_palette = get_theme_palette(ThemeName.DARK)
        expected_bg = get_palette_field(dark_palette, "bg").lower()
        expected_fg = get_palette_field(dark_palette, "text_main").lower()

        apply_theme(tk_root, ThemeName.DARK)
        style = ttk.Style(tk_root)

        # Inspect TLabel or general widget background configured by apply_theme
        tlabel_bg = style.lookup("TLabel", "background").lower()
        tlabel_fg = style.lookup("TLabel", "foreground").lower()

        assert tlabel_bg == expected_bg, (
            f"TLabel background in Dark theme should be {expected_bg}, got {tlabel_bg}"
        )
        assert tlabel_fg == expected_fg, (
            f"TLabel foreground in Dark theme should be {expected_fg}, got {tlabel_fg}"
        )


# ==============================================================================
# 5. MainWindow Integration & Accessible Status Bar Verification
# ==============================================================================


class TestMainWindowThemeIntegration:
    """Acceptance tests for MainWindow theme menu, dynamic switching, and accessible cues."""

    def _find_menu_cascade(self, root: tk.Tk, target_labels: tuple[str, ...]) -> tk.Menu | None:
        """Helper to locate a cascade menu matching any of target_labels from the menubar."""
        menubar_name = root.cget("menu")
        if not menubar_name:
            return None
        menubar: tk.Menu = root.nametowidget(menubar_name)
        end_idx = menubar.index("end")
        if end_idx is None:
            return None

        for i in range(end_idx + 1):
            try:
                label = menubar.entrycget(i, "label")
                if label in target_labels:
                    submenu_name = menubar.entrycget(i, "menu")
                    if submenu_name:
                        return root.nametowidget(submenu_name)
            except tk.TclError:
                pass
        return None

    def _collect_all_menu_labels(self, menu: tk.Menu) -> list[str]:
        """Recursively collect all entry labels within a menu."""
        labels: list[str] = []
        end_idx = menu.index("end")
        if end_idx is None:
            return labels
        for i in range(end_idx + 1):
            try:
                label = menu.entrycget(i, "label")
                if label:
                    labels.append(label)
                submenu_name = menu.entrycget(i, "menu")
                if submenu_name:
                    sub: tk.Menu = menu.nametowidget(submenu_name)
                    labels.extend(self._collect_all_menu_labels(sub))
            except tk.TclError:
                pass
        return labels

    def test_main_window_has_theme_or_view_menu(
        self, tk_root: tk.Tk, fresh_state: CharacterState
    ) -> None:
        """MainWindow menubar contains a 'Theme' or 'View' menu enabling theme selection."""
        window = MainWindow(root=tk_root, state=fresh_state)
        assert window is not None

        theme_menu = self._find_menu_cascade(tk_root, ("Theme", "View"))
        assert theme_menu is not None, "MainWindow menubar must have a 'Theme' or 'View' cascade menu"

        all_labels = self._collect_all_menu_labels(theme_menu)
        # Verify available themes are present in the menu
        expected_options = ["Default", "Dark", "High Contrast", "Colorblind"]
        for opt in expected_options:
            assert any(opt.lower() in lbl.lower() for lbl in all_labels), (
                f"Theme menu missing option matching '{opt}'. Found entries: {all_labels}"
            )

    def test_main_window_set_theme_dynamically(
        self, tk_root: tk.Tk, fresh_state: CharacterState
    ) -> None:
        """MainWindow provides set_theme(theme_name) to switch themes at runtime."""
        window = MainWindow(root=tk_root, state=fresh_state)
        assert hasattr(window, "set_theme") and callable(window.set_theme), (
            "MainWindow must implement set_theme(theme_name) method"
        )
        assert ThemeName is not None and callable(get_current_theme)

        # Switch to Dark
        window.set_theme(ThemeName.DARK)
        assert get_current_theme() in (ThemeName.DARK, "Dark")

        # Switch to Colorblind High Contrast
        window.set_theme(ThemeName.COLORBLIND_HIGH_CONTRAST)
        assert get_current_theme() in (
            ThemeName.COLORBLIND_HIGH_CONTRAST,
            "Colorblind High Contrast",
        )

    def test_main_window_status_accessible_cue_on_issues(
        self, tk_root: tk.Tk, fresh_state: CharacterState
    ) -> None:
        """_update_status outputs unambiguous text cues ([!] or [ISSUES]) when errors are pending.

        Ensures error status does not rely solely on red color perception.
        """
        # fresh_state has unspent attribute and skill points -> validate_build returns errors
        errors = fresh_state.validate_build()
        assert len(errors) > 0, "Precondition: fresh_state has build validation errors"

        window = MainWindow(root=tk_root, state=fresh_state)
        status_text = window.status_label.cget("text")

        accessible_cues = ["[ISSUES]", "[!]", "[ERROR]"]
        assert any(cue in status_text for cue in accessible_cues), (
            f"Status text '{status_text}' must contain an unambiguous text cue "
            f"([!] or [ISSUES]) so colorblind users are not dependent on red font color."
        )

    def test_main_window_status_accessible_cue_on_valid_build(
        self, tk_root: tk.Tk, fresh_state: CharacterState
    ) -> None:
        """_update_status outputs unambiguous text cue [VALID] when build has zero validation issues.

        Ensures valid status does not rely solely on green color perception.
        """
        window = MainWindow(root=tk_root, state=fresh_state)

        with patch.object(fresh_state, "validate_build", return_value=[]):
            window._update_status()
            status_text = window.status_label.cget("text")

            assert "[VALID]" in status_text, (
                f"Status text '{status_text}' must contain the explicit text cue '[VALID]' "
                f"when character build is valid, avoiding reliance solely on green font color."
            )

    def test_main_window_status_cue_transitions_reactively(
        self, tk_root: tk.Tk, fresh_state: CharacterState
    ) -> None:
        """Status bar text cues reactively transition between [!] and [VALID] as state changes."""
        window = MainWindow(root=tk_root, state=fresh_state)

        # 1. Initially has errors -> [!] or [ISSUES]
        status_initial = window.status_label.cget("text")
        assert any(cue in status_initial for cue in ("[ISSUES]", "[!]"))

        # 2. State updates to valid build -> [VALID]
        with patch.object(fresh_state, "validate_build", return_value=[]):
            fresh_state.notify_listeners("test_event")
            status_valid = window.status_label.cget("text")
            assert "[VALID]" in status_valid, (
                f"Expected '[VALID]' marker in status bar after state updated to valid: '{status_valid}'"
            )
