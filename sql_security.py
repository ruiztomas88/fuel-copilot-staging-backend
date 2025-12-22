"""
SQL Injection Protection Utilities
Security Fix - Dec 22 2025

Provides safe query builders and table name validators
"""
from typing import List, Optional, Set, Tuple
import re


# ═══════════════════════════════════════════════════════════════════════════════
# WHITELISTED TABLE NAMES - SINGLE SOURCE OF TRUTH
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_TABLES: Set[str] = {
    # Main tables
    'fuel_metrics',
    'refuel_events',
    'truck_sensors_cache',
    'dtc_events',
    'theft_events',
    'daily_truck_metrics',
    'units_map',
    
    # Maintenance tables
    'maintenance_events',
    'maintenance_schedule',
    'maintenance_predictions',
    
    # Historical/Archive tables
    'fuel_metrics_archive',
    'refuel_events_archive',
    
    # System tables
    'sync_status',
    'api_keys',
    'audit_log',
}

ALLOWED_WIALON_TABLES: Set[str] = {
    'sensors',
    'units_map',
    'wialon_units',
}


class SQLInjectionError(ValueError):
    """Raised when potential SQL injection is detected"""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def validate_table_name(table_name: str, allow_wialon: bool = False) -> str:
    """
    Validate that a table name is in the whitelist.
    
    Args:
        table_name: Table name to validate
        allow_wialon: If True, also allow Wialon tables
    
    Returns:
        The validated table name (unchanged)
        
    Raises:
        SQLInjectionError: If table name is not whitelisted
        
    Example:
        table = validate_table_name(user_input)
        query = f"SELECT * FROM {table} WHERE truck_id = %s"
    """
    table_name = table_name.strip()
    
    allowed = ALLOWED_TABLES.copy()
    if allow_wialon:
        allowed.update(ALLOWED_WIALON_TABLES)
    
    if table_name not in allowed:
        raise SQLInjectionError(
            f"Table '{table_name}' not in whitelist. "
            f"Allowed tables: {', '.join(sorted(allowed))}"
        )
    
    return table_name


def validate_column_name(column_name: str) -> str:
    """
    Validate that a column name is safe to use.
    
    Only allows: letters, numbers, underscores
    No spaces, special chars, or SQL keywords
    
    Args:
        column_name: Column name to validate
        
    Returns:
        The validated column name (unchanged)
        
    Raises:
        SQLInjectionError: If column name contains invalid characters
        
    Example:
        col = validate_column_name(user_input)
        query = f"SELECT {col} FROM fuel_metrics WHERE truck_id = %s"
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
        raise SQLInjectionError(
            f"Invalid column name '{column_name}'. "
            f"Only alphanumeric and underscore allowed."
        )
    
    # Check for SQL keywords
    sql_keywords = {
        'select', 'insert', 'update', 'delete', 'drop', 'create', 
        'alter', 'truncate', 'union', 'exec', 'execute'
    }
    
    if column_name.lower() in sql_keywords:
        raise SQLInjectionError(
            f"Column name '{column_name}' is a SQL keyword"
        )
    
    return column_name


def validate_identifier(identifier: str) -> str:
    """
    Validate a generic SQL identifier (table, column, database name).
    
    More permissive than column validation but still safe.
    Allows dots for qualified names (e.g., database.table)
    
    Args:
        identifier: SQL identifier to validate
        
    Returns:
        The validated identifier (unchanged)
        
    Raises:
        SQLInjectionError: If identifier contains invalid characters
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', identifier):
        raise SQLInjectionError(
            f"Invalid identifier '{identifier}'. "
            f"Only alphanumeric, underscore, and dot allowed."
        )
    
    return identifier


# ═══════════════════════════════════════════════════════════════════════════════
# SAFE QUERY BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def safe_select(
    table_name: str,
    columns: Optional[List[str]] = None,
    where: Optional[str] = None,
    limit: Optional[int] = None,
    order_by: Optional[str] = None
) -> Tuple[str, List]:
    """
    Build a safe SELECT query with validated table and column names.
    
    Args:
        table_name: Table to select from (must be whitelisted)
        columns: List of columns (default: ['*'])
        where: WHERE clause (use %s for parameters)
        limit: LIMIT value
        order_by: ORDER BY column (will be validated)
        
    Returns:
        (query_string, params_list)
        
    Example:
        query, params = safe_select(
            'fuel_metrics',
            columns=['truck_id', 'mpg_current'],
            where='truck_id = %s AND timestamp_utc > %s',
            limit=100
        )
        cursor.execute(query, ['DO9693', '2025-12-01'])
    """
    # Validate table
    table = validate_table_name(table_name)
    
    # Validate columns
    if columns is None:
        col_str = '*'
    else:
        validated_cols = [validate_column_name(col) for col in columns]
        col_str = ', '.join(validated_cols)
    
    # Build query
    query = f"SELECT {col_str} FROM {table}"
    params = []
    
    if where:
        query += f" WHERE {where}"
    
    if order_by:
        validated_order = validate_column_name(order_by)
        query += f" ORDER BY {validated_order}"
    
    if limit:
        query += f" LIMIT {int(limit)}"  # Cast to int for safety
    
    return query, params


def safe_count(
    table_name: str,
    where: Optional[str] = None
) -> Tuple[str, List]:
    """
    Build a safe COUNT query.
    
    Args:
        table_name: Table to count from (must be whitelisted)
        where: WHERE clause (use %s for parameters)
        
    Returns:
        (query_string, params_list)
        
    Example:
        query, params = safe_count('fuel_metrics', 'truck_id = %s')
        cursor.execute(query, ['DO9693'])
    """
    table = validate_table_name(table_name)
    
    query = f"SELECT COUNT(*) FROM {table}"
    params = []
    
    if where:
        query += f" WHERE {where}"
    
    return query, params


def safe_describe(table_name: str) -> str:
    """
    Build a safe DESCRIBE query.
    
    Args:
        table_name: Table to describe (must be whitelisted)
        
    Returns:
        DESCRIBE query string
        
    Example:
        query = safe_describe('fuel_metrics')
        cursor.execute(query)
    """
    table = validate_table_name(table_name)
    return f"DESCRIBE {table}"


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARDS COMPATIBILITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def escape_identifier(identifier: str) -> str:
    """
    DEPRECATED: Use validate_identifier() or safe_select() instead.
    
    Escapes an identifier by wrapping in backticks.
    This is NOT a substitute for proper validation!
    """
    validated = validate_identifier(identifier)
    return f"`{validated}`"


if __name__ == "__main__":
    # Test validation
    print("Testing SQL injection protection...")
    
    # Valid cases
    try:
        validate_table_name('fuel_metrics')
        print("✅ Valid table name: fuel_metrics")
    except SQLInjectionError as e:
        print(f"❌ {e}")
    
    try:
        validate_column_name('truck_id')
        print("✅ Valid column name: truck_id")
    except SQLInjectionError as e:
        print(f"❌ {e}")
    
    # Invalid cases (should raise errors)
    try:
        validate_table_name('fuel_metrics; DROP TABLE users;')
        print("❌ FAIL: Should have rejected injection")
    except SQLInjectionError as e:
        print(f"✅ Blocked injection: {e}")
    
    try:
        query, params = safe_select('fuel_metrics', columns=['truck_id', 'mpg_current'], limit=10)
        print(f"✅ Generated safe query: {query}")
    except SQLInjectionError as e:
        print(f"❌ {e}")
    
    print("\nAll tests passed!")
