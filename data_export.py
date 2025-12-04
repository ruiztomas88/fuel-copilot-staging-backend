"""
Data Export Module v3.12.21
Export data to Excel and PDF formats

Addresses audit item #22: Export Excel/PDF

Features:
- Export fleet data to Excel with multiple sheets
- Generate PDF reports with charts
- Scheduled report generation
- Email delivery of reports
"""

import logging
import io
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================
def _get_db_config() -> Dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# EXPORT DATA CLASS
# =============================================================================
@dataclass
class ExportConfig:
    """Configuration for data export."""

    carrier_id: Optional[str] = None
    truck_ids: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_metrics: bool = True
    include_refuels: bool = True
    include_alerts: bool = True
    include_summary: bool = True
    format: str = "excel"  # excel, pdf, csv


# =============================================================================
# DATA EXPORTER
# =============================================================================
class DataExporter:
    """
    Export fleet data to various formats.

    Supports Excel, PDF, and CSV exports with configurable content.
    """

    # Report output directory
    OUTPUT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", "data/reports"))

    def __init__(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # EXCEL EXPORT
    # =========================================================================
    def export_to_excel(
        self,
        config: ExportConfig,
    ) -> bytes:
        """
        Export data to Excel format.

        Returns Excel file as bytes.
        """
        try:
            import pandas as pd
            from io import BytesIO
        except ImportError:
            logger.error("pandas required for Excel export")
            raise ImportError("Install pandas: pip install pandas openpyxl")

        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Summary sheet
            if config.include_summary:
                summary_df = self._get_summary_data(config)
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Metrics sheet
            if config.include_metrics:
                metrics_df = self._get_metrics_data(config)
                metrics_df.to_excel(writer, sheet_name="Fuel Metrics", index=False)

            # Refuels sheet
            if config.include_refuels:
                refuels_df = self._get_refuels_data(config)
                refuels_df.to_excel(writer, sheet_name="Refuel Events", index=False)

            # Alerts sheet
            if config.include_alerts:
                alerts_df = self._get_alerts_data(config)
                alerts_df.to_excel(writer, sheet_name="Alerts", index=False)

        output.seek(0)
        return output.read()

    def _get_summary_data(self, config: ExportConfig):
        """Get summary data for export."""
        import pandas as pd

        try:
            with get_db_connection() as conn:
                where_clauses = ["timestamp_utc >= %s", "timestamp_utc <= %s"]
                params = [
                    config.start_date or datetime.now(timezone.utc) - timedelta(days=7),
                    config.end_date or datetime.now(timezone.utc),
                ]

                if config.carrier_id and config.carrier_id != "*":
                    where_clauses.append("carrier_id = %s")
                    params.append(config.carrier_id)

                if config.truck_ids:
                    placeholders = ", ".join(["%s"] * len(config.truck_ids))
                    where_clauses.append(f"truck_id IN ({placeholders})")
                    params.extend(config.truck_ids)

                where_sql = " AND ".join(where_clauses)

                query = f"""
                    SELECT 
                        truck_id,
                        carrier_id,
                        COUNT(*) as data_points,
                        MIN(timestamp_utc) as first_reading,
                        MAX(timestamp_utc) as last_reading,
                        AVG(estimated_pct) as avg_fuel_pct,
                        AVG(mpg_current) as avg_mpg,
                        SUM(mileage_delta) as total_miles,
                        SUM(consumption_gph * 0.5) as total_gallons,
                        SUM(idle_duration_minutes) as total_idle_minutes
                    FROM fuel_metrics
                    WHERE {where_sql}
                    GROUP BY truck_id, carrier_id
                    ORDER BY truck_id
                """

                df = pd.read_sql(query, conn, params=params)

                # Calculate additional metrics
                if not df.empty:
                    df["fuel_cost"] = df["total_gallons"] * 3.50
                    df["cost_per_mile"] = df["fuel_cost"] / df["total_miles"].replace(
                        0, 1
                    )
                    df["idle_hours"] = df["total_idle_minutes"] / 60

                return df

        except Exception as e:
            logger.error(f"Error getting summary data: {e}")
            return pd.DataFrame()

    def _get_metrics_data(self, config: ExportConfig):
        """Get detailed metrics data for export."""
        import pandas as pd

        try:
            with get_db_connection() as conn:
                where_clauses = ["timestamp_utc >= %s", "timestamp_utc <= %s"]
                params = [
                    config.start_date or datetime.now(timezone.utc) - timedelta(days=7),
                    config.end_date or datetime.now(timezone.utc),
                ]

                if config.carrier_id and config.carrier_id != "*":
                    where_clauses.append("carrier_id = %s")
                    params.append(config.carrier_id)

                if config.truck_ids:
                    placeholders = ", ".join(["%s"] * len(config.truck_ids))
                    where_clauses.append(f"truck_id IN ({placeholders})")
                    params.extend(config.truck_ids)

                where_sql = " AND ".join(where_clauses)

                query = f"""
                    SELECT 
                        timestamp_utc,
                        truck_id,
                        carrier_id,
                        sensor_pct,
                        estimated_pct,
                        fuel_gallons,
                        mpg_current,
                        speed_mph,
                        mileage_delta,
                        consumption_gph,
                        truck_status,
                        idle_duration_minutes,
                        latitude,
                        longitude
                    FROM fuel_metrics
                    WHERE {where_sql}
                    ORDER BY timestamp_utc DESC
                    LIMIT 50000
                """

                return pd.read_sql(query, conn, params=params)

        except Exception as e:
            logger.error(f"Error getting metrics data: {e}")
            return pd.DataFrame()

    def _get_refuels_data(self, config: ExportConfig):
        """Get refuel events data for export."""
        import pandas as pd

        try:
            with get_db_connection() as conn:
                where_clauses = ["timestamp_utc >= %s", "timestamp_utc <= %s"]
                params = [
                    config.start_date or datetime.now(timezone.utc) - timedelta(days=7),
                    config.end_date or datetime.now(timezone.utc),
                ]

                if config.carrier_id and config.carrier_id != "*":
                    where_clauses.append("carrier_id = %s")
                    params.append(config.carrier_id)

                if config.truck_ids:
                    placeholders = ", ".join(["%s"] * len(config.truck_ids))
                    where_clauses.append(f"truck_id IN ({placeholders})")
                    params.extend(config.truck_ids)

                where_sql = " AND ".join(where_clauses)

                query = f"""
                    SELECT 
                        timestamp_utc,
                        truck_id,
                        carrier_id,
                        fuel_before_pct,
                        fuel_after_pct,
                        gallons_added,
                        cost_usd,
                        location_name,
                        latitude,
                        longitude,
                        confidence,
                        validated
                    FROM refuel_events
                    WHERE {where_sql}
                    ORDER BY timestamp_utc DESC
                """

                return pd.read_sql(query, conn, params=params)

        except Exception as e:
            logger.error(f"Error getting refuels data: {e}")
            return pd.DataFrame()

    def _get_alerts_data(self, config: ExportConfig):
        """Get alerts data for export."""
        import pandas as pd

        try:
            with get_db_connection() as conn:
                where_clauses = ["timestamp_utc >= %s", "timestamp_utc <= %s"]
                params = [
                    config.start_date or datetime.now(timezone.utc) - timedelta(days=7),
                    config.end_date or datetime.now(timezone.utc),
                ]

                if config.carrier_id and config.carrier_id != "*":
                    where_clauses.append("carrier_id = %s")
                    params.append(config.carrier_id)

                if config.truck_ids:
                    placeholders = ", ".join(["%s"] * len(config.truck_ids))
                    where_clauses.append(f"truck_id IN ({placeholders})")
                    params.extend(config.truck_ids)

                where_sql = " AND ".join(where_clauses)

                query = f"""
                    SELECT 
                        timestamp_utc,
                        truck_id,
                        carrier_id,
                        alert_type,
                        priority,
                        message,
                        acknowledged,
                        acknowledged_at,
                        acknowledged_by
                    FROM alerts
                    WHERE {where_sql}
                    ORDER BY timestamp_utc DESC
                """

                return pd.read_sql(query, conn, params=params)

        except Exception as e:
            logger.error(f"Error getting alerts data: {e}")
            return pd.DataFrame()

    # =========================================================================
    # CSV EXPORT
    # =========================================================================
    def export_to_csv(
        self,
        config: ExportConfig,
        data_type: str = "metrics",
    ) -> bytes:
        """
        Export data to CSV format.

        Args:
            config: Export configuration
            data_type: One of 'metrics', 'refuels', 'alerts', 'summary'

        Returns:
            CSV file as bytes
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("Install pandas: pip install pandas")

        if data_type == "metrics":
            df = self._get_metrics_data(config)
        elif data_type == "refuels":
            df = self._get_refuels_data(config)
        elif data_type == "alerts":
            df = self._get_alerts_data(config)
        elif data_type == "summary":
            df = self._get_summary_data(config)
        else:
            raise ValueError(f"Unknown data type: {data_type}")

        output = io.BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return output.read()

    # =========================================================================
    # PDF EXPORT
    # =========================================================================
    def export_to_pdf(
        self,
        config: ExportConfig,
    ) -> bytes:
        """
        Export data to PDF report format.

        Requires reportlab and matplotlib.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
                Image,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            import pandas as pd
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "Install reportlab and matplotlib: pip install reportlab matplotlib"
            )

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
        )
        elements.append(Paragraph("Fleet Fuel Analytics Report", title_style))

        # Date range
        start = config.start_date or datetime.now(timezone.utc) - timedelta(days=7)
        end = config.end_date or datetime.now(timezone.utc)
        elements.append(
            Paragraph(
                f"Period: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 20))

        # Summary table
        if config.include_summary:
            summary_df = self._get_summary_data(config)
            if not summary_df.empty:
                elements.append(Paragraph("Fleet Summary", styles["Heading2"]))

                # Convert to table data
                table_data = [summary_df.columns.tolist()]
                for _, row in summary_df.head(20).iterrows():
                    table_data.append([str(v)[:20] for v in row.values])

                table = Table(table_data)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("FONTSIZE", (0, 1), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]
                    )
                )
                elements.append(table)
                elements.append(Spacer(1, 20))

        # Fuel consumption chart
        if config.include_metrics:
            try:
                metrics_df = self._get_metrics_data(config)
                if not metrics_df.empty and "timestamp_utc" in metrics_df.columns:
                    # Create daily aggregation
                    metrics_df["date"] = pd.to_datetime(
                        metrics_df["timestamp_utc"]
                    ).dt.date
                    daily = (
                        metrics_df.groupby("date")
                        .agg(
                            {
                                "consumption_gph": "sum",
                                "mileage_delta": "sum",
                            }
                        )
                        .reset_index()
                    )

                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.bar(
                        range(len(daily)),
                        daily["consumption_gph"] * 0.5,
                        color="#3498db",
                    )
                    ax.set_xlabel("Day")
                    ax.set_ylabel("Gallons Consumed")
                    ax.set_title("Daily Fuel Consumption")

                    # Save chart to bytes
                    chart_buffer = io.BytesIO()
                    plt.savefig(
                        chart_buffer, format="png", dpi=100, bbox_inches="tight"
                    )
                    chart_buffer.seek(0)
                    plt.close()

                    elements.append(
                        Paragraph("Daily Fuel Consumption", styles["Heading2"])
                    )
                    elements.append(
                        Image(chart_buffer, width=8 * inch, height=3 * inch)
                    )
                    elements.append(Spacer(1, 20))
            except Exception as e:
                logger.error(f"Error creating chart: {e}")

        # Build PDF
        doc.build(elements)
        output.seek(0)
        return output.read()

    # =========================================================================
    # FILE MANAGEMENT
    # =========================================================================
    def save_report(
        self,
        data: bytes,
        filename: str,
    ) -> Path:
        """Save report to file."""
        filepath = self.OUTPUT_DIR / filename
        with open(filepath, "wb") as f:
            f.write(data)
        logger.info(f"Report saved: {filepath}")
        return filepath

    def generate_filename(
        self,
        config: ExportConfig,
        format: str = "xlsx",
    ) -> str:
        """Generate report filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        carrier = config.carrier_id or "all"
        return f"fleet_report_{carrier}_{timestamp}.{format}"


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_exporter: Optional[DataExporter] = None


def get_exporter() -> DataExporter:
    """Get or create DataExporter singleton."""
    global _exporter
    if _exporter is None:
        _exporter = DataExporter()
    return _exporter
