
# ============================================================================
# TRUCK SPECS ENDPOINTS - MPG Baselines & Fleet Comparison
# ============================================================================
@app.get("/api/v2/truck-specs", tags=["Truck Specs"])
async def get_all_truck_specs():
    """Get all truck specifications with MPG baselines"""
    try:
        import pymysql
        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT truck_id, vin, make, model, year, engine_model, 
                   mpg_loaded, mpg_empty, last_updated
            FROM truck_specs
            ORDER BY make, model, year DESC
        """)

        specs = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"truck_specs": specs, "total": len(specs)}
    except Exception as e:
        logger.error(f"Error fetching truck specs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/fleet/specs-summary", tags=["Truck Specs"])
async def get_fleet_specs_summary():
    """Get fleet-wide MPG baseline summary grouped by make/model"""
    try:
        import pymysql
        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT 
                make,
                model,
                COUNT(*) as truck_count,
                AVG(mpg_loaded) as avg_mpg_loaded,
                AVG(mpg_empty) as avg_mpg_empty,
                MIN(year) as oldest_year,
                MAX(year) as newest_year
            FROM truck_specs
            GROUP BY make, model
            ORDER BY make, model
        """)

        summary = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format year_range
        for row in summary:
            if row['oldest_year'] and row['newest_year']:
                if row['oldest_year'] == row['newest_year']:
                    row['year_range'] = str(row['oldest_year'])
                else:
                    row['year_range'] = f"{row['oldest_year']}-{row['newest_year']}"

        return {"fleet_summary": summary, "total_groups": len(summary)}
    except Exception as e:
        logger.error(f"Error fetching fleet specs summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

