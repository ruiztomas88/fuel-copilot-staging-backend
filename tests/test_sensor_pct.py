from sqlalchemy import text

from database_mysql import get_sqlalchemy_engine

engine = get_sqlalchemy_engine()
with engine.connect() as conn:
    result = conn.execute(
        text(
            """
        SELECT truck_id, sensor_pct, estimated_pct, drift_pct, mpg_current
        FROM fuel_metrics 
        WHERE truck_id='LC6799' 
        ORDER BY timestamp_utc DESC 
        LIMIT 1
    """
        )
    ).fetchone()
    if result:
        print(
            f"truck_id={result[0]}, sensor_pct={result[1]}, estimated_pct={result[2]}, drift={result[3]}, mpg={result[4]}"
        )
    else:
        print("No data found")
