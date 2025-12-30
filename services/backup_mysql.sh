#!/bin/bash
# ============================================================================
# MySQL Database Backup Script
# Runs every 6 hours via cron
# Keeps last 7 days of backups (4 backups per day = 28 total)
# ============================================================================

BACKUP_DIR="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="fuel_copilot_local"
DB_USER="root"
DB_PASS=""
RETENTION_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup filename with timestamp
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  MySQL Backup - Fuel Analytics                            ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')                              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "🗄️  Database: $DB_NAME"
echo "📦 Backup file: $BACKUP_FILE"

# Perform backup
if [ -z "$DB_PASS" ]; then
    mysqldump -u "$DB_USER" "$DB_NAME" > "$BACKUP_FILE" 2>/dev/null
else
    mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$BACKUP_FILE" 2>/dev/null
fi

# Check if backup was successful
if [ $? -eq 0 ]; then
    # Compress backup
    gzip "$BACKUP_FILE"
    COMPRESSED_FILE="${BACKUP_FILE}.gz"
    SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
    
    echo "✅ Backup completado: $SIZE"
    echo ""
    
    # Delete old backups (older than RETENTION_DAYS)
    echo "🧹 Limpiando backups antiguos (mayores a $RETENTION_DAYS días)..."
    find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +$RETENTION_DAYS -delete
    
    # Count remaining backups
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" | wc -l)
    echo "📊 Total backups disponibles: $BACKUP_COUNT"
    
    # Log backup to file
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup successful: $COMPRESSED_FILE ($SIZE)" >> "$BACKUP_DIR/backup.log"
else
    echo "❌ Error al crear backup"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Backup FAILED" >> "$BACKUP_DIR/backup.log"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
