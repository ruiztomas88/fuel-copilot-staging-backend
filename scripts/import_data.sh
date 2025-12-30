#!/bin/bash
# Import database

echo "Importing fuel_metrics..."
mysql -u root fuel_copilot_local < fuel_metrics_utf8.sql

if [ $? -eq 0 ]; then
    echo "✅ fuel_metrics imported!"
    echo "Checking count..."
    mysql -u root fuel_copilot_local -e "SELECT COUNT(*) as total_records FROM fuel_metrics;"
else
    echo "❌ Import failed"
    exit 1
fi

echo "Importing refuel_events..."
iconv -f UTF-16LE -t UTF-8 refuel_events_30days.sql > refuel_events_utf8.sql
mysql -u root fuel_copilot_local < refuel_events_utf8.sql

if [ $? -eq 0 ]; then
    echo "✅ refuel_events imported!"
    mysql -u root fuel_copilot_local -e "SELECT COUNT(*) as total_refuels FROM refuel_events;"
else
    echo "❌ Refuel import failed"
fi

echo ""
echo "=== DATABASE SUMMARY ==="
mysql -u root fuel_copilot_local -e "
    SELECT 
        'fuel_metrics' as table_name,
        COUNT(*) as records,
        MIN(timestamp_utc) as earliest,
        MAX(timestamp_utc) as latest
    FROM fuel_metrics
    UNION ALL
    SELECT 
        'refuel_events',
        COUNT(*),
        MIN(timestamp_utc),
        MAX(timestamp_utc)
    FROM refuel_events;
"

echo "✅ Database import complete!"
