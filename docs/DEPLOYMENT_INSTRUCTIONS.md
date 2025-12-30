# 🚀 DEPLOYMENT INSTRUCTIONS - AUDIT FIXES
## Fecha: 23 Diciembre 2025

---

## ⚠️ PRE-REQUISITOS

Antes de deployar, asegúrate de:
- [ ] Backup de base de datos completo
- [ ] Acceso SSH a servidor de producción
- [ ] Variables de entorno configuradas
- [ ] Código en branch principal actualizado

---

## 📋 CHECKLIST DE DEPLOYMENT

### 1️⃣ BACKEND (Este Repositorio)

#### A. Configurar Variables de Entorno
```bash
# En servidor de producción
sudo nano /etc/environment

# Añadir:
DB_PASSWORD=FuelCopilot2025!
WIALON_MYSQL_PASSWORD=Tomas2025
```

O si usas `.env`:
```bash
cd /path/to/fuel-analytics-backend
nano .env

# Añadir:
DB_PASSWORD=FuelCopilot2025!
WIALON_MYSQL_PASSWORD=Tomas2025
```

#### B. Pull y Deploy Backend
```bash
# En servidor
cd /path/to/fuel-analytics-backend
git pull origin main

# Restart servicios
sudo systemctl restart fuel-analytics
sudo systemctl restart wialon-sync

# Verificar logs
sudo journalctl -u fuel-analytics -f
```

#### C. Ejecutar Limpieza de Base de Datos
```bash
# Conectar a MySQL
mysql -u fuel_admin -p fuel_copilot

# Ejecutar script de limpieza
source scripts/cleanup_mpg_corruption.sql

# O desde línea de comandos:
mysql -u fuel_admin -p fuel_copilot < scripts/cleanup_mpg_corruption.sql
```

**Verificación:**
```sql
-- Debe retornar 0
SELECT COUNT(*) FROM fuel_metrics 
WHERE mpg_current > 8.5 OR mpg_current < 2.5;
```

---

### 2️⃣ FRONTEND (Repositorio Separado)

⚠️ **IMPORTANTE:** El frontend está en un repositorio separado.

#### A. Copiar Helper de Confidence
```bash
# Desde este repo, copiar:
# CONFIDENCE_HELPERS_FOR_FRONTEND.ts
# 
# Hacia:
# frontend/src/utils/confidenceHelpers.ts
```

#### B. Actualizar Componentes

**Archivo 1:** `src/pages/MaintenanceDashboard.tsx`

```typescript
// AÑADIR al inicio:
import { displayConfidence, styleConfidence, getConfidenceColor, getConfidenceBgColor } from '../utils/confidenceHelpers';

// LÍNEA 157 - Cambiar:
{(p.confidence * 100).toFixed(0)}%
// Por:
<span className={getConfidenceColor(p.confidence)}>
  {displayConfidence(p.confidence)}
</span>

// LÍNEA 234 - Cambiar:
{(summary.avgConfidence * 100).toFixed(0)}%
// Por:
{displayConfidence(summary.avgConfidence)}

// LÍNEA 366 - Cambiar:
{(event.confidence * 100).toFixed(0)}%
// Por:
{displayConfidence(event.confidence)}
```

**Archivo 2:** `src/pages/PredictiveMaintenanceUnified.tsx`

```typescript
// AÑADIR al inicio:
import { displayConfidence, styleConfidence } from '../utils/confidenceHelpers';

// LÍNEA 260 - Cambiar:
style={{ width: `${alert.confidence * 100}%` }}
// Por:
style={{ width: `${styleConfidence(alert.confidence)}%` }}

// LÍNEA 264 - Cambiar:
{(alert.confidence * 100).toFixed(0)}%
// Por:
{displayConfidence(alert.confidence)}
```

**Archivo 3:** `src/pages/AlertSettings.tsx`

```typescript
// AÑADIR al inicio:
import { displayConfidence } from '../utils/confidenceHelpers';

// LÍNEA 219 - Cambiar:
{(settings?.thresholds.theft_confidence_min || 0) * 100}%
// Por:
{displayConfidence(settings?.thresholds.theft_confidence_min)}
```

#### C. Build y Deploy Frontend
```bash
cd /path/to/frontend
npm run build
# Deploy según tu proceso (Vercel, Netlify, etc.)
```

---

## 🧪 TESTING POST-DEPLOYMENT

### Test 1: MPG Values
```bash
# Conectar a base de datos
mysql -u fuel_admin -p fuel_copilot

# Ejecutar:
SELECT 
    truck_id,
    COUNT(*) as records,
    MIN(mpg_current) as min_mpg,
    MAX(mpg_current) as max_mpg,
    AVG(mpg_current) as avg_mpg
FROM fuel_metrics
WHERE timestamp_utc > NOW() - INTERVAL 1 HOUR
  AND mpg_current IS NOT NULL
GROUP BY truck_id;
```

