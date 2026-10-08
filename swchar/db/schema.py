"""Database DDL schema initialization for Savage Worlds character generator."""

import sqlite3

SCHEMA_DDL = """
-- Equipment catalog master table
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0.0,
    weight REAL NOT NULL DEFAULT 0.0,
    min_str TEXT,
    damage TEXT,
    range TEXT,
    armor_bonus INTEGER DEFAULT 0,
    parry_bonus INTEGER DEFAULT 0,
    notes TEXT
);

-- Persisted characters table
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    concept TEXT,
    ancestry TEXT NOT NULL,
    cash REAL NOT NULL DEFAULT 500.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inventory items linked to characters
CREATE TABLE IF NOT EXISTS character_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    catalog_item_id INTEGER,
    custom_name TEXT NOT NULL,
    category TEXT NOT NULL,
    cost REAL NOT NULL,
    weight REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    is_equipped BOOLEAN NOT NULL DEFAULT 0,
    min_str TEXT,
    damage TEXT,
    armor_bonus INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (catalog_item_id) REFERENCES catalog_items(id)
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database tables idempotently.

    Args:
        conn: SQLite connection with foreign keys enabled.
    """
    conn.executescript(SCHEMA_DDL)
