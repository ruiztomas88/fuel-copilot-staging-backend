"""
J1939 DTC Database - Catálogo Expandido v5.7.6
═══════════════════════════════════════════════════════════════════════════════

Comprehensive J1939 DTC (Diagnostic Trouble Code) database for Class 8 trucks.
Includes descriptions in Spanish for fleet operations in Latin America.

Structure:
- SPN (Suspect Parameter Number): Identifies component/signal
- FMI (Failure Mode Identifier): Describes failure type (0-31)

Sources:
- SAE J1939-73 (Application Layer - Diagnostics)
- Cummins, Detroit Diesel, Paccar manufacturer codes
- Real-world fleet data from Fuel Analytics operations

Author: Fuel Analytics Team
Version: 5.7.6
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class DTCSystem(Enum):
    """Vehicle system classification for DTC codes"""

    ENGINE = "ENGINE"
    TRANSMISSION = "TRANSMISSION"
    AFTERTREATMENT = "AFTERTREATMENT"  # DEF/SCR/DPF
    ELECTRICAL = "ELECTRICAL"
    COOLING = "COOLING"
    FUEL = "FUEL"
    AIR_INTAKE = "AIR_INTAKE"
    EXHAUST = "EXHAUST"
    BRAKES = "BRAKES"
    HVAC = "HVAC"
    BODY = "BODY"
    CHASSIS = "CHASSIS"
    UNKNOWN = "UNKNOWN"


class DTCSeverity(Enum):
    """DTC severity levels"""

    CRITICAL = "critical"  # Stop truck immediately
    WARNING = "warning"  # Service within 24-48 hours
    INFO = "info"  # Monitor, service at next scheduled maintenance


@dataclass
class SPNInfo:
    """SPN (Suspect Parameter Number) Information"""

    spn: int
    name_en: str  # English name
    name_es: str  # Spanish name
    system: DTCSystem
    severity: DTCSeverity
    description_es: str  # Spanish description
    action_es: str  # Recommended action in Spanish


# ═══════════════════════════════════════════════════════════════════════════════
# FMI (Failure Mode Identifier) DESCRIPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

FMI_DESCRIPTIONS = {
    0: {
        "en": "Data Valid But Above Normal Operational Range - Most Severe Level",
        "es": "Datos válidos pero sobre el rango operacional normal - Nivel más severo",
        "severity": DTCSeverity.CRITICAL,
    },
    1: {
        "en": "Data Valid But Below Normal Operational Range - Most Severe Level",
        "es": "Datos válidos pero bajo el rango operacional normal - Nivel más severo",
        "severity": DTCSeverity.CRITICAL,
    },
    2: {
        "en": "Data Erratic, Intermittent Or Incorrect",
        "es": "Datos erráticos, intermitentes o incorrectos",
        "severity": DTCSeverity.WARNING,
    },
    3: {
        "en": "Voltage Above Normal, Or Shorted To High Source",
        "es": "Voltaje sobre lo normal, o cortocircuito a fuente alta",
        "severity": DTCSeverity.CRITICAL,
    },
    4: {
        "en": "Voltage Below Normal, Or Shorted To Low Source",
        "es": "Voltaje bajo lo normal, o cortocircuito a tierra",
        "severity": DTCSeverity.CRITICAL,
    },
    5: {
        "en": "Current Below Normal Or Open Circuit",
        "es": "Corriente bajo lo normal o circuito abierto",
        "severity": DTCSeverity.CRITICAL,
    },
    6: {
        "en": "Current Above Normal Or Grounded Circuit",
        "es": "Corriente sobre lo normal o circuito a tierra",
        "severity": DTCSeverity.CRITICAL,
    },
    7: {
        "en": "Mechanical System Not Responding Or Out Of Adjustment",
        "es": "Sistema mecánico no responde o fuera de ajuste",
        "severity": DTCSeverity.WARNING,
    },
    8: {
        "en": "Abnormal Frequency Or Pulse Width Or Period",
        "es": "Frecuencia, ancho de pulso o período anormal",
        "severity": DTCSeverity.WARNING,
    },
    9: {
        "en": "Abnormal Update Rate",
        "es": "Tasa de actualización anormal",
        "severity": DTCSeverity.INFO,
    },
    10: {
        "en": "Abnormal Rate Of Change",
        "es": "Tasa de cambio anormal",
        "severity": DTCSeverity.WARNING,
    },
    11: {
        "en": "Root Cause Not Known",
        "es": "Causa raíz desconocida",
        "severity": DTCSeverity.WARNING,
    },
    12: {
        "en": "Bad Intelligent Device Or Component",
        "es": "Dispositivo o componente inteligente defectuoso",
        "severity": DTCSeverity.CRITICAL,
    },
    13: {
        "en": "Out Of Calibration",
        "es": "Fuera de calibración",
        "severity": DTCSeverity.WARNING,
    },
    14: {
        "en": "Special Instructions",
        "es": "Instrucciones especiales",
        "severity": DTCSeverity.INFO,
    },
    15: {
        "en": "Data Valid But Above Normal Operating Range - Least Severe Level",
        "es": "Datos válidos pero sobre el rango operacional - Nivel menos severo",
        "severity": DTCSeverity.INFO,
    },
    16: {
        "en": "Data Valid But Above Normal Operating Range - Moderately Severe Level",
        "es": "Datos válidos pero sobre el rango operacional - Nivel moderado",
        "severity": DTCSeverity.WARNING,
    },
    17: {
        "en": "Data Valid But Below Normal Operating Range - Least Severe Level",
        "es": "Datos válidos pero bajo el rango operacional - Nivel menos severo",
        "severity": DTCSeverity.INFO,
    },
    18: {
        "en": "Data Valid But Below Normal Operating Range - Moderately Severe Level",
        "es": "Datos válidos pero bajo el rango operacional - Nivel moderado",
        "severity": DTCSeverity.WARNING,
    },
    19: {
        "en": "Received Network Data In Error",
        "es": "Datos de red recibidos con error",
        "severity": DTCSeverity.WARNING,
    },
    20: {
        "en": "Data Drifted High",
        "es": "Datos desviados hacia arriba",
        "severity": DTCSeverity.WARNING,
    },
    21: {
        "en": "Data Drifted Low",
        "es": "Datos desviados hacia abajo",
        "severity": DTCSeverity.WARNING,
    },
    31: {
        "en": "Condition Exists",
        "es": "Condición presente",
        "severity": DTCSeverity.WARNING,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - ENGINE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

ENGINE_SPNS = {
    # Core Engine
    91: SPNInfo(
        spn=91,
        name_en="Throttle Position",
        name_es="Posición del Acelerador",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de posición del pedal del acelerador. Controla la potencia del motor.",
        action_es="⛔ CRÍTICO: Puede causar pérdida de potencia o aceleración involuntaria. Revisar sensor y cableado.",
    ),
    100: SPNInfo(
        spn=100,
        name_en="Engine Oil Pressure",
        name_es="Presión de Aceite del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión de aceite del motor. Lubricación esencial para evitar daño al motor.",
        action_es="⛔ PARAR INMEDIATAMENTE. Verificar nivel de aceite. NO arrancar si la presión está baja. Riesgo de daño catastrófico al motor.",
    ),
    102: SPNInfo(
        spn=102,
        name_en="Manifold Absolute Pressure",
        name_es="Presión Absoluta del Múltiple",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de presión del múltiple de admisión. Afecta mezcla aire-combustible.",
        action_es="⚠️ Puede causar pérdida de potencia y consumo excesivo. Programar servicio pronto.",
    ),
    110: SPNInfo(
        spn=110,
        name_en="Engine Coolant Temperature",
        name_es="Temperatura del Refrigerante",
        system=DTCSystem.COOLING,
        severity=DTCSeverity.CRITICAL,
        description_es="Temperatura del líquido refrigerante del motor.",
        action_es="⛔ PARAR Y DEJAR ENFRIAR. Verificar nivel de refrigerante. Riesgo de sobrecalentamiento y daño al motor.",
    ),
    157: SPNInfo(
        spn=157,
        name_en="Fuel Rail Pressure",
        name_es="Presión del Riel de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión en el sistema de inyección de combustible.",
        action_es="⛔ Problema de sistema de combustible. Puede causar apagado del motor. Programar servicio inmediato.",
    ),
    190: SPNInfo(
        spn=190,
        name_en="Engine Speed",
        name_es="Velocidad del Motor (RPM)",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de revoluciones del motor (RPM).",
        action_es="⛔ Sensor de RPM defectuoso. Puede causar problemas de arranque o funcionamiento errático.",
    ),
    520: SPNInfo(
        spn=520,
        name_en="Engine Hours",
        name_es="Horas de Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Contador de horas de operación del motor.",
        action_es="📋 Informativo. Usar para programar mantenimiento basado en horas.",
    ),
    587: SPNInfo(
        spn=587,
        name_en="Engine Idle Speed",
        name_es="Velocidad de Ralentí",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Control de velocidad de ralentí del motor.",
        action_es="🔧 El motor puede tener ralentí inestable. Revisar en próximo servicio.",
    ),
    641: SPNInfo(
        spn=641,
        name_en="Variable Geometry Turbo",
        name_es="Turbo de Geometría Variable",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.CRITICAL,
        description_es="Control del turbocompresor de geometría variable.",
        action_es="⛔ Turbo VGT con falla. Puede causar pérdida significativa de potencia. Servicio urgente.",
    ),
    651: SPNInfo(
        spn=651,
        name_en="Injector Metering Rail 1 Pressure",
        name_es="Presión del Riel de Inyectores",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión de combustible en el riel de inyectores.",
        action_es="⛔ Sistema de inyección con falla. Puede causar humo, pérdida de potencia o apagado.",
    ),
    # Fuel System
    94: SPNInfo(
        spn=94,
        name_en="Fuel Delivery Pressure",
        name_es="Presión de Entrega de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Presión de combustible antes del sistema de inyección.",
        action_es="🔧 Verificar filtros de combustible y bomba de transferencia. Servicio en 48 horas.",
    ),
    96: SPNInfo(
        spn=96,
        name_en="Fuel Level",
        name_es="Nivel de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Sensor de nivel del tanque de combustible.",
        action_es="📋 Verificar sensor si lectura es incorrecta. No crítico para operación.",
    ),
    183: SPNInfo(
        spn=183,
        name_en="Fuel Rate",
        name_es="Tasa de Consumo de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Tasa de consumo de combustible instantánea.",
        action_es="📋 Informativo. Usar para monitoreo de eficiencia.",
    ),
    # Air Intake
    105: SPNInfo(
        spn=105,
        name_en="Intake Manifold Temperature",
        name_es="Temperatura del Múltiple de Admisión",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aire en el múltiple de admisión.",
        action_es="🔧 Verificar intercooler y sistema de admisión. Servicio en 48 horas.",
    ),
    106: SPNInfo(
        spn=106,
        name_en="Intake Manifold Pressure",
        name_es="Presión del Múltiple de Admisión",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Presión de aire de admisión (boost del turbo).",
        action_es="🔧 Posible fuga en sistema de admisión o problema de turbo.",
    ),
    108: SPNInfo(
        spn=108,
        name_en="Barometric Pressure",
        name_es="Presión Barométrica",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.INFO,
        description_es="Sensor de presión atmosférica para ajuste de inyección.",
        action_es="📋 Generalmente solo afecta rendimiento en altitud. Monitorear.",
    ),
    171: SPNInfo(
        spn=171,
        name_en="Ambient Air Temperature",
        name_es="Temperatura Ambiente",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.INFO,
        description_es="Temperatura del aire exterior.",
        action_es="📋 Informativo para cálculos de ECU. No crítico.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - COOLING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

COOLING_SPNS = {
    111: SPNInfo(
        spn=111,
        name_en="Coolant Level",
        name_es="Nivel de Refrigerante",
        system=DTCSystem.COOLING,
        severity=DTCSeverity.CRITICAL,
        description_es="Nivel del líquido refrigerante en el radiador.",
        action_es="⛔ Nivel bajo de refrigerante. Verificar inmediatamente. Riesgo de sobrecalentamiento.",
    ),
    175: SPNInfo(
        spn=175,
        name_en="Engine Oil Temperature",
        name_es="Temperatura de Aceite del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aceite del motor.",
        action_es="🔧 Temperatura de aceite anormal. Verificar sistema de enfriamiento.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - AFTERTREATMENT (DEF/SCR/DPF)
# ═══════════════════════════════════════════════════════════════════════════════

AFTERTREATMENT_SPNS = {
    1761: SPNInfo(
        spn=1761,
        name_en="DEF Tank Level",
        name_es="Nivel del Tanque de DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Nivel de líquido DEF (AdBlue/urea) en el tanque.",
        action_es="⛔ DEF bajo. El motor puede reducir potencia a 5 MPH si se vacía. Rellenar urgente.",
    ),
    3031: SPNInfo(
        spn=3031,
        name_en="DEF Quality",
        name_es="Calidad del DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de calidad del líquido DEF.",
        action_es="⛔ DEF contaminado o incorrecto. Drenar y rellenar con DEF certificado. Riesgo de derating.",
    ),
    3216: SPNInfo(
        spn=3216,
        name_en="DEF System Inducement",
        name_es="Inducción del Sistema DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Sistema de reducción de potencia por problemas de DEF.",
        action_es="⛔ ¡URGENTE! Motor en modo de inducción. Potencia limitada. Reparar sistema DEF inmediatamente.",
    ),
    3226: SPNInfo(
        spn=3226,
        name_en="SCR Catalyst Conversion Efficiency",
        name_es="Eficiencia del Catalizador SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Eficiencia de conversión del catalizador SCR.",
        action_es="🔧 Catalizador SCR degradado. Programar reemplazo. Puede activar inducción si empeora.",
    ),
    3242: SPNInfo(
        spn=3242,
        name_en="DPF Differential Pressure",
        name_es="Presión Diferencial del DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Presión diferencial en el filtro de partículas diesel.",
        action_es="🔧 DPF posiblemente obstruido. Puede necesitar regeneración forzada.",
    ),
    3246: SPNInfo(
        spn=3246,
        name_en="DPF Soot Load",
        name_es="Carga de Hollín del DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Nivel de acumulación de hollín en el DPF.",
        action_es="🔧 DPF con alta carga de hollín. Realizar regeneración pronto.",
    ),
    3251: SPNInfo(
        spn=3251,
        name_en="DPF Regeneration",
        name_es="Regeneración del DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Estado del proceso de regeneración del DPF.",
        action_es="🔧 Problema con regeneración del DPF. Verificar si se completó correctamente.",
    ),
    4364: SPNInfo(
        spn=4364,
        name_en="DEF Dosing",
        name_es="Dosificación de DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Sistema de dosificación de líquido DEF.",
        action_es="⛔ Falla en dosificación DEF. Puede causar derating. Servicio urgente.",
    ),
    5246: SPNInfo(
        spn=5246,
        name_en="DEF Tank Temperature",
        name_es="Temperatura del Tanque DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del líquido DEF (puede congelarse).",
        action_es="🔧 Verificar calentador del tanque DEF en clima frío.",
    ),
    # Exhaust System
    411: SPNInfo(
        spn=411,
        name_en="EGR Temperature",
        name_es="Temperatura del EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del sistema de recirculación de gases de escape.",
        action_es="🔧 Verificar válvula EGR y enfriador. Servicio en 48 horas.",
    ),
    412: SPNInfo(
        spn=412,
        name_en="EGR Differential Pressure",
        name_es="Presión Diferencial del EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Presión diferencial del sistema EGR.",
        action_es="🔧 Posible obstrucción en sistema EGR. Verificar válvula y enfriador.",
    ),
    1127: SPNInfo(
        spn=1127,
        name_en="DPF Outlet Temperature",
        name_es="Temperatura de Salida del DPF",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de gases a la salida del filtro de partículas.",
        action_es="🔧 Monitorear durante regeneración. Temperaturas anormales indican problema.",
    ),
    1173: SPNInfo(
        spn=1173,
        name_en="EGR Mass Flow Rate",
        name_es="Flujo Másico del EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Flujo de gases recirculados por el EGR.",
        action_es="🔧 Flujo anormal. Verificar válvula EGR y sensor de flujo.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - ELECTRICAL SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

ELECTRICAL_SPNS = {
    158: SPNInfo(
        spn=158,
        name_en="Battery Potential / Power Input",
        name_es="Voltaje de Batería / Entrada de Energía",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje de la batería del vehículo.",
        action_es="🔋 Voltaje anormal. Verificar batería y alternador. Puede causar problemas de arranque.",
    ),
    167: SPNInfo(
        spn=167,
        name_en="Alternator Charging Voltage",
        name_es="Voltaje de Carga del Alternador",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje de salida del alternador.",
        action_es="🔋 Alternador con voltaje anormal. Revisar alternador y correa.",
    ),
    168: SPNInfo(
        spn=168,
        name_en="Battery Potential",
        name_es="Potencial de Batería",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Estado de carga de la batería.",
        action_es="🔋 Batería con voltaje bajo/alto. Verificar estado de batería.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - TRANSMISSION
# ═══════════════════════════════════════════════════════════════════════════════

TRANSMISSION_SPNS = {
    127: SPNInfo(
        spn=127,
        name_en="Transmission Oil Pressure",
        name_es="Presión de Aceite de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión de aceite en la transmisión automática.",
        action_es="⛔ Presión de aceite de transmisión anormal. Puede causar daño. Verificar nivel y condición.",
    ),
    177: SPNInfo(
        spn=177,
        name_en="Transmission Oil Temperature",
        name_es="Temperatura de Aceite de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.CRITICAL,
        description_es="Temperatura del aceite de la transmisión.",
        action_es="⛔ Transmisión sobrecalentada. Reducir carga. Verificar enfriador de transmisión.",
    ),
    161: SPNInfo(
        spn=161,
        name_en="Transmission Input Shaft Speed",
        name_es="Velocidad del Eje de Entrada de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.WARNING,
        description_es="Sensor de velocidad del eje de entrada de la transmisión.",
        action_es="🔧 Sensor de velocidad con falla. Puede causar cambios erráticos.",
    ),
    191: SPNInfo(
        spn=191,
        name_en="Transmission Output Shaft Speed",
        name_es="Velocidad del Eje de Salida de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.WARNING,
        description_es="Sensor de velocidad del eje de salida de la transmisión.",
        action_es="🔧 Sensor de velocidad de salida con falla. Afecta velocímetro y cambios.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - BRAKES
# ═══════════════════════════════════════════════════════════════════════════════

BRAKES_SPNS = {
    521: SPNInfo(
        spn=521,
        name_en="Service Brake Status",
        name_es="Estado del Freno de Servicio",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.CRITICAL,
        description_es="Estado del sistema de frenos de servicio.",
        action_es="⛔ ¡CRÍTICO DE SEGURIDAD! Problema en sistema de frenos. No operar hasta verificar.",
    ),
    524: SPNInfo(
        spn=524,
        name_en="Parking Brake Status",
        name_es="Estado del Freno de Estacionamiento",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.WARNING,
        description_es="Estado del freno de estacionamiento.",
        action_es="🔧 Verificar freno de estacionamiento. Puede no activarse correctamente.",
    ),
    1121: SPNInfo(
        spn=1121,
        name_en="ABS Lamp Status",
        name_es="Estado de Lámpara ABS",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.WARNING,
        description_es="Indicador del sistema antibloqueo de frenos.",
        action_es="🔧 ABS con falla. Frenos funcionan pero sin antibloqueo. Servicio pronto.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - HVAC
# ═══════════════════════════════════════════════════════════════════════════════

HVAC_SPNS = {
    441: SPNInfo(
        spn=441,
        name_en="AC High Pressure Switch",
        name_es="Interruptor de Alta Presión AC",
        system=DTCSystem.HVAC,
        severity=DTCSeverity.INFO,
        description_es="Presión alta del sistema de aire acondicionado.",
        action_es="📋 Sistema AC con presión alta. Verificar refrigerante y condensador.",
    ),
    464: SPNInfo(
        spn=464,
        name_en="AC Refrigerant Pressure",
        name_es="Presión de Refrigerante AC",
        system=DTCSystem.HVAC,
        severity=DTCSeverity.INFO,
        description_es="Presión del refrigerante del aire acondicionado.",
        action_es="📋 Sistema AC puede necesitar servicio. No crítico para operación.",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

# Merge all SPN databases
SPN_DATABASE: dict[int, SPNInfo] = {
    **ENGINE_SPNS,
    **COOLING_SPNS,
    **AFTERTREATMENT_SPNS,
    **ELECTRICAL_SPNS,
    **TRANSMISSION_SPNS,
    **BRAKES_SPNS,
    **HVAC_SPNS,
}


# ═══════════════════════════════════════════════════════════════════════════════
# LOOKUP FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_spn_info(spn: int) -> Optional[SPNInfo]:
    """
    Get detailed information for a SPN code.

    Args:
        spn: Suspect Parameter Number

    Returns:
        SPNInfo if found, None otherwise
    """
    return SPN_DATABASE.get(spn)


def get_fmi_info(fmi: int) -> dict:
    """
    Get detailed information for a FMI code.

    Args:
        fmi: Failure Mode Identifier (0-31)

    Returns:
        Dict with en/es descriptions and severity
    """
    return FMI_DESCRIPTIONS.get(
        fmi,
        {
            "en": f"Unknown FMI ({fmi})",
            "es": f"FMI desconocido ({fmi})",
            "severity": DTCSeverity.INFO,
        },
    )


def get_dtc_description(spn: int, fmi: int, language: str = "es") -> dict:
    """
    Get full description for a DTC code (SPN.FMI combination).

    Args:
        spn: Suspect Parameter Number
        fmi: Failure Mode Identifier
        language: "en" or "es" (default Spanish)

    Returns:
        Dict with component, failure_mode, severity, action
    """
    spn_info = get_spn_info(spn)
    fmi_info = get_fmi_info(fmi)

    if spn_info:
        component = spn_info.name_es if language == "es" else spn_info.name_en
        description = spn_info.description_es
        action = spn_info.action_es
        system = spn_info.system.value
        # Use higher severity between SPN and FMI
        severity = max(
            spn_info.severity,
            fmi_info["severity"],
            key=lambda s: {"CRITICAL": 3, "WARNING": 2, "INFO": 1}.get(
                s.value.upper(), 0
            ),
        )
    else:
        component = (
            f"Componente Desconocido (SPN {spn})"
            if language == "es"
            else f"Unknown Component (SPN {spn})"
        )
        description = "No hay información disponible para este código."
        action = "Consultar manual del fabricante."
        system = DTCSystem.UNKNOWN.value
        severity = fmi_info["severity"]

    failure_mode = fmi_info["es"] if language == "es" else fmi_info["en"]

    return {
        "code": f"SPN{spn}.FMI{fmi}",
        "spn": spn,
        "fmi": fmi,
        "component": component,
        "failure_mode": failure_mode,
        "description": description,
        "action": action,
        "system": system,
        "severity": severity.value,
    }


def get_all_spns_by_system(system: DTCSystem) -> list[SPNInfo]:
    """Get all SPNs for a specific vehicle system."""
    return [info for info in SPN_DATABASE.values() if info.system == system]


def get_critical_spns() -> list[int]:
    """Get list of all critical SPN codes."""
    return [
        spn
        for spn, info in SPN_DATABASE.items()
        if info.severity == DTCSeverity.CRITICAL
    ]


def get_database_stats() -> dict:
    """Get statistics about the DTC database."""
    systems = {}
    severities = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}

    for info in SPN_DATABASE.values():
        system = info.system.value
        systems[system] = systems.get(system, 0) + 1
        severities[info.severity.value.upper()] += 1

    return {
        "total_spns": len(SPN_DATABASE),
        "total_fmis": len(FMI_DESCRIPTIONS),
        "by_system": systems,
        "by_severity": severities,
    }
