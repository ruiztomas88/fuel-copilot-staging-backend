# 🚀 DEPLOYMENT GUIDE - PRODUCTION

**Fecha:** 23 Diciembre 2025  
**Cambios:** Audit P0 fixes + Memory cleanup implementation  
**Versión:** v6.5.0

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### ✅ Verificaciones Locales (COMPLETADAS)

- [x] Todos los bugs P0 verificados/corregidos
- [x] Tests unitarios pasando (`test_p1_p3_fixes.py`)
- [x] Cleanup implementado en 5 engines
- [x] Cleanup orchestrator creado
- [x] Git working tree clean
- [x] Commit y push completados

### ⏳ Verificaciones Pre-Deploy

```bash
# 1. Verificar estado del repositorio
git status
git log --oneline -5

# 2. Ejecutar tests de integración
python tests/test_cleanup_integration.py

# 3. Verificar que no hay archivos sin commit
git diff
```

---

## 🎯 DEPLOYMENT PASO A PASO

### PASO 1: Backup de Base de Datos 🔒

**Ubicación:** VM de producción  
**Usuario:** root o usuario con permisos MySQL

```bash
# Conectar a VM
ssh usuario@vm-production-ip

# Crear directorio de backups si no existe
mkdir -p ~/backups

# Backup completo de la base de datos
mysqldump -u root -p fuel_copilot > ~/backups/fuel_copilot_backup_$(date +%Y%m%d_%H%M%S).sql

# Verificar tamaño del backup
ls -lh ~/backups/fuel_copilot_backup_*.sql | tail -1

# Comprimir backup (opcional)
gzip ~/backups/fuel_copilot_backup_$(date +%Y%m%d_%H%M%S).sql
```

**Tiempo estimado:** 2-5 minutos

---

### PASO 2: Detener Servicios Backend

```bash
# Ver estado actual
sudo systemctl status fuel-analytics-backend
sudo systemctl status wialon-sync

# Detener servicios
sudo systemctl stop fuel-analytics-backend
sudo systemctl stop wialon-sync

# Verificar que están detenidos
sudo systemctl is-active fuel-analytics-backend
# Debería mostrar: inactive
```

**Tiempo estimado:** 30 segundos

---

### PASO 3: Pull de Cambios

```bash
# Ir al directorio del proyecto
cd /path/to/fuel-analytics-backend

# Verificar branch actual
git branch
# Debería mostrar: * main

# Hacer backup del código actual
cp -r . ../fuel-analytics-backend.backup.$(date +%Y%m%d_%H%M%S)

# Pull de cambios
git pull origin main

# Verificar cambios descargados
git log --oneline -5
# Deberías ver: 62a3d9e ✅ Verificación completa P0 bugs...
```

**Tiempo estimado:** 1-2 minutos

---

### PASO 4: Actualizar Dependencias (si es necesario)

```bash
# Activar virtual environment
source venv/bin/activate

# Actualizar dependencias
pip install -r requirements.txt --upgrade

# Verificar versiones críticas
python -c "import pymysql; print(f'PyMySQL: {pymysql.__version__}')"
python -c "import yaml; print('PyYAML: OK')"
```

**Tiempo estimado:** 1-3 minutos

---

### PASO 5: Ejecutar Tests Pre-Deploy

```bash
# Tests de integración
python tests/test_cleanup_integration.py

# Tests unitarios P1-P3
python tests/test_p1_p3_fixes.py

# Si hay errores, NO continuar con deployment
# Investigar y resolver primero
```

**Tiempo estimado:** 2-3 minutos

---

### PASO 6: Iniciar Servicios

```bash
# Iniciar servicios en orden
sudo systemctl start fuel-analytics-backend
sudo systemctl start wialon-sync

# Verificar que iniciaron correctamente
sudo systemctl status fuel-analytics-backend
sudo systemctl status wialon-sync

# Ambos deberían mostrar: active (running)
```

**Tiempo estimado:** 1 minuto

---

### PASO 7: Monitoreo Post-Deploy (CRÍTICO)

**Primeros 10 minutos - Monitoreo activo:**

```bash
# Terminal 1: Ver logs del backend
journalctl -u fuel-analytics-backend -f

# Terminal 2: Ver logs de wialon-sync
journalctl -u wialon-sync -f

# Terminal 3: Monitorear memoria/CPU
watch -n 5 'ps aux | grep -E "python|fuel" | grep -v grep'
```

**Qué buscar:**

- ✅ `INFO` logs normales
- ✅ `Processing truck X...` mensajes
- ✅ No hay tracebacks de Python
- ✅ No hay errores de conexión MySQL
- ⚠️ Si ves `ERROR` o `CRITICAL` → investigar inmediatamente

**Tiempo de monitoreo:** 10-15 minutos

---

### PASO 8: Validación Funcional

```bash
# 1. Verificar que hay datos recientes en DB
mysql -u root -p fuel_copilot -e "
SELECT COUNT(*) as recent_readings,
       MAX(timestamp_utc) as last_update
FROM fuel_metrics
WHERE timestamp_utc > NOW() - INTERVAL 10 MINUTE;
"

# Debería mostrar:
# recent_readings > 0
# last_update = fecha/hora reciente

# 2. Verificar API (si está expuesta)
curl http://localhost:5000/health
# Debería devolver: {"status": "ok"}

# 3. Verificar logs de cleanup orchestrator
grep -i "cleanup" /var/log/fuel-analytics/*.log | tail -20
```

