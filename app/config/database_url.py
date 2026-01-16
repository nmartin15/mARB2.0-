"""
Database URL configuration and SSL handling.

This module provides utilities for parsing and configuring database URLs,
including automatic SSL mode handling for localhost connections.

**Documentation References:**
- Database Config: See `app/config/database.py` for database setup
- Alembic: See `alembic/env.py` for migration configuration
"""
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional


def parse_database_url(database_url: str) -> str:
    """
    Parse and configure database URL with SSL handling for localhost.
    
    Automatically handles SSL mode for localhost connections:
    - If connecting to localhost and SSL mode not set, disables SSL
    - If connecting to localhost with sslmode=require, overrides to disable
    - Skips SSL handling for SQLite databases
    
    Args:
        database_url: Raw database URL from environment or configuration
        
    Returns:
        Configured database URL with appropriate SSL settings
        
    Examples:
        >>> parse_database_url("postgresql://user:pass@localhost:5432/db")
        'postgresql://user:pass@localhost:5432/db?sslmode=disable'
        
        >>> parse_database_url("sqlite:///db.sqlite")
        'sqlite:///db.sqlite'
    """
    parsed_url = urlparse(database_url)
    is_sqlite = parsed_url.scheme in ("sqlite", "sqlite+pysqlite", "sqlite3")
    
    # Skip SSL handling for SQLite (file-based databases)
    if is_sqlite:
        return database_url
    
    # Only apply SSL mode handling for PostgreSQL/MySQL (not SQLite)
    query_params = parse_qs(parsed_url.query)
    
    # Check if connecting to localhost
    is_localhost = (
        parsed_url.hostname in ("localhost", "127.0.0.1", "::1")
        or not parsed_url.hostname
    )
    
    # For localhost connections, use sslmode=disable if not explicitly set
    if is_localhost and "sslmode" not in query_params:
        query_params["sslmode"] = ["disable"]
        # Reconstruct URL
        new_query = urlencode(query_params, doseq=True)
        parsed_url = parsed_url._replace(query=new_query)
        database_url = urlunparse(parsed_url)
    elif is_localhost and query_params.get("sslmode") == ["require"]:
        # Override require to disable for localhost
        query_params["sslmode"] = ["disable"]
        new_query = urlencode(query_params, doseq=True)
        parsed_url = parsed_url._replace(query=new_query)
        database_url = urlunparse(parsed_url)
    
    return database_url


def get_database_url(default: Optional[str] = None, load_env: bool = True) -> str:
    """
    Get database URL from environment with SSL handling.
    
    Args:
        default: Default database URL if DATABASE_URL not set in environment
        load_env: Whether to load .env file (default: True, set False if already loaded)
        
    Returns:
        Configured database URL
        
    Raises:
        ValueError: If DATABASE_URL not set and no default provided
    """
    import os
    
    if load_env:
        from dotenv import load_dotenv
        # Load .env file before reading environment variables
        load_dotenv()
    
    database_url = os.getenv("DATABASE_URL", default)
    if database_url is None:
        raise ValueError(
            "DATABASE_URL not set in environment and no default provided"
        )
    
    return parse_database_url(database_url)
