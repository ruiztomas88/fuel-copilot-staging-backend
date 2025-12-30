# 🚀 Instrucciones de Deployment - Fuel Analytics v7.1.0

## 📋 Pre-requisitos

### 1. Variables de Entorno (CRÍTICO)
Crear/actualizar archivo `.env` en el directorio del backend:

```bash
# Seguridad - OBLIGATORIO
MYSQL_PASSWORD=tu_password_seguro_aqui
ALLOWED_ORIGINS=https://fuelanalytics.fleetbooster.net
ENVIRONMENT=production

# Opcional - para features futuras
FUEL_PRICE_API_KEY=  # Dejar vacío por ahora
```

**⚠️ IMPORTANTE**: Ya no hay passwords hardcodeados. Si falta `MYSQL_PASSWORD`, el backend lanzará RuntimeError.

### 2. Dependencias Python Nuevas
```bash
# En la VM backend
cd /ruta/al/backend
pip install scikit-learn==1.3.2
pip install numpy==1.24.3
```

### 3. Verificar Instalación Existente
```bash
# Verificar que estos paquetes ya estén instalados
pip show fastapi uvicorn mysql-connector-python requests
```

---

## 🔧 Pasos de Deployment Backend

### Paso 0: Limpiar caché de Python (CRÍTICO)
```bash
# IMPORTANTE: Eliminar __pycache__ ANTES del pull para evitar errores
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

# En Windows PowerShell:
Get-ChildItem -Path . -Filter __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Filter *.pyc -Recurse | Remove-Item -Force
```

### Paso 1: Pull del código
```bash
cd /ruta/al/backend
git pull origin main
```

### Paso 2: Configurar Variables de Entorno
```bash
# Crear archivo .env si no existe
nano .env

# Agregar las variables (ver sección Pre-requisitos)
# Guardar con Ctrl+X, Y, Enter
```

### Paso 3: Verificar configuración
```bash
# Verificar que el archivo existe
cat .env

# Verificar permisos (solo el usuario debe leer)
chmod 600 .env
```

### Paso 4: Instalar nuevas dependencias
```bash
pip install scikit-learn==1.3.2 numpy==1.24.3
```

### Paso 5: Reiniciar el servicio backend
```bash
# Si usas systemd
sudo systemctl restart fuel-analytics-backend

# Si usas PM2
pm2 restart fuel-analytics-backend

# Si ejecutas manualmente con uvicorn
pkill -f uvicorn  # Matar proceso anterior
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 &

# Verificar que esté corriendo
ps aux | grep uvicorn
```

### Paso 6: Verificar logs
```bash
# systemd
sudo journalctl -u fuel-analytics-backend -f

# PM2
pm2 logs fuel-analytics-backend

# Manual (si usaste nohup)
tail -f nohup.out
```

### Paso 7: Verificar endpoints nuevos
```bash
# Test predictive maintenance
curl http://localhost:8000/api/v2/trucks/DO9693/predictive-maintenance

# Test fleet summary
curl http://localhost:8000/api/v2/fleet/predictive-maintenance-summary
```

---

## 🎨 Pasos de Deployment Frontend

### Paso 1: Pull del código
```bash
cd /ruta/al/frontend
git pull origin main
```

### Paso 2: Instalar dependencias (si hay nuevas)
```bash
npm install
```

### Paso 3: Build para producción
```bash
npm run build
```

### Paso 4: Desplegar build
```bash
# Si usas Netlify
netlify deploy --prod

# Si usas Vercel
vercel --prod

# Si usas servidor propio
rsync -avz dist/ usuario@servidor:/var/www/fuelanalytics/
```

### Paso 5: Verificar navegación
Abrir en el browser y verificar:
- ✅ `/metrics-detail` - Nueva página con 4 tabs
- ✅ `/truck/DO9693` - Sensores deben mostrar edad cuando están stale
- ✅ `/command-center` - Verificar que no haya errores

---

## 🧪 Verificación Post-Deployment

### Backend Health Check
```bash
# 1. Verificar que el servidor responde
curl http://localhost:8000/health

# 2. Verificar credenciales seguras (NO debe haber passwords)
grep -r "FuelCopilot2025" *.py
# Debe retornar 0 resultados

# 3. Verificar CORS
curl -H "Origin: https://fuelanalytics.fleetbooster.net" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:8000/api/v2/trucks

# 4. Test algoritmos nuevos
curl http://localhost:8000/api/v2/trucks/DO9693/predictive-maintenance | jq
```

