#!/usr/bin/env python3
"""
Script para importar códigos SPN desde el sitio web de numeralkod.com
y actualizar dtc_database.py con descripciones en inglés y español
"""

import re
import sys
from typing import Dict, Tuple


def parse_spn_table() -> Dict[int, str]:
    """
    Parsea la tabla de SPNs desde el contenido del sitio web
    """
    # Contenido copiado del sitio web (formato: | SPN Code | Description |)
    spn_content = """
| 16 | Engine Fuel Filter (suction side) Differential Pressure |
| 18 | Engine Extended Range Fuel Pressure |
| 19 | Engine Extended Range Engine Oil Pressure |
| 20 | Engine Extended Range Engine Coolant Pressure |
| 21 | Engine ECU Temperature |
| 27 | EGR #1 Valve Position |
| 28 | Accelerator Pedal Position #3 |
| 29 | Accelerator Pedal Position #2 |
| 51 | Engine Throttle Position |
| 52 | Engine Intercooler Temperature |
| 84 | Wheel-Based Vehicle Speed |
| 91 | Accelerator Pedal Position #1 |
| 92 | Engine Percent Load At Current Speed |
| 94 | Engine Fuel Delivery Pressure |
| 95 | Engine Fuel Filter Differential Pressure |
| 96 | Fuel Level |
| 97 | Water In Fuel Indicator |
| 98 | Engine Oil Level |
| 99 | Engine Oil Filter Differential Pressure |
| 100 | Engine Oil Pressure |
| 101 | Engine Crankcase Pressure |
| 102 | Engine Intake Manifold #1 Pressure |
| 105 | Engine Intake Manifold #1 Temperature |
| 106 | Engine Air Inlet Pressure |
| 107 | Engine Air Filter 1 Differential Pressure |
| 108 | Barometric Pressure |
| 110 | Engine Coolant Temperature |
| 111 | Engine Coolant Level |
| 131 | Engine Exhaust Back Pressure |
| 158 | Keyswitch Battery Potential |
| 167 | Charging System Potential |
| 168 | Battery Potential / Power Input #1 |
| 171 | Ambient Air Temperature |
| 172 | Engine Air Inlet Temperature |
| 173 | Engine Exhaust Gas Temperature |
| 174 | Engine Fuel Temperature 1 |
| 175 | Engine Oil Temperature 1 |
| 177 | Transmission Oil Temperature |
| 183 | Engine Fuel Rate |
| 190 | Engine Speed |
| 247 | Engine Total Hours of Operation |
| 250 | Engine Total Fuel Used |
| 411 | Engine Exhaust Gas Recirculation Differential Pressure |
| 412 | Engine Exhaust Gas Recirculation Temperature |
| 512 | Driver's Demand Engine – Percent Torque |
| 513 | Actual Engine – Percent Torque |
| 544 | Engine Reference Torque |
| 636 | Engine Position Sensor |
| 637 | Engine Timing Sensor |
| 639 | J1939 Network #1 |
| 651 | Engine Injector Cylinder #01 |
| 652 | Engine Injector Cylinder #02 |
| 653 | Engine Injector Cylinder #03 |
| 654 | Engine Injector Cylinder #04 |
| 655 | Engine Injector Cylinder #05 |
| 656 | Engine Injector Cylinder #06 |
| 657 | Engine Injector Cylinder #07 |
| 658 | Engine Injector Cylinder #08 |
| 723 | Engine Speed Sensor #2 |
| 1127 | Engine Turbocharger 1 Boost Pressure |
| 1172 | Engine Turbocharger 1 Turbine Inlet Temperature |
| 1761 | Aftertreatment 1 Diesel Exhaust Fluid Tank Level |
| 3031 | Aftertreatment 1 Diesel Exhaust Fluid Tank Temperature |
| 3216 | Aftertreatment #1 Intake NOx |
| 3217 | Aftertreatment #1 Intake O2 |
| 3226 | Aftertreatment #1 Outlet NOx |
| 3227 | Aftertreatment #1 Outlet O2 |
| 3245 | Aftertreatment #1 Diesel Particulate Filter Differential Pressure |
| 3246 | Aftertreatment #1 Diesel Particulate Filter Intake Gas Temperature |
| 3247 | Aftertreatment #1 Diesel Particulate Filter Outlet Gas Temperature |
| 3361 | Aftertreatment 1 Diesel Exhaust Fluid Dosing Unit |
| 3363 | Aftertreatment 1 Diesel Exhaust Fluid Tank Heater |
| 3364 | Aftertreatment 1 Diesel Exhaust Fluid Tank Quality |
| 3516 | Aftertreatment 1 Diesel Exhaust Fluid Concentration |
| 3610 | Aftertreatment #1 Diesel Particulate Filter Soot Load |
| 3700 | DPF Active Regeneration Status |
| 3719 | Particulate Trap #1 Soot Load Percent |
| 3720 | Particulate Trap #1 Ash Load Percent |
| 4076 | Aftertreatment #1 Fuel Pressure #1 |
| 4331 | Aftertreatment 1 Diesel Exhaust Fluid Actual Dosing Quantity |
| 4334 | Aftertreatment 1 Diesel Exhaust Fluid Doser Absolute Pressure |
| 4358 | Aftertreatment #1 SCR Catalyst Exhaust Gas Differential Pressure |
| 4360 | Aftertreatment #1 SCR Catalyst Intake Gas Temperature |
| 4363 | Aftertreatment #1 SCR Catalyst Outlet Gas Temperature |
| 4364 | Aftertreatment #1 SCR Catalyst Conversion Efficiency |
| 4765 | Aftertreatment #1 Diesel Oxidation Catalyst Intake Gas Temperature |
| 4766 | Aftertreatment #1 Diesel Oxidation Catalyst Outlet Gas Temperature |
| 4767 | Aftertreatment #1 Diesel Oxidation Catalyst Differential Pressure |
| 5394 | Aftertreatment 1 Diesel Exhaust Fluid Dosing Valve 1 |
| 5444 | Aftertreatment 1 Diesel Exhaust Fluid Quality |
| 5829 | Engine NOx Level |
| 5837 | Fuel Type |
| 5963 | Aftertreatment 1 Total Diesel Exhaust Fluid Used |
"""

    spn_data = {}

    # Pattern: | número | descripción |
    pattern = r"\|\s*(\d+)\s*\|\s*([^|]+)\s*\|"

    for match in re.finditer(pattern, spn_content):
        spn = int(match.group(1))
        desc = match.group(2).strip()
        spn_data[spn] = desc

    return spn_data


