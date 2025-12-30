# ✅ QUICK DEPLOYMENT CHECKLIST
## 23 Diciembre 2025

---

## 📋 PRE-DEPLOYMENT

- [ ] **Backup completo de base de datos**
  ```bash
  mysqldump -u fuel_admin -p fuel_copilot > backup_$(date +%Y%m%d).sql
  ```

- [ ] **Git pull en servidor**
  ```bash
  cd /path/to/fuel-analytics-backend
  git pull origin main
  ```

---

## 🔧 DEPLOYMENT STEPS

### 1. Variables de Entorno (5 min)
- [ ] Configurar `DB_PASSWORD=FuelCopilot2025!`
- [ ] Configurar `WIALON_MYSQL_PASSWORD=Tomas2025`
- [ ] Verificar: `printenv | grep PASSWORD`

### 2. Limpieza Base de Datos (10 min)
- [ ] Ejecutar: `mysql -u fuel_admin -p < scripts/cleanup_mpg_corruption.sql`
- [ ] Verificar: `SELECT MAX(mpg_current) FROM fuel_metrics;` → debe ser ≤8.2

### 3. Restart Servicios (5 min)
- [ ] `sudo systemctl restart fuel-analytics`
- [ ] `sudo systemctl restart wialon-sync`
- [ ] Verificar logs: `sudo journalctl -u fuel-analytics -f`

### 4. Frontend (si aplica) (15 min)
- [ ] Copiar `CONFIDENCE_HELPERS_FOR_FRONTEND.ts` al repo frontend
- [ ] Actualizar `MaintenanceDashboard.tsx` (3 lugares)
- [ ] Actualizar `PredictiveMaintenanceUnified.tsx` (2 lugares)
- [ ] Actualizar `AlertSettings.tsx` (1 lugar)
- [ ] Build y deploy frontend

---

## ✅ POST-DEPLOYMENT VERIFICATION

### Inmediato (primeros 5 min)
- [ ] Servicios corriendo: `systemctl status fuel-analytics`
- [ ] No errores en logs: `journalctl -u fuel-analytics --since "5 min ago"`
- [ ] DB conectando con env vars (no hardcoded)

### Primera hora
- [ ] MPG values ≤8.2: 
  ```sql
  SELECT MAX(mpg_current) FROM fuel_metrics 
  WHERE timestamp_utc > NOW() - INTERVAL 1 HOUR;
  ```
- [ ] Frontend muestra confidence 0-100% (no >100%)

### Primeras 24 horas
- [ ] Monitorear MPG trends
- [ ] Verificar no hay crashes por NaN
- [ ] Confirmar no hay memory leaks

---

## 🆘 ROLLBACK (si algo falla)

```bash
# Backend
cd /path/to/fuel-analytics-backend
git revert HEAD
sudo systemctl restart fuel-analytics

# Database
mysql -u fuel_admin -p fuel_copilot < backup_20251223.sql
```

---

## 📞 DOCUMENTACIÓN

Ver detalles en:
- `AUDIT_FIXES_SUMMARY.md` - Detalles técnicos
- `DEPLOYMENT_INSTRUCTIONS.md` - Guía completa
- `FIXES_EXECUTIVE_SUMMARY.md` - Resumen ejecutivo

---

**Tiempo estimado total:** 35-60 minutos  
**Riesgo:** 🟢 BAJO  
**Estado:** ✅ LISTO
