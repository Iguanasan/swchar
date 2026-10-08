# Savage Worlds Character Generator (`swchar`)

A desktop application for creating, managing, and equipping characters for the tabletop roleplaying game *Savage Worlds Adventure Edition* (SWADE). The application provides an interactive character creation workflow enforcing official point budgets, ancestry modifiers, edge prerequisites, and derived combat statistics. It maintains a persistent local equipment catalog and character inventories in a SQLite database and supports importing and exporting characters using structured XML documents.

## Features
- **Full SWADE Rules Support**: 10 Core Ancestries, 5 Attributes, 5 Core Skills + full skill catalog, Hindrance point redemption economy, Edges with prerequisite checking, and Arcane Backgrounds.
- **Derived Statistics Engine**: Automatic calculations for Pace, Running die, Parry, Toughness (with armor and size modifiers), Bennies, and Load Limits.
- **Local SQLite Inventory**: Master catalog of weapons, armor, and gear with live weight tracking and encumbrance penalty warnings.
- **XML Import/Export**: Portable character files adhering to a standardized XML schema.
- **Desktop Graphical Interface**: Native, responsive desktop GUI built using Python's `tkinter` and `ttk`.

## Development & Testing
Run tests using:
```bash
pytest
```
