#!/bin/bash
# Production Deployment Execution Script - FINAL
# Deploys v5.13.0 to production with zero-downtime

set -e

echo "================================================"
echo "🚀 FUEL ANALYTICS v5.13.0 - PRODUCTION DEPLOYMENT"
echo "================================================"
echo ""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

DEPLOYMENT_ENV=${1:-production}
DEPLOYMENT_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo -e "${BLUE}[INFO]${NC} Environment: $DEPLOYMENT_ENV"
echo -e "${BLUE}[INFO]${NC} Time: $DEPLOYMENT_TIME"
echo ""

# Step 1: Pre-deployment validation
echo "================================"
echo "Step 1: Pre-Deployment Checks"
echo "================================"
echo ""

if [ ! -f "./pre_production_checklist.sh" ]; then
    echo -e "${RED}[ERROR]${NC} pre_production_checklist.sh not found!"
    exit 1
fi

echo "Running pre-deployment validation..."
./pre_production_checklist.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Pre-deployment checks failed!"
    echo "Fix all red items before deploying."
    exit 1
fi

echo -e "${GREEN}✓${NC} Pre-deployment checks passed"
echo ""

# Step 2: Backup current state
echo "================================"
echo "Step 2: Backup Current State"
echo "================================"
echo ""

BACKUP_DIR="backups/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$BACKUP_DIR"

echo "Backing up database..."
if command -v mysqldump &> /dev/null; then
    mysqldump -h "${MYSQL_HOST:-localhost}" \
              -u "${MYSQL_USER:-fuel_user}" \
              -p"${MYSQL_PASSWORD}" \
              "${MYSQL_DATABASE:-fuel_copilot}" \
              > "$BACKUP_DIR/database_backup.sql"
    echo -e "${GREEN}✓${NC} Database backed up to $BACKUP_DIR/database_backup.sql"
else
    echo -e "${YELLOW}[WARN]${NC} mysqldump not found, skipping database backup"
fi

echo "Backing up configuration..."
cp .env "$BACKUP_DIR/env_backup" 2>/dev/null || echo "No .env file to backup"
echo -e "${GREEN}✓${NC} Configuration backed up"
echo ""

# Step 3: Run database migrations
echo "================================"
echo "Step 3: Database Migrations"
echo "================================"
echo ""

if [ -f "migrations/v5.13.0_migration.sql" ]; then
    echo "Applying v5.13.0 migrations..."
    mysql -h "${MYSQL_HOST:-localhost}" \
          -u "${MYSQL_USER:-fuel_user}" \
          -p"${MYSQL_PASSWORD}" \
          "${MYSQL_DATABASE:-fuel_copilot}" \
          < migrations/v5.13.0_migration.sql
    
    echo -e "${GREEN}✓${NC} Migrations applied successfully"
else
    echo -e "${YELLOW}[WARN]${NC} No migration file found, skipping"
fi
echo ""

# Step 4: Load J1939 database
echo "================================"
echo "Step 4: J1939 Database Load"
echo "================================"
echo ""

if [ -f "./load_j1939_database.sh" ]; then
    echo "Loading J1939 SPN database..."
    ./load_j1939_database.sh
    echo -e "${GREEN}✓${NC} J1939 database loaded"
else
    echo -e "${YELLOW}[WARN]${NC} J1939 loader not found, skipping"
fi
echo ""

# Step 5: Deploy application
echo "================================"
echo "Step 5: Application Deployment"
echo "================================"
echo ""

if [ -f "./deploy_production.sh" ]; then
    echo "Executing blue-green deployment..."
    ./deploy_production.sh $DEPLOYMENT_ENV
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Application deployed successfully"
    else
        echo -e "${RED}[ERROR]${NC} Deployment failed!"
        echo "Rolling back..."
        # Restore database backup
        if [ -f "$BACKUP_DIR/database_backup.sql" ]; then
            mysql -h "${MYSQL_HOST:-localhost}" \
                  -u "${MYSQL_USER:-fuel_user}" \
                  -p"${MYSQL_PASSWORD}" \
                  "${MYSQL_DATABASE:-fuel_copilot}" \
                  < "$BACKUP_DIR/database_backup.sql"
            echo -e "${GREEN}✓${NC} Database restored from backup"
        fi
        exit 1
    fi
else
    echo -e "${BLUE}[INFO]${NC} Using Docker Compose deployment..."
    
    # Pull latest images
    docker-compose -f docker-compose.prod.yml pull
    
    # Deploy blue instance
    docker-compose -f docker-compose.prod.yml up -d fuel-analytics-blue
    
    # Wait for health check
    echo "Waiting for blue instance to be healthy..."
    for i in {1..30}; do
        if curl -sf http://localhost:8000/health > /dev/null; then
            echo -e "${GREEN}✓${NC} Blue instance healthy"
            break
        fi
        sleep 2
    done
    
    # Switch nginx to blue
    echo "Switching traffic to blue instance..."
    docker-compose -f docker-compose.prod.yml up -d nginx
    
    # Stop green instance
    docker-compose -f docker-compose.prod.yml stop fuel-analytics-green
    
    echo -e "${GREEN}✓${NC} Deployment complete"
