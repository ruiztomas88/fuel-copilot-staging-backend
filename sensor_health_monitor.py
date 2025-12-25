"""
Sensor Health Monitor - Quick Win Implementation
Trackea salud de sensores y alerta cuando empiezan a fallar

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SensorHealth(Enum):
    """Estados de salud del sensor"""

    EXCELLENT = "excellent"  # >95% uptime, sin issues
    GOOD = "good"  # 85-95% uptime, issues menores
    FAIR = "fair"  # 70-85% uptime, issues frecuentes
    POOR = "poor"  # 50-70% uptime, muchos issues
    CRITICAL = "critical"  # <50% uptime, sensor casi muerto


@dataclass
class SensorIssue:
    """Issue detectado en sensor"""

    timestamp: str
    issue_type: str  # "missing", "stuck", "erratic", "out_of_range"
    severity: str  # "low", "medium", "high"
    description: str
    value: Optional[float] = None


@dataclass
class SensorHealthReport:
    """Reporte de salud de un sensor"""

    truck_id: str
    sensor_name: str
    health: SensorHealth
    uptime_pct: float  # % de tiempo con datos válidos
    last_value: Optional[float]
    last_updated: Optional[str]
    issues_24h: int
    issues_7d: int
    recent_issues: List[SensorIssue]
    recommendations: List[str]


class SensorHealthMonitor:
    """
    Monitor de salud de sensores

    Features:
    - Trackea cada sensor individualmente
    - Detecta patrones de falla (missing, stuck, erratic, out_of_range)
    - Calcula uptime y health score
    - Genera recomendaciones automáticas
    - Alerta cuando sensor empieza a degradarse
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.health_file = self.data_dir / "sensor_health.json"
        self.issues_file = self.data_dir / "sensor_issues.json"

        # Estado en memoria
        self.sensor_history: Dict[str, List[Dict]] = (
            {}
        )  # sensor_key -> list of readings
        self.sensor_issues: Dict[str, List[SensorIssue]] = (
            {}
        )  # sensor_key -> list of issues

        self._load_state()

    def _load_state(self):
        """Carga estado persistido"""
        try:
            if self.issues_file.exists():
                with open(self.issues_file, "r") as f:
                    data = json.load(f)
                    self.sensor_issues = {
                        k: [SensorIssue(**issue) for issue in v]
                        for k, v in data.items()
                    }
                logger.info(
                    f"Loaded sensor issues for {len(self.sensor_issues)} sensors"
                )

        except Exception as e:
            logger.error(f"Error loading sensor health state: {e}")

    def _save_state(self):
        """Persiste estado"""
        try:
            # Solo guardar issues (history es demasiado grande)
            with open(self.issues_file, "w") as f:
                json.dump(
                    {
                        k: [asdict(issue) for issue in v]
                        for k, v in self.sensor_issues.items()
                    },
                    f,
                    indent=2,
                )

        except Exception as e:
            logger.error(f"Error saving sensor health state: {e}")

    def record_sensor_reading(
        self,
        truck_id: str,
        sensor_name: str,
        value: Optional[float],
        timestamp: datetime,
        is_valid: bool = True,
    ):
        """
        Registra una lectura de sensor

        Args:
            truck_id: ID del truck
            sensor_name: Nombre del sensor (fuel_pct, speed, rpm, etc.)
            value: Valor del sensor (None si no disponible)
            timestamp: Cuándo se leyó
            is_valid: Si el valor es válido (dentro de rango esperado)
        """
        sensor_key = f"{truck_id}_{sensor_name}"

        # Inicializar history si no existe
        if sensor_key not in self.sensor_history:
            self.sensor_history[sensor_key] = []

        # Agregar lectura
        reading = {
            "timestamp": timestamp.isoformat(),
            "value": value,
            "is_valid": is_valid,
        }
        self.sensor_history[sensor_key].append(reading)

        # Mantener solo últimas 1000 lecturas (para no llenar memoria)
        if len(self.sensor_history[sensor_key]) > 1000:
            self.sensor_history[sensor_key] = self.sensor_history[sensor_key][-1000:]

        # Detectar issues
        self._detect_sensor_issues(truck_id, sensor_name, value, timestamp)

    def _detect_sensor_issues(
        self,
        truck_id: str,
        sensor_name: str,
        value: Optional[float],
        timestamp: datetime,
    ):
        """
        Detecta issues en sensor

        Patrones detectados:
        - Missing: Sensor no reporta valor
        - Stuck: Mismo valor por mucho tiempo
        - Erratic: Cambios muy bruscos
        - Out of range: Valor fuera de rango esperado
        """
        sensor_key = f"{truck_id}_{sensor_name}"

        if sensor_key not in self.sensor_issues:
            self.sensor_issues[sensor_key] = []

        # Issue 1: Missing data
        if value is None:
            issue = SensorIssue(
                timestamp=timestamp.isoformat(),
                issue_type="missing",
                severity="medium",
                description=f"{sensor_name} no reportó valor",
            )
            self.sensor_issues[sensor_key].append(issue)
            logger.debug(f"Sensor issue detected: {sensor_key} - missing data")
            return

        # Obtener últimas lecturas válidas
        history = self.sensor_history.get(sensor_key, [])
        valid_readings = [r for r in history if r["value"] is not None]

        if len(valid_readings) < 2:
            return  # No suficiente historia para comparar

        last_value = valid_readings[-2]["value"]

        # Issue 2: Stuck (mismo valor por >30 min)
        if value == last_value:
            same_value_count = 1
            for r in reversed(valid_readings[:-1]):
                if r["value"] == value:
                    same_value_count += 1
                else:
                    break

            # Si >60 lecturas consecutivas con mismo valor (>30 min a 30s/ciclo)
            if same_value_count > 60:
                issue = SensorIssue(
                    timestamp=timestamp.isoformat(),
                    issue_type="stuck",
                    severity="high",
                    description=f"{sensor_name} stuck en {value} por {same_value_count} lecturas",
                    value=value,
                )
                self.sensor_issues[sensor_key].append(issue)
                logger.warning(
                    f"Sensor issue detected: {sensor_key} - stuck at {value}"
                )

        # Issue 3: Erratic (cambio >20% en 1 lectura para fuel_pct)
        if sensor_name == "fuel_pct":
            pct_change = (
                abs((value - last_value) / last_value * 100) if last_value > 0 else 0
            )

            if pct_change > 20:
                issue = SensorIssue(
                    timestamp=timestamp.isoformat(),
                    issue_type="erratic",
                    severity="medium",
                    description=f"{sensor_name} cambió {pct_change:.1f}% bruscamente ({last_value} -> {value})",
                    value=value,
                )
                self.sensor_issues[sensor_key].append(issue)
                logger.warning(
                    f"Sensor issue detected: {sensor_key} - erratic change {pct_change:.1f}%"
                )

        # Issue 4: Out of range
        out_of_range = False
        if sensor_name == "fuel_pct" and (value < 0 or value > 100):
            out_of_range = True
        elif sensor_name == "speed" and value < 0:
            out_of_range = True
        elif sensor_name == "rpm" and (value < 0 or value > 5000):
            out_of_range = True

        if out_of_range:
            issue = SensorIssue(
                timestamp=timestamp.isoformat(),
                issue_type="out_of_range",
                severity="high",
                description=f"{sensor_name} fuera de rango: {value}",
                value=value,
            )
            self.sensor_issues[sensor_key].append(issue)
            logger.warning(
                f"Sensor issue detected: {sensor_key} - out of range {value}"
            )

        # Limpiar issues antiguos (>7 días)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self.sensor_issues[sensor_key] = [
            issue
            for issue in self.sensor_issues[sensor_key]
            if datetime.fromisoformat(issue.timestamp).replace(tzinfo=timezone.utc)
            >= cutoff
        ]

        # Persistir
        self._save_state()

    def get_sensor_health_report(
        self, truck_id: str, sensor_name: str
    ) -> SensorHealthReport:
        """
        Genera reporte de salud de un sensor

        Args:
            truck_id: ID del truck
            sensor_name: Nombre del sensor

        Returns:
            SensorHealthReport
        """
        sensor_key = f"{truck_id}_{sensor_name}"

        # Obtener historia
        history = self.sensor_history.get(sensor_key, [])
        issues = self.sensor_issues.get(sensor_key, [])

        if not history:
            return SensorHealthReport(
                truck_id=truck_id,
                sensor_name=sensor_name,
                health=SensorHealth.CRITICAL,
                uptime_pct=0.0,
                last_value=None,
                last_updated=None,
                issues_24h=0,
                issues_7d=0,
                recent_issues=[],
                recommendations=[
                    "Sensor nunca ha reportado datos - verificar conexión"
                ],
            )

        # Calcular uptime (últimas 24 horas)
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_readings = [
            r
            for r in history
            if datetime.fromisoformat(r["timestamp"]).replace(tzinfo=timezone.utc)
            >= cutoff_24h
        ]

        if recent_readings:
            valid_count = sum(
                1 for r in recent_readings if r["value"] is not None and r["is_valid"]
            )
            uptime_pct = valid_count / len(recent_readings) * 100
        else:
            uptime_pct = 0.0

        # Contar issues
        cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
        issues_24h = sum(
            1
            for i in issues
            if datetime.fromisoformat(i.timestamp).replace(tzinfo=timezone.utc)
            >= cutoff_24h
        )
        issues_7d = len(issues)

        # Última lectura
        last_reading = history[-1] if history else None
        last_value = last_reading["value"] if last_reading else None
        last_updated = last_reading["timestamp"] if last_reading else None

        # Determinar health
        if uptime_pct >= 95 and issues_24h == 0:
            health = SensorHealth.EXCELLENT
        elif uptime_pct >= 85:
            health = SensorHealth.GOOD
        elif uptime_pct >= 70:
            health = SensorHealth.FAIR
        elif uptime_pct >= 50:
            health = SensorHealth.POOR
        else:
            health = SensorHealth.CRITICAL

        # Issues recientes (últimas 5)
        recent_issues = sorted(issues, key=lambda i: i.timestamp, reverse=True)[:5]

        # Generar recomendaciones
        recommendations = self._generate_recommendations(
            sensor_name, health, uptime_pct, issues, recent_issues
        )

        return SensorHealthReport(
            truck_id=truck_id,
            sensor_name=sensor_name,
            health=health,
            uptime_pct=round(uptime_pct, 1),
            last_value=last_value,
            last_updated=last_updated,
            issues_24h=issues_24h,
            issues_7d=issues_7d,
            recent_issues=recent_issues,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        sensor_name: str,
        health: SensorHealth,
        uptime_pct: float,
        all_issues: List[SensorIssue],
        recent_issues: List[SensorIssue],
    ) -> List[str]:
        """Genera recomendaciones basadas en issues detectados"""
        recommendations = []

        if health == SensorHealth.CRITICAL:
            recommendations.append(
                f"⚠️ URGENTE: {sensor_name} en estado crítico - requiere atención inmediata"
            )
        elif health == SensorHealth.POOR:
            recommendations.append(
                f"⚠️ {sensor_name} en mal estado - considerar reemplazo pronto"
            )

        # Analizar tipos de issues
        issue_types = [i.issue_type for i in all_issues]

        if issue_types.count("missing") > 10:
            recommendations.append(
                "Sensor frecuentemente reporta datos faltantes - "
                "verificar cableado y conexiones"
            )

        if issue_types.count("stuck") > 3:
            recommendations.append(
                "Sensor se queda stuck frecuentemente - "
                "posible falla mecánica en sensor de nivel"
            )

        if issue_types.count("erratic") > 5:
            recommendations.append(
                "Lecturas erráticas frecuentes - "
                "verificar calibración y grounding eléctrico"
            )

        if issue_types.count("out_of_range") > 0:
            recommendations.append(
                "Valores fuera de rango detectados - "
                "sensor puede estar dañado o mal calibrado"
            )

        if uptime_pct < 80 and not recommendations:
            recommendations.append(
                f"Uptime bajo ({uptime_pct:.1f}%) - "
                "monitorear de cerca para prevenir fallas"
            )

        if not recommendations:
            recommendations.append("✅ Sensor operando normalmente")

        return recommendations

    def get_truck_sensor_health_summary(
        self, truck_id: str
    ) -> Dict[str, SensorHealthReport]:
        """
        Obtiene reporte de salud de todos los sensores de un truck

        Args:
            truck_id: ID del truck

        Returns:
            Dict con sensor_name -> SensorHealthReport
        """
        # Determinar qué sensores tiene este truck
        sensor_names = set()
        for sensor_key in self.sensor_history.keys():
            if sensor_key.startswith(f"{truck_id}_"):
                sensor_name = sensor_key.replace(f"{truck_id}_", "")
                sensor_names.add(sensor_name)

        # Generar reportes
        reports = {}
        for sensor_name in sensor_names:
            reports[sensor_name] = self.get_sensor_health_report(truck_id, sensor_name)

        return reports


