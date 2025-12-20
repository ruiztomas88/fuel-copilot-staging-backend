"""
J1939 DTC Database - Catálogo Expandido v5.8.0
═══════════════════════════════════════════════════════════════════════════════

Comprehensive J1939 DTC (Diagnostic Trouble Code) database for Class 8 trucks.
Includes descriptions in Spanish for fleet operations in Latin America.

Structure:
- SPN (Suspect Parameter Number): Identifies component/signal
- FMI (Failure Mode Identifier): Describes failure type (0-31)

Sources:
- SAE J1939-73 (Application Layer - Diagnostics)
- Official MondoTracking/Pacific Track Documentation
- Cummins, Detroit Diesel, Paccar manufacturer codes
- Real-world fleet data from Fuel Analytics operations

Author: Fuel Analytics Team
Version: 5.8.0
Updated: December 2025 - Full SPN/FMI from official documentation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


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
    5444: SPNInfo(
        spn=5444,
        name_en="Aftertreatment 1 Diesel Exhaust Fluid Quality",
        name_es="Calidad del Fluido DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Calidad del Diesel Exhaust Fluid (DEF/AdBlue) fuera de especificación. Puede estar contaminado, diluido con agua, o degradado por edad.",
        action_es="⛔ CRÍTICO: Vaciar tanque DEF y rellenar con DEF nuevo certificado ISO 22241. DEF contaminado puede causar falla del sistema SCR y derate del motor. Verificar fuente de DEF.",
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
# SPN DATABASE - WIALON DETECTED SPNs (Added from real fleet data)
# ═══════════════════════════════════════════════════════════════════════════════

WIALON_DETECTED_SPNS = {
    # SPN 597 - Brake Switch
    597: SPNInfo(
        spn=597,
        name_en="Brake Switch",
        name_es="Interruptor del Pedal de Freno",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.WARNING,
        description_es="Sensor que detecta cuando se presiona el pedal de freno. Importante para luces de freno y control de crucero.",
        action_es="🔧 Verificar interruptor del pedal de freno. Puede afectar luces de freno y funciones de seguridad.",
    ),
    # SPN 829 - J1939 Network
    829: SPNInfo(
        spn=829,
        name_en="J1939 Network #1",
        name_es="Red J1939 #1",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Estado de comunicación del bus de datos J1939. Red de comunicación entre módulos del vehículo.",
        action_es="🔧 Error de comunicación en red CAN/J1939. Verificar conectores y cableado. Puede causar lecturas erráticas.",
    ),
    # SPN 1089 - Engine Torque Mode
    1089: SPNInfo(
        spn=1089,
        name_en="Engine Torque Mode",
        name_es="Modo de Torque del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Estado del modo de control de torque del motor. Define cómo la ECU controla la potencia.",
        action_es="🔧 El motor puede estar en modo de protección o limitado. Verificar otros códigos activos.",
    ),
    # SPN 1322 - Engine Protection System
    1322: SPNInfo(
        spn=1322,
        name_en="Engine Protection System Timer State",
        name_es="Estado del Timer de Protección del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Sistema de protección del motor activado. Indica que el motor está en modo de protección por una condición crítica.",
        action_es="⛔ SISTEMA DE PROTECCIÓN ACTIVO. El motor puede apagarse automáticamente. Revisar otros DTCs inmediatamente.",
    ),
    # SPN 1548 - Malfunction Indicator Lamp (MIL)
    1548: SPNInfo(
        spn=1548,
        name_en="Malfunction Indicator Lamp Command",
        name_es="Comando de Luz de Falla (Check Engine)",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Control de la luz de 'Check Engine'. Indica que hay una falla activa que requiere atención.",
        action_es="⚠️ LUZ CHECK ENGINE ACTIVA. Indica falla que requiere diagnóstico. Revisar todos los DTCs activos.",
    ),
    # SPN 1592 - Engine Protection System Config
    1592: SPNInfo(
        spn=1592,
        name_en="Engine Protection System Config",
        name_es="Configuración del Sistema de Protección",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Parámetros de configuración del sistema de protección del motor.",
        action_es="🔧 Error en configuración de protección del motor. Puede requerir reprogramación de ECU.",
    ),
    # SPN 1636 - SCR Catalyst System
    1636: SPNInfo(
        spn=1636,
        name_en="SCR Catalyst Conversion Efficiency",
        name_es="Eficiencia del Catalizador SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Eficiencia del sistema de reducción catalítica selectiva (SCR/DEF). Controla emisiones de NOx.",
        action_es="⛔ SISTEMA SCR CON BAJA EFICIENCIA. Puede causar DERATING (reducción de potencia). Verificar DEF y catalizador.",
    ),
    # SPN 2023 - DEF Actual Dose
    2023: SPNInfo(
        spn=2023,
        name_en="DEF Actual Dosing Quantity",
        name_es="Cantidad Real de Dosificación DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Cantidad real de DEF siendo inyectada vs cantidad esperada.",
        action_es="🔧 Dosificación de DEF incorrecta. Verificar bomba de DEF, líneas e inyector. Puede causar falla SCR.",
    ),
    # SPN 2791 - EGR Cooler Efficiency
    2791: SPNInfo(
        spn=2791,
        name_en="EGR Cooler Efficiency",
        name_es="Eficiencia del Enfriador EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Eficiencia del enfriador de gases de escape recirculados (EGR).",
        action_es="🔧 Enfriador EGR con baja eficiencia. Puede causar altas temperaturas y daño al motor. Programar servicio.",
    ),
    # SPN 3510 - DEF Tank Temperature
    3510: SPNInfo(
        spn=3510,
        name_en="DEF Tank Temperature",
        name_es="Temperatura del Tanque de DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del líquido DEF en el tanque. DEF se congela a -11°C y degrada sobre 30°C.",
        action_es="🔧 Temperatura DEF fuera de rango. Si está congelado, esperar que caliente. Si está caliente, estacionar a la sombra.",
    ),
    # SPN 5571 - Engine Protection Torque Derate
    5571: SPNInfo(
        spn=5571,
        name_en="Engine Protection Torque Derate",
        name_es="Reducción de Torque por Protección",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Motor está reduciendo torque/potencia como medida de protección. Indica condición crítica.",
        action_es="⛔ MOTOR EN DERATING. Potencia reducida por protección. El camión puede quedarse en velocidad baja. ATENCIÓN URGENTE.",
    ),
    # ═══════════════════════════════════════════════════════════════════════════════
    # CÓDIGOS SPN ADICIONALES DEL ESTÁNDAR J1939 (Importados desde numeralkod.com)
    # ═══════════════════════════════════════════════════════════════════════════════
    # ─────────────────────────────────────────────────────────────────────────
    # MOTOR - SENSORES CRÍTICOS DE PRESIÓN Y TEMPERATURA
    # ─────────────────────────────────────────────────────────────────────────
    100: SPNInfo(
        spn=100,
        name_en="Engine Oil Pressure",
        name_es="Presión de Aceite del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión del aceite lubricante del motor. Crítica para prevenir daños en componentes internos.",
        action_es="⛔ DETENER EL MOTOR: Verificar nivel de aceite, bomba de aceite, filtro obstruido. Verificar sensor de presión de aceite y su cableado.",
    ),
    175: SPNInfo(
        spn=175,
        name_en="Engine Oil Temperature 1",
        name_es="Temperatura del Aceite del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aceite lubricante del motor. Temperatura alta puede indicar falla de enfriador.",
        action_es="🔧 Verificar enfriador de aceite, nivel de aceite, viscosidad correcta. Temperatura normal: 80-110°C.",
    ),
    190: SPNInfo(
        spn=190,
        name_en="Engine Speed",
        name_es="Velocidad del Motor (RPM)",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de velocidad del motor (RPM). Esencial para control del motor y funcionamiento del vehículo.",
        action_es="⛔ Verificar sensor de posición del cigüeñal (CKP), conexiones eléctricas, reluctor. Motor puede no arrancar.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # SISTEMA DE COMBUSTIBLE
    # ─────────────────────────────────────────────────────────────────────────
    96: SPNInfo(
        spn=96,
        name_en="Fuel Level",
        name_es="Nivel de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Nivel de combustible en el tanque principal.",
        action_es="ℹ️ Verificar sensor de nivel de combustible, calibración, cableado. Rellenar tanque si está bajo.",
    ),
    97: SPNInfo(
        spn=97,
        name_en="Water In Fuel Indicator",
        name_es="Indicador de Agua en Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Detección de agua en el sistema de combustible. Agua puede dañar inyectores y bomba.",
        action_es="⚠️ DRENAR AGUA del separador de combustible inmediatamente. Verificar calidad del combustible y fuente de agua.",
    ),
    183: SPNInfo(
        spn=183,
        name_en="Engine Fuel Rate",
        name_es="Caudal de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Tasa de consumo de combustible actual del motor.",
        action_es="ℹ️ Información de consumo en tiempo real. Útil para diagnóstico de eficiencia.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # INYECTORES (651-656)
    # ─────────────────────────────────────────────────────────────────────────
    657: SPNInfo(
        spn=657,
        name_en="Engine Injector Cylinder #07",
        name_es="Inyector Cilindro #7",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Falla en el inyector del cilindro 7.",
        action_es="🔧 Verificar inyector, cableado, resistencia, códigos de balance. Reemplazar si está defectuoso.",
    ),
    658: SPNInfo(
        spn=658,
        name_en="Engine Injector Cylinder #08",
        name_es="Inyector Cilindro #8",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Falla en el inyector del cilindro 8.",
        action_es="🔧 Verificar inyector, cableado, resistencia, códigos de balance. Reemplazar si está defectuoso.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # SISTEMA ELÉCTRICO Y BATERÍA
    # ─────────────────────────────────────────────────────────────────────────
    168: SPNInfo(
        spn=168,
        name_en="Battery Potential / Power Input #1",
        name_es="Voltaje de Batería Principal",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje de la batería principal del vehículo. Voltaje bajo puede causar problemas de arranque.",
        action_es="🔧 Verificar alternador, batería, conexiones. Voltaje normal: 24-28V (sistema 24V) o 12-14V (sistema 12V).",
    ),
    158: SPNInfo(
        spn=158,
        name_en="Keyswitch Battery Potential",
        name_es="Voltaje con Switch ON",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje de batería con llave de contacto activada.",
        action_es="🔧 Verificar batería, conexiones del switch de ignición, caída de voltaje.",
    ),
    167: SPNInfo(
        spn=167,
        name_en="Charging System Potential",
        name_es="Voltaje del Sistema de Carga",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje del alternador/sistema de carga.",
        action_es="🔧 Verificar alternador, regulador de voltaje, banda del alternador. Verificar que esté cargando correctamente.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # SISTEMA DE POSTRATAMIENTO (AFTERTREATMENT) - DEF/SCR/DPF
    # ─────────────────────────────────────────────────────────────────────────
    3216: SPNInfo(
        spn=3216,
        name_en="Aftertreatment #1 Intake NOx",
        name_es="NOx Entrada Sistema SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Sensor de NOx a la entrada del sistema SCR. Mide emisiones antes de tratamiento.",
        action_es="🔧 Verificar sensor de NOx, calentador del sensor, cableado. Verificar calibración. Reemplazar si defectuoso.",
    ),
    3217: SPNInfo(
        spn=3217,
        name_en="Aftertreatment #1 Intake O2",
        name_es="Oxígeno Entrada Sistema SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Sensor de oxígeno a la entrada del sistema de postratamiento.",
        action_es="🔧 Verificar sensor O2, calentador, cableado. Verificar fugas en escape.",
    ),
    3226: SPNInfo(
        spn=3226,
        name_en="Aftertreatment #1 Outlet NOx",
        name_es="NOx Salida Sistema SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Sensor de NOx a la salida del sistema SCR. Mide eficiencia de reducción de NOx.",
        action_es="🔧 Verificar sensor de NOx, calidad del DEF, eficiencia del catalizador SCR. Si NOx salida alto: verificar dosificación DEF.",
    ),
    3227: SPNInfo(
        spn=3227,
        name_en="Aftertreatment #1 Outlet O2",
        name_es="Oxígeno Salida Sistema SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Sensor de oxígeno a la salida del sistema SCR.",
        action_es="🔧 Verificar sensor O2 downstream, calentador, eficiencia del catalizador.",
    ),
    3700: SPNInfo(
        spn=3700,
        name_en="DPF Active Regeneration Status",
        name_es="Estado de Regeneración Activa DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.INFO,
        description_es="Estado actual del proceso de regeneración del filtro de partículas diésel (DPF).",
        action_es="ℹ️ Normal durante regeneración. Si regeneraciones son muy frecuentes (más de 1 por día): verificar consumo de aceite, inyectores, sensor de presión diferencial DPF.",
    ),
    3719: SPNInfo(
        spn=3719,
        name_en="Particulate Trap #1 Soot Load Percent",
        name_es="Porcentaje de Hollín en Filtro DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Nivel de hollín acumulado en el filtro de partículas diésel. >100% requiere regeneración forzada.",
        action_es="⚠️ Si >100%: Regeneración forzada estacionaria requerida. Si >140%: Limpieza profesional o reemplazo del DPF necesario.",
    ),
    3720: SPNInfo(
        spn=3720,
        name_en="Particulate Trap #1 Ash Load Percent",
        name_es="Porcentaje de Ceniza en Filtro DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Nivel de ceniza acumulada en el DPF (no se puede regenerar, solo limpieza profesional).",
        action_es="⚠️ Si >100%: Limpieza profesional del DPF requerida o reemplazo. Ceniza se acumula con uso normal (250,000-400,000 km).",
    ),
    4364: SPNInfo(
        spn=4364,
        name_en="Aftertreatment #1 SCR Catalyst Conversion Efficiency",
        name_es="Eficiencia de Conversión Catalizador SCR",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Eficiencia del catalizador SCR en reducir NOx. Eficiencia normal debe ser >80%.",
        action_es="⚠️ Si <60%: Verificar calidad DEF, dosificación correcta, temperatura catalizador. Catalizador puede estar contaminado o degradado. Reemplazo puede ser necesario.",
    ),
    5963: SPNInfo(
        spn=5963,
        name_en="Aftertreatment 1 Total Diesel Exhaust Fluid Used",
        name_es="Consumo Total de DEF (Litros)",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.INFO,
        description_es="Cantidad total acumulada de DEF consumido por el sistema desde el inicio.",
        action_es="ℹ️ Información de consumo histórico. Consumo normal: 2-6% del diésel consumido. Útil para planificación de rellenado.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # TURBO Y ADMISIÓN
    # ─────────────────────────────────────────────────────────────────────────
    1127: SPNInfo(
        spn=1127,
        name_en="Engine Turbocharger 1 Boost Pressure",
        name_es="Presión del Turbocompresor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Presión de sobrealimentación (boost) del turbocompresor.",
        action_es="🔧 Verificar actuador VGT/wastegate, sensor de presión boost, fugas en mangueras de admisión, intercooler.",
    ),
    1172: SPNInfo(
        spn=1172,
        name_en="Engine Turbocharger 1 Turbine Inlet Temperature",
        name_es="Temperatura Entrada Turbina Turbo",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de gases de escape a la entrada de la turbina del turbo.",
        action_es="🔧 Temperatura alta puede indicar problemas de inyección o timing. Temperatura normal: 600-800°C bajo carga.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # SENSORES ADICIONALES DEL MOTOR
    # ─────────────────────────────────────────────────────────────────────────
    171: SPNInfo(
        spn=171,
        name_en="Ambient Air Temperature",
        name_es="Temperatura Ambiente",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Temperatura del aire ambiente exterior.",
        action_es="ℹ️ Verificar sensor si lecturas no son razonables. Afecta cálculos de densidad de aire.",
    ),
    172: SPNInfo(
        spn=172,
        name_en="Engine Air Inlet Temperature",
        name_es="Temperatura Aire Admisión",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aire a la entrada del motor (después del intercooler).",
        action_es="🔧 Verificar sensor IAT, intercooler funcionando correctamente. Temperatura alta reduce potencia.",
    ),
    173: SPNInfo(
        spn=173,
        name_en="Engine Exhaust Gas Temperature",
        name_es="Temperatura Gases de Escape",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de los gases de escape del motor.",
        action_es="🔧 Temperatura muy alta puede indicar problemas de inyección, turbo, o DPF saturado.",
    ),
    174: SPNInfo(
        spn=174,
        name_en="Engine Fuel Temperature 1",
        name_es="Temperatura del Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Temperatura del combustible en el sistema.",
        action_es="ℹ️ Temperatura alta puede reducir potencia. Verificar enfriador de combustible si aplicable.",
    ),
    247: SPNInfo(
        spn=247,
        name_en="Engine Total Hours of Operation",
        name_es="Horas Totales de Operación del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Horómetro total del motor desde fabricación.",
        action_es="ℹ️ Información de horómetro. Útil para programar mantenimientos preventivos.",
    ),
    250: SPNInfo(
        spn=250,
        name_en="Engine Total Fuel Used",
        name_es="Combustible Total Consumido",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Cantidad total acumulada de combustible consumido por el motor.",
        action_es="ℹ️ Información histórica de consumo. Útil para análisis de eficiencia a largo plazo.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # OTROS SENSORES DE POSTRATAMIENTO
    # ─────────────────────────────────────────────────────────────────────────
    4765: SPNInfo(
        spn=4765,
        name_en="Aftertreatment #1 Diesel Oxidation Catalyst Intake Gas Temperature",
        name_es="Temperatura Entrada Catalizador DOC",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.INFO,
        description_es="Temperatura de gases a la entrada del catalizador de oxidación diésel (DOC).",
        action_es="ℹ️ Verificar sensor de temperatura. DOC requiere temperatura mínima para funcionar (250°C+).",
    ),
    4766: SPNInfo(
        spn=4766,
        name_en="Aftertreatment #1 Diesel Oxidation Catalyst Outlet Gas Temperature",
        name_es="Temperatura Salida Catalizador DOC",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.INFO,
        description_es="Temperatura de gases a la salida del catalizador de oxidación diésel (DOC).",
        action_es="ℹ️ Temperatura salida debe ser mayor que entrada durante regeneración activa.",
    ),
    4767: SPNInfo(
        spn=4767,
        name_en="Aftertreatment #1 Diesel Oxidation Catalyst Differential Pressure",
        name_es="Presión Diferencial Catalizador DOC",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Presión diferencial a través del catalizador de oxidación (DOC).",
        action_es="🔧 Presión diferencial alta puede indicar obstrucción del DOC. Verificar sensor y limpiar/reemplazar DOC si necesario.",
    ),
    5394: SPNInfo(
        spn=5394,
        name_en="Aftertreatment 1 Diesel Exhaust Fluid Dosing Valve 1",
        name_es="Válvula Dosificadora DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Válvula de dosificación del fluido DEF (inyector de DEF).",
        action_es="🔧 Verificar válvula dosificadora, cristalización de urea, cableado, suministro de DEF. Limpiar o reemplazar si está obstruida.",
    ),
    5837: SPNInfo(
        spn=5837,
        name_en="Fuel Type",
        name_es="Tipo de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Tipo de combustible configurado o detectado por el sistema.",
        action_es="ℹ️ Verificar que el tipo de combustible sea correcto para el motor (diésel, biodiésel, etc).",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# SPN DATABASE - ADDITIONAL J1939 OFFICIAL CODES
# ═══════════════════════════════════════════════════════════════════════════════

ADDITIONAL_SPNS = {
    # ─────────────────────────────────────────────────────────────────────────
    # FUEL SYSTEM SPNs
    # ─────────────────────────────────────────────────────────────────────────
    16: SPNInfo(
        spn=16,
        name_en="Engine Fuel Filter Differential Pressure",
        name_es="Presión Diferencial del Filtro de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Diferencia de presión entre entrada y salida del filtro de combustible.",
        action_es="🔧 Filtro de combustible posiblemente obstruido. Reemplazar en próximo servicio.",
    ),
    38: SPNInfo(
        spn=38,
        name_en="Second Fuel Level",
        name_es="Nivel de Combustible Secundario",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Nivel de combustible en tanque secundario.",
        action_es="📋 Informativo. Monitorear nivel de combustible.",
    ),
    95: SPNInfo(
        spn=95,
        name_en="Engine Fuel Filter Differential Pressure",
        name_es="Presión Diferencial Filtro Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Presión diferencial del filtro de combustible del motor.",
        action_es="🔧 Filtro de combustible requiere atención. Programar reemplazo.",
    ),
    97: SPNInfo(
        spn=97,
        name_en="Water in Fuel Indicator",
        name_es="⚠️ Indicador de Agua en Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.CRITICAL,
        description_es="Se detectó agua en el sistema de combustible.",
        action_es="⛔ DRENAR SEPARADOR DE AGUA inmediatamente. Agua puede dañar inyectores.",
    ),
    174: SPNInfo(
        spn=174,
        name_en="Engine Fuel Temperature",
        name_es="Temperatura del Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del combustible del motor.",
        action_es="🔧 Combustible caliente puede afectar rendimiento. Verificar sistema de enfriamiento.",
    ),
    183: SPNInfo(
        spn=183,
        name_en="Engine Fuel Rate",
        name_es="Tasa de Consumo de Combustible",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Tasa de consumo de combustible instantánea del motor.",
        action_es="📋 Informativo. Usar para monitorear eficiencia de combustible.",
    ),
    250: SPNInfo(
        spn=250,
        name_en="Engine Total Fuel Used",
        name_es="Combustible Total Usado",
        system=DTCSystem.FUEL,
        severity=DTCSeverity.INFO,
        description_es="Total de combustible usado por el motor desde fábrica.",
        action_es="📋 Informativo. Usar para análisis de consumo histórico.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # ENGINE CORE SPNs
    # ─────────────────────────────────────────────────────────────────────────
    21: SPNInfo(
        spn=21,
        name_en="Engine ECU Temperature",
        name_es="Temperatura de ECU del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de la unidad de control del motor (ECU).",
        action_es="🔧 ECU con temperatura anormal. Verificar ventilación del compartimento.",
    ),
    51: SPNInfo(
        spn=51,
        name_en="Engine Throttle Position",
        name_es="Posición del Acelerador",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Posición del acelerador del motor.",
        action_es="⛔ Problema de acelerador. Puede causar pérdida de control de potencia.",
    ),
    92: SPNInfo(
        spn=92,
        name_en="Engine Percent Load at Current Speed",
        name_es="Porcentaje de Carga del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Porcentaje de carga actual del motor a la velocidad actual.",
        action_es="📋 Informativo. Útil para análisis de operación.",
    ),
    98: SPNInfo(
        spn=98,
        name_en="Engine Oil Level",
        name_es="Nivel de Aceite del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Nivel de aceite en el cárter del motor.",
        action_es="⛔ VERIFICAR NIVEL DE ACEITE inmediatamente. Puede causar daño al motor.",
    ),
    99: SPNInfo(
        spn=99,
        name_en="Engine Oil Filter Differential Pressure",
        name_es="Presión Diferencial Filtro de Aceite",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Diferencia de presión en el filtro de aceite.",
        action_es="🔧 Filtro de aceite posiblemente obstruido. Programar cambio.",
    ),
    101: SPNInfo(
        spn=101,
        name_en="Engine Crankcase Pressure",
        name_es="Presión del Cárter",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.WARNING,
        description_es="Presión de gases en el cárter del motor.",
        action_es="🔧 Presión del cárter anormal. Verificar sistema de ventilación y posible blow-by.",
    ),
    164: SPNInfo(
        spn=164,
        name_en="Engine Injection Control Pressure",
        name_es="Presión de Control de Inyección",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión de control del sistema de inyección.",
        action_es="⛔ Problema de presión de inyección. Puede causar mal funcionamiento del motor.",
    ),
    235: SPNInfo(
        spn=235,
        name_en="Engine Total Idle Hours",
        name_es="Horas Totales de Ralentí",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Total de horas que el motor ha estado en ralentí.",
        action_es="📋 Informativo. Usar para análisis de idle time.",
    ),
    236: SPNInfo(
        spn=236,
        name_en="Engine Total Idle Fuel Used",
        name_es="Combustible Total Usado en Ralentí",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Total de combustible usado durante ralentí.",
        action_es="📋 Informativo. Útil para calcular costos de idle.",
    ),
    247: SPNInfo(
        spn=247,
        name_en="Engine Total Hours of Operation",
        name_es="Horas Totales de Operación",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Total de horas de operación del motor.",
        action_es="📋 Informativo. Usar para programar mantenimiento.",
    ),
    512: SPNInfo(
        spn=512,
        name_en="Driver's Demand Engine Percent Torque",
        name_es="Torque Demandado por Conductor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Porcentaje de torque que el conductor está demandando.",
        action_es="📋 Informativo. Usado para análisis de estilo de manejo.",
    ),
    513: SPNInfo(
        spn=513,
        name_en="Actual Engine Percent Torque",
        name_es="Torque Real del Motor",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Porcentaje de torque actual que el motor está produciendo.",
        action_es="📋 Informativo. Si difiere mucho del demandado, puede indicar problema.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # TURBO/AIR INTAKE SPNs
    # ─────────────────────────────────────────────────────────────────────────
    52: SPNInfo(
        spn=52,
        name_en="Engine Intercooler Temperature",
        name_es="Temperatura del Intercooler",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aire después del intercooler.",
        action_es="🔧 Intercooler posiblemente obstruido o con fuga. Verificar.",
    ),
    103: SPNInfo(
        spn=103,
        name_en="Engine Turbocharger 1 Speed",
        name_es="Velocidad del Turbo 1",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Velocidad de rotación del turbocompresor.",
        action_es="🔧 Velocidad del turbo fuera de rango. Verificar estado del turbo.",
    ),
    104: SPNInfo(
        spn=104,
        name_en="Turbocharger Lube Oil Pressure",
        name_es="Presión de Aceite del Turbo",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión de aceite de lubricación del turbocompresor.",
        action_es="⛔ Presión de aceite del turbo baja. Riesgo de daño al turbo. Parar motor.",
    ),
    107: SPNInfo(
        spn=107,
        name_en="Engine Air Filter Differential Pressure",
        name_es="Presión Diferencial Filtro de Aire",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Diferencia de presión en el filtro de aire.",
        action_es="🔧 Filtro de aire obstruido. Reemplazar pronto para evitar pérdida de potencia.",
    ),
    132: SPNInfo(
        spn=132,
        name_en="Engine Inlet Air Mass Flow Rate",
        name_es="Flujo Másico de Aire de Admisión",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Cantidad de aire entrando al motor.",
        action_es="🔧 Flujo de aire anormal. Verificar filtros y sistema de admisión.",
    ),
    172: SPNInfo(
        spn=172,
        name_en="Engine Air Inlet Temperature",
        name_es="Temperatura de Aire de Entrada",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aire entrando al motor.",
        action_es="🔧 Temperatura de aire de admisión anormal. Verificar intercooler.",
    ),
    641: SPNInfo(
        spn=641,
        name_en="Engine Turbocharger Variable Geometry Actuator #1",
        name_es="Actuador VGT del Turbo #1",
        system=DTCSystem.AIR_INTAKE,
        severity=DTCSeverity.CRITICAL,
        description_es="Control del turbo de geometría variable.",
        action_es="⛔ Turbo VGT con falla. Pérdida de potencia. Servicio urgente.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # COOLING SYSTEM SPNs
    # ─────────────────────────────────────────────────────────────────────────
    109: SPNInfo(
        spn=109,
        name_en="Engine Coolant Pressure",
        name_es="Presión del Refrigerante",
        system=DTCSystem.COOLING,
        severity=DTCSeverity.WARNING,
        description_es="Presión del sistema de refrigeración.",
        action_es="🔧 Presión del refrigerante fuera de rango. Verificar tapa y mangueras.",
    ),
    176: SPNInfo(
        spn=176,
        name_en="Turbocharger Oil Temperature",
        name_es="Temperatura de Aceite del Turbo",
        system=DTCSystem.COOLING,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aceite de lubricación del turbo.",
        action_es="🔧 Aceite del turbo caliente. Verificar flujo de aceite y enfriamiento.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # TRANSMISSION SPNs
    # ─────────────────────────────────────────────────────────────────────────
    124: SPNInfo(
        spn=124,
        name_en="Transmission Oil Level",
        name_es="Nivel de Aceite de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.CRITICAL,
        description_es="Nivel de aceite en la transmisión.",
        action_es="⛔ Verificar nivel de aceite de transmisión. Puede causar daño.",
    ),
    126: SPNInfo(
        spn=126,
        name_en="Transmission Filter Differential Pressure",
        name_es="Presión Diferencial Filtro Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.WARNING,
        description_es="Presión diferencial del filtro de transmisión.",
        action_es="🔧 Filtro de transmisión obstruido. Programar cambio.",
    ),
    127: SPNInfo(
        spn=127,
        name_en="Transmission Oil Pressure",
        name_es="Presión de Aceite de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión de aceite en la transmisión.",
        action_es="⛔ Presión de aceite de transmisión baja. Parar y verificar.",
    ),
    160: SPNInfo(
        spn=160,
        name_en="Main Shaft Speed",
        name_es="Velocidad del Eje Principal",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.INFO,
        description_es="Velocidad del eje principal de transmisión.",
        action_es="📋 Informativo. Usado para diagnóstico de transmisión.",
    ),
    161: SPNInfo(
        spn=161,
        name_en="Transmission Input Shaft Speed",
        name_es="Velocidad del Eje de Entrada",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.INFO,
        description_es="Velocidad del eje de entrada de la transmisión.",
        action_es="📋 Informativo. Usado para diagnóstico.",
    ),
    163: SPNInfo(
        spn=163,
        name_en="Transmission Current Range",
        name_es="Marcha Actual de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.INFO,
        description_es="Marcha actualmente seleccionada.",
        action_es="📋 Informativo.",
    ),
    177: SPNInfo(
        spn=177,
        name_en="Transmission Oil Temperature",
        name_es="Temperatura de Aceite de Transmisión",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura del aceite de transmisión.",
        action_es="🔧 Aceite de transmisión caliente. Reducir carga y verificar nivel.",
    ),
    191: SPNInfo(
        spn=191,
        name_en="Transmission Output Shaft Speed",
        name_es="Velocidad del Eje de Salida",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.INFO,
        description_es="Velocidad del eje de salida de transmisión.",
        action_es="📋 Informativo. Usado para cálculo de velocidad.",
    ),
    523: SPNInfo(
        spn=523,
        name_en="Transmission Current Gear",
        name_es="Marcha Actual",
        system=DTCSystem.TRANSMISSION,
        severity=DTCSeverity.INFO,
        description_es="Marcha actualmente enganchada.",
        action_es="📋 Informativo.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # BRAKES SPNs
    # ─────────────────────────────────────────────────────────────────────────
    70: SPNInfo(
        spn=70,
        name_en="Parking Brake Switch",
        name_es="Interruptor Freno de Estacionamiento",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.WARNING,
        description_es="Estado del interruptor del freno de estacionamiento.",
        action_es="🔧 Verificar freno de estacionamiento.",
    ),
    116: SPNInfo(
        spn=116,
        name_en="Brake Application Pressure",
        name_es="Presión de Aplicación de Frenos",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión del sistema de frenos al aplicarlos.",
        action_es="⛔ PROBLEMA DE FRENOS. Verificar inmediatamente.",
    ),
    117: SPNInfo(
        spn=117,
        name_en="Brake Primary Pressure",
        name_es="Presión Primaria de Frenos",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión del circuito primario de frenos.",
        action_es="⛔ Presión primaria de frenos baja. NO OPERAR hasta reparar.",
    ),
    118: SPNInfo(
        spn=118,
        name_en="Brake Secondary Pressure",
        name_es="Presión Secundaria de Frenos",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.CRITICAL,
        description_es="Presión del circuito secundario de frenos.",
        action_es="⛔ Presión secundaria de frenos baja. Verificar sistema.",
    ),
    521: SPNInfo(
        spn=521,
        name_en="Brake Pedal Position",
        name_es="Posición del Pedal de Freno",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.WARNING,
        description_es="Posición actual del pedal de freno.",
        action_es="🔧 Sensor de pedal de freno con falla. Verificar sensor.",
    ),
    563: SPNInfo(
        spn=563,
        name_en="Anti-Lock Braking (ABS) Active",
        name_es="Sistema ABS Activo",
        system=DTCSystem.BRAKES,
        severity=DTCSeverity.INFO,
        description_es="Estado de activación del sistema ABS.",
        action_es="📋 Informativo. ABS funcionando normalmente.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # ELECTRICAL SPNs
    # ─────────────────────────────────────────────────────────────────────────
    114: SPNInfo(
        spn=114,
        name_en="Net Battery Current",
        name_es="Corriente Neta de Batería",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Corriente neta de la batería (carga/descarga).",
        action_es="🔧 Corriente de batería anormal. Verificar alternador y batería.",
    ),
    115: SPNInfo(
        spn=115,
        name_en="Alternator Current",
        name_es="Corriente del Alternador",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Corriente de salida del alternador.",
        action_es="🔧 Alternador con salida anormal. Verificar estado.",
    ),
    158: SPNInfo(
        spn=158,
        name_en="Keyswitch Battery Potential",
        name_es="Voltaje de Batería en Switch",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje de batería en el interruptor de encendido.",
        action_es="🔧 Voltaje bajo. Verificar batería y conexiones.",
    ),
    167: SPNInfo(
        spn=167,
        name_en="Charging System Potential",
        name_es="Voltaje del Sistema de Carga",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje del sistema de carga (alternador).",
        action_es="🔧 Sistema de carga con voltaje anormal. Verificar alternador.",
    ),
    168: SPNInfo(
        spn=168,
        name_en="Battery Potential / Power Input #1",
        name_es="Voltaje de Batería",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Voltaje de la batería principal.",
        action_es="🔧 Voltaje de batería bajo o alto. Verificar sistema eléctrico.",
    ),
    620: SPNInfo(
        spn=620,
        name_en="5 Volts DC Supply",
        name_es="Suministro de 5V DC",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.CRITICAL,
        description_es="Suministro de 5 voltios para sensores.",
        action_es="⛔ Falla de voltaje de referencia. Múltiples sensores pueden fallar.",
    ),
    627: SPNInfo(
        spn=627,
        name_en="Power Supply",
        name_es="Suministro de Energía",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.CRITICAL,
        description_es="Estado del suministro principal de energía.",
        action_es="⛔ Problema de suministro eléctrico. Verificar cableado.",
    ),
    629: SPNInfo(
        spn=629,
        name_en="Controller #1",
        name_es="Controlador #1 (ECU)",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.CRITICAL,
        description_es="Falla interna del módulo de control del motor.",
        action_es="⛔ ECU con falla interna. Puede requerir reprogramación o reemplazo.",
    ),
    639: SPNInfo(
        spn=639,
        name_en="J1939 Network #1",
        name_es="Red J1939 #1",
        system=DTCSystem.ELECTRICAL,
        severity=DTCSeverity.WARNING,
        description_es="Estado de la red de comunicación J1939.",
        action_es="🔧 Error de comunicación en red CAN. Verificar cableado y conectores.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # EXHAUST/EGR SPNs
    # ─────────────────────────────────────────────────────────────────────────
    27: SPNInfo(
        spn=27,
        name_en="EGR Valve Position",
        name_es="Posición de Válvula EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Posición de la válvula de recirculación de gases de escape.",
        action_es="🔧 Válvula EGR posiblemente atascada. Programar limpieza/servicio.",
    ),
    131: SPNInfo(
        spn=131,
        name_en="Engine Exhaust Back Pressure",
        name_es="Contrapresión de Escape",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Presión en el sistema de escape.",
        action_es="🔧 Contrapresión alta. Posible obstrucción en escape o DPF.",
    ),
    173: SPNInfo(
        spn=173,
        name_en="Engine Exhaust Gas Temperature",
        name_es="Temperatura de Gases de Escape",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de los gases de escape del motor.",
        action_es="🔧 Temperatura de escape fuera de rango. Verificar sistema de escape.",
    ),
    411: SPNInfo(
        spn=411,
        name_en="EGR Differential Pressure",
        name_es="Presión Diferencial EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Diferencia de presión en el sistema EGR.",
        action_es="🔧 Sistema EGR con flujo anormal. Verificar válvula y enfriador.",
    ),
    412: SPNInfo(
        spn=412,
        name_en="EGR Temperature",
        name_es="Temperatura EGR",
        system=DTCSystem.EXHAUST,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de los gases EGR.",
        action_es="🔧 Temperatura EGR fuera de rango. Verificar enfriador EGR.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # AFTERTREATMENT SPNs (DPF/SCR/DEF)
    # ─────────────────────────────────────────────────────────────────────────
    3216: SPNInfo(
        spn=3216,
        name_en="Aftertreatment #1 Intake NOx",
        name_es="NOx de Entrada Postratamiento",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Nivel de NOx entrando al sistema de postratamiento.",
        action_es="🔧 Niveles de NOx anormales. Verificar sistema de combustión.",
    ),
    3224: SPNInfo(
        spn=3224,
        name_en="Aftertreatment #1 Intake NOx Sensor",
        name_es="Sensor NOx de Entrada",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de NOx antes del catalizador SCR.",
        action_es="⛔ Sensor NOx con falla. Puede causar derating. Reemplazar.",
    ),
    3226: SPNInfo(
        spn=3226,
        name_en="Aftertreatment #1 Outlet NOx",
        name_es="NOx de Salida Postratamiento",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Nivel de NOx saliendo del sistema de postratamiento.",
        action_es="🔧 NOx alto en salida. Sistema SCR no está limpiando bien.",
    ),
    3234: SPNInfo(
        spn=3234,
        name_en="Aftertreatment #1 Outlet NOx Sensor",
        name_es="Sensor NOx de Salida",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Sensor de NOx después del catalizador SCR.",
        action_es="⛔ Sensor NOx de salida con falla. Reemplazo urgente.",
    ),
    3242: SPNInfo(
        spn=3242,
        name_en="DPF Intake Gas Temperature",
        name_es="Temperatura de Entrada al DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de gases entrando al filtro de partículas.",
        action_es="🔧 Temperatura de entrada al DPF fuera de rango.",
    ),
    3244: SPNInfo(
        spn=3244,
        name_en="DPF Outlet Gas Temperature",
        name_es="Temperatura de Salida del DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.WARNING,
        description_es="Temperatura de gases saliendo del filtro de partículas.",
        action_es="🔧 Temperatura de salida del DPF fuera de rango.",
    ),
    3251: SPNInfo(
        spn=3251,
        name_en="DPF Differential Pressure",
        name_es="Presión Diferencial del DPF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Diferencia de presión a través del filtro de partículas (DPF).",
        action_es="⛔ DPF posiblemente obstruido. Requiere regeneración o limpieza. Puede causar derating.",
    ),
    3360: SPNInfo(
        spn=3360,
        name_en="DEF Controller",
        name_es="Controlador de DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Unidad de control del sistema de dosificación DEF.",
        action_es="⛔ Controlador DEF con falla. Sistema SCR no funcionará. Derating inminente.",
    ),
    3361: SPNInfo(
        spn=3361,
        name_en="DEF Dosing Unit",
        name_es="Unidad de Dosificación DEF",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Bomba e inyector de DEF.",
        action_es="⛔ Unidad de dosificación DEF con falla. No inyecta DEF correctamente.",
    ),
    3364: SPNInfo(
        spn=3364,
        name_en="DEF Tank Quality",
        name_es="Calidad del DEF en Tanque",
        system=DTCSystem.AFTERTREATMENT,
        severity=DTCSeverity.CRITICAL,
        description_es="Calidad/concentración del líquido DEF en el tanque.",
        action_es="⛔ DEF contaminado o diluido. Drenar y rellenar con DEF certificado.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # VEHICLE SPEED/DISTANCE SPNs
    # ─────────────────────────────────────────────────────────────────────────
    84: SPNInfo(
        spn=84,
        name_en="Wheel-Based Vehicle Speed",
        name_es="Velocidad del Vehículo (Ruedas)",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.INFO,
        description_es="Velocidad del vehículo basada en sensores de rueda.",
        action_es="📋 Informativo. Error puede indicar problema de sensor.",
    ),
    244: SPNInfo(
        spn=244,
        name_en="Trip Distance",
        name_es="Distancia del Viaje",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.INFO,
        description_es="Distancia recorrida en el viaje actual.",
        action_es="📋 Informativo.",
    ),
    245: SPNInfo(
        spn=245,
        name_en="Total Vehicle Distance",
        name_es="Distancia Total del Vehículo",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.INFO,
        description_es="Odómetro total del vehículo.",
        action_es="📋 Informativo. Usar para programar mantenimiento.",
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # CRUISE CONTROL SPNs
    # ─────────────────────────────────────────────────────────────────────────
    86: SPNInfo(
        spn=86,
        name_en="Cruise Control Set Speed",
        name_es="Velocidad de Crucero Establecida",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Velocidad establecida en el control de crucero.",
        action_es="📋 Informativo.",
    ),
    595: SPNInfo(
        spn=595,
        name_en="Cruise Control Active",
        name_es="Control de Crucero Activo",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Estado de activación del control de crucero.",
        action_es="📋 Informativo.",
    ),
    596: SPNInfo(
        spn=596,
        name_en="Cruise Control Enable Switch",
        name_es="Interruptor de Control de Crucero",
        system=DTCSystem.ENGINE,
        severity=DTCSeverity.INFO,
        description_es="Estado del interruptor de habilitación del crucero.",
        action_es="📋 Error puede indicar problema de switch.",
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
    **WIALON_DETECTED_SPNS,
    **ADDITIONAL_SPNS,
}


# ═══════════════════════════════════════════════════════════════════════════════
# LOOKUP FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_spn_info(spn: int) -> Optional[SPNInfo]:
    """
    Get detailed information for a SPN code.
    🆕 v5.9.0: Falls back to J1939 complete database if not found in main DB

    Args:
        spn: Suspect Parameter Number

    Returns:
        SPNInfo if found, None otherwise
    """
    # First, try main database (curated, detailed info)
    spn_info = SPN_DATABASE.get(spn)

    if spn_info:
        return spn_info

    # Fallback to J1939 complete database (2000+ SPNs)
    try:
        from j1939_complete_spn_map import J1939_SPN_MAP

        j1939_data = J1939_SPN_MAP.get(spn)
        if j1939_data:
            # Create SPNInfo from J1939 complete data
            # Map category to system
            category = j1939_data.get("category", "unknown")
            system_map = {
                "engine_control": DTCSystem.ENGINE,
                "engine_performance": DTCSystem.ENGINE,
                "fuel_system": DTCSystem.FUEL,
                "fuel_quality": DTCSystem.FUEL,
                "lubrication": DTCSystem.ENGINE,
                "air_intake": DTCSystem.AIR_INTAKE,
                "exhaust_system": DTCSystem.EXHAUST,
                "aftertreatment": DTCSystem.AFTERTREATMENT,
                "transmission": DTCSystem.TRANSMISSION,
                "electrical_system": DTCSystem.ELECTRICAL,
                "cooling_system": DTCSystem.COOLING,
                "brakes": DTCSystem.BRAKES,
                "vehicle_dynamics": DTCSystem.CHASSIS,
            }
            system = system_map.get(category, DTCSystem.UNKNOWN)

            # Determine severity from priority
            priority = j1939_data.get("priority", "medium")
            severity = (
                DTCSeverity.CRITICAL
                if priority == "high"
                else DTCSeverity.WARNING if priority == "medium" else DTCSeverity.INFO
            )

            name = j1939_data.get("name", f"SPN {spn}")
            component = j1939_data.get("component", "Unknown")

            return SPNInfo(
                spn=spn,
                name_en=name,
                name_es=name,  # TODO: Add Spanish translation
                system=system,
                severity=severity,
                description_es=f"{component} - {name}",
                action_es=f"Revisar {component.lower()} en próxima mantención",
            )
    except (ImportError, Exception) as e:
        # J1939 complete database not available or error
        pass

    return None


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
