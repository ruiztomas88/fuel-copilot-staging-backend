"""
🔍 DIAGNÓSTICO: RA9250 OFFLINE EN FRONTEND
Verifica por qué aparece offline cuando Wialon lo muestra como MOVING
"""
import mysql.connector
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

def diagnose_ra9250():
    """Analiza el estado de RA9250 en la base de datos"""
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "fuel_admin"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "fuel_copilot"),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )
    
    cursor = conn.cursor(dictionary=True)
    truck_id = "RA9250"
    
    print(f"🔍 DIAGNÓSTICO: {truck_id}")
    print("="*80)
    
    # 1. Verificar si existe en tabla trucks
    cursor.execute("SELECT * FROM trucks WHERE id = %s", (truck_id,))
    truck = cursor.fetchone()
    
    if not truck:
        print(f"\n❌ ERROR: {truck_id} NO EXISTE en tabla trucks")
        print("   → Necesita agregarse a la base de datos")
        cursor.close()
        conn.close()
        return
    
    print(f"\n✅ Truck encontrado en DB:")
    print(f"   ID: {truck['id']}")
    print(f"   Tank: {truck['tank_capacity_gal']:.1f} gal")
    
    # 2. Último registro en fuel_metrics
    cursor.execute("""
        SELECT 
            timestamp_utc,
            truck_status,
            speed_mph,
            rpm,
            fuel_rate_lh,
            fuel_lvl,
            TIMESTAMPDIFF(MINUTE, timestamp_utc, NOW()) as age_minutes
        FROM fuel_metrics
        WHERE truck_id = %s
        ORDER BY timestamp_utc DESC
        LIMIT 1
    """, (truck_id,))
    
    latest = cursor.fetchone()
    
    if not latest:
        print(f"\n❌ ERROR: NO HAY DATOS en fuel_metrics para {truck_id}")
        print("   → El truck no se está sincronizando desde Wialon")
        print("   → Verificar que wialon_sync_enhanced.py esté procesando este truck")
        cursor.close()
        conn.close()
        return
    
    print(f"\n📊 ÚLTIMO REGISTRO en fuel_metrics:")
    print(f"   Timestamp: {latest['timestamp_utc']} UTC")
    print(f"   Edad: {latest['age_minutes']} minutos")
    print(f"   Status: {latest['truck_status']}")
    print(f"   Speed: {latest['speed_mph']} mph")
    print(f"   RPM: {latest['rpm']}")
    print(f"   Fuel Rate: {latest['fuel_rate_lh']} L/h")
    print(f"   Fuel Level: {latest['fuel_lvl']}%")
    
    # 3. Diagnóstico del problema
    age_min = latest['age_minutes']
    status = latest['truck_status']
    
    print(f"\n🔬 ANÁLISIS:")
    
    if age_min > 15:
        print(f"   ❌ PROBLEMA IDENTIFICADO: Data age = {age_min} min > 15 min")
        print(f"      → Backend marca como OFFLINE si data age > 15 min")
        print(f"      → Último mensaje recibido hace {age_min} minutos")
        print(f"\n   🔧 POSIBLES CAUSAS:")
        print(f"      1. Wialon sync detenido o con errores")
        print(f"      2. Truck no está enviando datos a Wialon")
        print(f"      3. Timestamp del GPS está desactualizado")
        print(f"      4. Filtro de trucks en wialon_sync excluyendo RA9250")
    elif status == "OFFLINE":
        print(f"   ❌ PROBLEMA: Status guardado como OFFLINE en DB")
        print(f"      → Data age = {age_min} min (OK)")
        print(f"      → Pero status = OFFLINE en fuel_metrics")
        print(f"\n   🔧 REVISAR:")
        print(f"      - determine_truck_status() está marcando incorrectamente")
        print(f"      - Speed: {latest['speed_mph']} mph")
        print(f"      - RPM: {latest['rpm']}")
    else:
        print(f"   ✅ Status en DB: {status}")
        print(f"   ✅ Data age: {age_min} min (< 15 min)")
        print(f"   ℹ️  El problema puede estar en el FRONTEND o en la API")
        print(f"\n   🔧 VERIFICAR:")
        print(f"      1. Endpoint /api/fleet está devolviendo status correcto")
        print(f"      2. Frontend está parseando correctamente el status")
        print(f"      3. Cache del frontend no está desactualizado")
    
    # 4. Últimos 10 registros para ver patrón
    cursor.execute("""
        SELECT 
            timestamp_utc,
            truck_status,
            speed_mph,
            rpm,
            TIMESTAMPDIFF(MINUTE, timestamp_utc, NOW()) as age_minutes
        FROM fuel_metrics
        WHERE truck_id = %s
        ORDER BY timestamp_utc DESC
        LIMIT 10
    """, (truck_id,))
    
    history = cursor.fetchall()
    
    print(f"\n📜 ÚLTIMOS 10 REGISTROS:")
    print(f"{'Timestamp':<20} {'Status':<10} {'Speed':>7} {'RPM':>6} {'Age':>8}")
    print("-"*80)
    for row in history:
        print(f"{str(row['timestamp_utc']):<20} {row['truck_status']:<10} "
              f"{row['speed_mph']:>7.1f} {row['rpm']:>6} {row['age_minutes']:>6} min")
    
    # 5. Verificar logs de wialon_sync
    print(f"\n🔍 SIGUIENTE PASO:")
    print(f"   En el VM, verificar logs de wialon_sync:")
    print(f"   Get-Content logs\\wialon-stdout.log -Tail 100 | Select-String '{truck_id}'")
    print(f"\n   Buscar:")
    print(f"   - ✅ Mensajes de procesamiento de {truck_id}")
    print(f"   - ❌ Errores al procesar {truck_id}")
    print(f"   - ⏱️  Timestamp de los mensajes vs NOW()")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        diagnose_ra9250()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
