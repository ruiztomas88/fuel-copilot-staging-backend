"""Test directo de conexión MySQL"""
import os
import sys

# Configurar variables
os.environ['MYSQL_USER'] = 'fuel_admin'
os.environ['MYSQL_PASSWORD'] = 'FuelCopilot2025!'

print("=" * 60)
print("TEST DE CONEXIÓN MYSQL DIRECTO")
print("=" * 60)

print(f"\n1. Variables de entorno:")
print(f"   MYSQL_USER: {os.getenv('MYSQL_USER')}")
print(f"   MYSQL_PASSWORD: {'***' if os.getenv('MYSQL_PASSWORD') else 'NOT SET'}")

try:
    from config import DATABASE as DB
    print(f"\n2. Config importado:")
    print(f"   DB.USER: {DB.USER}")
    print(f"   DB.PASSWORD: {'***' if DB.PASSWORD else 'EMPTY!'}")
    print(f"   DB.HOST: {DB.HOST}")
    print(f"   DB.DATABASE: {DB.DATABASE}")
except Exception as e:
    print(f"\n❌ Error importando config: {e}")
    sys.exit(1)

try:
    from database_mysql import get_sqlalchemy_engine
    print(f"\n3. Creando engine SQLAlchemy...")
    engine = get_sqlalchemy_engine()
    print(f"   ✅ Engine creado: {engine}")
    
    from sqlalchemy import text
    print(f"\n4. Probando query...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM fuel_metrics WHERE truck_id='DO9693'"))
        count = result.fetchone()[0]
        print(f"   ✅ Registros de DO9693: {count}")
        
        result2 = conn.execute(text("""
            SELECT timestamp_utc, estimated_pct, mpg_current, rpm 
            FROM fuel_metrics 
            WHERE truck_id='DO9693' 
            ORDER BY timestamp_utc DESC 
            LIMIT 1
        """))
        row = result2.fetchone()
        if row:
            print(f"\n5. Último registro:")
            print(f"   Timestamp: {row[0]}")
            print(f"   Fuel: {row[1]}%")
            print(f"   MPG: {row[2]}")
            print(f"   RPM: {row[3]}")
        
    print(f"\n✅ CONEXIÓN MySQL EXITOSA")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
