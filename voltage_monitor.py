"""
═══════════════════════════════════════════════════════════════════════════════
VOLTAGE MONITOR - Alertas de Batería y Alternador
═══════════════════════════════════════════════════════════════════════════════

Usa el sensor `pwr_int` (voltaje interno) para detectar:
- Batería baja (no va a arrancar)
- Alternador fallando (no está cargando)
- Sobrevoltaje (riesgo de daño a electrónicos)

También correlaciona voltaje bajo con problemas de sensores (drift, lecturas erráticas)

🆕 v3.12.28: New module for Phase 2

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 2025
═══════════════════════════════════════════════════════════════════════════════
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VoltageStatus(Enum):
    """Estado del sistema eléctrico"""

    CRITICAL_LOW = "CRITICAL_LOW"  # < 11.5V - No va a arrancar
    LOW = "LOW"  # 11.5-12.2V - Batería descargándose
    NORMAL = "NORMAL"  # 12.2-14.8V - OK
    HIGH = "HIGH"  # 14.8-15.5V - Alternador alto
    CRITICAL_HIGH = "CRITICAL_HIGH"  # > 15.5V - Riesgo de daño


@dataclass
class VoltageAlert:
    """Alerta de voltaje"""

    truck_id: str
    voltage: float
    status: VoltageStatus
    is_engine_running: bool

    # Alerta
    priority: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "OK"
    message: Optional[str] = None
    action: Optional[str] = None

    # Impacto en sensores
    may_affect_sensors: bool = False
    sensor_warning: Optional[str] = None

    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "truck_id": self.truck_id,
            "voltage": self.voltage,
            "status": self.status.value,
            "is_engine_running": self.is_engine_running,
            "priority": self.priority,
            "message": self.message,
            "action": self.action,
            "may_affect_sensors": self.may_affect_sensors,
            "sensor_warning": self.sensor_warning,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE UMBRALES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class VoltageThresholds:
    """Umbrales de voltaje para Class 8 trucks (sistema 12V)"""

    # Motor APAGADO (voltaje de batería)
    battery_critical_low: float = 11.5  # No arranca
    battery_low: float = 12.2  # Carga baja
    battery_normal_min: float = 12.2
    battery_normal_max: float = 12.8  # Batería full

    # Motor ENCENDIDO (voltaje de carga)
    charging_critical_low: float = 12.5  # Alternador no carga
    charging_low: float = 13.2  # Carga débil
    charging_normal_min: float = 13.5
    charging_normal_max: float = 14.8  # Carga normal
    charging_high: float = 15.0  # Sobrecarga leve
    charging_critical_high: float = 15.5  # Riesgo de daño


DEFAULT_THRESHOLDS = VoltageThresholds()


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES PRINCIPALES
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_voltage(
    pwr_int: Optional[float],
    rpm: Optional[float] = None,
    truck_id: str = "UNKNOWN",
    thresholds: VoltageThresholds = DEFAULT_THRESHOLDS,
) -> Optional[VoltageAlert]:
    """
    Analizar voltaje del sistema y generar alertas.

    Args:
        pwr_int: Voltaje del sensor pwr_int (volts)
        rpm: RPM del motor (None si no disponible, 0 = apagado, >0 = encendido)
        truck_id: ID del camión
        thresholds: Umbrales de voltaje

    Returns:
        VoltageAlert con diagnóstico completo, or None if no voltage data
    """
    if pwr_int is None:
        return None

    # Determinar si motor está encendido
    is_running = rpm is not None and rpm > 100

    # Analizar según estado del motor
    if is_running:
        return _analyze_charging_voltage(pwr_int, rpm, truck_id, thresholds)
    else:
        return _analyze_battery_voltage(pwr_int, truck_id, thresholds)


def _analyze_battery_voltage(
    voltage: float,
    truck_id: str,
    thresholds: VoltageThresholds,
) -> VoltageAlert:
    """Analizar voltaje con motor apagado (estado de batería)"""

    if voltage < thresholds.battery_critical_low:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.CRITICAL_LOW,
            is_engine_running=False,
            priority="CRITICAL",
            message=f"🚨 BATERÍA MUERTA ({voltage:.1f}V) - No va a arrancar",
            action="Cargar batería o jump start inmediatamente",
            may_affect_sensors=True,
            sensor_warning="Voltaje crítico puede causar lecturas erráticas de sensores",
            timestamp=datetime.now(),
        )

    elif voltage < thresholds.battery_low:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.LOW,
            is_engine_running=False,
            priority="HIGH",
            message=f"⚠️ Batería baja ({voltage:.1f}V) - Riesgo de no arranque",
            action="Verificar conexiones, considerar carga o reemplazo",
            may_affect_sensors=True,
            sensor_warning="Voltaje bajo puede afectar precisión de sensores",
            timestamp=datetime.now(),
        )

    elif voltage <= thresholds.battery_normal_max:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.NORMAL,
            is_engine_running=False,
            priority="OK",
            message=f"✅ Batería OK ({voltage:.1f}V)",
            action=None,
            may_affect_sensors=False,
            timestamp=datetime.now(),
        )

    else:
        # Voltaje alto con motor apagado es raro, posible error de lectura
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.HIGH,
            is_engine_running=False,
            priority="LOW",
            message=f"❓ Voltaje inusual con motor apagado ({voltage:.1f}V)",
            action="Verificar lectura del sensor",
            may_affect_sensors=False,
            timestamp=datetime.now(),
        )


def _analyze_charging_voltage(
    voltage: float,
    rpm: float,
    truck_id: str,
    thresholds: VoltageThresholds,
) -> VoltageAlert:
    """Analizar voltaje con motor encendido (sistema de carga)"""

    if voltage < thresholds.charging_critical_low:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.CRITICAL_LOW,
            is_engine_running=True,
            priority="CRITICAL",
            message=f"🚨 ALTERNADOR FALLANDO ({voltage:.1f}V con motor a {rpm:.0f} RPM)",
            action="Detener de forma segura. Verificar alternador, correa, conexiones",
            may_affect_sensors=True,
            sensor_warning="Sistema eléctrico comprometido - lecturas de sensores no confiables",
            timestamp=datetime.now(),
        )

    elif voltage < thresholds.charging_low:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.LOW,
            is_engine_running=True,
            priority="HIGH",
            message=f"⚠️ Carga débil ({voltage:.1f}V) - Alternador no carga bien",
            action="Programar revisión de alternador y correa",
            may_affect_sensors=True,
            sensor_warning="Voltaje marginal puede causar drift en sensores",
            timestamp=datetime.now(),
        )

    elif voltage <= thresholds.charging_normal_max:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.NORMAL,
            is_engine_running=True,
            priority="OK",
            message=f"✅ Sistema de carga OK ({voltage:.1f}V)",
            action=None,
            may_affect_sensors=False,
            timestamp=datetime.now(),
        )

    elif voltage <= thresholds.charging_high:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.HIGH,
            is_engine_running=True,
            priority="MEDIUM",
            message=f"⚠️ Sobrecarga leve ({voltage:.1f}V)",
            action="Monitorear. Si persiste, revisar regulador de voltaje",
            may_affect_sensors=False,
            timestamp=datetime.now(),
        )

    else:
        return VoltageAlert(
            truck_id=truck_id,
            voltage=voltage,
            status=VoltageStatus.CRITICAL_HIGH,
            is_engine_running=True,
            priority="CRITICAL",
            message=f"🚨 SOBREVOLTAJE ({voltage:.1f}V) - Riesgo de daño a electrónicos",
            action="Detener y revisar alternador/regulador inmediatamente",
            may_affect_sensors=True,
            sensor_warning="Sobrevoltaje puede dañar sensores y ECU",
            timestamp=datetime.now(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CORRELACIÓN CON PROBLEMAS DE SENSORES
# ═══════════════════════════════════════════════════════════════════════════════


def check_voltage_sensor_correlation(
    voltage: float,
    fuel_sensor_variance: float,
    fuel_drift_pct: float,
) -> Dict:
    """
    Verificar si voltaje bajo puede estar causando problemas en sensores.

    Útil para diagnosticar cuando el Kalman filter tiene drift alto
    o los sensores dan lecturas erráticas.

    Args:
        voltage: Voltaje actual (pwr_int)
        fuel_sensor_variance: Varianza del sensor de combustible
        fuel_drift_pct: Drift actual del Kalman filter

    Returns:
        Dict con análisis de correlación
    """
    result = {
        "voltage": voltage,
        "is_voltage_issue": False,
        "correlation_found": False,
        "explanation": "",
        "recommendation": "",
    }

    # Umbrales para considerar "problemas"
    VARIANCE_THRESHOLD = 2.0
    DRIFT_THRESHOLD = 5.0
    VOLTAGE_CONCERN = 12.0

    has_sensor_issues = (
        fuel_sensor_variance > VARIANCE_THRESHOLD
        or abs(fuel_drift_pct) > DRIFT_THRESHOLD
    )

    has_voltage_issue = voltage < VOLTAGE_CONCERN

    if has_voltage_issue and has_sensor_issues:
        result["is_voltage_issue"] = True
        result["correlation_found"] = True
        result["explanation"] = (
            f"Voltaje bajo ({voltage:.1f}V) correlaciona con problemas de sensor "
            f"(varianza: {fuel_sensor_variance:.2f}, drift: {fuel_drift_pct:.1f}%). "
            "El voltaje insuficiente puede causar lecturas erráticas."
        )
        result["recommendation"] = (
            "1. Resolver problema eléctrico primero (batería/alternador)\n"
            "2. Los problemas de sensor pueden resolverse automáticamente\n"
            "3. Si persisten después de fix eléctrico, recalibrar sensores"
        )

    elif has_voltage_issue and not has_sensor_issues:
        result["is_voltage_issue"] = True
        result["correlation_found"] = False
        result["explanation"] = (
            f"Voltaje bajo ({voltage:.1f}V) pero sensores funcionando bien. "
            "Atender voltaje antes de que afecte sensores."
        )
        result["recommendation"] = "Revisar sistema eléctrico preventivamente"

    elif not has_voltage_issue and has_sensor_issues:
        result["is_voltage_issue"] = False
        result["correlation_found"] = False
        result["explanation"] = (
            f"Voltaje OK ({voltage:.1f}V). Problemas de sensor no relacionados "
            "con sistema eléctrico."
        )
        result["recommendation"] = "Investigar sensor de combustible directamente"

    else:
        result["explanation"] = "Sistema eléctrico y sensores funcionando normalmente"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING PARA FLOTA
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_fleet_voltage(
    fleet_data: List[Dict],
) -> Dict:
    """
    Analizar voltaje de toda la flota.

    Args:
        fleet_data: Lista de dicts con {truck_id, pwr_int, rpm}

    Returns:
        Dict con resumen y alertas
    """
    alerts = []
    critical_count = 0
    warning_count = 0
    ok_count = 0
    no_data_count = 0

    for truck in fleet_data:
        truck_id = truck.get("truck_id", "UNKNOWN")
        pwr_int = truck.get("pwr_int")
        rpm = truck.get("rpm")

        if pwr_int is None:
            no_data_count += 1
            continue

        alert = analyze_voltage(pwr_int, rpm, truck_id)

        if alert is None:
            no_data_count += 1
            continue

        if alert.priority == "CRITICAL":
            critical_count += 1
            alerts.append(alert)
        elif alert.priority in ["HIGH", "MEDIUM"]:
            warning_count += 1
            alerts.append(alert)
        else:
            ok_count += 1

    # Ordenar alertas por prioridad
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "OK": 4}
    alerts.sort(key=lambda x: priority_order.get(x.priority, 5))

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_trucks": len(fleet_data),
            "critical": critical_count,
            "warnings": warning_count,
            "ok": ok_count,
            "no_data": no_data_count,
        },
        "alerts": [a.to_dict() for a in alerts],
        "needs_attention": critical_count > 0 or warning_count > 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRACIÓN CON FUEL COPILOT
# ═══════════════════════════════════════════════════════════════════════════════


def get_voltage_quality_factor(
    voltage: Optional[float], is_engine_running: bool = True
) -> float:
    """
    Obtener factor de calidad basado en voltaje para ajustar confianza del Kalman.

    Usar en estimator.py para reducir confianza cuando voltaje es marginal.

    Args:
        voltage: Voltaje actual
        is_engine_running: Si el motor está encendido

    Returns:
        Factor 0.5-1.0 (1.0 = voltaje perfecto, 0.5 = voltaje crítico)
    """
    if voltage is None:
        return 1.0  # No data, assume OK

    if is_engine_running:
        if voltage >= 13.5 and voltage <= 14.8:
            return 1.0  # Perfecto
        elif voltage >= 13.0 and voltage <= 15.0:
            return 0.95  # Muy bueno
        elif voltage >= 12.5 and voltage <= 15.5:
            return 0.85  # Aceptable
        elif voltage >= 12.0:
            return 0.7  # Marginal
        else:
            return 0.5  # Crítico
    else:
        if voltage >= 12.4:
            return 1.0
        elif voltage >= 12.0:
            return 0.9
        elif voltage >= 11.5:
            return 0.7
        else:
            return 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT COOLDOWN MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class VoltageAlertManager:
    """Manages voltage alerts with cooldown to prevent spam"""

    def __init__(self, cooldown_minutes: int = 60):
        self.cooldown_minutes = cooldown_minutes
        self._last_alert_time: Dict[str, datetime] = {}

    def should_alert(self, truck_id: str, priority: str) -> bool:
        """Check if we should send alert (respects cooldown)"""
        key = f"{truck_id}_{priority}"

        # Critical alerts always go through
        if priority == "CRITICAL":
            self._last_alert_time[key] = datetime.now()
            return True

        last_time = self._last_alert_time.get(key)
        if last_time is None:
            self._last_alert_time[key] = datetime.now()
            return True

        elapsed_minutes = (datetime.now() - last_time).total_seconds() / 60
        if elapsed_minutes >= self.cooldown_minutes:
            self._last_alert_time[key] = datetime.now()
            return True

        return False

    def process_alert(self, alert: VoltageAlert) -> Optional[VoltageAlert]:
        """Process alert, return it if should be sent, None otherwise"""
        if alert is None:
            return None
        if alert.priority == "OK":
            return None
        if self.should_alert(alert.truck_id, alert.priority):
            return alert
        return None


# Global alert manager instance
_voltage_alert_manager: Optional[VoltageAlertManager] = None


def get_voltage_alert_manager() -> VoltageAlertManager:
    """Get or create global voltage alert manager"""
    global _voltage_alert_manager
    if _voltage_alert_manager is None:
        _voltage_alert_manager = VoltageAlertManager()
    return _voltage_alert_manager


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("TEST: Voltage Monitor")
    print("=" * 70)

    # Test casos
    test_cases = [
        # (voltage, rpm, description)
        (14.2, 700, "Normal - motor encendido"),
        (12.6, 0, "Normal - motor apagado"),
        (11.2, 0, "Batería muerta"),
        (12.8, 650, "Alternador no carga"),
        (15.8, 750, "Sobrevoltaje"),
        (13.0, 600, "Carga débil"),
    ]

    for voltage, rpm, desc in test_cases:
        alert = analyze_voltage(voltage, rpm if rpm > 0 else None, "TEST001")
        print(f"\n{desc}:")
        print(f"  Voltage: {voltage}V, RPM: {rpm}")
        print(f"  Status: {alert.status.value}")
        print(f"  Priority: {alert.priority}")
        print(f"  Message: {alert.message}")
        if alert.may_affect_sensors:
            print(f"  ⚠️ Sensor warning: {alert.sensor_warning}")

    print("\n" + "=" * 70)
    print("TEST: Fleet Analysis")
    print("=" * 70)

    fleet = [
        {"truck_id": "CO0681", "pwr_int": 14.2, "rpm": 700},
        {"truck_id": "PC1280", "pwr_int": 12.9, "rpm": 650},
        {"truck_id": "OG2033", "pwr_int": 11.3, "rpm": None},
        {"truck_id": "YM6023", "pwr_int": 15.6, "rpm": 720},
        {"truck_id": "DO9356", "pwr_int": None, "rpm": None},
    ]

    result = analyze_fleet_voltage(fleet)
    print(f"\nSummary: {result['summary']}")
    print(f"Needs attention: {result['needs_attention']}")

    if result["alerts"]:
        print("\nAlerts:")
        for a in result["alerts"]:
            print(f"  [{a['priority']}] {a['truck_id']}: {a['message']}")
