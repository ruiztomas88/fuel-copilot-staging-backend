"""
Example 2: Smart Alerts based on truck-specific MPG baselines

Generate alerts when trucks underperform their expected MPG
"""

from datetime import datetime

from truck_specs_engine import get_truck_specs_engine, validate_truck_mpg


def check_fleet_mpg_alerts(threshold_pct: float = 20.0) -> list:
    """
    Check all trucks and generate alerts for underperformers

    Args:
        threshold_pct: Alert if MPG is this % below baseline

    Returns:
        List of alerts
    """
    # Simulate current MPG readings (in reality, get from database)
    current_readings = {
        "MR7679": 5.2,  # 2017 Freightliner - should be 6.8
        "MJ9547": 7.5,  # 2023 Kenworth T680 - should be 7.8
        "JR7099": 3.8,  # 2006 Freightliner Century - should be 5.0
        "OM7769": 4.2,  # 2006 Kenworth T600 - should be 5.0
    }

    alerts = []

    for truck_id, current_mpg in current_readings.items():
        result = validate_truck_mpg(truck_id, current_mpg, is_loaded=True)

        if result["status"] in ["WARNING", "CRITICAL"]:
            alerts.append(
                {
                    "truck_id": truck_id,
                    "truck_info": result["truck_info"],
                    "current_mpg": current_mpg,
                    "expected_mpg": result["expected_mpg"],
                    "deviation_pct": result["deviation_pct"],
                    "severity": result["status"],
                    "message": result["message"],
                    "timestamp": datetime.now().isoformat(),
                }
            )

    return alerts


def format_alert_email(alerts: list) -> str:
    """Format alerts for email notification"""
    if not alerts:
        return "✅ All trucks operating within expected MPG ranges"

    email = f"⚠️ MPG Performance Alerts - {len(alerts)} trucks underperforming\n\n"

    critical = [a for a in alerts if a["severity"] == "CRITICAL"]
    warnings = [a for a in alerts if a["severity"] == "WARNING"]

    if critical:
        email += f"🚨 CRITICAL ({len(critical)}):\n"
        for alert in critical:
            email += f"  • {alert['truck_id']} ({alert['truck_info']})\n"
            email += f"    Current: {alert['current_mpg']:.1f} MPG | Expected: {alert['expected_mpg']:.1f} MPG | {alert['deviation_pct']:.1f}%\n"
        email += "\n"

    if warnings:
        email += f"⚠️  WARNING ({len(warnings)}):\n"
        for alert in warnings:
            email += f"  • {alert['truck_id']} ({alert['truck_info']})\n"
            email += f"    Current: {alert['current_mpg']:.1f} MPG | Expected: {alert['expected_mpg']:.1f} MPG | {alert['deviation_pct']:.1f}%\n"

    return email


if __name__ == "__main__":
    print("Checking fleet MPG performance...\n")

    alerts = check_fleet_mpg_alerts(threshold_pct=15.0)

    print(format_alert_email(alerts))

    # Could also send to Slack, email, etc.
    # send_slack_alert(format_alert_email(alerts))
