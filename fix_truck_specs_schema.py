"""
Fix truck_specs table schema - add missing mpg_loaded and mpg_empty columns
"""

import logging

from sqlalchemy import text

from database_mysql import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_truck_specs_schema():
    """Add missing columns to truck_specs if they don't exist"""
    with get_db_connection() as conn:
        # Check if columns exist
        result = conn.execute(text("DESCRIBE truck_specs")).fetchall()
        columns = [row[0] for row in result]

        logger.info(f"Current columns: {columns}")

        # Add mpg_loaded if missing
        if "mpg_loaded" not in columns:
            logger.info("Adding mpg_loaded column...")
            conn.execute(
                text(
                    """
                ALTER TABLE truck_specs 
                ADD COLUMN mpg_loaded FLOAT NULL COMMENT 'MPG when loaded (from baseline)' 
                AFTER model
            """
                )
            )
            conn.commit()
            logger.info("✅ Added mpg_loaded column")
        else:
            logger.info("mpg_loaded column already exists")

        # Add mpg_empty if missing
        if "mpg_empty" not in columns:
            logger.info("Adding mpg_empty column...")
            conn.execute(
                text(
                    """
                ALTER TABLE truck_specs 
                ADD COLUMN mpg_empty FLOAT NULL COMMENT 'MPG when empty (from baseline)'
                AFTER mpg_loaded
            """
                )
            )
            conn.commit()
            logger.info("✅ Added mpg_empty column")
        else:
            logger.info("mpg_empty column already exists")

        # Verify
        result = conn.execute(text("DESCRIBE truck_specs")).fetchall()
        new_columns = [row[0] for row in result]
        logger.info(f"Updated columns: {new_columns}")


if __name__ == "__main__":
    fix_truck_specs_schema()