**Tiempo estimado:** 3-5 minutos

---

## 🧹 EJECUTAR CLEANUP MANUAL (Primera Vez)

```bash
# Activar venv
source venv/bin/activate

# Ejecutar cleanup orchestrator
python cleanup_orchestrator.py

# Debería mostrar:
# 🧹 MEMORY CLEANUP ORCHESTRATOR
# ✅ Active trucks: X
# 📊 CLEANUP RESULTS
#    driver_behavior: ✅ Cleaned Y trucks
#    ...
# TOTAL: Z inactive trucks removed
```

**Nota:** Después configurar crontab para ejecución automática (ver abajo)

---

## 📅 CONFIGURAR CLEANUP AUTOMÁTICO (Crontab)

```bash
# Editar crontab
crontab -e

# Agregar línea (ejecuta cada domingo a las 3:00 AM):
0 3 * * 0 cd /path/to/fuel-analytics-backend && /path/to/venv/bin/python cleanup_orchestrator.py >> /var/log/fuel-analytics/cleanup.log 2>&1

# Verificar crontab
crontab -l
```

**Alternativa con systemd timer:**

```bash
# Crear archivo: /etc/systemd/system/fuel-cleanup.service
[Unit]
Description=Fuel Analytics Memory Cleanup
After=network.target

[Service]
Type=oneshot
User=fuel-analytics
WorkingDirectory=/path/to/fuel-analytics-backend
ExecStart=/path/to/venv/bin/python cleanup_orchestrator.py

# Crear archivo: /etc/systemd/system/fuel-cleanup.timer
[Unit]
Description=Run Fuel Analytics Cleanup Weekly

[Timer]
OnCalendar=Sun *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target

# Habilitar timer
sudo systemctl enable fuel-cleanup.timer
sudo systemctl start fuel-cleanup.timer

# Verificar
sudo systemctl list-timers | grep fuel-cleanup
```

---

## 🚨 ROLLBACK PROCEDURE (Si algo sale mal)

```bash
# 1. Detener servicios
sudo systemctl stop fuel-analytics-backend
sudo systemctl stop wialon-sync

# 2. Restaurar código anterior
cd /path/to/fuel-analytics-backend
rm -rf *
cp -r ../fuel-analytics-backend.backup.YYYYMMDD_HHMMSS/* .

# 3. Restaurar base de datos (si es necesario)
mysql -u root -p fuel_copilot < ~/backups/fuel_copilot_backup_YYYYMMDD_HHMMSS.sql

# 4. Reiniciar servicios
sudo systemctl start fuel-analytics-backend
sudo systemctl start wialon-sync

# 5. Verificar logs
journalctl -u fuel-analytics-backend -f
```

---

## 📊 POST-DEPLOYMENT MONITORING (Primeras 48 horas)

### Día 1 - Monitoreo Intensivo

- [ ] Revisar logs cada 2 horas
- [ ] Verificar que no hay memory leaks (htop/top)
- [ ] Confirmar que datos fluyen normalmente
- [ ] Verificar alertas en sistema de monitoreo

### Día 2 - Monitoreo Normal

- [ ] Revisar logs 2 veces al día
- [ ] Verificar métricas de sistema
- [ ] Confirmar que cleanup orchestrator funcionó (si se ejecutó)

### Comandos útiles:

```bash
# Ver uso de memoria
free -h
ps aux --sort=-%mem | head -10

# Ver errores en logs
journalctl -u fuel-analytics-backend --since "1 hour ago" | grep -i error

# Ver uso de disco
df -h
du -sh /path/to/fuel-analytics-backend/*
```

---

## ✅ DEPLOYMENT CHECKLIST FINAL

- [ ] Backup de DB completado y verificado
- [ ] Servicios detenidos correctamente
- [ ] Git pull ejecutado (commit 62a3d9e visible)
- [ ] Tests de integración pasados
- [ ] Servicios reiniciados y activos
- [ ] Logs sin errores críticos (10 min monitoreo)
- [ ] Validación funcional OK (datos recientes en DB)
- [ ] Cleanup manual ejecutado exitosamente
- [ ] Crontab/systemd timer configurado
- [ ] Monitoreo día 1 programado

---

## 📞 CONTACTO EN CASO DE PROBLEMAS

**Si encuentras errores durante deployment:**

1. **NO PANIC** - Tienes backup de código y DB
2. Capturar logs: `journalctl -u fuel-analytics-backend --since "10 minutes ago" > error_logs.txt`
3. Revisar error específico
4. Si no puedes resolver en 15 min → ejecutar ROLLBACK
5. Documentar el problema para análisis posterior

---

## 📝 REGISTRO DE DEPLOYMENT

**Fecha de deployment:** ******\_******  
**Hora de inicio:** ******\_******  
**Hora de finalización:** ******\_******  
**Realizado por:** ******\_******  
**Resultado:** ✅ Exitoso / ❌ Rollback  
**Notas:**

```
[Agregar cualquier observación relevante]
```

---

**LISTO PARA DEPLOYMENT** 🚀

**Tiempo total estimado:** 20-30 minutos  
**Ventana de mantenimiento sugerida:** Domingo 3:00-4:00 AM (menor tráfico)
