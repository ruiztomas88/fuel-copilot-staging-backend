"""
Database Migration - Add Quick Wins Columns
Agrega columnas necesarias para Confidence Scoring y otros Quick Wins

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

import os
import logging
from datetime import datetime

import MySQLdb

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_database():
    """
    Agrega columnas a fuel_metrics para Quick Wins:
    - confidence_score: Score de confianza 0-100
    - confidence_level: Nivel de confianza (high/medium/low/very_low)
    - confidence_warnings: Warnings sobre calidad de datos
    """

    try:
        # Conectar a DB
        conn = MySQLdb.connect(
            host="localhost",
            user="fuel_admin",
            passwd=os.getenv("MYSQL_PASSWORD", ""),
            db="fuel_copilot",
        )
        cursor = conn.cursor()

        logger.info("Connected to fuel_copilot database")

        # =====================================================================
        # Verificar si columnas ya existen
        # =====================================================================
        cursor.execute(
            """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'fuel_copilot' 
            AND TABLE_NAME = 'fuel_metrics'
        """
        )
        existing_columns = [row[0] for row in cursor.fetchall()]

        logger.info(f"Found {len(existing_columns)} existing columns in fuel_metrics")

        # =====================================================================
        # 1. Agregar confidence_score
        # =====================================================================
        if "confidence_score" not in existing_columns:
            logger.info("Adding confidence_score column...")
            cursor.execute(
                """
                ALTER TABLE fuel_metrics 
                ADD COLUMN confidence_score DECIMAL(5,2) DEFAULT NULL 
                COMMENT 'Confidence score 0-100 for this estimation'
            """
            )
            conn.commit()
            logger.info("✓ confidence_score column added")
        else:
            logger.info("✓ confidence_score column already exists")

        # =====================================================================
        # 2. Agregar confidence_level
        # =====================================================================
        if "confidence_level" not in existing_columns:
            logger.info("Adding confidence_level column...")
            cursor.execute(
                """
                ALTER TABLE fuel_metrics 
                ADD COLUMN confidence_level VARCHAR(20) DEFAULT NULL 
                COMMENT 'Confidence level: high, medium, low, very_low'
            """
            )
            conn.commit()
            logger.info("✓ confidence_level column added")
        else:
            logger.info("✓ confidence_level column already exists")

        # =====================================================================
        # 3. Agregar confidence_warnings
        # =====================================================================
        if "confidence_warnings" not in existing_columns:
            logger.info("Adding confidence_warnings column...")
            cursor.execute(
                """
                ALTER TABLE fuel_metrics 
                ADD COLUMN confidence_warnings TEXT DEFAULT NULL 
                COMMENT 'Warnings about data quality issues (pipe-separated)'
            """
            )
            conn.commit()
            logger.info("✓ confidence_warnings column added")
        else:
            logger.info("✓ confidence_warnings column already exists")

        # =====================================================================
        # 4. Crear índice en confidence_level para queries rápidas
        # =====================================================================
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.STATISTICS 
            WHERE TABLE_SCHEMA = 'fuel_copilot' 
            AND TABLE_NAME = 'fuel_metrics' 
            AND INDEX_NAME = 'idx_confidence_level'
        """
        )
        index_exists = cursor.fetchone()[0] > 0

        if not index_exists and "confidence_level" in existing_columns:
            logger.info("Creating index on confidence_level...")
            cursor.execute(
                """
                CREATE INDEX idx_confidence_level 
                ON fuel_metrics(confidence_level)
            """
            )
            conn.commit()
            logger.info("✓ Index idx_confidence_level created")
        else:
            logger.info("✓ Index idx_confidence_level already exists or column missing")

        # =====================================================================
        # 5. Verificar estructura final
        # =====================================================================
        cursor.execute("DESCRIBE fuel_metrics")
        columns = cursor.fetchall()

        logger.info("\n" + "=" * 80)
        logger.info("FINAL FUEL_METRICS STRUCTURE:")
        logger.info("=" * 80)

        new_columns = ["confidence_score", "confidence_level", "confidence_warnings"]
        for col in columns:
            col_name = col[0]
            col_type = col[1]
            if col_name in new_columns:
                logger.info(f"  ✓ {col_name:30} {col_type}")

        logger.info("=" * 80)

        # =====================================================================
        # 6. Estadísticas de la tabla
        # =====================================================================
        cursor.execute("SELECT COUNT(*) FROM fuel_metrics")
        total_rows = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM fuel_metrics 
            WHERE confidence_score IS NOT NULL
        """
        )
        rows_with_confidence = cursor.fetchone()[0]

        logger.info(f"\nTotal rows in fuel_metrics: {total_rows:,}")
        logger.info(f"Rows with confidence data: {rows_with_confidence:,}")

        if total_rows > 0:
            logger.info(f"Coverage: {rows_with_confidence/total_rows*100:.1f}%")

        # =====================================================================
        # Close
        # =====================================================================
        cursor.close()
        conn.close()

        logger.info("\n✅ Database migration completed successfully!")
        logger.info("\nNext steps:")
        logger.info(
            "  1. Deploy updated wialon_sync_enhanced.py with confidence scoring"
        )
        logger.info("  2. Monitor logs to verify confidence_score is being calculated")
        logger.info("  3. Update dashboard to display confidence badges")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    logger.info("Starting database migration...")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("-" * 80)

    migrate_database()