# Singleton
_monitor_instance = None


def get_sensor_health_monitor() -> SensorHealthMonitor:
    """Obtiene instancia singleton"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SensorHealthMonitor()
    return _monitor_instance


# Integración en wialon_sync_enhanced.py:
#
# En process_truck(), después de obtener sensor readings (línea ~1900):
#
#   from sensor_health_monitor import get_sensor_health_monitor
#
#   monitor = get_sensor_health_monitor()
#
#   # Registrar cada sensor
#   monitor.record_sensor_reading(
#       truck_id=truck_id,
#       sensor_name="fuel_pct",
#       value=sensor_pct,
#       timestamp=timestamp,
#       is_valid=sensor_pct is not None and 0 <= sensor_pct <= 100
#   )
#
#   monitor.record_sensor_reading(
#       truck_id=truck_id,
#       sensor_name="speed",
#       value=speed,
#       timestamp=timestamp,
#       is_valid=speed is not None and speed >= 0
#   )
#
#   monitor.record_sensor_reading(
#       truck_id=truck_id,
#       sensor_name="rpm",
#       value=rpm,
#       timestamp=timestamp,
#       is_valid=rpm is not None and 0 <= rpm <= 5000
#   )
#
# API endpoint para obtener sensor health:
#
#   @app.get("/api/sensor-health/{truck_id}")
#   def get_truck_sensor_health(truck_id: str):
#       monitor = get_sensor_health_monitor()
#       return monitor.get_truck_sensor_health_summary(truck_id)
#
#   @app.get("/api/sensor-health/{truck_id}/{sensor_name}")
#   def get_sensor_health_detail(truck_id: str, sensor_name: str):
#       monitor = get_sensor_health_monitor()
#       report = monitor.get_sensor_health_report(truck_id, sensor_name)
#       return asdict(report)
