"""
🔍 DIAGNÓSTICO DE REFUELS PERDIDOS
Analiza los últimos 7 días para identificar refuels no detectados
"""
import mysql.connector
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

def analyze_missed_refuels():
    """
    Busca patrones de fuel jumps que debieron detectarse como refuels pero no lo fueron
    """
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "fuel_admin"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "fuel_copilot"),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )
    
    cursor = conn.cursor(dictionary=True)
    
    # Buscar jumps significativos en fuel_metrics (últimos 7 días)
    print("🔍 BUSCANDO FUEL JUMPS NO DETECTADOS (últimos 7 días)...\n")
    
    query = """
    WITH fuel_changes AS (
        SELECT 
            fm.truck_id,
            fm.timestamp_utc,
            fm.fuel_lvl,
            LAG(fm.fuel_lvl) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as prev_fuel_lvl,
            LAG(fm.timestamp_utc) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as prev_timestamp,
            t.tank_capacity_gal,
            fm.fuel_lvl - LAG(fm.fuel_lvl) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc) as jump_pct,
            TIMESTAMPDIFF(MINUTE, 
                LAG(fm.timestamp_utc) OVER (PARTITION BY fm.truck_id ORDER BY fm.timestamp_utc),
                fm.timestamp_utc
            ) as gap_minutes
        FROM fuel_metrics fm
        JOIN trucks t ON fm.truck_id = t.id
        WHERE fm.timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    )
    SELECT 
        truck_id,
        timestamp_utc,
        prev_fuel_lvl,
        fuel_lvl,
        jump_pct,
        (jump_pct / 100) * tank_capacity_gal as jump_gal,
        gap_minutes,
        tank_capacity_gal
    FROM fuel_changes
    WHERE jump_pct >= 10  -- Salto de al menos 10%
        AND gap_minutes >= 5  -- Gap de al menos 5 minutos
        AND gap_minutes <= 5760  -- Menos de 4 días (96 horas)
        AND (jump_pct / 100) * tank_capacity_gal >= 5  -- Al menos 5 galones
    ORDER BY timestamp_utc DESC
    LIMIT 50;
    """
    
    cursor.execute(query)
    potential_refuels = cursor.fetchall()
    
    print(f"📊 Encontrados {len(potential_refuels)} FUEL JUMPS potenciales:\n")
    print("="*100)
    
    for event in potential_refuels:
        # Verificar si existe en refuel_events
        check_query = """
        SELECT COUNT(*) as count 
        FROM refuel_events 
        WHERE truck_id = %s 
        AND ABS(TIMESTAMPDIFF(MINUTE, timestamp_utc, %s)) <= 30
        """
        cursor.execute(check_query, (event['truck_id'], event['timestamp_utc']))
        result = cursor.fetchone()
        
        is_recorded = result['count'] > 0
        status = "✅ REGISTRADO" if is_recorded else "❌ PERDIDO"
        
        print(f"{status} | {event['truck_id']} | {event['timestamp_utc']}")
        print(f"   Jump: {event['prev_fuel_lvl']:.1f}% → {event['fuel_lvl']:.1f}% "
              f"(+{event['jump_pct']:.1f}%, +{event['jump_gal']:.1f} gal)")
        print(f"   Gap: {event['gap_minutes']:.0f} min ({event['gap_minutes']/60:.1f} h)")
        print(f"   Tank: {event['tank_capacity_gal']:.0f} gal")
        
        if not is_recorded:
            print("   🔥 REFUEL NO DETECTADO - ANALIZAR")
        
        print("-"*100)
    
    # Estadísticas
    missed = sum(1 for e in potential_refuels if not is_recorded_refuel(cursor, e))
    detected = len(potential_refuels) - missed
    
    print("\n📊 RESUMEN:")
    print(f"   Total fuel jumps: {len(potential_refuels)}")
    print(f"   ✅ Detectados: {detected}")
    print(f"   ❌ Perdidos: {missed}")
    
    if missed > 0:
        print(f"\n⚠️  TASA DE PÉRDIDA: {missed/len(potential_refuels)*100:.1f}%")
        print("\n🔧 POSIBLES CAUSAS:")
        print("   1. MIN_REFUEL_JUMP_PCT muy alto (actual: 10%)")
        print("   2. MIN_REFUEL_GALLONS muy alto (actual: 5 gal)")
        print("   3. MAX_REFUEL_GAP_HOURS muy bajo (actual: 96h)")
        print("   4. Tank nearly full rejection (>95% y <10% y <15 gal)")
        print("   5. Kalman vs Sensor discrepancy")
    
    cursor.close()
    conn.close()

def is_recorded_refuel(cursor, event):
    """Check if refuel exists in refuel_events table"""
    query = """
    SELECT COUNT(*) as count 
    FROM refuel_events 
    WHERE truck_id = %s 
    AND ABS(TIMESTAMPDIFF(MINUTE, timestamp_utc, %s)) <= 30
    """
    cursor.execute(query, (event['truck_id'], event['timestamp_utc']))
    result = cursor.fetchone()
    return result['count'] > 0

if __name__ == "__main__":
    try:
        analyze_missed_refuels()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