### Frontend Health Check
```bash
# 1. Verificar que el build fue exitoso
ls -lh dist/

# 2. Verificar tamaño del bundle (debe ser < 2MB)
du -sh dist/assets/

# 3. Verificar que los componentes nuevos están en el bundle
grep -r "MetricsOverview" dist/assets/*.js
```

---

## 🔄 Configuración de Cron Jobs (Recomendado)

### 1. Cleanup de Pending Drops (cada 24 horas)
```bash
crontab -e

# Agregar esta línea:
0 2 * * * cd /ruta/al/backend && python -c "from alert_service import AlertService; AlertService().cleanup_stale_drops(24.0)"
```

### 2. Backup de Base de Datos (diario)
```bash
# Ya existe auto_backup_db.py, solo asegurar que esté en cron
0 3 * * * cd /ruta/al/backend && python auto_backup_db.py
```

---

## 📊 Monitoreo Post-Deployment (Primeras 48 horas)

### KPIs a Monitorear:
1. **Theft Detection False Positives**: Objetivo <10%
   - Revisar alertas de robo en `/command-center`
   - Verificar que no haya demasiados falsos positivos

2. **Predictive Maintenance Accuracy**:
   - Verificar que las alertas sean coherentes (30+ días anticipación)
   - Comparar RUL (Remaining Useful Life) con mantenimientos reales

3. **Fleet Score**:
   - Abrir `/metrics-detail`
   - Verificar que el score (0-100) sea razonable
   - Comparar con baseline histórico

4. **Sensor Display**:
   - Abrir `/truck/DO9693` cuando ECU esté offline
   - Verificar que muestre "46 PSI ⏰ 3h ago" en lugar de "N/A"

---

## 🐛 Troubleshooting Común

### Error: "MYSQL_PASSWORD environment variable not set"
```bash
# Verificar que .env existe
cat .env | grep MYSQL_PASSWORD

# Si no existe, crearlo:
echo "MYSQL_PASSWORD=tu_password" >> .env

# Reiniciar servicio
sudo systemctl restart fuel-analytics-backend
```

### Error: "ModuleNotFoundError: No module named 'sklearn'"
```bash
pip install scikit-learn==1.3.2
```

### Error: CORS blocked in browser console
```bash
# Verificar ALLOWED_ORIGINS en .env
cat .env | grep ALLOWED_ORIGINS

# Debe ser:
ALLOWED_ORIGINS=https://fuelanalytics.fleetbooster.net

# Si está mal, corregir y reiniciar
sudo systemctl restart fuel-analytics-backend
```

### Frontend muestra página blanca
```bash
# Verificar que el build fue exitoso
npm run build

# Verificar console del browser (F12)
# Buscar errores de importación

# Verificar que la ruta /metrics-detail está en App.tsx
grep "metrics-detail" src/App.tsx
```

---

## 📈 ROI Esperado (Primeros 3 meses)

### Predictive Maintenance:
- **Meta**: Evitar 1 falla mayor por truck
- **Ahorro**: $5,000-10,000 por falla evitada
- **Flota 15 trucks**: $75K-150K

### Theft Detection Mejorado:
- **Reducción falsos positivos**: 67% (25% → 8%)
- **Ahorro tiempo admin**: ~10 horas/mes
- **Valor**: $1,500/mes

### Idle Engine Optimization:
- **Reducción idle improductivo**: 15-30%
- **Ahorro combustible**: $500-1,200 por truck/año
- **Flota 15 trucks**: $7.5K-18K/año

**TOTAL ANUALIZADO**: $267K-555K para 15 trucks

---

## 🔐 Checklist Final Pre-Launch

- [ ] `.env` configurado con MYSQL_PASSWORD
- [ ] `scikit-learn` y `numpy` instalados
- [ ] Backend reiniciado sin errores
- [ ] Endpoints `/api/v2/trucks/{id}/predictive-maintenance` funcionan
- [ ] CORS configurado para dominio de producción
- [ ] Frontend build exitoso
- [ ] Ruta `/metrics-detail` accesible
- [ ] Sensores muestran edad correctamente en TruckDetail
- [ ] Cron job de cleanup configurado
- [ ] Logs monitoreados por 24 horas

---

## 📞 Contacto de Emergencia

Si algo falla crítico:
1. Rollback a versión anterior: `git checkout HEAD~1`
2. Reiniciar servicios
3. Revisar logs: `sudo journalctl -u fuel-analytics-backend -n 100`

**Versión anterior estable**: commit antes de `0a00213` (v7.0)

---

**Fecha de Deployment Planeado**: _________________  
**Responsable**: _________________  
**Backup Completado**: [ ] Sí [ ] No  
**Testing Completado**: [ ] Sí [ ] No  
