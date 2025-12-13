"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                            ADMIN ROUTER                                        ║
║              Super Admin Only - Carriers, Users, System Stats                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - GET /admin/carriers  → List all carriers                                    ║
║  - GET /admin/users     → List all users                                       ║
║  - GET /admin/stats     → System-wide statistics                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

@version 5.6.0
@date December 2025
"""

from fastapi import APIRouter, HTTPException, Depends
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelAnalytics/api/admin",
    tags=["Admin"],
)

# Import auth dependencies
try:
    from auth import require_super_admin, TokenData, USERS_DB
except ImportError:
    from ..auth import require_super_admin, TokenData, USERS_DB


@router.get("/carriers")
async def list_carriers(current_user: TokenData = Depends(require_super_admin)):
    """
    List all carriers (super_admin only).
    Reads from MySQL carriers table.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT carrier_id, name, contact_email, timezone, 
                       created_at, updated_at, active
                FROM carriers
                ORDER BY name
            """
                )
            )
            carriers = [dict(row._mapping) for row in result]

            # Add truck count for each carrier
            for carrier in carriers:
                count_result = conn.execute(
                    text(
                        """
                    SELECT COUNT(DISTINCT truck_id) as truck_count
                    FROM fuel_metrics
                    WHERE carrier_id = :carrier_id
                """
                    ),
                    {"carrier_id": carrier["carrier_id"]},
                )
                carrier["truck_count"] = count_result.scalar() or 0

            return {"carriers": carriers, "total": len(carriers)}
    except Exception as e:
        logger.error(f"Error listing carriers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def list_users(current_user: TokenData = Depends(require_super_admin)):
    """List all users (super_admin only)."""
    users = []
    for username, user_data in USERS_DB.items():
        users.append(
            {
                "username": username,
                "name": user_data["name"],
                "carrier_id": user_data["carrier_id"],
                "role": user_data["role"],
                "email": user_data.get("email"),
                "active": user_data.get("active", True),
            }
        )
    return {"users": users, "total": len(users)}


@router.get("/stats")
async def get_admin_stats(current_user: TokenData = Depends(require_super_admin)):
    """
    Get system-wide statistics (super_admin only).
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            # Total records
            total_records = conn.execute(
                text("SELECT COUNT(*) FROM fuel_metrics")
            ).scalar()

            # Records by carrier
            carrier_stats = conn.execute(
                text(
                    """
                SELECT carrier_id, 
                       COUNT(*) as records,
                       COUNT(DISTINCT truck_id) as trucks,
                       MIN(timestamp_utc) as first_record,
                       MAX(timestamp_utc) as last_record
                FROM fuel_metrics
                GROUP BY carrier_id
            """
                )
            )

            carriers = [dict(row._mapping) for row in carrier_stats]

            # Total refuels
            total_refuels = (
                conn.execute(text("SELECT COUNT(*) FROM refuel_events")).scalar() or 0
            )

            return {
                "total_records": total_records,
                "total_refuels": total_refuels,
                "carriers": carriers,
                "users_count": len(USERS_DB),
            }
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
