"""
SQL Validation Utilities - Security Enhancement
Created: 2025-12-23
Purpose: Prevent SQL injection in table names for debug/exploration scripts
"""
from typing import Set


# Whitelist of allowed Wialon database tables
ALLOWED_WIALON_TABLES: Set[str] = {
    'sensors',
    'units',
    'trips',
    'messages',
    'driving_events',
    'units_map',
    'alerts',
    'events',
    'violations',
    'params',
    'driver_behavior',
    'harsh_events',
    'speed_violations',
    'avl_units',
    'avl_unit_states',
}

# Whitelist of allowed Fuel Copilot local tables
ALLOWED_LOCAL_TABLES: Set[str] = {
    'fuel_metrics',
    'truck_sensors_cache',
    'refuels',
    'thefts',
    'driver_behavior',
    'dtc_codes',
    'maintenance_predictions',
    'alerts_log',
    'mpg_baselines',
}


def validate_table_name(table: str, allowed_tables: Set[str] = None) -> str:
    """
    Validate table name against whitelist to prevent SQL injection.
    
    Args:
        table: Table name to validate
        allowed_tables: Set of allowed table names (defaults to ALLOWED_WIALON_TABLES)
    
    Returns:
        str: The validated table name
    
    Raises:
        ValueError: If table name is not in whitelist
    
    Example:
        >>> table = validate_table_name("sensors")
        >>> cursor.execute(f"SELECT * FROM {table} LIMIT 5")
    """
    if allowed_tables is None:
        allowed_tables = ALLOWED_WIALON_TABLES
    
    # Normalize to lowercase for case-insensitive comparison
    table_lower = table.lower().strip()
    
    if table_lower not in {t.lower() for t in allowed_tables}:
        raise ValueError(
            f"Invalid table name: '{table}'. "
            f"Allowed tables: {', '.join(sorted(allowed_tables))}"
        )
    
    return table_lower


def validate_wialon_table(table: str) -> str:
    """Validate table name for Wialon database."""
    return validate_table_name(table, ALLOWED_WIALON_TABLES)


def validate_local_table(table: str) -> str:
    """Validate table name for local fuel_copilot database."""
    return validate_table_name(table, ALLOWED_LOCAL_TABLES)


def is_safe_identifier(identifier: str, max_length: int = 64) -> bool:
    """
    Check if a string is a safe SQL identifier (table/column name).
    
    Safe identifiers:
    - Start with letter or underscore
    - Contain only alphanumeric and underscore
    - Not longer than max_length (MySQL default is 64)
    
    Args:
        identifier: String to check
        max_length: Maximum allowed length
    
    Returns:
        bool: True if safe, False otherwise
    """
    if not identifier:
        return False
    
    if len(identifier) > max_length:
        return False
    
    # Must start with letter or underscore
    if not (identifier[0].isalpha() or identifier[0] == '_'):
        return False
    
    # Must contain only alphanumeric and underscore
    return all(c.isalnum() or c == '_' for c in identifier)
