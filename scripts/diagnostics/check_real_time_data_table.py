"""
Verificar si la tabla real_time_data existe
"""
from database_mysql import get_sqlalchemy_engine
from sqlalchemy import text

engine = get_sqlalchemy_engine()

with engine.connect() as conn:
    # Ver todas las tablas
    result = conn.execute(text("SHOW TABLES"))
    tables = [row[0] for row in result]
    
    print("Tablas en la base de datos:")
    for table in sorted(tables):
        print(f"   - {table}")
    
    # Buscar real_time_data
    if "real_time_data" in tables:
        print("\n✅ real_time_data EXISTE")
        
        # Ver columnas
        result = conn.execute(text("DESCRIBE real_time_data"))
        print("\nColumnas de real_time_data:")
        for row in result:
            print(f"   - {row[0]} ({row[1]})")
    else:
        print("\n❌ real_time_data NO EXISTE")
        print("\n🔍 Puede ser que se refiera a fuel_metrics o fuel_monitoring")
