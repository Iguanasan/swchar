"""SQLite database connection and lifecycle management for swchar."""

import sqlite3
from pathlib import Path
from typing import Any


def get_db_connection(db_path: str = "data/swchar.db") -> sqlite3.Connection:
    """Create and return an open SQLite connection with foreign keys enabled.

    Args:
        db_path: Path to on-disk database file or ':memory:'.

    Returns:
        sqlite3.Connection configured with row_factory=sqlite3.Row and PRAGMA foreign_keys=ON.
    """
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


class DatabaseManager:
    """Connection manager supporting context protocol and database lifecycle management."""

    def __init__(self, db_path: str = "data/swchar.db") -> None:
        """Initialize DatabaseManager with database path.

        Args:
            db_path: SQLite database file path or ':memory:'.
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def get_connection(self) -> sqlite3.Connection:
        """Retrieve active SQLite connection, opening it if necessary."""
        if self._conn is None:
            self._conn = get_db_connection(self.db_path)
        return self._conn

    def close(self) -> None:
        """Close the managed connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DatabaseManager":
        """Enter context manager, returning DatabaseManager instance."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, ensuring connection is closed."""
        self.close()