def translate_to_spanish(english_desc: str) -> Tuple[str, str]:
    """
    Traduce descripciones de inglés a español (versión simplificada)
    Retorna (nombre_es, descripcion_es)
    """
    translations = {
        # Engine / Motor
        "Engine": "Motor",
        "Fuel": "Combustible",
        "Filter": "Filtro",
        "Pressure": "Presión",
        "Temperature": "Temperatura",
        "Oil": "Aceite",
        "Coolant": "Refrigerante",
        "Exhaust": "Escape",
        "Gas": "Gases",
        "Intake": "Admisión",
        "Air": "Aire",
        "Turbocharger": "Turbocompresor",
        "Throttle": "Acelerador",
        "Injector": "Inyector",
        "Cylinder": "Cilindro",
        "Speed": "Velocidad",
        "Load": "Carga",
        "Level": "Nivel",
        "Differential": "Diferencial",
        "Manifold": "Colector",
        "Battery": "Batería",
        "Potential": "Voltaje",
        "Sensor": "Sensor",
        "Position": "Posición",
        "Pedal": "Pedal",
        "Accelerator": "Acelerador",
        "Water": "Agua",
        "Indicator": "Indicador",
        "Total": "Total",
        "Hours": "Horas",
        "Operation": "Operación",
        "Used": "Utilizado",
        "Rate": "Caudal",
        # Aftertreatment / Sistema de tratamiento de gases
        "Aftertreatment": "Sistema de Postratamiento",
        "Diesel Particulate Filter": "Filtro de Partículas Diésel",
        "DPF": "Filtro DPF",
        "Diesel Exhaust Fluid": "Fluido DEF",
        "DEF": "DEF",
        "SCR Catalyst": "Catalizador SCR",
        "SCR": "SCR",
        "Diesel Oxidation Catalyst": "Catalizador de Oxidación Diésel",
        "Soot": "Hollín",
        "Ash": "Ceniza",
        "NOx": "NOx",
        "Regeneration": "Regeneración",
        "Active": "Activa",
        "Status": "Estado",
        "Dosing": "Dosificación",
        "Tank": "Tanque",
        "Quality": "Calidad",
        "Concentration": "Concentración",
        "Heater": "Calentador",
        "Unit": "Unidad",
        "Valve": "Válvula",
        "Outlet": "Salida",
        "Conversion": "Conversión",
        "Efficiency": "Eficiencia",
        "Actual": "Real",
        "Quantity": "Cantidad",
    }

    spanish = english_desc
    for eng, spa in translations.items():
        spanish = re.sub(r"\b" + eng + r"\b", spa, spanish, flags=re.IGNORECASE)

    # Nombre corto (primeras 60 caracteres)
    nombre_corto = spanish[:60]

    return nombre_corto, spanish


