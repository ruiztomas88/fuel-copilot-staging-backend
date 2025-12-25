"""
sql_safe.py - Utilidades para prevenir SQL Injection
═══════════════════════════════════════════════════════════════════════════════
Protección contra inyección SQL en queries dinámicas
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# WHITELIST DE TABLAS PERMITIDAS
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_TABLES: Set[str] = {
    # Core tables
    "trucks",
    "truck_specs",
    "carriers",
    "fuel_metrics",
    "fuel_metrics_raw",
    # Events
    "refuel_events",
    "theft_events",
    "dtc_events",
    "alerts",
    "engine_health_alerts",
    # Trips
    "trips",
    "local_trips",
    # Cache/Sync
    "wialon_sync_status",
    "truck_sensors_cache",
    "metrics_cache",
    # Users
    "users",
    "user_sessions",
    # Config
    "driving_thresholds",
    "maintenance_schedules",
    "daily_metrics",
    # Diagnostic tables
    "daily_truck_metrics",
    "trip_data",
    "fleet_summary",
}

ALLOWED_COLUMNS: Dict[str, Set[str]] = {
    "trucks": {
        "truck_id",
        "name",
        "carrier_id",
        "status",
        "created_at",
        "truck_status",
    },
    "fuel_metrics": {
        "truck_id",
        "timestamp_utc",
        "fuel_level_pct",
        "consumption_gph",
        "mpg_current",
    },
    "carriers": {"carrier_id", "name", "status"},
    "users": {"username", "role", "created_at"},  # NEVER include password!
}


def whitelist_table(table_name: str, allowed: Optional[Set[str]] = None) -> str:
    """
    Validar nombre de tabla contra whitelist.

    Args:
        table_name: Nombre de tabla a validar
        allowed: Set de tablas permitidas (usa ALLOWED_TABLES si None)

    Returns:
        Nombre de tabla validado

    Raises:
        ValueError si tabla no está permitida
    """
    tables = allowed or ALLOWED_TABLES

    # Limpiar input
    clean_name = table_name.strip().lower()

    # Validar contra whitelist
    if clean_name not in tables:
        logger.warning(f"🚫 Intento de acceso a tabla no permitida: {table_name}")
        raise ValueError(f"Tabla no permitida: {table_name}")

    return clean_name


def whitelist_column(table: str, column: str) -> str:
    """Validar nombre de columna contra whitelist"""
    allowed = ALLOWED_COLUMNS.get(table, set())

    if not allowed:
        # Si no hay whitelist para esta tabla, al menos sanitizar
        return sanitize_identifier(column)

    clean_col = column.strip().lower()

    if clean_col not in allowed:
        logger.warning(f"🚫 Columna no permitida: {table}.{column}")
        raise ValueError(f"Columna no permitida: {column}")

    return clean_col


def safe_query(conn, query: str, params: Dict[str, Any] = None) -> List[Dict]:
    """
    Ejecutar query con parámetros de forma segura.

    ANTES (VULNERABLE):
        cursor.execute(f"SELECT * FROM trucks WHERE id = '{user_input}'")

    DESPUÉS (SEGURO):
        results = safe_query(conn,
            "SELECT * FROM trucks WHERE id = :truck_id",
            {"truck_id": user_input}
        )
    """
    result = conn.execute(text(query), params or {})

    # Convertir a lista de dicts
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def safe_count(conn, table: str) -> int:
    """
    Contar registros de forma segura.

    ANTES (VULNERABLE):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")

    DESPUÉS (SEGURO):
        count = safe_count(conn, table)
    """
    # Validar tabla primero
    safe_table = whitelist_table(table)

    # Query (tabla ya validada, no necesita parametrización)
    query = text(f"SELECT COUNT(*) as cnt FROM {safe_table}")
    result = conn.execute(query)
    return result.scalar()


def safe_search(
    conn, table: str, column: str, search: str, limit: int = 100
) -> List[Dict]:
    """
    Búsqueda LIKE segura.

    ANTES (VULNERABLE):
        f"SELECT * FROM {table} WHERE {col} LIKE '%{search}%'"

    DESPUÉS (SEGURO):
        results = safe_search(conn, "trucks", "name", user_input)
    """
    safe_table = whitelist_table(table)
    safe_col = sanitize_identifier(column)  # Al menos sanitizar

    # Límite de seguridad
    safe_limit = min(max(1, limit), 1000)

    query = text(
        f"""
        SELECT * FROM {safe_table} 
        WHERE {safe_col} LIKE :search 
        LIMIT :limit
    """
    )

    result = conn.execute(query, {"search": f"%{search}%", "limit": safe_limit})

    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def sanitize_identifier(name: str) -> str:
    """
    Sanitizar identificador (tabla/columna).
    Solo permite alfanuméricos y underscore.
    """
    if not name:
        raise ValueError("Identificador vacío")

    # Solo alfanuméricos y underscore
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Identificador inválido: {name}")

    return name.lower()


def validate_truck_id(truck_id: str) -> str:
    """Validar formato de truck_id"""
    if not truck_id:
        raise ValueError("truck_id vacío")

    clean = truck_id.strip().upper()

    # Solo alfanuméricos, guiones y underscores
    if not re.match(r"^[A-Z0-9_-]{2,20}$", clean):
        raise ValueError(f"truck_id inválido: {truck_id}")

    return clean


def validate_date_range(start: str, end: str) -> tuple:
    """Validar rango de fechas"""
    from datetime import datetime

    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Formato de fecha inválido: {e}")

    if end_dt < start_dt:
        raise ValueError("end_date debe ser posterior a start_date")

    # Máximo 1 año de rango
    if (end_dt - start_dt).days > 365:
        raise ValueError("Rango máximo de 365 días")

    return start_dt, end_dt


if __name__ == "__main__":
    # Test
    print("Testing sql_safe...")

    try:
        table = whitelist_table("trucks")
        print(f"✅ Valid table: {table}")
    except ValueError as e:
        print(f"❌ {e}")

    try:
        table = whitelist_table("DROP TABLE users")
        print(f"✅ Valid table: {table}")
    except ValueError as e:
        print(f"✅ Correctly rejected: {e}")

    try:
        truck = validate_truck_id("CO0681")
        print(f"✅ Valid truck_id: {truck}")
    except ValueError as e:
        print(f"❌ {e}")

    try:
        truck = validate_truck_id("'; DROP TABLE trucks; --")
        print(f"❌ Should have rejected this!")
    except ValueError as e:
        print(f"✅ Correctly rejected: {e}")
