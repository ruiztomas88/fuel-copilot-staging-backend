"""
Daily Reports Generator - Automated Fleet Summary Reports

Generates and sends daily reports via email with:
- Fleet-wide fuel consumption summary
- Per-truck performance metrics
- Top/bottom performers ranking
- Refuel events summary
- Alert/incident summary
- Recommendations

Can be scheduled via cron or used standalone.

Author: Fuel Copilot Team
Version: v3.4.0
Date: November 25, 2025

Usage:
    # Generate report for yesterday
    python daily_reports.py

    # Generate report for specific date
    python daily_reports.py --date 2024-11-25

    # Send via email
    python daily_reports.py --send

    # Schedule with cron (daily at 6 AM):
    # 0 6 * * * cd /path/to/fuel_copilot && python daily_reports.py --send
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

from timezone_utils import (
    utc_now,
    get_today_local,
    local_to_utc,
    format_local,
    BUSINESS_TZ,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class TruckDailySummary:
    """Daily summary for a single truck"""

    truck_id: str

    # Distance & Fuel
    total_miles: float = 0.0
    total_gallons_consumed: float = 0.0
    avg_mpg: Optional[float] = None

    # Idle
    total_idle_hours: float = 0.0
    total_idle_gallons: float = 0.0

    # Refuels
    refuel_count: int = 0
    total_refuel_gallons: float = 0.0

    # Health & Alerts
    avg_health_score: float = 0.0
    avg_drift_pct: float = 0.0
    max_drift_pct: float = 0.0
    alerts_count: int = 0

    # Operational
    moving_hours: float = 0.0
    stopped_hours: float = 0.0
    offline_hours: float = 0.0

    # Timestamps
    first_reading: Optional[datetime] = None
    last_reading: Optional[datetime] = None

    def efficiency_score(self) -> float:
        """Calculate efficiency score (0-100)"""
        score = 100.0

        # MPG penalty/bonus (benchmark 6.5 MPG)
        if self.avg_mpg:
            if self.avg_mpg < 5.5:
                score -= 20
            elif self.avg_mpg < 6.0:
                score -= 10
            elif self.avg_mpg > 7.0:
                score += 10
            elif self.avg_mpg > 7.5:
                score += 15

        # Idle penalty (>2 hours is excessive)
        if self.total_idle_hours > 4:
            score -= 15
        elif self.total_idle_hours > 2:
            score -= 5

        # Drift penalty
        if self.max_drift_pct > 15:
            score -= 15
        elif self.max_drift_pct > 10:
            score -= 10

        return max(0, min(100, score))


@dataclass
class FleetDailySummary:
    """Daily summary for entire fleet"""

    report_date: date
    generated_at: datetime = field(default_factory=utc_now)

    # Fleet totals
    total_trucks: int = 0
    active_trucks: int = 0  # Had at least 1 reading

    # Distance & Fuel
    total_fleet_miles: float = 0.0
    total_fleet_gallons: float = 0.0
    avg_fleet_mpg: Optional[float] = None

    # Idle
    total_fleet_idle_hours: float = 0.0
    total_fleet_idle_gallons: float = 0.0

    # Refuels
    total_refuel_events: int = 0
    total_refuel_gallons: float = 0.0

    # Health
    avg_fleet_health: float = 0.0
    trucks_critical: int = 0
    trucks_warning: int = 0

    # Alerts
    total_alerts: int = 0
    critical_alerts: int = 0

    # Per-truck summaries
    truck_summaries: List[TruckDailySummary] = field(default_factory=list)

    def top_performers(self, n: int = 5) -> List[TruckDailySummary]:
        """Get top N trucks by efficiency score"""
        sorted_trucks = sorted(
            [t for t in self.truck_summaries if t.total_miles > 10],
            key=lambda t: t.efficiency_score(),
            reverse=True,
        )
        return sorted_trucks[:n]

    def bottom_performers(self, n: int = 5) -> List[TruckDailySummary]:
        """Get bottom N trucks by efficiency score"""
        sorted_trucks = sorted(
            [t for t in self.truck_summaries if t.total_miles > 10],
            key=lambda t: t.efficiency_score(),
        )
        return sorted_trucks[:n]

    def high_drift_trucks(self, threshold: float = 10.0) -> List[TruckDailySummary]:
        """Get trucks with drift exceeding threshold"""
        return [t for t in self.truck_summaries if t.max_drift_pct > threshold]


class DailyReportGenerator:
    """Generates daily fleet reports from database"""

    def __init__(self, db_config: Optional[Dict] = None):
        self.db_config = db_config or self._get_db_config()
        self._engine = None

    def _get_db_config(self) -> Dict:
        """Get database configuration from environment"""
        return {
            "host": os.getenv("LOCAL_DB_HOST", "localhost"),
            "port": int(os.getenv("LOCAL_DB_PORT", "3306")),
            "user": os.getenv("LOCAL_DB_USER", "fuel_admin"),
            "password": os.getenv("LOCAL_DB_PASS", ""),
            "database": os.getenv("LOCAL_DB_NAME", "fuel_copilot"),
        }

    def _get_engine(self):
        """Get SQLAlchemy engine"""
        if self._engine is None:
            from sqlalchemy import create_engine

            config = self.db_config
            connection_string = (
                f"mysql+pymysql://{config['user']}:{config['password']}"
                f"@{config['host']}:{config['port']}/{config['database']}"
                f"?charset=utf8mb4"
            )
            self._engine = create_engine(connection_string, pool_pre_ping=True)
        return self._engine

    def generate_report(self, report_date: date) -> FleetDailySummary:
        """
        Generate daily report for specified date

        Args:
            report_date: Date to generate report for

        Returns:
            FleetDailySummary with all metrics
        """
        logger.info(f"📊 Generating daily report for {report_date}")

        # Initialize summary
        summary = FleetDailySummary(report_date=report_date)

        try:
            # Get data from database
            truck_data = self._fetch_truck_data(report_date)

            if not truck_data:
                logger.warning(f"No data found for {report_date}")
                return summary

            # Process each truck
            for truck_id, readings in truck_data.items():
                truck_summary = self._process_truck_readings(truck_id, readings)
                summary.truck_summaries.append(truck_summary)

            # Calculate fleet totals
            summary.total_trucks = len(summary.truck_summaries)
            summary.active_trucks = len(
                [
                    t
                    for t in summary.truck_summaries
                    if t.total_miles > 0 or t.first_reading is not None
                ]
            )

            summary.total_fleet_miles = sum(
                t.total_miles for t in summary.truck_summaries
            )
            summary.total_fleet_gallons = sum(
                t.total_gallons_consumed for t in summary.truck_summaries
            )

            if summary.total_fleet_gallons > 0:
                summary.avg_fleet_mpg = (
                    summary.total_fleet_miles / summary.total_fleet_gallons
                )

            summary.total_fleet_idle_hours = sum(
                t.total_idle_hours for t in summary.truck_summaries
            )
            summary.total_fleet_idle_gallons = sum(
                t.total_idle_gallons for t in summary.truck_summaries
            )

            summary.total_refuel_events = sum(
                t.refuel_count for t in summary.truck_summaries
            )
            summary.total_refuel_gallons = sum(
                t.total_refuel_gallons for t in summary.truck_summaries
            )

            summary.avg_fleet_health = (
                sum(t.avg_health_score for t in summary.truck_summaries)
                / len(summary.truck_summaries)
                if summary.truck_summaries
                else 0
            )

            summary.trucks_critical = len(
                [t for t in summary.truck_summaries if t.avg_health_score < 50]
            )
            summary.trucks_warning = len(
                [t for t in summary.truck_summaries if 50 <= t.avg_health_score < 75]
            )

            summary.total_alerts = sum(t.alerts_count for t in summary.truck_summaries)

            logger.info(
                f"✅ Report generated: {summary.active_trucks} active trucks, "
                f"{summary.total_fleet_miles:.0f} miles, {summary.total_fleet_gallons:.0f} gallons"
            )

        except Exception as e:
            logger.error(f"❌ Failed to generate report: {e}")
            import traceback

            traceback.print_exc()

        return summary

    def _fetch_truck_data(self, report_date: date) -> Dict[str, List[Dict]]:
        """Fetch truck data from database for the given date"""
        from sqlalchemy import text

        engine = self._get_engine()

        # Query for all readings on the given date
        query = text(
            """
            SELECT 
                truck_id,
                timestamp_utc,
                truck_status,
                estimated_gallons,
                consumption_gph,
                mpg_current,
                drift_pct,
                refuel_gallons,
                odometer_mi,
                idle_mode,
                speed_mph
            FROM fuel_metrics
            WHERE DATE(timestamp_utc) = :report_date
            ORDER BY truck_id, timestamp_utc
        """
        )

        with engine.connect() as conn:
            result = conn.execute(query, {"report_date": report_date})
            rows = result.fetchall()

        # Group by truck_id
        truck_data = {}
        for row in rows:
            truck_id = row[0]
            if truck_id not in truck_data:
                truck_data[truck_id] = []
            truck_data[truck_id].append(
                {
                    "timestamp_utc": row[1],
                    "truck_status": row[2],
                    "estimated_gallons": row[3],
                    "consumption_gph": row[4],
                    "mpg_current": row[5],
                    "drift_pct": row[6],
                    "refuel_gallons": row[7],
                    "odometer_mi": row[8],
                    "idle_mode": row[9],
                    "speed_mph": row[10],
                }
            )

        return truck_data

    def _process_truck_readings(
        self, truck_id: str, readings: List[Dict]
    ) -> TruckDailySummary:
        """Process readings for a single truck"""
        summary = TruckDailySummary(truck_id=truck_id)

        if not readings:
            return summary

        # Timestamps
        summary.first_reading = readings[0]["timestamp_utc"]
        summary.last_reading = readings[-1]["timestamp_utc"]

        # Calculate totals
        mpg_values = []
        drift_values = []
        prev_odom = None

        for reading in readings:
            # Distance from odometer delta
            if reading["odometer_mi"] and prev_odom:
                delta_mi = reading["odometer_mi"] - prev_odom
                if 0 < delta_mi < 100:  # Sanity check
                    summary.total_miles += delta_mi
            prev_odom = reading["odometer_mi"]

            # MPG
            if reading["mpg_current"]:
                mpg_values.append(reading["mpg_current"])

            # Drift
            if reading["drift_pct"] is not None:
                drift_values.append(abs(reading["drift_pct"]))

            # Refuels
            if reading["refuel_gallons"] and reading["refuel_gallons"] > 0:
                summary.refuel_count += 1
                summary.total_refuel_gallons += reading["refuel_gallons"]

            # Status hours (assuming ~20s intervals)
            interval_hours = 20 / 3600
            status = reading["truck_status"]
            if status == "MOVING":
                summary.moving_hours += interval_hours
            elif status == "STOPPED":
                summary.stopped_hours += interval_hours
                # Idle consumption
                if reading["consumption_gph"]:
                    summary.total_idle_hours += interval_hours
                    summary.total_idle_gallons += (
                        reading["consumption_gph"] * interval_hours
                    )
            elif status == "OFFLINE":
                summary.offline_hours += interval_hours

        # Calculate fuel consumed from readings
        if readings:
            first_fuel = readings[0].get("estimated_gallons")
            last_fuel = readings[-1].get("estimated_gallons")
            if first_fuel and last_fuel:
                # Account for refuels
                base_consumption = first_fuel - last_fuel + summary.total_refuel_gallons
                if base_consumption > 0:
                    summary.total_gallons_consumed = base_consumption

        # Averages
        if mpg_values:
            summary.avg_mpg = sum(mpg_values) / len(mpg_values)

        if drift_values:
            summary.avg_drift_pct = sum(drift_values) / len(drift_values)
            summary.max_drift_pct = max(drift_values)

        return summary


class EmailReportSender:
    """Sends reports via email"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("REPORT_FROM_EMAIL", self.smtp_user)
        self.to_emails = os.getenv("REPORT_TO_EMAILS", "").split(",")

    def is_configured(self) -> bool:
        """Check if email is configured"""
        return bool(self.smtp_user and self.smtp_password and any(self.to_emails))

    def send_report(self, summary: FleetDailySummary) -> bool:
        """Send report via email"""
        if not self.is_configured():
            logger.warning(
                "⚠️ Email not configured. Set SMTP_* and REPORT_TO_EMAILS in .env"
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚛 Fleet Daily Report - {summary.report_date}"
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)

            # Plain text version
            text_content = self._generate_text_report(summary)
            msg.attach(MIMEText(text_content, "plain"))

            # HTML version
            html_content = self._generate_html_report(summary)
            msg.attach(MIMEText(html_content, "html"))

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"📧 Report sent to {', '.join(self.to_emails)}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            return False

    def _generate_text_report(self, summary: FleetDailySummary) -> str:
        """Generate plain text report"""
        lines = [
            f"FUEL COPILOT DAILY REPORT",
            f"Date: {summary.report_date}",
            f"Generated: {format_local(summary.generated_at)}",
            "",
            "=" * 50,
            "FLEET OVERVIEW",
            "=" * 50,
            f"Total Trucks: {summary.total_trucks}",
            f"Active Trucks: {summary.active_trucks}",
            f"Total Miles: {summary.total_fleet_miles:,.0f}",
            f"Total Gallons: {summary.total_fleet_gallons:,.1f}",
            (
                f"Avg Fleet MPG: {summary.avg_fleet_mpg:.2f}"
                if summary.avg_fleet_mpg
                else "Avg Fleet MPG: N/A"
            ),
            "",
            f"Total Idle Hours: {summary.total_fleet_idle_hours:.1f}",
            f"Total Idle Gallons: {summary.total_fleet_idle_gallons:.1f}",
            "",
            f"Refuel Events: {summary.total_refuel_events}",
            f"Refuel Gallons: {summary.total_refuel_gallons:.1f}",
            "",
            f"Avg Health Score: {summary.avg_fleet_health:.0f}/100",
            f"Trucks Critical: {summary.trucks_critical}",
            f"Trucks Warning: {summary.trucks_warning}",
        ]

        # Top performers
        top = summary.top_performers(5)
        if top:
            lines.extend(
                [
                    "",
                    "=" * 50,
                    "TOP PERFORMERS",
                    "=" * 50,
                ]
            )
            for i, t in enumerate(top, 1):
                mpg_str = f"{t.avg_mpg:.1f}" if t.avg_mpg else "N/A"
                lines.append(
                    f"{i}. {t.truck_id}: {t.total_miles:.0f} mi, {mpg_str} MPG, Score: {t.efficiency_score():.0f}"
                )

        # Bottom performers
        bottom = summary.bottom_performers(5)
        if bottom:
            lines.extend(
                [
                    "",
                    "=" * 50,
                    "NEEDS ATTENTION",
                    "=" * 50,
                ]
            )
            for i, t in enumerate(bottom, 1):
                mpg_str = f"{t.avg_mpg:.1f}" if t.avg_mpg else "N/A"
                lines.append(
                    f"{i}. {t.truck_id}: {t.total_miles:.0f} mi, {mpg_str} MPG, Score: {t.efficiency_score():.0f}"
                )

        # High drift
        high_drift = summary.high_drift_trucks(10.0)
        if high_drift:
            lines.extend(
                [
                    "",
                    "=" * 50,
                    "HIGH DRIFT TRUCKS (>10%)",
                    "=" * 50,
                ]
            )
            for t in high_drift:
                lines.append(
                    f"- {t.truck_id}: Max {t.max_drift_pct:.1f}%, Avg {t.avg_drift_pct:.1f}%"
                )

        return "\n".join(lines)

    def _generate_html_report(self, summary: FleetDailySummary) -> str:
        """Generate HTML report"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
                .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
                .metric-label {{ font-size: 12px; color: #7f8c8d; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
                th {{ background-color: #3498db; color: white; }}
                tr:nth-child(even) {{ background-color: #ecf0f1; }}
                .good {{ color: #27ae60; }}
                .warning {{ color: #f39c12; }}
                .critical {{ color: #e74c3c; }}
            </style>
        </head>
        <body>
            <h1>🚛 Fleet Daily Report</h1>
            <p>Date: <strong>{summary.report_date}</strong> | Generated: {format_local(summary.generated_at)}</p>
            
            <h2>📊 Fleet Overview</h2>
            <div>
                <div class="metric">
                    <div class="metric-value">{summary.active_trucks}/{summary.total_trucks}</div>
                    <div class="metric-label">Active Trucks</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{summary.total_fleet_miles:,.0f}</div>
                    <div class="metric-label">Total Miles</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{summary.total_fleet_gallons:,.1f}</div>
                    <div class="metric-label">Total Gallons</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{summary.avg_fleet_mpg:.2f if summary.avg_fleet_mpg else 'N/A'}</div>
                    <div class="metric-label">Avg MPG</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{summary.avg_fleet_health:.0f}</div>
                    <div class="metric-label">Avg Health</div>
                </div>
            </div>
            
            <h2>🏆 Top Performers</h2>
            <table>
                <tr><th>Rank</th><th>Truck</th><th>Miles</th><th>MPG</th><th>Score</th></tr>
        """

        for i, t in enumerate(summary.top_performers(5), 1):
            mpg = f"{t.avg_mpg:.1f}" if t.avg_mpg else "N/A"
            html += f"<tr><td>{i}</td><td>{t.truck_id}</td><td>{t.total_miles:.0f}</td><td>{mpg}</td><td class='good'>{t.efficiency_score():.0f}</td></tr>"

        html += """
            </table>
            
            <h2>⚠️ Needs Attention</h2>
            <table>
                <tr><th>Rank</th><th>Truck</th><th>Miles</th><th>MPG</th><th>Score</th></tr>
        """

        for i, t in enumerate(summary.bottom_performers(5), 1):
            mpg = f"{t.avg_mpg:.1f}" if t.avg_mpg else "N/A"
            score_class = "critical" if t.efficiency_score() < 50 else "warning"
            html += f"<tr><td>{i}</td><td>{t.truck_id}</td><td>{t.total_miles:.0f}</td><td>{mpg}</td><td class='{score_class}'>{t.efficiency_score():.0f}</td></tr>"

        # High drift trucks
        high_drift = summary.high_drift_trucks(10.0)
        if high_drift:
            html += """
                </table>
                
                <h2>🔴 High Drift Trucks (&gt;10%)</h2>
                <table>
                    <tr><th>Truck</th><th>Max Drift</th><th>Avg Drift</th></tr>
            """
            for t in high_drift:
                html += f"<tr><td>{t.truck_id}</td><td class='critical'>{t.max_drift_pct:.1f}%</td><td>{t.avg_drift_pct:.1f}%</td></tr>"

        html += """
            </table>
            
            <hr>
            <p style="color: #7f8c8d; font-size: 11px;">
                Generated by Fuel Copilot v3.4.0 | © 2024
            </p>
        </body>
        </html>
        """

        return html