**Esperado:**
- `max_mpg` <= 8.2 para TODOS los trucks
- `min_mpg` >= 3.8 (o NULL)
- `avg_mpg` entre 4.5-7.0

---

### Test 2: Confidence Display (Frontend)
1. Abrir dashboard de mantenimiento predictivo
2. Verificar que todas las alertas muestran confidence 0-100%
3. Verificar que NO hay valores >100%
4. Verificar que progress bars no exceden container

**Ejemplo esperado:**
```
✅ Oil Pressure Alert: 85% confidence
✅ Coolant Temp: 92% confidence
❌ NO: 9500% confidence
```

---

### Test 3: Credentials
```bash
# Verificar que NO hay passwords hardcoded
grep -r "password.*=.*['\"].*2025" *.py
# Debe retornar: (vacío)

# Verificar que servicios usan env vars
# En logs debe aparecer:
# "Connecting to database using environment credentials"
```

---

## 🔄 ROLLBACK PLAN

Si algo falla:

### Rollback Backend
```bash
cd /path/to/fuel-analytics-backend
git log --oneline  # Ver commits
git revert <commit-hash>
sudo systemctl restart fuel-analytics
```

### Rollback Base de Datos
```sql
-- Si creaste backup antes de cleanup:
DROP TABLE fuel_metrics;
RENAME TABLE fuel_metrics_backup TO fuel_metrics;
```

### Rollback Frontend
```bash
# Deploy versión anterior
git checkout <previous-commit>
npm run build
# Deploy
```

---

## 📊 MONITORING

### Métricas a Monitorear (primeras 24h)

1. **MPG Values**
   ```sql
   -- Cada hora, verificar:
   SELECT MAX(mpg_current) FROM fuel_metrics 
   WHERE timestamp_utc > NOW() - INTERVAL 1 HOUR;
   -- Debe ser <= 8.2
   ```

2. **Service Logs**
   ```bash
   # Verificar NO hay errores de credenciales
   sudo journalctl -u fuel-analytics --since "1 hour ago" | grep -i "password\|auth"
   ```

3. **Frontend Console**
   - Abrir DevTools
   - Verificar NO hay errores de "NaN" o "undefined confidence"

---

## ✅ VALIDATION CHECKLIST

Después de deployment, verificar:

### Backend
- [ ] Servicios iniciaron correctamente
- [ ] No hay errores en logs
- [ ] MPG values <= 8.2
- [ ] Credentials desde env vars

### Base de Datos
- [ ] Script de limpieza ejecutado
- [ ] No hay MPG > 8.5
- [ ] No hay MPG < 2.5
- [ ] No hay MPG = 7.8 exacto

### Frontend
- [ ] Confidence muestra 0-100%
- [ ] No hay valores >100%
- [ ] Progress bars correctos
- [ ] No errores en console

---

## 🆘 TROUBLESHOOTING

### Problema: Servicios no inician
```bash
# Verificar env vars
printenv | grep PASSWORD

# Si no están configuradas:
export DB_PASSWORD='FuelCopilot2025!'
export WIALON_MYSQL_PASSWORD='Tomas2025'

# O añadir a systemd service:
sudo nano /etc/systemd/system/fuel-analytics.service
# Añadir bajo [Service]:
Environment="DB_PASSWORD=FuelCopilot2025!"
Environment="WIALON_MYSQL_PASSWORD=Tomas2025"

sudo systemctl daemon-reload
sudo systemctl restart fuel-analytics
```

### Problema: MPG siguen altos
```sql
-- Verificar que se ejecutó limpieza:
SELECT COUNT(*) FROM fuel_metrics WHERE mpg_current > 8.5;
-- Si retorna > 0, ejecutar de nuevo:
source scripts/cleanup_mpg_corruption.sql
```

### Problema: Frontend muestra NaN
```javascript
// Verificar que se importó helper:
import { displayConfidence } from '../utils/confidenceHelpers';

// Verificar que se usa:
{displayConfidence(alert.confidence)}  // ✅
{alert.confidence * 100}%             // ❌
```

---

## 📞 CONTACTO

Si encuentras problemas:
1. Revisar logs: `sudo journalctl -u fuel-analytics -f`
2. Verificar errores SQL
3. Contactar a DevOps/Backend team

---

## 📚 DOCUMENTACIÓN RELACIONADA

- `AUDIT_FIXES_SUMMARY.md` - Resumen completo de fixes
- `MANUAL_AUDITORIA_COMPLETO.md` - Auditoría original
- `scripts/cleanup_mpg_corruption.sql` - Script de limpieza DB
- `CONFIDENCE_HELPERS_FOR_FRONTEND.ts` - Helper TypeScript

---

**Última actualización:** 23 Diciembre 2025  
**Preparado por:** Claude (Anthropic)  
**Estado:** ✅ Listo para deployment
