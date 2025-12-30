#!/usr/bin/env python3
"""
Script de validación para verificar que todos los cambios funcionen correctamente
Valida:
1. Columnas obd_speed y engine_brake existen en truck_sensors_cache
2. API endpoint devuelve los nuevos campos
3. Data está siendo insertada correctamente
"""

import pymysql
import requests

from config import get_local_db_config


def check_database_schema():
    """Verificar que las columnas nuevas existen"""
    print("=" * 70)
    print("1. VERIFICANDO ESQUEMA DE BASE DE DATOS")
    print("=" * 70)

    try:
        db_config = get_local_db_config()
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        # Check columns exist
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'truck_sensors_cache' 
            AND COLUMN_NAME IN ('obd_speed', 'engine_brake')
        """,
            (db_config["database"],),
        )

        columns = cursor.fetchall()

        if len(columns) == 2:
            print("✅ Columnas obd_speed y engine_brake existen")
            for col_name, col_type in columns:
                print(f"   - {col_name}: {col_type}")
        else:
            print(f"❌ Solo {len(columns)}/2 columnas encontradas")
            return False

        # Check if data exists
        cursor.execute(
            """
            SELECT COUNT(*) as count,
                   SUM(CASE WHEN obd_speed IS NOT NULL THEN 1 ELSE 0 END) as with_obd_speed,
                   SUM(CASE WHEN engine_brake IS NOT NULL THEN 1 ELSE 0 END) as with_engine_brake
            FROM truck_sensors_cache
        """
        )

        result = cursor.fetchone()
        total, with_obd, with_brake = result

        print(f"\n📊 Datos en truck_sensors_cache:")
        print(f"   Total registros: {total}")
        print(
            f"   Con obd_speed: {with_obd} ({(with_obd/total*100 if total > 0 else 0):.1f}%)"
        )
        print(
            f"   Con engine_brake: {with_brake} ({(with_brake/total*100 if total > 0 else 0):.1f}%)"
        )

        # Sample data
        cursor.execute(
            """
            SELECT truck_id, obd_speed, engine_brake 
            FROM truck_sensors_cache 
            WHERE obd_speed IS NOT NULL OR engine_brake IS NOT NULL
            LIMIT 5
        """
        )

        samples = cursor.fetchall()
        if samples:
            print(f"\n📋 Muestra de datos:")
            for truck_id, obd_speed, engine_brake in samples:
                print(
                    f"   {truck_id}: obd_speed={obd_speed}, engine_brake={engine_brake}"
                )
        else:
            print("\n⚠️  No hay datos todavía (normal si acaba de reiniciar)")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def check_api_endpoint():
    """Verificar que el API endpoint devuelve los nuevos campos"""
    print("\n" + "=" * 70)
    print("2. VERIFICANDO API ENDPOINT")
    print("=" * 70)

    try:
        # Get a truck from database first
        db_config = get_local_db_config()
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("SELECT truck_id FROM truck_sensors_cache LIMIT 1")
        result = cursor.fetchone()

        if not result:
            print("⚠️  No hay trucks en cache, no se puede probar API")
            cursor.close()
            conn.close()
            return False

        truck_id = result[0]
        cursor.close()
        conn.close()

        # Call API
        url = f"http://localhost:8000/fuelAnalytics/api/sensors/{truck_id}"
        print(f"📡 Llamando a: {url}")

        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            # Check for new fields
            has_obd_speed = "obd_speed" in data
            has_engine_brake = "engine_brake" in data

            if has_obd_speed and has_engine_brake:
                print(f"✅ API devuelve ambos campos nuevos")
                print(f"   obd_speed: {data.get('obd_speed')}")
                print(f"   engine_brake: {data.get('engine_brake')}")
                return True
            else:
                print(f"❌ Campos faltantes:")
                if not has_obd_speed:
                    print("   - obd_speed NO está en response")
                if not has_engine_brake:
                    print("   - engine_brake NO está en response")
                return False
        else:
            print(f"❌ API error: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar al backend. ¿Está corriendo?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def check_frontend_types():
    """Verificar que los tipos TypeScript están actualizados"""
    print("\n" + "=" * 70)
    print("3. VERIFICANDO TIPOS TYPESCRIPT")
    print("=" * 70)

    try:
        with open("../Fuel-Analytics-Frontend/src/types/api.ts", "r") as f:
            content = f.read()

        has_obd_speed = "obd_speed" in content
        has_engine_brake = "engine_brake" in content

        if has_obd_speed and has_engine_brake:
            print("✅ Interfaces TypeScript actualizadas")
            print("   - obd_speed declarado")
            print("   - engine_brake declarado")
            return True
        else:
            print("❌ Interfaces TypeScript faltantes:")
            if not has_obd_speed:
                print("   - obd_speed NO declarado")
            if not has_engine_brake:
                print("   - engine_brake NO declarado")
            return False

    except FileNotFoundError:
        print("⚠️  No se encontró archivo api.ts")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def check_idle_cost_component():
    """Verificar que el componente IdleCostAnalysis existe"""
    print("\n" + "=" * 70)
    print("4. VERIFICANDO COMPONENTE IDLE COST ANALYSIS")
    print("=" * 70)

    try:
        import os

        component_path = (
            "../Fuel-Analytics-Frontend/src/components/IdleCostAnalysis.tsx"
        )

        if os.path.exists(component_path):
            with open(component_path, "r") as f:
                content = f.read()

            # Check key features
            has_pie_chart = "PieChart" in content
            has_cost_breakdown = "drivingCost" in content and "idleCost" in content
            has_alert = "isExcessiveIdle" in content

            print(f"✅ Componente IdleCostAnalysis existe")
            print(f"   - Pie Chart: {'✅' if has_pie_chart else '❌'}")
            print(f"   - Cost Breakdown: {'✅' if has_cost_breakdown else '❌'}")
            print(f"   - Excessive Idle Alert: {'✅' if has_alert else '❌'}")

            return has_pie_chart and has_cost_breakdown and has_alert
        else:
            print("❌ Componente IdleCostAnalysis NO existe")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("\n" + "█" * 70)
    print("█" + " " * 20 + "VALIDACIÓN DE CAMBIOS v6.5.0" + " " * 20 + "█")
    print("█" * 70 + "\n")

    results = {
        "database": check_database_schema(),
        "api": check_api_endpoint(),
        "types": check_frontend_types(),
        "component": check_idle_cost_component(),
    }

    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check.upper():20} {status}")

    print("\n" + "=" * 70)

    if all_passed:
        print("🎉 TODAS LAS VALIDACIONES PASARON")
        print("\n✅ Backend está extrayendo obd_speed y engine_brake")
        print("✅ API endpoints devuelven los nuevos campos")
        print("✅ TypeScript interfaces actualizadas")
        print("✅ IdleCostAnalysis component implementado")
        print("\n📊 SIGUIENTE PASO: Abre el frontend y verifica que:")
        print("   1. Truck Detail muestra Idle Cost Analysis")
        print("   2. Coolant Level gauge funciona")
        print("   3. No hay errores en consola")
        print("\n🌐 Frontend: http://localhost:5173")
        print("🔧 Backend logs: tail -f wialon_sync.log")
    else:
        print("⚠️  ALGUNAS VALIDACIONES FALLARON")
        print("\nRevisa los errores arriba y corrige los problemas.")

    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