def save_report_to_file(
    summary: FleetDailySummary, output_dir: str = "data/reports"
) -> str:
    """Save report to JSON file"""
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(output_dir, f"daily_report_{summary.report_date}.json")

    # Convert to serializable format
    data = {
        "report_date": str(summary.report_date),
        "generated_at": summary.generated_at.isoformat(),
        "total_trucks": summary.total_trucks,
        "active_trucks": summary.active_trucks,
        "total_fleet_miles": summary.total_fleet_miles,
        "total_fleet_gallons": summary.total_fleet_gallons,
        "avg_fleet_mpg": summary.avg_fleet_mpg,
        "total_fleet_idle_hours": summary.total_fleet_idle_hours,
        "total_fleet_idle_gallons": summary.total_fleet_idle_gallons,
        "total_refuel_events": summary.total_refuel_events,
        "total_refuel_gallons": summary.total_refuel_gallons,
        "avg_fleet_health": summary.avg_fleet_health,
        "trucks_critical": summary.trucks_critical,
        "trucks_warning": summary.trucks_warning,
        "total_alerts": summary.total_alerts,
        "truck_summaries": [
            {
                "truck_id": t.truck_id,
                "total_miles": t.total_miles,
                "total_gallons_consumed": t.total_gallons_consumed,
                "avg_mpg": t.avg_mpg,
                "total_idle_hours": t.total_idle_hours,
                "total_idle_gallons": t.total_idle_gallons,
                "refuel_count": t.refuel_count,
                "total_refuel_gallons": t.total_refuel_gallons,
                "avg_health_score": t.avg_health_score,
                "avg_drift_pct": t.avg_drift_pct,
                "max_drift_pct": t.max_drift_pct,
                "efficiency_score": t.efficiency_score(),
            }
            for t in summary.truck_summaries
        ],
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"📄 Report saved to {filename}")
    return filename


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate daily fleet reports")
    parser.add_argument(
        "--date", type=str, help="Report date (YYYY-MM-DD). Default: yesterday"
    )
    parser.add_argument("--send", action="store_true", help="Send report via email")
    parser.add_argument(
        "--output",
        type=str,
        default="data/reports",
        help="Output directory for JSON reports",
    )

    args = parser.parse_args()

    # Determine report date
    if args.date:
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        # Default to yesterday
        report_date = (get_today_local() - timedelta(days=1)).date()

    logger.info(f"🚀 Starting Daily Report Generator")
    logger.info(f"   Report Date: {report_date}")

    # Generate report
    generator = DailyReportGenerator()
    summary = generator.generate_report(report_date)

    # Save to file
    save_report_to_file(summary, args.output)

    # Print summary
    print("\n" + "=" * 60)
    print(f"DAILY REPORT - {report_date}")
    print("=" * 60)
    print(f"Active Trucks: {summary.active_trucks}/{summary.total_trucks}")
    print(f"Total Miles: {summary.total_fleet_miles:,.0f}")
    print(f"Total Gallons: {summary.total_fleet_gallons:,.1f}")
    print(
        f"Avg MPG: {summary.avg_fleet_mpg:.2f}"
        if summary.avg_fleet_mpg
        else "Avg MPG: N/A"
    )
    print(f"Avg Health: {summary.avg_fleet_health:.0f}/100")
    print("=" * 60)

    # Send via email if requested
    if args.send:
        sender = EmailReportSender()
        sender.send_report(summary)


if __name__ == "__main__":
    main()
