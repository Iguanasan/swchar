"""Database layer for swchar, including connection management, schema, seed, and repository."""

from swchar.db.connection import DatabaseManager, get_db_connection
from swchar.db.schema import init_schema
from swchar.db.catalog_seed import seed_default_catalog
from swchar.db.repository import InventoryRepository

__all__ = [
    "DatabaseManager",
    "get_db_connection",
    "init_schema",
    "seed_default_catalog",
    "InventoryRepository",
]
