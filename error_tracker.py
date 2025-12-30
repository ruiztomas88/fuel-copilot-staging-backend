"""
Error Tracking and Analysis Module
Tracks backend errors and generates diagnostic reports
"""

import json
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ERRORS_FILE = Path(__file__).parent / "logs" / "error_tracking.json"
ERRORS_FILE.parent.mkdir(exist_ok=True)


class ErrorTracker:
    """Track and analyze backend errors"""

    def __init__(self):
        self.errors: List[Dict] = []
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.load_errors()

    def load_errors(self):
        """Load error history from file"""
        if ERRORS_FILE.exists():
            try:
                with open(ERRORS_FILE, "r") as f:
                    data = json.load(f)
                    self.errors = data.get("errors", [])
                    self.error_counts = defaultdict(int, data.get("error_counts", {}))
            except Exception:
                pass

    def save_errors(self):
        """Save error history to file"""
        try:
            with open(ERRORS_FILE, "w") as f:
                json.dump(
                    {
                        "errors": self.errors[-1000:],  # Keep last 1000 errors
                        "error_counts": dict(self.error_counts),
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def track_error(
        self,
        error: Exception,
        context: str = "",
        endpoint: str = "",
        request_data: Optional[Dict] = None,
    ):
        """Track an error occurrence"""
        error_type = type(error).__name__
        error_msg = str(error)

        self.error_counts[error_type] += 1

        error_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": error_type,
            "message": error_msg,
            "context": context,
            "endpoint": endpoint,
            "request_data": request_data,
            "traceback": traceback.format_exc(),
            "count": self.error_counts[error_type],
        }

        self.errors.append(error_record)
        self.save_errors()

        return error_record

    def get_error_summary(self, last_hours: int = 24) -> Dict:
        """Get error summary for last N hours"""
        cutoff = datetime.now(timezone.utc).timestamp() - (last_hours * 3600)

        recent_errors = [
            e
            for e in self.errors
            if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff
        ]

        error_types = defaultdict(int)
        error_endpoints = defaultdict(int)

        for error in recent_errors:
            error_types[error["type"]] += 1
            if error.get("endpoint"):
                error_endpoints[error["endpoint"]] += 1

        return {
            "period_hours": last_hours,
            "total_errors": len(recent_errors),
            "error_types": dict(error_types),
            "error_endpoints": dict(error_endpoints),
            "most_common_error": (
                max(error_types, key=error_types.get) if error_types else None
            ),
            "recent_errors": recent_errors[-10:],  # Last 10 errors
        }

    def get_top_errors(self, limit: int = 10) -> List[Dict]:
        """Get top errors by frequency"""
        sorted_errors = sorted(
            self.error_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [
            {"type": err_type, "count": count}
            for err_type, count in sorted_errors[:limit]
        ]

    def clear_old_errors(self, days: int = 7):
        """Clear errors older than N days"""
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

        self.errors = [
            e
            for e in self.errors
            if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff
        ]

        self.save_errors()


# Global error tracker instance
error_tracker = ErrorTracker()


def generate_diagnostic_report() -> str:
    """Generate a diagnostic report of system errors"""
    summary = error_tracker.get_error_summary(24)
    top_errors = error_tracker.get_top_errors()

    report = []
    report.append("=" * 80)
    report.append("BACKEND DIAGNOSTIC REPORT")
    report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    report.append("=" * 80)
    report.append("")

    report.append(f"📊 Last 24 Hours Summary:")
    report.append(f"   Total Errors: {summary['total_errors']}")
    if summary["most_common_error"]:
        report.append(f"   Most Common: {summary['most_common_error']}")
    report.append("")

    report.append("🔝 Top Errors (All Time):")
    for i, err in enumerate(top_errors, 1):
        report.append(f"   {i}. {err['type']}: {err['count']} occurrences")
    report.append("")

    report.append("📈 Errors by Type (Last 24h):")
    for err_type, count in summary["error_types"].items():
        report.append(f"   {err_type}: {count}")
    report.append("")

    if summary["error_endpoints"]:
        report.append("🎯 Errors by Endpoint (Last 24h):")
        for endpoint, count in summary["error_endpoints"].items():
            report.append(f"   {endpoint}: {count}")
        report.append("")

    report.append("🕒 Recent Errors:")
    for err in summary["recent_errors"][-5:]:
        report.append(f"   [{err['timestamp']}] {err['type']}: {err['message'][:80]}")

    report.append("")
    report.append("=" * 80)

    return "\n".join(report)


if __name__ == "__main__":
    # Generate and print diagnostic report
    print(generate_diagnostic_report())