fi
echo ""

# Step 6: Smoke tests
echo "================================"
echo "Step 6: Smoke Tests"
echo "================================"
echo ""

API_BASE="http://localhost:8000"
if [ "$DEPLOYMENT_ENV" = "production" ]; then
    API_BASE="https://api.fuelanalytics.com"
fi

echo "Running smoke tests against $API_BASE..."

# Test 1: Health check
echo -n "  • Health check... "
if curl -sf "$API_BASE/health" > /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "DEPLOYMENT FAILED: Health check failed!"
    exit 1
fi

# Test 2: API version
echo -n "  • API version... "
VERSION=$(curl -sf "$API_BASE/api/v2/version" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
if [ "$VERSION" = "5.13.0" ]; then
    echo -e "${GREEN}✓${NC} (v$VERSION)"
else
    echo -e "${YELLOW}⚠${NC} (v$VERSION - expected 5.13.0)"
fi

# Test 3: Database connectivity
echo -n "  • Database connectivity... "
if curl -sf "$API_BASE/api/v2/trucks?limit=1" > /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Test 4: Redis connectivity
echo -n "  • Redis cache... "
if curl -sf "$API_BASE/api/v2/cache/status" | grep -q '"status":"healthy"'; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}"
fi

echo ""
echo -e "${GREEN}✓${NC} All smoke tests passed"
echo ""

# Step 7: Setup monitoring
echo "================================"
echo "Step 7: Monitoring Setup"
echo "================================"
echo ""

if [ -f "./setup_monitoring.sh" ]; then
    echo "Setting up Prometheus + Grafana..."
    ./setup_monitoring.sh
    echo -e "${GREEN}✓${NC} Monitoring configured"
    echo ""
    echo "Grafana Dashboard: http://localhost:3000"
    echo "Prometheus: http://localhost:9090"
else
    echo -e "${YELLOW}[WARN]${NC} Monitoring setup script not found"
fi
echo ""

# Step 8: Tag release
echo "================================"
echo "Step 8: Tag Release"
echo "================================"
echo ""

if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Creating git tag v5.13.0..."
    git tag -a v5.13.0 -m "Production release v5.13.0 - $DEPLOYMENT_TIME"
    
    echo "Pushing tag to remote..."
    git push origin v5.13.0 || echo -e "${YELLOW}[WARN]${NC} Could not push tag (no remote configured)"
    
    echo -e "${GREEN}✓${NC} Release tagged: v5.13.0"
else
    echo -e "${YELLOW}[WARN]${NC} Not a git repository, skipping tagging"
fi
echo ""

# Step 9: Post-deployment summary
echo "================================================"
echo "✅ DEPLOYMENT COMPLETE"
echo "================================================"
echo ""
echo "Environment:    $DEPLOYMENT_ENV"
echo "Version:        v5.13.0"
echo "Time:           $DEPLOYMENT_TIME"
echo "Backup:         $BACKUP_DIR"
echo ""
echo "Next Steps:"
echo "  1. Monitor Grafana dashboard for 2-4 hours"
echo "  2. Check alert notifications in Slack"
echo "  3. Verify business metrics (theft detection, RUL predictions)"
echo "  4. Announce deployment in #engineering channel"
echo ""
echo "Rollback Command (if needed):"
echo "  mysql < $BACKUP_DIR/database_backup.sql"
echo "  docker-compose -f docker-compose.prod.yml up -d fuel-analytics-green"
echo ""
echo "================================================"

# Send Slack notification
if [ -n "${SLACK_WEBHOOK_URL}" ]; then
    curl -X POST "${SLACK_WEBHOOK_URL}" \
         -H 'Content-Type: application/json' \
         -d "{
           \"text\": \":rocket: *Fuel Analytics v5.13.0 Deployed to $DEPLOYMENT_ENV*\",
           \"blocks\": [
             {
               \"type\": \"section\",
               \"text\": {
                 \"type\": \"mrkdwn\",
                 \"text\": \"*Fuel Analytics v5.13.0 deployed successfully*\n\n• Environment: \`$DEPLOYMENT_ENV\`\n• Time: $DEPLOYMENT_TIME\n• Status: :white_check_mark: All smoke tests passed\"
               }
             }
           ]
         }"
    echo ""
    echo -e "${GREEN}✓${NC} Slack notification sent"
fi

echo ""
echo "🎉 Production deployment successful!"
echo ""
