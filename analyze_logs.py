#!/usr/bin/env python3
"""
Log Analyzer - Analiza logs del backend para identificar problemas
"""

import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def analyze_log_file(log_file: Path) -> Dict:
    """Analiza un archivo de log y extrae métricas"""

    if not log_file.exists():
        return {"error": f"Log file not found: {log_file}"}

    errors = []
    warnings = []
    info_count = 0
    request_count = 0
    error_types = Counter()
    endpoints_with_errors = Counter()
    timestamps = []

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            # Timestamp
            ts_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line)
            if ts_match:
                try:
                    timestamps.append(
                        datetime.strptime(ts_match.group(), "%Y-%m-%d %H:%M:%S")
                    )
                except:
                    pass

            # Level detection
            if "ERROR:" in line or "[ERROR]" in line:
                errors.append(line.strip())
                # Extract error type
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 3:
                        error_types[parts[2].strip()[:50]] += 1

            elif "WARNING:" in line or "[WARNING]" in line:
                warnings.append(line.strip())

            elif "INFO:" in line or "[INFO]" in line:
                info_count += 1

            # HTTP requests
            if '" 200 ' in line or '" 404 ' in line or '" 500 ' in line:
                request_count += 1

                # Extract endpoint and status
                endpoint_match = re.search(r'"[A-Z]+ ([^ ]+) HTTP', line)
                status_match = re.search(r'" (\d{3}) ', line)

                if endpoint_match and status_match:
                    endpoint = endpoint_match.group(1)
                    status = status_match.group(1)

                    if status in ["500", "503"]:
                        endpoints_with_errors[endpoint] += 1

    # Análisis temporal
    uptime = None
    if len(timestamps) >= 2:
        uptime = (timestamps[-1] - timestamps[0]).total_seconds() / 3600

    return {
        "file": str(log_file.name),
        "total_lines": sum(1 for _ in open(log_file)),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": info_count,
        "requests": request_count,
        "uptime_hours": round(uptime, 2) if uptime else None,
        "error_types": dict(error_types.most_common(10)),
        "endpoints_with_errors": dict(endpoints_with_errors.most_common(10)),
        "recent_errors": errors[-5:] if errors else [],
        "recent_warnings": warnings[-5:] if warnings else [],
    }


def generate_report(backend_dir: Path) -> str:
    """Genera reporte completo de análisis de logs"""

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("ANÁLISIS DE LOGS DEL BACKEND")
    report_lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 80)
    report_lines.append("")

    # Analizar logs principales
    logs_to_analyze = [
        backend_dir / "backend.log",
        backend_dir / "wialon_sync.log",
        backend_dir / "monitor.log",
    ]

    total_errors = 0
    total_warnings = 0

    for log_file in logs_to_analyze:
        if not log_file.exists():
            continue

        report_lines.append(f"\n📋 Analizando: {log_file.name}")
        report_lines.append("-" * 80)

        analysis = analyze_log_file(log_file)

        if "error" in analysis:
            report_lines.append(f"   ⚠️  {analysis['error']}")
            continue

        total_errors += analysis["errors"]
        total_warnings += analysis["warnings"]

        report_lines.append(f"   Total líneas: {analysis['total_lines']:,}")
        report_lines.append(f"   Errores: {analysis['errors']}")
        report_lines.append(f"   Warnings: {analysis['warnings']}")
        report_lines.append(f"   Info: {analysis['info']}")
        report_lines.append(f"   Requests HTTP: {analysis['requests']}")

        if analysis["uptime_hours"]:
            report_lines.append(f"   Uptime: {analysis['uptime_hours']:.2f} horas")

        if analysis["error_types"]:
            report_lines.append("\n   🔴 Tipos de errores más comunes:")
            for error_type, count in list(analysis["error_types"].items())[:5]:
                report_lines.append(f"      • {error_type}: {count}")

        if analysis["endpoints_with_errors"]:
            report_lines.append("\n   ⚠️  Endpoints con errores:")
            for endpoint, count in analysis["endpoints_with_errors"].items():
                report_lines.append(f"      • {endpoint}: {count} errores")

        if analysis["recent_errors"]:
            report_lines.append("\n   📌 Últimos errores:")
            for error in analysis["recent_errors"][-3:]:
                # Truncar línea si es muy larga
                error_short = error[:120] + "..." if len(error) > 120 else error
                report_lines.append(f"      {error_short}")

    # Resumen general
    report_lines.append("\n" + "=" * 80)
    report_lines.append("📊 RESUMEN GENERAL")
    report_lines.append("=" * 80)
    report_lines.append(f"Total errores en todos los logs: {total_errors}")
    report_lines.append(f"Total warnings en todos los logs: {total_warnings}")

    # Estado de salud
    if total_errors == 0:
        health_status = "✅ EXCELENTE - Sin errores"
    elif total_errors < 10:
        health_status = "✅ BUENO - Pocos errores"
    elif total_errors < 50:
        health_status = "⚠️  ATENCIÓN - Errores moderados"
    else:
        health_status = "🔴 CRÍTICO - Muchos errores"

    report_lines.append(f"\nEstado de salud: {health_status}")

    # Recomendaciones
    report_lines.append("\n" + "=" * 80)
    report_lines.append("💡 RECOMENDACIONES")
    report_lines.append("=" * 80)

    if total_errors > 50:
        report_lines.append(
            "• 🚨 ACCIÓN REQUERIDA: Revisa y corrige los errores urgentemente"
        )
    if total_errors > 20:
        report_lines.append("• ⚠️  Considera ejecutar ./emergency_recovery.sh")
    if total_warnings > 100:
        report_lines.append("• 📝 Revisa warnings para prevenir futuros errores")

    report_lines.append("• ✅ Ejecuta ./monitor_backend.sh para monitoreo continuo")
    report_lines.append(
        "• 📊 Revisa http://localhost:8000/health para métricas en tiempo real"
    )

    report_lines.append("\n" + "=" * 80)

    return "\n".join(report_lines)


if __name__ == "__main__":
    backend_dir = Path(__file__).parent

    # Generar reporte
    report = generate_report(backend_dir)
    print(report)

    # Guardar reporte
    report_file = (
        backend_dir
        / "logs"
        / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    report_file.parent.mkdir(exist_ok=True)

    with open(report_file, "w") as f:
        f.write(report)

    print(f"\n✅ Reporte guardado en: {report_file}")