def generate_dtc_database_entries(spn_data: Dict[int, str]) -> str:
    """
    Genera entradas de Python para dtc_database.py
    """
    output = []
    output.append("# =============================================")
    output.append(f"# SPNs importados desde numeralkod.com ({len(spn_data)} códigos)")
    output.append("# =============================================\n")

    # Categorizar por sistema
    engine_spns = []
    aftertreatment_spns = []
    other_spns = []

    for spn, desc_en in sorted(spn_data.items()):
        if (
            "aftertreatment" in desc_en.lower()
            or "def" in desc_en.lower()
            or "scr" in desc_en.lower()
            or "dpf" in desc_en.lower()
        ):
            aftertreatment_spns.append((spn, desc_en))
        elif "engine" in desc_en.lower():
            engine_spns.append((spn, desc_en))
        else:
            other_spns.append((spn, desc_en))

    # Generar entradas por categoría
    for category, spn_list in [
        ("MOTOR / ENGINE", engine_spns),
        ("SISTEMA DE POSTRATAMIENTO / AFTERTREATMENT", aftertreatment_spns),
        ("OTROS SISTEMAS / OTHER SYSTEMS", other_spns),
    ]:
        if spn_list:
            output.append(f"\n    # {category}")
            output.append("    # " + "=" * 70)

            for spn, desc_en in spn_list:
                nombre_es, desc_es = translate_to_spanish(desc_en)

                # Determinar sistema
                if "aftertreatment" in desc_en.lower() or "def" in desc_en.lower():
                    system = "DTCSystem.AFTERTREATMENT"
                    severity = "DTCSeverity.WARNING"
                elif "engine" in desc_en.lower():
                    system = "DTCSystem.ENGINE"
                    severity = "DTCSeverity.WARNING"
                elif "fuel" in desc_en.lower():
                    system = "DTCSystem.FUEL"
                    severity = "DTCSeverity.WARNING"
                else:
                    system = "DTCSystem.OTHER"
                    severity = "DTCSeverity.INFO"

                output.append(
                    f"""
    {spn}: SPNInfo(
        spn={spn},
        name_en="{desc_en}",
        name_es="{nombre_es}",
        system={system},
        severity={severity},
        description_es="{desc_es}",
        action_es="Verificar sensor/actuador según código FMI. Consultar manual de servicio."
    ),"""
                )

    return "\n".join(output)


def main():
    print("🌐 Importando códigos SPN desde numeralkod.com...")

    # Parsear SPNs
    spn_data = parse_spn_table()
    print(f"✅ Parseados {len(spn_data)} códigos SPN")

    # Generar código Python
    python_code = generate_dtc_database_entries(spn_data)

    # Guardar en archivo
    output_file = "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/spn_imports.py"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(python_code)

    print(f"💾 Código generado en: {output_file}")
    print("\n📊 Estadísticas:")
    print(f"   - Total SPNs: {len(spn_data)}")
    print(f"   - Rango: {min(spn_data.keys())} - {max(spn_data.keys())}")

    # Mostrar algunos ejemplos
    print("\n📋 Ejemplos de códigos importados:")
    for spn in sorted(list(spn_data.keys()))[:10]:
        print(f"   SPN {spn}: {spn_data[spn]}")

    print("\n✅ Listo! Ahora puedes:")
    print("   1. Revisar spn_imports.py")
    print("   2. Copiar las entradas relevantes a dtc_database.py")
    print("   3. Ajustar severidades y descripciones en español según sea necesario")


if __name__ == "__main__":
    main()
